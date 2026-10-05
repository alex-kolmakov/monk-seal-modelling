"""Unit tests for query_env_buffers: no silent defaults, no swallowed errors.

Run: uv run pytest tests/unit/test_env_query.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

from src.simulation.environment.utils import query_env_buffers


def buf(data: np.ndarray, lat_min=32.0, lon_min=-17.0, step=0.1) -> dict:
    return {
        "data": data,
        "lat_min": lat_min,
        "lat_step": step,
        "lon_min": lon_min,
        "lon_step": step,
        "shape": data.shape,
    }


SWH = buf(np.full((5, 5), 2.0))
DEPTH = buf(np.full((5, 5), 40.0))


def test_inside_grid_reads_value():
    r = query_env_buffers(32.2, -16.8, {"swh": SWH, "depth": DEPTH, "tide": 0.4})
    assert r["swh"] == 2.0
    assert r["depth"] == 40.0
    assert r["tide"] == 0.4
    assert r["out_of_bounds"] is False


def test_outside_grid_is_none_and_flagged_not_a_default():
    r = query_env_buffers(40.0, -16.8, {"swh": SWH, "depth": DEPTH, "tide": 0.4})
    assert r["swh"] is None, "off-grid swell must not read as calm sea (0.0)"
    assert r["out_of_bounds"] is True
    assert r["is_land"] is False


def test_malformed_buffer_raises_instead_of_being_skipped():
    broken = {"data": np.zeros((2, 2)), "lat_min": 32.0}  # no steps, no shape
    with pytest.raises(KeyError):
        query_env_buffers(32.0, -17.0, {"swh": broken})


def test_land_cell_feels_swell_of_nearest_water():
    swh = np.full((5, 5), 3.5)
    swh[2, 2] = np.nan  # land on the wave grid
    r = query_env_buffers(32.2, -16.8, {"swh": buf(swh)})
    assert r["swh"] == 3.5, "a seal ashore must not read calm sea during a storm"
