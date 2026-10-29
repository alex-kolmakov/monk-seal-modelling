"""config.forage_box: feeding cells are picked only inside the box.

Run: uv run pytest tests/unit/test_forage_box.py -v
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.simulation.agents.config import MADEIRA_CONFIG, MADEIRA_FORAGE_BOX
from src.simulation.agents.seal import SealAgent

N, STEP = 61, 0.05
LAT0, LON0 = 31.5, -18.0
BOX = (32.0, 33.0, -17.0, -16.2)  # the seal sits at its east edge; shelf lies beyond it too


def _grid(data: np.ndarray) -> dict:
    return {
        "data": data,
        "lat_min": LAT0,
        "lat_step": STEP,
        "lat_max": None,
        "lon_min": LON0,
        "lon_step": STEP,
        "shape": data.shape,
    }


def _buffers() -> dict:
    return {
        "depth": _grid(np.full((N, N), 60.0)),
        "chl": _grid(np.full((N, N), 0.3)),
        "swh": _grid(np.full((N, N), 0.5)),
        "tide": 0.0,
    }


def _targets(box, n=30):
    config = replace(
        MADEIRA_CONFIG, forage_max_depth_m=100.0, feeding_range_km=60.0, forage_box=box
    )
    out = []
    for seed in range(n):
        a = SealAgent("1", start_pos=(32.5, -16.4), age=6, sex="F", config=config, seed=seed)
        target = a._pick_trip_target(_buffers())
        assert target is not None
        out.append(target)
    return out


def _inside(pos, box=BOX) -> bool:
    return box[0] <= pos[0] <= box[1] and box[2] <= pos[1] <= box[3]


def test_trips_go_beyond_the_box_when_there_is_none():
    assert not all(_inside(t) for t in _targets(None))


def test_every_trip_is_aimed_inside_the_box():
    assert all(_inside(t) for t in _targets(BOX))


def test_madeira_box_stops_short_of_porto_santo():
    lat_min, lat_max, lon_min, lon_max = MADEIRA_FORAGE_BOX
    assert lat_max < 32.99  # Porto Santo's shelf starts there
    assert lat_min < 32.35 and lon_min < -17.3 and lon_max > -16.3  # Madeira and Desertas inside
