"""
Seal Agent Configuration

Tunable parameters for the Mediterranean Monk Seal simulation.
Adjust these values to calibrate the model for different environments
(e.g., oligotrophic Madeira vs productive Cabo Blanco).
"""

from dataclasses import dataclass


@dataclass
class SealConfig:
    """Configuration parameters for seal physiology and behavior."""

    # === PHYSIOLOGY ===
    mass: float = 300.0  # kg - Adult female body mass
    stomach_capacity: float = 15.0  # kg - Maximum stomach load (~5% body mass)
    initial_energy: float = 90000.0  # Starting energy (90% of max)
    max_energy: float = 100000.0  # Maximum energy capacity

    # === METABOLIC RATES ===
    # RMR: Resting Metabolic Rate (kJ/h)
    # Kleiber baseline for 300kg: ~880 kJ/h
    # Phocid seals at rest: ~1.0–1.3× Kleiber (Lavigne et al. 1986; Bowen & Lavigne 1987)
    # 750 kJ/h ≈ 0.85× Kleiber — appropriate for subtropical phocid
    rmr: float = 750.0  # kJ/h - Phocid RMR for 300kg subtropical seal

    # AMR multiplier (Active Metabolic Rate = RMR × this factor)
    amr_multiplier: float = 1.5  # Applied during FORAGING, TRANSITING, HAULING_OUT
    recovery_metabolic_multiplier: float = 0.5  # Near-torpid RECOVERY (model assumption)

    # === FORAGING RATES (base rates, modulated by HSI) ===
    # Depth-based intake rates (kg/h) - before HSI multiplier
    shallow_foraging_rate: float = 3.0  # 0-50m depth (95% of dives occur here)
    medium_foraging_rate: float = 1.0  # 50-100m depth
    deep_foraging_rate: float = 0.0  # >100m depth (cannot reach benthos)

    # === PRODUCTIVITY MULTIPLIER ===
    # HSI = min(chlorophyll / hsi_chl_threshold, 1.0)
    # Final rate = base_rate × max(hsi_floor, HSI)
    hsi_chl_threshold: float = 0.5  # mg/m³ - Chlorophyll for HSI=1.0
    hsi_floor: float = 0.5  # Minimum multiplier (prevents starvation in oligotrophic waters)

    # === ENERGY THRESHOLDS ===
    starvation_threshold: float = 0.10  # 10% of max energy = death
    critical_energy_threshold: float = 0.15  # 15% = desperate foraging mode
    # Behavioural switches (fractions of max energy / stomach capacity; model assumptions)
    tired_energy_fraction: float = 0.20  # Below: too tired to forage, seek rest
    wake_energy_fraction: float = 0.95  # Sleeping on land with empty stomach: wake below this
    recovery_exit_fraction: float = 0.50  # RECOVERY ends above this energy
    full_stomach_fraction: float = 0.8  # Above: stop foraging and rest
    low_tide_haulout_stomach_fraction: float = 0.5  # Low tide + this full: haul out early

    # === TIDAL THRESHOLDS (metres above mean sea level, see environment.TIDE_DATUM_M) ===
    # PLACEHOLDERS: no cave-beach height reference yet [fact-check]. +/-0.30 m puts
    # ~1/3 of hours above/below at the Desertas (IBI zos, Jan-May 2026), matching the
    # share the old normalised 0.70/0.30 sine thresholds produced.
    high_tide_m: float = 0.30  # Above this, caves flood
    low_tide_m: float = -0.30  # Below this, cave beaches are exposed

    # === STORM THRESHOLDS ===
    storm_threshold: float = 2.5  # SWH (m) - Seals seek shelter
    max_landing_swell: float = 4.0  # SWH (m) - Cannot safely haul out

    # === DIGESTION ===
    digestion_rate: float = 1.0  # kg/h - Rate of stomach emptying during rest
    energy_per_kg_food: float = 3500.0  # kJ per kg of digested food


# Default configuration for Madeira (oligotrophic environment)
MADEIRA_CONFIG = SealConfig(
    rmr=750.0,  # Phocid RMR baseline; food scarcity affects behaviour, not physiology
    hsi_floor=0.5,  # Higher floor for oligotrophic waters
)
