import pandas as pd
import matplotlib.pyplot as plt
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import argparse

def analyze_long_run(results_file="data/real_long/long_sim_results_stats.csv"):
    if not os.path.exists(results_file):
        logger.error(f"Stats file not found: {results_file}")
        return

    logger.info(f"Loading stats from {results_file}...")
    df = pd.read_csv(results_file)
    df['date'] = pd.to_datetime(df['date'])
    
    output_dir = os.path.dirname(results_file)
    plot_dir = os.path.join(output_dir, "analysis_plots")
    os.makedirs(plot_dir, exist_ok=True)
    
    # Prefix for plots based on filename
    basename = os.path.splitext(os.path.basename(results_file))[0]

    # Plot 1: Population Dynamics
    plt.figure(figsize=(12, 6))
    plt.plot(df['date'], df['total_agents'], label='Total Agents', color='blue', linewidth=2)
    plt.plot(df['date'], df['pup_count'], label='Pups', color='green', linestyle='--', linewidth=1.5)
    plt.title(f"Monk Seal Population Dynamics ({basename})")
    plt.xlabel("Date")
    plt.ylabel("Count")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, f"{basename}_population.png"))
    plt.close()
    logger.info(f"Saved {basename}_population.png")

    # Plot 2: Average Energy
    plt.figure(figsize=(12, 6))
    plt.plot(df['date'], df['avg_energy'], label='Average Energy', color='orange')
    plt.axhline(y=0, color='red', linestyle=':', label='Starvation Threshold')
    plt.title(f"Average Population Energy ({basename})")
    plt.xlabel("Date")
    plt.ylabel("Energy")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, f"{basename}_energy.png"))
    plt.close()
    logger.info(f"Saved {basename}_energy.png")

    logger.info("Analysis Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default="data/real_long/long_sim_results_stats.csv", help="Path to stats CSV")
    args = parser.parse_args()
    
    analyze_long_run(args.file)
