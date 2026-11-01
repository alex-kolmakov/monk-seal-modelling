<p align="center">
  <img src="docs/media/poster.png" alt="Seal of Approval, Copernicus Marine Hackathon 2026" width="520">
</p>

<h1 align="center">🦭 Seal of Approval</h1>

<p align="center">
  <strong>A cave-visit forecast for the Madeira monk seal (<em>Monachus monachus</em>), built on Copernicus Marine data, and the agent-based model behind it</strong>
</p>

<p align="center">
  <a href="https://github.com/alex-kolmakov/seal-of-approval/actions/workflows/lint_typecheck_test.yml">
    <img src="https://github.com/alex-kolmakov/seal-of-approval/actions/workflows/lint_typecheck_test.yml/badge.svg" alt="CI Status">
  </a>
  <a href="https://marine.copernicus.eu/">
    <img src="https://img.shields.io/badge/data-Copernicus%20Marine-00629B.svg" alt="Copernicus Marine">
  </a>
</p>

Fewer than 40 Mediterranean monk seals live around Madeira and depend on two caves on the Desertas. The programme team that looks after them has had to plan cave visits (camera maintenance, colony risk assessment) without a forecast. Seal of Approval turns the Copernicus Marine IBI wave and sea-level forecast into **hourly visit windows for each cave, up to 8 days ahead**, and runs a colony of digital seals on the same forecast to show how it copes with a storm. Built for the Copernicus Marine Hackathon 2026.

## The page

| A calm week: green = the cave can be visited | A storm week, replayed: red = closed, seals under strain |
|---|---|
| <img src="docs/media/ui-calm-week.png" alt="Forecast page, calm week with green visit windows"> | <img src="docs/media/ui-storm-replay.png" alt="Forecast page, storm-week replay with red closed blocks"> |

Silent screen recordings: [calm week](docs/media/forecast-green-cave-windows.mp4) · [storm replay](docs/media/forecast-red-storm-replay.mp4).

A cave is open in an hour when waves are below 1 m, the tide is low, and swell does not come from the cave's bad side. Each cave reads the closest all-sea wave tile, picked with EMODnet bathymetry. Details, thresholds and limits: [docs/forecast_page.md](docs/forecast_page.md).

```bash
git clone https://github.com/alex-kolmakov/seal-of-approval.git && cd seal-of-approval
uv sync
cp .env.example .env     # Copernicus login (free) and the two cave positions, kept out of the repo
uv run python -m src.data_ingestion.download_bathymetry
uv run python prototype/fetch_forecast.py && uv run python prototype/build_forecast.py
uv run python prototype/serve.py   # open http://localhost:8765
```

Needs Python 3.12+, [uv](https://github.com/astral-sh/uv) and, for animations, FFmpeg.

## The model

The page runs on an agent-based model of individual seals: energy balance, stomach load, digestion, body mass, hauling out with the real hourly tide, day trips to feeding grounds, and storm effects. No births yet, so it is not a population model.

```bash
# 30 seals, 1 Jan to 30 May 2026 (data files must exist in data/real_long/)
uv run python -m src.data_ingestion.download_data --from 01-01-2026 --to 30-05-2026
uv run python -m src.simulation.run_real_long --from 01-01-2026 --to 30-05-2026 --agents 30 --seed 42

# colony animation
uv run python -m src.visualization.seal_animator --colony-csv data/real_long/long_sim_results.csv \
  --physics-file data/real_long/physics_20260101_20260530.nc
```

An interactive notebook is also available: `uv run marimo edit notebooks/explore.py`.

## Docs

| Document | Description |
|---|---|
| [Forecast page](docs/forecast_page.md) | Data, visit rules, how to run, limits |
| [Seal agent](docs/seal_agent_documentation.md) | Biology, state machine, sources |
| [Model parameters](docs/model_parameters.md) | Every setting, what it does, how it was calibrated |
| [Data retrieval](docs/copernicus_data_discovery.md) | Copernicus datasets and downloads |
| [Visualization](docs/visualization_guide.md) | Animation tools |

## Development

```bash
uv run pytest
uv run ruff check . && uv run pyrefly check
```

CI runs ruff, pyrefly and pytest on every push.

## Feedback welcome

Many behaviour thresholds are placeholders (tide height at which a cave floods, swell that washes seals off, energy budget). If you work with monk seals and can check them, please [open an issue](https://github.com/alex-kolmakov/seal-of-approval/issues). The settings and their status are in [docs/model_parameters.md](docs/model_parameters.md).

## Credits

Data: [Copernicus Marine Service](https://marine.copernicus.eu/) (IBI forecast), [EMODnet Bathymetry](https://emodnet.ec.europa.eu/en/bathymetry). Field knowledge and thresholds: the IFCN Madeira monk seal programme (VECLAM team). Poster photo: Marinko Babić, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0), via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Monachus_monachus_DSC_0274.jpg); the poster is shared under the same licence.

Supports priorities 1 (protecting and restoring ocean health) and 3 (coastal and island communities, outermost regions) of the [European Ocean Pact](https://oceans-and-fisheries.ec.europa.eu/european-ocean-pact_en).
