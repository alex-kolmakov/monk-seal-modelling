"""config.haulout_box: seals rest, sleep and haul out only inside the box, and travel to it first.

Run: uv run pytest tests/unit/test_haulout_box.py -v
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.simulation.agents.config import MADEIRA_CONFIG
from src.simulation.agents.seal import SealAgent, SealState

BOX = (32.35, 32.60, -16.60, -16.40)
N, STEP = 41, 0.05  # open water, 100 m deep everywhere: 2° x 2° around the box
LAT0, LON0 = 31.5, -17.5


def _buf(value: float) -> dict:
    return {
        "data": np.full((N, N), value),
        "lat_min": LAT0,
        "lat_step": STEP,
        "lon_min": LON0,
        "lon_step": STEP,
        "shape": (N, N),
    }


def _buffers(tide: float) -> dict:
    return {"depth": _buf(100.0), "chl": _buf(0.3), "swh": _buf(0.5), "tide": tide}


def _agent(pos, state, box=BOX, stomach=0.0):
    config = replace(MADEIRA_CONFIG, haulout_box=box)
    a = SealAgent("1", start_pos=pos, age=6, sex="F", config=config, seed=3)
    a.state = state
    a.stomach_load = stomach
    return a


def test_resting_outside_the_box_turns_into_a_trip_to_it():
    a = _agent((33.2, -16.5), SealState.RESTING, stomach=5.0)
    start = a.pos
    for _ in range(10):
        a.update_with_buffers(_buffers(0.0))
    assert a.state == SealState.HAULING_OUT
    assert a.pos[0] < start[0], "should have moved south, towards the box"


def test_resting_inside_the_box_is_left_alone():
    a = _agent((32.5, -16.5), SealState.RESTING, stomach=5.0)
    a.update_with_buffers(_buffers(0.0))
    assert a.state == SealState.RESTING


def test_sleeping_outside_the_box_wakes_up_and_heads_for_it():
    a = _agent((33.2, -16.5), SealState.SLEEPING)
    a.update_with_buffers(_buffers(-0.5))
    assert a.state == SealState.HAULING_OUT


def test_a_full_seal_outside_the_box_does_not_rest_in_the_water():
    a = _agent((33.2, -16.5), SealState.FORAGING, stomach=a_cap(0.9))
    a.update_with_buffers(_buffers(0.0))  # mid tide: it would normally rest in the water
    assert a.state == SealState.HAULING_OUT


def a_cap(fraction: float) -> float:
    return (
        SealAgent("0", start_pos=(32.5, -16.5), config=MADEIRA_CONFIG, seed=0).stomach_capacity
        * fraction
    )


def test_no_box_keeps_the_old_behaviour():
    a = _agent((33.2, -16.5), SealState.RESTING, box=None, stomach=5.0)
    a.update_with_buffers(_buffers(0.0))
    assert a.state == SealState.RESTING
