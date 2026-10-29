"""EMODnet bathymetry as the sea floor the seals navigate and forage on.

The file is the NetCDF written by `src.data_ingestion.download_bathymetry`: elevation in metres
(negative = sea). The model wants the Copernicus convention instead: depth in metres, positive
down, NaN on land, latitude ascending.
"""

import numpy as np
import xarray as xr


def to_depth_map(elevation: xr.DataArray) -> xr.DataArray:
    """Elevation (m, negative at sea) to depth (m, positive, NaN where the cell is not sea)."""
    depth = (-elevation).where(elevation < 0)
    depth = depth.rename("depth").sortby("lat").sortby("lon")
    if depth.dims != ("lat", "lon"):
        depth = depth.transpose("lat", "lon")
    return depth


def load_emodnet_bathymetry(path: str) -> xr.DataArray:
    """Read an EMODnet bathymetry NetCDF as a depth map (positive metres, NaN on land)."""
    with xr.open_dataset(path) as ds:
        if "elevation" not in ds:
            raise ValueError(f"{path}: no 'elevation' variable (found {list(ds.data_vars)})")
        elevation = ds["elevation"].load()
    if not {"lat", "lon"} <= set(elevation.dims):
        raise ValueError(
            f"{path}: elevation must have lat and lon dimensions, has {elevation.dims}"
        )
    if not np.isfinite(elevation.values).any():
        raise ValueError(f"{path}: elevation holds no data")
    return to_depth_map(elevation)
