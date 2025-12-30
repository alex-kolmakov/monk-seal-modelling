from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional
import math
import random
from src.simulation.agents.movement import correlated_random_walk
from src.simulation.environment.utils import query_env_buffers


class SealState(Enum):
    FORAGING = "FORAGING"
    RESTING = "RESTING" # Short Naps (Sea or Land)
    SLEEPING = "SLEEPING" # Deep Sleep (Strictly Land)
    HAULING_OUT = "HAULING_OUT" # Transition to Land
    TRANSITING = "TRANSITING"
    NURSING = "NURSING"

class PupStage(Enum):
    NEWBORN = "NEWBORN"       # 0-2 months: Cave-bound, high mortality
    POST_MOLT = "POST_MOLT"   # 2-3 months: Near entrance
    TRANSITION = "TRANSITION" # 3-4.5 months: Learning to dive
    WEANED = "WEANED"         # > 4.5 months: Independent

@dataclass
class SealMemory:
    haulout_sites: List[Tuple[float, float]] = field(default_factory=list)
    high_hsi_patches: List[Tuple[float, float]] = field(default_factory=list)
    last_known_storm_pos: Optional[Tuple[float, float]] = None

class SealAgent:
    def __init__(self, agent_id: str, start_pos: Tuple[float, float], age: int = 5, sex: str = "F", mother=None):
        self.id = agent_id
        self.pos = start_pos 
        self.heading = random.uniform(0, 2 * math.pi)
        self.age = age
        self.sex = sex
        self.mother = mother
        
        # Physiological Parameters
        self.mass = 300.0 
        self.stomach_load = 0.0
        self.stomach_capacity = 15.0 
        
        # Energy
        if self.age == 0: # Is Pup
            self.energy = 10000.0 
            self.max_energy = 50000.0 
            self.pup_stage = PupStage.NEWBORN
            self.maternal_cave_pos = start_pos
        else:
            self.energy = 50000.0 
            self.max_energy = 100000.0 
            self.pup_stage = None
            self.maternal_cave_pos = None

        self.rmr = 753.0 
        
        # Parental State
        self.pup = None 
        self.foraging_timer = 0 
        
        # State
        self.state = SealState.FORAGING
        if self.age == 0:
            self.state = SealState.RESTING 
            
        self.memory = SealMemory()
        
        # Thresholds
        self.storm_threshold = 2.5 
        self.max_landing_swell = 4.0 
        self.age_in_hours = 0
        
    def update_with_buffers(self, env_buffers: Dict):
        """
        Multiprocessing-friendly update loop.
        Uses env_buffers (dict of numpy arrays) instead of Environment object.
        """
        self.age_in_hours += 1
        hour_of_day = self.age_in_hours % 24
        is_night = (hour_of_day >= 20 or hour_of_day < 6)
        
        if self.age_in_hours % (24 * 365) == 0:
            self.age += 1 

        # 1. Sense Environment at current pos
        env_data = query_env_buffers(self.pos[0], self.pos[1], env_buffers)

        # Pup Development
        if self.pup_stage:
            self.update_pup_development(env_data)
            if self.state == "DEAD": return

        swh = env_data.get('swh', 0.0)
        is_land = env_data.get('is_land', False)
        
        # Storm Logic
        if swh > self.max_landing_swell:
             if self.state == SealState.HAULING_OUT:
                 self.state = SealState.RESTING 
                 
        elif swh > self.storm_threshold:
             if not is_land and self.state != SealState.HAULING_OUT and self.state != SealState.SLEEPING:
                 self.state = SealState.HAULING_OUT

        self.burn_energy()
        if self.energy <= 0:
            self.state = "DEAD"
            return

        self.decide_activity(env_data, is_night, is_land)
        
        # Execute Action
        # Pass env_buffers to actions so they can query other locations
        if self.state == SealState.FORAGING:
            self.forage(env_data, env_buffers)
            
        elif self.state == SealState.RESTING:
            self.rest(env_data, env_buffers) 
            
        elif self.state == SealState.SLEEPING:
            self.sleep(env_data, env_buffers) 
            
        elif self.state == SealState.HAULING_OUT:
            self.haul_out_search(env_buffers)
            
        elif self.state == SealState.TRANSITING:
            self.transit(env_buffers)
            
        elif self.state == SealState.NURSING:
            self.nurse_pup_action(env_buffers)

    # Legacy update (wraps buffers call if needed, but we should use update_with_buffers mainly)
    def update(self, env_data, environment=None):
        # Fallback for old calls if any
        # Assuming environment has buffers exposed or we just crash/fix caller
        raise NotImplementedError("Use update_with_buffers() for multiprocessing support")

    def update_pup_development(self, env_data):
        age_months = self.age_in_hours / 720.0
        if age_months < 2.0:
            self.pup_stage = PupStage.NEWBORN
            swh = env_data.get('swh', 0.0)
            if swh > 2.5:
                if random.random() < 0.01: 
                    self.state = "DEAD"
                    return
        elif age_months < 3.0:
            self.pup_stage = PupStage.POST_MOLT
        elif age_months < 4.5:
            self.pup_stage = PupStage.TRANSITION
        else:
            if self.pup_stage != PupStage.WEANED:
                self.pup_stage = PupStage.WEANED
                self.mother = None 
                self.max_energy = 100000.0 

    def decide_activity(self, env_data, is_night, is_land):
        if self.state == "DEAD": return

        # --- PUP LOGIC ---
        if self.pup_stage and self.pup_stage != PupStage.WEANED:
            if self.pup_stage == PupStage.NEWBORN or self.pup_stage == PupStage.POST_MOLT:
                if not is_land:
                    self.state = SealState.HAULING_OUT
                else:
                    self.state = SealState.SLEEPING 
            elif self.pup_stage == PupStage.TRANSITION:
                if is_land:
                     self.state = SealState.SLEEPING
                else:
                     self.state = SealState.RESTING 
            return

        # --- MOTHER LOGIC ---
        if self.sex == 'F' and self.pup and self.pup.state != "DEAD" and self.pup.pup_stage != PupStage.WEANED:
            if self.state == SealState.NURSING:
                if self.energy < self.max_energy * 0.6:
                    self.state = SealState.FORAGING
                    self.foraging_timer = 0
                return

            if self.state == SealState.FORAGING:
                self.foraging_timer += 1
                if self.stomach_load > self.stomach_capacity * 0.9 or self.foraging_timer > 9:
                    self.state = SealState.HAULING_OUT
                return

            if self.state == SealState.HAULING_OUT:
                if is_land:
                    self.state = SealState.NURSING
                return

        # --- ADULT LOGIC ---
        if self.state == SealState.HAULING_OUT:
            if is_land:
                self.state = SealState.SLEEPING
            return

        if self.state == SealState.SLEEPING:
            if not is_land:
                self.state = SealState.HAULING_OUT 
                return
            if not is_night and self.energy > self.max_energy * 0.95:
                self.state = SealState.FORAGING
            return

        if self.state == SealState.RESTING:
            if is_night:
                if is_land:
                    self.state = SealState.SLEEPING
                else:
                    self.state = SealState.HAULING_OUT
                return
            if self.stomach_load == 0 and self.energy > self.max_energy * 0.9:
                self.state = SealState.FORAGING
            return

        if self.state == SealState.FORAGING:
            if is_night or self.energy < self.max_energy * 0.2:
                if is_land:
                    self.state = SealState.SLEEPING
                else:
                    self.state = SealState.HAULING_OUT
                return
            if self.stomach_load > self.stomach_capacity * 0.8:
                self.state = SealState.RESTING
                return

    def _move_smart(self, env_buffers, seek_land=False, target_pos=None):
        """Move logic using stateless buffers query."""
        if env_buffers is None:
            self.pos, self.heading = correlated_random_walk(None, self.pos, self.heading)
            return
            
        if target_pos:
             dx = target_pos[0] - self.pos[0]
             dy = target_pos[1] - self.pos[1]
             target_heading = math.atan2(dy, dx)
             self.heading = target_heading 
        
        for _ in range(10):
            new_pos, new_heading = correlated_random_walk(None, self.pos, self.heading)
            # Query Logic
            check_data = query_env_buffers(new_pos[0], new_pos[1], env_buffers)
            cell_is_land = check_data.get('is_land', False)

            if seek_land:
                if cell_is_land:
                    self.pos = new_pos
                    self.heading = new_heading
                    return
            else:
                if not cell_is_land:
                    self.pos = new_pos
                    self.heading = new_heading
                    return
                    
    def forage(self, env_data, env_buffers):
        self._move_smart(env_buffers, seek_land=False)
        chl = env_data.get('chl', 0.05)
        # 30,000 conversion factor: chl 0.1 -> 3000 energy -> 0.6kg
        food_value = chl * 30000.0 * random.uniform(0.5, 1.5)
        space = self.stomach_capacity - self.stomach_load
        mass_gain = min(space, food_value / 5000.0)
        self.stomach_load += mass_gain
        # REMOVED: self.energy += mass_gain * 5000.0 (Double Counting Fix)

    def transit(self, env_buffers):
         self._move_smart(env_buffers, seek_land=False)

    def haul_out_search(self, env_buffers):
        target = None
        if self.sex == 'F' and self.pup and self.pup.pup_stage != PupStage.WEANED:
            target = self.pup.maternal_cave_pos
        self._move_smart(env_buffers, seek_land=True, target_pos=target)

    def rest(self, env_data, env_buffers):
        digestion_rate = 5000.0 # BOOSTED: 500 -> 5000 (Approx 1kg/hr)
        if self.stomach_load > 0:
            self.energy += digestion_rate
            self.stomach_load -= (digestion_rate / 5000.0)
            self.stomach_load = max(0, self.stomach_load) 
        self.energy += 20.0
        self.energy = min(self.energy, self.max_energy)

    def sleep(self, env_data, env_buffers):
        is_land = env_data.get('is_land', False)
        if not is_land:
             self.state = SealState.HAULING_OUT
             return

        digestion_rate = 5000.0 # BOOSTED: 500 -> 5000
        if self.stomach_load > 0:
            self.energy += digestion_rate
            self.stomach_load -= (digestion_rate / 5000.0)
            self.stomach_load = max(0, self.stomach_load)
        
        self.energy += 1000.0 
        self.energy = min(self.energy, self.max_energy)

    def burn_energy(self):
        self.energy -= self.rmr

    def nurse_pup_action(self, env_buffers):
        if self.pup and self.pup.state != "DEAD":
            transfer_amount = 1000.0
            if self.energy > transfer_amount:
                self.energy -= transfer_amount
                self.pup.energy += transfer_amount
                self.pup.energy = min(self.pup.energy, self.pup.max_energy)
                
    def reproduce(self):
        if self.sex != 'F' or self.age < 4: return None
        if self.energy < self.max_energy * 0.8: return None
        if hasattr(self, 'pup') and self.pup and self.pup.pup_stage != PupStage.WEANED: return None 

        if random.random() < 0.0005: 
            self.energy -= 20000.0 
            pup_id = f"{self.id}_pup_{random.randint(1000,9999)}"
            pup = SealAgent(agent_id=pup_id, start_pos=self.pos, age=0, sex=random.choice(['M', 'F']), mother=self)
            self.pup = pup 
            return pup
        return None
