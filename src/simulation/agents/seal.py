import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from src.simulation.agents.movement import correlated_random_walk
from src.simulation.environment.utils import query_env_buffers


class SealState(Enum):
    FORAGING = "FORAGING"
    RESTING = "RESTING"  # Short Naps (Sea or Land)
    SLEEPING = "SLEEPING"  # Deep Sleep (Strictly Land)
    HAULING_OUT = "HAULING_OUT"  # Transition to Land
    TRANSITING = "TRANSITING"
    RECOVERY = "RECOVERY"
    DEAD = "DEAD"


@dataclass
class SealMemory:
    haulout_sites: list[tuple[float, float]] = field(default_factory=list)
    high_hsi_patches: list[tuple[float, float]] = field(default_factory=list)
    last_known_storm_pos: tuple[float, float] | None = None


class SealAgent:
    def __init__(self, agent_id: str, start_pos: tuple[float, float], age: int = 5, sex: str = "F"):
        self.id = agent_id
        self.pos = start_pos
        self.heading = random.uniform(0, 2 * math.pi)
        self.age = age
        self.sex = sex
        self.sex = sex

        # Physiological Parameters
        self.mass = 300.0
        self.stomach_load = 0.0
        self.stomach_capacity = 15.0

        # Energy
        # Energy
        self.energy = 90000.0  # Start with good body condition (90%)
        self.max_energy = 100000.0

        self.rmr = 753.0

        # Parental State
        self.foraging_timer = 0
        self.missing_chl_count = 0

        # State
        self.state = SealState.FORAGING
        if self.age == 0:
            self.state = SealState.RESTING  # Pups start resting/sleeping

        self.memory = SealMemory()

        # Thresholds
        self.storm_threshold = 2.5
        self.max_landing_swell = 4.0
        self.age_in_hours = 0
        self.state_duration = 0  # Track how long we've been in current state
        self.patch_residence_time = 0  # Track time in current forage patch (Boredom)
        self.haulout_failures = 0  # Track consecutive failed haul-out attempts
        self.distance_to_land = 999.0  # Track distance to nearest land (km)
        self.debug = self.id == "0"

    def log(self, msg):
        if self.debug:
            print(f"[Seal {self.id} | {self.age_in_hours}h | {self.state.name}] {msg}")

    def update_with_buffers(self, env_buffers: dict):
        """
        Multiprocessing-friendly update loop.
        Uses env_buffers (dict of numpy arrays) instead of Environment object.
        """
        self.age_in_hours += 1
        hour_of_day = self.age_in_hours % 24
        is_night = hour_of_day >= 20 or hour_of_day < 6

        if self.age_in_hours % (24 * 365) == 0:
            self.age += 1

        if self.debug and self.age_in_hours % 24 == 0:
            self.log(
                f"Seal(Age={self.age:.1f}, Energy={self.energy:.1f}/{self.max_energy}, "
                f"Stomach={self.stomach_load:.1f}, Pos=({self.pos[0]:.2f}, {self.pos[1]:.2f})"
            )

        # 1. Sense Environment at current pos
        env_data = query_env_buffers(self.pos[0], self.pos[1], env_buffers)

        # Track distance to nearest land (update every 6 hours to save computation)
        if self.age_in_hours % 6 == 0:
            self.distance_to_land = self._get_distance_to_nearest_land(env_buffers)
            if self.distance_to_land > 15.0:
                self.log(f"⚠️  FAR FROM LAND: {self.distance_to_land:.1f}km from nearest island")

        swh = env_data.get("swh", 0.0)
        is_land = env_data.get("is_land", False)

        # Storm Logic
        if swh > self.max_landing_swell:
            if self.state == SealState.HAULING_OUT:
                self.state = (
                    SealState.TRANSITING
                )  # Move to safety instead of resting in impact zone

        elif swh > self.storm_threshold:
            if (
                not is_land
                and self.state != SealState.HAULING_OUT
                and self.state != SealState.SLEEPING
            ):
                self.state = SealState.HAULING_OUT

        # Male Risk Feature (Human Interaction / Boldness)
        if self.sex == "M" and self.age >= 4:
            # Higher background mortality for adult males (approx 10% annual)
            # 0.1 / 8760 ~= 1e-5
            if random.random() < 1.0e-5:
                self.state = SealState.DEAD
                return

        self.burn_energy()
        if self.energy <= self.max_energy * 0.10:
            self.log(f"DIED of Starvation (Critical Condition). Energy={self.energy:.1f}")
            self.state = SealState.DEAD
            return

        old_state = self.state

        self.decide_activity(env_data, is_night, is_land)
        if self.state != old_state:
            self.state_duration = 0
            self.log(
                f"State Change: State={self.state.name}. Night={is_night}, Land={is_land}, "
                f"Tide={env_data.get('tide', 0.5):.2f}"
            )
            # Reset patch residence time if state changes
            if old_state == SealState.FORAGING:
                self.patch_residence_time = 0
        else:
            self.state_duration += 1

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

    # Legacy update (wraps buffers call if needed, but we should use update_with_buffers mainly)
    def update(self, env_data, environment=None):
        # Fallback for old calls if any
        # Assuming environment has buffers exposed or we just crash/fix caller
        raise NotImplementedError("Use update_with_buffers() for multiprocessing support")

    def decide_activity(self, env_data, is_night, is_land):
        if self.state == "DEAD":
            return

        # Tide Data
        tide = env_data.get("tide", 0.5)
        high_tide_threshold = 0.70
        low_tide_threshold = 0.30

        # --- TIDE FORCING (Highest Priority) ---
        # High Tide: Must be in water (Forage/Transit)
        if tide > high_tide_threshold:
            if is_land:
                # DANGER: We are on land during high tide (Inundation risk)
                # Must exit immediately
                self.log(f"HIGH TIDE ({tide:.2f} > {high_tide_threshold}): Evacuating land!")
                self.state = SealState.TRANSITING  # Will seek water
                return
            elif self.state in [SealState.HAULING_OUT, SealState.RESTING, SealState.SLEEPING]:
                # In water but trying to rest/haulout - Force filter
                # Cannot Haulout at High Tide (Caves flooded)
                self.log(f"HIGH TIDE ({tide:.2f}): Forcing Foraging (Caves flooded)")
                self.state = SealState.FORAGING
                return

        # --- ADULT LOGIC ---

        # 1. HAULING OUT PROCESS
        if self.state == SealState.HAULING_OUT:
            # Abort if tide gets too high
            if tide > high_tide_threshold and not is_land:
                self.state = SealState.FORAGING
                return

            if is_land:
                # Successfully reached land!
                self.state = SealState.SLEEPING
                self.haulout_failures = 0  # Reset failure counter

                # Memorize Haulout
                found = False
                for site in self.memory.haulout_sites:
                    dist = math.sqrt((site[0] - self.pos[0]) ** 2 + (site[1] - self.pos[1]) ** 2)
                    if dist < 0.05:  # Nearby (~5km)
                        found = True
                        break
                if not found:
                    self.memory.haulout_sites.append(self.pos)
            return

        # 2. SLEEPING (On Land)
        if self.state == SealState.SLEEPING:
            if not is_land:
                # Bottling (Sleeping in water)
                # If tide is low, we should try to Haul Out properly
                if tide < low_tide_threshold:
                     self.state = SealState.HAULING_OUT
                     return

                # If we are exhausted, stay bottling
                if self.energy > self.max_energy * 0.20:
                     # Wake up check
                     if self.stomach_load == 0:
                         self.state = SealState.FORAGING
                return

            # On Land
            if tide > high_tide_threshold:
                 # Forced to wake up by tide
                 self.state = SealState.FORAGING
                 return

            # Wake up if hungry
            if self.stomach_load == 0 and self.energy < self.max_energy * 0.95:
                 self.state = SealState.FORAGING
            return

        # 3. RESTING (In Water)
        if self.state == SealState.RESTING:
            # If Tide is Low -> Opportunity to Haul Out
            if tide < low_tide_threshold:
                # Prefer Hauling Out over floating rest
                self.state = SealState.HAULING_OUT
                return

            # Wake up if digested or hungry
            if self.stomach_load == 0 and self.energy > self.max_energy * 0.9:
                self.state = SealState.FORAGING
            return

        # 4. FORAGING
        if self.state == SealState.FORAGING:
            # Desperation Override
            is_desperate = self.energy < self.max_energy * 0.15 and self.stomach_load < 0.1
            if is_desperate:
                return # Keep eating

            # Tiredness / Satiety
            is_tired = self.energy < self.max_energy * 0.2
            is_full = self.stomach_load > self.stomach_capacity * 0.8

            if is_full or is_tired:
                # seek rest
                # Check Tide for decision
                if tide < low_tide_threshold:
                    self.state = SealState.HAULING_OUT
                else:
                    self.state = SealState.RESTING # Rest in water until tide drops
                return

            # Low Tide Opportunity: Maybe haul out if semi-full?
            # (Optional: Seals like to sleep at low tide even if not 100% full)
            if tide < low_tide_threshold and self.stomach_load > self.stomach_capacity * 0.5:
                 self.state = SealState.HAULING_OUT
                 return

        # 5. TRANSITING
        if self.state == SealState.TRANSITING:
            # If we were transiting to escape land (Tide Panic), check if we are safe
            if not is_land:
                self.log("TRANSITING -> FORAGING: Safe in water (Escaped land/Tide Panic ended)")
                self.state = SealState.FORAGING
                return
            # Else: We are still on land, so we must keep TRANSITING (Panic Move)
            return

    def _get_home_bias(self):
        # Return vector to home (first haulout site)
        if self.memory.haulout_sites:
            home = self.memory.haulout_sites[0]
            return home, 0.5  # Coordinate, Strength
        return None, 0.0

    def _path_intersects_land(self, start_pos, end_pos, env_buffers, steps=10):
        """Check if straight line path crosses through land.

        This checks INTERMEDIATE points only (not start or end).
        This allows: water->land (hauling out) and land->water (entering water)
        This prevents: water->water paths that cross land (walking through islands)

        For a typical 0.05 degree move (~5.5km), 10 steps samples every ~550m.
        """
        d_lat = end_pos[0] - start_pos[0]
        d_lon = end_pos[1] - start_pos[1]

        # Check intermediate points only (exclude endpoints)
        for i in range(1, steps):  # Changed from range(1, steps + 1)
            f = i / steps  # Changed from i / (steps + 1)
            p_lat = start_pos[0] + d_lat * f
            p_lon = start_pos[1] + d_lon * f

            data = query_env_buffers(p_lat, p_lon, env_buffers)
            if data.get("is_land", False):
                return True
        return False

    def _calculate_distance_km(self, pos1, pos2):
        """Calculate distance between two lat/lon positions in kilometers."""
        from math import atan2, cos, radians, sin, sqrt

        earth_radius_km = 6371  # Earth radius in km
        lat1, lon1 = radians(pos1[0]), radians(pos1[1])
        lat2, lon2 = radians(pos2[0]), radians(pos2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return earth_radius_km * c

    def _find_nearest_land(self, env_buffers, max_radius_km=10.0, num_samples=36):
        """
        Find nearest land cell within radius by sampling in expanding circles.

        Args:
            env_buffers: Environment data buffers
            max_radius_km: Maximum search radius in kilometers
            num_samples: Number of points to sample per circle

        Returns:
            Tuple of (land_position, distance_km) or (None, None) if no land found
        """
        from math import cos, radians, sin

        if env_buffers is None:
            return None, None

        # Convert km to approximate degrees (rough: 1 degree ≈ 111 km)
        max_radius_deg = max_radius_km / 111.0

        # Search in expanding circles
        num_circles = 10
        best_land_pos = None
        best_distance = float("inf")

        for circle_idx in range(1, num_circles + 1):
            radius_deg = (circle_idx / num_circles) * max_radius_deg

            # Sample points around circle
            for i in range(num_samples):
                angle = (i / num_samples) * 2 * 3.14159

                # Calculate sample position
                # Rough approximation for small distances
                sample_lat = self.pos[0] + radius_deg * cos(angle)
                sample_lon = self.pos[1] + radius_deg * sin(angle) / cos(radians(self.pos[0]))

                # Check if this is land
                data = query_env_buffers(sample_lat, sample_lon, env_buffers)
                # For distance calculation, include ALL land (even coastline)
                # For navigation targets, we still prefer non-coastline land
                if data.get("is_land", False):
                    # Found land! Calculate actual distance
                    distance = self._calculate_distance_km(self.pos, (sample_lat, sample_lon))

                    if distance < best_distance:
                        best_distance = distance
                        best_land_pos = (sample_lat, sample_lon)

        if best_land_pos:
            self.log(
                f"Found land at {best_distance:.2f}km: "
                f"({best_land_pos[0]:.4f}, {best_land_pos[1]:.4f})"
            )
            return best_land_pos, best_distance

        return None, None

    def _get_distance_to_nearest_land(self, env_buffers):
        """Get distance to nearest land for proximity tracking."""
        # First check if we're already on land
        current_data = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
        if current_data.get("is_land", False):
            return 0.0  # We're on land, distance is zero

        # Otherwise search for nearest land
        _, distance = self._find_nearest_land(env_buffers, max_radius_km=20.0, num_samples=24)
        return distance if distance is not None else 999.0  # Return large number if no land found

    def _find_nearest_water(self, env_buffers, max_radius_km=5.0, num_samples=36):
        """
        Find nearest water cell (not land) within radius.
        Used when seal is stuck on land and needs to find water.

        Args:
            env_buffers: Environment data buffers
            max_radius_km: Maximum search radius in kilometers
            num_samples: Number of points to sample per circle

        Returns:
            Tuple of (water_position, distance_km) or (None, None) if no water found
        """
        from math import cos, radians, sin

        if env_buffers is None:
            return None, None

        # Convert km to approximate degrees
        max_radius_deg = max_radius_km / 111.0

        # Search in expanding circles
        num_circles = 10
        best_water_pos = None
        best_distance = float("inf")

        for circle_idx in range(1, num_circles + 1):
            radius_deg = (circle_idx / num_circles) * max_radius_deg

            # Sample points around circle
            for i in range(num_samples):
                angle = (i / num_samples) * 2 * 3.14159

                # Calculate sample position
                sample_lat = self.pos[0] + radius_deg * cos(angle)
                sample_lon = self.pos[1] + radius_deg * sin(angle) / cos(radians(self.pos[0]))

                # Check if this is water (not land)
                data = query_env_buffers(sample_lat, sample_lon, env_buffers)
                if not data.get("is_land", False):
                    # Found water! Calculate actual distance
                    distance = self._calculate_distance_km(self.pos, (sample_lat, sample_lon))

                    if distance < best_distance:
                        best_distance = distance
                        best_water_pos = (sample_lat, sample_lon)

        if best_water_pos:
            self.log(
                f"Found water at {best_distance:.2f}km: "
                f"({best_water_pos[0]:.4f}, {best_water_pos[1]:.4f})"
            )
            return best_water_pos, best_distance

        return None, None

    def _move_smart(
        self, env_buffers, intention="WATER", target_pos=None, speed=0.05
    ):
        """
        Move logic using stateless buffers query.

        Args:
            env_buffers: Environment data buffers
            intention: "WATER", "LAND", "SHELF"
                - WATER: Avoid land (Transit/Forage in open water)
                - LAND: Seek land (Haul out) - coast is valid target
                - SHELF: Seek shallow water (<100m) but NOT land (Foraging)
            target_pos: Optional (lat, lon) target to navigate towards
            speed: Movement speed in degrees/step
        """
        if env_buffers is None:
            self.pos, self.heading = correlated_random_walk(
                None, self.pos, self.heading, speed=speed
            )
            return

        # Deep Water Panic - Find Nearest Shallow Water
        # If we're in dangerously deep water, search for nearest shallow water
        curr_data_check = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
        depth_check = curr_data_check.get("depth", 9999)

        # Extreme depth threshold - abyssal zone, seal is in danger
        if depth_check is None or depth_check > 1000:
            # Search for nearest shallow water (<100m) that is NOT land
            best_shallow = None
            best_dist = float("inf")

            # Search in a grid around current position
            search_radius = 0.2  # degrees (~22km)
            search_steps = 8
            for i in range(search_steps):
                for j in range(search_steps):
                    test_lat = self.pos[0] + (i - search_steps / 2) * (
                        search_radius / search_steps
                    )
                    test_lon = self.pos[1] + (j - search_steps / 2) * (
                        search_radius / search_steps
                    )

                    test_data = query_env_buffers(test_lat, test_lon, env_buffers)
                    test_depth = test_data.get("depth", 9999)
                    test_is_land = test_data.get("is_land", False)

                    # Valid shallow water: depth < 100m and NOT land
                    if test_depth is not None and test_depth < 100 and not test_is_land:
                        dist = (
                            (test_lat - self.pos[0]) ** 2 + (test_lon - self.pos[1]) ** 2
                        ) ** 0.5
                        if dist < best_dist:
                            best_dist = dist
                            best_shallow = (test_lat, test_lon)

            if best_shallow and target_pos is None:
                target_pos = best_shallow
                self.log(
                    f"DEEP WATER PANIC! Depth={depth_check}m, "
                    f"heading to shallow water at {target_pos}"
                )
                intention = "SHELF"  # Force intention to find shelf
            elif target_pos is None:
                # Fallback to home if no shallow water found
                bias_pos, _ = self._get_home_bias()
                if bias_pos:
                    target_pos = bias_pos
                    self.log(
                        f"DEEP WATER PANIC! Depth={depth_check}m, no shallow water found, "
                        f"heading home to {target_pos}"
                    )

        # Apply target heading if we have one
        if target_pos:
            d_lat = target_pos[0] - self.pos[0]
            d_lon = target_pos[1] - self.pos[1]
            target_heading = math.atan2(d_lat, d_lon)
            self.heading = target_heading

        # Sample candidates
        # COLLISION CHECK (Pre-computation)
        curr_data = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
        currently_on_land = curr_data.get("is_land", False)

        candidates: list[dict[str, Any]] = []
        step_speed = speed

        # Candidate Generation Strategy
        if currently_on_land:
            # PANIC/ESCAPE: We are on land. Ignore momentum (CRW).
            # Sample 360 degrees uniformly to find water.
            for _ in range(20):  # More samples to ensure we find a valid move
                new_heading = random.uniform(0, 2 * math.pi)
                # Manual projection (simple approximation suffices for short steps)
                new_lat = self.pos[0] + step_speed * math.cos(new_heading)
                # Adjust lon for latitude (approx)
                new_lon = self.pos[1] + step_speed * math.sin(new_heading) / math.cos(
                    math.radians(self.pos[0])
                )

                check_data = query_env_buffers(new_lat, new_lon, env_buffers)
                candidates.append(
                    {"pos": (new_lat, new_lon), "heading": new_heading, "data": check_data}
                )
        else:
             # Normal Movement: Correlated Random Walk (Momentum)
             for _ in range(10):
                new_pos, new_heading = correlated_random_walk(
                    None, self.pos, self.heading, speed=step_speed
                )
                check_data = query_env_buffers(new_pos[0], new_pos[1], env_buffers)
                candidates.append(
                    {"pos": new_pos, "heading": new_heading, "data": check_data}
                )

        # Filter candidates based on intention
        valid_candidates = []

        for c in candidates:
            c_is_land = c["data"].get("is_land", False)
            c_is_coastline = c["data"].get("is_coastline", False)

            # Check path intersection with land
            # Only check if we are NOT on land (if on land, we can move anywhere to escape)
            path_crosses_land = False
            if not currently_on_land:
                 path_crosses_land = self._path_intersects_land(self.pos, c["pos"], env_buffers)

            if intention == "WATER":
                # Must not be land
                # Must not cross land
                if not c_is_land and not path_crosses_land:
                    # Avoid coastline for "WATER" intention (pure transit/forage)
                    if not c_is_coastline:
                        valid_candidates.append(c)

            elif intention == "SHELF":
                # Must not be land
                # Must not cross land
                # Prefer depth < 100 (Gradient descent checks this later)
                if not c_is_land and not path_crosses_land:
                     # Coastline is risky for SHELF intention too, but maybe acceptable?
                     # Let's avoid it to be safe, unless we are desperate.
                     # Let's avoid it to be safe, unless we are desperate.
                     if not c_is_coastline:
                         valid_candidates.append(c)

            elif intention == "LAND":
                # Can be land
                # Can cross land (entering from water)
                # If target is land, we WANT to hit land
                valid_candidates.append(c)

        # Fallback: If no candidates filtered, relax constraints
        if not valid_candidates:
             # Try allowing coastline
            if intention in ["WATER", "SHELF"]:
                 for c in candidates:
                    c_is_land = c["data"].get("is_land", False)
                    if not currently_on_land:
                        path_crosses_land = self._path_intersects_land(
                            self.pos, c["pos"], env_buffers
                        )
                    else:
                        path_crosses_land = False

                    if not c_is_land and not path_crosses_land:
                        valid_candidates.append(c)

            # Still nothing? Just use all candidates (Panic/Stuck)
            if not valid_candidates:
                valid_candidates = candidates
                self.log(
                    f"WARNING: No valid move candidates for intention {intention}. "
                    "Using UNSAFE fallback."
                )

        candidates = valid_candidates
        best_c = None

        # Selection Logic
        if intention == "LAND":
            # 1. Try to find actual Land
            land_matches = [c for c in candidates if c["data"].get("is_land", False)]
            if land_matches:
                best_c = random.choice(land_matches)
            else:
                 # Move towards target if exists
                 if target_pos:
                     best_c = min(
                        candidates,
                        key=lambda c: (c["pos"][0] - target_pos[0]) ** 2
                        + (c["pos"][1] - target_pos[1]) ** 2,
                    )
                 else:
                     best_c = random.choice(candidates)

        elif intention == "SHELF":
             # Prioritize Shallow Water (<100m)
             # Sort candidates by depth
             def get_depth_score(c):
                 d = c["data"].get("depth")
                 if d is None:
                     return 9999
                 if d < 0:
                     return 9999  # Bad data
                 # Ideal: 0-50m. Penalty for >100m.
                 return d

             candidates.sort(key=get_depth_score)

             # If top candidate is shallow (<100m), pick it
             top_depth = get_depth_score(candidates[0])
             if top_depth < 100:
                 best_c = candidates[0] # Steepest descent to shallow
             else:
                 # No shallow options? Move towards target or random
                  if target_pos:
                     best_c = min(
                        candidates,
                        key=lambda c: (c["pos"][0] - target_pos[0]) ** 2
                        + (c["pos"][1] - target_pos[1]) ** 2,
                    )
                  else:
                      best_c = candidates[0] # Move to shallowest available

        elif intention == "WATER":
             # Just move, maybe bias to target
             if target_pos:
                     best_c = min(
                        candidates,
                        key=lambda c: (c["pos"][0] - target_pos[0]) ** 2
                        + (c["pos"][1] - target_pos[1]) ** 2,
                    )
             else:
                 # WANDER: Prefer shallow water (<100m) to stay on shelf
                 shallow_candidates = [
                     c
                     for c in candidates
                     if c["data"].get("depth", 9999) is not None
                     and c["data"].get("depth", 9999) <= 100
                 ]
                 if shallow_candidates:
                     best_c = random.choice(shallow_candidates)
                 else:
                     best_c = random.choice(candidates)

        # Determine specific best_c if not set above (Fallback)
        if not best_c:
            best_c = random.choice(candidates)

        # Execute Move
        best_pos = best_c["pos"]
        self.pos = cast(tuple[float, float], best_pos)
        self.heading = float(cast(float, best_c["heading"]))

    def forage(self, env_data, env_buffers):
        # 1. Determine Feed Mode based on Age
        is_adult = (
            self.age >= 6
        )  # Sexual maturity is 6. Let's use 4 for "Adult Foraging"?
        # Let's say Subadults (4+) act like adults.

        # 2. Feeding Logic
        # Octopus Density Index based on Depth
        # Depth > 200m: 0.05
        # 50-200m: 0.5
        # 0-50m: 3.0 (Targeting ~3kg/hr)

        # Check Depth
        # If we are doing "Spot Feeding" (Adult), we check current pos.
        # If "Transit Feeding" (Juv), we move first.

        if is_adult:
            # Spot Feeding: Check current location
            # If good patch found, stay (don't move).
            # If bad, move to find better.

            depth = env_data.get("depth")
            if depth is None:
                depth = 9999

            # Simple Spot Logic with Boredom/Depletion:
            # If depth < 50m, Base 90%. If 50-100m, Base 50%.
            # Prob = Base * (0.8 ^ residence_time)
            base_prob = 0.0
            if depth <= 50:
                base_prob = 0.9
            elif depth <= 100:
                base_prob = 0.5

            stay_prob = base_prob * (0.8**self.patch_residence_time)

            should_move = True
            if random.random() < stay_prob:
                should_move = False

            if should_move:
                self.patch_residence_time = 0  # Reset timer on move

                # ISLAND PROXIMITY BOUNDARY: If too far from land, navigate back
                # This prevents seals from drifting into open ocean
                if self.distance_to_land > 12.0:
                    # Too far from islands - navigate toward nearest land
                    self.log(
                        f"BOUNDARY: {self.distance_to_land:.1f}km from land, returning to islands"
                    )
                    land_pos, _ = self._find_nearest_land(env_buffers, max_radius_km=20.0)
                    if land_pos:
                        self._move_smart(env_buffers, intention="LAND", target_pos=land_pos)
                    else:
                        # No land found - move toward remembered haulout site
                        if self.memory.haulout_sites:
                            target = min(
                                self.memory.haulout_sites,
                                key=lambda p: (p[0] - self.pos[0]) ** 2 + (p[1] - self.pos[1]) ** 2,
                            )
                            self._move_smart(env_buffers, intention="LAND", target_pos=target)
                        else:
                            self._move_smart(env_buffers, intention="LAND", target_pos=None)
                else:
                    # Normal foraging movement
                    # If Deep (>120m), swim towards Shelf (Shallow Water)
                    # If we are ON LAND, we must seek water!
                    is_land = env_data.get("is_land", False)
                    if is_land:
                        # SMART WATER ESCAPE: Find nearest water
                        self.log("On land - searching for nearest water to escape")
                        water_pos, water_dist = self._find_nearest_water(
                            env_buffers, max_radius_km=5.0
                        )
                        if water_pos:
                            self.log(f"WATER ESCAPE: Navigating to water at {water_dist:.2f}km")
                            self._move_smart(env_buffers, intention="WATER", target_pos=water_pos)
                        else:
                            # No water found - try random movement
                            self.log("WARNING: No water found nearby, trying random escape")
                            self._move_smart(env_buffers, intention="WATER", target_pos=None)
                    else:
                        # If deep, intention is SHELF. Else WATER (random foraging)
                        depth = env_data.get("depth", 9999)
                        if depth > 100:
                            self.log(f"Forage Move. Depth={depth:.1f}m. Seeking Shelf.")
                            self._move_smart(env_buffers, intention="SHELF", target_pos=None)
                        else:
                             self._move_smart(env_buffers, intention="WATER", target_pos=None)
                pass
            else:
                self.patch_residence_time += 1
                self.log(f"Forage Stay. Depth={depth:.1f}m (PatchTime={self.patch_residence_time})")

            # Re-read depth at final position
            check = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
            depth = check.get("depth")
            if depth is None:
                depth = 9999

        else:
            # Transit Feeding (Juvenile)
            # Explore larger distances.
            # If Deep (>120m), swim towards Land
            target = None
            d_check = env_data.get("depth")
            is_land = env_data.get("is_land", False)

            # SMART WATER ESCAPE: If on land, find nearest water
            if is_land:
                self.log("On land - searching for nearest water to escape")
                water_pos, water_dist = self._find_nearest_water(env_buffers, max_radius_km=5.0)
                if water_pos:
                    self.log(f"WATER ESCAPE: Navigating to water at {water_dist:.2f}km")
                    self._move_smart(env_buffers, intention="WATER", target_pos=water_pos)
                else:
                    # No water found nearby - try random movement
                    self.log("WARNING: No water found nearby, trying random escape")
                    self._move_smart(env_buffers, intention="WATER", target_pos=None)
            else:
                # Normal transit feeding in water
                d_check = env_data.get("depth", 9999)
                if d_check > 100:
                    self._move_smart(env_buffers, intention="SHELF", target_pos=None)
                else:
                    self._move_smart(env_buffers, intention="WATER", target_pos=None)

            check = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
            depth = check.get("depth")
            if depth is None:
                depth = 9999

        # 3. Calculate Intake
        # CRITICAL: Check if we're actually on land (even with inferred depth)
        # Seals cannot eat on land!
        final_check = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
        if final_check.get("is_land", False):
            # We're on land - cannot forage here
            self.log(f"Cannot forage on land (Depth={depth:.1f}m inferred, but is_land=True)")
            return

        if depth <= 50:  # High Quality (0-50m)
            rate = 3.0
        elif depth <= 100:  # Medium Quality (50-100m)
            rate = 1.0
        else:
            rate = 0.0  # Desert (>100m)

        # Random variability (success rate)
        mass_gain = rate * random.uniform(0.5, 1.5)

        space = self.stomach_capacity - self.stomach_load
        actual_gain = min(space, mass_gain)
        self.stomach_load += actual_gain
        if actual_gain > 0:
            self.log(f"Forage Eat: Depth={depth:.1f}m, Rate={rate}, Gained={actual_gain:.2f}kg")

            # UPDATE HOME POSITION: If we successfully foraged in valid water, update home
            # This prevents returning to coastline cells during panic
            if depth < 100 and not final_check.get("is_land", False):
                # This is a good foraging location - update home
                self.memory.haulout_sites.append((self.pos[0], self.pos[1]))
                # Keep only the most recent haulout site
                if len(self.memory.haulout_sites) > 5:
                    self.memory.haulout_sites.pop(0)
                self.log(
                    f"Updated home position to current foraging location "
                    f"({self.pos[0]:.4f}, {self.pos[1]:.4f})"
                )

    def transit(self, env_buffers):
        # Check if we are stuck on land (e.g. High Tide Evacuation)
        curr_data = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
        if curr_data.get("is_land", False):
            self.log("TRANSITING on land - searching for nearest water to escape")
            water_pos, water_dist = self._find_nearest_water(
                env_buffers, max_radius_km=5.0
            )
            if water_pos:
                self.log(f"WATER ESCAPE: Navigating to water at {water_dist:.2f}km")
                self._move_smart(env_buffers, intention="WATER", target_pos=water_pos)
            else:
                # No water found - try random
                self.log("WARNING: No water found nearby in TRANSIT, trying random escape")
                self._move_smart(env_buffers, intention="WATER", target_pos=None)
        else:
            # We are in water, just transit normally
            self._move_smart(env_buffers, intention="WATER", target_pos=None)

    def haul_out_search(self, env_buffers):
        """Search for and navigate to land for hauling out."""
        target = None

        # Use smart land-finding to locate nearest land
        land_pos, land_dist = self._find_nearest_land(env_buffers, max_radius_km=15.0)

        if land_pos:
            if self.state_duration == 0:  # Log only on first attempt
                self.log(f"HAUL-OUT: Found land at {land_dist:.2f}km, navigating...")
            target = land_pos
        else:
            # No land found - try memory as fallback
            if self.memory.haulout_sites:
                # Find closest remembered site
                closest = min(
                    self.memory.haulout_sites,
                    key=lambda p: (p[0] - self.pos[0]) ** 2 + (p[1] - self.pos[1]) ** 2,
                )
                target = closest
                if self.state_duration == 0:
                    self.log("No land found nearby, using remembered haulout site")

        if target:
            self._move_smart(env_buffers, intention="LAND", target_pos=target)
        else:
            # No target at all - just move toward land generally
            self._move_smart(env_buffers, intention="LAND", target_pos=None)

        # Timeout: If hunting for land too long (>5h), give up and bottle (Sleep in water)
        if self.state_duration > 5:
            self.log("Haulout Warning: Could not find land for 5h. Bottling in water.")
            self.state = SealState.SLEEPING

    def rest(self, env_data, env_buffers):
        # Check tide - if low, maybe switch to hauling out?
        tide = env_data.get("tide", 0.5)
        if tide < 0.30: # LOW_TIDE_THRESHOLD
             # We are resting in water, but tide is good for hauling out
             # Let decide_activity switch us next tick - just finish this rest step
             pass

        digestion_rate = 3500.0  # Adjusted for cephalopods
        if self.stomach_load > 0:
            self.energy += digestion_rate
            self.stomach_load -= digestion_rate / 3500.0
            self.stomach_load = max(0, self.stomach_load)
        self.energy += 20.0
        self.energy = min(self.energy, self.max_energy)

    def sleep(self, env_data, env_buffers):
        tide = env_data.get("tide", 0.5)
        is_land = env_data.get("is_land", False)

        # TIDE SAFETY CHECK:
        # If sleeping on land and tide rises, we must wake up and move!
        if is_land and tide > 0.75: # HIGH_TIDE_THRESHOLD + buffer
             self.log(f"Waking up from sleep on land due to rising tide ({tide:.2f})!")
             self.state = SealState.FORAGING # Or TRANSIT
             return

        digestion_rate = 3500.0
        if self.stomach_load > 0:
            self.energy += digestion_rate
            self.stomach_load -= digestion_rate / 3500.0
            self.stomach_load = max(0, self.stomach_load)

        self.energy = min(self.energy, self.max_energy)

    def burn_energy(self):
        # Active Metabolic Rate (AMR) = 1.5 * RMR for active states
        multiplier = 1.0
        if self.state in [SealState.FORAGING, SealState.TRANSITING, SealState.HAULING_OUT]:
            multiplier = 1.5

        self.energy -= self.rmr * multiplier
