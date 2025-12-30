import pandas as pd
import matplotlib.pyplot as plt
import argparse

def plot_tracks(csv_file: str):
    """
    Plot agent tracks from simulation CSV.
    """
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"File not found: {csv_file}")
        return

    plt.figure(figsize=(10, 8))
    
    # Plot Tracks
    for agent_id, group in df.groupby('agent_id'):
        plt.plot(group['lon'], group['lat'], marker='o', markersize=2, label=f'Seal {agent_id}', alpha=0.7)
        # Mark Start/End
        plt.scatter(group['lon'].iloc[0], group['lat'].iloc[0], c='green', s=50, marker='^', zorder=5) # Start
        plt.scatter(group['lon'].iloc[-1], group['lat'].iloc[-1], c='red', s=50, marker='x', zorder=5) # End

    plt.title(f"Seal Agent Tracks (Madeira)\n{len(df['agent_id'].unique())} Agents, {len(df)} steps")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    
    # Save
    output_img = csv_file.replace('.csv', '_tracks.png')
    plt.savefig(output_img)
    print(f"Plot saved to {output_img}")
    # plt.show() # Disabled for headless env

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to simulation results CSV")
    args = parser.parse_args()
    
    plot_tracks(args.file)
