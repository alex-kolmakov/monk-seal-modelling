"""
Test the enhanced data discovery capabilities.

This script tests:
1. Dataset description extraction
2. Grid coverage extraction
3. Variable discovery
"""

from src.data_ingestion.copernicus_manager import CopernicusManager
from pprint import pprint

def test_dataset_info():
    """Test getting comprehensive dataset information."""
    print("="*80)
    print("TEST 1: Get Dataset Info")
    print("="*80)
    
    manager = CopernicusManager()
    dataset_id = "cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m"
    
    print(f"\nFetching info for: {dataset_id}")
    info = manager.get_dataset_info(dataset_id)
    
    if info:
        print("\n✓ SUCCESS: Dataset info retrieved")
        print(f"\nDataset Name: {info.get('dataset_name')}")
        print(f"Product: {info.get('product_title')}")
        
        # Check coverage
        if 'coverage' in info:
            print("\n✓ Coverage information available:")
            coverage = info['coverage']
            
            if 'bbox' in coverage:
                bbox = coverage['bbox']
                print(f"  Bounding Box: {bbox['lon_min']:.2f}°E to {bbox['lon_max']:.2f}°E, {bbox['lat_min']:.2f}°N to {bbox['lat_max']:.2f}°N")
            
            if 'time' in coverage:
                time_info = coverage['time']
                print(f"  Time Range: {time_info['min']} to {time_info['max']}")
                print(f"  Resolution: {time_info['step_days']} days")
            
            if 'depth' in coverage:
                depth_info = coverage['depth']
                print(f"  Depth Levels: {depth_info['levels']}")
                print(f"  Depth Range: {depth_info['min']:.1f}m to {depth_info['max']:.1f}m")
        
        # Check variables
        if 'variables' in info:
            print(f"\n✓ Variables available ({len(info['variables'])}):")
            for var in info['variables']:
                print(f"  - {var['short_name']}: {var.get('standard_name', 'N/A')} ({var.get('units', 'N/A')})")
    else:
        print("\n✗ FAILED: Could not retrieve dataset info")
    
    print()

def test_coverage_extraction():
    """Test extracting coverage for a dataset."""
    print("="*80)
    print("TEST 2: Get Dataset Coverage")
    print("="*80)
    
    manager = CopernicusManager()
    dataset_id = "cmems_mod_ibi_wav_my_0.027deg_PT1H-i"
    
    print(f"\nFetching coverage for: {dataset_id}")
    coverage = manager.get_dataset_coverage(dataset_id)
    
    if coverage:
        print("\n✓ SUCCESS: Coverage retrieved")
        print("\nCoverage Details:")
        pprint(coverage, indent=2, width=100)
    else:
        print("\n✗ FAILED: Could not retrieve coverage")
    
    print()

def test_variable_extraction():
    """Test extracting variables from a dataset."""
    print("="*80)
    print("TEST 3: Get Dataset Variables")
    print("="*80)
    
    manager = CopernicusManager()
    dataset_id = "cmems_mod_ibi_bgc-plankton_my_0.027deg_P1D-m"
    
    print(f"\nFetching variables for: {dataset_id}")
    variables = manager.get_dataset_variables(dataset_id)
    
    if variables:
        print(f"\n✓ SUCCESS: Found {len(variables)} variables")
        print("\nVariables:")
        for var in variables:
            print(f"  • {var['short_name']}")
            print(f"    Standard Name: {var.get('standard_name', 'N/A')}")
            print(f"    Units: {var.get('units', 'N/A')}")
    else:
        print("\n✗ FAILED: Could not retrieve variables")
    
    print()

def test_region_search():
    """Test searching datasets by region."""
    print("="*80)
    print("TEST 4: Search Datasets by Region")
    print("="*80)
    
    manager = CopernicusManager()
    
    # Madeira region
    madeira_region = {
        'min_lon': -17.5,
        'max_lon': -16.0,
        'min_lat': 32.2,
        'max_lat': 33.5
    }
    
    print(f"\nSearching for IBI datasets covering Madeira region")
    results = manager.search_datasets_advanced(
        keywords=['IBI', 'MULTIYEAR'],
        region=madeira_region
    )
    
    if results:
        print(f"\n✓ SUCCESS: Found {len(results)} datasets")
        print("\nFirst 5 results:")
        for i, ds in enumerate(results[:5], 1):
            print(f"  {i}. {ds['dataset_id']}")
            print(f"     {ds.get('dataset_name', 'N/A')}")
    else:
        print("\n✗ FAILED: No datasets found")
    
    print()

def test_product_metadata():
    """Test getting product metadata."""
    print("="*80)
    print("TEST 5: Get Product Metadata")
    print("="*80)
    
    manager = CopernicusManager()
    product_id = "IBI_MULTIYEAR_PHY_005_002"
    
    print(f"\nFetching metadata for product: {product_id}")
    metadata = manager.get_product_metadata(product_id)
    
    if metadata:
        print("\n✓ SUCCESS: Product metadata retrieved")
        print(f"\nTitle: {metadata.get('title')}")
        print(f"DOI: {metadata.get('doi')}")
        print(f"Processing Level: {metadata.get('processing_level')}")
        print(f"Number of datasets: {len(metadata.get('datasets', []))}")
        
        if metadata.get('keywords'):
            print(f"\nKeywords (first 10):")
            for kw in metadata['keywords'][:10]:
                print(f"  - {kw}")
    else:
        print("\n✗ FAILED: Could not retrieve product metadata")
    
    print()

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TESTING ENHANCED DATA DISCOVERY CAPABILITIES")
    print("="*80)
    print()
    
    try:
        test_dataset_info()
        test_coverage_extraction()
        test_variable_extraction()
        test_region_search()
        test_product_metadata()
        
        print("="*80)
        print("ALL TESTS COMPLETED")
        print("="*80)
        print()
        print("Summary:")
        print("✓ Dataset description extraction: TESTED")
        print("✓ Grid location/coverage extraction: TESTED")
        print("✓ Variable discovery: TESTED")
        print("✓ Region-based search: TESTED")
        print("✓ Product metadata: TESTED")
        print()
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
