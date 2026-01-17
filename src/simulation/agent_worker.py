from typing import Any

from src.simulation.agents.seal import SealAgent


def update_agent_worker(agent: SealAgent, env_buffers: dict[str, Any]) -> SealAgent:
    """
    Top-level worker function for ProcessPoolExecutor.
    Receives an agent and environment buffers (pickled),
    updates the agent state, and returns the modified agent.
    """
    try:
        # Pass the buffers directly to the new update method
        agent.update_with_buffers(env_buffers)
        return agent
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error in agent worker {agent.id}: {e}")
        return agent
