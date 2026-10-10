# Seal Agent Architecture & Scientific Validation

## Overview

The `SealAgent` is the core individual-based component of the Monk Seal ABM. It simulates the decision-making, physiology, and movement of a single *Monachus monachus* individual within the Madeiran archipelago.

This document focuses on the **scientific validation** of model parameters. For implementation details and tuning guidance, see the [Model Parameters & Tuning Guide](model_parameters.md).

## Agent State Machine

The agent operates as a Finite State Machine (FSM). Transitions are driven by internal physiological variables (Energy, Stomach Load) and external environmental forcing (Tides, Storms, Food Availability).

**State Summary:**

| State | Location | Metabolic Rate | Energy Flow | Trigger to Exit |
|:------|:---------|:---------------|:------------|:----------------|
| FORAGING | Sea (0-50m) | AMR (1,584 kJ/h = 1,056 × 1.5) | Stomach ↑ | Full, tired, low tide, or critical with food → RECOVERY |
| RESTING | Sea | RMR (1,056 kJ/h) | Energy ↑ (digests 1 kg/h) | Stomach empty, or low tide |
| TRANSITING | Sea | AMR (1,584 kJ/h) | — | Reaches water / food patch |
| HAULING_OUT | Sea→Land | AMR (1,584 kJ/h) | — | Reaches land or aborts |
| SLEEPING | Land | RMR (1,056 kJ/h) | Energy ↑ (digests 1 kg/h) | High tide, or empty stomach and hungry |
| RECOVERY | Sea | 0.5 × RMR (528 kJ/h) | Energy ↑ (digests 2 kg/h) | Energy > 50%, or empty stomach above critical |
| DEAD | — | — | — | Starvation (energy ≤ 10% of max with body mass down to lean mass) or adult-male background risk |

## Scientific Validation of Parameters

Parameters are drawn from peer-reviewed research where it exists; several are model assumptions that still need field calibration (marked as such below). For tuning guidance and sensitivity analysis, see [Model Parameters & Tuning Guide](model_parameters.md).

### Parameters and Sources

Each row gives its source, or says it is a model assumption:

| Parameter | Value | Source & Notes |
|:----------|:------|:---------------|
| Body Mass | 300 kg | Adult females average 300kg, males 315-320kg. Range: 240-400kg. [Animal Diversity Web](https://animaldiversity.org/accounts/Monachus_monachus/), [Eastern Adriatic Monk Seal Project](https://adriaticmonkseal.org/biology/) |
| Fasting Reserve | body mass above 240 kg, at 20 MJ/kg, up to 400 kg | Northern elephant seal proxies ([Holser et al. 2023](https://academic.oup.com/conphys/article/11/1/coad034/7179824), [Fowler et al. 2008](https://journals.biologists.com/jeb/article/211/18/2943/17658/Hormonal-regulation-of-glucose-clearance-in)); no body composition data exist for either monk seal species (monk seal researcher, pers. comm. 2026-10-07). Checked against the 5–7 week lactation fast of Hawaiian monk seals (Johanos et al. 1994). Details in `model_parameters.md`. |
| Maintenance Intake | ~7.2 kg/day | Derived, not a parameter: RMR 1,056 kJ/h × 24 h = 25,344 kJ/day ÷ 3,500 kJ/kg. More when active (AMR). |
| Shallow Foraging (0-50m) | 3.0 kg/h | Model assumption. Base rate modulated by HSI. "95% of dives at 0-50m" is attributed to [Hale et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Hale.pdf), a fishery-interaction paper *(unverified)* |
| Foraging Depth Distribution | 95% at 0-50m *(unverified)* | Spot feeding observed <6m; only 5% exceed 50m *(unverified)*. [Hale et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Hale.pdf), [Kiraç et al. 2002](https://www.researchgate.net/publication/301657846) |
| Maximum Dive Depth | 200m *(unverified)* | Capable of 200m dives but regularly forage shallower *(unverified)*. [Eastern Adriatic Monk Seal Project](https://adriaticmonkseal.org/biology/) |
| HSI Productivity | min(chl/0.5, 1.0) | Chlorophyll modulates foraging yield. Madeira is oligotrophic (~0.1-0.3 mg/m³). |
| Swimming Speed | ~5.5 km/h | Model step of 0.05° per hour. Field ranges (max ~17 km/h; 40-81 km/day in transit, 12-14 km/day foraging) from [Adamantopoulou et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Adamantopoulou.pdf) *(unverified)* |
| Storm Threshold | 2.5m SWH | Seals seek shelter above this. Storm effects on monk seal behavior: [Gazo et al. 2000](https://www.researchgate.net/publication/227717823) *(unverified)*; specific SWH value is a model parameter requiring field calibration. Storm and high-tide flooding of inner cave beaches, washing pups out during the Oct–Dec pupping season, is described in [Pires et al. 2023](https://doi.org/10.3354/esr01260). |
| Max Landing Swell | 4.0m SWH | Physical danger of landing on rocky substrates. Model parameter requiring field calibration. [Karamanlidis et al. 2004](https://www.cambridge.org/core/journals/oryx/article/availability-of-resting-and-pupping-habitat-for-the-critically-endangered-mediterranean-monk-seal-monachus-monachus-in-the-archipelago-of-madeira/26FDF046B0B81D1A3DC707E722174931) |
| Tide | IBI hourly `zos` | Real hourly sea surface height at the Desertas (M2, 12.42 h, dominates). A 12.4 h sine is used only with `--synthetic-tide`. Sighting rates 1.5× higher at high tide, [Pires et al. 2007](https://www.researchgate.net/publication/254846183) *(unverified)* |
| High Tide Threshold | +0.30 m | Caves flood, forcing seals into water. Placeholder above mean sea level (IBI `zos`); needs a cave-beach height reference. |
| Low Tide Threshold | −0.30 m | Cave beaches accessible for haul-out. Placeholder below mean sea level (IBI `zos`); needs a cave-beach height reference. |

> **Note**: The model treats Madeira seals as tide-driven, not circadian, following [Pires et al. 2007](https://www.researchgate.net/publication/254846183) *(unverified)*. There is no day/night cycle in the model.

### Biologically Reasonable Parameters

These values lack direct monk seal measurements but are consistent with observed behavior and pinniped physiology:

| Parameter | Value | Rationale |
|:----------|:------|:----------|
| Stomach Capacity | 15 kg | ~5% of body mass. Model assumption; requires direct measurement for *M. monachus*. Madeira scat DNA shows a fish-dominated diet (conger, stingrays, morays, sea breams; [Vijayakumar et al., preprint](https://ssrn.com/abstract=7031919)). |
| AMR Multiplier | 1.5× RMR | Applied during active states. AMR typically 1.5-3× RMR in pinnipeds. Costa & Williams (1999), "Marine mammal energetics." In: Reynolds & Rommel (eds.), *Biology of Marine Mammals*, Smithsonian Institution Press, pp. 176-217. |
| Digestion Rate | 1.0 kg/h | Full stomach (15kg) requires ~15h rest. Biologically plausible for cephalopod/fish diet. |
| Medium Foraging (50-100m) | 1.0 kg/h | Reduced intake reflects lower prey density at depth. |
| Deep Foraging (>100m) | 0.0 kg/h | Cannot reach benthos. Encourages seals to seek continental shelf. |

### Model-Specific Parameters

Parameters derived from allometric equations or requiring sensitivity analysis are documented in [Model Parameters & Tuning Guide](model_parameters.md):

- **RMR** (1,056 kJ/h) — 1.20× Kleiber, calibrated against adult survival (see below)
- **Starvation Threshold** (10%) — Model assumption; only reached once the body-mass reserve is spent
- **Critical Energy Level** (15%) — Triggers desperate foraging behavior
- **Energy-per-kg conversion** (3500 kJ/kg) — Model-specific unit mapping

## Digestion Model

The model separates **Foraging** (Ingestion) from **Digestion** (Energy Assimilation) for thermodynamic realism:

- **Ingestion**: Agents fill stomach (max 15kg) based on depth/prey encounters. **No immediate energy gain.**
- **Digestion**: Energy gained only by digesting stomach contents: 1 kg/h in `RESTING` and `SLEEPING`, 2 kg/h in `RECOVERY`, at 3,500 kJ/kg.
- **Metabolic Cost**: RMR (1,056 kJ/h at 300 kg, scaling with mass^0.75) in RESTING and SLEEPING; × `amr_multiplier` (1.5) in FORAGING, TRANSITING and HAULING_OUT; × `recovery_metabolic_multiplier` (0.5) in RECOVERY.

## RMR Derivation Note

The RMR value of **1,056 kJ/h** is 1.20× the Kleiber allometric baseline:

```
RMR = 293 × M^0.75  (terrestrial baseline)
    = 293 × 300^0.75
    = 293 × 72.08
    ≈ 21,119 kJ/day ≈ 880 kJ/h (baseline)
```

Phocid seals at rest measure ~1.0–1.3× Kleiber (Lavigne et al. 1986; Bowen & Lavigne 1987) *(unverified)*. The model uses **1,056 kJ/h** (1.20×), chosen by calibration inside that range (2026-10-08; 1.10–1.30× in steps of 0.05, three seeds of 30 seals, Jan–May 2026):
1. **Body mass**: at 1.20× the median seal's gain slows to about 1 kg a month by May (median 317 kg); below it seals keep gaining, at 1.30× they lose mass.
2. **Survival**: 1 of 90 seals starves in five months, in line with adult survival 0.98 F / 0.90 M ([Pires et al. 2023](https://doi.org/10.3354/esr01260)); at 1.25× and above, 4 of 90 starve.
3. **Recalibrate when the bathymetry changes.** Starvation mostly hits seals far from feeding water on the 3 km grid, so better bathymetry will move the balance point.

The earlier value, 750 kJ/h (0.85× Kleiber, an assumed subtropical reduction), sat below the reported range and left seals gaining about 16 kg a month.

## Model Simplifications

1. **Foraging Intake Rates**: Base rates by depth band (3 kg/h shallow, 1 kg/h medium, 0 kg/h deep) × HSI × a uniform 0.5–1.5 draw per hour. The draw stands in for prey type, individual experience and patch quality, none of which is modelled.
2. **Energy Thresholds**: Starvation (10%) and critical energy (15%) thresholds based on general pinniped physiology. Require validation through sensitivity analysis and calibration against observed survival rates.
3. **Energy-Mass Conversion**: 3,500 kJ per kg of digested food is a model assumption without direct empirical validation.

## References

**Primary Sources (with direct URLs):**
- [Pires, Neves & Karamanlidis 2007](https://www.researchgate.net/publication/254846183) — Activity patterns of the Mediterranean monk seal (*Monachus monachus*) in the Archipelago of Madeira. *Aquatic Mammals* 33(3), 327-336.
- [Pires et al. 2008](https://www.cambridge.org/core/journals/oryx/article/critically-endangered-mediterranean-monk-seal-monachus-monachus-in-the-archipelago-of-madeira-priorities-for-conservation/307F69CCDC071125B306BBE9C7AC69D3) — The critically endangered Mediterranean monk seal in the Archipelago of Madeira: priorities for conservation. *Oryx* 42(2).
- [Hale et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Hale.pdf) — Mediterranean monk seal (*Monachus monachus*) fishery interactions in the Archipelago of Madeira. *Aquatic Mammals* 37(3), 298-305.
- [Gazo et al. 2000](https://www.researchgate.net/publication/227717823) — Pup survival in the Mediterranean monk seal (*Monachus monachus*) colony at Cabo Blanco Peninsula (Western Sahara-Mauritania). *Marine Mammal Science* 16(1), 158-168. *(Storm-effect detail unverified; specific SWH thresholds are model parameters.)*
- [Karamanlidis et al. 2004](https://www.cambridge.org/core/journals/oryx/article/availability-of-resting-and-pupping-habitat-for-the-critically-endangered-mediterranean-monk-seal-monachus-monachus-in-the-archipelago-of-madeira/26FDF046B0B81D1A3DC707E722174931) — Availability of resting and pupping habitat for the critically endangered Mediterranean monk seal in the Archipelago of Madeira. *Oryx* 38(2), 180-185.

- [Pires et al. 2023](https://doi.org/10.3354/esr01260) — First demographic parameter estimates for the Mediterranean monk seal population at Madeira, Portugal. *Endangered Species Research* 51, 269-283.

**Supporting Sources:**
- [Kiraç et al. 2002](https://www.researchgate.net/publication/301657846) — Observations on diving behaviour of free ranging Mediterranean monk seals (*Monachus monachus*) on Turkish coasts. *The Monachus Guardian* 5(1), 37-42.
- [Adamantopoulou et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Adamantopoulou.pdf) — Movements of Mediterranean monk seals (*Monachus monachus*) in the Eastern Mediterranean Sea. *Aquatic Mammals* 37(3), 256-261. DOI: 10.1578/AM.37.3.2011.256
- [Vijayakumar et al. (preprint, not peer reviewed)](https://ssrn.com/abstract=7031919) — Metabarcoding of Mediterranean monk seal scats from Madeira reveals a diverse piscivorous diet. SSRN 7031919.
- [Alfaghi et al. 2013](https://doi.org/10.1578/AM.39.1.2013.81) — First confirmed sighting of the Mediterranean monk seal (*Monachus monachus*) in Libya since 1972. *Aquatic Mammals* 39(1), 81-84.
- Johanos, Becker & Ragen 1994 — Annual reproductive cycle of the female Hawaiian monk seal (*Monachus schauinslandi*). *Marine Mammal Science* 10(1), 13-30. Lactation fast.
- [Holser et al. 2023](https://academic.oup.com/conphys/article/11/1/coad034/7179824) — Effects of disease on foraging behaviour and success in an individual free-ranging northern elephant seal. *Conservation Physiology* 11(1), coad034. Mass and energy gain at sea.
- [Fowler et al. 2008](https://journals.biologists.com/jeb/article/211/18/2943/17658/Hormonal-regulation-of-glucose-clearance-in) — Hormonal regulation of glucose clearance in lactating northern elephant seals (*Mirounga angustirostris*). *Journal of Experimental Biology* 211(18), 2943. Mass and blubber change in lactation.
- [Animal Diversity Web — Monachus monachus](https://animaldiversity.org/accounts/Monachus_monachus/) — Species profile with body mass data.
- [Eastern Adriatic Monk Seal Project](https://adriaticmonkseal.org/biology/) — Biology overview, dive depths.
- Costa, D.P. & Williams, T.M. (1999). Marine mammal energetics. In: Reynolds, J.E. & Rommel, S.A. (eds.), *Biology of Marine Mammals*, Smithsonian Institution Press, pp. 176-217.