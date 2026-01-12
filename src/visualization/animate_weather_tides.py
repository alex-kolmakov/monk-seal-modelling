"""
Create animated visualization of time-varying environmental data over 2 years.

This script creates a 60fps video animation showing 6-hourly snapshots of:
- Surface temperature
- Wave height
- Chlorophyll concentration
- Tidal changes (sea surface height)

Usage:
    python -m src.visualization.animate_weather_tides
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.animation import FuncAnimation, FFMpegWriter
import os
from datetime import datetime, timedelta

def load_data():
    """Load environmental data files."""
    data_dir = "data/real_long"
    
    print("Loading datasets...")
    physics = xr.open_dataset(os.path.join(data_dir, "physics_2022_2023.nc"))
    waves = xr.open_dataset(os.path.join(data_dir, "waves_2022_2023.nc"))
    bgc = xr.open_dataset(os.path.join(data_dir, "bgc_2022_2023.nc"))
    tidal = xr.open_dataset(os.path.join(data_dir, "tidal_2023_2024.nc"))
    
    return physics, waves, bgc, tidal

def create_animation(physics, waves, bgc, tidal, output_file="data/real_long/weather_tides_animation.mp4", 
                     fps=60):
    """Create animated visualization of time-varying weather layers."""
    
    print("Preparing data...")
    
    # Get coordinates from physics (reference grid)
    lat = physics['thetao'].isel(time=0, depth=0).latitude.values
    lon = physics['thetao'].isel(time=0, depth=0).longitude.values
    
    # Get time range - physics has DAILY data for 2 years (2023-2024)
    # Use all timesteps to show full 2 years
    times = physics.time.values
    total_days = len(times)
    
    print(f"Total days in dataset: {total_days}")
    
    # Use all daily timesteps
    time_indices = range(0, total_days)
    n_frames = len(time_indices)
    
    print(f"Creating animation with {n_frames} frames (daily intervals)")
    print(f"Time range: {times[0]} to {times[-1]}")
    print(f"Video duration: ~{n_frames/fps:.1f} seconds at {fps} fps")
    
    # Define extent
    extent = [-17.5, -16.0, 32.2, 33.2]
    
    # Create figure with 2x2 grid
    fig = plt.figure(figsize=(16, 12))
    
    # Create subplots
    ax1 = plt.subplot(2, 2, 1, projection=ccrs.PlateCarree())
    ax2 = plt.subplot(2, 2, 2, projection=ccrs.PlateCarree())
    ax3 = plt.subplot(2, 2, 3, projection=ccrs.PlateCarree())
    ax4 = plt.subplot(2, 2, 4, projection=ccrs.PlateCarree())
    
    axes = [ax1, ax2, ax3, ax4]
    
    # Setup axes
    for ax in axes:
        ax.set_extent(extent)
        ax.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        ax.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Initialize plots (will be updated in animation)
    plots = {}
    
    # 1. Temperature (top-left)
    temp_init = physics['thetao'].isel(time=0, depth=0).values
    temp_plot = ax1.pcolormesh(lon, lat, temp_init, cmap='RdYlBu_r',
                               shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                               vmin=17, vmax=22)
    plt.colorbar(temp_plot, ax=ax1, label='Temperature (°C)', shrink=0.7)
    ax1.set_title('Surface Temperature', fontsize=12, fontweight='bold')
    plots['temp'] = temp_plot
    
    # 2. Waves (top-right)
    try:
        wave_init = waves['VHM0'].isel(time=0).interp(
            latitude=lat, longitude=lon, method='nearest'
        ).values
    except:
        wave_init = np.full_like(temp_init, np.nan)
    
    wave_plot = ax2.pcolormesh(lon, lat, wave_init, cmap='Blues',
                               shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                               vmin=0, vmax=4)
    plt.colorbar(wave_plot, ax=ax2, label='Wave Height (m)', shrink=0.7)
    ax2.set_title('Significant Wave Height', fontsize=12, fontweight='bold')
    plots['wave'] = wave_plot
    
    # 3. Chlorophyll (bottom-left)
    chl_init = bgc['chl'].isel(time=0, depth=0).values
    chl_plot = ax3.pcolormesh(lon, lat, chl_init, cmap='Greens',
                              shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                              vmin=0, vmax=0.5)
    plt.colorbar(chl_plot, ax=ax3, label='Chlorophyll (mg/m³)', shrink=0.7)
    ax3.set_title('Chlorophyll Concentration', fontsize=12, fontweight='bold')
    plots['chl'] = chl_plot
    
    # 4. Tidal/Sea Level (bottom-right)
    # Interpolate tidal data to match physics grid
    try:
        tidal_init = tidal['adt'].isel(time=0).interp(
            latitude=lat, longitude=lon, method='nearest'
        ).values
        # Convert from meters to cm for better visualization
        tidal_init_cm = tidal_init * 100
        
        # Calculate data range for color scale (use percentiles to avoid outliers)
        all_tidal_data = tidal['adt'].values * 100
        vmin_tidal = np.nanpercentile(all_tidal_data, 5)
        vmax_tidal = np.nanpercentile(all_tidal_data, 95)
        
    except:
        tidal_init_cm = np.full_like(temp_init, np.nan)
        vmin_tidal, vmax_tidal = -20, 20
    
    tidal_plot = ax4.pcolormesh(lon, lat, tidal_init_cm, cmap='RdBu_r',
                                shading='auto', transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=vmin_tidal, vmax=vmax_tidal)
    plt.colorbar(tidal_plot, ax=ax4, label='Sea Level Height (cm)', shrink=0.7)
    ax4.set_title('Sea Level Anomaly (Long-term)', fontsize=12, fontweight='bold')
    plots['tidal'] = tidal_plot
    
    # Add date counter at the top
    date_text = fig.text(0.5, 0.97, '', ha='center', fontsize=18, fontweight='bold',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    def update(frame_idx):
        """Update function for animation."""
        time_idx = time_indices[frame_idx]
        current_time = times[time_idx]
        
        # Update date counter with readable format
        current_datetime = np.datetime_as_string(current_time, unit='D')
        # Format: YYYY-MM-DD
        date_text.set_text(f'{current_datetime} | Day {time_idx + 1} of {total_days}')
        
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
        
        # Update tidal data
        # Find closest time in tidal dataset
        try:
            tidal_time_idx = np.abs(tidal.time.values - current_time).argmin()
            tidal_data = tidal['adt'].isel(time=tidal_time_idx).interp(
                latitude=lat, longitude=lon, method='nearest'
            ).values
            tidal_data_cm = tidal_data * 100  # Convert to cm
        except:
            tidal_data_cm = np.full_like(temp_data, np.nan)
        plots['tidal'].set_array(tidal_data_cm.ravel())
        
        if frame_idx % 100 == 0:
            print(f"  Frame {frame_idx}/{n_frames} ({100*frame_idx/n_frames:.1f}%)")
        
        return list(plots.values()) + [date_text]
    
    print("Creating animation...")
    anim = FuncAnimation(fig, update, frames=n_frames, interval=1000/fps, blit=False)  # blit=False to show text
    
    # Save animation
    print(f"Saving animation to {output_file}...")
    writer = FFMpegWriter(fps=fps, metadata=dict(artist='Seal Simulation'), bitrate=3000)
    anim.save(output_file, writer=writer)
    
    print(f"Animation saved successfully!")
    plt.close()
    
    return output_file

def main():
    """Main function."""
    
    # Load data
    physics, waves, bgc, tidal = load_data()
    
    # Create animation (6-hour intervals, 60 fps)
    output_file = create_animation(physics, waves, bgc, tidal,
                                   output_file="data/real_long/weather_tides_60fps.mp4",
                                   fps=60)
    
    print(f"\n✓ Animation complete: {output_file}")

if __name__ == "__main__":
    main()
