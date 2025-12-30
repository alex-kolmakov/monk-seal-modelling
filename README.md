# Madeira Monk Seal ABM

An Agent-Based Model (ABM) simulating the population dynamics of the Mediterranean Monk Seal (*Monachus monachus*) in the Madeira archipelago. The model integrates real-world oceanographic data (Copernicus Marine Service) to drive agent behavior, physiology, and survival.

## Features
*   **Data-Driven Environment**: Uses real Physics (Currents, Temp), Waves, and Biogeochemistry (Chlorophyll) data from Copernicus.
*   **Physiological Agents**: Simulates energy balance, stomach load, digestion, and starvation.
*   **Life History**: Includes reproduction, pup development stages, and storm-induced mortality.
*   **Interactive Dashboard**: Visualize population tracks and telemetry in a web-based dashboard.

## Prerequisites
*   **Python 3.12+**
*   **uv** (Fast Python package manager)

## Installation
1.  Clone the repository.
2.  Sync dependencies:
    ```bash
    uv sync
    ```

## Data Setup
The simulation requires Copernicus Marine data (NetCDF).
1.  **Download Data**:
    Run the ingestion script to fetch 2023-2024 data (Physics, Waves, BGC):
    ```bash
    uv run python -m src.data_ingestion.download_data
    ```
    *Note: Requires Copernicus Marine credentials configured in environment or `.netrc`.*

2.  **Verify Data**:
    Ensure `data/real_long/` contains:
    *   `physics_2022_2023.nc`
    *   `waves_2022_2023.nc`
    *   `bgc_2022_2023.nc`

## Running the Simulation
Run a long-term simulation (e.g., 2 years) using the real data:

```bash
uv run python -m src.simulation.run_real_long \
  --duration_days 730 \
  --output_file data/real_long/my_simulation_results.csv
```

*   **Runtime**: ~5 minutes for 2 years (50 agents).
*   **Output**: Generates a CSV file with full agent telemetry and a `_stats.csv` with daily summaries.

## Visualization & Analysis
### 1. Run the Dashboard
Visualize the results in an interactive map:

```bash
uv run python -m src.visualization.app data/real_long/my_simulation_results.csv
```
Open your browser at `http://127.0.0.1:8050`.

### 2. Static Analysis
Generate report plots (Population Dynamics, Energy Trends):

```bash
uv run python -m src.analysis.analyze_long_run \
  --results_file data/real_long/my_simulation_results_stats.csv
```
Plots will be saved to `data/real_long/analysis_plots/`.

## Documentation
*   [Seal Agent Architecture](docs/seal_agent_documentation.md): Details on biological parameters and state machine.
*   [Copernicus Data Discovery](docs/copernicus_data_discovery.md): Notes on dataset selection.