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
    rmr=600.0,           # Higher metabolic rate
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
| `rmr` | 500.0 | kJ/h | Resting Metabolic Rate (energy burn at rest) |
| `amr_multiplier` | 1.5 | - | Active Metabolic Rate multiplier (AMR = RMR × this) |

**Tuning tips:**
- `rmr` is the most sensitive parameter for survival outcomes
- Lower RMR (400-500) = oligotrophic adaptation (Madeira)
- Higher RMR (700-900) = productive environments (Cabo Blanco)
- `amr_multiplier` affects energy cost of foraging, transiting, and hauling out

**Derivation:**
```
Kleiber equation: RMR = 293 × M^0.75
For 300kg seal: 293 × 72.08 ≈ 880 kJ/h (terrestrial baseline)
Marine mammals: typically 1.5-2× higher (~1320-1760 kJ/h)
Madeira model: uses 500 kJ/h (hypometabolism hypothesis)
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

**Tuning tips:**
- Increasing thresholds makes seals more "cautious" (seek food earlier)
- Decreasing thresholds allows seals to push closer to starvation
- The gap between critical and starvation determines the "danger zone" duration

### Tidal Thresholds

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `high_tide_threshold` | 0.70 | ratio | Tide level that floods caves (forces seals into water) |
| `low_tide_threshold` | 0.30 | ratio | Tide level that exposes cave beaches (allows haul-out) |

**Tuning tips:**
- Wider gap (e.g., 0.20-0.80) = more time available for both hauling out and foraging
- Narrower gap (e.g., 0.35-0.65) = tighter activity windows
- For Mediterranean simulations (negligible tides), set both to 0.5

### Storm Thresholds

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `storm_threshold` | 2.5 | m SWH | Wave height that triggers shelter-seeking |
| `max_landing_swell` | 4.0 | m SWH | Wave height that prevents hauling out |

**Tuning tips:**
- Lower thresholds = more cautious seals (seek shelter earlier)
- Higher thresholds = seals tolerate rougher conditions
- The gap affects how long seals remain in "storm mode"

### Digestion

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `digestion_rate` | 1.0 | kg/h | Rate of stomach emptying during rest |
| `energy_per_kg_food` | 3500.0 | kJ/kg | Energy gained per kg of digested food |

**Tuning tips:**
- Higher `digestion_rate` = faster recovery, shorter rest periods needed
- `energy_per_kg_food` affects the energy balance equation directly
- Daily maintenance requires ~3kg food → 10,500 kJ vs ~12,000 kJ daily burn (at 500 kJ/h RMR)

## Pre-configured Environments

### Madeira (Default)

Oligotrophic Atlantic environment with strong tidal forcing:

```python
MADEIRA_CONFIG = SealConfig(
    rmr=500.0,        # Hypometabolism adaptation
    hsi_floor=0.5,    # Higher floor for low-chlorophyll waters
)
```

### Custom: Productive Environment (e.g., Cabo Blanco)

For nutrient-rich waters with higher prey availability:

```python
CABO_BLANCO_CONFIG = SealConfig(
    rmr=700.0,                    # Higher metabolic rate (no hypometabolism needed)
    hsi_floor=0.3,                # Lower floor (more food available)
    shallow_foraging_rate=4.0,    # Higher base foraging rate
    hsi_chl_threshold=1.0,        # Higher chlorophyll baseline
)
```

### Custom: Mediterranean (Negligible Tides)

For Mediterranean populations where tides don't drive behavior:

```python
MEDITERRANEAN_CONFIG = SealConfig(
    high_tide_threshold=0.5,      # Effectively disables tidal forcing
    low_tide_threshold=0.5,       # Seals can haul out anytime
    # Day/night behavior would need separate implementation
)
```

## Sensitivity Analysis

Key parameters to vary for sensitivity analysis:

| Parameter | Suggested Range | Impact |
|-----------|-----------------|--------|
| `rmr` | 400-900 kJ/h | Survival rates, population dynamics |
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
    agent_id=1,
    initial_position=(32.5, -16.5),
    config=my_config
)
```

### For Batch Experiments

```python
# Parameter sweep example
rmr_values = [400, 500, 600, 700, 800]
results = []

for rmr in rmr_values:
    config = SealConfig(rmr=rmr)
    # Run simulation with this config
    result = run_simulation(config=config, duration_days=60)
    results.append({"rmr": rmr, "survival_rate": result.survival_rate})
```

## Parameter Validation Status

Parameters are categorized by validation status:

- **VALIDATED**: Directly supported by monk seal research literature
- **REASONABLE**: Biologically plausible based on observed behavior
- **MODEL PARAMETER**: Derived from equations or model-specific (requires sensitivity analysis)

See [Seal Agent Documentation](seal_agent_documentation.md) for scientific validation and literature sources for each parameter.
