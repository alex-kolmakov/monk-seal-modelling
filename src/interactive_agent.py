
import sys
import argparse
from src.data_ingestion.copernicus_manager import CopernicusManager
from src.data_ingestion.ranker import DatasetRanker

def interactive_session():
    print(">>> Agent: Hi! I can help you find Copernicus Marine datasets for your Monk Seal modeling.")
    print(">>> Agent: Please tell me what you are looking for (e.g., 'model seal behavior in Madeira').")
    
    # Simple interactive loop
    while True:
        try:
            user_input = input(">>> User: ")
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print(">>> Agent: Goodbye!")
                break
                
            # 1. Analyze intent
            # We no longer hardcode "physics" vs "bio". We let the ranker decide based on keywords.
            
            print(f">>> Agent: Searching for datasets relevant to: '{user_input}'...")
            
            manager = CopernicusManager()
            ranker = DatasetRanker()
            
            # Fetch candidate datasets
            # Strategy: 
            # 1. Always fetch IBI (since user is interested in Madeira)
            # 2. If user explicitly asks for "Global", we could add that, but let's start with IBI to keep it fast.
            # 3. If "Madeira" is not in IBI, we might miss it, but IBI covers it.
            
            datasets = manager.list_datasets("IBI")
            
            # Also fetch GLOBAL validation if needed, or just rely on IBI.
            # For comprehensive search, we might want to search for "Madeira" specifically if IBI didn't return good stuff?
            # But "IBI" list is a good superset.
            
            if not datasets:
                 print(">>> Agent: IBI catalog search empty, trying broader search...")
                 datasets = manager.list_datasets()
            
            # Rank using the raw user input
            ranked = ranker.rank_datasets(datasets, user_query=user_input)
            
            print(f">>> Agent: I found {len(ranked)} datasets. Here are the top 3 matches:")
            
            for i, ds in enumerate(ranked[:3]):
                title = ds.get('title')
                reasons = ds.get('ranking_reasons', [])
                product_id = ds.get('product_id')
                
                print(f"\n{i+1}. {title}")
                print(f"   ID: {product_id}")
                if reasons:
                    print(f"   Why this fits:")
                    for r in reasons:
                        print(f"   - {r}")
                else:
                    print("   (No specific keyword match, but high baseline score)")
                    
            print("\n>>> Agent: Would you like to download any of these? (Type 'download ID' or ask another question)")
            
            # Check for download command in next input? 
            # For this simple loop, we just loop back.
            # But if user says "download X", we should handle it.
            
        except KeyboardInterrupt:
            print("\n>>> Agent: Goodbye!")
            break

def main():
    interactive_session()

if __name__ == "__main__":
    main()
