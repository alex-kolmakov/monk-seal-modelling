import argparse
import json
import logging
import os
from dataclasses import replace
from datetime import datetime

from src.simulation.agents.config import (
    DESERTAS_FEED_EXCLUDE_BOX,
    DESERTAS_HAULOUT_BOX,
    MADEIRA_CONFIG,
    SHELF_DEPTH_M,
)
from src.simulation.environment.environment import TIDE_DATUM_M
from src.simulation.simulation import Simulation

logging.basicConfig(level=logging.INFO)


def _write_run_metadata(output_csv: str, **fields) -> None:
    """Write <output>_meta.json next to the results so every run records its inputs."""
    meta_file = output_csv.replace(".csv", "_meta.json")
    with open(meta_file, "w") as f:
        json.dump(fields, f, indent=2, default=str)
    print(f"Run metadata: {meta_file}")


def run_long_simulation(
    start_time: str,
    duration_days: int,
    data_tag: str,
    output_file: str = "long_sim_results.csv",
    seed: int | None = None,
    num_agents: int = 1,
    num_workers: int | None = None,
    config=None,
    synthetic_tide: bool = False,
    overwrite: bool = False,
    allow_time_wrap: bool = False,
    bathymetry_file: str | None = None,
):
    """Run a monk seal simulation for the given date range.

    Args:
        start_time:    Simulation start, e.g. "2024-01-01 00:00"
        duration_days: Number of days to simulate.
        data_tag:      File-naming suffix, e.g. "20240101_20251231".
                       All NetCDF files are expected as physics_{tag}.nc etc.
        output_file:   CSV filename (placed in data/real_long/).
        seed:          Random seed for reproducibility.
        num_agents:    Number of seal agents.
        num_workers:   Parallel workers (default: os.cpu_count()).
        config:        SealConfig instance (None = use MADEIRA_CONFIG defaults).
        synthetic_tide: Use the synthetic sine tide instead of ssh_{tag}.nc (IBI zos).
        overwrite:     Replace an existing output CSV instead of refusing to run.
        bathymetry_file: EMODnet bathymetry NetCDF (download_bathymetry) used as the sea floor
                       instead of the depth derived from physics_{tag}.nc.
    """
    print(
        f"--- Monk Seal Simulation  start={start_time}"
        f"  days={duration_days}  agents={num_agents} ---"
    )

    data_dir   = "data/real_long"
    output_csv = os.path.join(data_dir, output_file)

    nc_files: list[str] = [
        os.path.join(data_dir, f"physics_{data_tag}.nc"),   # thetao + depth
        os.path.join(data_dir, f"currents_{data_tag}.nc"),  # uo, vo
        os.path.join(data_dir, f"waves_{data_tag}.nc"),     # VHM0
        os.path.join(data_dir, f"bgc_{data_tag}.nc"),       # chl
    ]

    # Tide: IBI hourly zos. The synthetic sine is opt-in only, never a silent fallback.
    tide_file = os.path.join(data_dir, f"ssh_{data_tag}.nc")
    if synthetic_tide:
        print("Tide: synthetic sine (--synthetic-tide)")
    else:
        nc_files.append(tide_file)
        print(f"Tide: {tide_file}")

    if bathymetry_file is not None:
        print(f"Bathymetry: {bathymetry_file}")
    missing = [f for f in nc_files + ([bathymetry_file] if bathymetry_file else [])
               if not os.path.exists(f)]
    if missing:
        raise FileNotFoundError(f"Missing data files: {missing}")

    sim = Simulation(
        start_time=start_time,
        duration_days=duration_days,
        time_step_hours=1,
        output_file=output_csv,
        synthetic_tide=synthetic_tide,
        allow_time_wrap=allow_time_wrap,
        seed=seed,
        overwrite=overwrite,
    )
    print(f"Random seed: {sim.seed}")

    print("Loading Environment...")
    sim.load_environment(nc_files, bathymetry_file=bathymetry_file)
    meta = dict(
        start_time=start_time,
        duration_days=duration_days,
        seed=sim.seed,
        num_agents=num_agents,
        num_workers=num_workers or os.cpu_count(),
        tide_source=sim.environment.tide_source,
        tide_file=sim.environment.tide_file,
        tide_datum_m=TIDE_DATUM_M,
        allow_time_wrap=allow_time_wrap,
        nc_files=nc_files,
        bathymetry_file=bathymetry_file,
    )
    _write_run_metadata(output_csv, **meta)

    # Desertas Islands: ~32.5N, 16.5W
    sim.create_agents(num_agents=num_agents, start_lat=32.5, start_lon=-16.5, config=config)

    workers = num_workers or os.cpu_count()
    print(f"Starting Simulation Loop with {workers} workers...")
    sim.run(max_workers=workers)

    sim.save_results()
    _write_run_metadata(
        output_csv, **meta, n_deaths=sim.n_deaths_total, n_out_of_bounds=sim.n_out_of_bounds
    )
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from",    dest="date_from", required=True,
                        help="Start date DD-MM-YYYY")
    parser.add_argument("--to", dest="date_to", required=True, help="End date DD-MM-YYYY")
    parser.add_argument("--out", type=str, default="long_sim_results.csv")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--agents", type=int, default=1)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--synthetic-tide",
        action="store_true",
        help="Use a 12.4 h sine tide instead of ssh_{tag}.nc (IBI zos)",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing output CSV (default: refuse)"
    )
    parser.add_argument(
        "--haulout-desertas",
        action="store_true",
        help="Seals rest, sleep and haul out only on the Desertas (config.haulout_box)",
    )
    parser.add_argument(
        "--forage-shelf",
        action="store_true",
        help="Seals forage only on the shelf, sea at most 100 m deep (config.forage_max_depth_m)",
    )
    parser.add_argument(
        "--no-forage-at-desertas",
        action="store_true",
        help=(
            "Seals do not forage inside the Desertas box: they leave to "
            "feed and come back to rest"
        ),
    )
    parser.add_argument(
        "--feeding-trips",
        action="store_true",
        help=(
            "Seals stay out feeding until full, and digest afloat at the "
            "roost (config.feeding_trips)"
        ),
    )
    parser.add_argument(
        "--feeding-range-km",
        type=float,
        default=None,
        help="Each trip feeds at a random shelf cell within this many km (config.feeding_range_km)",
    )
    parser.add_argument(
        "--active-digestion",
        type=float,
        default=0.0,
        help=(
            "Digest at this fraction of the rest rate while swimming "
            "(config.active_digestion_fraction)"
        ),
    )
    parser.add_argument(
        "--max-hours-away",
        type=float,
        default=None,
        help=(
            "A feeding seal heads for the roost after this many hours "
            "away (config.max_hours_away)"
        ),
    )
    parser.add_argument(
        "--trip-speed-kmh",
        type=float,
        default=None,
        help="Swimming pace to feeding water and back to the roost (config.trip_speed_km_h)",
    )
    parser.add_argument(
        "--home-by-hours",
        type=float,
        default=None,
        help=(
            "Be back in the roost box this many hours after leaving it, counting the swim back "
            "(config.home_by_hours)"
        ),
    )
    parser.add_argument(
        "--allow-time-wrap",
        action="store_true",
        help="Replay input data from its start past its end (default: error)",
    )
    parser.add_argument(
        "--emodnet-bathymetry",
        nargs="?",
        const="data/real_long/bathymetry_emodnet.nc",
        default=None,
        metavar="FILE",
        help=(
            "Use EMODnet bathymetry as the sea floor instead of the depth derived from the "
            "physics file (default file: data/real_long/bathymetry_emodnet.nc, made by "
            "src.data_ingestion.download_bathymetry)"
        ),
    )
    args = parser.parse_args()

    dt_from = datetime.strptime(args.date_from, "%d-%m-%Y")
    dt_to = datetime.strptime(args.date_to, "%d-%m-%Y")
    tag = f"{dt_from:%Y%m%d}_{dt_to:%Y%m%d}"
    days = (dt_to - dt_from).days

    config = replace(
        MADEIRA_CONFIG,
        haulout_box=DESERTAS_HAULOUT_BOX if args.haulout_desertas else None,
        forage_max_depth_m=SHELF_DEPTH_M if args.forage_shelf else None,
        forage_exclude_box=DESERTAS_FEED_EXCLUDE_BOX if args.no_forage_at_desertas else None,
        feeding_trips=args.feeding_trips,
        max_hours_away=args.max_hours_away,
        active_digestion_fraction=args.active_digestion,
        feeding_range_km=args.feeding_range_km,
        trip_speed_km_h=args.trip_speed_kmh,
        home_by_hours=args.home_by_hours,
    )
    run_long_simulation(
        start_time=dt_from.strftime("%Y-%m-%d %H:%M"),
        duration_days=days,
        data_tag=tag,
        output_file=args.out,
        seed=args.seed,
        num_agents=args.agents,
        num_workers=args.workers,
        synthetic_tide=args.synthetic_tide,
        overwrite=args.overwrite,
        allow_time_wrap=args.allow_time_wrap,
        config=config,
        bathymetry_file=args.emodnet_bathymetry,
    )
