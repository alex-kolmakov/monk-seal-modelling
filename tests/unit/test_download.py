"""Unit tests for download functionality."""

from pathlib import Path

import pytest

from src.data_ingestion.download_data import DataDownloader, DatasetSpec, DownloadConfig, TimeRange


class TestDatasetSpec:
    """Tests for DatasetSpec dataclass."""

    def test_creation(self):
        """Test creating dataset specification."""
        spec = DatasetSpec(dataset_id="test_dataset", variables=["var1", "var2"])
        assert spec.dataset_id == "test_dataset"
        assert spec.variables == ["var1", "var2"]
        assert spec.output_filename is None


class TestTimeRange:
    """Tests for TimeRange dataclass."""

    def test_creation(self):
        """Test creating time range."""
        time_range = TimeRange(start_date="2023-01-01", end_date="2023-12-31")
        assert time_range.start_date == "2023-01-01"
        assert time_range.end_date == "2023-12-31"


class TestDownloadConfig:
    """Tests for DownloadConfig dataclass."""

    def test_creation(self, sample_region):
        """Test creating download configuration."""
        config = DownloadConfig(
            output_dir=Path("data/"),
            region=sample_region,
            time_range=TimeRange("2023-01-01", "2023-12-31"),
            datasets=[DatasetSpec("dataset1", ["var1"]), DatasetSpec("dataset2", ["var2"])],
        )
        assert config.output_dir == Path("data/")
        assert config.region == sample_region
        assert len(config.datasets) == 2
        assert config.overwrite is True
        assert config.max_workers == 3


class TestDataDownloader:
    """Tests for DataDownloader class."""

    def test_initialization(self, mock_manager):
        """Test downloader initialization."""
        downloader = DataDownloader(manager=mock_manager)
        assert downloader.manager == mock_manager

    def test_initialization_default_manager(self):
        """Test downloader initialization with default manager."""
        downloader = DataDownloader()
        assert downloader.manager is not None

    def test_validate_config_valid(self, mock_manager, sample_region):
        """Test configuration validation with valid config."""
        config = DownloadConfig(
            output_dir=Path("data/"),
            region=sample_region,
            time_range=TimeRange("2023-01-01", "2023-12-31"),
            datasets=[DatasetSpec("dataset1", ["var1"])],
        )

        downloader = DataDownloader(manager=mock_manager)
        # Should not raise
        downloader.validate_config(config)

    def test_validate_config_no_datasets(self, mock_manager, sample_region):
        """Test configuration validation with no datasets."""
        config = DownloadConfig(
            output_dir=Path("data/"),
            region=sample_region,
            time_range=TimeRange("2023-01-01", "2023-12-31"),
            datasets=[],
        )

        downloader = DataDownloader(manager=mock_manager)

        with pytest.raises(ValueError, match="No datasets specified"):
            downloader.validate_config(config)

    def test_download_dataset_success(self, mock_manager, sample_region):
        """Test successful dataset download."""
        mock_manager.download_data.return_value = True

        config = DownloadConfig(
            output_dir=Path("data/"),
            region=sample_region,
            time_range=TimeRange("2023-01-01", "2023-12-31"),
            datasets=[DatasetSpec("dataset1", ["var1"])],
        )
        spec = config.datasets[0]

        downloader = DataDownloader(manager=mock_manager)
        success = downloader.download_dataset(spec, config)

        assert success is True
        mock_manager.download_data.assert_called_once()

    def test_download_dataset_failure(self, mock_manager, sample_region):
        """Test failed dataset download."""
        mock_manager.download_data.return_value = False

        config = DownloadConfig(
            output_dir=Path("data/"),
            region=sample_region,
            time_range=TimeRange("2023-01-01", "2023-12-31"),
            datasets=[DatasetSpec("dataset1", ["var1"])],
        )
        spec = config.datasets[0]

        downloader = DataDownloader(manager=mock_manager)
        success = downloader.download_dataset(spec, config)

        assert success is False

    def test_download_batch(self, mock_manager, sample_region, tmp_path):
        """Test batch download."""
        mock_manager.download_data.return_value = True

        config = DownloadConfig(
            output_dir=tmp_path,
            region=sample_region,
            time_range=TimeRange("2023-01-01", "2023-12-31"),
            datasets=[DatasetSpec("dataset1", ["var1"]), DatasetSpec("dataset2", ["var2"])],
        )

        downloader = DataDownloader(manager=mock_manager)
        results = downloader.download_batch(config)

        assert len(results["success"]) == 2
        assert len(results["failed"]) == 0
        assert "dataset1" in results["success"]
        assert "dataset2" in results["success"]
