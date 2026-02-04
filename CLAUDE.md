# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent-based model simulating Mediterranean Monk Seal (*Monachus monachus*) population dynamics in the Madeira Archipelago. Uses real oceanographic data from Copernicus Marine Service with physiologically-validated seal agents.

## Commands

```bash
# Install dependencies
uv sync --all-groups

# Run tests (with coverage)
uv run pytest
uv run pytest tests/test_seal.py -v          # specific file
uv run pytest tests/test_seal.py::test_name  # specific test

# Lint and type check
uv run ruff check src/ tests/
uv run ruff check src/ tests/ --fix          # auto-fix
uv run pyrefly check

# Download environmental data (requires CMEMS_USERNAME/CMEMS_PASSWORD env vars)
uv run python -m src.data_ingestion.download_data --config madeira

# Run simulation
uv run python -m src.simulation.run_real_long --duration_days 60 --output_file data/results.csv

# Generate animations
uv run python -m src.visualization.seal_animator --seal-csv <csv> --physics-file <nc>
uv run python -m src.visualization.weather_visualizer --physics <nc> --waves <nc> --bgc <nc> --tidal <nc>
```

## Architecture

### Core Components

- **`src/simulation/agents/seal.py`**: `SealAgent` class implementing a 6-state Finite State Machine (FORAGING, RESTING, SLEEPING, HAULING_OUT, TRANSITING, RECOVERY). States transition based on energy, hunger, tides, storms, and location.

- **`src/simulation/agents/config.py`**: `SealConfig` dataclass with 40+ biologically-validated parameters. All parameters have scientific citations or validation status markers.

- **`src/simulation/agents/movement.py`**: Correlated random walk algorithm for realistic movement patterns.

- **`src/simulation/environment/environment.py`**: Xarray-based environmental data handler with data buffering strategy (pre-fetches 2D arrays per timestep to avoid repeated xarray indexing).

- **`src/simulation/simulation.py`**: Main simulation loop using `ProcessPoolExecutor` for multiprocessing. Workers receive buffered environment data (not Environment objects) to avoid pickling issues.

### Data Flow

1. Environmental data (NetCDF) loaded via xarray with lazy evaluation
2. Each timestep: environment buffers extracted as numpy arrays
3. Agents receive buffers via `update_with_buffers(env_buffers: dict)`
4. Multiprocessing workers return modified agents

### Key Patterns

- **Configuration-as-Data**: Use `SealConfig` for all tunable parameters
- **FSM-driven behavior**: Agent states control all behavior decisions
- **Buffer-based parallelism**: Environment buffers (not objects) passed to workers
- **Domain terminology**: Code uses marine biology terms (e.g., hauling out, foraging, RMR)

## Code Style

- Python 3.12+ with type hints throughout
- Ruff for linting (100 char line length)
- Pyrefly for type checking
- Dataclasses for configuration objects
- `SealState` enum for FSM states (not strings)
- Google-style docstrings

## Study Area

Madeira Archipelago: 32.0-33.5°N, 17.5-16.0°W. Simulations typically run 50-100 agents with 1-hour timesteps.
