"""Unit tests for correlated_random_walk movement algorithm.

TDD red phase — currently failing:
    - test_longitude_corrected_for_latitude
    - test_correlated_random_walk_no_dummy_param

Run: uv run pytest tests/unit/test_movement.py -v
"""

from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from src.simulation.agents.movement import correlated_random_walk


class TestLatitudeCorrectedLongitude:
    """Bug #6 — longitude step is not divided by cos(lat), causing ~15% error at 32°N."""

    def test_longitude_corrected_for_latitude(self):
        """At 32°N heading due east, the longitude step must be divided by cos(lat).

        Without correction: new_lon += step * cos(heading)
        With correction:    new_lon += step * cos(heading) / cos(lat)

        At 32.5°N, cos(32.5°) ≈ 0.843, so the corrected step is ~18.6% longer in
        degrees lon to maintain the same real-world distance (degrees of longitude
        are shorter than degrees of latitude at mid-latitudes).

        Fix — movement.py:64:
            new_lon = lon + step_size * math.cos(new_heading)
            →  new_lon = lon + step_size * math.cos(new_heading) / math.cos(math.radians(lat))
        """
        lat, lon = 32.5, -17.0
        step = 0.05

        # Freeze vonmises to 0 so heading stays exactly east (heading=0)
        with patch("numpy.random.vonmises", return_value=0.0):
            (new_pos, _) = correlated_random_walk((lat, lon), 0.0, speed=step)

        new_lat, new_lon = new_pos

        # Latitude must be unchanged for pure-east heading
        assert new_lat == pytest.approx(lat, abs=1e-10)

        # Corrected longitude: step / cos(lat) produces more eastward movement
        expected_lon = lon + step / math.cos(math.radians(lat))
        assert new_lon == pytest.approx(expected_lon, rel=1e-6)   # FAILS without fix

    def test_north_pole_latitude_unchanged(self):
        """Pure-north heading (π/2) must not alter longitude regardless of correction."""
        lat, lon = 32.5, -17.0

        with patch("numpy.random.vonmises", return_value=0.0):
            (new_pos, _) = correlated_random_walk((lat, lon), math.pi / 2, speed=0.05)

        # cos(π/2) = 0, so no longitude change even with lat correction
        assert new_pos[1] == pytest.approx(lon, abs=1e-10)

    def test_latitude_step_unchanged_by_correction(self):
        """Latitude step (sin component) must NOT be divided by cos(lat).

        Only the longitude component needs the correction — latitude degrees
        are the same real-world distance regardless of position.
        """
        lat, lon = 32.5, -17.0
        step = 0.05

        with patch("numpy.random.vonmises", return_value=0.0):
            (new_pos, _) = correlated_random_walk((lat, lon), math.pi / 2, speed=step)

        # heading=π/2 → sin(π/2)=1 → full step northward, no correction
        assert new_pos[0] == pytest.approx(lat + step, rel=1e-6)


class TestRemoveDummyDataInParam:
    """Bug #9 — data_in is an unused dummy first parameter; callers always pass None."""

    def test_correlated_random_walk_no_dummy_param(self):
        """correlated_random_walk must work when called with (pos, heading) signature.

        After removing data_in, the call sites in seal.py:495 and seal.py:588
        which pass None as the first arg must also be updated to drop it.

        Fix — movement.py:6:
            def correlated_random_walk(data_in, current_pos, ...) →
            def correlated_random_walk(current_pos, ...)

        And seal.py:495, 588:
            correlated_random_walk(None, self.pos, self.heading, ...) →
            correlated_random_walk(self.pos, self.heading, ...)
        """
        with patch("numpy.random.vonmises", return_value=0.0):
            # Call WITHOUT the dummy first argument
            (pos, heading) = correlated_random_walk((32.5, -17.0), 0.0, speed=0.05)  # FAILS

        assert pos[0] == pytest.approx(32.5, abs=1e-6)   # latitude unchanged (east heading)
