import os
import logging
from src.simulation.simulation import Simulation
from src.visualization.basic_plot import plot_tracks

# Configure logging to show progress
logging.basicConfig(level=logging.INFO)

import argparse

def run_long_simulation(duration_days=731, output_file="long_sim_results.csv"):
    print(f"--- Running Monk Seal Simulation ({duration_days} Days) ---")
    
    # Files
    data_dir = "data/real_long"
    nc_files = [
        os.path.join(data_dir, "physics_2022_2023.nc"),
        os.path.join(data_dir, "waves_2022_2023.nc"),
        os.path.join(data_dir, "bgc_2022_2023.nc")
    ]
    
    # Check if files exist
    missing = [f for f in nc_files if not os.path.exists(f)]
    if missing:
        print("Error: Missing data files. Please run 'src.download_long_data' first.")
        print(f"Missing: {missing}")
        return

    # Initialize Simulation
    # Time: Jan 1 2023 
    sim = Simulation(start_time="2023-01-01 00:00", duration_days=duration_days, time_step_hours=1)
    
    # Load Environment
    print("Loading Environment...")
    sim.load_environment(nc_files)
    
    # Create Agents
    # Desertas Islands: ~32.5N, 16.5W
    num_agents = 50 
    sim.create_agents(num_agents=num_agents, start_lat=32.5, start_lon=-16.5)
    
    # Run with Multiprocessing
    import multiprocessing
    workers = multiprocessing.cpu_count()
    print(f"Starting Simulation Loop with {workers} workers...")
    sim.run(max_workers=workers)
    
    # Save
    output_csv = os.path.join(data_dir, output_file)
    sim.save_results(output_csv)
    
    # Plot
    print("Plotting results...")
    try:
        plot_tracks(output_csv) # Removed output_image arg as it caused error previously
    except Exception as e:
        print(f"Plotting failed: {e}")
        
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=731, help="Simulation duration in days")
    parser.add_argument("--out", type=str, default="long_sim_results.csv", help="Output filename")
    args = parser.parse_args()
    
    run_long_simulation(duration_days=args.days, output_file=args.out)
