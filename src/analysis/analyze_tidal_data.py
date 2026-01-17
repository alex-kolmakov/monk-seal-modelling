"""
Analyze tidal data to check daily variation.

This script examines the tidal/sea level data to determine:
1. Temporal resolution (daily, sub-daily, etc.)
2. Magnitude of variations
3. Whether tidal signals are present

Usage:
    python -m src.analysis.analyze_tidal_data
"""

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from datetime import datetime

def analyze_tidal_data():
    """Analyze tidal data characteristics."""
    
    print("="*60)
    print("Tidal Data Analysis")
    print("="*60)
    
    # Load tidal data
    print("\nLoading tidal data...")
    tidal = xr.open_dataset("data/real_long/tidal_2023_2024.nc")
    
    # Basic info
    print(f"\nDataset Variables: {list(tidal.data_vars)}")
    print(f"Coordinates: {list(tidal.coords)}")
    print(f"Time range: {tidal.time.values[0]} to {tidal.time.values[-1]}")
    print(f"Total timesteps: {len(tidal.time)}")
    
    # Check temporal resolution
    time_diffs = np.diff(tidal.time.values)
    time_diff_hours = time_diffs[0].astype('timedelta64[h]').astype(int)
    print(f"\nTemporal resolution: {time_diff_hours} hours ({time_diff_hours/24:.1f} days)")
    
    # Analyze ADT (Absolute Dynamic Topography) - main sea level variable
    adt = tidal['adt']
    sla = tidal['sla']
    
    print(f"\n--- ADT (Absolute Dynamic Topography) ---")
    print(f"Shape: {adt.shape}")
    print(f"Min: {np.nanmin(adt.values):.4f} m")
    print(f"Max: {np.nanmax(adt.values):.4f} m")
    print(f"Mean: {np.nanmean(adt.values):.4f} m")
    print(f"Std Dev: {np.nanstd(adt.values):.4f} m")
    
    print(f"\n--- SLA (Sea Level Anomaly) ---")
    print(f"Shape: {sla.shape}")
    print(f"Min: {np.nanmin(sla.values):.4f} m")
    print(f"Max: {np.nanmax(sla.values):.4f} m")
    print(f"Mean: {np.nanmean(sla.values):.4f} m")
    print(f"Std Dev: {np.nanstd(sla.values):.4f} m")
    
    # Analyze temporal variation at a specific point (near Madeira)
    # Madeira: ~32.5°N, 16.5°W
    target_lat = 32.5
    target_lon = -16.5
    
    # Find nearest grid point
    lat_idx = np.abs(tidal.latitude.values - target_lat).argmin()
    lon_idx = np.abs(tidal.longitude.values - target_lon).argmin()
    
    actual_lat = tidal.latitude.values[lat_idx]
    actual_lon = tidal.longitude.values[lon_idx]
    
    print(f"\n--- Time Series Analysis at ({actual_lat:.2f}°N, {actual_lon:.2f}°W) ---")
    
    # Extract time series
    adt_timeseries = adt.isel(latitude=lat_idx, longitude=lon_idx).values
    sla_timeseries = sla.isel(latitude=lat_idx, longitude=lon_idx).values
    
    # Remove NaN values
    valid_adt = adt_timeseries[~np.isnan(adt_timeseries)]
    valid_sla = sla_timeseries[~np.isnan(sla_timeseries)]
    
    daily_changes = np.array([])
    
    if len(valid_adt) > 0:
        print(f"\nADT Time Series:")
        print(f"  Valid points: {len(valid_adt)}/{len(adt_timeseries)}")
        print(f"  Range: {valid_adt.min():.4f} to {valid_adt.max():.4f} m")
        print(f"  Daily variation (std): {valid_adt.std():.4f} m ({valid_adt.std()*100:.2f} cm)")
        
        # Calculate day-to-day changes
        if len(valid_adt) > 1:
            daily_changes = np.abs(np.diff(valid_adt))
            print(f"  Mean daily change: {daily_changes.mean():.4f} m ({daily_changes.mean()*100:.2f} cm)")
            print(f"  Max daily change: {daily_changes.max():.4f} m ({daily_changes.max()*100:.2f} cm)")
    
    if len(valid_sla) > 0:
        print(f"\nSLA Time Series:")
        print(f"  Valid points: {len(valid_sla)}/{len(sla_timeseries)}")
        print(f"  Range: {valid_sla.min():.4f} to {valid_sla.max():.4f} m")
        print(f"  Daily variation (std): {valid_sla.std():.4f} m ({valid_sla.std()*100:.2f} cm)")
        
        if len(valid_sla) > 1:
            daily_changes = np.abs(np.diff(valid_sla))
            print(f"  Mean daily change: {daily_changes.mean():.4f} m ({daily_changes.mean()*100:.2f} cm)")
            print(f"  Max daily change: {daily_changes.max():.4f} m ({daily_changes.max()*100:.2f} cm)")
    
    # Create visualization
    print("\nCreating visualization...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    # 1. ADT time series
    ax1 = axes[0, 0]
    if len(valid_adt) > 0:
        valid_times = tidal.time.values[~np.isnan(adt_timeseries)]
        ax1.plot(valid_times, valid_adt, 'b-', linewidth=1)
        ax1.set_xlabel('Date')
        ax1.set_ylabel('ADT (m)')
        ax1.set_title(f'Sea Surface Height Time Series\n({actual_lat:.2f}°N, {actual_lon:.2f}°W)')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
    
    # 2. SLA time series
    ax2 = axes[0, 1]
    if len(valid_sla) > 0:
        valid_times = tidal.time.values[~np.isnan(sla_timeseries)]
        ax2.plot(valid_times, valid_sla, 'r-', linewidth=1)
        ax2.set_xlabel('Date')
        ax2.set_ylabel('SLA (m)')
        ax2.set_title(f'Sea Level Anomaly Time Series\n({actual_lat:.2f}°N, {actual_lon:.2f}°W)')
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
    
    # 3. Daily changes histogram (ADT)
    ax3 = axes[1, 0]
    if len(valid_adt) > 1:
        daily_changes = np.diff(valid_adt) * 100  # Convert to cm
        ax3.hist(daily_changes, bins=30, edgecolor='black', alpha=0.7)
        ax3.set_xlabel('Daily Change (cm)')
        ax3.set_ylabel('Frequency')
        ax3.set_title('Distribution of Daily Sea Level Changes (ADT)')
        ax3.axvline(0, color='red', linestyle='--', linewidth=2, label='No change')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # 4. Spatial map of mean ADT
    ax4 = axes[1, 1]
    mean_adt = adt.mean(dim='time').values * 100  # Convert to cm
    im = ax4.imshow(mean_adt, cmap='RdBu_r', aspect='auto',
                    extent=[tidal.longitude.values.min(), tidal.longitude.values.max(),
                           tidal.latitude.values.min(), tidal.latitude.values.max()])
    ax4.plot(actual_lon, actual_lat, 'k*', markersize=15, label='Analysis Point')
    ax4.set_xlabel('Longitude')
    ax4.set_ylabel('Latitude')
    ax4.set_title('Mean Sea Surface Height (cm)')
    plt.colorbar(im, ax=ax4, label='ADT (cm)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_file = "data/real_long/tidal_analysis.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved visualization to: {output_file}")
    
    # Conclusion
    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    
    if time_diff_hours == 24:
        print("\n⚠️  DAILY DATA: This dataset has DAILY resolution (24-hour intervals)")
        print("    Tidal cycles (12-24 hours) are NOT captured in this data.")
        print("    This data shows longer-term sea level variations, not tides.")
    else:
        print(f"\n✓ Sub-daily data: {time_diff_hours} hour resolution")
        print("  Tidal signals may be present.")
    
    if len(valid_adt) > 1:
        mean_change_cm = daily_changes.mean() * 100
        if mean_change_cm < 5:
            print(f"\n⚠️  LOW VARIATION: Mean daily change is only {mean_change_cm:.2f} cm")
            print("    Sea level changes are minimal on a daily basis.")
        else:
            print(f"\n✓ Significant variation: Mean daily change is {mean_change_cm:.2f} cm")
    
    print("\n" + "="*60)
    
    tidal.close()

if __name__ == "__main__":
    analyze_tidal_data()
