"""
Seal behavior animation with improved structure and type hints.

Creates animated visualizations of seal movements, behavioral states,
and physiological metrics over time.
"""

import logging
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.animation import FFMpegWriter, FuncAnimation
from matplotlib.patches import Rectangle

from src.visualization.config import SealAnimationConfig
from src.visualization.data_loader import EnvironmentalDataLoader, SealDataLoader

logger = logging.getLogger(__name__)


class SealBehaviorAnimator:
    """Animate seal behavior with map, track, and metrics.

    Example:
        >>> config = SealAnimationConfig()
        >>> animator = SealBehaviorAnimator(config)
        >>> animator.create_animation(
        ...     seal_csv=Path("seal_tracks.csv"),
        ...     physics_file=Path("physics.nc")
        ... )
    """

    def __init__(self, config: SealAnimationConfig):
        """Initialize animator with configuration.

        Args:
            config: Animation configuration
        """
        self.config = config
        self.seal_loader = SealDataLoader()
        self.env_loader = EnvironmentalDataLoader()

    def create_animation(
        self, seal_csv: Path, physics_file: Path, output_file: Path | None = None
    ) -> Path:
        """Create seal behavior animation.

        Args:
            seal_csv: Path to seal tracking CSV
            physics_file: Path to physics NetCDF (for bathymetry)
            output_file: Optional output path (default: config.output_dir/seal_animation.mp4)

        Returns:
            Path to saved animation
        """
        logger.info("Creating seal behavior animation")

        # Load data
        seal_data = self.seal_loader.load_csv(seal_csv)
        physics = self.env_loader.load_physics(physics_file)

        logger.info(f"Loaded {len(seal_data)} seal records")

        # Get bathymetry
        lat_bath, lon_bath, bathymetry = self.env_loader.create_bathymetry(physics)
        physics.close()

        # Setup output
        if output_file is None:
            output_file = self.config.output_dir / "seal_animation.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create figure
        fig = plt.figure(figsize=self.config.figsize)

        # Map extent
        min_lat = seal_data["lat"].min() - 0.2
        max_lat = seal_data["lat"].max() + 0.2
        min_lon = seal_data["lon"].min() - 0.2
        max_lon = seal_data["lon"].max() + 0.2

        # Create map axis (left side)
        ax_map = fig.add_subplot(1, 2, 1, projection=ccrs.PlateCarree())
        ax_map.set_extent(  # pyrefly: ignore
            [min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree()
        )

        # Plot bathymetry
        bath_plot = ax_map.pcolormesh(
            lon_bath,
            lat_bath,
            bathymetry,
            cmap="Blues_r",
            shading="auto",
            transform=ccrs.PlateCarree(),
            alpha=0.4,
            vmin=0,
            vmax=500,
        )

        # Add map features
        ax_map.add_feature(  # pyrefly: ignore
            cfeature.LAND, facecolor="#D2B48C", edgecolor="black", linewidth=0.8, alpha=0.7
        )
        ax_map.coastlines(resolution="10m", linewidth=1.0, color="black")  # pyrefly: ignore

        # Colorbar
        plt.colorbar(bath_plot, ax=ax_map, label="Depth (m)", shrink=0.7, pad=0.1)

        # Gridlines
        gl = ax_map.gridlines(  # pyrefly: ignore
            draw_labels=True, linewidth=0.5, alpha=0.5, linestyle="--"
        )
        gl.right_labels = False

        ax_map.set_title("Seal Movement Track", fontsize=14, fontweight="bold", pad=10)

        # Info panel (right side)
        ax_info = fig.add_subplot(1, 2, 2)
        ax_info.set_xlim(0, 1)
        ax_info.set_ylim(0, 1)
        ax_info.axis("off")

        # Initialize plot elements
        (track_line,) = ax_map.plot(
            [],
            [],
            "k-",
            linewidth=1,
            alpha=0.5,
            transform=ccrs.PlateCarree(),
            label=f"Track ({self.config.track_hours}h)",
        )
        (seal_marker,) = ax_map.plot(
            [], [], "o", markersize=12, transform=ccrs.PlateCarree(), label="Current Position"
        )

        # Info text elements
        info_texts = {
            "title": ax_info.text(0.5, 0.98, "", ha="center", fontsize=20, fontweight="bold"),
            "date": ax_info.text(0.5, 0.92, "", ha="center", fontsize=16),
            "state": ax_info.text(0.1, 0.82, "", fontsize=14, fontweight="bold"),
            "depth": ax_info.text(0.1, 0.40, "", fontsize=12),
            "position": ax_info.text(0.1, 0.35, "", fontsize=10, family="monospace"),
        }

        # Energy bar
        energy_bar_bg = Rectangle((0.1, 0.72), 0.8, 0.04, facecolor="lightgray", edgecolor="black")
        energy_bar = Rectangle((0.1, 0.72), 0.0, 0.04, facecolor="green", edgecolor="black")
        ax_info.add_patch(energy_bar_bg)
        ax_info.add_patch(energy_bar)
        ax_info.text(0.1, 0.77, "Energy", fontsize=11, fontweight="bold")
        info_texts["energy"] = ax_info.text(0.1, 0.69, "", fontsize=10)

        # Stomach bar
        stomach_bar_bg = Rectangle((0.1, 0.58), 0.8, 0.04, facecolor="lightgray", edgecolor="black")
        stomach_bar = Rectangle((0.1, 0.58), 0.0, 0.04, facecolor="orange", edgecolor="black")
        ax_info.add_patch(stomach_bar_bg)
        ax_info.add_patch(stomach_bar)
        ax_info.text(0.1, 0.63, "Stomach", fontsize=11, fontweight="bold")
        info_texts["stomach"] = ax_info.text(0.1, 0.55, "", fontsize=10)

        # State legend
        legend_start_y = 0.28
        ax_info.text(0.1, legend_start_y + 0.02, "States Legend:", fontsize=11, fontweight="bold")
        for i, (state, color) in enumerate(self.config.state_colors.items()):
            y_pos = legend_start_y - (i * 0.04)
            ax_info.plot([0.15], [y_pos], "o", color=color, markersize=10)
            ax_info.text(0.20, y_pos, state, fontsize=10, va="center")

        plt.tight_layout(rect=(0, 0, 0.98, 0.95))

        def update(frame: int) -> list:
            """Update animation frame."""
            if frame >= len(seal_data):
                return []

            current = seal_data.iloc[frame]

            # Track history
            track_start = max(0, frame - self.config.track_hours)
            track_lons = seal_data.iloc[track_start : frame + 1]["lon"].values
            track_lats = seal_data.iloc[track_start : frame + 1]["lat"].values

            track_line.set_data(list(track_lons), list(track_lats))

            # Seal marker
            state = current["state"]
            color = self.config.state_colors.get(state, "gray")
            seal_marker.set_data([current["lon"]], [current["lat"]])
            seal_marker.set_color(color)
            seal_marker.set_markeredgecolor("black")
            seal_marker.set_markeredgewidth(2)

            # Update info
            info_texts["title"].set_text(f"Seal {current['agent_id']} - Behavior Tracking")
            info_texts["date"].set_text(f"{current['timestamp']}")
            info_texts["state"].set_text(f"State: {state}")
            info_texts["state"].set_color(color)

            # Energy and stomach
            energy_pct = (current["energy"] / 100000.0) * 100
            stomach_pct = (current["stomach"] / 15.0) * 100

            info_texts["energy"].set_text(
                f"Energy: {current['energy']:.0f} / 100000 ({energy_pct:.1f}%)"
            )
            info_texts["stomach"].set_text(f"Stomach: {current['stomach']:.1f} / 15.0 kg")

            # Update bars
            energy_bar.set_width(0.8 * (energy_pct / 100))
            stomach_bar.set_width(0.8 * (stomach_pct / 100))

            # Bar colors
            if energy_pct > 70:
                energy_bar.set_facecolor("green")
            elif energy_pct > 40:
                energy_bar.set_facecolor("orange")
            else:
                energy_bar.set_facecolor("red")

            # Depth info
            if pd.notna(current.get("depth")):
                info_texts["depth"].set_text(f"Depth: {current['depth']:.1f} m")
            else:
                info_texts["depth"].set_text("Depth: N/A (on land)")

            info_texts["position"].set_text(
                f"Position:\n  Lat: {current['lat']:.4f}°\n  Lon: {current['lon']:.4f}°"
            )

            # Progress
            if frame % 100 == 0:
                progress = (frame / len(seal_data)) * 100
                logger.info(f"Frame {frame}/{len(seal_data)} ({progress:.1f}%)")

            return [track_line, seal_marker] + list(info_texts.values()) + [energy_bar, stomach_bar]

        # Create animation
        logger.info(f"Creating animation with {len(seal_data)} frames at {self.config.fps} fps")
        logger.info(f"Video duration: ~{len(seal_data) / self.config.fps:.1f} seconds")

        anim = FuncAnimation(
            fig, update, frames=len(seal_data), interval=1000 / self.config.fps, blit=False
        )

        # Save
        logger.info(f"Saving animation to {output_file}")
        writer = FFMpegWriter(
            fps=self.config.fps,
            metadata=dict(artist="Seal Simulation"),
            bitrate=self.config.bitrate,
        )
        anim.save(str(output_file), writer=writer)
        plt.close()

        logger.info(f"Animation saved to {output_file}")
        return output_file


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seal behavior animation")
    parser.add_argument("--seal-csv", type=Path, required=True, help="Seal tracking CSV file")
    parser.add_argument("--physics-file", type=Path, required=True, help="Physics NetCDF file")
    parser.add_argument("--output", type=Path, help="Output video file")
    parser.add_argument("--fps", type=int, default=10, help="Frames per second")
    parser.add_argument("--track-hours", type=int, default=24, help="Hours of track history")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    config = SealAnimationConfig(fps=args.fps, track_hours=args.track_hours)

    animator = SealBehaviorAnimator(config)
    output_file = animator.create_animation(
        seal_csv=args.seal_csv, physics_file=args.physics_file, output_file=args.output
    )

    print(f"\n✓ Animation complete: {output_file}")


if __name__ == "__main__":
    main()
