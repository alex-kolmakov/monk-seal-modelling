import pandas as pd
import matplotlib.pyplot as plt
import argparse
import os

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except ImportError:
    HAS_CARTOPY = False

def plot_tracks(csv_file: str):
    """
    Plot agent tracks from simulation CSV.
    Uses Cartopy for map overlay if available.
    """
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"File not found: {csv_file}")
        return

    # Determine layout
    fig = plt.figure(figsize=(12, 10))
    
    if HAS_CARTOPY:
        print("Using Cartopy for map background...")
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        
        # Add Features
        ax.add_feature(cfeature.LAND, edgecolor='black', facecolor='lightgray', alpha=0.5, zorder=1)
        ax.add_feature(cfeature.COASTLINE, linewidth=1, zorder=2)
        ax.add_feature(cfeature.OCEAN, facecolor='azure', alpha=0.3, zorder=0)
        
        # Gridlines
        gl = ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
        
        # Set Extent from Data with buffer
        lat_min, lat_max = df['lat'].min(), df['lat'].max()
        lon_min, lon_max = df['lon'].min(), df['lon'].max()
        
        buff = 0.5
        ax.set_extent([lon_min - buff, lon_max + buff, lat_min - buff, lat_max + buff], crs=ccrs.PlateCarree())
        
        # Transform for data plotting
        transform = ccrs.PlateCarree()
    else:
        print("Cartopy not found. Using standard Matplotlib plotting.")
        ax = fig.add_subplot(1, 1, 1)
        ax.grid(True, linestyle='--', alpha=0.5)
        transform = None

    # Plot Tracks
    for agent_id, group in df.groupby('agent_id'):
        label = f'Seal {agent_id}'
        
        # Arguments for plot
        kwargs = {
            'marker': 'o', 
            'markersize': 2, 
            'label': label, 
            'alpha': 0.7
        }
        if transform: kwargs['transform'] = transform
            
        ax.plot(group['lon'], group['lat'], **kwargs)
        
        # Mark Start/End
        # Start
        skwargs = {'c': 'green', 's': 50, 'marker': '^', 'zorder': 5}
        if transform: skwargs['transform'] = transform
        ax.scatter(group['lon'].iloc[0], group['lat'].iloc[0], **skwargs)
        
        # End
        ekwargs = {'c': 'red', 's': 50, 'marker': 'x', 'zorder': 5}
        if transform: ekwargs['transform'] = transform
        ax.scatter(group['lon'].iloc[-1], group['lat'].iloc[-1], **ekwargs)

    plt.title(f"Seal Agent Tracks (Madeira)\n{len(df['agent_id'].unique())} Agents, {len(df)} steps")
    if not HAS_CARTOPY:
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        
    plt.legend()
    
    # Save
    output_img = csv_file.replace('.csv', '_tracks.png')
    plt.savefig(output_img)
    print(f"Plot saved to {output_img}")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to simulation results CSV")
    args = parser.parse_args()
    
    plot_tracks(args.file)
