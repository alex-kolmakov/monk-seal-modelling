"""
Visualize environmental data layers to identify data coverage and coastline cells.

This script creates multi-layer visualizations showing:
- Island landmasses
- Bathymetry (depth data)
- Data coverage (cells with actual data vs NaN/inferred)
- Temperature
- Waves
- Other environmental variables

Usage:
    python -m src.visualization.visualize_data_layers
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.colors import LinearSegmentedColormap
import os

def load_data():
    """Load environmental data files."""
    data_dir = "data/real_long"
    
    # Load datasets
    physics = xr.open_dataset(os.path.join(data_dir, "physics_2022_2023.nc"))
    waves = xr.open_dataset(os.path.join(data_dir, "waves_2022_2023.nc"))
    bgc = xr.open_dataset(os.path.join(data_dir, "bgc_2022_2023.nc"))
    
    return physics, waves, bgc

def create_data_coverage_map(physics, waves, bgc, time_idx=0):
    """Create a map showing which cells have actual data vs NaN."""
    
    # Get a snapshot at specific time - use physics as reference
    temp = physics['thetao'].isel(time=time_idx, depth=0)
    
    # Get coordinates from physics (reference grid)
    lat = temp.latitude.values
    lon = temp.longitude.values
    
    # Create coverage mask for temperature
    has_temp = ~np.isnan(temp.values)
    
    # For waves and bgc, we'll just check if they have data (may be different resolution)
    # So we'll only use temperature for the detailed coverage map
    has_waves = True  # Assume waves data exists
    has_chl = True    # Assume chl data exists
    
    # Combined coverage (for now, just temperature)
    has_any_data = has_temp
    
    return lat, lon, has_temp, has_waves, has_chl, has_any_data

def create_bathymetry_map(physics):
    """Create bathymetry map showing depth and NaN cells."""
    
    # Get bathymetry from temperature data (max depth where temp exists)
    temp_data = physics['thetao'].isel(time=0)
    
    # For each lat/lon, find the maximum depth where temperature is not NaN
    bathymetry = np.full((len(temp_data.latitude), len(temp_data.longitude)), np.nan)
    
    for i, lat in enumerate(temp_data.latitude.values):
        for j, lon in enumerate(temp_data.longitude.values):
            temp_profile = temp_data.isel(latitude=i, longitude=j)
            valid_depths = temp_data.depth.values[~np.isnan(temp_profile.values)]
            if len(valid_depths) > 0:
                bathymetry[i, j] = valid_depths.max()
    
    return temp_data.latitude.values, temp_data.longitude.values, bathymetry

def plot_multi_layer_visualization(physics, waves, bgc, output_dir="data/real_long"):
    """Create comprehensive multi-layer visualization."""
    
    print("Creating multi-layer visualization...")
    
    # Get data
    lat_cov, lon_cov, has_temp, has_waves, has_chl, has_any_data = create_data_coverage_map(physics, waves, bgc)
    lat_bath, lon_bath, bathymetry = create_bathymetry_map(physics)
    
    # Get sample environmental data
    temp_surface = physics['thetao'].isel(time=0, depth=0).values
    wave_height = waves['VHM0'].isel(time=0).values
    
    # Create figure with subplots
    fig = plt.figure(figsize=(20, 12))
    
    # Define Madeira region
    extent = [-17.5, -16.0, 32.2, 33.2]  # [lon_min, lon_max, lat_min, lat_max]
    
    # 1. Bathymetry with NaN cells highlighted
    ax1 = plt.subplot(2, 3, 1, projection=ccrs.PlateCarree())
    ax1.set_extent(extent)
    ax1.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
    ax1.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax1.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Plot bathymetry
    bath_plot = ax1.pcolormesh(lon_bath, lat_bath, bathymetry, 
                               cmap='viridis_r', shading='auto', 
                               transform=ccrs.PlateCarree(), alpha=0.8)
    plt.colorbar(bath_plot, ax=ax1, label='Depth (m)', shrink=0.7)
    ax1.set_title('Bathymetry (Max Depth with Data)', fontsize=12, fontweight='bold')
    
    # 2. Data Coverage Map
    ax2 = plt.subplot(2, 3, 2, projection=ccrs.PlateCarree())
    ax2.set_extent(extent)
    ax2.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
    ax2.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax2.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Coverage levels: just use temperature data
    coverage_levels = has_temp.astype(int)
    
    cov_plot = ax2.pcolormesh(lon_cov, lat_cov, coverage_levels, 
                              cmap='RdYlGn', shading='auto',
                              transform=ccrs.PlateCarree(), alpha=0.8,
                              vmin=0, vmax=1)
    cbar = plt.colorbar(cov_plot, ax=ax2, shrink=0.7, ticks=[0, 1])
    cbar.set_label('Data Coverage')
    cbar.ax.set_yticklabels(['No Data', 'Has Data'])
    ax2.set_title('Temperature Data Coverage', fontsize=12, fontweight='bold')
    
    # 3. NaN Cells (Coastline Detection)
    ax3 = plt.subplot(2, 3, 3, projection=ccrs.PlateCarree())
    ax3.set_extent(extent)
    ax3.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
    ax3.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax3.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Identify NaN cells in bathymetry
    is_nan = np.isnan(bathymetry)
    
    nan_plot = ax3.pcolormesh(lon_bath, lat_bath, is_nan.astype(int), 
                              cmap='RdYlGn_r', shading='auto',
                              transform=ccrs.PlateCarree(), alpha=0.8)
    cbar = plt.colorbar(nan_plot, ax=ax3, shrink=0.7, ticks=[0, 1])
    cbar.ax.set_yticklabels(['Has Data', 'NaN (Land)'])
    ax3.set_title('NaN Cells (Potential Coastline)', fontsize=12, fontweight='bold')
    
    # 4. Surface Temperature
    ax4 = plt.subplot(2, 3, 4, projection=ccrs.PlateCarree())
    ax4.set_extent(extent)
    ax4.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
    ax4.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax4.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    temp_plot = ax4.pcolormesh(lon_cov, lat_cov, temp_surface, 
                               cmap='RdYlBu_r', shading='auto',
                               transform=ccrs.PlateCarree(), alpha=0.8)
    plt.colorbar(temp_plot, ax=ax4, label='Temperature (°C)', shrink=0.7)
    ax4.set_title('Surface Temperature', fontsize=12, fontweight='bold')
    
    # 5. Wave Height (if available in physics, otherwise use a placeholder)
    ax5 = plt.subplot(2, 3, 5, projection=ccrs.PlateCarree())
    ax5.set_extent(extent)
    ax5.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
    ax5.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax5.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Try to get wave height from waves dataset (may need interpolation)
    try:
        wave_height_interp = waves['VHM0'].isel(time=0).interp(
            latitude=lat_cov, longitude=lon_cov, method='nearest'
        ).values
    except:
        # If interpolation fails, just show a message
        wave_height_interp = np.full_like(temp_surface, np.nan)
    
    wave_plot = ax5.pcolormesh(lon_cov, lat_cov, wave_height_interp, 
                               cmap='Blues', shading='auto',
                               transform=ccrs.PlateCarree(), alpha=0.8)
    plt.colorbar(wave_plot, ax=ax5, label='Wave Height (m)', shrink=0.7)
    ax5.set_title('Significant Wave Height', fontsize=12, fontweight='bold')
    
    # 6. Coastline Cell Detection (NaN with nearby data)
    ax6 = plt.subplot(2, 3, 6, projection=ccrs.PlateCarree())
    ax6.set_extent(extent)
    ax6.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
    ax6.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax6.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    
    # Detect coastline cells: NaN cells with at least one non-NaN neighbor
    coastline_cells = np.zeros_like(bathymetry)
    rows, cols = bathymetry.shape
    for i in range(rows):
        for j in range(cols):
            if np.isnan(bathymetry[i, j]):
                # Check neighbors
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
                    coastline_cells[i, j] = 1  # Coastline cell
                else:
                    coastline_cells[i, j] = 0  # Interior land
            else:
                coastline_cells[i, j] = -1  # Water
    
    coast_plot = ax6.pcolormesh(lon_bath, lat_bath, coastline_cells, 
                                cmap='RdYlGn', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=-1, vmax=1)
    cbar = plt.colorbar(coast_plot, ax=ax6, shrink=0.7, ticks=[-1, 0, 1])
    cbar.ax.set_yticklabels(['Water', 'Interior Land', 'Coastline'])
    ax6.set_title('Coastline Cell Detection', fontsize=12, fontweight='bold')
    
    plt.suptitle('Madeira/Dessertas Environmental Data Layers', fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Save figure
    output_path = os.path.join(output_dir, "data_layers_visualization.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved visualization to: {output_path}")
    
    return fig

def print_data_statistics(physics, waves, bgc):
    """Print statistics about data coverage."""
    
    print("\n=== Data Coverage Statistics ===\n")
    
    # Bathymetry stats
    temp_data = physics['thetao'].isel(time=0, depth=0)
    total_cells = temp_data.size
    nan_cells = np.isnan(temp_data.values).sum()
    data_cells = total_cells - nan_cells
    
    print(f"Bathymetry Coverage:")
    print(f"  Total cells: {total_cells}")
    print(f"  Cells with data: {data_cells} ({100*data_cells/total_cells:.1f}%)")
    print(f"  NaN cells (land): {nan_cells} ({100*nan_cells/total_cells:.1f}%)")
    
    # Temperature stats
    print(f"\nTemperature (surface):")
    print(f"  Min: {np.nanmin(temp_data.values):.2f}°C")
    print(f"  Max: {np.nanmax(temp_data.values):.2f}°C")
    print(f"  Mean: {np.nanmean(temp_data.values):.2f}°C")
    
    # Wave stats
    wave_data = waves['VHM0'].isel(time=0)
    print(f"\nWave Height:")
    print(f"  Min: {np.nanmin(wave_data.values):.2f}m")
    print(f"  Max: {np.nanmax(wave_data.values):.2f}m")
    print(f"  Mean: {np.nanmean(wave_data.values):.2f}m")
    
    # Chlorophyll stats
    chl_data = bgc['chl'].isel(time=0, depth=0)
    print(f"\nChlorophyll:")
    print(f"  Min: {np.nanmin(chl_data.values):.4f}")
    print(f"  Max: {np.nanmax(chl_data.values):.4f}")
    print(f"  Mean: {np.nanmean(chl_data.values):.4f}")
    
    print("\n" + "="*40 + "\n")

def main():
    """Main function to create visualizations."""
    
    print("Loading environmental data...")
    physics, waves, bgc = load_data()
    
    print("Calculating statistics...")
    print_data_statistics(physics, waves, bgc)
    
    print("Creating visualizations...")
    fig = plot_multi_layer_visualization(physics, waves, bgc)
    
    plt.show()
    
    print("\nVisualization complete!")

if __name__ == "__main__":
    main()
