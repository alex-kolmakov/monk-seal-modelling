"""Download EMODnet bathymetry for the Madeira download box.

    uv run python -m src.data_ingestion.download_bathymetry

Writes data/real_long/bathymetry_emodnet.nc (elevation in metres, negative = sea) on a grid of
1/240 degree, about 0.4 km. Pass it to the model with `run_real_long --emodnet-bathymetry`.
"""

import argparse
import io
import logging
import urllib.request
from pathlib import Path

import numpy as np
import xarray as xr
from PIL import Image

logger = logging.getLogger(__name__)

# Same box as the Copernicus downloads, so the seals never leave the bathymetry
LAT_MIN, LAT_MAX = 32.2, 33.5
LON_MIN, LON_MAX = -17.5, -16.0
CELLS_PER_DEGREE = 240
WCS_URL = "https://ows.emodnet-bathymetry.eu/wcs"
DEFAULT_OUT = Path("data/real_long/bathymetry_emodnet.nc")


def fetch_elevation(
    lat_min: float = LAT_MIN,
    lat_max: float = LAT_MAX,
    lon_min: float = LON_MIN,
    lon_max: float = LON_MAX,
    cells_per_degree: int = CELLS_PER_DEGREE,
) -> xr.DataArray:
    """EMODnet mean elevation (m, negative at sea) for a box, latitude ascending."""
    width = round((lon_max - lon_min) * cells_per_degree)
    height = round((lat_max - lat_min) * cells_per_degree)
    url = (
        f"{WCS_URL}?service=WCS&version=1.0.0&request=GetCoverage&coverage=emodnet:mean"
        f"&crs=EPSG:4326&BBOX={lon_min},{lat_min},{lon_max},{lat_max}"
        f"&WIDTH={width}&HEIGHT={height}&FORMAT=GeoTIFF"
    )
    logger.info(f"Fetching EMODnet bathymetry {width}x{height} cells")
    with urllib.request.urlopen(url, timeout=300) as resp:
        grid = np.array(Image.open(io.BytesIO(resp.read())), dtype="float32")
    if grid.shape != (height, width):
        raise RuntimeError(f"EMODnet returned {grid.shape}, expected {(height, width)}")
    dlat, dlon = (lat_max - lat_min) / height, (lon_max - lon_min) / width
    # GeoTIFF row 0 is the north edge; cell centres, latitude ascending
    lats = lat_min + dlat * (np.arange(height) + 0.5)
    lons = lon_min + dlon * (np.arange(width) + 0.5)
    return xr.DataArray(
        grid[::-1],
        dims=("lat", "lon"),
        coords={"lat": lats, "lon": lons},
        name="elevation",
        attrs={"units": "m", "source": "EMODnet Bathymetry DTM (mean), negative = sea"},
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    elevation = fetch_elevation()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    elevation.to_dataset().to_netcdf(args.out)
    sea = float((elevation < 0).mean())
    logger.info(f"Wrote {args.out}: {sea:.0%} of cells are sea")


if __name__ == "__main__":
    main()
