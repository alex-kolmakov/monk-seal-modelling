"""Unit tests for the Environment class — tide loading.

The tide is IBI hourly sea surface height (zos) in metres above a fixed datum.
It replaced DUACS SLA, which is daily and has the tide removed (a 12.4 h signal
cannot survive daily sampling), and a silent sine-wave fallback.

Run: uv run pytest tests/unit/test_environment.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.simulation.environment.environment import (
    SYNTHETIC_TIDE_AMPLITUDE_M,
    TIDE_DATUM_M,
    Environment,
    TideDataError,
)

M2_PERIOD_H = 12.42
S2_PERIOD_H = 12.00
REAL_SSH_FILE = Path("data/real_long/ssh_20260101_20260530.nc")

# ─── HELPERS ─────────────────────────────────────────────────────────────────


def tide_signal(times: pd.DatetimeIndex) -> np.ndarray:
    """M2 + S2 in metres (spring–neap beat), relative to mean sea level."""
    hours = np.asarray((times - times[0]) / pd.Timedelta(hours=1))
    return 0.75 * np.sin(2 * np.pi * hours / M2_PERIOD_H) + 0.25 * np.sin(
        2 * np.pi * hours / S2_PERIOD_H
    )


def write_zos(tmp_path, times: pd.DatetimeIndex, name: str = "ssh.nc") -> str:
    """Fake IBI zos file on a 2×2 grid inside the Desertas box, one land (NaN) cell.

    zos = datum + tide signal, as in the real product (model mean ~ -0.25 m).
    """
    signal = tide_signal(times)
    data = np.repeat(signal[:, None, None], 2, axis=1).repeat(2, axis=2) + TIDE_DATUM_M
    data[:, 0, 0] = np.nan  # land
    ds = xr.Dataset(
        {"zos": (["time", "latitude", "longitude"], data)},
        coords={
            "time": times,
            "latitude": np.array([32.40, 32.50], dtype=np.float32),
            "longitude": np.array([-16.55, -16.45], dtype=np.float32),
        },
    )
    path = str(tmp_path / name)
    ds.to_netcdf(path)
    return path


def tide_series_via_buffers(env: Environment, times: pd.DatetimeIndex) -> np.ndarray:
    values = []
    for t in times:
        env.update_buffers(t)
        values.append(env.buffers["tide"])
    return np.array(values)


def assert_semidiurnal(tide: np.ndarray) -> None:
    """Dominant period 12–13 h and >= 50 crossings of the mean in 30 days."""
    x = tide - tide.mean()
    freqs = np.fft.rfftfreq(len(x), d=1.0)
    power = np.abs(np.fft.rfft(x)) ** 2
    dominant = 1 / freqs[power[1:].argmax() + 1]
    crossings = int(((x[:-1] < 0) != (x[1:] < 0)).sum())
    assert 12.0 <= dominant <= 13.0, f"dominant period {dominant:.1f} h, expected 12–13 h"
    assert crossings >= 50, f"{crossings} mean crossings in 30 days, expected >= 50"


HOURS_30D = pd.date_range("2026-03-01", periods=30 * 24, freq="h")

# ─── TESTS ───────────────────────────────────────────────────────────────────


class TestTideFromZos:
    def test_tide_is_metres_above_datum_not_normalised(self, tmp_path):
        """buffers['tide'] = zos - datum, in metres: no per-file min–max scaling."""
        env = Environment()
        env.load_data([write_zos(tmp_path, HOURS_30D)])

        tide = tide_series_via_buffers(env, HOURS_30D[:48])

        np.testing.assert_allclose(tide, tide_signal(HOURS_30D)[:48], atol=1e-6)
        assert env.tide_source == "ibi_zos"
        assert tide.min() < -0.5 and tide.max() > 0.5, "metres, not squeezed into [0, 1]"

    def test_tide_is_semidiurnal(self, tmp_path):
        env = Environment()
        env.load_data([write_zos(tmp_path, HOURS_30D)])

        assert_semidiurnal(tide_series_via_buffers(env, HOURS_30D))

    @pytest.mark.skipif(not REAL_SSH_FILE.exists(), reason=f"{REAL_SSH_FILE} not downloaded")
    def test_real_ibi_zos_tide_is_semidiurnal(self):
        """The downloaded IBI product itself carries the tide at the Desertas."""
        env = Environment()
        env.load_data([str(REAL_SSH_FILE)])

        assert_semidiurnal(tide_series_via_buffers(env, HOURS_30D))

    def test_time_outside_file_raises_instead_of_wrapping(self, tmp_path):
        env = Environment()
        env.load_data([write_zos(tmp_path, HOURS_30D)])

        with pytest.raises(TideDataError, match="No tide at"):
            env.update_buffers(HOURS_30D[-1] + pd.Timedelta(hours=1))

    def test_daily_zos_rejected(self, tmp_path):
        daily = pd.date_range("2026-03-01", periods=30, freq="D")
        env = Environment()

        with pytest.raises(TideDataError, match="hourly"):
            env.load_data([write_zos(tmp_path, daily)])


class TestNoSilentFallback:
    def test_no_tide_source_raises(self):
        env = Environment()

        with pytest.raises(TideDataError, match="No tide source"):
            env.update_buffers("2026-03-01 06:00")

    def test_sla_file_rejected(self, tmp_path):
        """DUACS SLA is de-tided daily altimetry; loading it must fail loudly."""
        days = pd.date_range("2024-01-01", periods=3, freq="D")
        ds = xr.Dataset(
            {"sla": (["time", "latitude", "longitude"], np.zeros((3, 2, 2)))},
            coords={"time": days, "latitude": [32.4, 32.5], "longitude": [-16.55, -16.45]},
        )
        path = str(tmp_path / "tidal.nc")
        ds.to_netcdf(path)

        with pytest.raises(TideDataError, match="not a tide"):
            Environment().load_data([path])

    def test_synthetic_tide_is_opt_in_and_matches_old_sine_crossings(self):
        """The opt-in sine crosses +/-0.30 m exactly where the old one crossed 0.70/0.30."""
        env = Environment(synthetic_tide=True)
        tide = tide_series_via_buffers(env, HOURS_30D)
        hours = HOURS_30D.to_numpy().astype("datetime64[ns]").astype(np.int64) / (1e9 * 3600)
        old = 0.5 * (1 + np.sin(2 * np.pi * hours / 12.4))

        assert env.tide_source == "synthetic_sine"
        assert np.abs(tide).max() == pytest.approx(SYNTHETIC_TIDE_AMPLITUDE_M, abs=0.01)
        np.testing.assert_array_equal(tide > 0.30, old > 0.70)
        np.testing.assert_array_equal(tide < -0.30, old < 0.30)
        assert_semidiurnal(tide)
