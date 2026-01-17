"""Unit tests for visualization configuration."""

from pathlib import Path

from src.visualization.config import SealAnimationConfig, WeatherVisualizationConfig


class TestWeatherVisualizationConfig:
    """Tests for WeatherVisualizationConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = WeatherVisualizationConfig()

        assert config.data_dir == Path("data/real_long")
        assert config.output_dir == Path("data/real_long")
        assert config.fps == 10
        assert config.skip_days == 1
        assert config.bitrate == 5000
        assert config.figsize == (16, 10)
        assert config.dpi == 100

    def test_custom_values(self):
        """Test custom configuration values."""
        config = WeatherVisualizationConfig(data_dir=Path("custom/data"), fps=30, skip_days=2)

        assert config.data_dir == Path("custom/data")
        assert config.fps == 30
        assert config.skip_days == 2

    def test_data_ranges(self):
        """Test colormap data ranges."""
        config = WeatherVisualizationConfig()

        assert config.temp_range == (15.0, 25.0)
        assert config.wave_range == (0.0, 5.0)
        assert config.chl_range == (0.0, 0.5)
        assert config.depth_range == (0.0, 500.0)

    def test_custom_ranges(self):
        """Test custom data ranges."""
        config = WeatherVisualizationConfig(temp_range=(15.0, 25.0), wave_range=(0.0, 6.0))

        assert config.temp_range == (15.0, 25.0)
        assert config.wave_range == (0.0, 6.0)


class TestSealAnimationConfig:
    """Tests for SealAnimationConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SealAnimationConfig()

        assert config.data_dir == Path("data/real_long")
        assert config.output_dir == Path("data/real_long")
        assert config.fps == 10
        assert config.bitrate == 5000
        assert config.figsize == (16, 10)
        assert config.track_hours == 24

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SealAnimationConfig(fps=15, track_hours=48)

        assert config.fps == 15
        assert config.track_hours == 48

    def test_state_colors(self):
        """Test default state colors."""
        config = SealAnimationConfig()

        assert "FORAGING" in config.state_colors
        assert "HAULING_OUT" in config.state_colors
        assert "SLEEPING" in config.state_colors
        assert "RESTING" in config.state_colors
        assert "TRANSITING" in config.state_colors

        assert config.state_colors["FORAGING"] == "#2E86DE"
        assert config.state_colors["SLEEPING"] == "#E74C3C"

    def test_custom_state_colors(self):
        """Test custom state colors."""
        custom_colors = {"FORAGING": "#FF0000", "RESTING": "#00FF00"}
        config = SealAnimationConfig(state_colors=custom_colors)

        assert config.state_colors == custom_colors
