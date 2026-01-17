# Copernicus Data Retrieval & Integration

This document describes the methodology for data retrieval from Copernicus Marine Service and how environmental data is integrated into the Monk Seal ABM simulation.

## Overview

The simulation requires real-world oceanographic data to drive agent behavior. We use [Copernicus Marine Service](https://marine.copernicus.eu/) datasets covering the Madeira Archipelago region.

## Geographic Coverage

**Study Area**: Madeira Archipelago  
**Bounding Box**:
- Latitude: 32.0°N to 33.5°N
- Longitude: -17.5°W to -16.0°W

## Required Datasets

| Category | Product ID | Dataset ID | Variables | Resolution |
|----------|-----------|------------|-----------|------------|
| **Physics** | `IBI_MULTIYEAR_PHY_005_002` | `cmems_mod_ibi_phy_my_0.027deg_P1D-m` | `thetao`, `uo`, `vo` | Daily, ~3km |
| **Waves** | `IBI_MULTIYEAR_WAV_005_006` | `cmems_mod_ibi_wav_my_0.05deg_PT1H-i` | `VHM0` | Hourly, ~5km |
| **Biogeochemistry** | `IBI_MULTIYEAR_BGC_005_003` | `cmems_mod_ibi_bgc_my_0.027deg_P1D-m` | `chl` | Daily, ~3km |
| **Tidal/Sea Level** | `SEALEVEL_GLO_PHY_L4_MY_008_047` | `cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.25deg_P1D` | `adt`, `sla` | Daily, ~25km |

## Variable Mapping

The `Environment` class maps internal variable names to Copernicus variable names:

```python
self.var_map = {
    'swh': ['VHM0', 'VAVH', 'swh'],           # Significant Wave Height
    'chl': ['CHL', 'chl'],                     # Chlorophyll-a
    'temp': ['thetao', 'temp', 'sst'],         # Sea Temperature
    'uo': ['uo'],                              # Eastward Current
    'vo': ['vo'],                              # Northward Current
}
```

## Data Download

### Prerequisites

1. **Copernicus Marine Account**: Register at [marine.copernicus.eu](https://marine.copernicus.eu/)
2. **Configure Credentials**: Set `CMEMS_USERNAME` and `CMEMS_PASSWORD` environment variables, or configure `.netrc`

### Download Commands

```bash
# Download main environmental data (Physics, Waves, BGC)
uv run python -m src.data_ingestion.download_data --config madeira

# Download tidal/sea level data
uv run python -m src.data_ingestion.download_data --config tidal

# With verbose logging
uv run python -m src.data_ingestion.download_data --config madeira --verbose
```

### Output Structure

```
data/real_long/
├── cmems_mod_ibi_phy_my_*.nc     # Physics: temperature, currents
├── cmems_mod_ibi_wav_my_*.nc     # Waves: significant wave height
├── cmems_mod_ibi_bgc_my_*.nc     # BGC: chlorophyll
└── tidal_2023_2024.nc             # Tidal: sea surface height anomaly
```

## Tidal Model Integration

The simulation implements tidal forcing using a **12.4-hour semidiurnal sine wave**:

```python
# From environment.py
period = 12.4  # hours (semidiurnal tidal period)
tide = 0.5 * (1 + sin(2π × hours_since_epoch / period))
```

**Tide Values**:
- `0.0` = Low tide (caves accessible, seals haul out)
- `1.0` = High tide (caves flooded, seals forced to water)

**Behavioral Thresholds**:
| Threshold | Value | Effect |
|-----------|-------|--------|
| High Tide | 0.70 | Prevent haul-out, force seals into water |
| Low Tide | 0.30 | Allow haul-out to cave beaches |

This aligns with research showing Madeira monk seals are **tide-driven, not day/night driven** ([Pires et al. 2007](https://www.researchgate.net/publication/254846183)).

## Bathymetry Derivation

Bathymetry (sea floor depth) is derived from the physics dataset:

1. Load `thetao` (temperature) variable which has depth dimension
2. For each lat/lon cell, find maximum depth where `thetao` is not NaN
3. Create 2D bathymetry map for fast lookup during simulation

```python
# From environment.py
sample_slice = ds["thetao"].isel(time=0)
valid_mask = sample_slice.notnull()
bathymetry_map = ds["depth"].where(valid_mask).max(dim="depth")
```

## Land Detection

Land is detected using NaN values in bathymetry:
- **True Land**: Original depth = NaN, surrounded by mostly NaN cells
- **Coastline**: Original depth = NaN, but surrounded by water cells (<50% NaN neighbors)

This distinction prevents seals from getting stuck in coastline cells during navigation.

## Data Buffering Strategy

For performance, environmental data is pre-fetched into numpy arrays at each timestep:

1. **Update Buffers**: Load 2D arrays for current timestamp
2. **Fast Lookup**: Use index calculation instead of xarray selection
3. **Time Looping**: Data wraps around if simulation exceeds dataset time range

```python
# Fast index calculation for any lat/lon query
r_idx = int((lat - buf["lat_min"]) / buf["lat_step"])
c_idx = int((lon - buf["lon_min"]) / buf["lon_step"])
value = buf["data"][r_idx, c_idx]
```

## References

- [Copernicus Marine Service](https://marine.copernicus.eu/)
- [IBI Reanalysis Products](https://data.marine.copernicus.eu/products?q=IBI+MULTIYEAR)
- [copernicusmarine Python Package](https://pypi.org/project/copernicusmarine/)
