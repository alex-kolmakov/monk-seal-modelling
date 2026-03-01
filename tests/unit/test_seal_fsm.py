"""Unit tests for the SealAgent Finite State Machine.

TDD red phase — the following tests CURRENTLY FAIL (they expose real bugs):
    - TestDeathAndZombie::test_dead_agent_update_is_noop
    - TestBugMagicThresholds::test_sleep_wakes_at_config_high_tide_threshold
    - TestBugHauloutMemoryContamination::test_forage_does_not_contaminate_haulout_memory

All other tests are GREEN and document the intended, working behaviour.

Run:
    uv run pytest tests/unit/test_seal_fsm.py -v
    uv run pytest tests/unit/test_seal_fsm.py -v -k "red"   # failing tests only
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from src.simulation.agents.config import SealConfig
from src.simulation.agents.seal import SealAgent, SealState

# ─── GRID CONSTANTS ──────────────────────────────────────────────────────────
# Single reference point inside Madeira study area.
# 3×3 grid of 1° cells keeps any 0.05° movement step well within bounds.
_LAT = 32.5
_LON = -17.0
_STEP = 1.0


# ─── FIXTURE HELPERS ─────────────────────────────────────────────────────────

def _buf(data: np.ndarray, lat: float = _LAT, lon: float = _LON) -> dict:
    """Wrap a 2-D array into the buffer format expected by query_env_buffers."""
    rows, cols = data.shape
    return {
        "data": data,
        "lat_min": lat - (rows // 2) * _STEP,
        "lat_step": _STEP,
        "lon_min": lon - (cols // 2) * _STEP,
        "lon_step": _STEP,
        "shape": (rows, cols),
    }


def make_sea_buffers(
    tide: float = 0.5,
    swh: float = 0.5,
    depth: float = 30.0,
    chl: float = 0.5,
) -> dict:
    """3×3 open-water env_buffers centred at (_LAT, _LON).

    Note: `tide` is a top-level scalar in env_buffers, NOT a nested array —
    see environment/utils.py:109 where it is read as buffers.get("tide", 0.5).
    """
    return {
        "swh":   _buf(np.full((3, 3), swh)),
        "depth": _buf(np.full((3, 3), depth)),   # non-NaN → water
        "chl":   _buf(np.full((3, 3), chl)),
        "tide":  tide,
    }


def make_land_buffers(tide: float = 0.3, swh: float = 0.5) -> dict:
    """3×3 land env_buffers — all-NaN depth means query_env_buffers sets is_land=True.

    A 3×3 all-NaN neighbourhood means nan_count/total_count = 1.0 ≥ 0.5,
    so the land-detection logic in utils.py correctly flags this as true land
    (not a coastline cell).
    """
    return {
        "swh":   _buf(np.full((3, 3), swh)),
        "depth": _buf(np.full((3, 3), np.nan)),
        "tide":  tide,
    }


def make_seal(
    state: SealState = SealState.FORAGING,
    energy_pct: float = 0.9,
    stomach_load: float = 0.0,
    age: int = 6,
    config: SealConfig | None = None,
) -> SealAgent:
    """Deterministic SealAgent at the centre of the test grid.

    age=6 selects adult foraging mode (is_adult = age >= 6).
    distance_to_land=5.0 keeps the seal inside the normal ≤12 km boundary,
    preventing the boundary-return branch from firing inside forage().
    """
    cfg = config or SealConfig()
    seal = SealAgent("test", start_pos=(_LAT, _LON), age=age, config=cfg)
    seal.state = state
    seal.energy = seal.max_energy * energy_pct
    seal.stomach_load = stomach_load
    seal.distance_to_land = 5.0   # within island proximity boundary
    seal.debug = False             # suppress log output during tests
    return seal


# ─── FSM TRANSITION TESTS (green) ────────────────────────────────────────────

class TestForagingTransitions:
    """State transitions triggered from the FORAGING state."""

    def test_foraging_to_hauling_out_when_full_at_low_tide(self):
        """Full stomach + low tide → seize haul-out opportunity.

        decide_activity:L291 — tide < low_tide_threshold AND stomach > 50%
        capacity → HAULING_OUT.
        """
        seal = make_seal(state=SealState.FORAGING, stomach_load=12.0)  # 80% of 15 kg
        env_data = {"tide": 0.2, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.HAULING_OUT

    def test_foraging_to_resting_when_full_at_mid_tide(self):
        """Full stomach + mid tide → rest in water (no haul-out possible yet).

        is_full uses strict > 0.8 × capacity (12.0 kg), so we need 13.0 kg
        to actually trigger the satiety branch.
        """
        seal = make_seal(state=SealState.FORAGING, stomach_load=13.0)  # strictly > 0.8×15
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.RESTING

    def test_foraging_continues_when_desperate(self):
        """Critically low energy overrides all transitions — seal keeps eating."""
        seal = make_seal(state=SealState.FORAGING, energy_pct=0.12, stomach_load=0.05)
        env_data = {"tide": 0.2, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING


class TestSleepingTransitions:
    """State transitions triggered from the SLEEPING state."""

    def test_sleeping_wakes_when_hungry_on_land(self):
        """Empty stomach on land → wake and forage (energy < 95% of max)."""
        seal = make_seal(state=SealState.SLEEPING, energy_pct=0.8, stomach_load=0.0)
        env_data = {"tide": 0.4, "swh": 0.5, "is_land": True}
        seal.decide_activity(env_data, is_night=False, is_land=True)
        assert seal.state == SealState.FORAGING

    def test_sleeping_continues_when_full_on_safe_land(self):
        """Full stomach on safe land → keep sleeping."""
        seal = make_seal(state=SealState.SLEEPING, energy_pct=0.9, stomach_load=10.0)
        env_data = {"tide": 0.4, "swh": 0.5, "is_land": True}
        seal.decide_activity(env_data, is_night=False, is_land=True)
        assert seal.state == SealState.SLEEPING


class TestTideForcing:
    """Tidal forcing overrides all other state logic."""

    def test_high_tide_cancels_haul_out_attempt_in_water(self):
        """HAULING_OUT in water + high tide → forced back to FORAGING."""
        seal = make_seal(state=SealState.HAULING_OUT)
        env_data = {"tide": 0.8, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING

    def test_high_tide_evacuates_sleeping_seal_from_land(self):
        """SLEEPING on land at high tide → forced evacuation (TRANSITING)."""
        seal = make_seal(state=SealState.SLEEPING)
        env_data = {"tide": 0.8, "swh": 0.5, "is_land": True}
        seal.decide_activity(env_data, is_night=False, is_land=True)
        assert seal.state == SealState.TRANSITING

    def test_resting_uses_config_low_tide_threshold_for_haul_out(self):
        """decide_activity reads low_tide_threshold from config, not a magic number.

        With threshold=0.40, a tide of 0.35 (below threshold) triggers
        HAULING_OUT from RESTING. This verifies the config-driven path in
        decide_activity:L259, which is already correct.
        """
        config = SealConfig(low_tide_threshold=0.40)
        seal = make_seal(state=SealState.RESTING, config=config)
        env_data = {"tide": 0.35, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.HAULING_OUT


class TestStormForcing:
    """Storm/swell conditions override normal state behaviour."""

    def test_storm_aborts_haul_out_above_max_landing_swell(self):
        """SWH > max_landing_swell (4.0 m) aborts haul-out attempt → TRANSITING.

        Must test on land: in open water, decide_activity immediately follows up
        TRANSITING → FORAGING ("safe in water"), so the assertion would see
        FORAGING instead of TRANSITING.  On land, the TRANSITING branch keeps
        the seal in TRANSITING state (it's still escaping).
        """
        seal = make_seal(state=SealState.HAULING_OUT, energy_pct=0.9)
        buffers = make_land_buffers(swh=5.0, tide=0.4)   # on land + extreme swell
        seal.update_with_buffers(buffers)
        assert seal.state == SealState.TRANSITING

    def test_storm_triggers_haul_out_from_open_water(self):
        """Storm swell (above storm_threshold 2.5 m) forces seal to seek land."""
        seal = make_seal(state=SealState.FORAGING, energy_pct=0.9)
        buffers = make_sea_buffers(swh=3.0, tide=0.4)   # 3.0 > storm_threshold=2.5
        seal.update_with_buffers(buffers)
        assert seal.state == SealState.HAULING_OUT


# ─── DEATH AND ZOMBIE GUARD TESTS ────────────────────────────────────────────

class TestDeathAndZombie:
    """Starvation, mortality, and zombie-guard behaviour."""

    def test_starvation_triggers_dead_state(self):
        """Energy below 10% of max → seal dies of starvation.

        burn_energy() runs first each tick; at 9% energy the post-burn check
        at update_with_buffers:L136 sets state=DEAD and returns.
        """
        seal = make_seal(state=SealState.FORAGING, energy_pct=0.09)
        seal.update_with_buffers(make_sea_buffers())
        assert seal.state == SealState.DEAD

    def test_dead_agent_decide_activity_preserves_dead_state(self):
        """decide_activity must be a no-op for dead agents under any conditions."""
        seal = make_seal(state=SealState.DEAD, energy_pct=0.5)
        env_data = {"tide": 0.2, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.DEAD

    # ── RED ──────────────────────────────────────────────────────────────────

    def test_dead_agent_update_is_noop(self):
        """update_with_buffers must be a complete no-op for already-dead agents.

        BUG — simulation.py:110 / seal.py:180:
            Both guards compare agent.state == "DEAD" (a plain string).
            SealState is a plain Enum, not StrEnum, so SealState.DEAD != "DEAD".
            The guards therefore never fire: dead agents keep running every tick,
            burn energy, and inflate the active-agent population count.

        Fix (both files):
            if self.state == SealState.DEAD: return   # seal.py:180
            if agent.state == SealState.DEAD: continue  # simulation.py:110

        Additionally, guard the top of update_with_buffers so that direct
        unit-test calls on a dead agent are also safe:
            if self.state == SealState.DEAD: return   # update_with_buffers top
        """
        seal = make_seal(state=SealState.DEAD, energy_pct=0.9)
        initial_energy = seal.energy
        initial_pos = seal.pos

        seal.update_with_buffers(make_sea_buffers())

        assert seal.state == SealState.DEAD, "dead agent must not change state"
        assert seal.energy == initial_energy, "dead agent must not burn energy"   # FAILS
        assert seal.pos == initial_pos, "dead agent must not move"


# ─── BUG TESTS (red) ─────────────────────────────────────────────────────────

class TestRecoveryState:
    """#5 — RECOVERY state: entry, action (enhanced digestion), and exit logic."""

    def test_recovery_entered_from_foraging_when_critical_with_food(self):
        """Seal with critical energy but food in stomach enters RECOVERY instead of foraging.

        Entry condition: energy < 15% of max AND stomach_load > 0
        (the desperation branch would keep foraging with empty stomach, but a seal
        with food already in its stomach should stop and digest — that's RECOVERY).

        Fix — seal.py decide_activity FORAGING branch:
            Add: if energy < critical AND stomach_load > 0 → RECOVERY
        """
        seal = make_seal(state=SealState.FORAGING, energy_pct=0.12, stomach_load=5.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.RECOVERY   # FAILS: no RECOVERY entry implemented

    def test_recovery_continues_while_critical_and_digesting(self):
        """Seal stays in RECOVERY while energy < 50% and stomach still has food."""
        seal = make_seal(state=SealState.RECOVERY, energy_pct=0.30, stomach_load=3.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.RECOVERY   # FAILS: no RECOVERY branch in decide_activity

    def test_recovery_exits_to_foraging_when_healthy(self):
        """RECOVERY seal with energy > 50% transitions back to FORAGING."""
        seal = make_seal(state=SealState.RECOVERY, energy_pct=0.60, stomach_load=2.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING   # FAILS

    def test_recovery_action_digests_faster_than_resting(self):
        """recovery() must digest food faster than rest() — 2× digestion rate.

        Biological rationale: a seal in critical recovery prioritises digestion
        by minimising activity (no movement, enhanced gut motility).
        """
        # Rest baseline
        seal_r = make_seal(state=SealState.RESTING, stomach_load=5.0, energy_pct=0.5)
        energy_before_r = seal_r.energy
        seal_r.rest({"tide": 0.5, "is_land": False}, {})
        rest_energy_gain = seal_r.energy - energy_before_r

        # Recovery
        seal_rec = make_seal(state=SealState.RECOVERY, stomach_load=5.0, energy_pct=0.5)
        energy_before_rec = seal_rec.energy
        seal_rec.recovery({"tide": 0.5, "is_land": False}, {})   # FAILS: method missing
        recovery_energy_gain = seal_rec.energy - energy_before_rec

        assert recovery_energy_gain > rest_energy_gain, (
            "recovery() must convert food to energy faster than rest()"
        )

    def test_recovery_does_not_move(self):
        """recovery() action must not change the agent's position."""
        seal = make_seal(state=SealState.RECOVERY, stomach_load=3.0)
        initial_pos = seal.pos
        seal.recovery({"tide": 0.5, "is_land": False}, {})   # FAILS: method missing
        assert seal.pos == initial_pos

    def test_recovery_exits_when_stomach_empty_above_critical(self):
        """RECOVERY seal with empty stomach and energy > critical must forage to refill.

        Without food in the stomach, recovery() provides no energy gain while
        burn_energy() still drains 0.5×RMR each hour. This is guaranteed starvation
        — the seal must re-enter FORAGING to refill before continuing recovery.
        """
        seal = make_seal(state=SealState.RECOVERY, energy_pct=0.25, stomach_load=0.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING, (
            "RECOVERY seal with empty stomach must forage to refill, not starve in place"
        )

    def test_recovery_burns_at_half_rmr(self):
        """RECOVERY seals burn 0.5×RMR per hour (near-torpid), not 1.0×RMR.

        Halving the metabolic cost during RECOVERY doubles the digestion window —
        giving a starving seal with food in its stomach enough time to convert
        stomach contents into energy before reaching the death threshold.
        """
        import pytest
        seal = make_seal(state=SealState.RECOVERY, energy_pct=0.40)
        energy_before = seal.energy
        seal.burn_energy()
        energy_after = seal.energy
        expected_burn = seal.rmr * 0.5
        assert energy_after == pytest.approx(energy_before - expected_burn), (
            f"RECOVERY should burn 0.5×RMR={expected_burn:.1f} kJ/h, "
            f"got {energy_before - energy_after:.1f}"
        )


class TestBugMagicThresholds:
    """Bug #2 — sleep() uses hardcoded 0.75 instead of config.high_tide_threshold."""

    def test_sleep_wakes_at_config_high_tide_threshold(self):
        """sleep() must honour config.high_tide_threshold, not the magic 0.75.

        With high_tide_threshold=0.60, tide=0.70 exceeds the configured limit
        and must wake the seal.  The current hardcoded 0.75 causes the seal to
        stay asleep (0.70 < 0.75), silently ignoring the researcher's config.

        Fix — seal.py:993:
            if is_land and tide > 0.75:
            →  if is_land and tide > self.config.high_tide_threshold:
        """
        config = SealConfig(high_tide_threshold=0.60)
        seal = make_seal(state=SealState.SLEEPING, config=config)
        env_data = {"tide": 0.70, "is_land": True}

        seal.sleep(env_data, {})

        # 0.70 > config threshold 0.60 → must wake to FORAGING
        assert seal.state == SealState.FORAGING   # FAILS (0.70 < hardcoded 0.75)


class TestBugHauloutMemoryContamination:
    """Bug #3 — forage() contaminates memory.haulout_sites with foraging positions."""

    def test_forage_does_not_contaminate_haulout_memory(self):
        """Successful foraging must never write positions to memory.haulout_sites.

        BUG — seal.py:909:
            forage() appends the current foraging position (open water) to
            haulout_sites after every successful meal.  When the seal later
            searches for land to haul out, it navigates toward these open-water
            coordinates instead of actual beaches.

        Demonstrates the bug:
            1. Seal starts with empty haulout_sites.
            2. Seal forages successfully in shallow water.
            3. Bug: haulout_sites is now non-empty (open-water coords stored).

        Fix — seal.py:905–916:
            Remove the haulout_sites.append block from forage() entirely.
            Haul-out memory is correctly updated in decide_activity:L219-226
            when HAULING_OUT → SLEEPING transition occurs on land.

        Patching strategy:
            random.random → 0.1  forces should_move=False (seal stays in patch,
                                  since 0.1 < stay_prob=0.9 for depth≤50m)
            random.uniform → 1.0 gives deterministic mass_gain so the seal
                                  always eats (stomach_load increases)
        """
        seal = make_seal(state=SealState.FORAGING, stomach_load=0.0, energy_pct=0.9)
        seal.memory.haulout_sites.clear()

        buffers = make_sea_buffers(depth=30.0, chl=0.5)
        env_data = {"depth": 30.0, "is_land": False, "swh": 0.5, "hsi": 0.5}

        with patch("random.random", return_value=0.1):
            with patch("random.uniform", return_value=1.0):
                seal.forage(env_data, buffers)

        # Sanity-check: food was actually gained (ensures the buggy path runs)
        assert seal.stomach_load > 0, "seal must have eaten (fixture sanity check)"

        # The actual assertion — FAILS with current code
        assert seal.memory.haulout_sites == [], (
            "foraging positions must not be stored as haul-out sites"
        )


# ─── STARVATION TRAP TESTS ────────────────────────────────────────────────────

class TestStarvationTraps:
    """Critical-energy escape from RESTING and SLEEPING (bottling) states.

    Without these overrides a seal at ~12-14% energy with an empty stomach
    could remain in RESTING/SLEEPING for up to one tidal half-cycle (~6h)
    before a natural tide transition, losing up to ~3,000 kJ and crossing
    the 10% death threshold.
    """

    def test_resting_escapes_when_critical_and_empty_stomach(self):
        """RESTING seal with critical energy and empty stomach must start foraging.

        Fix — decide_activity RESTING block:
            Added: if stomach_load == 0 and energy < critical_threshold → FORAGING
        """
        seal = make_seal(state=SealState.RESTING, energy_pct=0.12, stomach_load=0.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING, (
            "critically starving RESTING seal with empty stomach must transition to FORAGING"
        )

    def test_resting_forages_when_stomach_empty_moderate_energy(self):
        """RESTING seal with empty stomach must forage regardless of energy level.

        RESTING's sole purpose is digestion.  When stomach_load == 0, digestion is
        complete and the seal should return to FORAGING even at moderate (50%) energy.
        The old 90%-threshold left seals trapped in RESTING until starvation.
        """
        seal = make_seal(state=SealState.RESTING, energy_pct=0.50, stomach_load=0.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False, "depth": 30.0}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING, (
            "RESTING seal with empty stomach must transition to FORAGING (digestion complete)"
        )

    def test_bottling_escapes_when_critical_and_empty_stomach(self):
        """Bottling (SLEEPING in water) seal with critical energy and empty stomach
        must wake and forage — it cannot recover without food.

        Fix — decide_activity SLEEPING bottling block:
            Added: if stomach_load == 0 and energy < critical_threshold → FORAGING
        """
        seal = make_seal(state=SealState.SLEEPING, energy_pct=0.12, stomach_load=0.0)
        # Bottling: is_land=False, tide mid-range (no tidal transition firing)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.FORAGING, (
            "critically starving bottling seal with empty stomach must transition to FORAGING"
        )

    def test_bottling_stays_when_exhausted_with_food(self):
        """Bottling seal at 12% energy but with food in stomach stays sleeping to digest.

        The RECOVERY state handles the active-digestion case when energy is
        critical AND the seal is foraging.  A bottling seal with food is already
        getting passive digestion — it should not be disturbed.
        """
        seal = make_seal(state=SealState.SLEEPING, energy_pct=0.12, stomach_load=5.0)
        env_data = {"tide": 0.5, "swh": 0.5, "is_land": False}
        seal.decide_activity(env_data, is_night=False, is_land=False)
        assert seal.state == SealState.SLEEPING, (
            "bottling seal with food in stomach should keep sleeping to digest"
        )
