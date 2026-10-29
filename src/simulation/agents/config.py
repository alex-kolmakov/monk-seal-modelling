"""
Seal Agent Configuration

Tunable parameters for the Mediterranean Monk Seal simulation.
Adjust these values to calibrate the model for different environments
(e.g., oligotrophic Madeira vs productive Cabo Blanco).
"""

from dataclasses import dataclass


@dataclass
class SealConfig:
    """Configuration parameters for seal physiology and behavior."""

    # === PHYSIOLOGY ===
    mass: float = 300.0  # kg - Adult female body mass
    stomach_capacity: float = 15.0  # kg - Maximum stomach load (~5% body mass)
    initial_energy: float = 90000.0  # Starting energy (90% of max)
    max_energy: float = 100000.0  # Short-term energy buffer; the reserve is body mass

    # === METABOLIC RATES ===
    # RMR: Resting Metabolic Rate (kJ/h)
    # Kleiber baseline for 300kg: ~880 kJ/h
    # Phocid seals at rest: ~1.0–1.3× Kleiber (Lavigne et al. 1986; Bowen & Lavigne 1987)
    # 1,056 kJ/h = 1.20× Kleiber, calibrated (2026-10-08, three seeds, Jan-May 2026):
    # body mass roughly levels off and ~1 in 90 seals starves in five months, in line
    # with adult survival 0.98 F / 0.90 M (Pires et al. 2023).
    # Re-checked on EMODnet bathymetry (2026-10-29, 3 seeds of 30 seals, Jan-May 2026, 1.10-1.30x):
    # median mass in May 316 kg (320 kg on the 3 km grid) and the same 3 of 90 starving at 1.20x,
    # so 1,056 stays; the colony settings (active_digestion_fraction) are what moved.
    rmr: float = 1056.0  # kJ/h at the starting mass; scales with mass^0.75

    # AMR multiplier (Active Metabolic Rate = RMR × this factor)
    amr_multiplier: float = 1.5  # Applied during FORAGING, TRANSITING, HAULING_OUT
    recovery_metabolic_multiplier: float = 0.5  # Near-torpid RECOVERY (model assumption)

    # === FORAGING RATES (base rates, modulated by HSI) ===
    # Depth-based intake rates (kg/h) - before HSI multiplier
    shallow_foraging_rate: float = 3.0  # 0-50m depth (95% of dives occur here)
    medium_foraging_rate: float = 1.0  # 50-100m depth
    deep_foraging_rate: float = 0.0  # >100m depth (cannot reach benthos)

    # === PRODUCTIVITY MULTIPLIER ===
    # HSI = min(chlorophyll / hsi_chl_threshold, 1.0)
    # Final rate = base_rate × max(hsi_floor, HSI)
    hsi_chl_threshold: float = 0.5  # mg/m³ - Chlorophyll for HSI=1.0
    hsi_floor: float = 0.5  # Minimum multiplier (prevents starvation in oligotrophic waters)

    # === ENERGY THRESHOLDS ===
    starvation_threshold: float = 0.10  # 10% of max energy = death
    critical_energy_threshold: float = 0.15  # 15% = desperate foraging mode
    # Behavioural switches (fractions of max energy / stomach capacity; model assumptions)
    tired_energy_fraction: float = 0.20  # Below: too tired to forage, seek rest
    wake_energy_fraction: float = 0.95  # Sleeping on land with empty stomach: wake below this
    recovery_exit_fraction: float = 0.50  # RECOVERY ends above this energy
    full_stomach_fraction: float = 0.8  # Above: stop foraging and rest
    low_tide_haulout_stomach_fraction: float = 0.5  # Low tide + this full: haul out early

    # === TIDAL THRESHOLDS (metres above mean sea level, see environment.TIDE_DATUM_M) ===
    # PLACEHOLDERS: no cave-beach height reference yet [fact-check]. +/-0.30 m puts
    # ~1/3 of hours above/below at the Desertas (IBI zos, Jan-May 2026), matching the
    # share the old normalised 0.70/0.30 sine thresholds produced.
    high_tide_m: float = 0.30  # Above this, caves flood
    low_tide_m: float = -0.30  # Below this, cave beaches are exposed

    # === WHERE SEALS MAY REST ===
    # (lat_min, lat_max, lon_min, lon_max). When set, seals rest, sleep and haul out only
    # inside this box (travelling to it first); None = anywhere, as before. Model
    # assumption: the colony uses the Desertas caves (IFCN call, 2026-10-22).
    haulout_box: tuple[float, float, float, float] | None = None

    # === WHERE SEALS MAY FORAGE ===
    # Metres. When set, a seal is FORAGING only where the sea is at most this deep: it will
    # not step off the shelf while foraging, and a seal that finds itself deeper switches to
    # TRANSITING and heads for the shelf. None = anywhere, as before. Model assumption; the
    # intake rate is already 0 below 100 m (deep_foraging_rate), so 100 m loses no food.
    forage_max_depth_m: float | None = None

    # (lat_min, lat_max, lon_min, lon_max). When set, seals do not forage inside this box:
    # a seal that is hungry there leaves for the nearest feeding water outside it (and comes
    # back to rest). Without it the Desertas shelf feeds a seal all the time, so it never
    # has a reason to leave. None = may forage anywhere, as before. Model assumption.
    forage_exclude_box: tuple[float, float, float, float] | None = None

    # (lat_min, lat_max, lon_min, lon_max). When set, feeding cells are picked only inside this
    # box, so a trip range wide enough for a day trip round Madeira does not also reach a far
    # shelf such as Porto Santo's. None = anywhere. Model assumption.
    forage_box: tuple[float, float, float, float] | None = None

    # Day-long feeding trips (model assumption). Off: a seal half full at low tide heads for the
    # roost however far away it is, and one that arrives at high tide is woken at once and sent
    # out again, so with a roost 25 km from the feeding grounds it shuttles with the tide,
    # feeds about 1 h a trip and digests almost nothing (a 12 kg stomach is only emptied at
    # rest). On: a seal away from the roost stays out until its stomach is full (or it is tired),
    # and one at the roost with food in the stomach rests in the water to digest instead of
    # leaving at high tide.
    feeding_trips: bool = False

    # Where a seal feeds when it leaves the roost (model assumption). None: the nearest allowed
    # water, so the whole colony feeds on one patch next to the roost. A number: each trip picks
    # a random allowed cell (shelf, outside the exclusion box) within this many km over open
    # water, so seals spread along the shelf. A day trip is about 45 km each way at 5.5 km/h:
    # 8 h out, 6 h feeding, 8 h back.
    feeding_range_km: float | None = None

    # Longest time away from the roost box before a feeding seal heads home (model assumption;
    # needs haulout_box). None: only a full stomach (or tiredness) sends it home. With digestion
    # on the move (active_digestion_fraction) a seal's stomach may never fill, so without a limit
    # it stays at the feeding grounds for days. A day trip is 8 h out, ~6 h feeding, 8 h back:
    # 16 h away before turning round is home within the day. A seal on its way home is no longer
    # turned back to feeding by high tide (it cannot land, but it can rest afloat at the roost).
    max_hours_away: float | None = None

    # How fast a seal swims when it travels to feeding water or back to the roost (model
    # assumption). None: 0.05 degrees an hour, about 5.5 km/h. A feeding trip around Madeira is
    # 100-150 km, so a same-day trip needs a faster, sustained pace than that default.
    trip_speed_km_h: float | None = None

    # Be back in the roost box this many hours after leaving it (model assumption; needs
    # haulout_box). The seal turns for home when the hours spent away plus the swim back (distance
    # to the box centre at the trip speed) reach this. None: not used. Unlike max_hours_away,
    # which counts only the way out and feeding, so the return comes on top of it.
    home_by_hours: float | None = None

    # === STORM THRESHOLDS ===
    storm_threshold: float = 2.5  # SWH (m) - Seals seek shelter
    max_landing_swell: float = 4.0  # SWH (m) - Cannot safely haul out
    # Behaviour above max_landing_swell (model assumptions; Pires et al. 2023 describe
    # storm swell flooding the inner cave beaches)
    storm_blocks_landing: bool = True  # No landing: a seal hauling out turns back to sea
    storm_wash_off: bool = True  # Seals already ashore are washed back into the water

    # === BODY MASS (the fasting reserve; max_energy is only the short-term buffer) ===
    # Surplus above max_energy is stored as body mass up to max_mass (the rest is
    # discarded); below critical_energy_threshold, mass above lean_mass is drawn back
    # into energy; RMR scales with (mass / mass at start)^0.75 (Kleiber).
    # No body composition data exist for either monk seal species (monk seal
    # researcher, pers. comm. 2026-10-07), so the values are northern elephant seal
    # proxies. The check: Hawaiian monk seal females fast through a 5-7 week
    # lactation (Johanos et al. 1994).
    mass_dynamics: bool = True
    # kJ/kg stored or mobilised. Elephant seal females gain 1,664 MJ per 86.7 kg at sea
    # (19 MJ/kg, Holser et al. 2023) and lose ~23 MJ/kg in lactation (from Fowler et al.
    # 2008 mass and blubber change).
    tissue_energy_density: float = 20000.0
    # kg - mass is never mobilised below this: 60% of max_mass, as elephant seal females
    # lose up to ~40% of their mass in lactation (Fowler et al. 2008)
    lean_mass: float = 240.0
    max_mass: float = 400.0  # kg - no storage above this (top of the ADW 240-400 kg range)

    # === MORTALITY ===
    # Background risk for adult males (age >= 4), from human interaction / boldness.
    # Model assumption. Upper bound: Pires et al. 2023 give adult male survival 0.90
    # (10%/yr from all causes); starvation deaths are modelled separately, so this is lower.
    male_annual_risk: float = 0.05

    # === DIGESTION ===
    digestion_rate: float = 1.0  # kg/h - Rate of stomach emptying during rest
    # Digestion while swimming, as a fraction of digestion_rate (model assumption). 0 = the stomach
    # is only emptied at rest or asleep, so a seal that swims 60% of the time (a 45 km commute
    # each way) can never process a day's food, however much it catches: at most ~7 kg/day = 25 MJ
    # against a 34 MJ/day burn. Real seals digest while travelling.
    active_digestion_fraction: float = 0.0
    energy_per_kg_food: float = 3500.0  # kJ per kg of digested food


# Desertas Islands (same box as environment.DESERTAS_BOX): use with replace(MADEIRA_CONFIG,
# haulout_box=...)
DESERTAS_HAULOUT_BOX = (32.35, 32.60, -16.60, -16.40)
SHELF_DEPTH_M = 100.0  # foraging limit that matches the shelf in the intake rates
# Where seals may not feed: the Desertas and their own shelf (wider than the haul-out box, which
# hugs the islands)
DESERTAS_FEED_EXCLUDE_BOX = (32.30, 32.68, -16.66, -16.30)
# Where seals may feed: the waters of Madeira and the Desertas. Its north edge is 4 km below the
# first Porto Santo shelf (32.99°N) and 55 km from the Desertas.
MADEIRA_FORAGE_BOX = (32.20, 32.95, -17.50, -16.00)

# Default configuration for Madeira (oligotrophic environment)
MADEIRA_CONFIG = SealConfig(
    rmr=1056.0,  # 1.20× Kleiber; holds on EMODnet too (2026-10-29)
    hsi_floor=0.5,  # Higher floor for oligotrophic waters
)
