import numpy as np
from typing import Dict, Any

def query_env_buffers(lat: float, lon: float, buffers: Dict) -> Dict[str, Any]:
    """
    Stateless query of environment buffers.
    buffers format: {
        var_name: {
            'data': np.array,
            'lat_min': float, 'lat_step': float,
            'lon_min': float, 'lon_step': float,
            'shape': tuple
        }
    }
    """
    result = {
        'swh': 0.0, 'chl': None, 'temp': 18.0, 
        'uo': 0.0, 'vo': 0.0, 'is_land': False,
        'hsi': 0.0, 'depth': None
    }
    
    land_votes = []
    original_depth_is_nan = False  # Track if original bathymetry was NaN
    
    for key, buf in buffers.items():
        try:
            # Fast Nearest Neighbor Index
            r_idx = int(round((lat - buf['lat_min']) / buf['lat_step']))
            c_idx = int(round((lon - buf['lon_min']) / buf['lon_step']))
            
            rows, cols = buf['shape']
            
            # IMPROVED LAND DETECTION: Check neighborhood to distinguish coastline from open water
            # Coastline cells have NaN but are surrounded by water
            # True land (islands) have NaN and are surrounded by more NaN cells
            if key == 'depth':
                # Check if ORIGINAL position (before clamping) is within bounds
                if 0 <= r_idx < rows and 0 <= c_idx < cols:
                    val_unclamped = buf['data'][r_idx, c_idx]
                    original_depth_is_nan = np.isnan(val_unclamped)
                    
                    # If NaN, check surrounding cells to determine if it's coastline or true land
                    if original_depth_is_nan:
                        # Count NaN cells in 3x3 neighborhood
                        nan_count = 0
                        total_count = 0
                        for dr in [-1, 0, 1]:
                            for dc in [-1, 0, 1]:
                                nr, nc = r_idx + dr, c_idx + dc
                                if 0 <= nr < rows and 0 <= nc < cols:
                                    total_count += 1
                                    if np.isnan(buf['data'][nr, nc]):
                                        nan_count += 1
                        
                        # If less than 50% of neighbors are NaN, it's likely a coastline cell (edge of land)
                        # Treat it as water for navigation purposes
                        if total_count > 0 and nan_count / total_count < 0.5:
                            original_depth_is_nan = False  # Coastline - treat as water
                else:
                    # Position is out of bounds - not land, just off the map
                    original_depth_is_nan = False
                
                # NOW clamp for depth inference (to avoid "void" panic)
                r_idx = max(0, min(r_idx, rows - 1))
                c_idx = max(0, min(c_idx, cols - 1))
                 
            # Standard bounds check for other variables
            if 0 <= r_idx < rows and 0 <= c_idx < cols:
                val = buf['data'][r_idx, c_idx]
                
                # Handling NaNs
                if np.isnan(val):
                    # User Request: Infer depth for Holes?
                    if key == 'depth':
                         # Search spiral/radius for valid depth FOR NAVIGATION
                         # Land detection already done above using unclamped position
                         found_depth: float | None = None
                         for radius in range(1, 4): # Check 3 layers (approx 3-9km)
                             if found_depth is not None: break
                             for dr in range(-radius, radius+1):
                                 for dc in range(-radius, radius+1):
                                     nr, nc = r_idx + dr, c_idx + dc
                                     if 0 <= nr < rows and 0 <= nc < cols:
                                         v = buf['data'][nr, nc]
                                         if not np.isnan(v):
                                             found_depth = float(v)
                                             break
                                             
                         if found_depth is not None:
                              result[key] = found_depth
                         # Else leave as None (will be 9999 in defaults)
                else:
                    result[key] = float(val)
        except Exception:
            pass
            
    # Land Logic: Use ORIGINAL bathymetry NaN to determine land
    # Key insight: If original depth was NaN, it's land (island shape from data)
    # Even if we inferred a depth from nearby water for navigation purposes
    if 'depth' in buffers:
        if original_depth_is_nan:
            result['is_land'] = True
            # COASTLINE DETECTION: If we have inferred depth but original was NaN, it's a coastline cell
            # These cells are problematic for seals - they appear navigable but are actually land
            if result.get('depth') is not None and result.get('depth') < 9999:
                result['is_coastline'] = True
            else:
                result['is_coastline'] = False
        else:
            result['is_land'] = False
            result['is_coastline'] = False
        
    # HSI Logic
    # Simple calculation based on extracted Chl
    chl = result.get('chl')
    if chl is None:
        chl = 0.0
    result['hsi'] = min(chl / 0.5, 1.0)
    
    return result
