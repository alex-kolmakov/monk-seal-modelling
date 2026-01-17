"""
Copernicus Marine Service API Manager.

This module provides a high-level interface to the Copernicus Marine Service API
for discovering and downloading ocean data.

Example:
    >>> from src.data_ingestion.copernicus_manager import CopernicusManager
    >>> manager = CopernicusManager()
    >>> datasets = manager.search_datasets(keywords=["IBI", "physics"])
    >>> manager.download_data(
    ...     dataset_id="cmems_mod_ibi_phy_my_0.027deg_P1D-m",
    ...     output_dir="data/",
    ...     start_date="2023-01-01",
    ...     end_date="2023-12-31"
    ... )
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import copernicusmarine
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_RETRY_BACKOFF = 2.0  # exponential backoff multiplier
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


# Custom Exceptions
class CopernicusError(Exception):
    """Base exception for Copernicus-related errors."""
    pass


class CopernicusAPIError(CopernicusError):
    """Raised when the Copernicus API returns an error."""
    pass


class DatasetNotFoundError(CopernicusError):
    """Raised when a requested dataset cannot be found."""
    pass


class InvalidCoordinatesError(CopernicusError):
    """Raised when geographic coordinates are invalid."""
    pass


class InvalidDateRangeError(CopernicusError):
    """Raised when date range is invalid."""
    pass


@dataclass
class RegionBounds:
    """Geographic region bounds.
    
    Attributes:
        min_lon: Minimum longitude (-180 to 180)
        max_lon: Maximum longitude (-180 to 180)
        min_lat: Minimum latitude (-90 to 90)
        max_lat: Maximum latitude (-90 to 90)
    """
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float
    
    def __post_init__(self) -> None:
        """Validate coordinates after initialization."""
        if not (MIN_LONGITUDE <= self.min_lon <= MAX_LONGITUDE):
            raise InvalidCoordinatesError(
                f"min_lon must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}"
            )
        if not (MIN_LONGITUDE <= self.max_lon <= MAX_LONGITUDE):
            raise InvalidCoordinatesError(
                f"max_lon must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}"
            )
        if not (MIN_LATITUDE <= self.min_lat <= MAX_LATITUDE):
            raise InvalidCoordinatesError(
                f"min_lat must be between {MIN_LATITUDE} and {MAX_LATITUDE}"
            )
        if not (MIN_LATITUDE <= self.max_lat <= MAX_LATITUDE):
            raise InvalidCoordinatesError(
                f"max_lat must be between {MIN_LATITUDE} and {MAX_LATITUDE}"
            )
        if self.min_lon >= self.max_lon:
            raise InvalidCoordinatesError("min_lon must be less than max_lon")
        if self.min_lat >= self.max_lat:
            raise InvalidCoordinatesError("min_lat must be less than max_lat")


class CopernicusManager:
    """Manager for interacting with the Copernicus Marine Service API.
    
    This class provides methods for discovering datasets, retrieving metadata,
    and downloading ocean data from the Copernicus Marine Service.
    
    Attributes:
        username: Copernicus username (from environment or credentials file)
        password: Copernicus password (from environment or credentials file)
    
    Example:
        >>> manager = CopernicusManager()
        >>> results = manager.search_datasets(keywords=["temperature", "IBI"])
        >>> print(f"Found {len(results)} datasets")
    """
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """Initialize the Copernicus Manager.
        
        Args:
            username: Copernicus username. If None, uses COPERNICUS_USERNAME env var.
            password: Copernicus password. If None, uses COPERNICUS_PASSWORD env var.
        """
        self.username = username or os.getenv("COPERNICUS_USERNAME")
        self.password = password or os.getenv("COPERNICUS_PASSWORD")
        logger.debug("CopernicusManager initialized")
    
    def _retry_with_backoff(
        self,
        func: Callable,
        *args: Any,
        max_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        initial_delay: float = DEFAULT_RETRY_DELAY,
        backoff: float = DEFAULT_RETRY_BACKOFF,
        **kwargs: Any
    ) -> Any:
        """Retry a function with exponential backoff.
        
        Args:
            func: Function to retry
            *args: Positional arguments for func
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            backoff: Multiplier for delay after each attempt
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of successful function call
        
        Raises:
            CopernicusAPIError: If all retry attempts fail
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff
                else:
                    logger.error(f"All {max_attempts} attempts failed")
        
        raise CopernicusAPIError(
            f"Failed after {max_attempts} attempts: {last_exception}"
        ) from last_exception
    
    @staticmethod
    def validate_coordinates(
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float
    ) -> None:
        """Validate geographic coordinates.
        
        Args:
            min_lon: Minimum longitude
            max_lon: Maximum longitude
            min_lat: Minimum latitude
            max_lat: Maximum latitude
        
        Raises:
            InvalidCoordinatesError: If coordinates are invalid
        """
        # This will raise InvalidCoordinatesError if invalid
        RegionBounds(
            min_lon=min_lon,
            max_lon=max_lon,
            min_lat=min_lat,
            max_lat=max_lat
        )
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> None:
        """Validate date range.
        
        Args:
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
        
        Raises:
            InvalidDateRangeError: If date range is invalid
        """
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError as e:
            raise InvalidDateRangeError(
                f"Invalid date format. Use YYYY-MM-DD: {e}"
            ) from e
        
        if start >= end:
            raise InvalidDateRangeError(
                f"start_date ({start_date}) must be before end_date ({end_date})"
            )
    
    def list_products(self, search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """List products from Copernicus Marine Service.
        
        Args:
            search_term: Optional search term to filter products
        
        Returns:
            List of product dictionaries with title, product_id, and description
        
        Example:
            >>> manager = CopernicusManager()
            >>> products = manager.list_products(search_term="IBI")
            >>> print(products[0]['title'])
        """
        logger.info(f"Listing products with search term: {search_term}")
        
        def _list() -> List[Dict[str, Any]]:
            contains = [search_term] if search_term else None
            catalogue = copernicusmarine.describe(
                contains=contains,
                disable_progress_bar=True
            )
            
            results = []
            if hasattr(catalogue, 'products'):
                for product in catalogue.products:
                    results.append({
                        'title': getattr(product, 'title', ''),
                        'product_id': getattr(product, 'product_id', ''),
                        'description': getattr(product, 'description', ''),
                    })
            
            return results
        
        try:
            return self._retry_with_backoff(_list)
        except CopernicusAPIError as e:
            logger.error(f"Failed to list products: {e}")
            return []
    
    def get_product_metadata(self, product_id: str) -> Dict[str, Any]:
        """Get comprehensive metadata for a specific product.
        
        Args:
            product_id: The Copernicus product ID (e.g., 'IBI_MULTIYEAR_PHY_005_002')
        
        Returns:
            Dictionary containing product metadata including title, description,
            DOI, keywords, and list of datasets
        
        Raises:
            DatasetNotFoundError: If product is not found
        
        Example:
            >>> manager = CopernicusManager()
            >>> metadata = manager.get_product_metadata("IBI_MULTIYEAR_PHY_005_002")
            >>> print(metadata['title'])
        """
        logger.info(f"Fetching metadata for product: {product_id}")
        
        def _get_metadata() -> Dict[str, Any]:
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
            
            raise DatasetNotFoundError(f"Product not found: {product_id}")
        
        return self._retry_with_backoff(_get_metadata)
    
    def get_dataset_info(self, dataset_id: str) -> Dict[str, Any]:
        """Get comprehensive information about a specific dataset.
        
        Args:
            dataset_id: The dataset ID (e.g., 'cmems_mod_ibi_phy-cur_my_0.027deg_P1D-m')
        
        Returns:
            Dictionary containing dataset metadata, coverage, and variables
        
        Raises:
            DatasetNotFoundError: If dataset is not found
        
        Example:
            >>> manager = CopernicusManager()
            >>> info = manager.get_dataset_info("cmems_mod_ibi_phy_my_0.027deg_P1D-m")
            >>> print(info['coverage']['bbox'])
        """
        logger.info(f"Fetching info for dataset: {dataset_id}")
        
        def _get_info() -> Dict[str, Any]:
            catalogue = copernicusmarine.describe(disable_progress_bar=True)
            
            if hasattr(catalogue, 'model_dump'):
                data = catalogue.model_dump()
                
                for product in data.get('products', []):
                    for dataset in product.get('datasets', []):
                        if dataset.get('dataset_id') == dataset_id:
                            coverage = self._extract_coverage(dataset)
                            variables = self._extract_variables(dataset)
                            
                            return {
                                'dataset_id': dataset_id,
                                'dataset_name': dataset.get('dataset_name'),
                                'product_id': product.get('product_id'),
                                'product_title': product.get('title'),
                                'product_description': product.get('description'),
                                'doi': dataset.get('digital_object_identifier'),
                                'coverage': coverage,
                                'variables': variables
                            }
            
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
        
        return self._retry_with_backoff(_get_info)
    
    def get_dataset_coverage(self, dataset_id: str) -> Dict[str, Any]:
        """Get spatial and temporal coverage information for a dataset.
        
        Args:
            dataset_id: The dataset ID
        
        Returns:
            Dictionary with latitude, longitude, time, and depth coverage
        
        Example:
            >>> manager = CopernicusManager()
            >>> coverage = manager.get_dataset_coverage("cmems_mod_ibi_phy_my_0.027deg_P1D-m")
            >>> print(coverage['bbox'])
        """
        info = self.get_dataset_info(dataset_id)
        return info.get('coverage', {})
    
    def get_dataset_variables(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Get list of available variables in a dataset.
        
        Args:
            dataset_id: The dataset ID
        
        Returns:
            List of dictionaries containing variable metadata
        
        Example:
            >>> manager = CopernicusManager()
            >>> variables = manager.get_dataset_variables("cmems_mod_ibi_phy_my_0.027deg_P1D-m")
            >>> print([v['short_name'] for v in variables])
        """
        info = self.get_dataset_info(dataset_id)
        return info.get('variables', [])
    
    def search_datasets(
        self,
        keywords: Optional[List[str]] = None,
        region: Optional[RegionBounds] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Search for datasets with filtering.
        
        Args:
            keywords: List of keywords to search for
            region: Geographic region bounds for filtering
            progress_callback: Optional callback(current, total, message) for progress updates
        
        Returns:
            List of matching datasets with metadata
        
        Example:
            >>> manager = CopernicusManager()
            >>> region = RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5)
            >>> results = manager.search_datasets(keywords=["physics"], region=region)
            >>> print(f"Found {len(results)} datasets")
        """
        logger.info(f"Searching datasets with keywords: {keywords}, region: {region}")
        
        def _search() -> List[Dict[str, Any]]:
            contains = keywords if keywords else None
            catalogue = copernicusmarine.describe(
                contains=contains,
                disable_progress_bar=True
            )
            
            results = []
            
            if hasattr(catalogue, 'model_dump'):
                data = catalogue.model_dump()
                products = data.get('products', [])
                
                total_datasets = sum(
                    len(p.get('datasets', [])) for p in products
                )
                current = 0
                
                for product in products:
                    for dataset in product.get('datasets', []):
                        current += 1
                        
                        if progress_callback:
                            progress_callback(
                                current,
                                total_datasets,
                                f"Processing {dataset.get('dataset_id', 'unknown')}"
                            )
                        
                        dataset_info = {
                            'dataset_id': dataset.get('dataset_id'),
                            'dataset_name': dataset.get('dataset_name'),
                            'product_id': product.get('product_id'),
                            'product_title': product.get('title')
                        }
                        
                        coverage = self._extract_coverage(dataset)
                        dataset_info['coverage'] = coverage
                        
                        # Extract variables
                        variables = self._extract_variables(dataset)
                        dataset_info['variables'] = variables
                        
                        # Filter by region if specified
                        if region:
                            if self._check_region_overlap(coverage, region):
                                results.append(dataset_info)
                        else:
                            results.append(dataset_info)
            
            logger.info(f"Found {len(results)} matching datasets")
            return results
        
        return self._retry_with_backoff(_search)
    
    def download_data(
        self,
        dataset_id: str,
        output_dir: str | Path,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        variables: Optional[List[str]] = None,
        minimum_longitude: Optional[float] = None,
        maximum_longitude: Optional[float] = None,
        minimum_latitude: Optional[float] = None,
        maximum_latitude: Optional[float] = None,
        overwrite: bool = True
    ) -> bool:
        """Download subset of data from a dataset.
        
        Args:
            dataset_id: The dataset ID to download
            output_dir: Directory to save downloaded files
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
            variables: List of variable names to download
            minimum_longitude: Minimum longitude for spatial subset
            maximum_longitude: Maximum longitude for spatial subset
            minimum_latitude: Minimum latitude for spatial subset
            maximum_latitude: Maximum latitude for spatial subset
            overwrite: Whether to overwrite existing files
        
        Returns:
            True if download successful, False otherwise
        
        Raises:
            InvalidCoordinatesError: If coordinates are invalid
            InvalidDateRangeError: If date range is invalid
        
        Example:
            >>> manager = CopernicusManager()
            >>> success = manager.download_data(
            ...     dataset_id="cmems_mod_ibi_phy_my_0.027deg_P1D-m",
            ...     output_dir="data/",
            ...     start_date="2023-01-01",
            ...     end_date="2023-12-31",
            ...     minimum_longitude=-17.5,
            ...     maximum_longitude=-16.0,
            ...     minimum_latitude=32.2,
            ...     maximum_latitude=33.5
            ... )
        """
        logger.info(f"Downloading {dataset_id} to {output_dir}")
        
        # Validate inputs
        if start_date and end_date:
            self.validate_date_range(start_date, end_date)
        
        if all([minimum_longitude, maximum_longitude, minimum_latitude, maximum_latitude]):
            # Verify they are not None for type checker
            assert minimum_longitude is not None
            assert maximum_longitude is not None
            assert minimum_latitude is not None
            assert maximum_latitude is not None
            
            self.validate_coordinates(
                float(minimum_longitude),
                float(maximum_longitude),
                float(minimum_latitude),
                float(maximum_latitude)
            )
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        def _download() -> bool:
            copernicusmarine.subset(
                dataset_id=dataset_id,
                output_directory=str(output_path),
                start_datetime=start_date,
                end_datetime=end_date,
                variables=variables,
                minimum_longitude=minimum_longitude,
                maximum_longitude=maximum_longitude,
                minimum_latitude=minimum_latitude,
                maximum_latitude=maximum_latitude,
                overwrite=overwrite
            )
            return True
        
        try:
            return self._retry_with_backoff(_download)
        except CopernicusAPIError as e:
            logger.error(f"Failed to download data: {e}")
            return False
    
    def _extract_coverage(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Extract coverage information from dataset metadata.
        
        Args:
            dataset: Dataset dictionary from catalogue
        
        Returns:
            Dictionary with coverage information (bbox, time, depth, etc.)
        """
        coverage: Dict[str, Any] = {}
        
        try:
            versions = dataset.get('versions', [])
            if not versions:
                return coverage
            
            parts = versions[0].get('parts', [])
            if not parts:
                return coverage
            
            services = parts[0].get('services', [])
            
            # Prefer 'arco-geo-series' service
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
    
    def _extract_variables(self, dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract variable information from dataset metadata.
        
        Args:
            dataset: Dataset dictionary from catalogue
        
        Returns:
            List of variable dictionaries with short_name, standard_name, units
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
                    break
        
        except Exception as e:
            logger.warning(f"Error extracting variables: {e}")
        
        return variables
    
    def _check_region_overlap(
        self,
        coverage: Dict[str, Any],
        region: RegionBounds
    ) -> bool:
        """Check if dataset coverage overlaps with specified region.
        
        Args:
            coverage: Dataset coverage dictionary
            region: Region bounds to check against
        
        Returns:
            True if there is overlap, False otherwise
        """
        bbox = coverage.get('bbox')
        if not bbox:
            return False
        
        lon_overlap = (
            bbox['lon_min'] <= region.max_lon and
            bbox['lon_max'] >= region.min_lon
        )
        lat_overlap = (
            bbox['lat_min'] <= region.max_lat and
            bbox['lat_max'] >= region.min_lat
        )
        
        return lon_overlap and lat_overlap
