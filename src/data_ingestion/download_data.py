import os
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.data_ingestion.copernicus_manager import CopernicusManager

def download_dataset_task(ds, output_dir, start_date, end_date, min_lon, max_lon, min_lat, max_lat):
    """Worker function for a single dataset download."""
    manager = CopernicusManager()
    
    # Check if target file already exists
    if os.path.exists(os.path.join(output_dir, ds["name"])):
        return f"Skipping {ds['id']} (File {ds['name']} exists)"

    print(f"--- Downloading {ds['id']} ---")
    try:
        success = manager.download_data(
            dataset_id=ds["id"],
            output_dir=output_dir,
            start_date=start_date,
            end_date=end_date,
            variables=ds["vars"],
            minimum_longitude=min_lon,
            maximum_longitude=max_lon,
            minimum_latitude=min_lat,
            maximum_latitude=max_lat,
            overwrite=True
        )
        if success:
            return f"Successfully downloaded {ds['id']}"
        else:
            return f"FAILED to download {ds['id']}"
    except Exception as e:
        return f"Exception downloading {ds['id']}: {e}"

def download_long_data():
    output_dir = "data/real_long"
    os.makedirs(output_dir, exist_ok=True)
    
    # Time Range: 2 full years (2023-2024)
    start_date = "2023-01-01"
    end_date = "2024-12-31" 
    
    # Madeira Region
    min_lon = -17.5
    max_lon = -16.0
    min_lat = 32.2
    max_lat = 33.5
    
    datasets = [
        # Physics Forecast (Daily)
        {
            "id": "cmems_mod_ibi_phy_anfc_0.027deg-3D_P1D-m", 
            "vars": ["thetao", "uo", "vo"],
            "name": "physics_2022_2023.nc" 
        },
        # Waves Forecast (Hourly)
        {
            "id": "cmems_mod_ibi_wav_anfc_0.027deg_PT1H-i", 
            "vars": ["VHM0"],
            "name": "waves_2022_2023.nc"
        },
        # BGC Forecast (Daily)
        {
            "id": "cmems_mod_ibi_bgc_anfc_0.027deg-3D_P1D-m", 
            "vars": ["chl"], 
            "name": "bgc_2022_2023.nc"
        }
    ]
    
    print("--- Starting 2023-2024 Download (Parallel) ---")
    
    # Use ThreadPoolExecutor to run downloads in parallel
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                download_dataset_task, ds, output_dir, start_date, end_date, min_lon, max_lon, min_lat, max_lat
            ): ds for ds in datasets
        }
        
        for future in as_completed(futures):
            res = future.result()
            print(res)
            results.append(res)

    # Renaming Logic
    # Map dataset ID substring to target name
    rename_map = {
        "ibi_phy": "physics_2022_2023.nc",
        "ibi_wav": "waves_2022_2023.nc",
        "ibi_bgc": "bgc_2022_2023.nc"
    }
    
    print("--- Renaming Files ---")
    files = glob.glob(os.path.join(output_dir, "*.nc"))
    for f in files:
        fname = os.path.basename(f)
        # Check against map
        for key, target in rename_map.items():
            if key in fname and target not in fname:
                target_path = os.path.join(output_dir, target)
                # Overwrite if exists
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.rename(f, target_path)
                print(f"Renamed {fname} -> {target}")
                break
                
    print("Download script complete.")

if __name__ == "__main__":
    download_long_data()
