from typing import Any

from src.simulation.agents.seal import SealAgent


def update_agent_worker(agent: SealAgent, env_buffers: dict[str, Any]) -> SealAgent:
    """
    Top-level worker function for ProcessPoolExecutor.
    Receives an agent and environment buffers (pickled),
    updates the agent state, and returns the modified agent.

    Exceptions are not caught: executor.map re-raises them in the parent, so a
    failing agent stops the run instead of silently freezing in place.
    """
    agent.update_with_buffers(env_buffers)
    return agent
