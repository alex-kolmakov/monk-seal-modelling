# Bringing the Atlantic Ocean to Your Laptop: How We Used Copernicus Data to Simulate Monk Seal Habitat

*Building a realistic agent-based model for the critically endangered Mediterranean Monk Seal required one essential ingredient: real-world oceanographic data. Here's how we tapped into Europe's Copernicus Marine Service to bring the waters of Madeira to life.*

---

## The Challenge: Simulating Reality

When we set out to build an agent-based model (ABM) for the Mediterranean Monk Seal (*Monachus monachus*) in Madeira, we faced a fundamental question: **How do you make a digital ocean behave like the real thing?**

The answer couldn't be "make it up." These seals—one of the world's most endangered marine mammals with only 25-40 individuals remaining in Madeira—don't forage in abstract mathematical spaces. They hunt octopus on specific depth contours. They haul out on beaches only when tides permit. They avoid storms that could wash them into rocky cave walls.

We needed real data. Lots of it.

---

## Enter Copernicus: Europe's Eye on Earth

The [Copernicus Marine Service](https://marine.copernicus.eu/) is a treasure trove of oceanographic data, offering free access to reanalysis products covering decades of ocean conditions. For our purposes, we targeted the **IBI (Iberia-Biscay-Ireland)** regional model, which provides high-resolution coverage (~3km) perfect for the Madeira Archipelago.

### What We Needed

Our simulation required four distinct environmental layers:

| Category | Why We Needed It | Real-World Application |
|----------|------------------|------------------------|
| **Physics** (Temperature, Currents) | Derive bathymetry; understand habitat zones | Seals forage where temperature and depth intersect with prey availability |
| **Waves** (Significant Wave Height) | Storm detection and cave flooding | Pups are washed out of caves when SWH > 2.5m |
| **Biogeochemistry** (Chlorophyll-a) | Food availability proxy | Oligotrophic waters = less prey = different foraging strategy |
| **Tides** (Sea Surface Height) | Cave accessibility | Atlantic tides flood caves, forcing seals into water at high tide |

---

## The Discovery Process

Finding the *right* datasets in Copernicus is half the battle. The catalog contains thousands of products, each with multiple datasets at different resolutions and temporal frequencies.

### Step 1: Narrow by Region

We searched for "IBI" (Iberia-Biscay-Ireland) products, which cover the Atlantic from the Canary Islands to Ireland. The Madeira Archipelago sits at the southern edge of this domain.

```python
# Using the copernicusmarine Python package
from src.data_ingestion.copernicus_manager import CopernicusManager

manager = CopernicusManager()
products = manager.list_products(search_term="IBI MULTIYEAR")
```

### Step 2: Pick Your Poison (Reanalysis vs. Forecast)

Copernicus offers two flavors:
- **Reanalysis (MULTIYEAR)**: Historical data, consistent methodology, ideal for validation
- **Forecast (NRT)**: Near-real-time, operational predictions

We chose **reanalysis** for reproducibility. Our simulations cover 2023-2024, well within the reanalysis archive.

### Step 3: Map Variables to Datasets

Here's the tricky part: a single "product" contains multiple "datasets," each with different variables, resolutions, and time steps. We had to dig into metadata to find exactly what we needed:

| Product ID | Dataset ID | Variables | Resolution |
|------------|------------|-----------|------------|
| `IBI_MULTIYEAR_PHY_005_002` | `cmems_mod_ibi_phy_my_0.027deg_P1D-m` | `thetao`, `uo`, `vo` | Daily, ~3km |
| `IBI_MULTIYEAR_WAV_005_006` | `cmems_mod_ibi_wav_my_0.05deg_PT1H-i` | `VHM0` | Hourly, ~5km |
| `IBI_MULTIYEAR_BGC_005_003` | `cmems_mod_ibi_bgc_my_0.027deg_P1D-m` | `chl` | Daily, ~3km |
| `SEALEVEL_GLO_PHY_L4_MY_008_047` | `cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.25deg_P1D` | `adt`, `sla` | Daily, ~25km |

---

## The Implementation

### Download Configuration

We built a configuration-driven download system that makes fetching Madeira data a one-liner:

```bash
# Download all environmental data for Madeira region
uv run python -m src.data_ingestion.download_data --config madeira
```

Under the hood, this uses our `DataDownloader` class with a pre-configured region:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DownloadConfig:
    output_dir: Path
    region: RegionBounds  # Madeira: 32.0°N-33.5°N, -17.5°W--16.0°W
    time_range: TimeRange  # 2023-2024
    datasets: list[DatasetSpec]
```

### Variable Mapping: Handling Copernicus Naming Chaos

Different Copernicus products use different variable names for the same thing. Sea temperature might be `thetao`, `temp`, or `sst` depending on the product. Our `Environment` class handles this with a mapping layer:

```python
self.var_map = {
    'swh': ['VHM0', 'VAVH', 'swh'],           # Significant Wave Height
    'chl': ['CHL', 'chl'],                     # Chlorophyll-a
    'temp': ['thetao', 'temp', 'sst'],         # Sea Temperature
    'uo': ['uo'],                              # Eastward Current
    'vo': ['vo'],                              # Northward Current
}
```

This means our simulation code can simply ask for `swh` without knowing which product it came from.

---

## Deriving Bathymetry: The Hidden Trick

Here's something non-obvious: **Copernicus doesn't give you bathymetry directly** in the standard downloads. But the physics products include depth as a dimension, with temperature data at each depth level.

We derived bathymetry by finding the deepest level where temperature data exists:

```python
# For each grid cell, find maximum depth where thetao is not NaN
sample_slice = ds["thetao"].isel(time=0)
valid_mask = sample_slice.notnull()
bathymetry_map = ds["depth"].where(valid_mask).max(dim="depth")
```

The result? A 2D bathymetry map that tells us water depth at every point. This is critical for our seal agents—they forage primarily in the 0-50m zone where octopus and fish are accessible.

---

## Tidal Forcing: The Madeira Specialty

Most monk seal populations in the Mediterranean don't deal with tides—the Mediterranean has negligible tidal range. But the Madeira population sits in the Atlantic, where **12.4-hour semidiurnal tides** completely change the game.

Research from Pires et al. (2007) showed that Madeira seals are **tide-driven, not day/night driven**:
- High tide floods cave beaches → seals forced into water → activity increases
- Low tide exposes cave beaches → seals can haul out to rest → activity decreases

We implemented this as a simple sine wave:

```python
period = 12.4  # hours (semidiurnal tidal period)
tide = 0.5 * (1 + sin(2π × hours_since_epoch / period))
```

Where `tide = 0.0` represents low tide and `tide = 1.0` represents high tide.

---

## Performance: Making It Fast

Loading and querying NetCDF files with `xarray` is elegant, but when you have 50 seal agents each querying environmental data every hour for 2 years (876,000 queries), things get slow.

Our solution: **buffer pre-fetching**.

At each timestamp, we:
1. Load the current time slice into numpy arrays
2. Pre-compute grid indices for fast lookup
3. Implement index-based queries instead of xarray selection

```python
def update_buffers(self, time: pd.Timestamp):
    # Pre-fetch 2D slices for current timestamp
    for var in ['swh', 'chl', 'temp']:
        ds_t = ds.sel(time=time, method="nearest")
        self.buffers[var] = {
            "data": ds_t[var].values,  # 2D numpy array
            "lat_min": lats.min(),
            "lat_step": lats[1] - lats[0],
            # ...
        }

def query(self, lat, lon):
    # O(1) lookup via index calculation
    r_idx = int((lat - buf["lat_min"]) / buf["lat_step"])
    c_idx = int((lon - buf["lon_min"]) / buf["lon_step"])
    return buf["data"][r_idx, c_idx]
```

This reduced query time from ~10ms to ~0.01ms—a 1000x speedup.

---

## The Data Pipeline Today

After all this work, our data pipeline looks deceptively simple:

```
Copernicus Marine Service
         │
         ▼
┌─────────────────────────────────────┐
│  download_data.py (--config madeira)│
│  • Physics: temp, currents          │
│  • Waves: significant wave height   │
│  • BGC: chlorophyll-a              │
│  • Tides: sea surface height        │
└─────────────────────────────────────┘
         │
         ▼
    data/real_long/*.nc
         │
         ▼
┌─────────────────────────────────────┐
│  Environment class                   │
│  • Load NetCDF files                │
│  • Derive bathymetry                │
│  • Buffer pre-fetching              │
│  • Fast spatial queries             │
└─────────────────────────────────────┘
         │
         ▼
    Seal Agent Simulation
```

---

## Lessons Learned

1. **Real data matters**: Using actual oceanographic conditions revealed behaviors that wouldn't emerge from synthetic data—like the crucial role of tides in controlling haul-out timing.

2. **Discovery is half the work**: Finding the right Copernicus datasets took more time than downloading them. Document your choices.

3. **Name normalization is essential**: Copernicus products use inconsistent naming. Build a mapping layer early.

4. **Pre-compute what you can**: Bathymetry is static. Derive it once and cache it.

5. **Buffer for speed**: Individual xarray queries don't scale to millions of lookups. Pre-fetch entire time slices into numpy.

---

## What's Next?

With real environmental data powering our simulation, the next challenge was making our digital seals behave like real ones. That required diving deep into monk seal research—and building a knowledge base that could guide our parameter choices.

*Coming up: How we used NotebookLM to synthesize decades of monk seal research into actionable model parameters.*

---

## Resources

- **Repository**: [monk-seal-modelling](https://github.com/alex-kolmakov/monk-seal-modelling)
- **Copernicus Marine Service**: [marine.copernicus.eu](https://marine.copernicus.eu/)
- **IBI Reanalysis Products**: [Copernicus IBI Products](https://data.marine.copernicus.eu/products?q=IBI+MULTIYEAR)
- **copernicusmarine Python Package**: [PyPI](https://pypi.org/project/copernicusmarine/)
