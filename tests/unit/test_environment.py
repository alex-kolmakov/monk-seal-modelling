"""Unit tests for the Environment class — tidal data loading.

TDD red phase — currently failing:
    - TestTidalDataLoading::test_tidal_dataset_detected_on_load
    - TestTidalDataLoading::test_buffers_tide_comes_from_dataset_not_sine_wave
    - TestTidalDataLoading::test_tidal_fallback_to_sine_when_no_tidal_file

Run: uv run pytest tests/unit/test_environment.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.simulation.environment.environment import Environment

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def make_fake_tidal_dataset(sla_value: float = 0.10) -> xr.Dataset:
    """Minimal xarray Dataset that mimics the structure of tidal_2023_2024.nc.

    The real file has:
        dims: time(695), latitude(6), longitude(6)
        vars: sla (sea level anomaly, metres), adt (absolute dynamic topography)

    We create a 3-timestep, 2×2 dataset with a known, constant sla value so
    that normalised tide output is predictable in tests.
    """
    times = pd.date_range("2023-01-01", periods=3, freq="D")
    lats = np.array([32.12, 32.38], dtype=np.float32)
    lons = np.array([-17.38, -17.12], dtype=np.float32)

    # Vary sla across time so min/max normalisation is non-trivial
    sla_data = np.full((3, 2, 2), sla_value, dtype=np.float64)
    sla_data[0] = -0.10    # min
    sla_data[2] =  0.20    # max
    # Middle timestep = sla_value (default 0.10)

    return xr.Dataset(
        {"sla": (["time", "latitude", "longitude"], sla_data)},
        coords={"time": times, "latitude": lats, "longitude": lons},
    )


class TestTidalDataLoading:
    """#4 — Environment must load and use real tidal SLA data from NetCDF."""

    def test_tidal_dataset_detected_on_load(self, tmp_path):
        """After loading a file containing 'sla', the environment stores tidal metadata.

        Fix — environment.py load_data():
            Detect 'sla' or 'adt' variable in a loaded dataset and set:
                self.tidal_dataset   (the xr.Dataset)
                self.tidal_variable  ('sla' or 'adt')
                self.tidal_min / self.tidal_max  (pre-computed spatial-mean bounds)
        """
        ds = make_fake_tidal_dataset()
        nc_path = str(tmp_path / "tidal.nc")
        ds.to_netcdf(nc_path)

        env = Environment()
        env.load_data([nc_path])

        assert hasattr(env, "tidal_dataset"), "tidal_dataset must be set after loading"   # FAILS
        assert env.tidal_variable == "sla"
        assert env.tidal_min < env.tidal_max

    def test_buffers_tide_comes_from_dataset_not_sine_wave(self, tmp_path):
        """buffers['tide'] must be interpolated from SLA, not from a sine wave.

        Strategy:
            - Build a fake tidal dataset with known SLA at a specific timestamp.
            - The middle timestep has sla=0.10.  With min=-0.10 and max=0.20:
                  normalised = (0.10 - (-0.10)) / (0.20 - (-0.10)) = 0.20/0.30 ≈ 0.667
            - The sine wave at the same timestamp would produce a completely
              different value, confirming the source changed.

        Fix — environment.py update_buffers():
            Replace the sine-wave block with:
                if hasattr(self, 'tidal_dataset') and self.tidal_dataset is not None:
                    use the dataset
                else:
                    fall back to sine wave
        """
        ds = make_fake_tidal_dataset(sla_value=0.10)
        nc_path = str(tmp_path / "tidal.nc")
        ds.to_netcdf(nc_path)

        env = Environment()
        env.load_data([nc_path])
        env.update_buffers("2023-01-02")   # middle timestep → sla ≈ 0.10

        tide = env.buffers["tide"]
        expected = (0.10 - (-0.10)) / (0.20 - (-0.10))   # ≈ 0.667

        assert isinstance(tide, float)
        assert tide == pytest.approx(expected, abs=0.05), (   # FAILS
            f"expected tide ≈ {expected:.3f} from SLA, got {tide:.3f} (sine wave?)"
        )

    def test_tidal_fallback_to_sine_when_no_tidal_file(self):
        """Without a tidal file, update_buffers() must still produce a valid tide value.

        The sine wave fallback must remain intact so the model degrades gracefully
        when the tidal NetCDF is not available.
        """
        env = Environment()
        env.update_buffers("2023-06-15 06:00:00")
        tide = env.buffers.get("tide")

        assert tide is not None
        assert 0.0 <= tide <= 1.0, "fallback sine tide must be in [0, 1]"

    def test_tidal_value_in_zero_one_range(self, tmp_path):
        """Normalised tide must always be in [0, 1] for any timestamp in the dataset."""
        ds = make_fake_tidal_dataset()
        nc_path = str(tmp_path / "tidal.nc")
        ds.to_netcdf(nc_path)

        env = Environment()
        env.load_data([nc_path])

        for ts in ["2023-01-01", "2023-01-02", "2023-01-03"]:
            env.update_buffers(ts)
            tide = env.buffers["tide"]
            assert 0.0 <= tide <= 1.0, f"tide={tide} out of range for {ts}"
