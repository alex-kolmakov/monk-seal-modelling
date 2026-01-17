
import argparse
import sys
import os
import json
from src.data_ingestion.copernicus_manager import CopernicusManager
# from src.data_ingestion.ranker import DatasetRanker

def main():
    parser = argparse.ArgumentParser(description="Monk Seal ABM Data Agent")
    parser.add_argument("--action", choices=["list", "recommend", "download"], required=True, help="Action to perform")
    parser.add_argument("--term", type=str, help="Search term for listing datasets", default=None)
    parser.add_argument("--goal", type=str, choices=["physics", "biogeochemistry"], default="physics", help="Goal for recommendation")
    parser.add_argument("--dataset_id", type=str, help="Dataset ID for download")
    parser.add_argument("--output_dir", type=str, default="data", help="Output directory for download")
    
    args = parser.parse_args()
    
    manager = CopernicusManager()
    # ranker = DatasetRanker()

    if args.action == "list":
        datasets = manager.search_datasets(keywords=[args.term])
        print(f"Found {len(datasets)} datasets.")
        for ds in datasets[:5]: # Show top 5
            print(f"- {ds.get('title', 'No Title')} ({ds.get('product_id', 'No ID')})")

    elif args.action == "recommend":
        # First get all candidate datasets (broad search based on goal)
        ignore_term = "physics" if args.goal == "physics" else "biogeochemistry" # naive term usage
        # Actually, let's search for "IBI" (Iberia-Biscay-Ireland) as a good default for this region
        datasets = manager.search_datasets(keywords=["IBI"]) 
        if not datasets:
            datasets = manager.search_datasets() # Fallback to everything
            
        # ranked = ranker.rank_datasets(datasets, args.goal)
        
        # print(f"Top 3 Recommended Datasets for {args.goal}:")
        # for i, ds in enumerate(ranked[:3]):
        #     print(f"{i+1}. {ds.get('title')} (ID: {ds.get('product_id')})")
        #     print(f"   Score: {ds.get('ranking_score')}")
        #     reasons = ds.get('ranking_reasons', [])
        #     if reasons:
        #         print(f"   Reasoning: {'; '.join(reasons)}")
        pass
            
    elif args.action == "download":
        if not args.dataset_id:
            print("Error: --dataset_id required for download")
            sys.exit(1)
            
        # Hardcoded default box for Madeira roughly
        # Madeira: ~32.7N, 17W.
        # Box: 32N to 34N, -18W to -16W
        
        print("Starting download... (This may take a while for large files)")
        success = manager.download_data(
            dataset_id=args.dataset_id,
            output_dir=args.output_dir,
            start_date="2023-01-01", # Example start
            end_date="2023-01-07",   # Example end (1 week)
            minimum_longitude=-18.0,
            maximum_longitude=-16.0,
            minimum_latitude=32.0,
            maximum_latitude=34.0
        )
        
        if success:
            print("Download successful!")
        else:
            print("Download failed.")

if __name__ == "__main__":
    main()
