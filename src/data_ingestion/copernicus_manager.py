
import copernicusmarine
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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

    def get_product_metadata(self, product_id: str) -> Dict[str, Any]:
        """
        Get comprehensive metadata for a specific product.
        
        Args:
            product_id: The Copernicus product ID (e.g., 'IBI_MULTIYEAR_PHY_005_002')
            
        Returns:
            Dictionary containing product metadata including title, description, 
            DOI, keywords, and list of datasets
        """
        logger.info(f"Fetching metadata for product: {product_id}")
        try:
            catalogue = copernicusmarine.describe(
                product_id=product_id,
                disable_progress_bar=True
            )
            
            if hasattr(catalogue, 'model_dump'):
                data = catalogue.model_dump()
                products = data.get('products', [])
                
                if products:
                    product = products[0]
                    return {
                        'product_id': product.get('product_id'),
                        'title': product.get('title'),
                        'description': product.get('description'),
                        'doi': product.get('digital_object_identifier'),
                        'keywords': product.get('keywords', []),
                        'processing_level': product.get('processing_level'),
                        'production_center': product.get('production_center'),
                        'sources': product.get('sources', []),
                        'datasets': [
                            {
                                'dataset_id': ds.get('dataset_id'),
                                'dataset_name': ds.get('dataset_name')
                            }
                            for ds in product.get('datasets', [])
                        ]
                    }
            
            logger.warning(f"No metadata found for product: {product_id}")
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching product metadata: {e}")
            return {}

    def get_dataset_info(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get comprehensive information about a specific dataset.
        
        Args:
            dataset_id: The dataset ID (e.g., 'cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m')
            
        Returns:
            Dictionary containing dataset metadata, coverage, and variables
        """
        logger.info(f"Fetching info for dataset: {dataset_id}")
        
        # Search through all products to find this dataset
        try:
            # Use a broad search to find the dataset
            catalogue = copernicusmarine.describe(disable_progress_bar=True)
            
            if hasattr(catalogue, 'model_dump'):
                data = catalogue.model_dump()
                
                # Search through all products and datasets
                for product in data.get('products', []):
                    for dataset in product.get('datasets', []):
                        if dataset.get('dataset_id') == dataset_id:
                            # Found it! Extract comprehensive info
                            coverage = self._extract_coverage(dataset)
                            variables = self._extract_variables(dataset)
                            
                            return {
                                'dataset_id': dataset_id,
                                'dataset_name': dataset.get('dataset_name'),
                                'product_id': product.get('product_id'),
                                'product_title': product.get('title'),
                                'doi': dataset.get('digital_object_identifier'),
                                'coverage': coverage,
                                'variables': variables
                            }
            
            logger.warning(f"Dataset not found: {dataset_id}")
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching dataset info: {e}")
            return {}

    def get_dataset_coverage(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get spatial and temporal coverage information for a dataset.
        
        Args:
            dataset_id: The dataset ID
            
        Returns:
            Dictionary with latitude, longitude, time, and depth coverage
        """
        info = self.get_dataset_info(dataset_id)
        return info.get('coverage', {})

    def get_dataset_variables(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Get list of available variables in a dataset.
        
        Args:
            dataset_id: The dataset ID
            
        Returns:
            List of dictionaries containing variable metadata
        """
        info = self.get_dataset_info(dataset_id)
        return info.get('variables', [])

    def search_datasets_advanced(
        self, 
        keywords: List[str] = None,
        region: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """
        Advanced search for datasets with filtering.
        
        Args:
            keywords: List of keywords to search for
            region: Dictionary with 'min_lon', 'max_lon', 'min_lat', 'max_lat'
            
        Returns:
            List of matching datasets with metadata
        """
        logger.info(f"Advanced search with keywords: {keywords}, region: {region}")
        
        try:
            # Build search query
            contains = keywords if keywords else None
            catalogue = copernicusmarine.describe(
                contains=contains,
                disable_progress_bar=True
            )
            
            results = []
            
            if hasattr(catalogue, 'model_dump'):
                data = catalogue.model_dump()
                
                for product in data.get('products', []):
                    for dataset in product.get('datasets', []):
                        dataset_info = {
                            'dataset_id': dataset.get('dataset_id'),
                            'dataset_name': dataset.get('dataset_name'),
                            'product_id': product.get('product_id'),
                            'product_title': product.get('title')
                        }
                        
                        # Extract coverage for filtering
                        coverage = self._extract_coverage(dataset)
                        dataset_info['coverage'] = coverage
                        
                        # Filter by region if specified
                        if region:
                            if self._check_region_overlap(coverage, region):
                                results.append(dataset_info)
                        else:
                            results.append(dataset_info)
            
            logger.info(f"Found {len(results)} matching datasets")
            return results
            
        except Exception as e:
            logger.error(f"Error in advanced search: {e}")
            return []

    def _extract_coverage(self, dataset: Dict) -> Dict[str, Any]:
        """
        Extract coverage information from dataset metadata.
        
        Args:
            dataset: Dataset dictionary from catalogue
            
        Returns:
            Dictionary with coverage information
        """
        coverage = {}
        
        try:
            # Get the first version and part
            versions = dataset.get('versions', [])
            if not versions:
                return coverage
            
            parts = versions[0].get('parts', [])
            if not parts:
                return coverage
            
            services = parts[0].get('services', [])
            
            # Prefer 'arco-geo-series' service for most complete metadata
            target_service = None
            for service in services:
                if service.get('service_name') == 'arco-geo-series':
                    target_service = service
                    break
            
            # Fallback to first service with variables
            if not target_service:
                for service in services:
                    if service.get('variables'):
                        target_service = service
                        break
            
            if not target_service:
                return coverage
            
            # Extract from first variable (coverage is same for all)
            variables = target_service.get('variables', [])
            if not variables:
                return coverage
            
            first_var = variables[0]
            
            # Get bounding box
            bbox = first_var.get('bbox', [])
            if len(bbox) == 4:
                coverage['bbox'] = {
                    'lon_min': bbox[0],
                    'lat_min': bbox[1],
                    'lon_max': bbox[2],
                    'lat_max': bbox[3]
                }
            
            # Get detailed coordinates
            coordinates = first_var.get('coordinates', [])
            for coord in coordinates:
                coord_id = coord.get('coordinate_id')
                
                if coord_id == 'latitude':
                    coverage['latitude'] = {
                        'min': coord.get('minimum_value'),
                        'max': coord.get('maximum_value'),
                        'step': coord.get('step'),
                        'unit': coord.get('coordinate_unit')
                    }
                elif coord_id == 'longitude':
                    coverage['longitude'] = {
                        'min': coord.get('minimum_value'),
                        'max': coord.get('maximum_value'),
                        'step': coord.get('step'),
                        'unit': coord.get('coordinate_unit')
                    }
                elif coord_id == 'time':
                    # Convert milliseconds to datetime
                    min_ms = coord.get('minimum_value')
                    max_ms = coord.get('maximum_value')
                    step_ms = coord.get('step')
                    
                    coverage['time'] = {
                        'min': pd.Timestamp(min_ms, unit='ms').isoformat() if min_ms else None,
                        'max': pd.Timestamp(max_ms, unit='ms').isoformat() if max_ms else None,
                        'step_days': step_ms / 86400000.0 if step_ms else None,
                        'unit': coord.get('coordinate_unit')
                    }
                elif coord_id == 'depth':
                    depth_values = coord.get('values')
                    coverage['depth'] = {
                        'levels': len(depth_values) if depth_values else 0,
                        'min': min(depth_values) if depth_values else None,
                        'max': max(depth_values) if depth_values else None,
                        'values': depth_values,
                        'unit': coord.get('coordinate_unit')
                    }
        
        except Exception as e:
            logger.warning(f"Error extracting coverage: {e}")
        
        return coverage

    def _extract_variables(self, dataset: Dict) -> List[Dict[str, Any]]:
        """
        Extract variable information from dataset metadata.
        
        Args:
            dataset: Dataset dictionary from catalogue
            
        Returns:
            List of variable dictionaries
        """
        variables = []
        
        try:
            versions = dataset.get('versions', [])
            if not versions:
                return variables
            
            parts = versions[0].get('parts', [])
            if not parts:
                return variables
            
            services = parts[0].get('services', [])
            
            # Get variables from first service
            for service in services:
                service_vars = service.get('variables', [])
                if service_vars:
                    for var in service_vars:
                        variables.append({
                            'short_name': var.get('short_name'),
                            'standard_name': var.get('standard_name'),
                            'units': var.get('units'),
                            'bbox': var.get('bbox')
                        })
                    break  # Use first service with variables
        
        except Exception as e:
            logger.warning(f"Error extracting variables: {e}")
        
        return variables

    def _check_region_overlap(
        self, 
        coverage: Dict[str, Any], 
        region: Dict[str, float]
    ) -> bool:
        """
        Check if dataset coverage overlaps with specified region.
        
        Args:
            coverage: Dataset coverage dictionary
            region: Region bounds (min_lon, max_lon, min_lat, max_lat)
            
        Returns:
            True if there is overlap
        """
        bbox = coverage.get('bbox')
        if not bbox:
            return False
        
        # Check for overlap
        lon_overlap = (
            bbox['lon_min'] <= region['max_lon'] and
            bbox['lon_max'] >= region['min_lon']
        )
        lat_overlap = (
            bbox['lat_min'] <= region['max_lat'] and
            bbox['lat_max'] >= region['min_lat']
        )
        
        return lon_overlap and lat_overlap

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
