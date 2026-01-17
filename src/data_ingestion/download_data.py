"""
Data download functionality for Copernicus Marine Service.

This module provides configuration and download orchestration for Copernicus datasets.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from src.data_ingestion.copernicus_manager import CopernicusManager, RegionBounds

logger = logging.getLogger(__name__)


@dataclass
class DatasetSpec:
    """Specification for a dataset to download.

    Attributes:
        dataset_id: The Copernicus dataset ID
        variables: List of variable names to download
        output_filename: Optional custom output filename
    """

    dataset_id: str
    variables: list[str]
    output_filename: str | None = None


@dataclass
class TimeRange:
    """Time range for data download.

    Attributes:
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
    """

    start_date: str
    end_date: str


@dataclass
class DownloadConfig:
    """Configuration for downloading Copernicus data.

    Attributes:
        output_dir: Directory to save downloaded files
        region: Geographic region bounds
        time_range: Time range for download
        datasets: List of datasets to download
        overwrite: Whether to overwrite existing files
        max_workers: Maximum number of parallel downloads

    Example:
        >>> config = DownloadConfig(
        ...     output_dir=Path("data/"),
        ...     region=RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5),
        ...     time_range=TimeRange(start_date="2023-01-01", end_date="2023-12-31"),
        ...     datasets=[
        ...         DatasetSpec(
        ...             dataset_id="cmems_mod_ibi_phy_my_0.027deg_P1D-m",
        ...             variables=["thetao", "uo", "vo"]
        ...         )
        ...     ]
        ... )
    """

    output_dir: Path
    region: RegionBounds
    time_range: TimeRange
    datasets: list[DatasetSpec]
    overwrite: bool = True
    max_workers: int = 3


class DataDownloader:
    """Orchestrates downloading of Copernicus datasets.

    Example:
        >>> downloader = DataDownloader()
        >>> config = DownloadConfig(...)
        >>> results = downloader.download_batch(config)
        >>> print(f"Downloaded {len(results['success'])} datasets")
    """

    def __init__(self, manager: CopernicusManager | None = None):
        """Initialize data downloader.

        Args:
            manager: Optional CopernicusManager instance
        """
        self.manager = manager or CopernicusManager()

    def validate_config(self, config: DownloadConfig) -> None:
        """Validate download configuration.

        Args:
            config: Download configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        if not config.datasets:
            raise ValueError("No datasets specified")

        # Validate date range
        self.manager.validate_date_range(config.time_range.start_date, config.time_range.end_date)

        # Region bounds are validated in RegionBounds.__post_init__

        logger.debug(f"Configuration validated: {len(config.datasets)} datasets")

    def download_dataset(
        self,
        spec: DatasetSpec,
        config: DownloadConfig,
        progress_callback: Callable[[str], None] | None = None,
    ) -> bool:
        """Download a single dataset.

        Args:
            spec: Dataset specification
            config: Download configuration
            progress_callback: Optional callback for progress updates

        Returns:
            True if download successful, False otherwise
        """
        logger.info(f"Downloading {spec.dataset_id}")

        if progress_callback:
            progress_callback(f"Downloading {spec.dataset_id}")

        try:
            success = self.manager.download_data(
                dataset_id=spec.dataset_id,
                output_dir=config.output_dir,
                start_date=config.time_range.start_date,
                end_date=config.time_range.end_date,
                variables=spec.variables,
                minimum_longitude=config.region.min_lon,
                maximum_longitude=config.region.max_lon,
                minimum_latitude=config.region.min_lat,
                maximum_latitude=config.region.max_lat,
                overwrite=config.overwrite,
            )

            if success:
                logger.info(f"Successfully downloaded {spec.dataset_id}")
                if progress_callback:
                    progress_callback(f"✓ {spec.dataset_id}")
            else:
                logger.error(f"Failed to download {spec.dataset_id}")
                if progress_callback:
                    progress_callback(f"✗ {spec.dataset_id}")

            return success

        except Exception as e:
            logger.error(f"Error downloading {spec.dataset_id}: {e}")
            if progress_callback:
                progress_callback(f"✗ {spec.dataset_id}: {e}")
            return False

    def download_batch(
        self,
        config: DownloadConfig,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """Download multiple datasets in parallel.

        Args:
            config: Download configuration
            progress_callback: Optional callback(current, total, message)

        Returns:
            Dictionary with 'success' and 'failed' lists of dataset IDs

        Example:
            >>> downloader = DataDownloader()
            >>> results = downloader.download_batch(config)
            >>> print(f"Success: {len(results['success'])}, Failed: {len(results['failed'])}")
        """
        self.validate_config(config)

        # Create output directory
        config.output_dir.mkdir(parents=True, exist_ok=True)

        results = {"success": [], "failed": []}

        total = len(config.datasets)
        completed = 0

        logger.info(f"Starting batch download of {total} datasets")

        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            # Submit all download tasks
            future_to_spec = {
                executor.submit(
                    self.download_dataset,
                    spec,
                    config,
                    None,  # Individual progress handled by batch callback
                ): spec
                for spec in config.datasets
            }

            # Process completed downloads
            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                completed += 1

                try:
                    success = future.result()
                    if success:
                        results["success"].append(spec.dataset_id)
                    else:
                        results["failed"].append(spec.dataset_id)
                except Exception as e:
                    logger.error(f"Exception for {spec.dataset_id}: {e}")
                    results["failed"].append(spec.dataset_id)

                if progress_callback:
                    status = "✓" if spec.dataset_id in results["success"] else "✗"
                    progress_callback(completed, total, f"{status} {spec.dataset_id}")

        logger.info(
            f"Batch download complete: {len(results['success'])} success, "
            f"{len(results['failed'])} failed"
        )

        return results


# Example configuration for Madeira region
MADEIRA_CONFIG_EXAMPLE = DownloadConfig(
    output_dir=Path("data/real_long"),
    region=RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5),
    time_range=TimeRange(start_date="2023-01-01", end_date="2024-12-31"),
    datasets=[
        DatasetSpec(
            dataset_id="cmems_mod_ibi_phy_my_0.027deg_P1D-m",
            variables=["thetao", "uo", "vo", "so", "zos"],
        ),
        DatasetSpec(
            dataset_id="cmems_mod_ibi_wav_my_0.05deg_PT1H-i", variables=["VHM0", "VMDR", "VTPK"]
        ),
        DatasetSpec(
            dataset_id="cmems_mod_ibi_bgc_my_0.027deg_P1D-m", variables=["chl", "o2", "no3", "po4"]
        ),
    ],
    overwrite=True,
    max_workers=3,
)


# Tidal/sea level data configuration for Madeira region
TIDAL_CONFIG_EXAMPLE = DownloadConfig(
    output_dir=Path("data/real_long"),
    region=RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.0, max_lat=33.5),
    time_range=TimeRange(start_date="2023-01-01", end_date="2024-12-31"),
    datasets=[
        DatasetSpec(
            dataset_id="cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.25deg_P1D",
            variables=["adt", "sla"],
            output_filename="tidal_2023_2024.nc",
        )
    ],
    overwrite=True,
    max_workers=1,
)


def main() -> None:
    """CLI entry point for downloading data."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Copernicus Marine data")
    parser.add_argument(
        "--config",
        type=str,
        default="madeira",
        choices=["madeira", "tidal"],
        help="Predefined configuration to use",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Select configuration
    if args.config == "madeira":
        config = MADEIRA_CONFIG_EXAMPLE
    elif args.config == "tidal":
        config = TIDAL_CONFIG_EXAMPLE
    else:
        raise ValueError(f"Unknown config: {args.config}")

    # Download
    downloader = DataDownloader()

    def progress(current: int, total: int, message: str) -> None:
        print(f"[{current}/{total}] {message}")

    results = downloader.download_batch(config, progress_callback=progress)

    print("\n=== Download Complete ===")
    print(f"Success: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")

    if results["failed"]:
        print("\nFailed datasets:")
        for dataset_id in results["failed"]:
            print(f"  - {dataset_id}")


if __name__ == "__main__":
    main()
