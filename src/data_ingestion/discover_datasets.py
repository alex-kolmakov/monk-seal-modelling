"""
Dataset discovery functionality for Copernicus Marine Service.

This module provides both a programmatic API and CLI for discovering datasets.
"""

import argparse
import json
import logging
from pathlib import Path

from src.data_ingestion.copernicus_manager import (
    CopernicusManager,
    RegionBounds,
)

logger = logging.getLogger(__name__)

# Predefined regions
KNOWN_REGIONS = {
    "madeira": RegionBounds(min_lon=-17.5, max_lon=-16.0, min_lat=32.2, max_lat=33.5),
    "ibi": RegionBounds(min_lon=-19.0, max_lon=5.0, min_lat=26.0, max_lat=56.0),
    "mediterranean": RegionBounds(min_lon=-6.0, max_lon=36.0, min_lat=30.0, max_lat=46.0),
}


class DatasetDiscovery:
    """Business logic for dataset discovery.

    Example:
        >>> discovery = DatasetDiscovery()
        >>> results = discovery.search(keywords=["IBI", "physics"])
        >>> print(f"Found {len(results)} datasets")
    """

    def __init__(self, manager: CopernicusManager | None = None):
        """Initialize dataset discovery.

        Args:
            manager: Optional CopernicusManager instance. Creates new one if None.
        """
        self.manager = manager or CopernicusManager()

    def search(
        self,
        keywords: list[str] | None = None,
        region_name: str | None = None,
        region_bounds: RegionBounds | None = None,
    ) -> list[dict]:
        """Search for datasets.

        Args:
            keywords: List of search keywords
            region_name: Name of predefined region ('madeira', 'ibi', 'mediterranean')
            region_bounds: Custom region bounds

        Returns:
            List of dataset dictionaries

        Raises:
            ValueError: If region_name is invalid
        """
        # Resolve region
        region = None
        if region_name:
            if region_name.lower() not in KNOWN_REGIONS:
                raise ValueError(
                    f"Unknown region: {region_name}. Valid regions: {list(KNOWN_REGIONS.keys())}"
                )
            region = KNOWN_REGIONS[region_name.lower()]
        elif region_bounds:
            region = region_bounds

        return self.manager.search_datasets(keywords=keywords, region=region)

    def get_dataset_details(self, dataset_id: str) -> dict:
        """Get detailed information about a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dataset information dictionary

        Raises:
            DatasetNotFoundError: If dataset not found
        """
        return self.manager.get_dataset_info(dataset_id)

    def export_results(
        self, results: list[dict], output_file: str | Path, format: str = "json"
    ) -> None:
        """Export search results to file.

        Args:
            results: List of dataset dictionaries
            output_file: Path to output file
            format: Output format ('json' or 'csv')

        Raises:
            ValueError: If format is not supported
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Exported {len(results)} results to {output_path}")
        else:
            raise ValueError(f"Unsupported format: {format}")


def format_coverage(coverage: dict) -> str:
    """Format coverage information for display."""
    lines = []

    if "bbox" in coverage:
        bbox = coverage["bbox"]
        lines.append("  Bounding Box:")
        lines.append(f"    Longitude: {bbox['lon_min']:.2f}°E to {bbox['lon_max']:.2f}°E")
        lines.append(f"    Latitude:  {bbox['lat_min']:.2f}°N to {bbox['lat_max']:.2f}°N")

    if "time" in coverage:
        time_info = coverage["time"]
        lines.append("  Time Range:")
        lines.append(f"    Start: {time_info['min']}")
        lines.append(f"    End:   {time_info['max']}")
        if time_info.get("step_days"):
            lines.append(f"    Resolution: {time_info['step_days']:.1f} days")

    if "depth" in coverage:
        depth_info = coverage["depth"]
        lines.append("  Depth:")
        lines.append(f"    Levels: {depth_info['levels']}")
        if depth_info.get("min") is not None and depth_info.get("max") is not None:
            lines.append(f"    Range: {depth_info['min']:.1f}m to {depth_info['max']:.1f}m")

    return "\n".join(lines)


def format_variables(variables: list[dict]) -> str:
    """Format variable list for display."""
    lines = []
    for var in variables:
        name = var["short_name"]
        std_name = var.get("standard_name", "N/A")
        units = var.get("units", "N/A")
        lines.append(f"  - {name}")
        lines.append(f"    Standard Name: {std_name}")
        lines.append(f"    Units: {units}")
    return "\n".join(lines)


def main() -> int:
    """CLI entry point for dataset discovery."""
    parser = argparse.ArgumentParser(
        description="Discover Copernicus Marine datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for datasets
  %(prog)s --search "wave IBI"

  # Search with region filter
  %(prog)s --search "physics" --region madeira

  # Get dataset details
  %(prog)s --dataset-id "cmems_mod_ibi_phy_my_0.027deg_P1D-m"

  # Export results
  %(prog)s --search "IBI" --export results.json
        """,
    )

    parser.add_argument("--search", type=str, help="Search keywords (space-separated)")
    parser.add_argument(
        "--region", type=str, choices=list(KNOWN_REGIONS.keys()), help="Filter by predefined region"
    )
    parser.add_argument("--dataset-id", type=str, help="Get details for specific dataset ID")
    parser.add_argument("--export", type=str, help="Export results to JSON file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s"
    )

    discovery = DatasetDiscovery()

    try:
        if args.dataset_id:
            # Get specific dataset details
            print(f"\n=== Dataset Details: {args.dataset_id} ===\n")
            info = discovery.get_dataset_details(args.dataset_id)

            print(f"Dataset ID: {info['dataset_id']}")
            print(f"Dataset Name: {info.get('dataset_name', 'N/A')}")
            print(f"Product: {info.get('product_title', 'N/A')}")
            print("\nCoverage:")
            print(format_coverage(info.get("coverage", {})))
            print("\nVariables:")
            print(format_variables(info.get("variables", [])))

        elif args.search:
            # Search for datasets
            keywords = args.search.split()
            print(f"\n=== Searching for: {' '.join(keywords)} ===")
            if args.region:
                print(f"Region filter: {args.region}\n")

            results = discovery.search(keywords=keywords, region_name=args.region)

            print(f"\nFound {len(results)} datasets:\n")

            for i, ds in enumerate(results, 1):
                print(f"{i}. {ds['dataset_id']}")
                print(f"   Product: {ds.get('product_title', 'N/A')}")

                # Show coverage summary
                coverage = ds.get("coverage", {})
                if "bbox" in coverage:
                    bbox = coverage["bbox"]
                    print(
                        f"   Region: {bbox['lon_min']:.1f}°E to {bbox['lon_max']:.1f}°E, "
                        f"{bbox['lat_min']:.1f}°N to {bbox['lat_max']:.1f}°N"
                    )

                # Show variables
                variables = ds.get("variables", [])
                if variables:
                    var_names = [v["short_name"] for v in variables[:5]]
                    var_str = ", ".join(var_names)
                    if len(variables) > 5:
                        var_str += f" (+{len(variables) - 5} more)"
                    print(f"   Variables: {var_str}")

                print()

            # Export if requested
            if args.export:
                discovery.export_results(results, args.export)
                print(f"Results exported to: {args.export}")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            raise
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
