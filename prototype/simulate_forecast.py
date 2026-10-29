"""Run the real agent-based model on the latest Copernicus forecast and export seal tracks for the page.

Steps (each reports progress through the `say` callback):
  1. download the model inputs (IBI forecast: temperature with depth levels, currents, waves, chlorophyll, hourly zos)
     into data/forecast_run/data/real_long/ under the names run_real_long expects
  2. run `python -m src.simulation.run_real_long` there (a working directory of its own, so the model code stays untouched)
  3. convert the hourly CSV into prototype/seals.json: one lat/lon/state/mass track per seal

Credentials come from COPERNICUS_USERNAME / COPERNICUS_PASSWORD (repo .env).
"""
import csv
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import copernicusmarine as cm
import xarray as xr

HERE = Path(__file__).parent
REPO = HERE.parent
RUN_DIR = REPO / "data" / "forecast_run"
INPUT_DIR = RUN_DIR / "data" / "real_long"
BOX = dict(minimum_longitude=-17.5, maximum_longitude=-16.03, minimum_latitude=32.2, maximum_latitude=33.5)
MAX_ENERGY = 100000.0  # SealConfig.max_energy (kJ)
STATES = ["FORAGING", "RESTING", "SLEEPING", "HAULING_OUT", "TRANSITING", "RECOVERY", "DEAD"]


def load_env() -> None:
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def _subset(dataset_id: str, variables: list[str], name: str, start: datetime, end: datetime, **extra) -> None:
    cm.subset(
        dataset_id=dataset_id, variables=variables, output_directory=str(INPUT_DIR), output_filename=name, overwrite=True,
        username=os.environ["COPERNICUS_USERNAME"], password=os.environ["COPERNICUS_PASSWORD"],
        start_datetime=start.strftime("%Y-%m-%dT%H:%M:%S"), end_datetime=end.strftime("%Y-%m-%dT%H:%M:%S"),
        **BOX, **extra,
    )


def download_inputs(say) -> tuple[date, date]:
    """Fetch the forecast inputs; returns (first day, last day) the model can run over."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = today + timedelta(days=11)
    say("Downloading hourly waves")
    _subset("cmems_mod_ibi_wav_anfc_0.027deg_PT1H-i", ["VHM0"], "waves_tmp.nc", today, end)
    waves = xr.open_dataset(INPUT_DIR / "waves_tmp.nc")
    last = waves.time.values[-1].astype("datetime64[D]").astype(object)  # last day with wave data (names the files)
    first = today.date()
    tag = f"{first:%Y%m%d}_{last:%Y%m%d}"
    waves.close()
    (INPUT_DIR / "waves_tmp.nc").replace(INPUT_DIR / f"waves_{tag}.nc")
    say("Downloading hourly sea surface height (tide)")
    _subset("cmems_mod_ibi_phy_anfc_0.027deg-2D_PT1H-m", ["zos"], f"ssh_{tag}.nc", today, end)
    # daily products: start a day earlier so the first model hour has data on both sides
    d0 = today - timedelta(days=1)
    say("Downloading temperature with depth levels (for bathymetry)")
    _subset("cmems_mod_ibi_phy_anfc_0.027deg-3D_P1D-m", ["thetao"], f"physics_{tag}.nc", d0, end)
    say("Downloading surface currents")
    _subset("cmems_mod_ibi_phy_anfc_0.027deg-3D_P1D-m", ["uo", "vo"], f"currents_{tag}.nc", d0, end, minimum_depth=0, maximum_depth=2)
    say("Downloading chlorophyll")
    _subset("cmems_mod_ibi_bgc_anfc_0.027deg-3D_P1D-m", ["chl"], f"bgc_{tag}.nc", d0, end, minimum_depth=0, maximum_depth=2)
    # the products have different horizons (e.g. chl a day or two shorter than waves): stop where the shortest one does.
    # The model accepts times up to one native step past a file's last value, so each file covers until last + step.
    covered = []
    for f in INPUT_DIR.glob(f"*_{tag}.nc"):
        with xr.open_dataset(f) as ds:
            t = ds.time.values
            covered.append(t[-1] + (t[-1] - t[-2]))
    last = min(covered).astype("datetime64[D]").astype(object)  # --to is exclusive: the run ends at 00:00 that day
    run_tag = f"{first:%Y%m%d}_{last:%Y%m%d}"  # run_real_long finds its inputs by the --from/--to dates
    if run_tag != tag:
        for f in INPUT_DIR.glob(f"*_{tag}.nc"):
            f.replace(f.with_name(f.name.replace(tag, run_tag)))
    return first, last


def run_model(first: date, last: date, agents: int, seed: int, say, desertas: bool = True, shelf: bool = True, leave_to_feed: bool = True, trips: bool = True) -> Path:
    out = INPUT_DIR / "seals.csv"
    for f in INPUT_DIR.glob("seals*"):
        f.unlink()
    for f in INPUT_DIR.glob("_tmp_agent_*"):
        f.unlink()
    cmd = [sys.executable, "-m", "src.simulation.run_real_long", "--from", f"{first:%d-%m-%Y}", "--to", f"{last:%d-%m-%Y}",
           "--out", "seals.csv", "--agents", str(agents), "--seed", str(seed), "--overwrite"]
    if desertas:
        cmd.append("--haulout-desertas")  # rest, sleep and haul out only on the Desertas
    if shelf:
        cmd.append("--forage-shelf")  # forage only where the sea is at most 100 m deep
    if leave_to_feed:
        cmd.append("--no-forage-at-desertas")  # no feeding at the roost: seals leave to feed and come back to rest
    if trips:
        # stay out feeding until full; digest afloat at the roost; each trip to a random shelf cell within 90 km, swum at
        # 10 km/h so a seal can circle Madeira and be back at the Desertas the same day (turns home to be back within 24 h);
        # digest at 70% of the rest rate while swimming (calibrated on EMODnet: calm January 2026 keeps the colony's mass level)
        cmd += ["--feeding-trips", "--feeding-range-km", "90", "--active-digestion", "0.7", "--trip-speed-kmh", "10",
                "--home-by-hours", "24"]
    # sea floor: EMODnet, the one the colony was calibrated on (the run's working directory is not the repo's)
    cmd += ["--emodnet-bathymetry", str(REPO / "data" / "real_long" / "bathymetry_emodnet.nc")]
    say(f"Running the seal model: {agents} seals, {(last - first).days} days")
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    proc = subprocess.run(cmd, cwd=RUN_DIR, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("model failed: " + (proc.stderr or proc.stdout)[-1500:])
    return out


def export_tracks(csv_path: Path, first: date, seed: int, path: Path | None = None) -> Path:
    tracks: dict[int, dict] = {}
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            t = tracks.setdefault(int(r["agent_id"]), dict(lat=[], lon=[], s=[], m=[], e=[], k=[]))
            t["lat"].append(round(float(r["lat"]), 4))
            t["lon"].append(round(float(r["lon"]), 4))
            t["s"].append(STATES.index(r["state"]))
            t["m"].append(round(float(r["mass"]), 1) if r.get("mass") else None)
            t["e"].append(round(float(r["energy"]) / MAX_ENERGY * 100) if r.get("energy") else None)  # % of the short-term buffer
            t["k"].append(round(float(r["stomach"]), 1) if r.get("stomach") else None)  # kg in the stomach
    hours = max(len(t["lat"]) for t in tracks.values())
    out = {"start": f"{first:%Y-%m-%d}T00", "hours": hours, "seed": seed, "states": STATES, "lean_mass": 240.0, "max_mass": 400.0, "stomach_cap": 15.0, "seals": list(tracks.values()),
           "made": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    path = path or HERE / "seals.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    return path


def refresh_page_forecast(say) -> None:
    """Re-download the forecast shown on the page and rebuild forecast.js."""
    say("Updating the forecast shown on the page")
    for script in ("fetch_forecast.py", "build_forecast.py"):
        proc = subprocess.run([sys.executable, str(HERE / script)], cwd=REPO, env=os.environ, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"{script} failed: " + (proc.stderr or proc.stdout)[-1500:])


def simulate(agents: int, seed: int, say, desertas: bool = True, shelf: bool = True, leave_to_feed: bool = True, trips: bool = True) -> None:
    load_env()
    refresh_page_forecast(say)
    first, last = download_inputs(say)
    csv_path = run_model(first, last, agents, seed, say, desertas, shelf, leave_to_feed, trips)
    say("Exporting seal tracks")
    export_tracks(csv_path, first, seed)


if __name__ == "__main__":
    simulate(int(sys.argv[1]) if len(sys.argv) > 1 else 12, int(sys.argv[2]) if len(sys.argv) > 2 else 42, print)
