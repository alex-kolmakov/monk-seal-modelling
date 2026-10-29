"""The colony in the hardest weather of winter 2025-26: long storms must show up as danger to the
modelled seals.

Scenario: 20 Jan - 3 Feb 2026, real Copernicus IBI waves at the Desertas. Two spells of rough sea,
20-26 Jan (peak 6.2 m on 24 Jan) and 26 Jan - 1 Feb (>= 4 m for 42 h on 27-29 Jan); waves stayed at
or above 2.5 m for most of the 19 days to 8 Feb. The same colony is run twice: with the real waves
and with the waves capped at 1 m (control). Seals are not hurt by waves directly; the danger is that
they cannot land (so cannot rest or digest ashore), are pushed to sea, and eat less. The control
shows that the loss is due to the storm and not to a model that starves its seals anyway.

Needs data/real_long/{physics,currents,bgc,waves,ssh}_20260101_20260530.nc (not in git): skipped
without them. Run: uv run pytest tests/integration/test_winter_storms_2026.py -v (about 2 minutes)
"""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import pytest
import xarray as xr

from src.simulation.agents.config import (
    DESERTAS_FEED_EXCLUDE_BOX,
    DESERTAS_HAULOUT_BOX,
    MADEIRA_CONFIG,
    SHELF_DEPTH_M,
)
from src.simulation.run_real_long import run_long_simulation

SRC = Path(__file__).resolve().parents[2] / "data" / "real_long"
TAG = "20260120_20260203"
EMODNET = SRC / "bathymetry_emodnet.nc"
SOURCES = {
    n: SRC / f"{n}_20260101_20260530.nc" for n in ("physics", "currents", "bgc", "waves", "ssh")
}
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in SOURCES.values()),
    reason="needs the Jan-May 2026 Copernicus files in data/real_long",
)

# The prototype colony: roosts on the Desertas, feeds on the shelf within a day trip, digests while
# swimming. max_hours_away 24 and active_digestion_fraction are the calibration that keeps this
# colony's mass level in calm January weather on the Copernicus 3 km sea floor (+0.4 kg per seal in
# 14 days, 0.4).
COLONY = replace(
    MADEIRA_CONFIG,
    haulout_box=DESERTAS_HAULOUT_BOX,
    forage_max_depth_m=SHELF_DEPTH_M,
    forage_exclude_box=DESERTAS_FEED_EXCLUDE_BOX,
    feeding_trips=True,
    feeding_range_km=45.0,
    active_digestion_fraction=0.4,
    max_hours_away=24.0,
)
# On EMODnet the colony makes same-day trips around Madeira: swims 10 km/h, feeds up to 90 km out
# and is back in the roost 24 h after leaving it (home_by_hours counts the swim back). That
# leaves less time to feed, so digestion while swimming is 0.7 (calm control -0.8 kg in 14 days,
# 2026-10-29, three seeds of 12 seals; 0.5 gives -1.9 kg).
COLONY_EMODNET = replace(
    COLONY,
    active_digestion_fraction=0.7,
    feeding_range_km=90.0,
    trip_speed_km_h=10.0,
    max_hours_away=None,
    home_by_hours=24.0,
)
AGENTS, SEED = 12, 42


def _slice(dst: Path, wave_cap: float | None) -> None:
    dst.mkdir(parents=True)
    for name, path in SOURCES.items():
        daily = name in (
            "physics",
            "currents",
            "bgc",
        )  # daily products start a day early: data on both sides of hour 0
        ds = (
            xr.open_dataset(path)
            .sel(time=slice("2026-01-19" if daily else "2026-01-20", "2026-02-04"))
            .load()
        )
        if name == "waves" and wave_cap is not None:
            ds["VHM0"] = ds["VHM0"].clip(max=wave_cap)
        ds.to_netcdf(dst / f"{name}_{TAG}.nc")


def _run(
    root: Path, wave_cap: float | None, monkeypatch, bathymetry_file: str | None = None
) -> list[dict]:
    _slice(root / "data" / "real_long", wave_cap)
    monkeypatch.chdir(root)  # run_long_simulation reads and writes under ./data/real_long
    run_long_simulation(
        start_time="2026-01-20 00:00",
        duration_days=14,
        data_tag=TAG,
        output_file="run.csv",
        seed=SEED,
        num_agents=AGENTS,
        config=COLONY if bathymetry_file is None else COLONY_EMODNET,
        overwrite=True,
        bathymetry_file=bathymetry_file,
    )
    with open(root / "data" / "real_long" / "run.csv") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module", params=["copernicus", "emodnet"])
def runs(request, tmp_path_factory):
    """Storm and calm runs on the Copernicus 3 km sea floor and on EMODnet (if downloaded)."""
    bathymetry = None
    if request.param == "emodnet":
        if not EMODNET.exists():
            pytest.skip("needs data/real_long/bathymetry_emodnet.nc (download_bathymetry)")
        bathymetry = str(EMODNET)
    with pytest.MonkeyPatch.context() as mp:
        storm = _run(tmp_path_factory.mktemp("storm"), None, mp, bathymetry)
        calm = _run(tmp_path_factory.mktemp("calm"), 1.0, mp, bathymetry)
    return storm, calm


def _final(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["time"] == rows[-1]["time"]]


def _mean(rows: list[dict], key: str) -> float:
    return sum(float(r[key]) for r in rows) / len(rows)


def test_the_scenario_is_a_real_storm_winter():
    waves = (
        xr.open_dataset(SOURCES["waves"])
        .VHM0.sel(
            time=slice("2026-01-20", "2026-02-03"),
            latitude=slice(32.3, 32.8),
            longitude=slice(-16.8, -16.3),
        )
        .max(dim=["latitude", "longitude"])
    )
    assert float(waves.max()) > 5.5, "the 24 Jan peak is about 6.2 m"
    assert int((waves >= 2.5).sum()) > 250, (
        "most of the 15 days are at or above the 2.5 m storm threshold"
    )
    assert int((waves >= 4.0).sum()) > 80, "and 4 m (no landing possible) for days in total"


def test_nobody_rests_ashore_when_the_swell_is_too_big_to_land(runs):
    storm, _ = runs
    limit = MADEIRA_CONFIG.max_landing_swell
    big = [
        r for r in storm if r["swh"] and float(r["swh"]) > limit + 0.5
    ]  # 0.5 m clear of the limit: the hour the swell crosses it is not a test
    # seeds 42-44: about 190-210 such seal-hours on the 3 km sea floor, 55-85 on EMODnet (the
    # colony spends less time in the roughest water there); the guard is just that the check bites
    assert len(big) > 50, "the scenario has enough seal-hours well above the landing limit"
    assert not [
        r
        for r in big
        if r["is_land"] == "True" and r["state"] in ("SLEEPING", "RESTING", "HAULING_OUT")
    ]


def test_swell_above_the_landing_limit_drives_the_colony_off_the_beaches(runs):
    """Within the storm run: ashore share above the landing limit is a fraction of that in lighter
    seas.

    Between 2.5 m (storm threshold) and the limit seals go ashore for shelter, so only above it
    do they lose the beaches.
    """
    storm, _ = runs
    ashore = lambda rows: sum(r["is_land"] == "True" for r in rows) / len(rows)  # noqa: E731
    limit = MADEIRA_CONFIG.max_landing_swell
    rough = [r for r in storm if r["swh"] and float(r["swh"]) > limit]
    light = [r for r in storm if r["swh"] and float(r["swh"]) <= limit]
    assert len(rough) > 100
    assert ashore(rough) < 0.4 * ashore(light), (ashore(rough), ashore(light))


def test_the_calm_control_keeps_its_condition(runs):
    """If the control lost mass too, the calibration (not the weather) would starve the seals."""
    _, calm = runs
    assert _mean(_final(calm), "mass") > 297.0, _mean(_final(calm), "mass")


def test_the_storms_cost_the_seals_body_mass(runs):
    storm, calm = runs
    lost = _mean(_final(calm), "mass") - _mean(_final(storm), "mass")
    assert lost > 6.0, f"storm colony only {lost:.1f} kg lighter than the calm one"


def test_the_storms_cut_food_intake_and_drain_the_energy_buffer(runs):
    storm, calm = runs
    assert _mean(_final(storm), "energy_in_kj") < 0.7 * _mean(_final(calm), "energy_in_kj")
    assert (
        _mean(_final(storm), "energy") < _mean(_final(calm), "energy") - 20000
    )  # kJ, 20 points of the 100 000 buffer
