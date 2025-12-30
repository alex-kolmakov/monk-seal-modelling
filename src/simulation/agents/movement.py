import numpy as np
import math

def correlated_random_walk(
    data_in, 
    # data_in is dummy here, usually we'd need current_pos, current_heading
    # But for a functional approach let's define args explicitly
    current_pos: tuple,
    current_heading: float,
    speed: float = 0.5, # km or degrees per step? Let's assume degrees approx for now or convert.
                        # 1 deg lat ~ 111km. 50km foraging -> 0.5 degrees roughly.
                        # Let's use small steps: 0.01 degrees (~1km)
    tortuosity: float = 0.8, # 1.0 = straight line, 0.0 = random
    bias_pos: tuple = None,
    bias_strength: float = 0.0
) -> tuple:
    """
    Calculates next position using Correlated Random Walk.
    Returns (new_pos_lat, new_pos_lon, new_heading)
    """
    lat, lon = current_pos
    
    # 1. Random Turn
    # Von Mises distribution for directional persistence
    # concentration (kappa) ~ tortuosity
    kappa = tortuosity * 10
    turn_angle = np.random.vonmises(0, kappa) 
    
    # 2. Apply Turn to Heading
    new_heading = current_heading + turn_angle
    
    # 3. Bias (e.g. towards haulout or food) - Simple vector addition
    if bias_pos:
        target_lat, target_lon = bias_pos
        # Vector to target
        dy = target_lat - lat
        dx = target_lon - lon
        target_heading = math.atan2(dy, dx)
        
        # Mix headings based on bias_strength
        # This is a naive mixing: weighted average of vectors
        # Better: new_heading = arg( (1-w)*exp(i*theta) + w*exp(i*target) )
        
        # Simple Approach: Linear Interpolation of angle (be careful of wrap around)
        # Actually, let's just nudge the heading towards target
        diff = target_heading - new_heading
        # Normalize to -pi, pi
        diff = (diff + np.pi) % (2 * np.pi) - np.pi
        
        new_heading += diff * bias_strength

    # 4. Move
    # Step size in degrees (approx)
    step_size = 0.01 # ~1.1km
    
    new_lat = lat + step_size * math.sin(new_heading)
    new_lon = lon + step_size * math.cos(new_heading)
    
    return (new_lat, new_lon), new_heading
