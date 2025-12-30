# Copernicus Data Discovery Process

This document outlines the methodology used to identify and select the specific Copernicus Marine Service datasets for the Monk Seal Agent-Based Model (ABM) in the Madeira region.

## 1. Initial Search & Requirements
Our goal was to find environmental data for the Madeira Archipelago (approx. 32°N-34°N, 16°W-18°W) corresponding to:
*   **Physics**: Ocean Currents (Eastward `uo`, Northward `vo`) and Temperature (`thetao`).
*   **Waves**: Significant Wave Height (`VHM0`) for storm detection.
*   **Biogeochemistry**: Chlorophyll-a (`chl`) as a proxy for food availability.

We prioritized **Reanalysis** products (Multi-year) for consistent historical data (Jan 2023 test period) and the **IBI** (Iberia-Biscay-Ireland) region for high resolution (~0.027° or 3km).

## 2. Product Identification
Using the `copernicusmarine` CLI and Python API, we searched for "IBI" and "MULTIYEAR".

| Category | Product Title | Product ID |
| :--- | :--- | :--- |
| **Physics** | Atlantic-Iberian Biscay Irish- Ocean Physics Reanalysis | `IBI_MULTIYEAR_PHY_005_002` |
| **Waves** | Atlantic-Iberian Biscay Irish- Ocean Wave Reanalysis | `IBI_MULTIYEAR_WAV_005_006` |
| **BGC** | Atlantic-Iberian Biscay Irish- Ocean Biogeochemistry Reanalysis | `IBI_MULTIYEAR_BGC_005_003` |

## 3. Dataset Selection & Variable Mapping
A "Product" in Copernicus contains multiple "Datasets" (e.g., daily means, hourly, climatologies). We inspected the products to find the specific dataset IDs that contained our target variables at the desired temporal resolution (Daily or Hourly).

### A. Physics (Temperature)
*   **Dataset ID**: `cmems_mod_ibi_phy-temp_my_0.027deg_P1D-m`
*   **Selected Variable**: `thetao` (Sea water potential temperature)
*   **Resolution**: Daily, 0.027°

### B. Physics (Currents)
*   **Dataset ID**: `cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m`
*   **Selected Variables**: `uo`, `vo` (Eastward/Northward velocity)
*   **Resolution**: Daily, 0.027°
*   *Note: We initially attempted to use `phy-wcur` which contained Vertical Velocity (`wo`), before correcting to `phy-cur`.*

### C. Waves
*   **Dataset ID**: `cmems_mod_ibi_wav_my_0.027deg_PT1H-i`
*   **Selected Variable**: `VHM0` (Spectral significant wave height)
*   **Resolution**: Hourly, 0.027°

### D. Biogeochemistry
*   **Dataset ID**: `cmems_mod_ibi_bgc-plankton_my_0.027deg_P1D-m`
*   **Selected Variable**: `chl` (Mass concentration of chlorophyll-a)
*   **Resolution**: Daily, 0.027°

## 4. Integration Strategy
The `Environment` class in the ABM loads these NetCDF files using `xarray`. A mapping dictionary ensures that the internal simulation logic (e.g., asking for `temp`) correctly pulls from the specific variable name in the file (`thetao`).

```python
self.var_map = {
    'swh': ['VHM0', 'VAVH', 'swh'],
    'chl': ['CHL', 'chl'],
    'temp': ['thetao', 'temp'],
    'uo': ['uo'],
    'vo': ['vo']
}
```
