"""Minimal weather visualization - 5 panels animation."""

import logging
from pathlib import Path
from typing import Optional
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from src.visualization.config import WeatherVisualizationConfig

logger = logging.getLogger(__name__)


class WeatherVisualizer:
    """Minimal visualizer for 5 environmental panels."""
    
    def __init__(self, config: WeatherVisualizationConfig):
        self.config = config
    
    def create_animation(
        self,
        physics: xr.Dataset,
        waves: xr.Dataset,
        bgc: xr.Dataset,
        tidal: xr.Dataset
    ) -> Path:
        """Create animation with 5 hardcoded panels."""
        logger.info("Creating animation")
        
        # Setup
        times = physics.time.values
        lat, lon = physics.latitude.values, physics.longitude.values
        extent = [lon.min(), lon.max(), lat.min(), lat.max()]
        
        # Calculate bathymetry
        depth_data = physics['thetao'].isel(time=0)
        bathymetry = np.full_like(depth_data.isel(depth=0).values, np.nan)
        for i in range(len(physics.depth)):
            layer = depth_data.isel(depth=i).values
            valid_mask = ~np.isnan(layer)
            bathymetry[valid_mask] = -physics.depth.values[i]
        
        # 6 panels in 3x2 layout: bathymetry, temperature, waves, chlorophyll, sea_level, currents
        fig, axes = plt.subplots(2, 3, figsize=(24, 14), 
                                 subplot_kw={'projection': ccrs.PlateCarree()})
        axes = axes.flatten()
        
        # Setup each axis (remove right-side labels to avoid overlap)
        for ax in axes:
            ax.set_extent(extent)
            ax.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='black', linewidth=0.5)
            ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
            gl = ax.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
            gl.right_labels = False  # Remove right-side labels
            gl.top_labels = False
        
        # Initialize plots
        plots = []
        
        # Row 1: Temperature, Waves, Currents
        # Row 2: Chlorophyll, Sea Level Anomaly, Bathymetry
        
        # Panel 0: Temperature
        temp = physics['thetao'].isel(time=0, depth=0).values
        p0 = axes[0].pcolormesh(lon, lat, temp, cmap='RdYlBu_r', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=self.config.temp_range[0], vmax=self.config.temp_range[1])
        plt.colorbar(p0, ax=axes[0], label='Temperature (°C)', shrink=0.7)
        axes[0].set_title('Surface Temperature', fontweight='bold')
        plots.append(p0)
        
        # Panel 1: Waves
        wave = waves['VHM0'].isel(time=0).interp(latitude=lat, longitude=lon, method='nearest').values
        p1 = axes[1].pcolormesh(lon, lat, wave, cmap='Blues', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=self.config.wave_range[0], vmax=self.config.wave_range[1])
        plt.colorbar(p1, ax=axes[1], label='Wave Height (m)', shrink=0.7)
        axes[1].set_title('Significant Wave Height', fontweight='bold')
        plots.append(p1)
        
        # Panel 2: Currents
        uo = physics['uo'].isel(time=0, depth=0).values
        vo = physics['vo'].isel(time=0, depth=0).values
        speed = np.sqrt(uo**2 + vo**2)
        p2 = axes[2].pcolormesh(lon, lat, speed, cmap='YlOrRd', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=self.config.current_range[0], vmax=self.config.current_range[1])
        plt.colorbar(p2, ax=axes[2], label='Current Speed (m/s)', shrink=0.7)
        axes[2].set_title('Ocean Current Speed', fontweight='bold')
        plots.append(p2)
        
        # Panel 3: Chlorophyll
        chl = bgc['chl'].isel(time=0, depth=0).values
        p3 = axes[3].pcolormesh(lon, lat, chl, cmap='Greens', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8,
                                vmin=self.config.chl_range[0], vmax=self.config.chl_range[1])
        plt.colorbar(p3, ax=axes[3], label='Chlorophyll (mg/m³)', shrink=0.7)
        axes[3].set_title('Chlorophyll', fontweight='bold')
        plots.append(p3)
        
        # Panel 4: Sea Level Anomaly
        tidal_idx = min(0, len(tidal.time) - 1)
        sea = tidal['adt'].isel(time=tidal_idx).interp(latitude=lat, longitude=lon, method='nearest').values * 100
        p4 = axes[4].pcolormesh(lon, lat, sea, cmap='RdBu_r', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8)
        plt.colorbar(p4, ax=axes[4], label='Sea Level (cm)', shrink=0.7)
        axes[4].set_title('Sea Level Anomaly', fontweight='bold')
        plots.append(p4)
        
        # Panel 5: Bathymetry (static)
        p5 = axes[5].pcolormesh(lon, lat, bathymetry, cmap='viridis_r', shading='auto',
                                transform=ccrs.PlateCarree(), alpha=0.8)
        plt.colorbar(p5, ax=axes[5], label='Depth (m)', shrink=0.7)
        axes[5].set_title('Bathymetry', fontweight='bold')
        # Bathymetry is static, no plot object needed for updates
        
        # Apply tight layout
        plt.tight_layout(rect=(0, 0, 1, 0.96))
        
        # Create date header using middle panel for centering (works with blit=True!)
        # Position above axes[1] (middle top panel) to center across entire figure
        date_text = axes[1].text(0.5, 1.25, '', transform=axes[1].transAxes,
                                ha='center', va='bottom', fontsize=18, 
                                fontweight='bold', clip_on=False)
        
        
        # Init function for animation (required for blit=True with text)
        def init():
            date_text.set_text('')
            return plots + [date_text]
        
        # Animation update function
        def update(frame_idx):
            time_idx = frame_idx * self.config.skip_days
            
            # Update date header
            date_str = f"{str(times[time_idx])[:10]} (Day {time_idx+1}/{len(times)})"
            date_text.set_text(date_str)
            
            # Panel 0: Update temperature
            temp = physics['thetao'].isel(time=time_idx, depth=0).values
            plots[0].set_array(temp.ravel())
            
            # Panel 1: Update waves
            wave = waves['VHM0'].isel(time=time_idx).interp(latitude=lat, longitude=lon, method='nearest').values
            plots[1].set_array(wave.ravel())
            
            # Panel 2: Update currents
            uo = physics['uo'].isel(time=time_idx, depth=0).values
            vo = physics['vo'].isel(time=time_idx, depth=0).values
            speed = np.sqrt(uo**2 + vo**2)
            plots[2].set_array(speed.ravel())
            
            # Panel 3: Update chlorophyll
            chl = bgc['chl'].isel(time=time_idx, depth=0).values
            plots[3].set_array(chl.ravel())
            
            # Panel 4: Update sea level
            tidal_idx = min(time_idx, len(tidal.time) - 1)
            sea = tidal['adt'].isel(time=tidal_idx).interp(latitude=lat, longitude=lon, method='nearest').values * 100
            plots[4].set_array(sea.ravel())
            
            # Panel 5 (bathymetry) is static, no update needed
            
            if frame_idx % 10 == 0:
                logger.info(f"Frame {frame_idx}/{n_frames} ({100*frame_idx/n_frames:.1f}%)")
            
            return plots + [date_text]
        
        # Create animation with init_func (blit=True for speed!)
        n_frames = len(times) // self.config.skip_days
        anim = animation.FuncAnimation(fig, update, init_func=init, frames=n_frames, 
                                      interval=100, blit=True)
        
        # Save
        output_file = self.config.output_dir / "weather_animation.mp4"
        writer = animation.FFMpegWriter(fps=self.config.fps, bitrate=self.config.bitrate)
        logger.info(f"Saving animation to {output_file}")
        anim.save(str(output_file), writer=writer)
        logger.info(f"Animation saved to {output_file}")
        
        plt.close(fig)
        return output_file
    
    def visualize_all(
        self,
        physics_file: Path,
        waves_file: Path,
        bgc_file: Path,
        tidal_file: Path,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None
    ) -> Path:
        """Load data, filter, and create animation."""
        logger.info("Starting weather visualization")
        
        # Load
        physics = xr.open_dataset(physics_file)
        waves = xr.open_dataset(waves_file)
        bgc = xr.open_dataset(bgc_file)
        tidal = xr.open_dataset(tidal_file)
        
        # Filter by time
        if start_date or end_date:
            logger.info(f"Filtering time: {start_date} to {end_date}")
            physics = physics.sel(time=slice(start_date, end_date))
            waves = waves.sel(time=slice(start_date, end_date))
            bgc = bgc.sel(time=slice(start_date, end_date))
            tidal = tidal.sel(time=slice(start_date, end_date))
        
        # Filter by extent
        if any([min_lon, max_lon, min_lat, max_lat]):
            logger.info(f"Filtering extent: lon=[{min_lon}, {max_lon}], lat=[{min_lat}, {max_lat}]")
            physics = physics.sel(longitude=slice(min_lon, max_lon), latitude=slice(min_lat, max_lat))
            waves = waves.sel(longitude=slice(min_lon, max_lon), latitude=slice(min_lat, max_lat))
            bgc = bgc.sel(longitude=slice(min_lon, max_lon), latitude=slice(min_lat, max_lat))
            tidal = tidal.sel(longitude=slice(min_lon, max_lon), latitude=slice(min_lat, max_lat))
        
        return self.create_animation(physics, waves, bgc, tidal)


def main() -> None:
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create weather animation")
    parser.add_argument("--physics", type=Path, required=True)
    parser.add_argument("--waves", type=Path, required=True)
    parser.add_argument("--bgc", type=Path, required=True)
    parser.add_argument("--tidal", type=Path, required=True)
    parser.add_argument("--start-date", type=str)
    parser.add_argument("--end-date", type=str)
    parser.add_argument("--min-lon", type=float)
    parser.add_argument("--max-lon", type=float)
    parser.add_argument("--min-lat", type=float)
    parser.add_argument("--max-lat", type=float)
    parser.add_argument("--verbose", action="store_true")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    config = WeatherVisualizationConfig()
    visualizer = WeatherVisualizer(config)
    
    output_file = visualizer.visualize_all(
        physics_file=args.physics,
        waves_file=args.waves,
        bgc_file=args.bgc,
        tidal_file=args.tidal,
        start_date=args.start_date,
        end_date=args.end_date,
        min_lon=args.min_lon,
        max_lon=args.max_lon,
        min_lat=args.min_lat,
        max_lat=args.max_lat
    )
    
    print(f"\n✓ Visualization complete: {output_file}")


if __name__ == "__main__":
    main()
