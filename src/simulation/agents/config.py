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
    # Marine mammals typically 1.5-2x higher (~1320-1760 kJ/h)
    # Madeira hypothesis: hypometabolism (~0.6x due to oligotrophic environment)
    rmr: float = 500.0  # kJ/h - Conservative for oligotrophic Madeira

    # AMR multiplier (Active Metabolic Rate = RMR × this factor)
    amr_multiplier: float = 1.5  # Applied during FORAGING, TRANSITING, HAULING_OUT

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

    # === TIDAL THRESHOLDS ===
    high_tide_threshold: float = 0.70  # Tide level that floods caves
    low_tide_threshold: float = 0.30  # Tide level that exposes cave beaches

    # === STORM THRESHOLDS ===
    storm_threshold: float = 2.5  # SWH (m) - Seals seek shelter
    max_landing_swell: float = 4.0  # SWH (m) - Cannot safely haul out

    # === DIGESTION ===
    digestion_rate: float = 1.0  # kg/h - Rate of stomach emptying during rest
    energy_per_kg_food: float = 3500.0  # kJ per kg of digested food


# Default configuration for Madeira (oligotrophic environment)
MADEIRA_CONFIG = SealConfig(
    rmr=500.0,  # Lower RMR for hypometabolism
    hsi_floor=0.5,  # Higher floor for oligotrophic waters
)
