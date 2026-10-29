"""config.forage_max_depth_m: seals forage only on the shelf and head back to it when they are off
it.

Run: uv run pytest tests/unit/test_forage_shelf.py -v
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.simulation.agents.config import MADEIRA_CONFIG
from src.simulation.agents.seal import SealAgent, SealState

N, STEP = 41, 0.05
LAT0, LON0 = 31.5, -17.5
SHELF_EDGE = 32.5  # south of this: 50 m shelf; north of it: 500 m deep


def _grid(data: np.ndarray) -> dict:
    return {
        "data": data,
        "lat_min": LAT0,
        "lat_step": STEP,
        "lon_min": LON0,
        "lon_step": STEP,
        "shape": data.shape,
    }


def _buffers() -> dict:
    lat = LAT0 + np.arange(N) * STEP
    depth = np.where(lat[:, None] <= SHELF_EDGE, 50.0, 500.0) * np.ones((N, N))
    return {
        "depth": _grid(depth),
        "chl": _grid(np.full((N, N), 0.3)),
        "swh": _grid(np.full((N, N), 0.5)),
        "tide": 0.0,
    }


def _agent(pos, limit):
    config = replace(MADEIRA_CONFIG, forage_max_depth_m=limit)
    a = SealAgent("1", start_pos=pos, age=6, sex="F", config=config, seed=5)
    a.state = SealState.FORAGING
    return a


def _depth(pos):
    return 50.0 if pos[0] <= SHELF_EDGE else 500.0


def test_a_seal_in_deep_water_stops_foraging_and_heads_for_the_shelf():
    a = _agent((SHELF_EDGE + 0.2, -16.5), 100.0)
    a.update_with_buffers(_buffers())
    assert a.state == SealState.TRANSITING
    for _ in range(40):
        a.update_with_buffers(_buffers())
    assert _depth(a.pos) == 50.0, a.pos


def test_foraging_never_happens_in_deep_water():
    a = _agent((SHELF_EDGE - 0.1, -16.5), 100.0)
    for _ in range(200):
        a.update_with_buffers(_buffers())
        if a.state == SealState.FORAGING:
            assert _depth(a.pos) == 50.0, a.pos


def test_without_a_limit_deep_foraging_is_unchanged():
    a = _agent((SHELF_EDGE + 0.2, -16.5), None)
    a.update_with_buffers(_buffers())
    assert a.state == SealState.FORAGING
