"""
Animate seal behavior over time.
Shows seal movement, behavioral states, and key metrics.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.animation import FFMpegWriter
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
from pathlib import Path

def create_bathymetry_map(physics):
    """Create bathymetry map showing depth from temperature data."""
    temp_data = physics['thetao'].isel(time=0)
    bathymetry = np.full((len(temp_data.latitude), len(temp_data.longitude)), np.nan)
    
    for i in range(len(temp_data.latitude)):
        for j in range(len(temp_data.longitude)):
            temp_profile = temp_data.isel(latitude=i, longitude=j).values
            valid_depths = physics.depth.values[~np.isnan(temp_profile)]
            if len(valid_depths) > 0:
                bathymetry[i, j] = valid_depths.max()
    
    return temp_data.latitude.values, temp_data.longitude.values, bathymetry

def load_seal_data(csv_file):
    """Load seal tracking data from CSV."""
    df = pd.read_csv(csv_file, parse_dates=['time'])
    df = df.rename(columns={'time': 'timestamp'})  # Rename for consistency
    return df

def create_seal_animation(seal_data, physics_file, output_file, fps=10):
    """
    Create animation of seal behavior.
    
    Args:
        seal_data: DataFrame with seal tracking data
        physics_file: Path to physics NetCDF for bathymetry
        output_file: Output video file path
        fps: Frames per second
    """
    # Load physics data for bathymetry
    print("Loading bathymetry from physics data...")
    physics = xr.open_dataset(physics_file)
    lat_bath, lon_bath, bathymetry = create_bathymetry_map(physics)
    physics.close()
    
    # Get coordinate bounds
    min_lat, max_lat = seal_data['lat'].min() - 0.2, seal_data['lat'].max() + 0.2
    min_lon, max_lon = seal_data['lon'].min() - 0.2, seal_data['lon'].max() + 0.2
    
    # State colors
    state_colors = {
        'FORAGING': '#2E86DE',      # Blue
        'HAULING_OUT': '#F39C12',   # Orange
        'SLEEPING': '#E74C3C',      # Red
        'RESTING': '#9B59B6',       # Purple
        'TRANSITING': '#1ABC9C'     # Teal
    }
    
    # Create figure
    fig = plt.figure(figsize=(16, 10))
    
    # Main map (left side, larger)
    ax_map = fig.add_subplot(1, 2, 1, projection=ccrs.PlateCarree())
    ax_map.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())
    
    # Plot bathymetry first (as background)
    bath_plot = ax_map.pcolormesh(lon_bath, lat_bath, bathymetry, 
                                  cmap='Blues_r', shading='auto',
                                  transform=ccrs.PlateCarree(), alpha=0.4,
                                  vmin=0, vmax=500)
    
    # Add map features on top
    ax_map.add_feature(cfeature.LAND, facecolor='#D2B48C', edgecolor='black', linewidth=0.8, alpha=0.7)
    ax_map.coastlines(resolution='10m', linewidth=1.0, color='black')
    # Gridlines handled later in layout section
    
    # Add colorbar for bathymetry - increased padding
    cbar = plt.colorbar(bath_plot, ax=ax_map, label='Depth (m)', shrink=0.7, pad=0.1)
    
    # Add title to map
    ax_map.set_title('Seal Movement Track', fontsize=14, fontweight='bold', pad=10)
    
    # Info panel (right side)
    ax_info = fig.add_subplot(1, 2, 2)
    ax_info.set_xlim(0, 1)
    ax_info.set_ylim(0, 1)
    ax_info.axis('off')
    
    # Initialize plot elements
    track_line, = ax_map.plot([], [], 'k-', linewidth=1, alpha=0.5, 
                              transform=ccrs.PlateCarree(), label='Track (24h)')
    seal_marker, = ax_map.plot([], [], 'o', markersize=12, 
                               transform=ccrs.PlateCarree(), label='Current Position')
    
    # Info text elements - Moved down to avoid top edge
    info_texts = {
        'title': ax_info.text(0.5, 0.98, '', ha='center', fontsize=20, fontweight='bold'),
        'date': ax_info.text(0.5, 0.92, '', ha='center', fontsize=16),
        'state': ax_info.text(0.1, 0.82, '', fontsize=14, fontweight='bold'),
        'depth': ax_info.text(0.1, 0.40, '', fontsize=12),
        'position': ax_info.text(0.1, 0.35, '', fontsize=10, family='monospace'),
    }
    
    # Energy bar - Moved up and resized
    energy_bar_bg = plt.Rectangle((0.1, 0.72), 0.8, 0.04, 
                                  facecolor='lightgray', edgecolor='black')
    energy_bar = plt.Rectangle((0.1, 0.72), 0.0, 0.04, 
                               facecolor='green', edgecolor='black')
    ax_info.add_patch(energy_bar_bg)
    ax_info.add_patch(energy_bar)
    ax_info.text(0.1, 0.77, 'Energy', fontsize=11, fontweight='bold')
    info_texts['energy'] = ax_info.text(0.1, 0.69, '', fontsize=10)
    
    # Stomach bar - Moved up
    stomach_bar_bg = plt.Rectangle((0.1, 0.58), 0.8, 0.04, 
                                   facecolor='lightgray', edgecolor='black')
    stomach_bar = plt.Rectangle((0.1, 0.58), 0.0, 0.04, 
                                facecolor='orange', edgecolor='black')
    ax_info.add_patch(stomach_bar_bg)
    ax_info.add_patch(stomach_bar)
    ax_info.text(0.1, 0.63, 'Stomach', fontsize=11, fontweight='bold')
    info_texts['stomach'] = ax_info.text(0.1, 0.55, '', fontsize=10)
    
    # Legend for states - Fixed spacing
    legend_start_y = 0.28
    ax_info.text(0.1, legend_start_y + 0.02, 'States Legend:', fontsize=11, fontweight='bold')
    for i, (state, color) in enumerate(state_colors.items()):
        y_pos = legend_start_y - (i * 0.04)
        ax_info.plot([0.15], [y_pos], 'o', color=color, markersize=10)
        ax_info.text(0.20, y_pos, state, fontsize=10, va='center')
    
    # Adjust map gridlines to prevent right-side overlap
    gl = ax_map.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5, linestyle='--')
    gl.right_labels = False # Turn off right labels to avoid overlap with colorbar
    
    plt.tight_layout(rect=[0, 0, 0.98, 0.95])
    
    def update(frame):
        """Update function for animation."""
        if frame >= len(seal_data):
            return []
        
        # Current data
        current = seal_data.iloc[frame]
        
        # Track history (last 24 hours)
        track_start = max(0, frame - 24)
        track_lons = seal_data.iloc[track_start:frame+1]['lon'].values
        track_lats = seal_data.iloc[track_start:frame+1]['lat'].values
        
        # Update track
        track_line.set_data(track_lons, track_lats)
        
        # Update seal marker
        state = current['state']
        color = state_colors.get(state, 'gray')
        seal_marker.set_data([current['lon']], [current['lat']])
        seal_marker.set_color(color)
        seal_marker.set_markeredgecolor('black')
        seal_marker.set_markeredgewidth(2)
        
        # Update info texts
        info_texts['title'].set_text(f"Seal {current['agent_id']} - Behavior Tracking")
        info_texts['date'].set_text(f"{current['timestamp']}")
        info_texts['state'].set_text(f"State: {state}")
        info_texts['state'].set_color(color)
        
        # Energy and stomach
        energy_pct = (current['energy'] / 100000.0) * 100
        stomach_pct = (current['stomach'] / 15.0) * 100
        
        info_texts['energy'].set_text(f"Energy: {current['energy']:.0f} / 100000 ({energy_pct:.1f}%)")
        info_texts['stomach'].set_text(f"Stomach: {current['stomach']:.1f} / 15.0 kg")
        
        # Update bars
        energy_bar.set_width(0.8 * (energy_pct / 100))
        stomach_bar.set_width(0.8 * (stomach_pct / 100))
        
        # Set bar colors based on levels
        if energy_pct > 70:
            energy_bar.set_facecolor('green')
        elif energy_pct > 40:
            energy_bar.set_facecolor('orange')
        else:
            energy_bar.set_facecolor('red')
        
        # Other info
        if pd.notna(current.get('depth')):
            info_texts['depth'].set_text(f"Depth: {current['depth']:.1f} m")
        else:
            info_texts['depth'].set_text(f"Depth: N/A (on land)")
        
        info_texts['position'].set_text(
            f"Position:\n  Lat: {current['lat']:.4f}°\n  Lon: {current['lon']:.4f}°"
        )
        
        # Progress indicator
        progress = (frame / len(seal_data)) * 100
        print(f"\rRendering frame {frame}/{len(seal_data)} ({progress:.1f}%)", end='')
        
        return [track_line, seal_marker] + list(info_texts.values()) + [energy_bar, stomach_bar]
    
    # Create animation
    print(f"Creating animation with {len(seal_data)} frames...")
    print(f"Video duration: ~{len(seal_data)/fps:.1f} seconds at {fps} fps")
    
    anim = animation.FuncAnimation(fig, update, frames=len(seal_data),
                                   interval=1000/fps, blit=False)
    
    # Save animation
    print(f"\nSaving animation to {output_file}...")
    writer = FFMpegWriter(fps=fps, metadata=dict(artist='Seal Simulation'), bitrate=5000)
    anim.save(output_file, writer=writer)
    
    print(f"\n✓ Animation saved: {output_file}")
    plt.close()

if __name__ == "__main__":
    # Paths
    seal_csv = "data/real_long/test_water_escape_seed42.csv"
    physics_file = "data/real_long/physics_2022_2023.nc"
    output_file = "data/real_long/seal_behavior_animation.mp4"
    
    # Load data
    print(f"Loading seal data from {seal_csv}...")
    seal_data = load_seal_data(seal_csv)
    print(f"Loaded {len(seal_data)} records")
    
    # Create animation
    create_seal_animation(seal_data, physics_file, output_file, fps=10)
    
    print("Done!")
