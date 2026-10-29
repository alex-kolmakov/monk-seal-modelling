"""A swimming seal never ends a move on a land or coastline cell (a shore on a 0.4 km sea floor).

Run: uv run pytest tests/unit/test_snap_to_sea.py -v
"""

from __future__ import annotations

import numpy as np

from src.simulation.agents.config import MADEIRA_CONFIG
from src.simulation.agents.seal import SealAgent, SealState

N, STEP = 61, 0.005  # 0.55 km cells
LAT0, LON0 = 32.5, -16.8


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
    depth = np.full((N, N), 60.0)
    depth[30, 30] = np.nan  # one shore cell: mostly water around it, so navigation counts it as sea
    return {
        "depth": _grid(depth),
        "chl": _grid(np.full((N, N), 0.3)),
        "swh": _grid(np.full((N, N), 0.5)),
        "tide": 0.0,
    }


def _on_shore(pos, buffers) -> bool:
    return SealAgent._is_shore_cell(pos[0], pos[1], buffers)


def _seal_on_the_shore_cell(buffers):
    shore = (LAT0 + 30 * STEP, LON0 + 30 * STEP)
    a = SealAgent("1", start_pos=shore, age=6, sex="F", config=MADEIRA_CONFIG, seed=3)
    a.state = SealState.FORAGING
    assert _on_shore(a.pos, buffers)
    return a


def test_snap_moves_a_seal_from_the_shore_to_the_sea():
    buffers = _buffers()
    a = _seal_on_the_shore_cell(buffers)
    a._snap_to_sea(buffers)
    assert not _on_shore(a.pos, buffers)


def test_a_swimming_move_never_ends_on_the_shore_cell():
    buffers = _buffers()
    for seed in range(20):
        a = _seal_on_the_shore_cell(buffers)
        a.rng = np.random.default_rng(seed)
        a._move_smart(buffers, intention="WATER", speed=0.001)
        assert not _on_shore(a.pos, buffers), seed


def test_a_seal_hauling_out_may_stay_on_the_shore():
    buffers = _buffers()
    a = _seal_on_the_shore_cell(buffers)
    a._move_smart(buffers, intention="LAND", speed=0.0005)
    assert _on_shore(a.pos, buffers)
