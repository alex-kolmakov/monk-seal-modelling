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
