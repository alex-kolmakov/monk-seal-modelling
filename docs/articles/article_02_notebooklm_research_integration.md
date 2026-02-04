# From Research Papers to Code: How NotebookLM Helped Us Parameterize a Digital Monk Seal

*Building a realistic simulation isn't just about code—it's about biology. Here's how we used Google's NotebookLM to synthesize decades of monk seal research into a living knowledge base that guided every parameter choice in our model.*

---

## The Problem: Too Much Literature, Not Enough Time

When you're building an agent-based model of an endangered species, you can't just guess the parameters. Every value needs justification:

- *How much does an adult monk seal weigh?*
- *How deep do they dive when foraging?*
- *How long can a pup survive without nursing?*
- *What wave heights are lethal?*

The answers exist—scattered across decades of research papers, field studies, and conservation reports. But reading every paper, cross-referencing findings, and extracting the right numbers for your specific use case? That's a research project in itself.

We needed a way to **curate knowledge** and make it **queryable**.

---

## Enter NotebookLM: Your AI Research Partner

[NotebookLM](https://notebooklm.google.com/) is Google's AI-powered notebook that lets you upload sources (PDFs, Google Docs, URLs) and then ask questions grounded in that corpus. Unlike generic ChatGPT queries, NotebookLM's answers are **source-cited**, meaning you can trace every claim back to its origin.

For our monk seal project, we created a dedicated notebook titled **"Monk Seal Knowledge Database"** and populated it with:

- **Primary research papers** (Pires et al. 2007, 2008, 2023; Hale et al. 2011; Gazo et al. 2000)
- **Conservation reports** from the Lobo Marinho project in Madeira
- **Species profiles** from Animal Diversity Web and other databases
- **Historical population data** documenting the recovery from 6-8 individuals in the 1980s

---

## The Curation Process

### Step 1: Identify What You Need to Know

Before uploading sources randomly, we outlined the **domains** our model would need:

| Domain | Questions to Answer |
|--------|---------------------|
| **Physiology** | Body mass, stomach capacity, metabolic rates |
| **Foraging** | Dive depths, prey preferences, intake rates |
| **Behavior** | Activity patterns, tidal responses, storm avoidance |
| **Demographics** | Survival rates, reproduction, maturity timing |
| **Habitat** | Cave requirements, depth preferences, home range |
| **Threats** | Storm mortality, fishery interactions, disturbance |

### Step 2: Source High-Quality Literature

Not all sources are equal. We prioritized:

1. **Madeira-specific studies** (our target population)
2. **Peer-reviewed publications** (validated methodology)
3. **Long-term monitoring data** (not anecdotes)
4. **Recent updates** (population status has changed dramatically since 1980s)

### Step 3: Upload and Tag

NotebookLM allows you to organize sources. We tagged by topic:
- `behavior` - Activity patterns, tidal responses
- `demographics` - Survival rates, reproduction
- `foraging` - Dive behavior, prey
- `habitat` - Cave ecology, distribution

---

## Asking the Right Questions

Having a knowledge base is useless if you don't know how to query it. Here's how we approached parameter extraction:

### Pattern 1: Quantitative Parameters

```
Q: "What is the typical body mass of an adult Mediterranean monk seal?"

A: Adult females average 300kg, males 315-320kg. Range: 240-400kg.
[Source: Animal Diversity Web, Eastern Adriatic Monk Seal Project]
```

This gave us our `mass` parameter:

```python
mass: float = 300.0  # kg - Adult female body mass
```

### Pattern 2: Behavioral Thresholds

```
Q: "At what wave height do monk seals seek shelter from storms?"

A: Seals seek shelter when SWH > 2.5m. Storms are the leading cause of 
natural mortality, particularly for pups. Wave heights > 4.0m prevent 
safe hauling out.
[Source: Gazo et al. 2000, Karamanlidis et al. 2004]
```

This gave us two critical thresholds:

```python
storm_threshold: float = 2.5   # SWH (m) - Seals seek shelter
max_landing_swell: float = 4.0  # SWH (m) - Cannot safely haul out
```

### Pattern 3: Surprising Findings

Sometimes the literature contradicts intuition:

```
Q: "Are Mediterranean monk seals primarily nocturnal?"

A: In Madeira, activity patterns are TIDE-DRIVEN, not day/night driven. 
This is unlike Mediterranean populations where tides are negligible.
Activity at sea increases during high tide as rising water floods cave 
beaches and reduces haul-out space.
[Source: Pires et al. 2007]
```

This was a crucial insight. Our initial model assumed nocturnal behavior. The literature forced us to rethink:

```python
# WRONG: Diurnal/nocturnal logic
if is_night:
    state = RESTING

# RIGHT: Tidal forcing (Madeira-specific)
if tide > 0.70:  # High tide floods caves
    state = FORAGING  # Forced into water
```

---

## The Deep Dive: Counter-Intuitive Findings

Some of the most valuable insights from NotebookLM were findings that challenged our assumptions:

### 1. Tidal Forcing vs. Day/Night Cycles

Most seal simulations use day/night as the primary behavioral driver. But for Atlantic monk seals, **tides trump circadian rhythms**:

> "Seal activity at sea increases during high tide. Rising water levels inundate marine caves and reduce available haul-out space, forcing seals into the water."
> — Synthesized from Pires et al. 2007

### 2. Oligotrophic Adaptation

Madeira's waters are nutrient-poor (oligotrophic). We expected this would cause high mortality. But:

> "Despite inhabiting oligotrophic waters, adult seals exhibit survival rates (0.98 for females) comparable to those in nutrient-rich Cabo Blanco. The constraint manifests in **depressed reproductive rates and delayed maturity** rather than reduced adult survival."

This meant our model needed to cap **reproduction**, not **survival**. Seals don't starve—they just breed less often.

### 3. Cave Flooding and Pup Mortality

The mechanism of storm mortality wasn't what we expected:

> "High swells and storm surges inundate the interior beaches of marine caves. Pups can be washed into open sea, leading to drowning or separation from mothers. Pups born with lanugo (non-waterproof coat) cannot thermoregulate if forced into water before their first molt at 6-8 weeks."

This gave us specific logic for pup vulnerability tied to wave height and tide interactions.

---

## From Knowledge to Parameters

Here's how we translated research findings into the configuration file:

### Validated Parameters

| Parameter | Value | Source & Reasoning |
|-----------|-------|-------------------|
| Body Mass | 300 kg | Females average 300kg, males 315-320kg |
| Stomach Capacity | 15 kg | ~5% of body mass, allows "binge feeding" of multiple octopus |
| Daily Food Intake | 3 kg | ~1% of body mass for maintenance |
| Shallow Foraging Rate | 3.0 kg/h | 95% of dives occur at 0-50m (Hale et al. 2011) |
| Storm Threshold | 2.5m SWH | Seals seek shelter above this (Gazo et al. 2000) |
| High Tide Threshold | 0.70 | Prevents haul-out, caves flood (Pires et al. 2007) |
| Tidal Period | 12.4 hours | Standard Atlantic semidiurnal cycle |

### Derived Parameters

Some parameters required calculation from multiple sources:

```python
# RMR (Resting Metabolic Rate)
# Kleiber equation: RMR = 293 × M^0.75
# Baseline for 300kg seal: 293 × 72.08 ≈ 880 kJ/h

# But marine mammals run 1.5-2x higher (~1320-1760 kJ/h)
# Madeira population shows hypometabolism adaptation to oligotrophic waters
# We used conservative 500 kJ/h, reflecting this adaptation

rmr: float = 500.0  # kJ/h - Conservative for oligotrophic Madeira
```

### Model-Specific Parameters

Some values required calibration against observed behavior:

```python
# HSI Floor: Minimum productivity multiplier
# Madeira chlorophyll: ~0.1-0.3 mg/m³ (very low)
# Without a floor, seals would starve
# Calibrated to allow survival on 3kg/day intake

hsi_floor: float = 0.5  # Prevents starvation in oligotrophic waters
```

---

## The Documentation Link

Every parameter in our configuration file links back to research:

```python
@dataclass
class SealConfig:
    # === PHYSIOLOGY ===
    mass: float = 300.0  
    # ✅ VALIDATED: Adult females average 300kg, males 315-320kg
    # [Source: Animal Diversity Web, Eastern Adriatic Project]
    
    stomach_capacity: float = 15.0  
    # ✅ REASONABLE: ~5% of body mass. Juvenile necropsy found 
    # 1.25kg in "partially full" stomach (60kg individual)
    # [Source: Libyan Necropsy Study]
```

This traceability is crucial. When a reviewer asks "why 15kg stomach capacity?", we don't say "it felt right"—we point to the source.

---

## The NotebookLM Workflow

Here's the actual workflow we used:

```
┌─────────────────────────────────────────┐
│  1. Start Session                        │
│     Q: "Overview of monk seal physiology"│
│     → Get broad context, save session_id │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  2. Go Specific (same session)           │
│     Q: "What dive depths for foraging?"  │
│     → Cross-references previous context  │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  3. Cover Edge Cases                     │
│     Q: "What happens during storms?"     │
│     → Builds comprehensive picture       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  4. Extract Parameters                   │
│     Q: "What are the specific thresholds │
│         for storm avoidance behavior?"   │
│     → Get concrete numbers with sources  │
└─────────────────────────────────────────┘
```

The session-based approach is key. Each follow-up question has context from previous answers, allowing for deeper exploration.

---

## What We Couldn't Find

Honest research means acknowledging gaps. NotebookLM helped identify what **wasn't** in the literature:

| Gap | How We Handled It |
|-----|-------------------|
| Energy-mass conversion rates | Derived from Kleiber equation + sensitivity analysis |
| Exact digestion timing | Estimated from stomach capacity and daily intake |
| Starvation threshold | Based on general pinniped physiology (~10% body mass) |
| Optimal foraging depth transitions | Calibrated through simulation experiments |

These model-specific parameters are marked separately in our documentation:

```python
starvation_threshold: float = 0.10  
# 📊 MODEL PARAMETER: Based on general pinniped physiology
# Requires validation through sensitivity analysis
```

---

## The Living Knowledge Base

The NotebookLM notebook isn't static. As we encountered bugs (seals starving, getting stuck on land, sleeping for years), we went back to the research:

- **Bug**: Seals drift into deep water and never return
- **Query**: "What is the typical home range of Madeiran monk seals?"
- **Finding**: "Generally sedentary with ~50km home range" → Implemented island proximity boundary

- **Bug**: Seals never haul out at night
- **Query**: "Are monk seals nocturnal?"
- **Finding**: "Tide-driven, not day/night driven" → Rewrote behavior logic

The knowledge base became our debugging oracle.

---

## Lessons Learned

### 1. Curate Before You Query
Random source uploads lead to contradictory answers. Invest time in selecting high-quality, domain-specific literature.

### 2. Use Sessions for Deep Dives
Single queries give shallow answers. Multi-turn sessions with the same session_id build cumulative context.

### 3. Triangulate Findings
When NotebookLM cites a source, verify it. AI can hallucinate even with grounding. Cross-reference critical parameters.

### 4. Document the Trail
Link every parameter to its source. Your future self (and peer reviewers) will thank you.

### 5. Embrace Surprises
The most valuable findings are counterintuitive ones. When research contradicts your assumptions, trust the data.

---

## The Result: A Research-Grounded Model

Our seal agent configuration isn't arbitrary—it's a distillation of decades of monk seal research:

```python
# Default configuration for Madeira (oligotrophic environment)
MADEIRA_CONFIG = SealConfig(
    rmr=500.0,        # Lower RMR for hypometabolism adaptation
    hsi_floor=0.5,    # Higher floor for oligotrophic waters
    # ... 20+ other validated parameters
)
```

Every value tells a story, backed by citations, validated against behavior.

---

## What's Next?

With real environmental data (Article 1) and research-grounded parameters (this article), we had everything we needed to run our simulation. But the digital seals didn't cooperate. They starved. They got stuck. They slept for years.

The next article explores what we learned trying to keep our digital seals alive—and how those challenges mirror the very real struggles of this critically endangered species.

*Coming up: "The Hardest Part Wasn't the Code: Why Keeping a Digital Seal Alive Revealed Conservation Truths"*

---

## Resources

- **NotebookLM**: [notebooklm.google.com](https://notebooklm.google.com/)
- **Seal Agent Documentation**: [seal_agent_documentation.md](../seal_agent_documentation.md)
- **Key Research** (selected):
  - [Pires et al. 2007](https://www.researchgate.net/publication/254846183) - Activity patterns of the Mediterranean monk seal in the Archipelago of Madeira
  - [Pires et al. 2023](https://doi.org/10.3354/esr01270) - First demographic parameter estimates for the Mediterranean monk seal population at Madeira
  - [Hale et al. 2011](https://www.aquaticmammalsjournal.org/wp-content/uploads/2011/08/37_3_Hale.pdf) - Mediterranean monk seal fishery interactions in the Archipelago of Madeira
  - [Gazo et al. 2000](https://www.researchgate.net/publication/227717823) - Storm impacts and shelter-seeking behavior in Mediterranean monk seals
