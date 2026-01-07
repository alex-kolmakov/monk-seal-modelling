import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import contextily as ctx
from shapely.geometry import Point
import geopandas as gpd
import argparse
import numpy as np
import os

# Convert Lat/Lon to WebMercator (EPSG:3857) for Contextily
def latlon_to_webmercator(df, lat_col='lat', lon_col='lon'):
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df[lon_col], df[lat_col]), crs="EPSG:4326"
    )
    return gdf.to_crs(epsg=3857)

def animate_agent(agent_id, agent_df, output_dir, fps=10):
    """
    Generates a detailed animation for a specific agent.
    """
    print(f"Processing Agent {agent_id}...")
    
    # 1. Prepare Data
    # Resample to Daily (take last pos of day)
    agent_df['time'] = pd.to_datetime(agent_df['time'])
    daily_df = agent_df.groupby(pd.Grouper(key='time', freq='D')).last().reset_index()
    daily_df = daily_df.dropna(subset=['lat', 'lon']) # Drop days with no data
    
    if daily_df.empty:
        print(f"Skipping Agent {agent_id} (No valid data)")
        return

    # Project to WebMercator for Map Tiles
    gdf = latlon_to_webmercator(daily_df)
    
    # Extract coordinates
    xs = gdf.geometry.x.values
    ys = gdf.geometry.y.values
    times = daily_df['time'].dt.strftime('%Y-%m-%d').values
    states = daily_df['state'].values
    
    # 2. Setup Plot
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Set Bounds (Auto-scale to track + padding)
    margin = 50000 # 50km margin
    ax.set_xlim(xs.min() - margin, xs.max() + margin)
    ax.set_ylim(ys.min() - margin, ys.max() + margin)
    ax.set_axis_off() # clean look
    
    # Add Basemap
    try:
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron) # Clean, light map
    except Exception as e:
        print(f"Warning: Could not fetch map tiles: {e}")

    # Plot Elements
    # A. History Trail (Faint line)
    trail, = ax.plot([], [], color='#FF4500', alpha=0.3, linewidth=1.5, zorder=2)
    
    # B. Current Head (Bold dot)
    head = ax.scatter([], [], color='#FF4500', s=100, edgecolors='white', linewidth=1.5, zorder=3, label=f"Seal {agent_id}")
    
    # C. Info Text
    info_text = ax.text(0.05, 0.95, '', transform=ax.transAxes, fontsize=12, 
                        bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    
    ax.set_title(f"Seal {agent_id} Movement History", fontsize=16)

    def init():
        trail.set_data([], [])
        head.set_offsets(np.empty((0, 2)))
        info_text.set_text('')
        return trail, head, info_text

    def update(frame_idx):
        # Draw path up to frame_idx
        current_xs = xs[:frame_idx+1]
        current_ys = ys[:frame_idx+1]
        
        trail.set_data(current_xs, current_ys)
        
        # Draw head at current pos
        head.set_offsets(np.c_[xs[frame_idx], ys[frame_idx]])
        
        # State Color?
        state = states[frame_idx]
        color_map = {
            "FORAGING": "#1f77b4", "RESTING": "#2ca02c",
            "HAULING_OUT": "#ff7f0e", "TRANSITING": "gray",
            "NURSING": "#e377c2", "SLEEPING": "#9467bd", "DEAD": "black"
        }
        head.set_color(color_map.get(state, 'red'))
        
        info_text.set_text(f"Date: {times[frame_idx]}\nState: {state}")
        
        return trail, head, info_text

    ani = animation.FuncAnimation(fig, update, frames=len(xs), init_func=init, blit=False)
    
    # Save
    filename = os.path.join(output_dir, f"seal_{agent_id}_trace.mp4")
    print(f"Saving {filename} ({len(xs)} frames)...")
    
    try:
        writer = animation.FFMpegWriter(fps=fps, bitrate=2000)
        ani.save(filename, writer=writer)
        print("Done!")
    except Exception as e:
        print(f"FFmpeg failed, falling back to GIF: {e}")
        writer = animation.PillowWriter(fps=fps)
        ani.save(filename.replace(".mp4", ".gif"), writer=writer)
        
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to CSV results")
    parser.add_argument("--output_dir", default="data/real_long/videos", help="Directory for output videos")
    parser.add_argument("--limit", type=int, default=3, help="Max number of agents to animate (prioritizing survivors/longest lived)")
    
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Loading {args.file}...")
    df = pd.read_csv(args.file)
    
    # Select agents to animate:
    # 1. Alive at end?
    last_time = pd.to_datetime(df['time']).max()
    final_state = df[pd.to_datetime(df['time']) == last_time]
    survivors = final_state[final_state['state'] != 'DEAD']['agent_id'].unique()
    
    # If no survivors, use longest lived
    target_ids = list(survivors)
    if len(target_ids) < args.limit:
        # Add random others? Or just stick to survivors?
        # Let's add some that lived long but died
        lifespans = df.groupby('agent_id')['time'].count().sort_values(ascending=False)
        others = [aid for aid in lifespans.index if aid not in target_ids]
        target_ids.extend(others)
    
    target_ids = target_ids[:args.limit]
    
    print(f"Selected {len(target_ids)} agents for animation: {target_ids}")
    
    for aid in target_ids:
        agent_df = df[df['agent_id'] == aid].copy()
        animate_agent(aid, agent_df, args.output_dir)

if __name__ == "__main__":
    main()
