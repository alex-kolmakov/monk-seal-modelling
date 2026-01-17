"""Unit tests for CopernicusManager."""

import pytest

from src.data_ingestion.copernicus_manager import (
    CopernicusManager,
    InvalidCoordinatesError,
    InvalidDateRangeError,
    RegionBounds,
)


class TestRegionBounds:
    """Tests for RegionBounds dataclass."""

    def test_valid_bounds(self):
        """Test creating valid region bounds."""
        region = RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5)
        assert region.min_lon == -17.5
        assert region.max_lon == -16.0
        assert region.min_lat == 32.2
        assert region.max_lat == 33.5

    def test_invalid_longitude_range(self):
        """Test that invalid longitude range raises error."""
        with pytest.raises(InvalidCoordinatesError, match="min_lon must be less than max_lon"):
            RegionBounds(min_lon=-16.0, max_lon=-17.5, min_lat=32.2, max_lat=33.5)

    def test_invalid_latitude_range(self):
        """Test that invalid latitude range raises error."""
        with pytest.raises(InvalidCoordinatesError, match="min_lat must be less than max_lat"):
            RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=33.5, max_lat=32.2)

    def test_longitude_out_of_bounds(self):
        """Test that longitude out of bounds raises error."""
        with pytest.raises(InvalidCoordinatesError, match="min_lon must be between"):
            RegionBounds(min_lon=-200.0, max_lon=-16.0, min_lat=32.2, max_lat=33.5)

    def test_latitude_out_of_bounds(self):
        """Test that latitude out of bounds raises error."""
        with pytest.raises(InvalidCoordinatesError, match="max_lat must be between"):
            RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=100.0)


class TestCopernicusManager:
    """Tests for CopernicusManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = CopernicusManager()
        assert manager is not None

    def test_initialization_with_credentials(self):
        """Test manager initialization with explicit credentials."""
        manager = CopernicusManager(username="test", password="pass")
        assert manager.username == "test"
        assert manager.password == "pass"

    def test_validate_coordinates_valid(self):
        """Test coordinate validation with valid inputs."""
        # Should not raise
        CopernicusManager.validate_coordinates(
            min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5
        )

    def test_validate_coordinates_invalid(self):
        """Test coordinate validation with invalid inputs."""
        with pytest.raises(InvalidCoordinatesError):
            CopernicusManager.validate_coordinates(
                min_lon=-16.0,
                max_lon=-17.5,  # Invalid: min > max
                min_lat=32.2,
                max_lat=33.5,
            )

    def test_validate_date_range_valid(self):
        """Test date range validation with valid inputs."""
        # Should not raise
        CopernicusManager.validate_date_range("2023-01-01", "2023-12-31")

    def test_validate_date_range_invalid_order(self):
        """Test date range validation with invalid order."""
        with pytest.raises(InvalidDateRangeError, match="must be before"):
            CopernicusManager.validate_date_range("2023-12-31", "2023-01-01")

    def test_validate_date_range_invalid_format(self):
        """Test date range validation with invalid format."""
        with pytest.raises(InvalidDateRangeError, match="Invalid date format"):
            CopernicusManager.validate_date_range("2023/01/01", "2023-12-31")

    def test_check_region_overlap_with_overlap(self):
        """Test region overlap detection with overlapping regions."""
        manager = CopernicusManager()
        coverage = {"bbox": {"lon_min": -19.0, "lat_min": 26.0, "lon_max": 5.0, "lat_max": 56.0}}
        region = RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5)

        assert manager._check_region_overlap(coverage, region) is True

    def test_check_region_overlap_no_overlap(self):
        """Test region overlap detection with non-overlapping regions."""
        manager = CopernicusManager()
        coverage = {"bbox": {"lon_min": 10.0, "lat_min": 40.0, "lon_max": 20.0, "lat_max": 50.0}}
        region = RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5)

        assert manager._check_region_overlap(coverage, region) is False

    def test_check_region_overlap_no_bbox(self):
        """Test region overlap detection with missing bbox."""
        manager = CopernicusManager()
        coverage = {}
        region = RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5)

        assert manager._check_region_overlap(coverage, region) is False
