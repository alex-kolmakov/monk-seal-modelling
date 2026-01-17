"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import Mock, MagicMock
from src.data_ingestion.copernicus_manager import CopernicusManager, RegionBounds


@pytest.fixture
def mock_manager():
    """Create a mock CopernicusManager."""
    manager = Mock(spec=CopernicusManager)
    return manager


@pytest.fixture
def sample_region():
    """Sample region bounds for Madeira."""
    return RegionBounds(
        min_lon=-17.5,
        max_lon=-16.0,
        min_lat=32.2,
        max_lat=33.5
    )


@pytest.fixture
def sample_dataset_info():
    """Sample dataset information."""
    return {
        'dataset_id': 'cmems_mod_ibi_phy_my_0.027deg_P1D-m',
        'dataset_name': 'Atlantic-Iberian Biscay Irish- Ocean Physics Reanalysis',
        'product_id': 'IBI_MULTIYEAR_PHY_005_002',
        'product_title': 'Atlantic-Iberian Biscay Irish- Ocean Physics Reanalysis',
        'coverage': {
            'bbox': {
                'lon_min': -19.0,
                'lat_min': 26.0,
                'lon_max': 5.0,
                'lat_max': 56.0
            },
            'time': {
                'min': '1993-01-01T00:00:00',
                'max': '2023-12-31T23:59:59',
                'step_days': 1.0
            }
        },
        'variables': [
            {'short_name': 'thetao', 'standard_name': 'sea_water_potential_temperature', 'units': 'degrees_C'},
            {'short_name': 'uo', 'standard_name': 'eastward_sea_water_velocity', 'units': 'm/s'},
            {'short_name': 'vo', 'standard_name': 'northward_sea_water_velocity', 'units': 'm/s'},
        ]
    }


@pytest.fixture
def sample_search_results():
    """Sample search results."""
    return [
        {
            'dataset_id': 'cmems_mod_ibi_phy_my_0.027deg_P1D-m',
            'dataset_name': 'Physics Dataset',
            'product_id': 'IBI_MULTIYEAR_PHY_005_002',
            'product_title': 'IBI Physics',
            'coverage': {
                'bbox': {'lon_min': -19.0, 'lat_min': 26.0, 'lon_max': 5.0, 'lat_max': 56.0}
            },
            'variables': [{'short_name': 'thetao'}]
        },
        {
            'dataset_id': 'cmems_mod_ibi_wav_my_0.05deg_PT1H-i',
            'dataset_name': 'Waves Dataset',
            'product_id': 'IBI_MULTIYEAR_WAV_005_006',
            'product_title': 'IBI Waves',
            'coverage': {
                'bbox': {'lon_min': -19.0, 'lat_min': 26.0, 'lon_max': 5.0, 'lat_max': 56.0}
            },
            'variables': [{'short_name': 'VHM0'}]
        }
    ]
