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
| **Temperature** | `IBI_MULTIYEAR_PHY_005_002` | `cmems_mod_ibi_phy-temp_my_0.027deg_P1D-m` | `thetao` | Daily, ~3km |
| **Currents** | `IBI_MULTIYEAR_PHY_005_002` | `cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m` | `uo`, `vo` | Daily, ~3km |
| **Tide (sea surface height)** | `IBI_MULTIYEAR_PHY_005_002` | `cmems_mod_ibi_phy-ssh_my_0.027deg_PT1H-m` | `zos` | Hourly, ~3km |
| **Waves** | `IBI_MULTIYEAR_WAV_005_006` | `cmems_mod_ibi_wav_my_0.027deg_PT1H-i` | `VHM0` | Hourly, ~3km |
| **Biogeochemistry** | `IBI_MULTIYEAR_BGC_005_003` | `cmems_mod_ibi_bgc-plankton_my_0.027deg_P1D-m` | `chl` | Daily, ~3km |

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
# Download all environmental data (temperature, currents, tide, waves, BGC)
uv run python -m src.data_ingestion.download_data --config madeira

# With verbose logging
uv run python -m src.data_ingestion.download_data --config madeira --verbose
```

### Output Structure

```
data/real_long/
├── physics_{tag}.nc     # thetao (temperature, all depth levels)
├── currents_{tag}.nc    # uo, vo
├── waves_{tag}.nc       # VHM0 (hourly)
├── bgc_{tag}.nc         # chl
└── ssh_{tag}.nc         # zos (hourly sea surface height, includes the tide)
```

## Tidal Model Integration

The tide is IBI hourly sea surface height (`zos`), averaged over the Desertas
(32.35–32.60°N, 16.60–16.40°W) and expressed **in metres above a fixed −0.25 m datum**
(the model's mean `zos` there). `zos` includes the tide: at the Desertas the M2
constituent (12.42 h) carries ~74% of the variance, with a ~2.5 m spring range.
The same variable exists in the analysis/forecast product, so the tide can be forecast.

```python
# From environment.py
tide = mean(zos over Desertas box) - TIDE_DATUM_M   # metres, hourly
```

**Behavioral Thresholds** (`SealConfig`, metres above mean sea level):
| Threshold | Value | Effect |
|-----------|-------|--------|
| `high_tide_m` | +0.30 | Prevent haul-out, force seals into water |
| `low_tide_m` | −0.30 | Allow haul-out to cave beaches |

These are **placeholders** pending a cave-beach height reference: they put roughly a
third of hours above and below each threshold, like the earlier normalised model.

**No silent fallback.** A run without `ssh_{tag}.nc` fails. A 12.4 h sine
(0.75 m amplitude) is available only with `--synthetic-tide`, and each run records its
tide source in `<output>_meta.json`.

> **Why not DUACS sea level anomaly?** It was used before. It is daily (a 12.4 h
> cycle cannot survive daily sampling), it is processed with the ocean tide removed, and
> it was min–max scaled per file. The environment now refuses `sla`/`adt` files.

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
