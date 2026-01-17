"""Data loading utilities for visualization."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)


class EnvironmentalDataLoader:
    """Load and validate environmental data files.

    Example:
        >>> loader = EnvironmentalDataLoader()
        >>> physics = loader.load_physics(Path("data/physics.nc"))
        >>> lat, lon, bath = loader.create_bathymetry(physics)
    """

    @staticmethod
    def load_physics(filepath: Path) -> xr.Dataset:
        """Load physics data (temperature, currents, salinity).

        Args:
            filepath: Path to physics NetCDF file

        Returns:
            Opened xarray Dataset

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required variables are missing
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Physics file not found: {filepath}")

        logger.info(f"Loading physics data from {filepath}")
        ds = xr.open_dataset(filepath)

        # Validate required variables
        required_vars = ["thetao"]  # Temperature is minimum requirement
        missing = [var for var in required_vars if var not in ds.data_vars]
        if missing:
            raise ValueError(f"Missing required variables in physics file: {missing}")

        return ds

    @staticmethod
    def load_waves(filepath: Path) -> xr.Dataset:
        """Load wave data (significant wave height, direction, period).

        Args:
            filepath: Path to waves NetCDF file

        Returns:
            Opened xarray Dataset

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Waves file not found: {filepath}")

        logger.info(f"Loading waves data from {filepath}")
        return xr.open_dataset(filepath)

    @staticmethod
    def load_bgc(filepath: Path) -> xr.Dataset:
        """Load biogeochemistry data (chlorophyll, oxygen, nutrients).

        Args:
            filepath: Path to BGC NetCDF file

        Returns:
            Opened xarray Dataset

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not filepath.exists():
            raise FileNotFoundError(f"BGC file not found: {filepath}")

        logger.info(f"Loading BGC data from {filepath}")
        return xr.open_dataset(filepath)

    @staticmethod
    def create_bathymetry(physics: xr.Dataset) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract bathymetry (maximum depth) from physics data.

        This function determines the maximum depth at each grid cell by finding
        the deepest level with valid temperature data.

        Args:
            physics: Physics dataset with temperature data

        Returns:
            Tuple of (latitude, longitude, bathymetry) arrays

        Example:
            >>> lat, lon, bath = loader.create_bathymetry(physics)
            >>> print(f"Max depth: {np.nanmax(bath):.1f}m")
        """
        logger.info("Creating bathymetry map from physics data")

        temp_data = physics["thetao"].isel(time=0)
        bathymetry = np.full((len(temp_data.latitude), len(temp_data.longitude)), np.nan)

        for i in range(len(temp_data.latitude)):
            for j in range(len(temp_data.longitude)):
                temp_profile = temp_data.isel(latitude=i, longitude=j).values
                valid_depths = physics.depth.values[~np.isnan(temp_profile)]
                if len(valid_depths) > 0:
                    bathymetry[i, j] = valid_depths.max()

        logger.info(f"Bathymetry created: {np.sum(~np.isnan(bathymetry))} valid cells")

        return (temp_data.latitude.values, temp_data.longitude.values, bathymetry)

    @staticmethod
    def detect_coastline(bathymetry: np.ndarray) -> np.ndarray:
        """Detect coastline cells (land cells adjacent to water).

        Args:
            bathymetry: 2D array of bathymetry data (NaN = land)

        Returns:
            2D array where:
                -1 = water
                 0 = interior land
                 1 = coastline
        """
        logger.info("Detecting coastline cells")

        coastline_cells = np.zeros_like(bathymetry)
        rows, cols = bathymetry.shape

        for i in range(rows):
            for j in range(cols):
                if np.isnan(bathymetry[i, j]):
                    # Check if any neighbor has data (is water)
                    has_water_neighbor = False
                    for di in [-1, 0, 1]:
                        for dj in [-1, 0, 1]:
                            ni, nj = i + di, j + dj
                            if 0 <= ni < rows and 0 <= nj < cols:
                                if not np.isnan(bathymetry[ni, nj]):
                                    has_water_neighbor = True
                                    break
                        if has_water_neighbor:
                            break

                    coastline_cells[i, j] = 1 if has_water_neighbor else 0
                else:
                    coastline_cells[i, j] = -1  # Water

        n_coastline = np.sum(coastline_cells == 1)
        logger.info(f"Detected {n_coastline} coastline cells")

        return coastline_cells


class SealDataLoader:
    """Load and validate seal tracking data.

    Example:
        >>> loader = SealDataLoader()
        >>> df = loader.load_csv(Path("seal_tracks.csv"))
        >>> print(f"Loaded {len(df)} records for {df['agent_id'].nunique()} seals")
    """

    @staticmethod
    def load_csv(filepath: Path) -> pd.DataFrame:
        """Load seal tracking data from CSV file.

        Args:
            filepath: Path to CSV file with seal tracking data

        Returns:
            DataFrame with seal tracking data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required columns are missing

        Example:
            >>> df = SealDataLoader.load_csv(Path("tracks.csv"))
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Seal data file not found: {filepath}")

        logger.info(f"Loading seal data from {filepath}")

        # Load with time parsing
        df = pd.read_csv(filepath, parse_dates=["time"])
        df = df.rename(columns={"time": "timestamp"})

        # Validate required columns
        required = ["agent_id", "lat", "lon", "state", "energy", "stomach"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        logger.info(f"Loaded {len(df)} records for {df['agent_id'].nunique()} seal(s)")

        return df
