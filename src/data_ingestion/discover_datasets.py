"""
Interactive dataset discovery tool for Copernicus Marine Service.

This tool allows you to:
1. Search for datasets by keyword
2. View detailed metadata (description, coverage, variables)
3. Filter by geographic region
4. Export results to JSON

Usage:
    # Search for datasets
    python -m src.data_ingestion.discover_datasets --search "wave IBI"
    
    # Search with region filter (Madeira)
    python -m src.data_ingestion.discover_datasets --search "physics" --region madeira
    
    # Get info for specific dataset
    python -m src.data_ingestion.discover_datasets --dataset-id "cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m"
    
    # Export results
    python -m src.data_ingestion.discover_datasets --search "IBI" --export results.json
"""

import argparse
import json
from typing import Dict, List
from src.data_ingestion.copernicus_manager import CopernicusManager
from pprint import pprint

# Predefined regions
REGIONS = {
    'madeira': {
        'min_lon': -17.5,
        'max_lon': -16.0,
        'min_lat': 32.2,
        'max_lat': 33.5,
        'name': 'Madeira Archipelago'
    },
    'ibi': {
        'min_lon': -19.0,
        'max_lon': 5.0,
        'min_lat': 26.0,
        'max_lat': 56.0,
        'name': 'Iberia-Biscay-Ireland'
    }
}

def format_coverage(coverage: Dict) -> str:
    """Format coverage information for display."""
    lines = []
    
    if 'bbox' in coverage:
        bbox = coverage['bbox']
        lines.append(f"  Bounding Box:")
        lines.append(f"    Longitude: {bbox['lon_min']:.2f}°E to {bbox['lon_max']:.2f}°E")
        lines.append(f"    Latitude:  {bbox['lat_min']:.2f}°N to {bbox['lat_max']:.2f}°N")
    
    if 'time' in coverage:
        time_info = coverage['time']
        lines.append(f"  Time Range:")
        lines.append(f"    Start: {time_info['min']}")
        lines.append(f"    End:   {time_info['max']}")
        if time_info['step_days']:
            lines.append(f"    Resolution: {time_info['step_days']:.1f} days")
    
    if 'depth' in coverage:
        depth_info = coverage['depth']
        lines.append(f"  Depth:")
        lines.append(f"    Levels: {depth_info['levels']}")
        if depth_info['min'] is not None and depth_info['max'] is not None:
            lines.append(f"    Range: {depth_info['min']:.1f}m to {depth_info['max']:.1f}m")
    
    return "\n".join(lines)

def format_variables(variables: List[Dict]) -> str:
    """Format variable list for display."""
    lines = []
    for var in variables:
        name = var['short_name']
        std_name = var.get('standard_name', 'N/A')
        units = var.get('units', 'N/A')
        lines.append(f"    • {name}: {std_name} ({units})")
    return "\n".join(lines)

def display_dataset_info(info: Dict, detailed: bool = True):
    """Display dataset information in a readable format."""
    print("\n" + "="*80)
    print(f"Dataset: {info['dataset_id']}")
    print("="*80)
    print(f"Name: {info.get('dataset_name', 'N/A')}")
    print(f"Product: {info.get('product_title', 'N/A')} ({info.get('product_id', 'N/A')})")
    
    if info.get('doi'):
        print(f"DOI: {info['doi']}")
    
    if detailed and 'coverage' in info:
        print("\nCoverage:")
        print(format_coverage(info['coverage']))
    
    if detailed and 'variables' in info:
        print(f"\nVariables ({len(info['variables'])}):")
        print(format_variables(info['variables']))
    
    print()

def search_datasets(args):
    """Search for datasets."""
    manager = CopernicusManager()
    
    # Parse keywords
    keywords = args.search.split() if args.search else None
    
    # Get region
    region = None
    if args.region:
        if args.region.lower() in REGIONS:
            region = REGIONS[args.region.lower()]
            print(f"Filtering by region: {region['name']}")
        else:
            print(f"Unknown region: {args.region}")
            print(f"Available regions: {', '.join(REGIONS.keys())}")
            return
    
    print(f"Searching for datasets with keywords: {keywords}")
    print()
    
    # Search
    results = manager.search_datasets_advanced(keywords=keywords, region=region)
    
    print(f"Found {len(results)} datasets")
    print()
    
    # Display results
    for i, ds in enumerate(results[:args.limit], 1):
        print(f"{i}. {ds['dataset_id']}")
        print(f"   {ds.get('dataset_name', 'N/A')}")
        print(f"   Product: {ds.get('product_title', 'N/A')}")
        
        if 'coverage' in ds and 'bbox' in ds['coverage']:
            bbox = ds['coverage']['bbox']
            print(f"   Coverage: {bbox['lon_min']:.1f}°E-{bbox['lon_max']:.1f}°E, {bbox['lat_min']:.1f}°N-{bbox['lat_max']:.1f}°N")
        
        print()
    
    if len(results) > args.limit:
        print(f"... and {len(results) - args.limit} more datasets")
        print(f"Use --limit to show more results")
    
    # Export if requested
    if args.export:
        with open(args.export, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults exported to: {args.export}")

def get_dataset_info_cmd(args):
    """Get detailed information about a specific dataset."""
    manager = CopernicusManager()
    
    print(f"Fetching information for: {args.dataset_id}")
    info = manager.get_dataset_info(args.dataset_id)
    
    if not info:
        print(f"Dataset not found: {args.dataset_id}")
        return
    
    display_dataset_info(info, detailed=True)
    
    # Export if requested
    if args.export:
        with open(args.export, 'w') as f:
            json.dump(info, f, indent=2, default=str)
        print(f"Information exported to: {args.export}")

def get_product_info(args):
    """Get information about a product."""
    manager = CopernicusManager()
    
    print(f"Fetching information for product: {args.product_id}")
    metadata = manager.get_product_metadata(args.product_id)
    
    if not metadata:
        print(f"Product not found: {args.product_id}")
        return
    
    print("\n" + "="*80)
    print(f"Product: {metadata['product_id']}")
    print("="*80)
    print(f"Title: {metadata.get('title', 'N/A')}")
    print(f"DOI: {metadata.get('doi', 'N/A')}")
    print(f"Processing Level: {metadata.get('processing_level', 'N/A')}")
    print(f"Production Center: {metadata.get('production_center', 'N/A')}")
    
    if metadata.get('description'):
        print(f"\nDescription:")
        print(f"  {metadata['description'][:300]}...")
    
    if metadata.get('keywords'):
        print(f"\nKeywords:")
        for kw in metadata['keywords'][:10]:
            print(f"  • {kw}")
        if len(metadata['keywords']) > 10:
            print(f"  ... and {len(metadata['keywords']) - 10} more")
    
    if metadata.get('datasets'):
        print(f"\nDatasets ({len(metadata['datasets'])}):")
        for ds in metadata['datasets'][:10]:
            print(f"  • {ds['dataset_id']}")
            print(f"    {ds.get('dataset_name', 'N/A')}")
        if len(metadata['datasets']) > 10:
            print(f"  ... and {len(metadata['datasets']) - 10} more")
    
    print()
    
    # Export if requested
    if args.export:
        with open(args.export, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        print(f"Information exported to: {args.export}")

def main():
    parser = argparse.ArgumentParser(
        description='Discover and explore Copernicus Marine datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for datasets')
    search_parser.add_argument('--search', '-s', type=str, help='Search keywords (space-separated)')
    search_parser.add_argument('--region', '-r', type=str, help='Region filter (madeira, ibi)')
    search_parser.add_argument('--limit', '-l', type=int, default=10, help='Maximum results to display')
    search_parser.add_argument('--export', '-e', type=str, help='Export results to JSON file')
    
    # Dataset info command
    dataset_parser = subparsers.add_parser('dataset', help='Get dataset information')
    dataset_parser.add_argument('dataset_id', type=str, help='Dataset ID')
    dataset_parser.add_argument('--export', '-e', type=str, help='Export to JSON file')
    
    # Product info command
    product_parser = subparsers.add_parser('product', help='Get product information')
    product_parser.add_argument('product_id', type=str, help='Product ID')
    product_parser.add_argument('--export', '-e', type=str, help='Export to JSON file')
    
    # For backward compatibility, support direct arguments
    parser.add_argument('--search', type=str, help='Search keywords (deprecated, use search command)')
    parser.add_argument('--dataset-id', type=str, help='Dataset ID (deprecated, use dataset command)')
    parser.add_argument('--product-id', type=str, help='Product ID (deprecated, use product command)')
    parser.add_argument('--region', type=str, help='Region filter')
    parser.add_argument('--limit', type=int, default=10, help='Maximum results')
    parser.add_argument('--export', type=str, help='Export to JSON file')
    
    args = parser.parse_args()
    
    # Handle subcommands
    if args.command == 'search':
        search_datasets(args)
    elif args.command == 'dataset':
        get_dataset_info_cmd(args)
    elif args.command == 'product':
        get_product_info(args)
    # Backward compatibility
    elif args.dataset_id:
        get_dataset_info_cmd(args)
    elif args.product_id:
        get_product_info(args)
    elif args.search:
        search_datasets(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
