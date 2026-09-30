"""Deaths are recorded, runs are reproducible, outputs are never silently appended.

Runs here use no data files (agents on defaults) and the synthetic tide, so they
exercise the simulation loop without downloads.

Run: uv run pytest tests/unit/test_deaths_and_reproducibility.py -v
"""

from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.simulation.agent_worker import update_agent_worker
from src.simulation.agents.seal import SealAgent, SealState
from src.simulation.simulation import Simulation

START = "2026-03-01"


def void_sim(tmp_path: Path, name: str, seed: int | None = 42, days: int = 2, agents: int = 6,
             **kwargs) -> Simulation:
    sim = Simulation(START, duration_days=days, output_file=str(tmp_path / name),
                     synthetic_tide=True, seed=seed, **kwargs)
    sim.create_agents(num_agents=agents)
    return sim


def run_to_bytes(sim: Simulation, workers: int) -> bytes:
    sim.run(max_workers=workers)
    sim.save_results()
    return Path(sim.output_file).read_bytes()


class AlwaysZeroRng:
    """Stand-in for np.random.Generator (whose methods are read-only)."""

    def random(self) -> float:
        return 0.0


def read_rows(path: str) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


class TestDeathsRecorded:
    def test_starving_agent_gets_one_dead_row_with_cause(self, tmp_path):
        sim = void_sim(tmp_path, "out.csv", agents=2)
        starving = sim.agents[0]
        starving.energy = starving.max_energy * 0.10 + 1.0  # next burn crosses the line

        with ThreadPoolExecutor(1) as ex:
            for _ in range(3):
                sim.step(ex)
                sim.current_time += sim.time_step

        rows = [r for r in sim.history if r["agent_id"] == starving.id]
        assert [r["state"] for r in rows] == ["DEAD"], "one DEAD row, then no more rows"
        assert rows[0]["death_cause"] == "starvation"
        assert [a.id for a in sim.agents] == [sim.agents[0].id] and len(sim.agents) == 1

    def test_daily_stats_count_deaths_and_reconcile(self, tmp_path):
        sim = void_sim(tmp_path, "out.csv", agents=3)
        for agent in sim.agents[:2]:
            agent.energy = agent.max_energy * 0.10 + 1.0

        with ThreadPoolExecutor(1) as ex:
            for _ in range(25):  # midnight stat on step 0 and step 24
                sim.step(ex)
                sim.current_time += sim.time_step

        first, second = sim.daily_stats
        assert first["n_deaths_today"] == 2 and first["total_agents"] == 1
        assert second["n_deaths_today"] == 0 and second["n_deaths_total"] == 2
        assert 3 - second["total_agents"] == second["n_deaths_total"]

    def test_male_risk_death_is_labelled(self):
        seal = SealAgent("7", start_pos=(32.5, -16.5), age=10, sex="M", seed=1)
        seal.rng = AlwaysZeroRng()  # pyrefly: ignore  # force the 1e-5 draw to hit

        seal.update_with_buffers({"tide": 0.0})

        assert seal.state == SealState.DEAD
        assert seal.death_cause == "male_risk"


class TestReproducibility:
    def test_same_seed_is_byte_identical_for_any_worker_count(self, tmp_path):
        one = run_to_bytes(void_sim(tmp_path, "w1.csv"), workers=1)
        four = run_to_bytes(void_sim(tmp_path, "w4.csv"), workers=4)

        assert one == four

    def test_different_seed_changes_the_run(self, tmp_path):
        """Guard: without this, the identity test above could pass vacuously."""
        a = run_to_bytes(void_sim(tmp_path, "s1.csv", seed=1), workers=2)
        b = run_to_bytes(void_sim(tmp_path, "s2.csv", seed=2), workers=2)

        assert a != b

    def test_agent_stream_depends_only_on_seed_and_id(self):
        a = SealAgent("3", start_pos=(32.5, -16.5), seed=42)
        b = SealAgent("3", start_pos=(32.5, -16.5), seed=42)
        c = SealAgent("4", start_pos=(32.5, -16.5), seed=42)

        assert a.heading == b.heading
        assert a.rng.random(5).tolist() == b.rng.random(5).tolist()
        assert a.heading != c.heading

    def test_unseeded_run_records_the_seed_it_drew(self, tmp_path):
        sim = void_sim(tmp_path, "u.csv", seed=None)
        assert isinstance(sim.seed, int)


class TestOutputFiles:
    def test_rerun_refuses_to_append(self, tmp_path):
        run_to_bytes(void_sim(tmp_path, "out.csv", days=1), workers=1)

        with pytest.raises(FileExistsError):
            void_sim(tmp_path, "out.csv", days=1).run(max_workers=1)

    def test_overwrite_replaces_instead_of_appending(self, tmp_path):
        first = run_to_bytes(void_sim(tmp_path, "out.csv", days=1), workers=1)
        again = run_to_bytes(void_sim(tmp_path, "out.csv", days=1, overwrite=True), workers=1)

        assert again == first
        assert len(read_rows(str(tmp_path / "out.csv"))) == 6 * 24


class TestWorkerFailures:
    def test_worker_exception_propagates(self):
        seal = SealAgent("0", start_pos=(32.5, -16.5), seed=1)

        def boom(_buffers):
            raise RuntimeError("agent bug")

        seal.update_with_buffers = boom  # pyrefly: ignore
        with pytest.raises(RuntimeError, match="agent bug"):
            update_agent_worker(seal, {})
