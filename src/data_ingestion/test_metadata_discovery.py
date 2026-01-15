"""
Test script to explore Copernicus Marine API metadata capabilities.

This script tests whether we can extract:
1. Dataset descriptions
2. Grid location/coverage (lat/lon bounds)
3. Available variables (columns)

Usage:
    python -m src.data_ingestion.test_metadata_discovery
"""

import copernicusmarine
import json
from pprint import pprint

def test_product_metadata():
    """Test extracting metadata from a known product."""
    
    # Use a known product from the documentation
    product_id = "IBI_MULTIYEAR_PHY_005_002"
    
    print("=" * 80)
    print(f"Testing Metadata Extraction for: {product_id}")
    print("=" * 80)
    print()
    
    try:
        # Get product catalog
        print("Fetching product catalog...")
        catalogue = copernicusmarine.describe(
            product_id=product_id,
            disable_progress_bar=True
        )
        
        print(f"✓ Catalogue type: {type(catalogue)}")
        print()
        
        # Check if it's a Pydantic model
        if hasattr(catalogue, 'model_dump'):
            print("✓ Pydantic v2 model detected")
            data = catalogue.model_dump()
            
            # Save raw structure for inspection
            with open('metadata_structure.json', 'w') as f:
                json.dump(data, f, indent=2, default=str)
            print("✓ Saved full structure to metadata_structure.json")
            print()
            
            # Extract products
            products = data.get('products', [])
            print(f"✓ Found {len(products)} product(s)")
            print()
            
            if products:
                product = products[0]
                
                # 1. DESCRIPTION
                print("-" * 80)
                print("1. DATASET DESCRIPTION")
                print("-" * 80)
                print(f"Product ID: {product.get('product_id', 'N/A')}")
                print(f"Title: {product.get('title', 'N/A')}")
                print(f"Description: {product.get('description', 'N/A')[:200]}...")
                print()
                
                # 2. DATASETS (sub-products)
                datasets = product.get('datasets', [])
                print("-" * 80)
                print(f"2. DATASETS (Found {len(datasets)})")
                print("-" * 80)
                
                for i, ds in enumerate(datasets[:3]):  # Show first 3
                    print(f"\nDataset {i+1}:")
                    print(f"  ID: {ds.get('dataset_id', 'N/A')}")
                    print(f"  Name: {ds.get('dataset_name', ds.get('title', 'N/A'))}")
                    
                    # 3. GRID COVERAGE
                    print(f"\n  Grid Coverage:")
                    coordinates = ds.get('coordinates', {})
                    
                    for coord_name in ['latitude', 'longitude', 'time', 'depth']:
                        if coord_name in coordinates:
                            coord_info = coordinates[coord_name]
                            print(f"    {coord_name.capitalize()}:")
                            
                            if isinstance(coord_info, dict):
                                # Check for min/max
                                if 'minimum_value' in coord_info:
                                    print(f"      Min: {coord_info.get('minimum_value')}")
                                if 'maximum_value' in coord_info:
                                    print(f"      Max: {coord_info.get('maximum_value')}")
                                if 'step' in coord_info:
                                    print(f"      Step: {coord_info.get('step')}")
                                if 'values' in coord_info:
                                    values = coord_info.get('values', [])
                                    if len(values) <= 5:
                                        print(f"      Values: {values}")
                                    else:
                                        print(f"      Values: {values[:3]} ... {values[-2:]} ({len(values)} total)")
                    
                    # 4. VARIABLES
                    print(f"\n  Available Variables:")
                    variables = ds.get('variables', [])
                    
                    if isinstance(variables, list):
                        for var in variables[:5]:  # Show first 5
                            if isinstance(var, dict):
                                short_name = var.get('short_name', var.get('name', 'N/A'))
                                long_name = var.get('long_name', 'N/A')
                                units = var.get('units', 'N/A')
                                print(f"    - {short_name}: {long_name} ({units})")
                        
                        if len(variables) > 5:
                            print(f"    ... and {len(variables) - 5} more")
                    
                    print()
                
                if len(datasets) > 3:
                    print(f"... and {len(datasets) - 3} more datasets")
                
        else:
            print("✗ Not a Pydantic model, exploring attributes...")
            print(f"Available attributes: {dir(catalogue)}")
            
            if hasattr(catalogue, 'products'):
                print(f"\nProducts: {catalogue.products}")
        
        print()
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print("✓ Can fetch dataset description: YES")
        print("✓ Can fetch grid location/coverage: TESTING...")
        print("✓ Can fetch available variables: TESTING...")
        print()
        print("Check metadata_structure.json for full details")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

def test_search_datasets():
    """Test searching for datasets."""
    
    print("\n" + "=" * 80)
    print("Testing Dataset Search")
    print("=" * 80)
    print()
    
    try:
        # Search for IBI products
        print("Searching for 'IBI' datasets...")
        catalogue = copernicusmarine.describe(
            contains=['IBI'],
            disable_progress_bar=True
        )
        
        if hasattr(catalogue, 'model_dump'):
            data = catalogue.model_dump()
            products = data.get('products', [])
            
            print(f"✓ Found {len(products)} products")
            print("\nFirst 5 products:")
            for i, p in enumerate(products[:5]):
                print(f"  {i+1}. {p.get('product_id')} - {p.get('title')}")
        
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    test_product_metadata()
    test_search_datasets()
