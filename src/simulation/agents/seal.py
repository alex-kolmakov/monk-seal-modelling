import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import cast

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

        # --- ADULT LOGIC ---
        if self.state == SealState.HAULING_OUT:
            # Tide Forcing: Hard to haul out at high tide?
            tide = env_data.get("tide", 0.5)
            if tide > 0.8 and not is_land:
                # Abort haul out, go forage
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

        if self.state == SealState.SLEEPING:
            if not is_land:
                # If we are sleeping in water (Bottling),
                # only Haul Out if we are NOT desperate/tired
                # If we are exhausted, just keep sleeping in water
                if self.energy > self.max_energy * 0.20:
                    self.state = SealState.HAULING_OUT
                    return

            # Tide Forcing (User: "High tide... forces seals into water")
            tide = env_data.get("tide", 0.5)
            if tide > 0.8:
                self.state = SealState.FORAGING
                return

            # Wake up if it's day AND (We are rested OR We are hungry/empty)
            if not is_night:
                if self.energy > self.max_energy * 0.90 or self.stomach_load == 0:
                    self.state = SealState.FORAGING
            return

        if self.state == SealState.RESTING:
            if is_night:
                if is_land:
                    self.state = SealState.SLEEPING
                else:
                    # If critical, don't waste energy hauling out. Sleep in water (Bottle).
                    if self.energy < self.max_energy * 0.15:
                        self.state = SealState.SLEEPING
                        self.log(
                            "Critical Energy: Sleeping in water (Bottling) instead of Hauling Out."
                        )
                    else:
                        self.state = SealState.HAULING_OUT
                return
            if self.stomach_load == 0 and self.energy > self.max_energy * 0.9:
                self.state = SealState.FORAGING
            return

        if self.state == SealState.FORAGING:
            # Desperation Override: If critical energy and empty stomach, MUST FORAGE.
            # Do not haul out to sleep/die.
            # Threshold: If we have ANY food (e.g. >0.1kg), we should digest it to survive.
            # Only forage if empty.
            is_desperate = self.energy < self.max_energy * 0.15 and self.stomach_load < 0.1

            if is_desperate:
                # Ignore Night/Tide, just eat.
                return

            if is_night:
                if is_land:
                    self.state = SealState.SLEEPING
                else:
                    # Night: Sleep. If critical, water sleep.
                    if self.energy < self.max_energy * 0.15:
                        self.state = SealState.SLEEPING
                        self.log("Critical Energy (Night): Bottling.")
                    else:
                        self.state = SealState.HAULING_OUT
                return

            # Day Logic - Tiredness
            if self.energy < self.max_energy * 0.2:
                # Only rest if we have food to digest.
                # If empty, we must keep foraging regardless of fatigue.
                if self.stomach_load > 0:
                    if is_land:
                        self.state = SealState.SLEEPING
                    else:
                        if self.energy < self.max_energy * 0.15:
                            self.state = SealState.SLEEPING
                            self.log("Critical Energy (Tired): Bottling.")
                        else:
                            self.state = SealState.HAULING_OUT
                    return
                # Else: Keep Foraging (Desperate for food)
            if self.stomach_load > self.stomach_capacity * 0.8:
                self.state = SealState.RESTING
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

    def _move_smart(self, env_buffers, seek_land=False, target_pos=None, speed=0.05):
        """Move logic using stateless buffers query."""
        if env_buffers is None:
            self.pos, self.heading = correlated_random_walk(
                None, self.pos, self.heading, speed=speed
            )
            return

        # Deep Water Panic - Find Nearest Shallow Water
        # If we're in dangerously deep water, search for nearest shallow water
        # This prevents returning to coastline cells (which may be marked as land)
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
                    test_lat = self.pos[0] + (i - search_steps / 2) * (search_radius / search_steps)
                    test_lon = self.pos[1] + (j - search_steps / 2) * (search_radius / search_steps)

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
            elif target_pos is None:
                # Fallback to home if no shallow water found
                bias_pos, _ = self._get_home_bias()
                if bias_pos:
                    target_pos = bias_pos
                    self.log(
                        f"DEEP WATER PANIC! Depth={depth_check}m, no shallow water found, "
                        f"heading home to {target_pos}"
                    )

        # Moderate depth - gentle bias toward home if not already targeting something
        elif depth_check > 500 and target_pos is None and not seek_land:
            bias_pos, _ = self._get_home_bias()
            if bias_pos:
                # Gentle pull home
                d_lat = bias_pos[0] - self.pos[0]
                d_lon = bias_pos[1] - self.pos[1]
                target_heading = math.atan2(d_lat, d_lon)

                # Mix headings (80% home, 20% current) - stronger than before
                diff = target_heading - self.heading
                diff = (diff + math.pi) % (2 * math.pi) - math.pi
                self.heading += diff * 0.4  # Increased from 0.2

        if target_pos:
            d_lat = target_pos[0] - self.pos[0]
            d_lon = target_pos[1] - self.pos[1]
            # atan2(y, x) -> atan2(d_lat, d_lon) for standard unit circle (0=East)
            # Check movement.py: computes sin(heading) for lat, cos(heading) for lon.
            # So wrapping: heading=0 -> sin(0)=0 (No N/S), cos(0)=1 (East). Correct.
            target_heading = math.atan2(d_lat, d_lon)
            self.heading = target_heading

        # Sample candidates
        candidates = []
        step_speed = speed

        for _ in range(10):
            new_pos, new_heading = correlated_random_walk(
                None, self.pos, self.heading, speed=step_speed
            )
            check_data = query_env_buffers(new_pos[0], new_pos[1], env_buffers)
            candidates.append({"pos": new_pos, "heading": new_heading, "data": check_data})

        # COLLISION CHECK: Prevent land crossing, but with special handling for land positions
        # - If in WATER: Never allow paths that cross land (prevents island teleportation)
        # - If on LAND and seeking WATER: Allow land crossing (escape from coastline)
        # - If on LAND and seeking LAND: Apply normal collision check

        curr_data = query_env_buffers(self.pos[0], self.pos[1], env_buffers)
        currently_on_land = curr_data.get("is_land", False)
        curr_depth = curr_data.get("depth", 9999)

        # Determine if we should apply collision check
        should_check_collision = True
        if currently_on_land and not seek_land:
            # On land, seeking water - allow land crossing to escape
            should_check_collision = False
            self.log("On land seeking water - allowing land crossing for escape")

        if should_check_collision:
            # Apply collision check to all candidates
            safe_candidates = []
            blocked_count = 0
            for c in candidates:
                path_crosses_land = self._path_intersects_land(self.pos, c["pos"], env_buffers)

                # Reject any path that crosses land
                if not path_crosses_land:
                    safe_candidates.append(c)
                else:
                    blocked_count += 1

            # Log collision filtering
            if blocked_count > 0:
                land_status = f"on_land={currently_on_land}, depth={curr_depth:.1f}m"
                self.log(
                    f"COLLISION CHECK ({land_status}): "
                    f"Blocked {blocked_count}/{len(candidates)} paths crossing land"
                )

            # If all paths cross land, keep original candidates as fallback
            # This prevents the seal from getting completely stuck
            if safe_candidates:
                candidates = safe_candidates
            else:
                self.log(
                    f"WARNING: All paths blocked. Pos: {self.pos}, "
                    f"SeekLand: {seek_land}, OnLand: {currently_on_land}"
                )

        # COASTLINE AVOIDANCE: Filter out coastline cells when seeking water FOR FORAGING
        # Coastline cells are problematic - they have is_land=True but inferred depths
        # Seals can get trapped there because they can't eat but appear navigable
        # IMPORTANT: Only avoid coastline when NOT seeking land (i.e., when foraging in water)
        # When seeking land (haul-out), coastline cells are acceptable destinations
        if not seek_land and not currently_on_land and len(candidates) > 0:
            non_coastline_candidates = []
            coastline_count = 0

            for c in candidates:
                # Check if this candidate position is a coastline cell
                c_pos = c["pos"]
                # assert isinstance(c_pos, tuple)
                c_pos_tuple = cast(tuple[float, float], c_pos)
                check_data = query_env_buffers(c_pos_tuple[0], c_pos_tuple[1], env_buffers)
                is_coastline = check_data.get("is_coastline", False)

                if not is_coastline:
                    non_coastline_candidates.append(c)
                else:
                    coastline_count += 1

            # If we have non-coastline options, use them
            if non_coastline_candidates:
                candidates = non_coastline_candidates
                if coastline_count > 0:
                    self.log(
                        f"COASTLINE AVOIDANCE: "
                        f"Filtered out {coastline_count} coastline cells (foraging in water)"
                    )
            else:
                # All candidates are coastline - keep them as fallback but log warning
                self.log(f"WARNING: All {len(candidates)} candidates are coastline cells")

        # Decision Logic
        best_c = None

        if seek_land:
            # Ensure we have a target for Beacon logic (Home Bias)
            if target_pos is None and self.memory.haulout_sites:
                target_pos, _ = self._get_home_bias()

            # 1. Try to find actual Land
            land_matches = [c for c in candidates if c["data"].get("is_land", False)]
            if land_matches:
                best_c = random.choice(land_matches)
            else:
                # 2. Gradient Descent: Find shallowest water (Approach Shelf)
                # Filter out those with invalid depth (9999) if possible
                valid_depths = [
                    c
                    for c in candidates
                    if c["data"].get("depth") is not None and c["data"]["depth"] != 9999
                ]
                if valid_depths:
                    if target_pos:
                        # BEACON FIX: If we have a target (Home),
                        # use it to break ties or guide on flat abyssal plains.
                        # Sort by depth first.
                        valid_depths.sort(key=lambda c: c["data"].get("depth", 9999))
                        # Take top 3 shallowest (or fewer)
                        top_k = valid_depths[:5]
                        # Pick the one that gets us closest to target
                        best_c = min(
                            top_k,
                            key=lambda c: (c["pos"][0] - target_pos[0]) ** 2
                            + (c["pos"][1] - target_pos[1]) ** 2,
                        )
                    else:
                        best_c = min(valid_depths, key=lambda c: c["data"].get("depth", 9999))
                else:
                    # All are void/unknown -> fallback to random choice from all
                    if target_pos:
                        best_c = min(
                            candidates,
                            key=lambda c: (c["pos"][0] - target_pos[0]) ** 2
                            + (c["pos"][1] - target_pos[1]) ** 2,
                        )
                    else:
                        best_c = random.choice(candidates)
        else:
            # Seek Water (Foraging / Transit)
            # Filter to water destinations only (collision already checked above)
            water_matches = [c for c in candidates if not c["data"].get("is_land", False)]

            if water_matches:
                if target_pos:
                    # FIX: Homing / Panic. Move towards target (Home).
                    best_c = min(
                        water_matches,
                        key=lambda c: (c["pos"][0] - target_pos[0]) ** 2
                        + (c["pos"][1] - target_pos[1]) ** 2,
                    )
                else:
                    # FIX: Bias towards Shallow Water (Shelf) to avoid Open Ocean death.
                    # Sort by depth map. (None = 9999).
                    def get_depth(c):
                        d = c["data"].get("depth")
                        return d if d is not None else 9999

                    # Pick one of the top 3 shallowest to allow some randomness but stay safe
                    water_matches.sort(key=get_depth)
                    # Take top 3 or all if less
                    top_k = water_matches[:3]
                    best_c = random.choice(top_k)
            else:
                # All Land (Trapped?) -> Pick random (hoping to escape)
                # FIX: Use memory to find coast (Haulout sites are coastal)
                if self.memory.haulout_sites:
                    # Find closest haulout
                    closest_h = min(
                        self.memory.haulout_sites,
                        key=lambda p: (p[0] - self.pos[0]) ** 2 + (p[1] - self.pos[1]) ** 2,
                    )
                    dist_sq = (closest_h[0] - self.pos[0]) ** 2 + (closest_h[1] - self.pos[1]) ** 2

                    if dist_sq < 0.0025:  # Very close (~0.05^2)
                        # We are at the haulout but still trapped.
                        # Try larger steps to "jump" into water
                        jump_candidates = []
                        for _ in range(10):
                            jp, jh = correlated_random_walk(
                                None, self.pos, self.heading, speed=0.15
                            )  # 3x speed
                            jd = query_env_buffers(jp[0], jp[1], env_buffers)
                            jump_candidates.append({"pos": jp, "heading": jh, "data": jd})

                        water_jumps = [
                            c for c in jump_candidates if not c["data"].get("is_land", False)
                        ]
                        if water_jumps:
                            best_c = random.choice(water_jumps)
                            self.log("Trapped on Haulout! JUMPING into Water.")
                        else:
                            # Still stuck? Just move random
                            best_c = random.choice(candidates)
                    else:
                        # Standard guide to haulout
                        best_c = min(
                            candidates,
                            key=lambda c: (c["pos"][0] - closest_h[0]) ** 2
                            + (c["pos"][1] - closest_h[1]) ** 2,
                        )

                    if not best_c:  # Fallback if logic above failed to set it (unlikely)
                        best_c = random.choice(candidates)

                    self.log("Trapped on Land! Using memory to guide back to coast.")
                else:
                    best_c = random.choice(candidates)

        # Exec Move
        if best_c:
            best_pos = best_c["pos"]
            # assert isinstance(best_pos, tuple)
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
                        self._move_smart(env_buffers, seek_land=True, target_pos=land_pos)
                    else:
                        # No land found - move toward remembered haulout site
                        if self.memory.haulout_sites:
                            target = min(
                                self.memory.haulout_sites,
                                key=lambda p: (p[0] - self.pos[0]) ** 2 + (p[1] - self.pos[1]) ** 2,
                            )
                            self._move_smart(env_buffers, seek_land=True, target_pos=target)
                        else:
                            self._move_smart(env_buffers, seek_land=True, target_pos=None)
                else:
                    # Normal foraging movement
                    # If Deep (>120m), swim towards Land (Shelf)
                    target = None
                    # if depth > 120: target = ... # Old static target was deep (318m)

                    # Seek Land if deep to find shelf (Madeira shelf is narrow, 100m is edge)
                    # But if we are ON LAND, we must seek water!
                    is_land = env_data.get("is_land", False)
                    if is_land:
                        # SMART WATER ESCAPE: Find nearest water
                        self.log("On land - searching for nearest water to escape")
                        water_pos, water_dist = self._find_nearest_water(
                            env_buffers, max_radius_km=5.0
                        )
                        if water_pos:
                            self.log(f"WATER ESCAPE: Navigating to water at {water_dist:.2f}km")
                            self._move_smart(env_buffers, seek_land=False, target_pos=water_pos)
                        else:
                            # No water found - try random movement
                            self.log("WARNING: No water found nearby, trying random escape")
                            self._move_smart(env_buffers, seek_land=False, target_pos=None)
                    else:
                        do_seek_land = depth > 100
                        self.log(f"Forage Move. Depth={depth:.1f}m. SeekLand={do_seek_land}")
                        self._move_smart(env_buffers, seek_land=do_seek_land, target_pos=None)
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
                    self._move_smart(env_buffers, seek_land=False, target_pos=water_pos)
                else:
                    # No water found nearby - try random movement
                    self.log("WARNING: No water found nearby, trying random escape")
                    self._move_smart(env_buffers, seek_land=False, target_pos=None)
            else:
                # Normal transit feeding in water
                do_seek_land = d_check is None or d_check > 100
                self._move_smart(env_buffers, seek_land=do_seek_land, target_pos=None)

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
        self._move_smart(env_buffers, seek_land=False)

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
            self._move_smart(env_buffers, seek_land=True, target_pos=target)
        else:
            # No target at all - just move toward land generally
            self._move_smart(env_buffers, seek_land=True, target_pos=None)

        # Timeout: If hunting for land too long (>5h), give up and bottle (Sleep in water)
        if self.state_duration > 5:
            self.log("Haulout Warning: Could not find land for 5h. Bottling in water.")
            self.state = SealState.SLEEPING

    def rest(self, env_data, env_buffers):
        digestion_rate = 3500.0  # Adjusted for cephalopods
        if self.stomach_load > 0:
            self.energy += digestion_rate
            self.stomach_load -= digestion_rate / 3500.0
            self.stomach_load = max(0, self.stomach_load)
        self.energy += 20.0
        self.energy = min(self.energy, self.max_energy)

    def sleep(self, env_data, env_buffers):
        # Removed strict 'if not is_land: return' to allow Water Sleeping (Bottling)

        digestion_rate = 3500.0
        if self.stomach_load > 0:
            self.energy += digestion_rate
            self.stomach_load -= digestion_rate / 3500.0
            self.stomach_load = max(0, self.stomach_load)

        # If sleeping in water, energy recovery is less efficient (thermal loss)?
        # For now keep it same (RMR is burn, so net is negative usually unless digesting)

        self.energy = min(self.energy, self.max_energy)

    def burn_energy(self):
        # Active Metabolic Rate (AMR) = 1.5 * RMR for active states
        multiplier = 1.0
        if self.state in [SealState.FORAGING, SealState.TRANSITING, SealState.HAULING_OUT]:
            multiplier = 1.5

        self.energy -= self.rmr * multiplier
