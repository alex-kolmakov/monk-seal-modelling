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
| `max_energy` | 100000.0 | kJ | Maximum energy storage capacity |

**Tuning tips:**
- Increase `stomach_capacity` to allow more "binge feeding" between rest periods
- Adjust `initial_energy` to simulate seals starting in different body conditions
- `max_energy` affects how long seals can survive without food

### Metabolic Rates

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `rmr` | 750.0 | kJ/h | Resting Metabolic Rate (energy burn at rest) |
| `amr_multiplier` | 1.5 | - | Active Metabolic Rate multiplier (AMR = RMR × this) |
| `recovery_metabolic_multiplier` | 0.5 | - | Metabolic multiplier in RECOVERY (near-torpid; model assumption) |

**Tuning tips:**
- `rmr` is the most sensitive parameter for survival outcomes
- Lower RMR (500-650) = hypometabolism scenarios
- Higher RMR (750-900) = closer to the reported phocid range; 750 is the Madeira default
- `amr_multiplier` affects energy cost of foraging, transiting, and hauling out

**Derivation:**
```
Kleiber equation: RMR = 293 × M^0.75
For 300kg seal: 293 × 72.08 ≈ 880 kJ/h (terrestrial baseline)
Phocid seals at rest: ~1.0–1.3× Kleiber (Lavigne et al. 1986) (unverified)
Madeira model: uses 750 kJ/h (~0.85× Kleiber), below that range — a model assumption
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
| `starvation_threshold` | 0.10 | ratio | Energy level that causes death (10% of max) |
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

**Tuning tips:**
- Wider gap (e.g., −0.50 to +0.50) = more time available for both hauling out and foraging
- Narrower gap (e.g., −0.15 to +0.15) = tighter activity windows
- For Mediterranean simulations (negligible tides), set both to `float("inf")`

### Storm Thresholds

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `storm_threshold` | 2.5 | m SWH | Wave height that triggers shelter-seeking |
| `max_landing_swell` | 4.0 | m SWH | Wave height that prevents hauling out |

**Tuning tips:**
- Lower thresholds = more cautious seals (seek shelter earlier)
- Higher thresholds = seals tolerate rougher conditions
- The gap affects how long seals remain in "storm mode"

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
- Maintenance at rest needs ~5.1 kg food/day (18,000 kJ at 750 kJ/h RMR ÷ 3,500 kJ/kg); active states need more

## Pre-configured Environments

### Madeira (Default)

Oligotrophic Atlantic environment with strong tidal forcing:

```python
MADEIRA_CONFIG = SealConfig(
    rmr=750.0,        # Phocid RMR baseline; food scarcity affects behaviour, not physiology
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
