"""Unit tests for data loaders."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.visualization.data_loader import EnvironmentalDataLoader, SealDataLoader


class TestEnvironmentalDataLoader:
    """Tests for EnvironmentalDataLoader."""

    def test_load_physics_missing_file(self):
        """Test loading physics from non-existent file."""
        loader = EnvironmentalDataLoader()

        with pytest.raises(FileNotFoundError, match="Physics file not found"):
            loader.load_physics(Path("nonexistent.nc"))

    def test_load_waves_missing_file(self):
        """Test loading waves from non-existent file."""
        loader = EnvironmentalDataLoader()

        with pytest.raises(FileNotFoundError, match="Waves file not found"):
            loader.load_waves(Path("nonexistent.nc"))

    def test_load_bgc_missing_file(self):
        """Test loading BGC from non-existent file."""
        loader = EnvironmentalDataLoader()

        with pytest.raises(FileNotFoundError, match="BGC file not found"):
            loader.load_bgc(Path("nonexistent.nc"))

    def test_create_bathymetry(self):
        """Test bathymetry creation from physics data."""
        # Create minimal physics dataset
        lat = np.array([32.0, 32.5, 33.0])
        lon = np.array([-17.0, -16.5, -16.0])
        depth = np.array([0, 10, 20, 50])
        time = pd.date_range("2023-01-01", periods=1)

        # Create temperature data (NaN = land, values = water)
        temp = np.random.rand(1, 4, 3, 3) * 5 + 15
        temp[0, :, 0, 0] = np.nan  # Land cell

        ds = xr.Dataset(
            {"thetao": (["time", "depth", "latitude", "longitude"], temp)},
            coords={"time": time, "depth": depth, "latitude": lat, "longitude": lon},
        )

        loader = EnvironmentalDataLoader()
        lat_out, lon_out, bath = loader.create_bathymetry(ds)

        assert len(lat_out) == 3
        assert len(lon_out) == 3
        assert bath.shape == (3, 3)
        assert np.isnan(bath[0, 0])  # Land cell
        assert not np.isnan(bath[1, 1])  # Water cell

    def test_detect_coastline(self):
        """Test coastline detection."""
        # Create simple bathymetry (NaN = land)
        bath = np.array([[np.nan, np.nan, np.nan], [np.nan, 100.0, 100.0], [np.nan, 100.0, 100.0]])

        loader = EnvironmentalDataLoader()
        coastline = loader.detect_coastline(bath)

        # Check that land cells adjacent to water are marked as coastline (1)
        assert coastline[0, 0] == 1  # Coastline (land next to water)
        assert coastline[0, 1] == 1  # Coastline
        assert coastline[1, 0] == 1  # Coastline
        assert coastline[1, 1] == -1  # Water
        assert coastline[2, 2] == -1  # Water


class TestSealDataLoader:
    """Tests for SealDataLoader."""

    def test_load_csv_missing_file(self):
        """Test loading from non-existent file."""
        loader = SealDataLoader()

        with pytest.raises(FileNotFoundError, match="Seal data file not found"):
            loader.load_csv(Path("nonexistent.csv"))

    def test_load_csv_missing_columns(self, tmp_path):
        """Test loading CSV with missing required columns."""
        # Create CSV with missing columns
        csv_file = tmp_path / "incomplete.csv"
        df = pd.DataFrame(
            {
                "agent_id": [1, 2],
                "time": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                "lat": [32.5, 32.6],
                "lon": [-16.5, -16.4],
                # Missing: state, energy, stomach
            }
        )
        df.to_csv(csv_file, index=False)

        loader = SealDataLoader()

        with pytest.raises(ValueError, match="Missing required columns"):
            loader.load_csv(csv_file)

    def test_load_csv_valid(self, tmp_path):
        """Test loading valid CSV."""
        # Create valid CSV
        csv_file = tmp_path / "valid.csv"
        df = pd.DataFrame(
            {
                "agent_id": [1, 1, 2],
                "time": ["2023-01-01 00:00:00", "2023-01-01 01:00:00", "2023-01-01 00:00:00"],
                "lat": [32.5, 32.51, 32.6],
                "lon": [-16.5, -16.49, -16.4],
                "state": ["FORAGING", "TRANSITING", "RESTING"],
                "energy": [80000, 79000, 85000],
                "stomach": [10.5, 10.0, 12.0],
            }
        )
        df.to_csv(csv_file, index=False)

        loader = SealDataLoader()
        result = loader.load_csv(csv_file)

        assert len(result) == 3
        assert "timestamp" in result.columns  # Renamed from 'time'
        assert result["agent_id"].nunique() == 2
        assert all(col in result.columns for col in ["lat", "lon", "state", "energy", "stomach"])
