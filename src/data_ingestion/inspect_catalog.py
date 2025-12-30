import copernicusmarine

def inspect_products():
    products = [
        "IBI_ANALYSISFORECAST_PHY_005_001", # Known good
        "IBI_ANALYSISFORECAST_WAV_005_005",
        "IBI_ANALYSISFORECAST_BGC_005_004"
    ]
    
    for pid in products:
        print(f"\n--- Inspecting Product: {pid} ---")
        try:
            # We can use describe to get details including datasets
            # The API might be 'open_dataset' or 'describe'. 
            # safe way: use the CLI functionality via command line wrapper or just print known info if available.
            # Actually, let's use the Python API if possible.
            # copernicusmarine.describe(product_id=...) prints to stdout usually.
            
            # Listing datasets directly is better if possible.
            # 'get' or 'open_dataset' requires ID.
            # let's try to just use valid catalogue access if possible.
            catalogue = copernicusmarine.describe(
                product_id=pid,
                disable_progress_bar=True
            )
            catalogue = copernicusmarine.describe(
                product_id=pid,
                disable_progress_bar=True
            )
            print(f"Type: {type(catalogue)}")
            # print(f"Dir: {dir(catalogue)}")
            
            # Try to get raw JSON if available
            if hasattr(catalogue, 'model_dump'): # Pydantic v2
                print("Dumping Pydantic model...")
                data = catalogue.model_dump()
                
                products_list = data.get('products', [])
                if products_list:
                    p_data = products_list[0]
                    datasets = p_data.get('datasets', [])
                    print(f"Datasets count: {len(datasets)}")
                    
                    for d in datasets:
                        print(f" - {d.get('dataset_id', 'No ID')}")
                        print(f"   (Name: {d.get('title') or d.get('name', 'N/A')})")
                else:
                    print("No products found in catalogue dump.")
            else:
                 print("Not a Pydantic v2 model?")
                 # Inspect attributes manually
                 print(f"Vars: {vars(catalogue).keys() if hasattr(catalogue, '__dict__') else 'No __dict__'}")
        except Exception as e:
            print(f"Error inspecting {pid}: {e}")

if __name__ == "__main__":
    inspect_products()
