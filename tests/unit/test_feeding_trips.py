"""config.feeding_trips: a seal stays out feeding until full, and digests afloat at the roost
instead of shuttling with the tide.

Run: uv run pytest tests/unit/test_feeding_trips.py -v
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.simulation.agents.config import MADEIRA_CONFIG
from src.simulation.agents.seal import SealAgent, SealState

BOX = (32.35, 32.60, -16.60, -16.40)
N, STEP = 41, 0.05
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
    return {"depth": _buf(60.0), "chl": _buf(0.3), "swh": _buf(0.5), "tide": tide}


def _agent(pos, state, trips, stomach):
    config = replace(MADEIRA_CONFIG, haulout_box=BOX, feeding_trips=trips)
    a = SealAgent("1", start_pos=pos, age=6, sex="F", config=config, seed=3)
    a.state = state
    a.stomach_load = stomach
    return a


def test_half_full_at_low_tide_far_from_the_roost_keeps_feeding():
    a = _agent((33.0, -16.5), SealState.FORAGING, trips=True, stomach=8.0)
    a.update_with_buffers(_buffers(-0.5))
    assert a.state == SealState.FORAGING


def test_without_the_rule_the_same_seal_heads_for_the_roost():
    a = _agent((33.0, -16.5), SealState.FORAGING, trips=False, stomach=8.0)
    a.update_with_buffers(_buffers(-0.5))
    assert a.state == SealState.HAULING_OUT


def test_a_full_seal_still_returns_to_the_roost():
    a = _agent((33.0, -16.5), SealState.FORAGING, trips=True, stomach=14.0)
    a.update_with_buffers(_buffers(0.0))
    assert a.state == SealState.HAULING_OUT


def test_arriving_at_the_roost_at_high_tide_with_food_rests_afloat():
    a = _agent((32.5, -16.5), SealState.HAULING_OUT, trips=True, stomach=10.0)
    for _ in range(3):
        a.update_with_buffers(_buffers(0.6))
    assert a.state == SealState.RESTING
    assert a.stomach_load < 10.0, "digesting"


def test_without_the_rule_high_tide_at_the_roost_sends_it_out_again():
    a = _agent((32.5, -16.5), SealState.HAULING_OUT, trips=False, stomach=10.0)
    a.update_with_buffers(_buffers(0.6))
    assert a.state == SealState.FORAGING


def test_an_empty_stomach_at_the_roost_still_goes_to_feed():
    a = _agent((32.5, -16.5), SealState.RESTING, trips=True, stomach=0.0)
    a.update_with_buffers(_buffers(0.6))
    assert a.state == SealState.FORAGING


def test_a_seal_on_a_shelf_edge_eats_where_it_stays_when_every_move_is_refused():
    """The move off the shelf is undone; the food it 'ate' in deep water (none) must be undone with
    it.
    """
    depth = np.full((N, N), 300.0)
    depth[18:23, 18:23] = 80.0  # a 5 x 5 pixel plateau, 80 m deep: the only place food can be had
    buf = {"depth": {**_buf(0), "data": depth}, "chl": _buf(0.5), "swh": _buf(0.5), "tide": 0.0}
    lat, lon = LAT0 + 20 * STEP, LON0 + 20 * STEP
    config = replace(MADEIRA_CONFIG, forage_max_depth_m=100.0)
    a = SealAgent("1", start_pos=(lat, lon), age=6, sex="F", config=config, seed=5)
    a.state, a.stomach_load = SealState.FORAGING, 0.0
    for _ in range(12):
        a.update_with_buffers(buf)
        if a.state != SealState.FORAGING:
            break
    assert a.stomach_load > 2.0, a.stomach_load


def _island_world():
    """Depth 300 m everywhere, an island wall (NaN) across lon -16.9..-16.7, shelf (60 m) at both
    sides of it.
    """
    depth = np.full((N, N), 300.0)
    lon = LON0 + np.arange(N) * STEP
    wall = (lon > -16.9) & (lon < -16.7)
    depth[:, wall] = np.nan
    depth[:, (lon >= -16.7) & (lon < -16.6)] = (
        60.0  # shelf just behind the island: 0.3 deg from the seal
    )
    depth[:, (lon > -17.4) & (lon <= -17.3)] = 60.0  # shelf on the seal's own side: 0.7 deg away
    return {"depth": {**_buf(0), "data": depth}, "chl": _buf(0.3), "swh": _buf(0.5), "tide": 0.0}


def _open_shelf_world():
    """Shelf (60 m) everywhere except deep water (300 m) within ~0.2 deg of the seal's start: it has
    to travel.
    """
    lat = LAT0 + np.arange(N)[:, None] * STEP
    lon = LON0 + np.arange(N)[None, :] * STEP
    depth = np.where(np.hypot(lat - 32.5, lon + 17.0) < 0.2, 300.0, 60.0)
    return {"depth": {**_buf(0), "data": depth}, "chl": _buf(0.3), "swh": _buf(0.5), "tide": 0.0}


def test_the_nearest_feeding_cell_is_not_one_across_an_island():
    """Seal 5 sat frozen 160 h: its nearest allowed cell was on the far side of Madeira, so every
    move was refused.
    """
    config = replace(MADEIRA_CONFIG, forage_max_depth_m=100.0)
    a = SealAgent("1", start_pos=(32.5, -17.0), age=6, sex="F", config=config, seed=2)
    target, _ = a._find_forage_cell(_island_world())
    assert target is not None
    lat, lon = target
    assert lon < -16.9, f"target ({lat:.2f}, {lon:.2f}) is across the island"


def test_feeding_range_spreads_the_colony_over_the_shelf_instead_of_one_patch():
    world = _open_shelf_world()
    config = replace(MADEIRA_CONFIG, forage_max_depth_m=100.0, feeding_range_km=45.0)
    targets = []
    for seed in range(12):
        a = SealAgent("1", start_pos=(32.5, -17.0), age=6, sex="F", config=config, seed=seed)
        a.state = SealState.TRANSITING
        a.update_with_buffers(world)
        assert a.trip_target is not None
        targets.append(a.trip_target)
        assert a._calculate_distance_km((32.5, -17.0), a.trip_target) <= 46.0
    assert len({(round(t[0], 1), round(t[1], 1)) for t in targets}) >= 6, targets


def test_without_feeding_range_every_seal_heads_for_the_nearest_cell():
    world = _open_shelf_world()
    config = replace(MADEIRA_CONFIG, forage_max_depth_m=100.0)
    a = SealAgent("1", start_pos=(32.5, -17.0), age=6, sex="F", config=config, seed=3)
    a.state = SealState.TRANSITING
    a.update_with_buffers(world)
    assert a.trip_target is None


def _swimmer(fraction):
    config = replace(MADEIRA_CONFIG, active_digestion_fraction=fraction, forage_max_depth_m=100.0)
    a = SealAgent("1", start_pos=(32.5, -17.0), age=6, sex="F", config=config, seed=3)
    a.state, a.stomach_load = SealState.TRANSITING, 10.0
    deep = {
        "depth": _buf(500.0),
        "chl": _buf(0.3),
        "swh": _buf(0.5),
        "tide": 0.0,
    }  # too deep to feed: stays in transit
    a.update_with_buffers(deep)
    assert a.state == SealState.TRANSITING
    return a


def test_a_swimming_seal_digests_at_the_set_fraction_of_the_rest_rate():
    assert _swimmer(0.0).stomach_load == 10.0
    assert abs(_swimmer(0.4).stomach_load - (10.0 - 0.4 * MADEIRA_CONFIG.digestion_rate)) < 1e-9
    assert (
        _swimmer(0.4).energy_in_kj
        == 0.4 * MADEIRA_CONFIG.digestion_rate * MADEIRA_CONFIG.energy_per_kg_food
    )


def _away(hours, limit, stomach=3.0):
    config = replace(MADEIRA_CONFIG, haulout_box=BOX, feeding_trips=True, max_hours_away=limit)
    a = SealAgent("1", start_pos=(33.0, -16.5), age=6, sex="F", config=config, seed=3)
    a.state, a.stomach_load, a.hours_away = SealState.FORAGING, stomach, hours
    return a


def test_a_seal_away_too_long_turns_for_the_roost_even_with_a_hungry_stomach():
    a = _away(23, 24.0)
    a.update_with_buffers(_buffers(0.0))
    assert a.state == SealState.HAULING_OUT, a.hours_away


def test_a_seal_inside_the_time_limit_keeps_feeding_and_without_a_limit_too():
    a = _away(10, 24.0)
    a.update_with_buffers(_buffers(0.0))
    assert a.state == SealState.FORAGING
    b = _away(200, None)
    b.update_with_buffers(_buffers(0.0))
    assert b.state == SealState.FORAGING


def test_a_seal_on_its_way_home_is_not_turned_back_to_feeding_by_high_tide():
    a = _away(30, 24.0)
    a.state = SealState.HAULING_OUT
    for _ in range(3):
        a.update_with_buffers(_buffers(0.6))
        assert a.state == SealState.HAULING_OUT
    assert a.pos[0] < 33.0, "still heading south for the box"


def test_time_away_resets_in_the_roost_box():
    config = replace(MADEIRA_CONFIG, haulout_box=BOX, feeding_trips=True, max_hours_away=24.0)
    a = SealAgent("1", start_pos=(32.5, -16.5), age=6, sex="F", config=config, seed=3)
    a.state, a.stomach_load, a.hours_away = SealState.RESTING, 5.0, 20
    a.update_with_buffers(_buffers(0.0))
    assert a.hours_away == 0


def _km(a, b):
    return float(np.hypot((a[0] - b[0]) * 111.0, (a[1] - b[1]) * 111.0 * np.cos(np.radians(a[0]))))


def test_trip_speed_sets_how_far_a_seal_swims_to_feeding_water_in_an_hour():
    def travelled(speed):
        config = replace(MADEIRA_CONFIG, forage_max_depth_m=100.0, trip_speed_km_h=speed)
        a = SealAgent("1", start_pos=(32.5, -17.0), age=6, sex="F", config=config, seed=3)
        a.state = SealState.TRANSITING
        start = a.pos
        a.update_with_buffers(_open_shelf_world())
        return _km(start, a.pos)

    default, fast = travelled(None), travelled(11.1)
    assert 4.0 < default < 7.0, default
    assert fast > 1.6 * default, (default, fast)


def test_trip_speed_sets_how_fast_a_seal_heads_home():
    def km_gained(speed):
        config = replace(MADEIRA_CONFIG, haulout_box=BOX, feeding_trips=True, trip_speed_km_h=speed)
        a = SealAgent("1", start_pos=(33.0, -16.5), age=6, sex="F", config=config, seed=3)
        a.state, a.stomach_load = SealState.HAULING_OUT, 3.0
        before = _km(a.pos, (32.475, -16.5))
        a.update_with_buffers(_buffers(0.0))
        return before - _km(a.pos, (32.475, -16.5))

    assert km_gained(11.1) > 1.6 * km_gained(None)


def _home_by(hours_away, lat, home_by, speed=None):
    config = replace(
        MADEIRA_CONFIG,
        haulout_box=BOX,
        feeding_trips=True,
        home_by_hours=home_by,
        trip_speed_km_h=speed,
    )
    a = SealAgent("1", start_pos=(lat, -16.5), age=6, sex="F", config=config, seed=3)
    a.state, a.stomach_load, a.hours_away = SealState.FORAGING, 3.0, hours_away
    a.update_with_buffers(_buffers(0.0))
    return a.state


def test_a_seal_turns_for_home_when_time_away_plus_the_swim_back_reach_the_deadline():
    # 33.0 N is 58 km from the box centre: 10.5 h at 5.5 km/h
    assert _home_by(10, 33.0, 24.0) == SealState.FORAGING  # 10 + 10.5 < 24
    assert _home_by(14, 33.0, 24.0) == SealState.HAULING_OUT  # 14 + 10.5 >= 24


def test_the_same_seal_close_to_the_roost_may_stay_out_longer():
    assert _home_by(14, 32.7, 24.0) == SealState.FORAGING  # 22 km away: 4 h back


def test_a_faster_swimmer_can_stay_out_longer_before_turning_for_home():
    assert _home_by(14, 33.0, 24.0, speed=11.1) == SealState.FORAGING  # 5.3 h back
