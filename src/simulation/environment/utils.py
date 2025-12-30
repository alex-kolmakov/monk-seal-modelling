import numpy as np
from typing import Dict

def query_env_buffers(lat: float, lon: float, buffers: Dict) -> Dict[str, float]:
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
        'swh': 0.0, 'chl': 0.05, 'temp': 18.0, 
        'uo': 0.0, 'vo': 0.0, 'is_land': False,
        'hsi': 0.0
    }
    
    land_votes = []
    
    for key, buf in buffers.items():
        try:
            # Fast Nearest Neighbor Index
            r_idx = int(round((lat - buf['lat_min']) / buf['lat_step']))
            c_idx = int(round((lon - buf['lon_min']) / buf['lon_step']))
            
            # Bounds check
            if 0 <= r_idx < buf['shape'][0] and 0 <= c_idx < buf['shape'][1]:
                val = buf['data'][r_idx, c_idx]
                
                if np.isnan(val):
                    if key == 'temp':
                        land_votes.append(True)
                else:
                    result[key] = float(val)
                    if key == 'temp':
                        land_votes.append(False)
        except Exception:
            pass
            
    # Land Logic
    if 'temp' in buffers and any(land_votes):
        result['is_land'] = True
        
    # HSI Logic
    # Simple calculation based on extracted Chl
    chl = result.get('chl', 0.0)
    result['hsi'] = min(chl / 0.5, 1.0)
    
    return result
