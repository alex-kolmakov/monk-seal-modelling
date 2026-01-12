# Bug Report: The "Sleeping Beauty" Anomaly

## Symptom
In the 2-year simulation, agent seals were observed "sleeping" for the entire duration (or extended periods) without dying of starvation, maintaining high energy levels.

## Root Cause Analysis
Investigated `src/simulation/agents/seal.py` and identified two critical logical flaws acting in tandem:

### 1. The "Photosynthesis" Bug (Infinite Energy)
The `sleep()` method contained a legacy line that unconditionally added energy to the seal, regardless of digestion.

```python
def sleep(self, env_data, env_buffers):
    # ... check land ...
    
    # Digestion Logic (Correct)
    if self.stomach_load > 0:
        # ... digest food ...

    # THE BUG:
    self.energy += 1000.0  # <--- Seals gain 1000 kcal/hr from "thin air"
    self.energy = min(self.energy, self.max_energy)
```
**Impact**: Seals could survive indefinitely on land without ever foraging, as `1000.0` (Gain) > `rmr` (Metabolic Cost).

### 2. The "Coma" Trap (Wake-up Condition)
The logic to transition from `SLEEPING` to `FORAGING` required the seal to be **fully rested** (> 95% Energy).

```python
# Inside decide_activity()
if self.state == SealState.SLEEPING:
    # ...
    # Only wake up if Day AND Energy is essentially full
    if not is_night and self.energy > self.max_energy * 0.95:
        self.state = SealState.FORAGING
```

**Impact**: 
*   Combined with Bug #1, seals stayed at 100% energy, so they *should* have woken up. Their staying asleep implies they might have been fluctuating just below 95% or getting stuck in a logic loop.
*   **Future Risk**: If we only fixed Bug #1, seals would digest their food, lose energy, drop below 95%, and then **never wake up** (entering a starvation coma) because they wouldn't meet the "High Energy" threshold to start foraging.

## The Fix

### 1. Remove Free Energy
Deleted the `self.energy += 1000.0` line in `sleep()`. Energy is now only gained via digestion.

### 2. Liberalize Wake-up Logic
Modified the wake-up condition to allow waking up if **Hungry** (Empty Stomach) OR **Rested** (High Energy), provided it is Day.

```python
# New Logic
if not is_night:
    # Wake up if thoroughly rested OR if belly is empty (need food)
    if self.energy > self.max_energy * 0.90 or self.stomach_load == 0:
        self.state = SealState.FORAGING
```
This ensures seals wake up to forage when they run out of food, preventing the starvation coma.
