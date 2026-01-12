"""
Download tidal/sea level data from Copernicus Marine Service for Madeira region.

This script downloads sea surface height data which includes tidal components.
Dataset: SEALEVEL_GLO_PHY_L4_MY_008_047 (Global Ocean Gridded L4 Sea Surface Heights)

Usage:
    python -m src.download_tidal_data
"""

import copernicusmarine
import os

def download_tidal_data():
    """Download sea level/tidal data for Madeira region (2023-2024)."""
    
    # Madeira region coordinates
    # Madeira: ~32.5°N, 16.5°W
    # Dessertas: ~32.4°N, 16.5°W
    # Add buffer around islands
    min_lat = 32.0
    max_lat = 33.5
    min_lon = -17.5
    max_lon = -16.0
    
    # Output directory
    output_dir = "data/real_long"
    os.makedirs(output_dir, exist_ok=True)
    
    # Dataset ID for sea surface height (includes tidal components)
    # This is a global gridded L4 product with daily resolution
    dataset_id = "cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.25deg_P1D"
    
    # Variables to download
    # - adt: Absolute Dynamic Topography (sea surface height above geoid)
    # - sla: Sea Level Anomaly
    variables = ["adt", "sla"]
    
    print("="*60)
    print("Downloading Tidal/Sea Level Data from Copernicus Marine Service")
    print("="*60)
    print(f"Dataset: {dataset_id}")
    print(f"Region: Madeira ({min_lat}°N-{max_lat}°N, {min_lon}°E-{max_lon}°E)")
    print(f"Period: 2023-01-01 to 2024-12-31")
    print(f"Variables: {', '.join(variables)}")
    print("="*60)
    print()
    
    output_file = os.path.join(output_dir, "tidal_2023_2024.nc")
    
    try:
        print("Initiating download...")
        copernicusmarine.subset(
            dataset_id=dataset_id,
            variables=variables,
            minimum_longitude=min_lon,
            maximum_longitude=max_lon,
            minimum_latitude=min_lat,
            maximum_latitude=max_lat,
            start_datetime="2023-01-01T00:00:00",
            end_datetime="2024-12-31T23:59:59",
            output_filename=output_file,
            force_download=True
        )
        
        print(f"\n✓ Download complete!")
        print(f"  File saved to: {output_file}")
        
        # Print file info
        import xarray as xr
        ds = xr.open_dataset(output_file)
        print(f"\n  Dataset info:")
        print(f"    Time range: {ds.time.values[0]} to {ds.time.values[-1]}")
        print(f"    Time steps: {len(ds.time)}")
        print(f"    Variables: {list(ds.data_vars)}")
        print(f"    Grid size: {len(ds.latitude)} x {len(ds.longitude)}")
        ds.close()
        
    except Exception as e:
        print(f"\n✗ Error downloading data: {e}")
        print("\nTrying alternative dataset...")
        
        # Alternative: Try the Near Real Time product
        dataset_id_nrt = "cmems_obs-sl_glo_phy-ssh_nrt_allsat-l4-duacs-0.25deg_P1D"
        
        try:
            print(f"Dataset: {dataset_id_nrt}")
            copernicusmarine.subset(
                dataset_id=dataset_id_nrt,
                variables=variables,
                minimum_longitude=min_lon,
                maximum_longitude=max_lon,
                minimum_latitude=min_lat,
                maximum_latitude=max_lat,
                start_datetime="2023-01-01T00:00:00",
                end_datetime="2024-12-31T23:59:59",
                output_filename=output_file,
                force_download=True
            )
            
            print(f"\n✓ Download complete!")
            print(f"  File saved to: {output_file}")
            
        except Exception as e2:
            print(f"\n✗ Error with alternative dataset: {e2}")
            print("\nNote: You may need to check available datasets using:")
            print("  copernicusmarine describe --include-datasets")
            return None
    
    return output_file

if __name__ == "__main__":
    download_tidal_data()
