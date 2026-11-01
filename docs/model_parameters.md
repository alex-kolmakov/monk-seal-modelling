# Model Parameters & Tuning Guide

This document describes all tunable parameters in the Monk Seal ABM and how to adjust them for different simulation scenarios.

## Configuration File

All model parameters are defined in `src/simulation/agents/config.py` as a `SealConfig` dataclass. You can create custom configurations for different environments or sensitivity analyses.

```python
from src.simulation.agents.config import SealConfig, MADEIRA_CONFIG

# Use default Madeira configuration
config = MADEIRA_CONFIG

# Or create a custom configuration
custom_config = SealConfig(
    rmr=600.0,           # Lower metabolic rate
    hsi_floor=0.3,       # Lower productivity floor
    storm_threshold=3.0  # Higher storm tolerance
)
```

## Parameter Reference

### Physiology

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `mass` | 300.0 | kg | Adult body mass (used for allometric calculations) |
| `stomach_capacity` | 15.0 | kg | Maximum stomach load (~5% of body mass) |
| `initial_energy` | 90000.0 | kJ | Starting energy level (90% of max) |
| `max_energy` | 100000.0 | kJ | Short-term energy buffer; the fasting reserve is body mass, see Body Mass |

**Tuning tips:**
- Increase `stomach_capacity` to allow more "binge feeding" between rest periods
- Adjust `initial_energy` to simulate seals starting in different body conditions
- `max_energy` sets how soon a hungry seal starts drawing on body mass; with `mass_dynamics` off it is the whole reserve

### Metabolic Rates

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `rmr` | 1056.0 | kJ/h | Resting Metabolic Rate at the starting mass (scales with mass^0.75) |
| `amr_multiplier` | 1.5 | - | Active Metabolic Rate multiplier (AMR = RMR × this) |
| `recovery_metabolic_multiplier` | 0.5 | - | Metabolic multiplier in RECOVERY (near-torpid; model assumption) |

**Tuning tips:**
- `rmr` is the most sensitive parameter for survival outcomes
- Lower RMR (500-750) = hypometabolism scenarios; seals gain mass up to `max_mass`
- 880–1,144 = the reported phocid range (1.0–1.3× Kleiber); 1,056 is the Madeira default
- `amr_multiplier` affects energy cost of foraging, transiting, and hauling out

**Derivation:**
```
Kleiber equation: RMR = 293 × M^0.75
For 300kg seal: 293 × 72.08 ≈ 880 kJ/h (terrestrial baseline)
Phocid seals at rest: ~1.0–1.3× Kleiber (Lavigne et al. 1986) (unverified)
Madeira model: uses 1,056 kJ/h (1.20× Kleiber), calibrated — see Body Mass
```

### Foraging Rates

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `shallow_foraging_rate` | 3.0 | kg/h | Food intake rate at 0-50m depth |
| `medium_foraging_rate` | 1.0 | kg/h | Food intake rate at 50-100m depth |
| `deep_foraging_rate` | 0.0 | kg/h | Food intake rate at >100m depth |

**Tuning tips:**
- These are **base rates** before HSI (productivity) modulation
- Set `deep_foraging_rate > 0` if simulating seals that can reach deep benthos
- Increase rates to simulate more productive foraging grounds

### Productivity (HSI)

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `hsi_chl_threshold` | 0.5 | mg/m³ | Chlorophyll level for HSI=1.0 |
| `hsi_floor` | 0.5 | - | Minimum productivity multiplier |

**How HSI works:**
```python
hsi = min(chlorophyll / hsi_chl_threshold, 1.0)
effective_rate = base_foraging_rate × max(hsi_floor, hsi)
```

**Tuning tips:**
- `hsi_floor` prevents starvation in oligotrophic waters
- Lower `hsi_floor` (0.2-0.3) = more realistic but higher mortality
- Higher `hsi_floor` (0.5-0.7) = guaranteed minimum food intake
- Adjust `hsi_chl_threshold` based on your study area's chlorophyll levels

### Energy Thresholds

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `starvation_threshold` | 0.10 | ratio | Energy level that causes death (10% of max); reached only when body mass is down to `lean_mass` |
| `critical_energy_threshold` | 0.15 | ratio | Energy level that triggers desperate foraging (15%) |
| `tired_energy_fraction` | 0.20 | ratio | Below this, a foraging seal stops to rest; a bottling seal stays asleep |
| `wake_energy_fraction` | 0.95 | ratio | A seal asleep on land with an empty stomach wakes below this |
| `recovery_exit_fraction` | 0.50 | ratio | RECOVERY ends above this energy |
| `full_stomach_fraction` | 0.8 | ratio of capacity | Above this, a foraging seal stops to rest |
| `low_tide_haulout_stomach_fraction` | 0.5 | ratio of capacity | At low tide, a seal this full hauls out early |

The five behavioural fractions are model assumptions, not field values. All of them
are read from `SealConfig`; `tests/unit/test_config_fields.py` fails if any field stops
affecting behaviour.

**Tuning tips:**
- Increasing thresholds makes seals more "cautious" (seek food earlier)
- Decreasing thresholds allows seals to push closer to starvation
- The gap between critical and starvation determines the "danger zone" duration

### Tidal Thresholds

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `high_tide_m` | +0.30 | m above mean sea level | Tide height that floods caves (forces seals into water) |
| `low_tide_m` | −0.30 | m above mean sea level | Tide height that exposes cave beaches (allows haul-out) |

Placeholders: no cave-beach height reference yet. At the Desertas (IBI `zos`, Jan–May 2026)
about a third of hours fall above `high_tide_m` and a third below `low_tide_m`.

### Where seals may rest

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `haulout_box` | `None` | (lat_min, lat_max, lon_min, lon_max) | When set, seals rest, sleep and haul out only inside the box and travel to it first. `None` = anywhere. `DESERTAS_HAULOUT_BOX` = 32.35–32.60°N, 16.60–16.40°W. |

Model assumption: the colony rests in the Desertas caves (IFCN call, 2026-10-22). `run_real_long --haulout-desertas` sets it.
Seals in RECOVERY stay where they are (they are stationary and critically low on energy), so they can rest outside the box.

### Where seals may forage

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `forage_max_depth_m` | `None` | m | When set, a seal is FORAGING only where the sea is at most this deep. It does not step off the shelf while foraging, and a seal that finds itself deeper switches to TRANSITING and heads for the shelf. `None` = anywhere. `SHELF_DEPTH_M` = 100. |

Model assumption. The intake rate is already 0 below 100 m (`deep_foraging_rate`), so 100 m loses no food. This is stricter than the diving
record: Madeira seals dive to 200 m and deeper (IFCN call, 2026-10-22). `run_real_long --forage-shelf` sets it.
In the Madeira forecast run, foraging in water deeper than 100 m fell from 38% of foraging hours to 0.

### No feeding at the roost

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `forage_exclude_box` | `None` | (lat_min, lat_max, lon_min, lon_max) | When set, seals do not forage inside the box. A seal that is hungry there switches to TRANSITING and heads for the nearest feeding water outside it (straight over open water for a long leg, hugging the shelf on the last stretch), and returns to rest when full or tired. `None` = may forage anywhere. `DESERTAS_FEED_EXCLUDE_BOX` = 32.30–32.68°N, 16.66–16.30°W. |
| `feeding_trips` | `False` | bool | When on, a seal away from the roost does not turn for home at low tide with a half-full stomach: it stays out until full or tired. A seal in the roost box with food in its stomach rests in the water to digest (RESTING) instead of being woken by high tide and sent out again. Off, a roost 25 km from the feeding grounds makes seals shuttle with the tide: about 1 h of feeding a trip and almost no digestion. Model assumption. |
| `feeding_range_km` | `None` | km | When set (and foraging is restricted by `forage_max_depth_m` or `forage_exclude_box`), each trip from the roost picks a random allowed feeding cell within this distance over open water (cells drawn evenly over the area, the first with a clear sea route is taken), instead of the nearest one. Without it the whole colony feeds on one patch next to the roost. A day trip at 5.5 km/h is about 45 km each way. A target not reached in 14 h is dropped and a new one picked. The nearest-cell search (`None`) also skips cells across an island: a seal on Madeira's south coast used to freeze for 160 h heading for a cell on the north shore. Model assumption. |
| `active_digestion_fraction` | `0.0` | fraction | Digestion while FORAGING, TRANSITING or HAULING_OUT, as a fraction of `digestion_rate`. At 0 the stomach is only emptied at rest or asleep, so a seal that swims 60% of the time can process at most ~7 kg/day (25 MJ) against a 34 MJ/day burn, however much it catches. Prototype colony (Desertas roost, shelf feeding, 45 km trips): 0.4 keeps mass level on calm January 2026 data (+1 kg per seal in 21 days); 0.3 loses 7 kg, 0.5 gains 5 kg and the seals stay at the feeding grounds (63% of hours foraging). Model assumption, calibrated. |
| `max_hours_away` | `None` | h | With `haulout_box` set: a FORAGING seal that has been outside the roost box this many hours switches to HAULING_OUT and heads home, whatever its stomach holds. `None` = only a full stomach or tiredness sends it home. Needed once `active_digestion_fraction` > 0, because a seal that digests as it swims never fills up and would stay at the feeding grounds for days. A seal on its way home (`feeding_trips`) is no longer turned back to FORAGING by high tide. Prototype: 24 (calm January 2026: +0.3 kg per seal in 21 days, foraging 45% of hours; 16 loses 5 kg). Model assumption, calibrated. |
| `trip_speed_km_h` | `None` | km/h | Swimming pace to feeding water and back to the roost. `None` = 0.05 degrees an hour, about 5.5 km/h. A trip around Madeira is 100-150 km, so a same-day trip needs a faster, sustained pace. Model assumption, no source: 10 km/h (2.8 m/s) is a cruising pace at the upper end of what is reported for phocids, 8 km/h keeps the same-day trips but costs the colony about 5 kg in the calm control. |
| `home_by_hours` | `None` | h | With `haulout_box` set: a feeding seal turns for the roost when the hours since it left the box plus the swim back (distance to the box centre at `trip_speed_km_h`) reach this. `max_hours_away` counts only the way out and feeding, so with it a seal is home after 24-38 h; `home_by_hours` 24 makes 94-99% of trips same-day. Model assumption. |

Model assumption. Without it the Desertas shelf feeds a seal all the time, so after hauling out it has no reason to leave and
the colony never commutes to Madeira. The box is wider than `DESERTAS_HAULOUT_BOX` on purpose: with the haul-out box
the seals fed 1.7-3 km outside its edge, still on the Desertas shelf. `run_real_long --no-forage-at-desertas` sets it.
In the Madeira forecast run (12 seals, 8 days) foraging inside the box fell to 0 and 973 of 2,304 seal-hours were on the Madeira side.
Side effect: sleeping fell from 350 to 128 hours and about 45% of the hours are spent travelling (TRANSITING or HAULING_OUT), because
high tide forces a seal off the beach and a seal that wants to feed must cross about 30 km. Tune with the tide thresholds
and the haul-out rules before reading anything biological into it.

**Tuning tips:**
- Wider gap (e.g., −0.50 to +0.50) = more time available for both hauling out and foraging
- Narrower gap (e.g., −0.15 to +0.15) = tighter activity windows
- For Mediterranean simulations (negligible tides), set both to `float("inf")`

### Storm Thresholds

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `storm_threshold` | 2.5 | m SWH | Wave height that triggers shelter-seeking |
| `max_landing_swell` | 4.0 | m SWH | Wave height that prevents hauling out |
| `storm_blocks_landing` | True | toggle | Above `max_landing_swell`, a seal hauling out turns back to sea |
| `storm_wash_off` | True | toggle | Above `max_landing_swell`, seals ashore are washed back into the water |

Both toggles are model assumptions: Pires et al. 2023 describe storm swell flooding the inner cave beaches. Land cells read the swell of the nearest water cell.

**Tuning tips:**
- Lower thresholds = more cautious seals (seek shelter earlier)
- Higher thresholds = seals tolerate rougher conditions
- The gap affects how long seals remain in "storm mode"

### Body Mass (the fasting reserve)

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `mass_dynamics` | True | toggle | Store surplus energy as body mass and draw it back when energy runs low |
| `tissue_energy_density` | 20000.0 | kJ/kg | Energy per kg of body mass stored or mobilised |
| `lean_mass` | 240.0 | kg | Mass is never mobilised below this |
| `max_mass` | 400.0 | kg | No storage above this; further surplus is discarded |

Surplus above `max_energy` becomes mass (`energy_stored_kj`) up to `max_mass`, and is discarded beyond it; below `critical_energy_threshold`, mass above `lean_mass` refills energy up to that level (`energy_mobilised_kj`); RMR = `rmr` × (mass / `mass`)^0.75. A seal starves only once its mass is down to `lean_mass`. The history carries `mass`, `energy_stored_kj` and `energy_mobilised_kj`. With `mass_dynamics` off there is one energy pool and a resting seal starves in about 3 days.

**Where the values come from.** No body composition analysis exists for adult females of either monk seal species (monk seal researcher, pers. comm. 2026-10-07), so these are northern elephant seal proxies, the best-studied related phocid:

- `tissue_energy_density`: females gain 1,663.6 MJ for 86.7 kg over a post-breeding foraging trip, 19 MJ/kg (N = 247, Holser et al. 2023). In lactation they go from 432.7 kg at 38.5% blubber to 317.0 kg at 30.6% in 17 days (Fowler et al. 2008), which at 35.4 MJ/kg adipose and 4.9 MJ/kg lean tissue (Holser et al. 2023) is about 23 MJ/kg lost. 20 MJ/kg sits between the two.
- `lean_mass`: 60% of `max_mass`, as females lose up to ~40% of their mass over lactation (Fowler et al. 2008).
- `max_mass`: the top of the 240–400 kg adult range (Animal Diversity Web).

**The check.** Hawaiian monk seal females fast through a lactation of 39 days on average (range 27–50) and are not starving at the end (Johanos et al. 1994). In the model a 300 kg seal at rest has about 60 kg, or 1,200 MJ, to draw on, about seven weeks; a 400 kg seal has 3,200 MJ. `test_resting_female_survives_a_seven_week_fast` holds the model to this. Mediterranean monk seals also forage while they have a dependent pup, so they depend less on stored lipid than Hawaiian ones.

**What keeps mass in check.** Metabolism scales with mass, so a heavier seal burns more until expenditure meets intake. At the old `rmr` of 750 kJ/h that point lay near 500 kg; at the calibrated 1,056 kJ/h (1.20× Kleiber, see the RMR derivation in `seal_agent_documentation.md`) the median seal's gain slows to about 1 kg a month.

**What it does to a run.** 2026 Jan–May, 30 seals, seed 42:

| | Single pool, `rmr` 750 | Reserve, `rmr` 750 | Reserve, `rmr` 1,056 (default) |
|---|---|---|---|
| Starvation deaths | 8 | 0 | 1 |
| Median mass by month (Jan → May) | 300 kg flat | 304 → 364 kg | 300 → 322 kg |
| Mass range at end | — | 284–400 kg | 265–347 kg |
| Food per seal per day | 9.6 kg | 9.6 kg | 9.8 kg (about 3% of body mass) |
| Time foraging | 35% | 37% | 35% |

There are still no births, lactation or molt to spend the reserve on. `rmr` must be recalibrated when the bathymetry changes.

**EMODnet bathymetry (optional).** `run_real_long --emodnet-bathymetry` replaces the depth map derived from the Copernicus physics file (3 km) with EMODnet at about 0.4 km (`python -m src.data_ingestion.download_bathymetry` fetches it). Off by default. It puts the Desertas shelf at about 10-30 m where the 3 km grid has 150-220 m. Recalibrated 2026-10-29 (real Jan-May 2026 data, three seeds):

- `rmr` stays at 1,056 (1.20× Kleiber). Plain model, 30 seals: median mass in May 316 kg on EMODnet and 320 kg on the 3 km grid, 3 of 90 seals starving on both. 1.15× leaves seals heavier (324 kg, 2 of 90), 1.25× lighter (305 kg, 3 of 90) and 1.30× starves 7 of 90. The 1 of 90 quoted in `seal_agent_documentation.md` is not reproduced by these seeds on either grid.
- Day trips around Madeira. With the 3 km grid and `max_hours_away` 24 the median trip kept the seal away 27 h and only a third of trips ended within a day (feeding reached the north and west coasts, up to 85 km out). On EMODnet the Desertas colony uses `trip_speed_km_h` 10, `feeding_range_km` 90, `home_by_hours` 24 (instead of `max_hours_away`) and `active_digestion_fraction` 0.7. Calm control (14 days, 12 seals, 3 seeds): 94-95% of trips back within 24 h, median 22 h away, median farthest point 70 km from the roost (p90 78 km), 70% of foraging on the north coast, mass change -0.8 kg, 36% of hours foraging. Slower swimming makes the day trip cost mass at once: at the default 5.5 km/h with `home_by_hours` 24 the colony loses 8-16 kg and forages 10-26% of the time. The digestion rate does not level the mass cleanly at this pace (0.5-0.7 give -1.9 to -0.8 kg, not monotonic over three seeds).

### Mortality

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `male_annual_risk` | 0.05 | per year | Background death risk for adult males (age ≥ 4), applied hourly |

Model assumption. Pires et al. 2023 give adult male survival 0.90 (10%/yr from all causes) as an upper bound; starvation is modelled separately, so this value sits below it.

### Digestion

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `digestion_rate` | 1.0 | kg/h | Rate of stomach emptying during rest |
| `energy_per_kg_food` | 3500.0 | kJ/kg | Energy gained per kg of digested food |

**Tuning tips:**
- Higher `digestion_rate` = faster recovery, shorter rest periods needed
- `energy_per_kg_food` affects the energy balance equation directly
- Maintenance at rest needs ~7.2 kg food/day (25,344 kJ at 1,056 kJ/h RMR ÷ 3,500 kJ/kg); active states need more

## Pre-configured Environments

### Madeira (Default)

Oligotrophic Atlantic environment with strong tidal forcing:

```python
MADEIRA_CONFIG = SealConfig(
    rmr=1056.0,       # 1.20× Kleiber; holds on EMODnet too (2026-10-29)
    hsi_floor=0.5,    # Higher floor for low-chlorophyll waters
)
```

### Custom: Productive Environment (e.g., Cabo Blanco)

For nutrient-rich waters with higher prey availability. Illustrative values, not calibrated:

```python
CABO_BLANCO_CONFIG = SealConfig(
    hsi_floor=0.3,                # Lower floor (more food available)
    shallow_foraging_rate=4.0,    # Higher base foraging rate
    hsi_chl_threshold=1.0,        # Higher chlorophyll baseline
)
```

### Custom: Mediterranean (Negligible Tides)

For Mediterranean populations where tides don't drive behavior:

```python
MEDITERRANEAN_CONFIG = SealConfig(
    high_tide_m=float("inf"),     # Caves never flood
    low_tide_m=float("inf"),      # Seals can haul out anytime
    # Day/night behavior would need separate implementation
)
```

## Sensitivity Analysis

Key parameters to vary for sensitivity analysis:

| Parameter | Suggested Range | Impact |
|-----------|-----------------|--------|
| `rmr` | 400-900 kJ/h (sweep range, not a literature range) | Survival rates, mortality timing |
| `hsi_floor` | 0.2-0.7 | Starvation risk in oligotrophic waters |
| `shallow_foraging_rate` | 2.0-5.0 kg/h | Energy acquisition, activity budgets |
| `starvation_threshold` | 0.05-0.15 | Mortality timing |
| `storm_threshold` | 2.0-3.5 m | Storm-related behavior frequency |

## Using Custom Configurations

### In Simulation Code

```python
from src.simulation.agents.config import SealConfig
from src.simulation.agents.seal import SealAgent

# Create custom config
my_config = SealConfig(rmr=600.0, hsi_floor=0.4)

# Initialize agent with custom config
agent = SealAgent(
    agent_id="1",
    start_pos=(32.5, -16.5),
    age=8,
    sex="F",
    config=my_config,
    seed=42,
)
```

### For Batch Experiments

```python
# Parameter sweep example
from src.simulation.run_real_long import run_long_simulation

for rmr in [400, 500, 600, 700, 800]:
    run_long_simulation(
        start_time="2026-01-01 00:00",
        duration_days=60,
        data_tag="20260101_20260530",
        output_file=f"sweep_rmr{rmr}.csv",
        seed=42,
        num_agents=30,
        config=SealConfig(rmr=rmr),
    )
# Deaths per run: n_deaths_total in data/real_long/sweep_rmr{rmr}_stats.csv
```

## Parameter Validation Status

Each parameter either cites a source or is marked as a model assumption; claims that could not be checked against the source are marked *unverified*. See [Seal Agent Documentation](seal_agent_documentation.md) for sources.
