import logging

import numpy as np
import pandas as pd
import xarray as xr

from .utils import navigation_grids, query_env_buffers

# Configure sorting
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tide = IBI hourly sea surface height (zos, metres) averaged over the colony box,
# measured from a fixed datum. zos is tidal (a separate *_detided product exists);
# its Desertas mean is -0.23 m (Mar 2024) / -0.27 m (Jan-May 2026), so -0.25 m is
# used as mean sea level. A fixed datum keeps thresholds comparable between runs.
TIDE_VARIABLE = "zos"
TIDE_DATUM_M = -0.25
DESERTAS_BOX = {"lat": (32.35, 32.60), "lon": (-16.60, -16.40)}

# Synthetic tide for tests and offline runs: a 12.4 h sine in metres.
# 0.75 m ~ the M2 amplitude at Madeira; with the default +/-0.30 m thresholds it
# crosses at sin = +/-0.4, the same points as the old normalised 0.70/0.30 sine.
SYNTHETIC_TIDE_AMPLITUDE_M = 0.75
SYNTHETIC_TIDE_PERIOD_H = 12.4

# Daily de-tided altimetry was used as "tide" before; refuse it explicitly.
NOT_A_TIDE_VARIABLES = ("sla", "adt")


class EnvironmentDataError(RuntimeError):
    """An input file is unreadable, irregular, or does not cover the requested time."""


class TideDataError(EnvironmentDataError):
    """The tide source is missing, invalid, or does not cover the requested time."""


def _regular_grid(ds: xr.Dataset, fp: str) -> xr.Dataset:
    """Ascending, evenly spaced lat/lon, as the index arithmetic in query_env_buffers assumes."""
    for coord in ("lat", "lon"):
        if coord not in ds.coords or ds[coord].size < 2:
            continue
        step = np.diff(ds[coord].values)
        if (step < 0).all():
            logger.info(f"{fp}: {coord} is descending; sorting ascending")
            ds = ds.sortby(coord)
            step = np.diff(ds[coord].values)
        if not (step > 0).all():
            raise EnvironmentDataError(f"{fp}: {coord} is not monotonic")
        if not np.allclose(step, step[0], rtol=1e-3):
            raise EnvironmentDataError(f"{fp}: {coord} spacing is not uniform")
    return ds


class Environment:
    """
    Environment handler using Xarray for Copernicus Marine Data.
    Handles loading NetCDF files, spatial interpolation, and HSI calculation.

    Args:
        synthetic_tide: Allow the synthetic sine tide when no zos file is loaded.
            Without it, update_buffers() raises instead of silently faking the tide.
        allow_time_wrap: Replay a dataset from its start when the run goes past its end.
            Without it, a time outside a dataset raises EnvironmentDataError.
    """

    def __init__(self, synthetic_tide: bool = False, allow_time_wrap: bool = False):
        self.datasets: list[xr.Dataset] = []

        # Fallback defaults
        self.defaults = {
            "swh": 0.0,
            "chl": 0.05,
            "temp": 18.0,
            "uo": 0.0,
            "vo": 0.0,
            "is_land": False,
        }

        # Variable mapping: Internal Name -> Possible Copernicus Names
        self.var_map = {
            "swh": ["VHM0", "VAVH", "swh", "significant_wave_height"],
            "chl": ["CHL", "chl", "mass_concentration_of_chlorophyll_a_in_sea_water"],
            "temp": ["thetao", "temp", "sst", "sea_surface_temperature"],
            "uo": ["uo", "eastward_sea_water_velocity"],
            "vo": ["vo", "northward_sea_water_velocity"],
        }

        # Optimization Buffers
        self.current_time = None
        self.buffers = {}  # {var_name: (values_2d, lats, lons)} or similar
        # Ideally, we align all buffers to a single grid, but data might differ.
        # We will store: {internal_key: {'data': np.array, 'lat': np.array, 'lon': np.array}}

        # Static bathymetry (set in load_data)
        self.bathymetry_map = None

        # Tide height series in metres above TIDE_DATUM_M (set in load_data from zos)
        self.synthetic_tide = synthetic_tide
        self.tide_series: pd.Series | None = None
        self.tide_file: str | None = None

        self.allow_time_wrap = allow_time_wrap
        self._warned_missing: set[str] = set()
        # Per-variable numpy views built once in load_data (see _build_fields)
        self._fields: dict[str, dict] = {}
        self._depth_buffer: dict | None = None

    @property
    def tide_source(self) -> str:
        """Where buffers['tide'] comes from, for run metadata."""
        if self.tide_series is not None:
            return f"ibi_{TIDE_VARIABLE}"
        return "synthetic_sine" if self.synthetic_tide else "none"

    def load_data(self, file_paths: list[str]):
        """Load multiple NetCDF files."""
        logger.info(f"Loading environment data from {len(file_paths)} files...")
        self.datasets = []
        self.bathymetry_map = None
        self.tide_series = None
        self.tide_file = None

        for fp in file_paths:
            try:
                ds = xr.open_dataset(fp)
                rename_dict = {}
                for coord in ds.coords:
                    if str(coord).lower() in ["latitude"]:
                        rename_dict[coord] = "lat"
                    elif str(coord).lower() in ["longitude"]:
                        rename_dict[coord] = "lon"
                if rename_dict:
                    ds = ds.rename(rename_dict)
                ds = _regular_grid(ds, fp)

                # Check for Depth/Thetao to compute Bathymetry
                if "depth" in ds.dims and ("thetao" in ds.data_vars or "thetao" in ds.keys()):
                    logger.info(f"Found depth info in {fp}, computing bathymetry map...")
                    # Use first time step to check valid depths
                    # Max Valid Depth = Depth where thetao is not null
                    # Note: Lazy loading might make this slow? Validating...
                    try:
                        # Find deepest depth with valid data for each pixel
                        # max_depth = ds.depth.where(valid_mask).max(dim='depth')
                        # Just getting it into memory to avoid repeated heavy I/O
                        # It's a 2D map, small size (47x871).
                        sample_slice = ds["thetao"].isel(time=0)
                        valid_mask = sample_slice.notnull()
                        self.bathymetry_map = (
                            ds["depth"].where(valid_mask).max(dim="depth").compute()
                        )
                        logger.info("Bathymetry map computed successfully.")
                    except Exception as e:
                        raise EnvironmentDataError(f"{fp}: cannot compute bathymetry: {e}") from e

                if TIDE_VARIABLE in ds.data_vars:
                    self._load_tide(ds, fp)
                    continue
                not_tides = [v for v in NOT_A_TIDE_VARIABLES if v in ds.data_vars]
                if not_tides:
                    raise TideDataError(
                        f"{fp} holds {not_tides}: daily altimetry with the tide removed, "
                        f"not a tide. Load IBI hourly '{TIDE_VARIABLE}' instead."
                    )

                # Agents only ever read the surface level: keep it, in memory, once,
                # instead of re-reading every depth level from disk each hourly step.
                if "depth" in ds.dims:
                    ds = ds.isel(depth=0)
                self.datasets.append(ds.load())
                logger.info(f"Loaded {fp}")
            except EnvironmentDataError:
                raise
            except Exception as e:
                raise EnvironmentDataError(f"Failed to load {fp}: {e}") from e

        self._build_fields()

    def _build_fields(self):
        """Extract each buffered variable once as numpy (time first) with its time index,
        so update_buffers is an index lookup per hour instead of an xarray selection."""
        self._fields = {}
        for int_key in set(self.defaults) - {"is_land"}:
            for ds in self.datasets:
                name = next((n for n in self.var_map.get(int_key, []) if n in ds), None)
                if name is None:
                    continue
                da = ds[name]
                has_time = "time" in da.dims
                data = da.values
                if has_time:
                    data = np.moveaxis(data, da.get_axis_num("time"), 0)
                self._fields[int_key] = {
                    "name": name,
                    "data": data,
                    "times": pd.DatetimeIndex(da.time.values) if has_time else None,
                    # native time step, for the coverage check in _time_index
                    "step": pd.Timedelta(int(np.median(np.diff(da.time.values.astype("int64")))))
                    if has_time and da.time.size > 1
                    else None,
                    "lats": da.lat.values,
                    "lons": da.lon.values,
                }
                break

        self._depth_buffer = None
        if self.bathymetry_map is not None:
            bm = self.bathymetry_map
            self._depth_buffer = {
                "data": bm.values,
                "lat_min": bm.lat.min().item(),
                "lat_step": (bm.lat.max() - bm.lat.min()).item() / (bm.lat.size - 1)
                if bm.lat.size > 1
                else 1.0,
                "lon_min": bm.lon.min().item(),
                "lon_step": (bm.lon.max() - bm.lon.min()).item() / (bm.lon.size - 1)
                if bm.lon.size > 1
                else 1.0,
                "shape": bm.shape,
            }
            land, filled = navigation_grids(bm.values)
            self._depth_buffer["land"] = land
            self._depth_buffer["filled"] = filled

    def _load_tide(self, ds: xr.Dataset, fp: str):
        """Reduce hourly zos to a colony-mean height series in metres above the datum."""
        if self.tide_series is not None:
            raise TideDataError(f"Second tide file {fp}; already loaded {self.tide_file}")
        (lat0, lat1), (lon0, lon1) = DESERTAS_BOX["lat"], DESERTAS_BOX["lon"]
        box = ds[TIDE_VARIABLE].sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
        series = box.mean(dim=["lat", "lon"], skipna=True).to_series() - TIDE_DATUM_M
        if series.isna().any() or len(series) < 2:
            raise TideDataError(f"{fp}: no valid {TIDE_VARIABLE} in the Desertas box")
        step = pd.Series(series.index).diff().dropna().unique()
        if len(step) != 1 or step[0] != pd.Timedelta(hours=1):
            raise TideDataError(f"{fp}: {TIDE_VARIABLE} must be hourly, got steps {step}")
        self.tide_series = series
        self.tide_file = fp
        logger.info(
            f"Tide: {TIDE_VARIABLE} from {fp}, {series.index[0]} -> {series.index[-1]}, "
            f"{series.min():+.2f} .. {series.max():+.2f} m above {TIDE_DATUM_M} m datum"
        )

    def _tide_at(self, time: pd.Timestamp | str) -> float:
        """Tide height (m above datum) at an hourly timestamp. Never wraps or clamps."""
        t = pd.Timestamp(time)
        if self.tide_series is not None:
            idx = self.tide_series.index.get_indexer(
                pd.DatetimeIndex([t]), method="nearest", tolerance=pd.Timedelta(minutes=30)
            )[0]
            if idx < 0:
                raise TideDataError(
                    f"No tide at {t}: {self.tide_file} covers "
                    f"{self.tide_series.index[0]} -> {self.tide_series.index[-1]}"
                )
            return float(self.tide_series.iloc[idx])
        if self.synthetic_tide:
            hours = t.value / (1e9 * 3600)
            phase = 2 * np.pi * hours / SYNTHETIC_TIDE_PERIOD_H
            return float(SYNTHETIC_TIDE_AMPLITUDE_M * np.sin(phase))
        raise TideDataError(
            f"No tide source: load an IBI hourly '{TIDE_VARIABLE}' file "
            "or construct Environment(synthetic_tide=True)"
        )

    def _time_index(self, field: dict, time: pd.Timestamp | str) -> int:
        """Index of the step nearest `time` (as xarray's sel(method="nearest")). Outside the
        data (more than one native step past either end) it raises, or replays from the
        start with allow_time_wrap."""
        times: pd.DatetimeIndex = field["times"]
        if len(times) < 2:
            return 0
        step = field["step"]
        t = pd.Timestamp(time)
        if not times[0] - step <= t <= times[-1] + step:
            if not self.allow_time_wrap:
                raise EnvironmentDataError(
                    f"No '{field['name']}' at {t}: data covers {times[0]} -> {times[-1]} "
                    "(pass allow_time_wrap / --allow-time-wrap to replay it)"
                )
            t = times[0] + (t - times[0]) % (times[-1] - times[0])
        return int(times.get_indexer(pd.DatetimeIndex([t]), method="nearest")[0])

    def update_buffers(self, time: pd.Timestamp | str):
        """Pre-fetch data for the current timestamp into numpy arrays."""
        if self.current_time == time:
            return

        self.current_time = time
        self.buffers = {}

        for int_key in sorted(set(self.defaults) - {"is_land"}):
            field = self._fields.get(int_key)
            if field is None:
                if int_key not in self._warned_missing:
                    self._warned_missing.add(int_key)
                    logger.warning(f"No loaded dataset has '{int_key}'; agents read it as None")
                continue
            data = field["data"]
            if field["times"] is not None:
                data = data[self._time_index(field, time)]
            lats, lons = field["lats"], field["lons"]
            self.buffers[int_key] = {
                "data": data,
                "lats": lats,
                "lons": lons,
                # Pre-computed resolution for fast index mapping
                "lat_min": lats.min(),
                "lat_step": lats[1] - lats[0] if len(lats) > 1 else 1.0,
                "lon_min": lons.min(),
                "lon_step": lons[1] - lons[0] if len(lons) > 1 else 1.0,
                "shape": data.shape,
            }

        # Static bathymetry, built once in _build_fields
        if self._depth_buffer is not None:
            self.buffers["depth"] = self._depth_buffer

        # Tide: metres above TIDE_DATUM_M (scalar, colony-wide)
        self.buffers["tide"] = self._tide_at(self.current_time)

    def get_data_at_pos(
        self, lat: float, lon: float, time: pd.Timestamp | str | None = None
    ) -> dict[str, float]:
        """Fast lookup from buffers."""
        # Ensure buffers are up to date
        if time is not None and time != self.current_time:
            self.update_buffers(time)

        # Delegate to stateless util
        data = query_env_buffers(lat, lon, self.buffers)

        if time:
             # If time provided, we might be out of sync with buffers["tide"]?
             # But get_data_at_pos forces update_buffers(time) if different.
             # So buffers["tide"] is correct.
             pass

        # Retrieve tide from buffers/utils
        # (utils.query_env_buffers will retrieve it)
        # data["tide"] is already in data from query_env_buffers (see next step)
        pass

        return data
