"""Unit tests for the Simulation class.

TDD red phase — currently failing:
    - TestSimulationInit::test_daily_stats_initialised_in_constructor
    - TestHistoryStreaming::test_history_flushed_to_disk_after_24_steps

Run: uv run pytest tests/unit/test_simulation.py -v
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.simulation.simulation import Simulation

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def make_minimal_simulation(tmp_path: Path | None = None) -> Simulation:
    """Simulation with no agents and no env data — for structural/init tests."""
    sim = Simulation("2023-01-01", duration_days=1)
    if tmp_path:
        sim.output_file = str(tmp_path / "output.csv")
    return sim


# ─── BUG #8 — daily_stats lazy init ──────────────────────────────────────────

class TestSimulationInit:
    """Bug #8 — daily_stats is initialised lazily with hasattr() instead of in __init__."""

    def test_daily_stats_initialised_in_constructor(self):
        """daily_stats must exist immediately after construction, before any step().

        BUG — simulation.py:149:
            if not hasattr(self, "daily_stats"):
                self.daily_stats = []
            self.daily_stats.append(stat)

        Accessing sim.daily_stats before any step() raises AttributeError.
        This makes it impossible to inspect stats before the first midnight step,
        and is a code smell (object not fully initialised in __init__).

        Fix — simulation.py __init__:
            self.daily_stats: list[dict] = []
        And remove the hasattr guard in step().
        """
        sim = make_minimal_simulation()
        # Must be accessible immediately — FAILS with AttributeError currently
        assert sim.daily_stats == []

    def test_history_initialised_in_constructor(self):
        """history list must exist after construction (already correct — regression guard)."""
        sim = make_minimal_simulation()
        assert sim.history == []


# ─── BUG #10 — history grows unbounded ───────────────────────────────────────

class TestHistoryStreaming:
    """Bug #10 — self.history grows unbounded; should flush to disk every 24 steps."""

    def test_history_flushed_to_disk_after_24_steps(self, tmp_path):
        """After 24 step() calls the in-memory history must be cleared (flushed).

        BUG — simulation.py:121-132:
            self.history.append({...}) per agent per step, never cleared.
            For 200 agents × 365 days × 24h = 1.75M dicts in RAM.

        Fix:
            In step(), after recording history, if step_count % 24 == 0:
                flush self.history to output_file (append mode) and clear the list.
            Simulation.__init__ must accept and store an output_file parameter.

        Test strategy:
            - Create a Simulation with output_file=tmp_path/out.csv
            - Add one fake agent that is already dead (so the main loop skips it,
              but we can inject history rows manually via a patched step)
            - Verify history list is empty after 24 calls to step()
            - Verify the CSV file has been written to disk
        """
        output_file = str(tmp_path / "output.csv")
        sim = Simulation("2023-01-01", duration_days=5, output_file=output_file)

        # Manually populate 24 rows of history (simulating 1 day of 1 agent)
        for i in range(24):
            sim.history.append({
                "time": f"2023-01-01 {i:02d}:00:00",
                "agent_id": "0",
                "lat": 32.5, "lon": -17.0,
                "state": "FORAGING", "energy": 90000.0, "stomach": 0.0,
            })

        # Trigger a flush — the Simulation should flush when history reaches 24 entries
        sim._flush_history_if_due()   # FAILS: method does not exist yet

        # After flush: in-memory list must be empty
        assert sim.history == [], "history must be cleared after flush"

        # And the CSV must exist with 24 rows (+ 1 header)
        assert Path(output_file).exists(), "output CSV must be written to disk"
        with open(output_file) as f:
            rows = list(csv.reader(f))
        assert len(rows) == 25, f"expected header + 24 data rows, got {len(rows)}"

    def test_history_not_flushed_before_24_steps(self, tmp_path):
        """Partial history (< 24 rows) must stay in memory — not flushed prematurely."""
        output_file = str(tmp_path / "output.csv")
        sim = Simulation("2023-01-01", duration_days=5, output_file=output_file)

        for i in range(10):
            sim.history.append({"time": i, "agent_id": "0", "lat": 32.5, "lon": -17.0,
                                 "state": "FORAGING", "energy": 90000.0, "stomach": 0.0})

        sim._flush_history_if_due()

        # Only 10 rows — must NOT flush
        assert len(sim.history) == 10
        assert not Path(output_file).exists()
