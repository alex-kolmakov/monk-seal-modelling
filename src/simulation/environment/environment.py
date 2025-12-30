import xarray as xr
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Environment:
    """
    Environment handler using Xarray for Copernicus Marine Data.
    Handles loading NetCDF files, spatial interpolation, and HSI calculation.
    """
    def __init__(self):
        self.datasets: List[xr.Dataset] = []
        
        # Fallback defaults
        self.defaults = {
            'swh': 0.0, 'chl': 0.05, 'temp': 18.0, 'uo': 0.0, 'vo': 0.0, 'is_land': False
        }
        
        # Variable mapping: Internal Name -> Possible Copernicus Names
        self.var_map = {
            'swh': ['VHM0', 'VAVH', 'swh', 'significant_wave_height'],
            'chl': ['CHL', 'chl', 'mass_concentration_of_chlorophyll_a_in_sea_water'],
            'temp': ['thetao', 'temp', 'sst', 'sea_surface_temperature'],
            'uo': ['uo', 'eastward_sea_water_velocity'],
            'vo': ['vo', 'northward_sea_water_velocity']
        }
        
        # Optimization Buffers
        self.current_time = None
        self.buffers = {} # {var_name: (values_2d, lats, lons)} or similar
        # Ideally, we align all buffers to a single grid, but data might differ.
        # We will store: {internal_key: {'data': np.array, 'lat': np.array, 'lon': np.array}}

    def load_data(self, file_paths: List[str]):
        """Load multiple NetCDF files."""
        logger.info(f"Loading environment data from {len(file_paths)} files...")
        self.datasets = []
        for fp in file_paths:
            try:
                ds = xr.open_dataset(fp)
                rename_dict = {}
                for coord in ds.coords:
                    if coord.lower() in ['latitude']: rename_dict[coord] = 'lat'
                    elif coord.lower() in ['longitude']: rename_dict[coord] = 'lon'
                if rename_dict: ds = ds.rename(rename_dict)
                # ds.load() <--- Removed to prevent OOM (Lazy Loading)
                self.datasets.append(ds)
                logger.info(f"Loaded {fp}")
            except Exception as e:
                logger.error(f"Failed to load {fp}: {e}")

    def update_buffers(self, time: Union[pd.Timestamp, str]):
        """Pre-fetch data for the current timestamp into numpy arrays."""
        if self.current_time == time:
            return
            
        self.current_time = time
        self.buffers = {}
        
        # Iterate over internal variables we need (keys of defaults)
        targets = set(self.defaults.keys()) - {'is_land'}
        
        for int_key in targets:
            possible_names = self.var_map.get(int_key, [])
            found = False
            for ds in self.datasets:
                for name in possible_names:
                    if name in ds:
                        try:
                            # Select time (Looping Logic)
                            # If requested time is outside dataset capacity, modulo it
                            if 'time' in ds.dims:
                                t_min = ds.time.min().values
                                t_max = ds.time.max().values
                                dt_range = t_max - t_min
                                if hasattr(dt_range, 'astype'): # numpy timedelta
                                    range_ns = dt_range.astype('timedelta64[ns]').astype(int)
                                    if range_ns > 0:
                                        # Offset requested time to be relative to t_min, then modulo
                                        t_req = pd.Timestamp(time).value
                                        t_start = pd.Timestamp(t_min).value
                                        offset = (t_req - t_start) % range_ns
                                        mapped_time = pd.Timestamp(t_start + offset)
                                        ds_t = ds.sel(time=mapped_time, method='nearest')
                                    else:
                                        ds_t = ds.isel(time=0)
                                else:
                                    # Fallback
                                    ds_t = ds.sel(time=time, method='nearest')
                            else:
                                ds_t = ds
                                
                            # Depth
                            if 'depth' in ds_t.dims:
                                ds_t = ds_t.isel(depth=0)
                                
                            # Extract Data
                            data = ds_t[name].values
                            lats = ds[name].lat.values
                            lons = ds[name].lon.values
                            
                            # Replace NaNs with unique value if needed, but we need NaNs for land mask
                            # Store
                            self.buffers[int_key] = {
                                'data': data,
                                'lats': lats,
                                'lons': lons,
                                # Pre-compute resolution for fast index mapping
                                'lat_min': lats.min(),
                                'lat_step': lats[1] - lats[0] if len(lats) > 1 else 1.0,
                                'lon_min': lons.min(),
                                'lon_step': lons[1] - lons[0] if len(lons) > 1 else 1.0,
                                'shape': data.shape
                            }
                            found = True
                            break
                        except Exception as e:
                            # logger.warning(f"Error buffering {name}: {e}")
                            pass
                if found: break
                
    def get_data_at_pos(self, lat: float, lon: float, time: Union[pd.Timestamp, str] = None) -> Dict[str, float]:
        """Fast lookup from buffers."""
        # Ensure buffers are up to date
        if time is not None and time != self.current_time:
            self.update_buffers(time)
            
        result = self.defaults.copy()
        result['is_land'] = False # default to False unless detected otherwise
        
        land_votes = []
        
        for key, buf in self.buffers.items():
            try:
                # Fast Nearest Neighbor Index
                # idx = (val - min) / step
                r_idx = int(round((lat - buf['lat_min']) / buf['lat_step']))
                c_idx = int(round((lon - buf['lon_min']) / buf['lon_step']))
                
                # Bounds check
                if 0 <= r_idx < buf['shape'][0] and 0 <= c_idx < buf['shape'][1]:
                    val = buf['data'][r_idx, c_idx]
                    
                    if np.isnan(val):
                        # If temperature is NaN, strong vote for land
                        if key == 'temp':
                            land_votes.append(True)
                    else:
                        result[key] = float(val)
                        if key == 'temp':
                            land_votes.append(False)
                else:
                    # Out of bounds
                    pass
            except Exception:
                pass
                
        # Land Logic: If temp was checked and is NaN -> Land
        # Or if we have data for 'swh' but checks say NaN?
        # Simplest: If temp is NaN, it's land.
        # Check if 'temp' key exists in buffers
        if 'temp' in self.buffers:
             # If we successfully updated 'temp', result['temp'] will be real val.
             # If result['temp'] is still default (18.0) AND we voted True?
             # My logic above: if not NaN, result[key] is updated.
             # So if result['temp'] == 18.0 (default) AND land_votes says True?
             # Wait, land_votes appends True if NaN.
             if any(land_votes):
                 result['is_land'] = True
        
        result['hsi'] = self.calculate_hsi(result)
        return result

    def calculate_hsi(self, features: Dict[str, float]) -> float:
        """
        Calculate Habitat Suitability Index (0.0 to 1.0).
        """
        chl = features.get('chl', 0.0)
        hsi = min(chl / 0.5, 1.0)
        return hsi
