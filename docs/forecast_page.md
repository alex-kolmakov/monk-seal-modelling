# Seal of Approval: cave visit forecast

A one-page forecast for the monk seal programme on the Desertas (Madeira). It reads the
Copernicus Marine IBI forecast for the two breeding caves, marks the hours when a cave can be
visited, and runs the seal model on the same forecast to show how a colony of digital seals
copes with the coming days. It was built for the Copernicus Marine Hackathon 2026.

Screen recordings (no sound): [calm week, green visit windows](media/forecast-green-cave-windows.mp4) and [storm week replay, red blocks = closed](media/forecast-red-storm-replay.mp4).

## Why

The programme team visits the caves for camera maintenance and colony risk assessment. No
cave-specific forecast existed, so the conditions for a safe visit were judged by hand. The page
gives the team hourly visit windows up to 8 days ahead.

## What it uses from Copernicus

| Dataset | Variables | Use |
|---|---|---|
| `cmems_mod_ibi_wav_anfc_0.027deg_PT1H-i` | `VHM0`, `VMDR`, `VHM0_SW1`, `VMDR_SW1` | wave height and direction, swell height and direction (hourly) |
| `cmems_mod_ibi_phy_anfc_0.027deg-2D_PT1H-m` | `zos` | sea surface height, the tide (hourly) |

The live seal run (`prototype/simulate_forecast.py`) also downloads daily `thetao`, `uo`, `vo` and
`chl` (`cmems_mod_ibi_phy_anfc_0.027deg-3D_P1D-m`, `cmems_mod_ibi_bgc_anfc_0.027deg-3D_P1D-m`).
Everything is fetched with the `copernicusmarine` toolbox for the box 32.2-33.5°N, 17.5-16.03°W,
from today to 11 days ahead. The sea floor is EMODnet bathymetry, not Copernicus.

## How a visit window is decided

A cave is open in an hour when all of these hold (defaults in `prototype/index.html`, editable on the page):

- waves below 1.0 m (from the programme coordinator, 22 Oct 2026);
- tide below -0.6 m against the mean level (assumed);
- swell not from the cave's bad side (Tabaqueiro: 250-335°; Bufador: 11.25-78.75°; the second from the
  coordinator's message of 26 Oct 2026, the sector edges are ours), unless waves are under 0.5 m;
- the window is at least 1 h long (assumed).

Seals are forced out of the caves at waves of about 2.25 m (the coordinator said 2 to 2.5 m).

## Which wave tile a cave reads

The wave grid is about 2.6 × 3.1 km, so one tile is bigger than a cave. Each cave reads the closest
tile that is fully sea, in the direction away from the island, past the shelf. EMODnet picks the
tile (the shelf is about 10-30 m deep there; the 3 km Copernicus floor has 150-220 m). Cave
positions are not in this repository: set `CAVE_TABAQUEIRO` and `CAVE_BUFADOR` (`lat,lon`) in `.env` (see
`.env.example`). They are only used to pick each cave's wave tile and to draw the page, and end up in the generated,
uncommitted `prototype/forecast.js`.

## Run it

```bash
cp .env.example .env                          # fill in the Copernicus login and the two cave positions
uv run python prototype/fetch_forecast.py     # waves and tide -> data/forecast/*.nc
uv run python prototype/build_forecast.py     # -> prototype/forecast.js
uv run python prototype/serve.py              # http://localhost:8765, runs the seal model on demand
```

`data/real_long/bathymetry_emodnet.nc` must exist (`uv run python -m src.data_ingestion.download_bathymetry`).

## Field test

The forecast issued on 22 October said Bufador would be closed on Mon 26 Oct (waves 1.1-1.3 m from the NE) and open
on Tue 27 Oct (0.9 m from the N). The programme team's footage showed it closed, then open. At Tabaqueiro
there was no distinctive closed day followed by an open one, so it could not be checked.

## Limits

- The 3 km wave grid cannot show swell funnelling into a cave mouth, so a green window is optimistic.
- Thresholds marked "assumed" are placeholders; those marked "call" are from the coordinator and
  have not been validated beyond the one field test above.
- The seals on the page are the model's, not tracked animals. Swim speed (10 km/h), the foraging
  range and the digestion rate are tuned, see [model_parameters.md](model_parameters.md).
