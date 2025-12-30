
import copernicusmarine
import pandas as pd
from datetime import datetime, timedelta
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CopernicusManager:
    def __init__(self):
        self.username = os.getenv("COPERNICUS_USERNAME")
        self.password = os.getenv("COPERNICUS_PASSWORD")
        # We assume credentials might also be stored in ~/.copernicusmarine/

    def list_datasets(self, search_term: str = None):
        """
        List datasets from Copernicus Marine Service matching the search term.
        """
        logger.info(f"Searching for datasets with term: {search_term}")
        try:
            # properly use 'contains' filter if provided
            contains = [search_term] if search_term else None
            catalogue = copernicusmarine.describe(contains=contains)
            
            results = []
            if hasattr(catalogue, 'products'):
                for p in catalogue.products:
                    # Convert object to dict for easier downstream handling
                    ds_dict = {
                        'title': getattr(p, 'title', ''),
                        'product_id': getattr(p, 'product_id', ''),
                        'description': getattr(p, 'description', ''),
                        # Add other relevant fields if needed
                    }
                    results.append(ds_dict)
            
            # If search term was not sent to API (e.g. if we want custom filtering), filter here.
            # But describe(contains=...) does it.
            
            return results
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            return []

    def download_data(self, dataset_id: str, output_dir: str, 
                      start_date: str = None, end_date: str = None,
                      variables: list = None,
                      minimum_longitude: float = None, maximum_longitude: float = None,
                      minimum_latitude: float = None, maximum_latitude: float = None,
                      overwrite: bool = True):
        """
        Download subset of data.
        """
        logger.info(f"Downloading {dataset_id} to {output_dir}")
        try:
            copernicusmarine.subset(
                dataset_id=dataset_id,
                output_directory=output_dir,
                start_datetime=start_date,
                end_datetime=end_date,
                variables=variables,
                minimum_latitude=minimum_latitude,
                maximum_latitude=maximum_latitude,
                overwrite=overwrite
            )
            return True
        except Exception as e:
            logger.error(f"Error downloading data: {e}")
            return False
