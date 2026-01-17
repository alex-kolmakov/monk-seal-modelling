# Visualization & Animation Guide

This document describes the visualization tools available in the Monk Seal ABM for creating animated outputs and analyzing simulation results.

## Overview

The visualization module provides two main animation tools:

| Tool | Purpose | Output |
|------|---------|--------|
| **Seal Animator** | Visualize seal movements, behavioral states, and physiology | `.mp4` video |
| **Weather Visualizer** | Animate environmental conditions over time | `.mp4` video |

## Seal Behavior Animation

The `SealBehaviorAnimator` creates animated visualizations of seal tracking data overlaid on bathymetric maps.

### Features

- **Map Layer**: Bathymetry (sea depth) with land/coastline features
- **Seal Track**: Historical movement path with color-coded behavioral states
- **Metrics Panel**: Real-time display of energy, stomach load, depth, and tide
- **State Legend**: Color-coded behavioral states (FORAGING, RESTING, SLEEPING, etc.)

### Usage

```bash
# Run seal animation from command line
uv run python -m src.visualization.seal_animator \
  --seal-csv data/real_long/simulation_results.csv \
  --physics-file data/real_long/cmems_mod_ibi_phy_my_*.nc \
  --output data/animations/seal_behavior.mp4 \
  --fps 10
```

### Configuration

Customize via `SealAnimationConfig`:

```python
from src.visualization.config import SealAnimationConfig

config = SealAnimationConfig(
    output_dir=Path("data/animations"),
    fps=10,                    # Frames per second
    dpi=150,                   # Resolution
    track_length=48,           # Hours of track history to show
    figsize=(14, 8),           # Figure size in inches
)
```

### Behavioral State Colors

| State | Color | Description |
|-------|-------|-------------|
| FORAGING | Blue | Actively hunting/eating |
| RESTING | Green | Digesting at sea (bottling) |
| SLEEPING | Purple | Resting on land |
| HAULING_OUT | Orange | Transitioning to land |
| TRANSITING | Yellow | Long-distance travel |
| DEAD | Red | Agent deceased |

---

## Weather/Environment Animation

The `WeatherVisualizer` creates 5-panel animations showing environmental conditions:

### Panels

1. **Sea Temperature** (`thetao`) - Heat map of surface water temperature
2. **Currents** (`uo`, `vo`) - Vector arrows showing current direction and strength
3. **Wave Height** (`VHM0`) - Significant wave height (storm detection)
4. **Chlorophyll** (`chl`) - Proxy for food availability (productivity)
5. **Tide Level** - Current tidal state indicator

### Usage

```bash
# Run weather animation from command line
uv run python -m src.visualization.weather_visualizer \
  --physics data/real_long/cmems_mod_ibi_phy_my_*.nc \
  --waves data/real_long/cmems_mod_ibi_wav_my_*.nc \
  --bgc data/real_long/cmems_mod_ibi_bgc_my_*.nc \
  --tidal data/real_long/tidal_2023_2024.nc \
  --output data/animations/weather.mp4 \
  --start-date 2023-06-01 \
  --end-date 2023-06-30
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
- Reduce `dpi` in config (e.g., 100 instead of 150)
- Reduce time range with `--start-date` and `--end-date`
- Increase `step` parameter to skip frames

### Memory errors with large datasets
- Filter data to smaller geographic region
- Use shorter time ranges
- Process in chunks and concatenate videos
