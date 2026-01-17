"""Visualization configuration dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WeatherVisualizationConfig:
    """Configuration for weather visualization.

    Attributes:
        data_dir: Directory containing input data files
        output_dir: Directory for output files
        fps: Frames per second for animations
        skip_days: Number of days to skip between frames
        bitrate: Video bitrate for animations
        figsize: Figure size (width, height) in inches
        dpi: Dots per inch for output
        temp_range: Temperature colormap range (min, max) in °C
        wave_range: Wave height colormap range (min, max) in meters
        chl_range: Chlorophyll colormap range (min, max)
        depth_range: Depth colormap range (min, max) in meters

    Example:
        >>> config = WeatherVisualizationConfig(
        ...     data_dir=Path("data/real_long"),
        ...     fps=30,
        ...     skip_days=2
        ... )
    """

    data_dir: Path = Path("data/real_long")
    output_dir: Path = Path("data/real_long")

    # Animation settings
    fps: int = 10
    skip_days: int = 1
    bitrate: int = 5000

    # Plot settings
    figsize: tuple[int, int] = (16, 10)
    dpi: int = 100

    # Plot ranges
    temp_range: tuple[float, float] = (15.0, 25.0)  # Wider range for seasonal variation
    wave_range: tuple[float, float] = (0.0, 5.0)  # More dramatic gradient, up to 5m
    chl_range: tuple[float, float] = (0.0, 0.5)
    current_range: tuple[float, float] = (0.0, 1.0)  # Current speed in m/s
    depth_range: tuple[float, float] = (0.0, 500.0)


@dataclass
class SealAnimationConfig:
    """Configuration for seal behavior animation.

    Attributes:
        data_dir: Directory containing input data files
        output_dir: Directory for output files
        fps: Frames per second for animation
        bitrate: Video bitrate
        figsize: Figure size (width, height) in inches
        track_hours: Number of hours of track history to display
        state_colors: Mapping of behavioral states to colors

    Example:
        >>> config = SealAnimationConfig(
        ...     fps=15,
        ...     track_hours=48
        ... )
    """

    data_dir: Path = Path("data/real_long")
    output_dir: Path = Path("data/real_long")

    # Animation settings
    fps: int = 10
    bitrate: int = 5000

    # Plot settings
    figsize: tuple[int, int] = (16, 10)
    track_hours: int = 24  # Hours of track history to show

    # State colors
    state_colors: dict[str, str] = field(
        default_factory=lambda: {
            "FORAGING": "#2E86DE",  # Blue
            "HAULING_OUT": "#F39C12",  # Orange
            "SLEEPING": "#E74C3C",  # Red
            "RESTING": "#9B59B6",  # Purple
            "TRANSITING": "#1ABC9C",  # Teal
        }
    )
