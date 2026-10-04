# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent-based model of individual Mediterranean Monk Seal (*Monachus monachus*) behaviour and energetics in the Madeira Archipelago, driven by real oceanographic data from Copernicus Marine Service. No births yet, so it is not a population-dynamics model.

## Commands

```bash
# Install dependencies
uv sync --all-groups

# Run tests (with coverage)
uv run pytest
uv run pytest tests/unit/test_seal_fsm.py -v             # specific file
uv run pytest tests/unit/test_seal_fsm.py::test_name     # specific test

# Lint and type check
uv run ruff check src/ tests/
uv run ruff check src/ tests/ --fix          # auto-fix
uv run pyrefly check

# Download environmental data (requires COPERNICUS_USERNAME/COPERNICUS_PASSWORD env vars)
uv run python -m src.data_ingestion.download_data --config madeira  # fixed 2022-2023 example, writes *_2022_2023.nc; the notebook downloads by date range

# Run simulation (dates DD-MM-YYYY; needs ssh_{tag}.nc unless --synthetic-tide)
uv run python -m src.simulation.run_real_long --from 01-01-2026 --to 30-05-2026 --agents 30 --seed 42 --out results.csv

# Generate animations
uv run python -m src.visualization.seal_animator colony --colony-csv <csv> --physics-file <nc>
uv run python -m src.visualization.seal_animator single --seal-csv <csv> --physics-file <nc>
uv run python -m src.visualization.weather_visualizer --physics <nc> --waves <nc> --bgc <nc> --tidal <nc>  # --tidal is still a legacy DUACS `adt` file
```

## Architecture

### Core Components

- **`src/simulation/agents/seal.py`**: `SealAgent` class implementing a Finite State Machine (FORAGING, RESTING, SLEEPING, HAULING_OUT, TRANSITING, RECOVERY, plus terminal DEAD). States transition based on energy, hunger, tides, storms, and location.

- **`src/simulation/agents/config.py`**: `SealConfig` dataclass with all tunable parameters. Sources, or a "model assumption" label, are in `docs/seal_agent_documentation.md` and `docs/model_parameters.md`; `tests/unit/test_config_fields.py` checks every field affects behaviour.

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

Madeira Archipelago download box: 32.2-33.5°N, 17.5-16.0°W. 1-hour timesteps. The real colony is ~27 seals (Pires et al. 2023).
