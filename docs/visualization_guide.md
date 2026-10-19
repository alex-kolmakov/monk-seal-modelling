# Visualization & Animation Guide

This document describes the visualization tools available in the Monk Seal ABM for creating animated outputs and analyzing simulation results.

## Overview

The visualization module provides two main animation tools:

| Tool | Purpose | Output |
|------|---------|--------|
| **Seal Animator** | Visualize seal movements, behavioral states, and physiology | `.mp4` video |
| **Weather Visualizer** | Animate environmental conditions over time | `.mp4` video |

## Seal Behavior Animation

The default renderer is the `ColonyAnimator`: every seal of a run on one bathymetric map, with the colony's state next to it.

### Features

- **Map**: bathymetry, coastline and each seal's recent track, coloured by behavioural state
- **Colony status**: seals alive, colony means of the energy buffer, stomach fill and fat reserve (body mass above `lean_mass`), and the live count per state
- **Tide**: hourly sea level ±48 h around the current frame, with the `high_tide_m` / `low_tide_m` bands
- **Swell**: mean and maximum significant wave height where the seals are, with the `storm_threshold` and `max_landing_swell` bands
- **Body mass**: every seal's mass since the start of the run, the median, and the `lean_mass` floor

Thresholds come from `SealConfig()` defaults. The tide, swell and mass panels read the run CSV's `tide`, `swh` and `mass` columns and stay empty (with a note) when a column is missing.

`SealBehaviorAnimator` (`single` mode) follows one seal's track with its energy, stomach and depth.

### Usage

```bash
# Whole colony from a simulation CSV (colony is the default mode, so the word can be left out)
uv run python -m src.visualization.seal_animator \
  --colony-csv   data/real_long/long_sim_results.csv \
  --physics-file data/real_long/physics_20260101_20260530.nc \
  --output data/animations/colony.mp4 \
  --fps 15 --step-hours 6

# One seal's track: --seal-csv must hold a single agent's rows (no filtering is done),
# e.g. df[df.agent_id == 0].to_csv("data/real_long/seal_0.csv", index=False)
uv run python -m src.visualization.seal_animator single \
  --seal-csv     data/real_long/seal_0.csv \
  --physics-file data/real_long/physics_20260101_20260530.nc \
  --output data/animations/seal_behavior.mp4 \
  --fps 10 --track-hours 24 --step-hours 6
```

### Configuration

Customize via `SealAnimationConfig`:

```python
from src.visualization.config import SealAnimationConfig

config = SealAnimationConfig(
    output_dir=Path("data/animations"),  # default: data/real_long
    fps=10,                    # Frames per second
    dpi=100,                   # Resolution
    track_hours=24,            # Hours of track history to show
    step_hours=6,              # Render every Nth hour
    figsize=(16, 10),          # Figure size in inches
)
```

### Behavioral State Colors

| State | Color | Description |
|-------|-------|-------------|
| FORAGING | Blue | Actively hunting/eating |
| RESTING | Purple | Digesting at sea (bottling) |
| SLEEPING | Red | Resting on land |
| HAULING_OUT | Orange | Transitioning to land |
| TRANSITING | Teal | Long-distance travel |
| RECOVERY | Grey | Stopped at sea to digest when energy is critical |

DEAD has no colour: a dead seal leaves the map.

---

## Weather/Environment Animation

The `WeatherVisualizer` creates 6-panel animations showing environmental conditions:

### Panels

1. **Surface Temperature** (`thetao`)
2. **Significant Wave Height** (`VHM0`)
3. **Ocean Current Speed** (`uo`, `vo`)
4. **Chlorophyll** (`chl`) - Proxy for food availability (productivity)
5. **Sea Level Anomaly** (DUACS `adt`) - legacy input; not the model's tide, which is IBI `zos`
6. **Bathymetry**

### Usage

```bash
# Run weather animation from command line
uv run python -m src.visualization.weather_visualizer \
  --physics data/real_long/physics_20260101_20260530.nc \
  --waves   data/real_long/waves_20260101_20260530.nc \
  --bgc     data/real_long/bgc_20260101_20260530.nc \
  --tidal   <legacy DUACS file with `adt`> \
  --start-date 2026-03-01 \
  --end-date   2026-03-31
# Writes <output_dir>/weather_animation.mp4 (default output_dir: data/real_long); there is no --output flag
```

### Configuration

```python
from src.visualization.config import WeatherVisualizationConfig

config = WeatherVisualizationConfig(
    output_dir=Path("data/animations"),
    fps=5,                     # Frames per second
    dpi=100,                   # Resolution
    figsize=(16, 10),          # Figure size
)
```

---

## Dependencies

Visualization requires:
- `matplotlib` >= 3.10 (animations, plots)
- `cartopy` >= 0.22 (map projections)
- `xarray` >= 2025.12 (NetCDF handling)
- `ffmpeg` (video encoding - must be installed on system)

### Installing FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (via chocolatey)
choco install ffmpeg
```

---

## Troubleshooting

### "No module named 'cartopy'"
```bash
uv add cartopy
```

### "ffmpeg not found"
Ensure FFmpeg is installed and in your PATH. Test with:
```bash
ffmpeg -version
```

### Animation runs slowly
- Reduce `dpi` (e.g., 80 instead of 100)
- Weather: reduce the time range with `--start-date` / `--end-date`, or raise `skip_days` in `WeatherVisualizationConfig`
- Seals: raise `--step-hours` to skip frames

### Memory errors with large datasets
- Filter data to smaller geographic region
- Use shorter time ranges
- Process in chunks and concatenate videos
