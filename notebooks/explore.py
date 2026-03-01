"""
Monk Seal Simulation — Marimo notebook

As a plain script:     uv run python notebooks/explore.py
As a Marimo notebook:  uv run marimo edit notebooks/explore.py

Edit the CONFIG block inside the first cell and save (Cmd/Ctrl+S).
"""

import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell
def _config():
    import os
    import sys
    import pandas as pd
    import plotly.express as px
    import marimo as mo
    from pathlib import Path
    from datetime import datetime

    # ══════════════════════════════════════════════════════════════════════════
    # CONFIG — edit these values
    # ══════════════════════════════════════════════════════════════════════════

    DATE_FROM = "01-01-2024"   # simulation start  (DD-MM-YYYY)
    DATE_TO   = "31-12-2024"   # simulation end    (DD-MM-YYYY)

    DOWNLOAD_DATA = True    # download only missing files; needs .env credentials

    RUN_SIM = True         # set True to run the simulation (minutes to hours)
                            # set back to False to freeze results without re-running

    NUM_AGENTS = 30         # number of seal agents
    SEED       = 42         # random seed

    # Seal physiology (see src/simulation/agents/config.py for all parameters)
    RMR       = 750.0   # resting metabolic rate (kJ/h), literature range 300–800
    HSI_FLOOR = 0.5     # habitat quality floor — 0.1 permissive, 0.9 strict
    STORM_SWH = 2.5     # wave height (m) above which seals avoid landing
    LOW_TIDE  = 0.30    # normalised tide for resting transitions (0–1)
    HIGH_TIDE = 0.70    # normalised tide for sleeping transitions (0–1)

    RENDER_VIDEO     = True  # set True to render MP4 after a successful run
    VIDEO_STEP_HOURS = 6      # hours between frames (1 = slow, 12 = fastest)
    VIDEO_FPS        = 15
    VIDEO_DPI        = 100

    # ══════════════════════════════════════════════════════════════════════════

    # Add project root to sys.path
    _root = str(Path(__file__).parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)

    mo.md(f"""
    # 🦭 Monk Seal Simulation

    Edit the **CONFIG** block in this cell and save (`Cmd/Ctrl+S`) to re-run.

    | | |
    |---|---|
    | Period | `{DATE_FROM}` → `{DATE_TO}` |
    | Agents | {NUM_AGENTS} · seed {SEED} |
    | Physiology | RMR {RMR} kJ/h · HSI floor {HSI_FLOOR} · storm SWH {STORM_SWH} m |
    | Download | {"on" if DOWNLOAD_DATA else "off"} · Simulate | {"on" if RUN_SIM else "off"} · Video | {"on" if RENDER_VIDEO else "off"} |
    """)
    return (
        DATE_FROM,
        DATE_TO,
        DOWNLOAD_DATA,
        HIGH_TIDE,
        HSI_FLOOR,
        LOW_TIDE,
        NUM_AGENTS,
        Path,
        RENDER_VIDEO,
        RMR,
        RUN_SIM,
        SEED,
        STORM_SWH,
        VIDEO_DPI,
        VIDEO_FPS,
        VIDEO_STEP_HOURS,
        datetime,
        mo,
        os,
        pd,
        px,
    )


@app.cell
def _pipeline(
    DATE_FROM,
    DATE_TO,
    DOWNLOAD_DATA,
    HIGH_TIDE,
    HSI_FLOOR,
    LOW_TIDE,
    NUM_AGENTS,
    Path,
    RENDER_VIDEO,
    RMR,
    RUN_SIM,
    SEED,
    STORM_SWH,
    VIDEO_DPI,
    VIDEO_FPS,
    VIDEO_STEP_HOURS,
    datetime,
    mo,
    os,
    pd,
    px,
):
    # ── Constants ──────────────────────────────────────────────────────────────
    DATA_DIR = Path("data/real_long")
    STATE_COLORS = {
        "FORAGING":    "#2E86DE", "HAULING_OUT": "#F39C12",
        "SLEEPING":    "#E74C3C", "RESTING":     "#9B59B6",
        "TRANSITING":  "#1ABC9C", "RECOVERY":    "#FF6B6B",
        "DEAD":        "#808080",
    }

    # ── Helpers ────────────────────────────────────────────────────────────────
    def load_dotenv():
        p = Path(".env")
        if not p.exists():
            return
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    def parse_dates():
        dt_from = datetime.strptime(DATE_FROM, "%d-%m-%Y")
        dt_to   = datetime.strptime(DATE_TO,   "%d-%m-%Y")
        tag      = f"{dt_from:%Y%m%d}_{dt_to:%Y%m%d}"
        duration = (dt_to - dt_from).days
        start    = dt_from.strftime("%Y-%m-%d %H:%M")
        return dt_from, dt_to, tag, duration, start

    def missing_files(tag):
        return [f for f in [
            DATA_DIR / f"physics_{tag}.nc",
            DATA_DIR / f"currents_{tag}.nc",
            DATA_DIR / f"waves_{tag}.nc",
            DATA_DIR / f"bgc_{tag}.nc",
        ] if not f.exists()]

    def download(tag, dt_from, dt_to):
        from src.data_ingestion.copernicus_manager import RegionBounds
        from src.data_ingestion.download_data import (
            DataDownloader, DatasetSpec, DownloadConfig, TimeRange,
        )
        if not (os.environ.get("COPERNICUS_USERNAME") and os.environ.get("COPERNICUS_PASSWORD")):
            raise RuntimeError("Missing COPERNICUS_USERNAME / COPERNICUS_PASSWORD in .env")
        tr  = TimeRange(dt_from.strftime("%Y-%m-%d"), dt_to.strftime("%Y-%m-%d"))
        rgn = RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5)
        DataDownloader().download_batch(DownloadConfig(
            output_dir=DATA_DIR, region=rgn, time_range=tr,
            datasets=[
                DatasetSpec("cmems_mod_ibi_phy-temp_my_0.027deg_P1D-m",     ["thetao"],   f"physics_{tag}.nc"),
                DatasetSpec("cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m",      ["uo", "vo"], f"currents_{tag}.nc"),
                DatasetSpec("cmems_mod_ibi_wav_my_0.027deg_PT1H-i",         ["VHM0"],     f"waves_{tag}.nc"),
                DatasetSpec("cmems_mod_ibi_bgc-plankton_my_0.027deg_P1D-m", ["chl"],      f"bgc_{tag}.nc"),
            ],
        ))
        DataDownloader().download_batch(DownloadConfig(
            output_dir=DATA_DIR,
            region=RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.0, max_lat=33.5),
            time_range=tr,
            datasets=[DatasetSpec("cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.25deg_P1D",
                                  ["adt", "sla"], f"tidal_{tag}.nc")],
        ))

    def run_sim(tag, duration_days, start_time):
        from src.simulation.agents.config import SealConfig
        from src.simulation.run_real_long import run_long_simulation
        run_long_simulation(
            start_time=start_time, duration_days=duration_days,
            data_tag=tag, output_file=f"sim_{tag}_{NUM_AGENTS}seals_s{SEED}.csv",
            seed=SEED, num_agents=NUM_AGENTS,
            config=SealConfig(rmr=RMR, hsi_floor=HSI_FLOOR,
                              low_tide_threshold=LOW_TIDE, high_tide_threshold=HIGH_TIDE,
                              storm_threshold=STORM_SWH),
        )
        return DATA_DIR / f"sim_{tag}_{NUM_AGENTS}seals_s{SEED}.csv"

    def make_charts(csv_path):
        df = pd.read_csv(csv_path, parse_dates=["time"])
        df = df.drop_duplicates(subset=["time", "agent_id"], keep="last")
        df["frame"] = df["time"].dt.floor("6h").astype(str)
        df_anim = df.groupby(["frame", "agent_id"]).last().reset_index()
        emax = df_anim["energy"].max() or 1.0
        df_anim["energy_pct"] = (df_anim["energy"] / emax * 100).clip(0, 100).round(1)
        fig_map = px.scatter_mapbox(
            df_anim, lat="lat", lon="lon", color="state",
            color_discrete_map=STATE_COLORS, animation_frame="frame",
            hover_data={"agent_id": True, "energy_pct": ":.0f"},
            mapbox_style="open-street-map", zoom=9,
            center={"lat": 32.5, "lon": -16.5}, size_max=12, height=520,
            title=f"Colony Tracks  {DATE_FROM} → {DATE_TO}",
        )
        fig_map.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
        counts = (df.groupby([df["time"].dt.date.rename("date"), "state"])
                  .size().reset_index(name="count"))
        fig_states = px.area(counts, x="date", y="count", color="state",
                             color_discrete_map=STATE_COLORS,
                             title="Behavioural State Distribution",
                             labels={"count": "Agent-hours"}, height=300)
        stats_path = csv_path.with_name(csv_path.stem + "_stats.csv")
        stats_df = pd.read_csv(stats_path, parse_dates=["date"]) if stats_path.exists() else None
        return fig_map, fig_states, stats_df

    # ── Pipeline ───────────────────────────────────────────────────────────────
    load_dotenv()
    dt_from, dt_to, tag, duration_days, start_time = parse_dates()

    if DOWNLOAD_DATA and missing_files(tag):
        with mo.status.spinner(title=f"Downloading {DATE_FROM} → {DATE_TO}…"):
            download(tag, dt_from, dt_to)

    if missing_files(tag):
        mo.stop(True, mo.callout(mo.md(
            f"**{len(missing_files(tag))} required file(s) missing.**  \n"
            "Set `DOWNLOAD_DATA = True` and ensure `.env` has Copernicus credentials."
        ), kind="warn"))

    if not RUN_SIM:
        mo.stop(True, mo.callout(
            mo.md("Set `RUN_SIM = True` in cell 1 and save to run the simulation."),
            kind="info",
        ))

    with mo.status.spinner(title=f"Simulating {NUM_AGENTS} seals × {duration_days} days…"):
        csv_path = run_sim(tag, duration_days, start_time)

    fig_map, fig_states, stats_df = make_charts(csv_path)
    _parts = [
        mo.callout(mo.md(f"✓ Results saved to `{csv_path.name}`"), kind="success"),
        mo.ui.plotly(fig_map),
    ]
    if stats_df is not None:
        _parts.append(mo.hstack([
            mo.ui.plotly(px.line(stats_df, x="date", y="total_agents", title="Seals Alive")),
            mo.ui.plotly(px.line(stats_df, x="date", y="avg_energy",   title="Mean Energy (kJ)")),
        ]))
    _parts.append(mo.ui.plotly(fig_states))

    if RENDER_VIDEO:
        from src.visualization.config import SealAnimationConfig
        from src.visualization.seal_animator import ColonyAnimator
        with mo.status.spinner(title="Rendering video…"):
            _mp4 = csv_path.with_suffix(".mp4")
            ColonyAnimator(SealAnimationConfig(
                step_hours=VIDEO_STEP_HOURS, fps=VIDEO_FPS, dpi=VIDEO_DPI,
            )).create_animation(
                colony_csv=csv_path,
                physics_file=DATA_DIR / f"physics_{tag}.nc",
                output_file=_mp4,
            )
        _parts.append(mo.callout(mo.md(f"✓ Video saved to `{_mp4}`"), kind="success"))

    mo.vstack(_parts)
    return


if __name__ == "__main__":
    app.run()
