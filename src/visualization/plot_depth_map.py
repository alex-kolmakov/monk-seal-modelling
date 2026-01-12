
import os
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np

def plot_depth_with_coastline():
    print("Loading data...")
    data_dir = "data/real_long"
    physics_file = os.path.join(data_dir, "physics_2022_2023.nc")
    
    # Load Data
    ds = xr.open_dataset(physics_file)
    
    # Standardize Coords
    rename_dict = {}
    for coord in ds.coords:
        if coord.lower() in ['latitude']: rename_dict[coord] = 'lat'
        elif coord.lower() in ['longitude']: rename_dict[coord] = 'lon'
    if rename_dict: ds = ds.rename(rename_dict)
    
    # Valid Region: Madeira + Desertas
    # Lat: 32.2 - 33.3
    # Lon: -17.3 - -16.2
    
    # Extract Depth (Bathymetry)
    # Using the logic from Environment.py: Max Depth where thetao is not NaN
    print("Computing Bathymetry...")
    sample_slice = ds['thetao'].isel(time=0)
    valid_mask = sample_slice.notnull()
    depth_map = ds['depth'].where(valid_mask).max(dim='depth').compute()
    
    # Plotting
    print("Plotting...")
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    
    # Set Extent to Madeira Archipelago
    ax.set_extent([-17.4, -16.2, 32.2, 33.4], crs=ccrs.PlateCarree())
    
    # Plot Depth (Bathymetry)
    # Use 'viridis_r' (reversed) so shallow is light/yellow, deep is dark/purple
    # Or 'Blues' for water look.
    depth_plot = depth_map.plot(
        ax=ax, 
        transform=ccrs.PlateCarree(), 
        cmap='Blues', 
        cbar_kwargs={'label': 'Depth (m)'},
        vmin=0, vmax=3000
    )
    
    # Overlay "Simulation Land" (NaN in depth map)
    # We can mask the depth map where it is NOT NaN to show water, 
    # and then plot the background or a specific color for NaN.
    # Actually, xarray plot handles NaNs as transparency (white by default).
    
    # Add Cartopy High Res Coastline (The "Actual Map")
    ax.add_feature(cfeature.LAND, edgecolor='black', facecolor='lightgray', alpha=0.5, zorder=2)
    ax.add_feature(cfeature.COASTLINE, linewidth=1, zorder=3)
    
    # Add Gridlines
    gl = ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
    
    plt.title("Madeira Bathymetry (Data) vs Actual Coastline (Cartopy)")
    plt.savefig("depth_verification_map.png")
    print("Saved plot to depth_verification_map.png")
    plt.close()

if __name__ == "__main__":
    plot_depth_with_coastline()
