"""Unit tests for dataset discovery functionality."""

import pytest
from pathlib import Path
from src.data_ingestion.discover_datasets import (
    DatasetDiscovery,
    KNOWN_REGIONS,
    format_coverage,
    format_variables
)
from src.data_ingestion.copernicus_manager import RegionBounds


class TestDatasetDiscovery:
    """Tests for DatasetDiscovery class."""
    
    def test_initialization(self, mock_manager):
        """Test discovery initialization."""
        discovery = DatasetDiscovery(manager=mock_manager)
        assert discovery.manager == mock_manager
    
    def test_initialization_default_manager(self):
        """Test discovery initialization with default manager."""
        discovery = DatasetDiscovery()
        assert discovery.manager is not None
    
    def test_search_with_keywords(self, mock_manager, sample_search_results):
        """Test search with keywords."""
        mock_manager.search_datasets.return_value = sample_search_results
        
        discovery = DatasetDiscovery(manager=mock_manager)
        results = discovery.search(keywords=["IBI", "physics"])
        
        assert len(results) == 2
        mock_manager.search_datasets.assert_called_once_with(
            keywords=["IBI", "physics"],
            region=None
        )
    
    def test_search_with_known_region(self, mock_manager, sample_search_results):
        """Test search with known region name."""
        mock_manager.search_datasets.return_value = sample_search_results
        
        discovery = DatasetDiscovery(manager=mock_manager)
        results = discovery.search(keywords=["physics"], region_name="madeira")
        
        assert len(results) == 2
        mock_manager.search_datasets.assert_called_once()
        call_args = mock_manager.search_datasets.call_args
        assert call_args[1]['keywords'] == ["physics"]
        assert isinstance(call_args[1]['region'], RegionBounds)
    
    def test_search_with_invalid_region_name(self, mock_manager):
        """Test search with invalid region name."""
        discovery = DatasetDiscovery(manager=mock_manager)
        
        with pytest.raises(ValueError, match="Unknown region"):
            discovery.search(region_name="invalid_region")
    
    def test_search_with_custom_region(self, mock_manager, sample_region, sample_search_results):
        """Test search with custom region bounds."""
        mock_manager.search_datasets.return_value = sample_search_results
        
        discovery = DatasetDiscovery(manager=mock_manager)
        results = discovery.search(region_bounds=sample_region)
        
        assert len(results) == 2
        mock_manager.search_datasets.assert_called_once_with(
            keywords=None,
            region=sample_region
        )
    
    def test_get_dataset_details(self, mock_manager, sample_dataset_info):
        """Test getting dataset details."""
        mock_manager.get_dataset_info.return_value = sample_dataset_info
        
        discovery = DatasetDiscovery(manager=mock_manager)
        info = discovery.get_dataset_details("cmems_mod_ibi_phy_my_0.027deg_P1D-m")
        
        assert info['dataset_id'] == 'cmems_mod_ibi_phy_my_0.027deg_P1D-m'
        assert 'coverage' in info
        assert 'variables' in info
    
    def test_export_results_json(self, mock_manager, sample_search_results, tmp_path):
        """Test exporting results to JSON."""
        discovery = DatasetDiscovery(manager=mock_manager)
        output_file = tmp_path / "results.json"
        
        discovery.export_results(sample_search_results, output_file, format='json')
        
        assert output_file.exists()
        
        import json
        with open(output_file) as f:
            data = json.load(f)
        
        assert len(data) == 2
        assert data[0]['dataset_id'] == 'cmems_mod_ibi_phy_my_0.027deg_P1D-m'
    
    def test_export_results_unsupported_format(self, mock_manager, sample_search_results, tmp_path):
        """Test exporting with unsupported format."""
        discovery = DatasetDiscovery(manager=mock_manager)
        output_file = tmp_path / "results.xml"
        
        with pytest.raises(ValueError, match="Unsupported format"):
            discovery.export_results(sample_search_results, output_file, format='xml')


class TestFormatting:
    """Tests for formatting functions."""
    
    def test_format_coverage(self):
        """Test coverage formatting."""
        coverage = {
            'bbox': {
                'lon_min': -17.5,
                'lat_min': 32.2,
                'lon_max': -16.0,
                'lat_max': 33.5
            },
            'time': {
                'min': '2023-01-01T00:00:00',
                'max': '2023-12-31T23:59:59',
                'step_days': 1.0
            }
        }
        
        result = format_coverage(coverage)
        
        assert "Bounding Box" in result
        assert "-17.50°E to -16.00°E" in result
        assert "Time Range" in result
        assert "2023-01-01" in result
    
    def test_format_variables(self):
        """Test variables formatting."""
        variables = [
            {
                'short_name': 'thetao',
                'standard_name': 'sea_water_potential_temperature',
                'units': 'degrees_C'
            },
            {
                'short_name': 'uo',
                'standard_name': 'eastward_sea_water_velocity',
                'units': 'm/s'
            }
        ]
        
        result = format_variables(variables)
        
        assert "thetao" in result
        assert "uo" in result
        assert "degrees_C" in result
        assert "m/s" in result


class TestKnownRegions:
    """Tests for known regions."""
    
    def test_known_regions_exist(self):
        """Test that known regions are defined."""
        assert 'madeira' in KNOWN_REGIONS
        assert 'ibi' in KNOWN_REGIONS
        assert 'mediterranean' in KNOWN_REGIONS
    
    def test_known_regions_are_valid(self):
        """Test that all known regions have valid bounds."""
        for name, region in KNOWN_REGIONS.items():
            assert isinstance(region, RegionBounds)
            assert region.min_lon < region.max_lon
            assert region.min_lat < region.max_lat
