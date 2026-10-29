"""EMODnet bathymetry replaces the depth map the seals navigate and forage on.

Run: uv run pytest tests/unit/test_bathymetry.py -v
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from src.simulation.environment.bathymetry import load_emodnet_bathymetry, to_depth_map
from src.simulation.environment.environment import Environment, EnvironmentDataError
from src.simulation.environment.utils import query_env_buffers

LATS = np.linspace(32.0, 33.0, 21)
LONS = np.linspace(-17.0, -16.0, 21)


def _elevation(lats=LATS, lons=LONS) -> xr.DataArray:
    """Open sea 80 m deep with an island (+50 m) in the middle."""
    grid = np.full((lats.size, lons.size), -80.0, dtype="float32")
    grid[8:13, 8:13] = 50.0
    return xr.DataArray(
        grid, dims=("lat", "lon"), coords={"lat": lats, "lon": lons}, name="elevation"
    )


def _write(tmp_path, elevation: xr.DataArray, name: str = "bathy.nc") -> str:
    path = tmp_path / name
    elevation.to_dataset().to_netcdf(path)
    return str(path)


def _write_chl(tmp_path, lats=LATS, lons=LONS) -> str:
    """A minimal Copernicus-style file on the model grid."""
    time = np.array(["2026-01-01T00", "2026-01-02T00"], dtype="datetime64[h]")
    chl = xr.DataArray(
        np.full((2, lats.size, lons.size), 0.3, dtype="float32"),
        dims=("time", "lat", "lon"),
        coords={"time": time, "lat": lats, "lon": lons},
        name="chl",
    )
    path = tmp_path / "bgc.nc"
    chl.to_dataset().to_netcdf(path)
    return str(path)


def test_depth_is_positive_and_land_is_nan():
    depth = to_depth_map(_elevation())
    assert float(depth.sel(lat=32.05, lon=-16.95)) == 80.0
    assert np.isnan(depth.sel(lat=32.5, lon=-16.5))


def test_dry_cell_at_zero_elevation_is_not_sea():
    elevation = _elevation()
    elevation[0, 0] = 0.0
    assert np.isnan(to_depth_map(elevation)[0, 0])


def test_latitude_is_made_ascending():
    """A GeoTIFF has north first; the model's grid lookup wants south first."""
    north_first = _elevation().isel(lat=slice(None, None, -1))
    depth = to_depth_map(north_first)
    assert (np.diff(depth.lat.values) > 0).all()
    assert np.isnan(depth.sel(lat=32.5, lon=-16.5))


def test_loader_reads_a_netcdf(tmp_path):
    depth = load_emodnet_bathymetry(_write(tmp_path, _elevation()))
    assert depth.dims == ("lat", "lon")
    assert float(depth.max()) == 80.0


def test_loader_rejects_a_file_without_elevation(tmp_path):
    path = tmp_path / "wrong.nc"
    xr.Dataset({"depth": _elevation().rename("depth")}).to_netcdf(path)
    with pytest.raises(ValueError, match="elevation"):
        load_emodnet_bathymetry(str(path))


def test_environment_uses_the_file_as_sea_floor(tmp_path):
    env = Environment(synthetic_tide=True)
    env.load_data([_write_chl(tmp_path)], bathymetry_file=_write(tmp_path, _elevation()))
    env.update_buffers("2026-01-01 00:00")
    sea = query_env_buffers(32.1, -16.9, env.buffers)
    island = query_env_buffers(32.5, -16.5, env.buffers)
    assert sea["depth"] == 80.0 and not sea["is_land"]
    assert island["is_land"]


def test_environment_refuses_a_bathymetry_that_does_not_cover_the_data(tmp_path):
    small = _elevation(LATS[:10], LONS)
    env = Environment()
    with pytest.raises(EnvironmentDataError, match="latitude"):
        env.load_data([_write_chl(tmp_path)], bathymetry_file=_write(tmp_path, small))


def test_environment_refuses_an_unreadable_bathymetry(tmp_path):
    env = Environment()
    with pytest.raises(EnvironmentDataError, match="Cannot read bathymetry"):
        env.load_data([_write_chl(tmp_path)], bathymetry_file=str(tmp_path / "missing.nc"))
