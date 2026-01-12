"""
Create animated visualization of environmental data layers over 2 years.

This script creates a video animation showing daily snapshots of:
- Bathymetry (static)
- Surface temperature
- Wave height
- Chlorophyll
- Coastline cells

Usage:
    python -m src.visualization.animate_weather_layers
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib.colors import LinearSegmentedColormap
import os
from datetime import datetime, timedelta

def load_data():
    """Load environmental data files."""
    data_dir = "data/real_long"
    
    print("Loading datasets...")
    physics = xr.open_dataset(os.path.join(data_dir, "physics_2022_2023.nc"))
    waves = xr.open_dataset(os.path.join(data_dir, "waves_2022_2023.nc"))
    bgc = xr.open_dataset(os.path.join(data_dir, "bgc_2022_2023.nc"))
    
    return physics, waves, bgc

def create_bathymetry_map(physics):
    """Create static bathymetry map."""
    temp_data = physics['thetao'].isel(time=0)
    
    bathymetry = np.full((len(temp_data.latitude), len(temp_data.longitude)), np.nan)
    
    for i, lat in enumerate(temp_data.latitude.values):
        for j, lon in enumerate(temp_data.longitude.values):
            temp_profile = temp_data.isel(latitude=i, longitude=j)
            valid_depths = temp_data.depth.values[~np.isnan(temp_profile.values)]
            if len(valid_depths) > 0:
                bathymetry[i, j] = valid_depths.max()
    
    return temp_data.latitude.values, temp_data.longitude.values, bathymetry

def detect_coastline_cells(bathymetry):
    """Detect coastline cells (NaN with water neighbors)."""
    coastline_cells = np.zeros_like(bathymetry)
    rows, cols = bathymetry.shape
    
    for i in range(rows):
        for j in range(cols):
            if np.isnan(bathymetry[i, j]):
                has_data_neighbor = False
                for di in [-1, 0, 1]:
                    for dj in [-1, 0, 1]:
                        ni, nj = i + di, j + dj
                        if 0 <= ni < rows and 0 <= nj < cols:
                            if not np.isnan(bathymetry[ni, nj]):
                                has_data_neighbor = True
                                break
                    if has_data_neighbor:
                        break
                if has_data_neighbor:
                    coastline_cells[i, j] = 1
                else:
                    coastline_cells[i, j] = 0
            else:
                coastline_cells[i, j] = -1
    
    return coastline_cells

def create_animation(physics, waves, bgc, output_file="data/real_long/weather_animation.mp4", 
                     fps=10, skip_days=1):
    """Create animated visualization of weather layers."""
    
    print("Preparing data...")
    
    # Get bathymetry (static)
    lat, lon, bathymetry = create_bathymetry_map(physics)
    coastline_cells = detect_coastline_cells(bathymetry)
    
    # Get time range
    times = physics.time.values
    total_days = len(times)
    
    # Sample every skip_days
    time_indices = range(0, total_days, skip_days)
    n_frames = len(time_indices)
    
    print(f"Creating animation with {n_frames} frames ({total_days} days, sampling every {skip_days} days)")
    
    # Define extent
    extent = [-17.5, -16.0, 32.2, 33.2]
    
    # Create figure
    fig = plt.figure(figsize=(16, 10))
    
    # Create subplots
    ax1 = plt.subplot(2, 3, 1, projection=ccrs.PlateCarree())
    ax2 = plt.subplot(2, 3, 2, projection=ccrs.PlateCarree())
    ax3 = plt.subplot(2, 3, 3, projection=ccrs.PlateCarree())
    ax4 = plt.subplot(2, 3, 4, projection=ccrs.PlateCarree())
    ax5 = plt.subplot(2, 3, 5, projection=ccrs.PlateCarree())
    ax6 = plt.subplot(2, 3, 6, projection=ccrs.PlateCarree())
    
    axes = [ax1, ax2, ax3, ax4, ax5, ax6]
    
    # Setup axes
    for ax in axes:
        ax.set_extent(extent)
        ax.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Initialize plots (will be updated in animation)
    plots = {}
    
    # 1. Bathymetry (static)
    bath_plot = ax1.pcolormesh(lon, lat, bathymetry, cmap='viridis_r', 
                               shading='auto', transform=ccrs.PlateCarree(), alpha=0.8)
    plt.colorbar(bath_plot, ax=ax1, label='Depth (m)', shrink=0.7)
    ax1.set_title('Bathymetry (Static)', fontsize=10, fontweight='bold')
    
    # 2. Temperature (will update)
    temp_init = physics['thetao'].isel(time=0, depth=0).values
    temp_plot = ax2.pcolormesh(lon, lat, temp_init, cmap='RdYlBu_r',
                               shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                               vmin=17, vmax=22)
    plt.colorbar(temp_plot, ax=ax2, label='Temperature (°C)', shrink=0.7)
    ax2.set_title('Surface Temperature', fontsize=10, fontweight='bold')
    plots['temp'] = temp_plot
    
    # 3. Waves (will update)
    try:
        wave_init = waves['VHM0'].isel(time=0).interp(
            latitude=lat, longitude=lon, method='nearest'
        ).values
    except:
        wave_init = np.full_like(temp_init, np.nan)
    
    wave_plot = ax3.pcolormesh(lon, lat, wave_init, cmap='Blues',
                               shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                               vmin=0, vmax=4)
    plt.colorbar(wave_plot, ax=ax3, label='Wave Height (m)', shrink=0.7)
    ax3.set_title('Significant Wave Height', fontsize=10, fontweight='bold')
    plots['wave'] = wave_plot
    
    # 4. Chlorophyll (will update)
    chl_init = bgc['chl'].isel(time=0, depth=0).values
    chl_plot = ax4.pcolormesh(lon, lat, chl_init, cmap='Greens',
                              shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                              vmin=0, vmax=0.5)
    plt.colorbar(chl_plot, ax=ax4, label='Chlorophyll', shrink=0.7)
    ax4.set_title('Chlorophyll Concentration', fontsize=10, fontweight='bold')
    plots['chl'] = chl_plot
    
    # 5. Coastline cells (static)
    coast_plot = ax5.pcolormesh(lon, lat, coastline_cells, cmap='RdYlGn',
                                shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=-1, vmax=1)
    cbar = plt.colorbar(coast_plot, ax=ax5, shrink=0.7, ticks=[-1, 0, 1])
    cbar.ax.set_yticklabels(['Water', 'Interior Land', 'Coastline'])
    ax5.set_title('Coastline Cells (Static)', fontsize=10, fontweight='bold')
    
    # 6. Data coverage (will update)
    has_data_init = ~np.isnan(temp_init)
    coverage_plot = ax6.pcolormesh(lon, lat, has_data_init.astype(int), cmap='RdYlGn',
                                   shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                                   vmin=0, vmax=1)
    cbar = plt.colorbar(coverage_plot, ax=ax6, shrink=0.7, ticks=[0, 1])
    cbar.ax.set_yticklabels(['No Data', 'Has Data'])
    ax6.set_title('Temperature Data Coverage', fontsize=10, fontweight='bold')
    plots['coverage'] = coverage_plot
    
    # Add date text
    date_text = fig.text(0.5, 0.95, '', ha='center', fontsize=14, fontweight='bold')
    
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    def update(frame_idx):
        """Update function for animation."""
        time_idx = time_indices[frame_idx]
        current_time = times[time_idx]
        
        # Update date text
        date_str = np.datetime_as_string(current_time, unit='D')
        date_text.set_text(f'Date: {date_str} (Day {time_idx + 1}/{total_days})')
        
        # Update temperature
        temp_data = physics['thetao'].isel(time=time_idx, depth=0).values
        plots['temp'].set_array(temp_data.ravel())
        
        # Update waves
        try:
            wave_data = waves['VHM0'].isel(time=time_idx).interp(
                latitude=lat, longitude=lon, method='nearest'
            ).values
        except:
            wave_data = np.full_like(temp_data, np.nan)
        plots['wave'].set_array(wave_data.ravel())
        
        # Update chlorophyll
        chl_data = bgc['chl'].isel(time=time_idx, depth=0).values
        plots['chl'].set_array(chl_data.ravel())
        
        # Update coverage
        has_data = ~np.isnan(temp_data)
        plots['coverage'].set_array(has_data.astype(int).ravel())
        
        if frame_idx % 10 == 0:
            print(f"  Frame {frame_idx}/{n_frames} ({100*frame_idx/n_frames:.1f}%)")
        
        return list(plots.values()) + [date_text]
    
    print("Creating animation...")
    anim = FuncAnimation(fig, update, frames=n_frames, interval=100, blit=True)
    
    # Save animation
    print(f"Saving animation to {output_file}...")
    writer = FFMpegWriter(fps=fps, metadata=dict(artist='Seal Simulation'), bitrate=1800)
    anim.save(output_file, writer=writer)
    
    print(f"Animation saved successfully!")
    plt.close()
    
    return output_file

def main():
    """Main function."""
    
    # Load data
    physics, waves, bgc = load_data()
    
    # Create animation (sample every 1 day, 30 fps = ~24 seconds for 2 years)
    output_file = create_animation(physics, waves, bgc, 
                                   output_file="data/real_long/weather_animation_2years.mp4",
                                   fps=30, skip_days=1)
    
    print(f"\n✓ Animation complete: {output_file}")
    print(f"  Duration: ~{len(physics.time)//30} seconds at 30 fps")

if __name__ == "__main__":
    main()
