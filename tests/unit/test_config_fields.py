"""Every SealConfig field must change behaviour.

The README offers SealConfig as the way to port the model to another colony, but
several fields were shadowed by literals (storm_threshold, max_landing_swell,
starvation_threshold, amr_multiplier, hsi_chl_threshold, ...), so changing them
did nothing. This test perturbs each field and requires the trajectory to differ.

Run: uv run pytest tests/unit/test_config_fields.py -v
"""

from __future__ import annotations

import math
from dataclasses import fields, replace

import numpy as np
import pytest

from src.simulation.agents.config import SealConfig
from src.simulation.agents.seal import SealAgent, SealState

LAT0, LON0, STEP, N = 32.5, -17.0, 0.05, 61  # 3° × 3° grid, 0.05° cells
HOURS = 300  # ~4 swell cycles; 200 also passes but with little margin
SEED = 7

# Fields that are not wired to behaviour yet, with the plan step that wires them.
NOT_YET_WIRED = {
    "mass": "mass is not a live state yet (P1 step 3, blocked on a blubber-mass source)",
}


def _buf(data: np.ndarray) -> dict:
    return {
        "data": data,
        "lat_min": LAT0 - (N // 2) * STEP,
        "lat_step": STEP,
        "lon_min": LON0 - (N // 2) * STEP,
        "lon_step": STEP,
        "shape": data.shape,
    }


def _static_world() -> tuple[dict, dict]:
    """Island at the centre, then shallow / medium / deep rings.

    chl is Madeira-like (0.35 mg/m³ at the coast, falling off): above ~0.25 HSI would
    saturate at hsi_chl_threshold and hsi_floor could never bind.
    """
    idx = np.arange(N) - N // 2
    r = np.hypot(*np.meshgrid(idx, idx, indexing="ij"))  # distance in cells
    depth = np.select([r < 3, r < 8, r < 14], [np.nan, 30.0, 75.0], default=500.0)
    chl = np.clip(0.35 - 0.015 * r, 0.05, None)
    return _buf(depth), _buf(chl)


DEPTH, CHL = _static_world()


def buffers_at(hour: int) -> dict:
    """Swell cycles 0–5 m every 3 days (crosses both storm thresholds); M2-like tide."""
    swh = 2.5 + 2.5 * math.sin(2 * math.pi * hour / 72)
    return {
        "depth": DEPTH,
        "chl": CHL,
        "swh": _buf(np.full((N, N), swh)),
        "tide": 0.75 * math.sin(2 * math.pi * hour / 12.42),
    }


def trajectory(config: SealConfig) -> list[tuple]:
    """Five agents from different starting conditions, stepped for HOURS hours."""
    starts = [  # (energy fraction or None = config.initial_energy, stomach kg, pos offset, state)
        (None, 0.0, (0.25, 0.0), SealState.FORAGING),
        (0.50, 0.0, (0.0, 0.45), SealState.FORAGING),
        (0.18, 4.0, (-0.3, 0.0), SealState.FORAGING),
        (0.13, 0.0, (0.0, -0.6), SealState.FORAGING),
        # Asleep on the island, empty, at low-ish tide: the hunger-wake branch decides
        # hour 0. In free runs the tide usually evicts sleepers before they get hungry.
        (0.90, 0.0, (0.0, 0.0), SealState.SLEEPING),
        # Adult male: exposed to male_annual_risk
        (None, 0.0, (0.25, 0.25), SealState.FORAGING),
    ]
    agents = []
    for i, (frac, stomach, (dlat, dlon), state) in enumerate(starts):
        sex = "M" if i == len(starts) - 1 else "F"
        a = SealAgent(str(i), start_pos=(LAT0 + dlat, LON0 + dlon), age=6, sex=sex,
                      config=config, seed=SEED)
        if frac is not None:
            a.energy = frac * config.max_energy
        a.stomach_load = stomach
        a.state = state
        agents.append(a)

    out = []
    for hour in range(HOURS):
        b = buffers_at(hour)
        for a in agents:
            if a.state != SealState.DEAD:
                a.update_with_buffers(b)
            out.append((a.id, a.state.name, round(a.energy, 6), round(a.stomach_load, 6),
                        round(a.pos[0], 9), round(a.pos[1], 9)))
    return out


# Rare-event fields: ±30% almost never changes a 300 h run, so push them to the extreme.
EXTREME_PERTURBATIONS = {
    "male_annual_risk": [1.0],  # certain death in the first hour
}


def perturbations(name: str, value: float) -> list[float]:
    """Up and down: a threshold may only bind on one side (e.g. 0.95 × 1.3 > 100%)."""
    if name in EXTREME_PERTURBATIONS:
        return EXTREME_PERTURBATIONS[name]
    return [value * 1.3, value * 0.7] if value != 0 else [0.5]


BASELINE = None


def baseline() -> list[tuple]:
    global BASELINE
    if BASELINE is None:
        BASELINE = trajectory(SealConfig())
    return BASELINE


def test_baseline_run_exercises_the_model():
    """Guard: the scenario must reach the branches the fields control."""
    states = {s for _, s, *_ in baseline()}
    assert {"FORAGING", "RESTING", "HAULING_OUT"} <= states, states
    assert "DEAD" in states or "RECOVERY" in states, states


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(f.name, marks=pytest.mark.xfail(reason=NOT_YET_WIRED[f.name], strict=True))
        if f.name in NOT_YET_WIRED
        else f.name
        for f in fields(SealConfig)
    ],
)
def test_every_config_field_changes_behaviour(name):
    changed = any(
        trajectory(replace(SealConfig(), **{name: value})) != baseline()
        for value in perturbations(name, getattr(SealConfig(), name))
    )
    assert changed, f"SealConfig.{name} has no effect on behaviour"
