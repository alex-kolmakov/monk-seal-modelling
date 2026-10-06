"""The energy budget closes: no energy is created or lost off the books.

Every agent-hour: Δenergy = Δin − Δburned − Δdiscarded − Δstored + Δmobilised.
"discarded" is surplus clipped at max_energy. With mass_dynamics it is "stored" as body
mass instead, "mobilised" is mass drawn back into energy, and Δmass × density reconciles.

Run: uv run pytest tests/unit/test_energy_budget.py -v
"""

from __future__ import annotations

import pytest

from src.simulation.agents.config import SealConfig
from src.simulation.agents.seal import SealAgent, SealState
from tests.unit.test_seal_fsm import make_sea_buffers

KJ_PER_KG = 3500.0


def seal(state: SealState = SealState.RESTING, energy: float = 50_000.0, stomach: float = 0.0,
         seed: int = 1, agent_id: str = "1", config: SealConfig | None = None) -> SealAgent:
    s = SealAgent(agent_id, start_pos=(32.5, -17.0), seed=seed, config=config)
    s.state, s.energy, s.stomach_load = state, energy, stomach
    return s


def ledger(s: SealAgent) -> tuple[float, float, float, float]:
    return s.energy, s.energy_in_kj, s.energy_burned_kj, s.energy_discarded_kj


class TestNoFreeEnergy:
    def test_rest_with_empty_stomach_gains_nothing(self):
        """rest() used to add +20 kJ every hour from nothing."""
        s = seal(SealState.RESTING, stomach=0.0)
        s.rest({"tide": 0.0, "is_land": False}, {})
        assert s.energy == 50_000.0
        assert s.energy_in_kj == 0.0

    def test_digestion_credits_only_what_is_in_the_stomach(self):
        """Less than 1 kg left used to be credited as a full 3,500 kJ."""
        s = seal(SealState.SLEEPING, stomach=0.3)
        s.sleep({"tide": 0.0, "is_land": True}, {})
        assert s.energy == pytest.approx(50_000.0 + 0.3 * KJ_PER_KG)
        assert s.stomach_load == 0.0

    def test_recovery_digests_double_rate_but_not_more_than_stomach(self):
        """RECOVERY used to credit a flat 7,000 kJ whatever was left."""
        s = seal(SealState.RECOVERY, stomach=1.5)
        s.recovery({"tide": 0.0, "is_land": False}, {})
        assert s.energy == pytest.approx(50_000.0 + 1.5 * KJ_PER_KG)

        s = seal(SealState.RECOVERY, stomach=5.0)
        s.recovery({"tide": 0.0, "is_land": False}, {})
        assert s.stomach_load == pytest.approx(3.0)
        assert s.energy == pytest.approx(50_000.0 + 2.0 * KJ_PER_KG)

    def test_surplus_above_max_energy_is_counted_not_lost(self):
        s = seal(SealState.SLEEPING, stomach=1.0)
        s.energy = s.max_energy - 1000.0
        s.sleep({"tide": 0.0, "is_land": True}, {})
        assert s.energy == s.max_energy
        assert s.energy_discarded_kj == pytest.approx(KJ_PER_KG - 1000.0)


class TestBudgetCloses:
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_every_agent_hour(self, seed):
        """Forage/rest/sleep cycles in shallow, productive water for ~3 months."""
        s = seal(SealState.FORAGING, energy=60_000.0, seed=seed, agent_id=str(seed))
        buffers = make_sea_buffers(depth=30.0, chl=0.5)

        for hour in range(2000):
            e0, in0, burn0, disc0 = ledger(s)
            s.update_with_buffers(buffers)
            e1, in1, burn1, disc1 = ledger(s)
            expected = (in1 - in0) - (burn1 - burn0) - (disc1 - disc0)
            assert e1 - e0 == pytest.approx(expected, abs=1e-6), f"hour {hour}, {s.state}"
            if s.state == SealState.DEAD:
                break

        assert s.energy_in_kj > 0, "the seal must have eaten, or the test proves nothing"
        total = s.energy_in_kj - s.energy_burned_kj - s.energy_discarded_kj
        assert s.energy - 60_000.0 == pytest.approx(total, abs=1e-3)


MASS_ON = SealConfig(mass_dynamics=True)


class TestMassDynamics:
    def test_off_by_default_surplus_is_discarded(self):
        s = seal(SealState.SLEEPING, stomach=1.0)
        s.energy = s.max_energy - 1000.0
        s.sleep({"tide": 0.0, "is_land": True}, {})
        assert s.mass == SealConfig().mass
        assert s.energy_stored_kj == 0.0

    def test_surplus_becomes_body_mass(self):
        s = seal(SealState.SLEEPING, stomach=1.0, config=MASS_ON)
        s.energy = s.max_energy - 1000.0
        s.sleep({"tide": 0.0, "is_land": True}, {})
        surplus = KJ_PER_KG - 1000.0
        assert s.energy == s.max_energy
        assert s.energy_discarded_kj == 0.0
        assert s.energy_stored_kj == pytest.approx(surplus)
        assert s.mass == pytest.approx(MASS_ON.mass + surplus / MASS_ON.tissue_energy_density)

    def test_mobilises_mass_below_critical_but_never_below_lean_mass(self):
        s = seal(config=MASS_ON)
        floor = s.max_energy * MASS_ON.critical_energy_threshold
        s.energy = floor - 5_000.0
        s._mobilise_mass()
        assert s.energy == pytest.approx(floor)
        assert s.energy_mobilised_kj == pytest.approx(5_000.0)

        s.mass = MASS_ON.lean_mass + 0.1  # only 0.1 kg left to give
        s.energy = 0.0
        s._mobilise_mass()
        assert s.mass == pytest.approx(MASS_ON.lean_mass)
        assert s.energy == pytest.approx(0.1 * MASS_ON.tissue_energy_density)

    def test_rmr_scales_with_mass(self):
        s = seal(SealState.RESTING, config=MASS_ON)
        s.mass = MASS_ON.mass * 1.2
        before = s.energy
        s.burn_energy()
        assert before - s.energy == pytest.approx(MASS_ON.rmr * 1.2**0.75)

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_budget_and_mass_close_every_agent_hour(self, seed):
        s = seal(SealState.FORAGING, energy=60_000.0, seed=seed, agent_id=str(seed),
                 config=MASS_ON)
        buffers = make_sea_buffers(depth=30.0, chl=0.5)
        density = MASS_ON.tissue_energy_density

        def book(a):
            return (a.energy, a.mass, a.energy_in_kj, a.energy_burned_kj,
                    a.energy_discarded_kj, a.energy_stored_kj, a.energy_mobilised_kj)

        for hour in range(2000):
            e0, m0, in0, b0, d0, st0, mo0 = book(s)
            s.update_with_buffers(buffers)
            e1, m1, in1, b1, d1, st1, mo1 = book(s)
            expected = (in1 - in0) - (b1 - b0) - (d1 - d0) - (st1 - st0) + (mo1 - mo0)
            assert e1 - e0 == pytest.approx(expected, abs=1e-6), f"hour {hour}, {s.state}"
            assert (m1 - m0) * density == pytest.approx((st1 - st0) - (mo1 - mo0), abs=1e-6)
            if s.state == SealState.DEAD:
                break

        assert s.energy_stored_kj > 0, "productive water must put mass on, or this proves nothing"
