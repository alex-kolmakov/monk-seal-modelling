import argparse
import logging
import os
import random
from datetime import datetime, timedelta

import numpy as np

from src.simulation.simulation import Simulation

logging.basicConfig(level=logging.INFO)


def run_long_simulation(
    start_time: str,
    duration_days: int,
    data_tag: str,
    output_file: str = "long_sim_results.csv",
    seed: int | None = None,
    num_agents: int = 1,
    num_workers: int | None = None,
    config=None,
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
    """
    print(f"--- Monk Seal Simulation  start={start_time}  days={duration_days}  agents={num_agents} ---")

    if seed is not None:
        print(f"Random seed: {seed}")
        random.seed(seed)
        np.random.seed(seed)

    data_dir   = "data/real_long"
    output_csv = os.path.join(data_dir, output_file)

    nc_files: list[str] = [
        os.path.join(data_dir, f"physics_{data_tag}.nc"),   # thetao + depth
        os.path.join(data_dir, f"currents_{data_tag}.nc"),  # uo, vo
        os.path.join(data_dir, f"waves_{data_tag}.nc"),     # VHM0
        os.path.join(data_dir, f"bgc_{data_tag}.nc"),       # chl
    ]

    tidal_file = os.path.join(data_dir, f"tidal_{data_tag}.nc")
    if os.path.exists(tidal_file):
        nc_files.append(tidal_file)
        print(f"Tidal data: {tidal_file}")
    else:
        print("Tidal data: not found — sine-wave fallback will be used")

    missing = [f for f in nc_files if not os.path.exists(f)]
    if missing:
        print(f"Error: Missing data files: {missing}")
        return

    sim = Simulation(
        start_time=start_time,
        duration_days=duration_days,
        time_step_hours=1,
        output_file=output_csv,
    )

    print("Loading Environment...")
    sim.load_environment(nc_files)

    # Desertas Islands: ~32.5N, 16.5W
    sim.create_agents(num_agents=num_agents, start_lat=32.5, start_lon=-16.5, config=config)

    workers = num_workers or os.cpu_count()
    print(f"Starting Simulation Loop with {workers} workers...")
    sim.run(max_workers=workers)

    sim.save_results()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from",    dest="date_from", required=True,
                        help="Start date DD-MM-YYYY")
    parser.add_argument("--to",      dest="date_to",   required=True,
                        help="End date DD-MM-YYYY")
    parser.add_argument("--out",     type=str, default="long_sim_results.csv")
    parser.add_argument("--seed",    type=int, default=None)
    parser.add_argument("--agents",  type=int, default=1)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()

    dt_from = datetime.strptime(args.date_from, "%d-%m-%Y")
    dt_to   = datetime.strptime(args.date_to,   "%d-%m-%Y")
    tag     = f"{dt_from:%Y%m%d}_{dt_to:%Y%m%d}"
    days    = (dt_to - dt_from).days

    run_long_simulation(
        start_time=dt_from.strftime("%Y-%m-%d %H:%M"),
        duration_days=days,
        data_tag=tag,
        output_file=args.out,
        seed=args.seed,
        num_agents=args.agents,
        num_workers=args.workers,
    )
