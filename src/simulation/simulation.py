import logging
import os
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat

import numpy as np
import pandas as pd

from src.simulation.agent_worker import update_agent_worker
from src.simulation.agents.seal import SealAgent
from src.simulation.environment.environment import Environment
from src.simulation.environment.utils import query_env_buffers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Simulation:
    """
    Main Simulation Controller.
    Manages the Environment, Time, and Population of Agents.
    Uses Multiprocessing for agent updates.
    """

    def __init__(self, start_time: str, duration_days: int, time_step_hours: int = 1):
        self.start_time = pd.Timestamp(start_time)
        self.current_time = self.start_time
        self.end_time = self.start_time + pd.Timedelta(days=duration_days)
        self.time_step = pd.Timedelta(hours=time_step_hours)

        self.environment = Environment()
        self.agents: list[SealAgent] = []

        # Track history for analysis
        self.history: list[dict] = []

        logger.info(
            f"Simulation Initialized: {self.start_time} to {self.end_time} (Step: {self.time_step})"
        )

    def load_environment(self, nc_files: list[str]):
        """Load environmental data from NetCDF files."""
        if not nc_files:
            logger.warning(
                "No environment files provided. Agents will run in 'void' mode (defaults)."
            )
            return

        self.environment.load_data(nc_files)

    def create_agents(
        self, num_agents: int = 100, start_lat: float = 32.74, start_lon: float = -16.69
    ):
        """Initialize N agents at a starting location."""
        for i in range(num_agents):
            lat = start_lat + np.random.uniform(-0.05, 0.05)
            lon = start_lon + np.random.uniform(-0.05, 0.05)
            sex = "M" if np.random.random() > 0.5 else "F"
            age = np.random.randint(1, 20)

            agent = SealAgent(agent_id=str(i), start_pos=(lat, lon), age=age, sex=sex)
            self.agents.append(agent)

        logger.info(f"Created {num_agents} agents around ({start_lat}, {start_lon})")

    def run(self, max_workers: int | None = None):
        """Run the simulation loop until end_time."""
        logger.info("Starting Simulation Loop...")

        step_count = 0

        # Use ProcessPoolExecutor for parallel processing
        # Use simple os.cpu_count() default if None
        workers = max_workers if max_workers else os.cpu_count()
        logger.info(f"Using {workers} workers for multiprocessing.")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            while self.current_time < self.end_time:
                self.step(executor)
                self.current_time += self.time_step
                step_count += 1

                if step_count % 24 == 0:
                    logger.info(
                        f"Simulation Progress: {self.current_time} ({step_count} steps). "
                        f"Agents: {len(self.agents)}"
                    )

        logger.info(f"Simulation Complete. Total Steps: {step_count}")

    def step(self, executor):
        """Execute one time step using the provided executor."""
        # 1. Update Environment Buffers (Sequential)
        self.environment.update_buffers(self.current_time)
        buffers = self.environment.buffers  # Extract dict for pickling

        # 2. Parallel Agent Update
        # Map update_agent_worker(agent, buffers) across agents
        # use repeat(buffers) to pass same env data to all

        # Generator for faster submission? List conversion needed for results.
        results = list(executor.map(update_agent_worker, self.agents, repeat(buffers)))

        # 3. Post-Process (Reconstruct agent list, filter dead, handle births)
        active_agents = []
        new_agents = []

        for agent in results:
            if agent.state == "DEAD":
                continue

            active_agents.append(agent)

            # Record History (Sequential)
            # Query env data again for history? Or agent carries it?
            # Agent doesn't carry env data.
            # We can re-query efficiently using buffers (main process).
            env_data = query_env_buffers(agent.pos[0], agent.pos[1], buffers)

            self.history.append(
                {
                    "time": self.current_time,
                    "agent_id": agent.id,
                    "lat": agent.pos[0],
                    "lon": agent.pos[1],
                    "state": str(agent.state).split(".")[-1],
                    "energy": agent.energy,
                    "stomach": agent.stomach_load,
                    **env_data,
                }
            )

        self.agents = active_agents + new_agents

        # Daily Stats Logging (at Midnight)
        if self.current_time.hour == 0:
            total_agents = len(self.agents)

            avg_energy = (
                sum(a.energy for a in self.agents) / total_agents if total_agents > 0 else 0
            )

            stat = {
                "date": self.current_time,
                "total_agents": total_agents,
                "avg_energy": avg_energy,
            }
            if not hasattr(self, "daily_stats"):
                self.daily_stats = []
            self.daily_stats.append(stat)
            logger.info(f"Daily Stats: {stat}")

    def save_results(self, output_file: str = "simulation_results.csv"):
        """Save history to CSV."""
        if not self.history:
            logger.warning("No history to save.")
            return

        df = pd.DataFrame(self.history)
        df.to_csv(output_file, index=False)
        logger.info(f"Results saved to {output_file} ({len(df)} records)")

        # Save Daily Stats
        if hasattr(self, "daily_stats") and self.daily_stats:
            stats_file = output_file.replace(".csv", "_stats.csv")
            df_stats = pd.DataFrame(self.daily_stats)
            df_stats.to_csv(stats_file, index=False)
            logger.info(f"Daily Stats saved to {stats_file}")
