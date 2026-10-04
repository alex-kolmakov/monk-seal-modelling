<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/5/51/Monachus_monachus_DSC_0274.jpg" alt="Mediterranean Monk Seal" width="600">
</p>

<h1 align="center">🦭 Madeira Monk Seal ABM</h1>

<p align="center">
  <strong>An Agent-Based Model of individual Mediterranean Monk Seal (<em>Monachus monachus</em>) behaviour and energetics in the Madeira Archipelago</strong>
</p>

<p align="center">
  <a href="https://github.com/alex-kolmakov/monk-seal-modelling/actions/workflows/lint_typecheck_test.yml">
    <img src="https://github.com/alex-kolmakov/monk-seal-modelling/actions/workflows/lint_typecheck_test.yml/badge.svg" alt="CI Status">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  </a>
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/uv-package%20manager-blueviolet.svg" alt="uv">
  </a>
  <a href="https://marine.copernicus.eu/">
    <img src="https://img.shields.io/badge/data-Copernicus%20Marine-00629B.svg" alt="Copernicus Marine">
  </a>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-project-structure">Structure</a> •
  <a href="#-documentation">Documentation</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ✨ Features

- 🌊 **Data-Driven Environment**: Real oceanographic data from [Copernicus Marine Service](https://marine.copernicus.eu/) (currents, temperature, waves, chlorophyll, hourly sea surface height)
- 🧬 **Physiological Agents**: Energy balance, stomach load, digestion, and starvation dynamics
- 🌙 **Tide-Driven Behavior**: Haul-out and cave access follow the real hourly tide (Copernicus IBI sea surface height, in metres), as observed for the Madeira population
- 🎬 **Animation Export**: Generate MP4 videos of seal movements and environmental conditions
- ⚡ **Fast Simulation**: Multiprocessing support for large population runs

---

## 🎬 Examples

<table>
  <tr>
    <td width="50%" align="center">
      <strong>🦭 Seal Behavior Animation</strong><br><br>
      <video src="https://github.com/user-attachments/assets/d2925b1e-9933-4059-a24e-f4783edc98b2" controls width="100%"></video>
    </td>
    <td width="50%" align="center">
      <strong>🌊 Weather & Environment</strong><br><br>
      <video src="https://github.com/user-attachments/assets/079d6047-7075-4f08-b64f-e0cca51b33b5" controls width="100%"></video>
    </td>
  </tr>
</table>

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Installation |
|-------------|---------|--------------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| uv | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| FFmpeg | Any | `brew install ffmpeg` (macOS) |

### Installation

```bash
git clone https://github.com/alex-kolmakov/monk-seal-modelling.git
cd monk-seal-modelling
uv sync
```

### Credentials

Create a `.env` file in the project root with your [Copernicus Marine](https://marine.copernicus.eu/) credentials (free registration):

```
COPERNICUS_USERNAME=your-username
COPERNICUS_PASSWORD=your-password
```

### Run — Interactive Notebook (recommended)

```bash
uv run marimo edit notebooks/explore.py
```

Opens a reactive notebook in your browser. Edit the **CONFIG** block at the top of the first cell:

| Variable | Description |
|---|---|
| `DATE_FROM` / `DATE_TO` | Date range in `DD-MM-YYYY` format — any period, any length |
| `DOWNLOAD_DATA` | Set `True` to fetch missing Copernicus files (uses `.env` credentials) |
| `RUN_SIM` | Set `True` to run the simulation |
| `NUM_AGENTS` | Number of seal agents (10–50 recommended) |
| `RENDER_VIDEO` | Set `True` to export an MP4 after the simulation |

Save (`Cmd/Ctrl+S`) to trigger reactive re-execution of dependent cells.

### Run — Plain Script

```bash
# Edit DATE_FROM, DATE_TO, RUN_SIM etc. directly in the file, then:
uv run python notebooks/explore.py
```

### Run — CLI

```bash
# Simulate 30 seals from 1 Jan to 30 May 2026
# Data files (incl. ssh_{tag}.nc for the tide) must already exist in data/real_long/
uv run python -m src.simulation.run_real_long \
  --from 01-01-2026 \
  --to   30-05-2026 \
  --agents 30 \
  --seed 42

# Output: data/real_long/long_sim_results.csv
#         data/real_long/long_sim_results_stats.csv
#         data/real_long/long_sim_results_meta.json   (run inputs, incl. tide source)
# Use --out to change the file name; --synthetic-tide to run without ssh_{tag}.nc
```

### Visualize Results

```bash
# Colony animation (requires a completed simulation CSV)
uv run python -m src.visualization.seal_animator colony \
  --colony-csv   data/real_long/long_sim_results.csv \
  --physics-file data/real_long/physics_20260101_20260530.nc

# Single-seal animation: `seal_animator single --seal-csv <csv> --physics-file <nc>`

# Environmental animation
uv run python -m src.visualization.weather_visualizer \
  --physics  data/real_long/physics_20260101_20260530.nc \
  --waves    data/real_long/waves_20260101_20260530.nc \
  --bgc      data/real_long/bgc_20260101_20260530.nc \
  --tidal    <legacy DUACS file with `adt`>   # not yet ported to zos
```

> **File naming**: all data files use a `YYYYMMDD_YYYYMMDD` tag derived from your chosen date range. The notebook handles this automatically.

---

## 📁 Project Structure

```
monk-seal-modelling/
├── 📂 src/
│   ├── 📂 simulation/           # Core simulation engine
│   │   ├── 📂 agents/           # Seal agent logic & movement
│   │   │   ├── seal.py          # SealAgent class with FSM
│   │   │   ├── config.py        # SealConfig (all tunable parameters)
│   │   │   └── movement.py      # Correlated random walk
│   │   ├── 📂 environment/      # Environmental data handling
│   │   │   ├── environment.py   # Xarray data loading & buffering, tide from zos
│   │   │   └── utils.py         # Fast spatial queries
│   │   ├── simulation.py        # Main simulation loop
│   │   ├── agent_worker.py      # Multiprocessing worker
│   │   └── run_real_long.py     # CLI entry point
│   │
│   ├── 📂 data_ingestion/       # Copernicus data retrieval
│   │   ├── copernicus_manager.py
│   │   ├── download_data.py     # CLI for data download
│   │   └── discover_datasets.py
│   │
│   ├── 📂 visualization/        # Plotting & animation
│   │   ├── seal_animator.py     # Seal behavior animations (single / colony)
│   │   ├── weather_visualizer.py # Environmental animations
│   │   ├── config.py            # Animation settings
│   │   └── data_loader.py
│
├── 📂 notebooks/
│   └── explore.py               # marimo notebook (recommended entry point)
│
├── 📂 data/                     # Data directory (gitignored)
│   └── 📂 real_long/            # Downloaded NetCDF files
│
├── 📂 docs/                     # Documentation
│   ├── seal_agent_documentation.md
│   ├── model_parameters.md
│   ├── copernicus_data_discovery.md
│   └── visualization_guide.md
│
├── 📂 tests/unit/               # Test suite
├── 📄 pyproject.toml            # Project configuration
└── 📄 README.md
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Seal Agent Architecture](docs/seal_agent_documentation.md) | Biological parameters, state machine, and scientific validation |
| [Model Parameters & Tuning](docs/model_parameters.md) | Configuration reference and how to adjust parameters |
| [Data Retrieval Guide](docs/copernicus_data_discovery.md) | Copernicus datasets, download process, tidal integration |
| [Visualization Guide](docs/visualization_guide.md) | Animation tools and troubleshooting |

---

## 🧪 Development

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_seal_fsm.py -v

# Run with verbose output
uv run pytest -v --tb=short
```

### Code Quality

```bash
# Lint with ruff
uv run ruff check src/ tests/

# Auto-fix linting issues
uv run ruff check src/ tests/ --fix

# Type checking with pyrefly
uv run pyrefly check
```

### CI/CD

The project uses GitHub Actions for continuous integration:

- **Linting**: `ruff check`
- **Type Checking**: `pyrefly check`  
- **Testing**: `pytest` with coverage reporting

---

## 🔬 Scientific Background

This model is based on research on the Mediterranean Monk Seal (*Monachus monachus*) population in the Madeira Archipelago. Key references:

- **Tidal Activity**: [Pires et al. 2007](https://www.researchgate.net/publication/254846183) - Activity patterns of the Mediterranean monk seal in the Archipelago of Madeira
- **Foraging Depths**: [Hale et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Hale.pdf) - Mediterranean monk seal fishery interactions in the Archipelago of Madeira
- **Pup Survival in Caves**: [Gazo et al. 2000](https://www.researchgate.net/publication/227717823) - Pup survival in the Mediterranean monk seal colony at Cabo Blanco Peninsula *(storm-driven mortality detail unverified)*
- **Population & Vital Rates**: [Pires et al. 2023](https://doi.org/10.3354/esr01260) - First demographic parameter estimates for the Madeira population (27 seals in 2021; adult survival 0.98 females, 0.90 males; pupping Oct–Dec)
- **Habitat**: [Karamanlidis et al. 2004](https://www.cambridge.org/core/journals/oryx/article/availability-of-resting-and-pupping-habitat-for-the-critically-endangered-mediterranean-monk-seal-monachus-monachus-in-the-archipelago-of-madeira/26FDF046B0B81D1A3DC707E722174931) - Availability of resting and pupping habitat for the Mediterranean monk seal in the Archipelago of Madeira

See [Seal Agent Documentation](docs/seal_agent_documentation.md) for complete parameter validation.

---

## 🔭 Seeking Guidance

This model is an independent open-science effort and I actively seek feedback from researchers and practitioners. If you work with monk seals, ocean data, or agent-based ecology, your input would be invaluable:

### Behavioural Parameter Validation

The current parameters are drawn from published literature but many are uncertain or Madeira-specific. Would love expert review on:

- **Tide thresholds** — `low_tide_m` (−0.30 m) and `high_tide_m` (+0.30 m) above mean sea level control cave access and haul-out timing. These are placeholders: at what tide height do the Desertas cave beaches flood or become accessible?
- **Energy budgets** — `rmr = 750 kJ/h` (~0.85× Kleiber for a 300kg subtropical phocid); does this match your field observations?
- **Foraging rates** — `shallow_foraging_rate = 3.0 kg/h` at depths < 50 m; are these realistic for Madeira's prey community?

### Activity Pattern Validation

Do the simulated activity budgets (time spent foraging / resting / hauling out per day) match any telemetry or observation data for the Madeira population?

### Model Extensions

- **Greece / Cabo Blanco populations** — the model uses a `SealConfig` dataclass that makes porting to new populations straightforward. Happy to collaborate on calibrating parameters for other subpopulations.
- **Pup and juvenile dynamics** — agents have an age and sex, but there are no births and no age-specific behaviour yet; adding them is a planned future direction.
- **Human disturbance** — the male risk feature is a stub; incorporating tourism pressure or fishing interaction data would strengthen demographic projections.

If any of these resonate with your work, feel free to [open an issue](https://github.com/alex-kolmakov/monk-seal-modelling/issues) or reach out directly.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest`)
5. Run linting (`uv run ruff check --fix`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

---

## 🙏 Acknowledgments

- **Copernicus Marine Service** for oceanographic data
- **IFCN Madeira** (Instituto das Florestas e Conservação da Natureza) and its monk seal programme, whose published field work this model draws on

---

<p align="center">
  Made with ❤️ for monk seal conservation
</p>
