<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/5/51/Monachus_monachus_DSC_0274.jpg" alt="Mediterranean Monk Seal" width="600">
</p>

<h1 align="center">🦭 Madeira Monk Seal ABM</h1>

<p align="center">
  <strong>An Agent-Based Model simulating the population dynamics of the Mediterranean Monk Seal (<em>Monachus monachus</em>) in the Madeira Archipelago</strong>
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
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
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

- 🌊 **Data-Driven Environment**: Real oceanographic data from [Copernicus Marine Service](https://marine.copernicus.eu/) (currents, temperature, waves, chlorophyll)
- 🧬 **Physiological Agents**: Energy balance, stomach load, digestion, and starvation dynamics
- 🌙 **Tide-Driven Behavior**: Realistic activity patterns based on Madeira population research
- 🎬 **Animation Export**: Generate MP4 videos of seal movements and environmental conditions
- ⚡ **Fast Simulation**: Multiprocessing support for large population runs

---

## 🎬 Examples

<table>
  <tr>
    <td width="50%" align="center">
      <strong>🦭 Seal Behavior Animation</strong><br><br>
      <video src="https://github.com/user-attachments/assets/1b9c0662-f8e9-42ad-9829-58c74959f3b2" controls width="100%"></video>
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
# Clone the repository
git clone https://github.com/alex-kolmakov/monk-seal-modelling.git
cd monk-seal-modelling

# Install dependencies
uv sync

# Install with dev/test dependencies
uv sync --all-groups
```

### Download Environmental Data

> **Note**: Requires [Copernicus Marine](https://marine.copernicus.eu/) account (free registration)

```bash
# Set credentials
export CMEMS_USERNAME="your-username"
export CMEMS_PASSWORD="your-password"

# Download Madeira region data (2023-2024)
uv run python -m src.data_ingestion.download_data --config madeira

# Download tidal data
uv run python -m src.data_ingestion.download_data --config tidal
```

### Run Simulation

```bash
# Run 60-day simulation with 50 agents
uv run python -m src.simulation.run_real_long \
  --duration_days 60 \
  --output_file data/real_long/simulation_results.csv

# Output: simulation_results.csv + simulation_results_stats.csv
```

### Visualize Results

```bash
# Generate seal behavior animation
uv run python -m src.visualization.seal_animator \
  --seal-csv data/real_long/simulation_results.csv \
  --physics-file data/real_long/cmems_mod_ibi_phy_my_*.nc

# Generate weather/environment animation
uv run python -m src.visualization.weather_visualizer \
  --physics data/real_long/cmems_mod_ibi_phy_my_*.nc \
  --waves data/real_long/cmems_mod_ibi_wav_my_*.nc \
  --bgc data/real_long/cmems_mod_ibi_bgc_my_*.nc \
  --tidal data/real_long/tidal_2023_2024.nc
```

---

## 📁 Project Structure

```
monk-seal-modelling/
├── 📂 src/
│   ├── 📂 simulation/           # Core simulation engine
│   │   ├── 📂 agents/           # Seal agent logic & movement
│   │   │   ├── seal.py          # SealAgent class with FSM
│   │   │   └── movement.py      # Correlated random walk
│   │   ├── 📂 environment/      # Environmental data handling
│   │   │   ├── environment.py   # Xarray data loading & buffering
│   │   │   └── utils.py         # Fast spatial queries
│   │   └── simulation.py        # Main simulation loop
│   │
│   ├── 📂 data_ingestion/       # Copernicus data retrieval
│   │   ├── copernicus_manager.py
│   │   ├── download_data.py     # CLI for data download
│   │   └── discover_datasets.py
│   │
│   ├── 📂 visualization/        # Plotting & animation
│   │   ├── seal_animator.py     # Seal behavior animations
│   │   └── weather_visualizer.py # Environmental animations
│   │
│   └── 📂 analysis/             # Statistical analysis
│       ├── analyze_long_run.py  # Population dynamics plots
│       └── analyze_tidal_data.py
│
├── 📂 data/                     # Data directory (gitignored)
│   └── 📂 real_long/            # Downloaded NetCDF files
│
├── 📂 docs/                     # Documentation
│   ├── seal_agent_documentation.md
│   ├── copernicus_data_discovery.md
│   └── visualization_guide.md
│
├── 📂 tests/                    # Test suite
├── 📄 pyproject.toml            # Project configuration
└── 📄 README.md
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Seal Agent Architecture](docs/seal_agent_documentation.md) | Biological parameters, state machine, and scientific validation |
| [Data Retrieval Guide](docs/copernicus_data_discovery.md) | Copernicus datasets, download process, tidal integration |
| [Visualization Guide](docs/visualization_guide.md) | Animation tools and troubleshooting |

---

## 🧪 Development

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/test_seal.py -v

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

- **Tidal Activity**: [Pires et al. 2007](https://www.researchgate.net/publication/254846183) - Tide-driven behavior patterns
- **Foraging Depths**: [Hale et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Hale.pdf) - 95% of dives at 0-50m
- **Storm Mortality**: [Gazo et al. 2000](https://www.researchgate.net/publication/227717823) - Pup survival and wave impacts
- **Habitat**: [Karamanlidis et al. 2004](https://www.cambridge.org/core/journals/oryx/article/availability-of-resting-and-pupping-habitat-for-the-critically-endangered-mediterranean-monk-seal-monachus-monachus-in-the-archipelago-of-madeira/26FDF046B0B81D1A3DC707E722174931) - Cave suitability

See [Seal Agent Documentation](docs/seal_agent_documentation.md) for complete parameter validation.

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

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Copernicus Marine Service** for oceanographic data
- **Lobo Marinho Madeira** for monk seal conservation research
- **University of Madeira** for population studies

---

<p align="center">
  Made with ❤️ for monk seal conservation
</p>
