"""config.forage_exclude_box: seals do not forage inside the box; a hungry seal there leaves for
feeding water outside it.

Run: uv run pytest tests/unit/test_forage_exclusion.py -v
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.simulation.agents.config import MADEIRA_CONFIG
from src.simulation.agents.seal import SealAgent, SealState

N, STEP = 61, 0.05
LAT0, LON0 = 31.5, -18.0
BOX = (32.4, 32.6, -16.7, -16.4)  # the "roost": shallow, so it would feed seals if it were allowed


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
    return {
        "depth": _grid(np.full((N, N), 60.0)),
        "chl": _grid(np.full((N, N), 0.3)),
        "swh": _grid(np.full((N, N), 0.5)),
        "tide": 0.0,
    }


def _agent(box):
    config = replace(MADEIRA_CONFIG, forage_exclude_box=box)
    a = SealAgent("1", start_pos=(32.5, -16.55), age=6, sex="F", config=config, seed=11)
    a.state = SealState.FORAGING
    return a


def _inside(pos) -> bool:
    return BOX[0] <= pos[0] <= BOX[1] and BOX[2] <= pos[1] <= BOX[3]


def test_a_seal_in_the_box_stops_foraging_and_leaves_it():
    a = _agent(BOX)
    a.update_with_buffers(_buffers())
    assert a.state == SealState.TRANSITING
    for _ in range(60):
        a.update_with_buffers(_buffers())
    assert not _inside(a.pos), a.pos


def test_it_never_forages_inside_the_box():
    a = _agent(BOX)
    for _ in range(150):
        a.update_with_buffers(_buffers())
        if a.state == SealState.FORAGING:
            assert not _inside(a.pos), a.pos


def test_without_a_box_foraging_at_the_roost_is_unchanged():
    a = _agent(None)
    a.update_with_buffers(_buffers())
    assert a.state == SealState.FORAGING
