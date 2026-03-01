"""
Seal behavior animation — vectorized rendering pipeline.

Creates animated visualizations of seal movements, behavioral states,
and physiological metrics over time.

Performance strategy
--------------------
1. Pre-compute every per-frame value (track slices, colors, bar widths, text)
   as numpy arrays *before* the render loop — eliminates O(n²) pandas iloc.
2. Render the static background (bathymetry, coastlines, cartopy features,
   legend) once with fig.canvas.draw(), then cache the pixel buffer via
   copy_from_bbox.  Each frame restores that cached buffer and only redraws
   the five dynamic artists (track_line, seal_marker, bars, text fields).
3. Pipe raw RGB24 frames directly to an ffmpeg subprocess — no FuncAnimation
   or FFMpegWriter overhead.
4. step_hours subsampling (default 6) reduces frame count ~6× for year-long
   runs while still showing 6-hourly position updates.
"""

import logging
import subprocess
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
        self.config = config
        self.seal_loader = SealDataLoader()
        self.env_loader = EnvironmentalDataLoader()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_animation(
        self, seal_csv: Path, physics_file: Path, output_file: Path | None = None
    ) -> Path:
        """Create seal behavior animation using a vectorized rendering pipeline.

        Args:
            seal_csv: Path to seal tracking CSV
            physics_file: Path to physics NetCDF (for bathymetry)
            output_file: Optional output path (default: config.output_dir/seal_animation.mp4)

        Returns:
            Path to saved animation
        """
        logger.info("Creating seal behavior animation (vectorized pipeline)")

        # ── 1. Load data ───────────────────────────────────────────────
        seal_data = self.seal_loader.load_csv(seal_csv)
        physics = self.env_loader.load_physics(physics_file)
        logger.info(f"Loaded {len(seal_data)} seal records")

        lat_bath, lon_bath, bathymetry = self.env_loader.create_bathymetry(physics)
        physics.close()

        if output_file is None:
            output_file = self.config.output_dir / "seal_animation.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # ── 2. Pre-compute all per-frame arrays ────────────────────────
        arrays = self._precompute_arrays(seal_data)
        step = max(1, self.config.step_hours)
        frame_indices = np.arange(0, len(seal_data), step)
        n_frames = len(frame_indices)
        logger.info(
            f"Subsampled to {n_frames} frames "
            f"(step={step}h, original {len(seal_data)} records)"
        )

        # ── 3. Build figure and static content ────────────────────────
        dpi = self.config.dpi
        fig, ax_map, ax_info, dynamic = self._build_figure(
            seal_data, lat_bath, lon_bath, bathymetry, dpi
        )

        # ── 4. Cache static background ─────────────────────────────────
        fig.canvas.draw()
        background = fig.canvas.copy_from_bbox(fig.bbox)

        # ── 5. Render loop → ffmpeg pipe ───────────────────────────────
        fig_w = int(round(fig.get_figwidth() * dpi))
        fig_h = int(round(fig.get_figheight() * dpi))
        # yuv420p requires even dimensions
        fig_w += fig_w % 2
        fig_h += fig_h % 2

        proc = self._open_ffmpeg(output_file, fig_w, fig_h)

        try:
            self._render_loop(
                fig, ax_map, ax_info, dynamic, arrays,
                frame_indices, n_frames, background, proc
            )
        finally:
            proc.stdin.close()  # type: ignore[union-attr]
            proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg exited with code {proc.returncode}")

        plt.close(fig)
        logger.info(f"Animation saved to {output_file}")
        return output_file

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _precompute_arrays(self, seal_data: pd.DataFrame) -> dict:
        """Extract all columns as numpy arrays and pre-compute derived values."""
        lons = seal_data["lon"].values.astype(float)
        lats = seal_data["lat"].values.astype(float)
        states = seal_data["state"].values.astype(str)
        energies = seal_data["energy"].values.astype(float)
        stomachs = seal_data["stomach"].values.astype(float)
        timestamps = seal_data["timestamp"].values.astype(str)
        agent_ids = seal_data["agent_id"].values.astype(str)
        depths = (
            seal_data["depth"].values.astype(float)
            if "depth" in seal_data.columns
            else np.full(len(seal_data), np.nan)
        )

        # Normalised percentages (0–1)
        energy_pcts = np.clip(energies / 100_000.0, 0.0, 1.0)
        stomach_pcts = np.clip(stomachs / 15.0, 0.0, 1.0)

        # Bar widths (0–0.8 range matches axes layout)
        energy_bar_widths = 0.8 * energy_pcts
        stomach_bar_widths = 0.8 * stomach_pcts

        # Energy bar colour — vectorised string selection
        energy_bar_colors = np.where(
            energy_pcts > 0.7, "green",
            np.where(energy_pcts > 0.4, "orange", "red")
        )

        # Seal marker colors from state_colors map
        sc = self.config.state_colors
        colors = np.array([sc.get(s, "gray") for s in states])

        return dict(
            lons=lons, lats=lats, states=states, energies=energies,
            stomachs=stomachs, timestamps=timestamps, agent_ids=agent_ids,
            depths=depths, energy_pcts=energy_pcts, stomach_pcts=stomach_pcts,
            energy_bar_widths=energy_bar_widths, stomach_bar_widths=stomach_bar_widths,
            energy_bar_colors=energy_bar_colors, colors=colors,
        )

    def _build_figure(self, seal_data, lat_bath, lon_bath, bathymetry, dpi):
        """Construct the matplotlib figure with all static and dynamic artists."""
        fig = plt.figure(figsize=self.config.figsize, dpi=dpi)

        # Map bounds with padding
        min_lat = seal_data["lat"].min() - 0.2
        max_lat = seal_data["lat"].max() + 0.2
        min_lon = seal_data["lon"].min() - 0.2
        max_lon = seal_data["lon"].max() + 0.2

        # ── Map axis (left) ────────────────────────────────────────────
        ax_map = fig.add_subplot(1, 2, 1, projection=ccrs.PlateCarree())
        ax_map.set_extent(  # pyrefly: ignore
            [min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree()
        )

        bath_plot = ax_map.pcolormesh(  # pyrefly: ignore
            lon_bath, lat_bath, bathymetry,
            cmap="Blues_r", shading="auto", transform=ccrs.PlateCarree(),
            alpha=0.4, vmin=0, vmax=500,
        )
        ax_map.add_feature(  # pyrefly: ignore
            cfeature.LAND, facecolor="#D2B48C", edgecolor="black", linewidth=0.8, alpha=0.7
        )
        ax_map.coastlines(resolution="10m", linewidth=1.0, color="black")  # pyrefly: ignore
        plt.colorbar(bath_plot, ax=ax_map, label="Depth (m)", shrink=0.7, pad=0.1)
        gl = ax_map.gridlines(  # pyrefly: ignore
            draw_labels=True, linewidth=0.5, alpha=0.5, linestyle="--"
        )
        gl.right_labels = False
        ax_map.set_title(  # pyrefly: ignore
            "Seal Movement Track", fontsize=14, fontweight="bold", pad=10
        )

        # Dynamic map artists — initialised empty so the static background
        # captures them as invisible (zero-size / no data).
        (track_line,) = ax_map.plot(  # pyrefly: ignore
            [], [], "k-", linewidth=1, alpha=0.5, transform=ccrs.PlateCarree()
        )
        (seal_marker,) = ax_map.plot(  # pyrefly: ignore
            [], [], "o", markersize=12, transform=ccrs.PlateCarree()
        )

        # ── Info panel (right) ─────────────────────────────────────────
        ax_info = fig.add_subplot(1, 2, 2)
        ax_info.set_xlim(0, 1)
        ax_info.set_ylim(0, 1)
        ax_info.axis("off")

        # Static labels and bar backgrounds
        ax_info.text(0.1, 0.77, "Energy", fontsize=11, fontweight="bold")
        ax_info.text(0.1, 0.63, "Stomach", fontsize=11, fontweight="bold")
        ax_info.add_patch(
            Rectangle((0.1, 0.72), 0.8, 0.04, facecolor="lightgray", edgecolor="black")
        )
        ax_info.add_patch(
            Rectangle((0.1, 0.58), 0.8, 0.04, facecolor="lightgray", edgecolor="black")
        )

        # Static legend
        legend_start_y = 0.28
        ax_info.text(
            0.1, legend_start_y + 0.02, "States Legend:", fontsize=11, fontweight="bold"
        )
        for i, (state_name, color) in enumerate(self.config.state_colors.items()):
            y_pos = legend_start_y - (i * 0.04)
            ax_info.plot([0.15], [y_pos], "o", color=color, markersize=10)
            ax_info.text(0.20, y_pos, state_name, fontsize=10, va="center")

        # Dynamic info-panel artists — all start empty/invisible
        info_texts = {
            "title": ax_info.text(0.5, 0.98, "", ha="center", fontsize=20, fontweight="bold"),
            "date": ax_info.text(0.5, 0.92, "", ha="center", fontsize=16),
            "state": ax_info.text(0.1, 0.82, "", fontsize=14, fontweight="bold"),
            "depth": ax_info.text(0.1, 0.40, "", fontsize=12),
            "position": ax_info.text(0.1, 0.35, "", fontsize=10, family="monospace"),
            "energy": ax_info.text(0.1, 0.69, "", fontsize=10),
            "stomach": ax_info.text(0.1, 0.55, "", fontsize=10),
        }

        energy_bar = Rectangle((0.1, 0.72), 0.0, 0.04, facecolor="green", edgecolor="black")
        stomach_bar = Rectangle((0.1, 0.58), 0.0, 0.04, facecolor="orange", edgecolor="black")
        ax_info.add_patch(energy_bar)
        ax_info.add_patch(stomach_bar)

        plt.tight_layout(rect=(0, 0, 0.98, 0.95))

        dynamic = dict(
            track_line=track_line,
            seal_marker=seal_marker,
            info_texts=info_texts,
            energy_bar=energy_bar,
            stomach_bar=stomach_bar,
        )
        return fig, ax_map, ax_info, dynamic

    def _open_ffmpeg(self, output_file: Path, fig_w: int, fig_h: int) -> subprocess.Popen:
        """Open an ffmpeg subprocess that reads raw RGB24 frames from stdin."""
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{fig_w}x{fig_h}",
            "-pix_fmt", "rgb24",
            "-r", str(self.config.fps),
            "-i", "-",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{self.config.bitrate}k",
            str(output_file),
        ]
        logger.info(f"Opening ffmpeg pipe: {fig_w}×{fig_h}px @ {self.config.fps}fps")
        return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _render_loop(
        self, fig, ax_map, ax_info, dynamic, arrays, frame_indices, n_frames, background, proc
    ):
        """Core render loop: restore background → update dynamic artists → pipe frame."""
        track_line = dynamic["track_line"]
        seal_marker = dynamic["seal_marker"]
        info_texts = dynamic["info_texts"]
        energy_bar = dynamic["energy_bar"]
        stomach_bar = dynamic["stomach_bar"]

        lons = arrays["lons"]
        lats = arrays["lats"]
        states = arrays["states"]
        energies = arrays["energies"]
        stomachs = arrays["stomachs"]
        timestamps = arrays["timestamps"]
        agent_ids = arrays["agent_ids"]
        depths = arrays["depths"]
        energy_pcts = arrays["energy_pcts"]
        energy_bar_widths = arrays["energy_bar_widths"]
        stomach_bar_widths = arrays["stomach_bar_widths"]
        energy_bar_colors = arrays["energy_bar_colors"]
        colors = arrays["colors"]

        track_win = self.config.track_hours

        for loop_idx, fi in enumerate(frame_indices):
            # ── Restore static pixel background (O(1) pixel blit) ─────
            fig.canvas.restore_region(background)

            # ── Update map artists ─────────────────────────────────────
            t_start = max(0, fi - track_win)
            track_line.set_data(lons[t_start : fi + 1], lats[t_start : fi + 1])

            seal_marker.set_data([lons[fi]], [lats[fi]])
            seal_marker.set_color(colors[fi])
            seal_marker.set_markeredgecolor("black")
            seal_marker.set_markeredgewidth(2)

            # ── Update info panel ──────────────────────────────────────
            info_texts["title"].set_text(f"Seal {agent_ids[fi]} - Behavior Tracking")
            info_texts["date"].set_text(timestamps[fi])
            info_texts["state"].set_text(f"State: {states[fi]}")
            info_texts["state"].set_color(colors[fi])
            info_texts["energy"].set_text(
                f"Energy: {energies[fi]:.0f} / 100000 ({100 * energy_pcts[fi]:.1f}%)"
            )
            info_texts["stomach"].set_text(f"Stomach: {stomachs[fi]:.1f} / 15.0 kg")

            depth_val = depths[fi]
            info_texts["depth"].set_text(
                f"Depth: {depth_val:.1f} m" if not np.isnan(depth_val) else "Depth: N/A (on land)"
            )
            info_texts["position"].set_text(
                f"Position:\n  Lat: {lats[fi]:.4f}°\n  Lon: {lons[fi]:.4f}°"
            )

            energy_bar.set_width(energy_bar_widths[fi])
            energy_bar.set_facecolor(energy_bar_colors[fi])
            stomach_bar.set_width(stomach_bar_widths[fi])

            # ── Draw only the dynamic artists onto the cached background ─
            ax_map.draw_artist(track_line)
            ax_map.draw_artist(seal_marker)
            for txt in info_texts.values():
                ax_info.draw_artist(txt)
            ax_info.draw_artist(energy_bar)
            ax_info.draw_artist(stomach_bar)

            # ── Blit updated regions ───────────────────────────────────
            fig.canvas.blit(ax_map.bbox)
            fig.canvas.blit(ax_info.bbox)

            # ── Pipe RGBA→RGB bytes to ffmpeg ──────────────────────────
            buf = np.asarray(fig.canvas.buffer_rgba())  # (H, W, 4), zero-copy
            proc.stdin.write(buf[:, :, :3].tobytes())  # type: ignore[union-attr]

            if loop_idx % 200 == 0:
                logger.info(f"  Frame {loop_idx}/{n_frames} ({100 * loop_idx / n_frames:.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# Colony animator — all seals simultaneously on a single map
# ══════════════════════════════════════════════════════════════════════════════

class ColonyAnimator:
    """Animate all seals in a colony run simultaneously.

    Fixed-identity rendering: every seal occupies a permanent slot (sorted by
    agent_id) in the scatter/track arrays throughout the simulation.  Dead seals
    become NaN positions — matplotlib skips them without reshuffling the live
    seals, eliminating the "teleportation jitter" from variable-length arrays.

    Layout uses GridSpec with explicit margins so the info panel never overlaps
    the cartopy map regardless of map extent or tight_layout quirks.

    Example:
        >>> config = SealAnimationConfig(step_hours=6, fps=15)
        >>> anim = ColonyAnimator(config)
        >>> anim.create_animation(
        ...     colony_csv=Path("colony_365d_30seals.csv"),
        ...     physics_file=Path("physics_2022_2023.nc"),
        ... )
    """

    def __init__(self, config: SealAnimationConfig):
        self.config = config
        self.env_loader = EnvironmentalDataLoader()

    # ------------------------------------------------------------------
    def create_animation(
        self,
        colony_csv: Path,
        physics_file: Path,
        output_file: Path | None = None,
    ) -> Path:
        """Render a colony-level animation from a multi-seal CSV.

        Args:
            colony_csv: CSV with columns time, agent_id, lat, lon, state, energy, stomach
            physics_file: Physics NetCDF (for bathymetry background)
            output_file: Output MP4 path (default: same dir as colony_csv)

        Returns:
            Path to saved animation
        """
        logger.info("Creating colony animation")

        # ── 1. Load, dedup, sort ───────────────────────────────────────
        logger.info(f"Loading {colony_csv} …")
        df = pd.read_csv(colony_csv, parse_dates=["time"])
        n_raw = len(df)
        # Deduplicate: handles CSVs that were accidentally appended multiple times
        df = df.drop_duplicates(subset=["time", "agent_id"], keep="last")
        df = df.sort_values(["time", "agent_id"]).reset_index(drop=True)

        agent_ids = sorted(df["agent_id"].unique())
        n_agents = len(agent_ids)
        logger.info(
            f"  {n_raw:,} raw rows → {len(df):,} after dedup | {n_agents} seals"
        )

        physics = self.env_loader.load_physics(physics_file)
        lat_bath, lon_bath, bathymetry = self.env_loader.create_bathymetry(physics)
        physics.close()

        if output_file is None:
            output_file = colony_csv.with_name(
                colony_csv.stem + "_colony_animation.mp4"
            )
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # ── 2. Subsample timestamps ────────────────────────────────────
        all_times = sorted(df["time"].unique())
        step = max(1, self.config.step_hours)
        sampled_times = all_times[::step]
        n_frames = len(sampled_times)
        logger.info(
            f"  {len(all_times)} timesteps → {n_frames} frames (step={step}h)"
        )

        # ── 3. Pivot into fixed (n_frames × n_agents) arrays ──────────
        # NaN = seal absent/dead at that timestep.  Fixed size means
        # scatter/track arrays never change length → no index shuffle.
        lats_p, lons_p, states_p, energies_p = self._build_pivot(
            df, sampled_times, agent_ids
        )

        # ── 4. Map extent: 98th-percentile bounds, not raw min/max ────
        # Raw min/max blows up the extent when seals escape far offshore.
        map_extent = [
            float(np.percentile(df["lon"], 1)) - 0.3,
            float(np.percentile(df["lon"], 99)) + 0.3,
            float(np.percentile(df["lat"], 1)) - 0.3,
            float(np.percentile(df["lat"], 99)) + 0.3,
        ]

        # ── 5. Build figure ────────────────────────────────────────────
        dpi = self.config.dpi
        track_win = max(1, self.config.track_hours // step)
        fig, ax_map, ax_info, scatter, track_lines, info_artists = self._build_figure(
            lat_bath, lon_bath, bathymetry, n_agents, map_extent, dpi
        )

        # ── 6. Settle layout + measure ACTUAL pixel dimensions ─────────
        # fig.get_figwidth() * dpi is unreliable: cartopy adjusts the figure
        # size during the first draw() to enforce its map aspect ratio.
        # If we tell ffmpeg the pre-draw size but buffer_rgba() returns a
        # different size, ffmpeg misinterprets the raw byte stream and the
        # frame boundaries are wrong (visible as two "halves" per frame).
        # The fix: do one draw() to settle everything, then read real dims.
        fig.canvas.draw()
        _probe = np.asarray(fig.canvas.buffer_rgba())
        actual_h, actual_w = _probe.shape[:2]
        # yuv420p codec requires even pixel dimensions
        actual_w -= actual_w % 2
        actual_h -= actual_h % 2
        logger.info(f"  Actual frame size after layout settle: {actual_w}×{actual_h}px")
        proc = self._open_ffmpeg(output_file, actual_w, actual_h)

        # ── 7. Render loop ─────────────────────────────────────────────
        try:
            self._render_loop(
                fig, ax_map, ax_info, scatter, track_lines, info_artists,
                lats_p, lons_p, states_p, energies_p,
                sampled_times, n_agents, n_frames, track_win, proc,
                actual_w, actual_h,
            )
        finally:
            proc.stdin.close()  # type: ignore[union-attr]
            proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg exited with code {proc.returncode}")

        plt.close(fig)
        logger.info(f"Colony animation saved to {output_file}")
        return output_file

    # ------------------------------------------------------------------
    def _build_pivot(
        self,
        df: pd.DataFrame,
        sampled_times: list,
        agent_ids: list,
    ) -> tuple:
        """Vectorised pivot: (n_frames × n_agents) numpy arrays, NaN for absent seals."""
        n_frames = len(sampled_times)
        n_agents = len(agent_ids)

        agent_to_idx = {a: i for i, a in enumerate(agent_ids)}
        time_to_idx = {t: i for i, t in enumerate(sampled_times)}

        lats_p = np.full((n_frames, n_agents), np.nan)
        lons_p = np.full((n_frames, n_agents), np.nan)
        states_p = np.full((n_frames, n_agents), "", dtype=object)
        energies_p = np.full((n_frames, n_agents), np.nan)

        sampled_set = set(sampled_times)
        df_sub = df[df["time"].isin(sampled_set)].copy()
        df_sub = df_sub[df_sub["agent_id"].isin(agent_to_idx)].copy()
        df_sub["_ti"] = df_sub["time"].map(time_to_idx)
        df_sub["_ai"] = df_sub["agent_id"].map(agent_to_idx)
        df_sub = df_sub.dropna(subset=["_ti", "_ai"])

        ti = df_sub["_ti"].values.astype(int)
        ai = df_sub["_ai"].values.astype(int)
        lats_p[ti, ai] = df_sub["lat"].values
        lons_p[ti, ai] = df_sub["lon"].values
        states_p[ti, ai] = df_sub["state"].values
        energies_p[ti, ai] = df_sub["energy"].values

        logger.info(f"  Pivot built: {n_frames} × {n_agents} arrays")
        return lats_p, lons_p, states_p, energies_p

    # ------------------------------------------------------------------
    def _build_figure(
        self, lat_bath, lon_bath, bathymetry, n_agents, map_extent, dpi
    ):
        """Build figure with hard-coded axes positions — nothing can move anything else.

        The root cause of the layout corruption was plt.colorbar(ax=ax_map), which
        internally shrinks ax_map's bounding box to make room for the colorbar.
        Cartopy then re-enforces its aspect ratio on the now-smaller axes, producing
        a completely different final layout.  The fix is two-fold:
          1. Use fig.add_axes() with explicit fractional positions for every panel.
          2. Pass cax=cbar_ax to colorbar so it uses a pre-placed axes and never
             touches ax_map's position.
        """
        fig = plt.figure(figsize=self.config.figsize, dpi=dpi)

        # ── Hard-coded panel positions (figure fraction) ───────────────
        # Map:     left 60 %   [left, bottom, width, height]
        # Cbar:    thin strip between map and info
        # Info:    right 33 %
        # Cartopy may centre the map within its box (aspect enforcement)
        # but will never overflow past x = 0.60.
        ax_map = fig.add_axes(
            [0.01, 0.05, 0.58, 0.90], projection=ccrs.PlateCarree()
        )
        cbar_ax = fig.add_axes([0.605, 0.18, 0.016, 0.58])
        ax_info = fig.add_axes([0.64, 0.05, 0.35, 0.90])

        # ── Map content ────────────────────────────────────────────────
        ax_map.set_extent(map_extent, crs=ccrs.PlateCarree())  # pyrefly: ignore

        bath_plot = ax_map.pcolormesh(  # pyrefly: ignore
            lon_bath, lat_bath, bathymetry,
            cmap="Blues_r", shading="auto", transform=ccrs.PlateCarree(),
            alpha=0.5, vmin=0, vmax=500,
        )
        ax_map.add_feature(  # pyrefly: ignore
            cfeature.LAND, facecolor="#D2B48C", edgecolor="black", linewidth=0.8, alpha=0.7
        )
        ax_map.coastlines(resolution="10m", linewidth=1.0, color="black")  # pyrefly: ignore

        # cax= hands the colorbar a pre-placed axes → ax_map is never moved
        plt.colorbar(bath_plot, cax=cbar_ax, label="Depth (m)")

        gl = ax_map.gridlines(  # pyrefly: ignore
            draw_labels=True, linewidth=0.5, alpha=0.5, linestyle="--"
        )
        gl.right_labels = False
        gl.top_labels = False

        ax_map.set_title(  # pyrefly: ignore
            f"Colony of {n_agents} Mediterranean Monk Seals",
            fontsize=13, fontweight="bold", pad=8,
        )

        # Per-seal track lines (one Line2D per agent, initially empty)
        track_lines = []
        for _ in range(n_agents):
            (line,) = ax_map.plot(  # pyrefly: ignore
                [], [], "-",
                linewidth=0.7, alpha=0.35, color="gray",
                transform=ccrs.PlateCarree(),
            )
            track_lines.append(line)

        # Scatter with n_agents fixed NaN slots — dead seals stay invisible
        # without displacing any live seal's index position.
        nan_xy = np.full((n_agents, 2), np.nan)
        scatter = ax_map.scatter(  # pyrefly: ignore
            nan_xy[:, 0], nan_xy[:, 1],
            s=60, zorder=5,
            c=["#cccccc"] * n_agents,
            edgecolors="black", linewidths=0.8,
            transform=ccrs.PlateCarree(),
        )

        # ── Info panel ─────────────────────────────────────────────────
        ax_info.set_xlim(0, 1)
        ax_info.set_ylim(0, 1)
        ax_info.axis("off")

        # Static decorations — drawn once, never updated
        ax_info.text(0.5, 0.96, "Colony Status",
                     ha="center", fontsize=14, fontweight="bold")
        ax_info.text(0.08, 0.715, "Mean Energy", fontsize=11, fontweight="bold")
        ax_info.add_patch(
            Rectangle((0.08, 0.660), 0.84, 0.040,
                       facecolor="lightgray", edgecolor="black")
        )

        legend_y = 0.30
        ax_info.text(0.08, legend_y + 0.048, "Behavioural States:",
                     fontsize=11, fontweight="bold")
        for i, (state_name, color) in enumerate(self.config.state_colors.items()):
            y = legend_y - i * 0.060
            ax_info.plot([0.12], [y], "o", color=color, markersize=9)
            ax_info.text(0.21, y, state_name, fontsize=10, va="center")

        # Dynamic artists — all start with empty / zero values
        info_artists: dict = {
            "date": ax_info.text(0.5, 0.89, "", ha="center", fontsize=13),
            "day": ax_info.text(0.5, 0.84, "", ha="center", fontsize=10,
                                color="gray"),
            "alive": ax_info.text(0.5, 0.78, "", ha="center", fontsize=28,
                                  fontweight="bold"),
            "alive_sub": ax_info.text(0.5, 0.73, "", ha="center", fontsize=10,
                                      color="gray"),
            "energy_val": ax_info.text(0.08, 0.620, "", fontsize=10),
            "state_counts": ax_info.text(0.08, 0.550, "", fontsize=10,
                                         family="monospace", va="top"),
        }
        energy_bar = Rectangle(
            (0.08, 0.660), 0.0, 0.040, facecolor="green", edgecolor="black"
        )
        ax_info.add_patch(energy_bar)
        info_artists["energy_bar"] = energy_bar

        return fig, ax_map, ax_info, scatter, track_lines, info_artists

    # ------------------------------------------------------------------
    def _open_ffmpeg(self, output_file: Path, fig_w: int, fig_h: int) -> subprocess.Popen:
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{fig_w}x{fig_h}",
            "-pix_fmt", "rgb24",
            "-r", str(self.config.fps),
            "-i", "-",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{self.config.bitrate}k",
            str(output_file),
        ]
        logger.info(f"Opening ffmpeg pipe: {fig_w}×{fig_h}px @ {self.config.fps}fps")
        return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # ------------------------------------------------------------------
    def _render_loop(
        self,
        fig,
        ax_map,
        ax_info,  # noqa: ARG002  (kept for future blit restoration)
        scatter,
        track_lines,
        info_artists,
        lats_p: np.ndarray,
        lons_p: np.ndarray,
        states_p: np.ndarray,
        energies_p: np.ndarray,
        sampled_times: list,
        n_agents: int,
        n_frames: int,
        track_win: int,
        proc: subprocess.Popen,
        actual_w: int,
        actual_h: int,
    ) -> None:
        state_colors = self.config.state_colors
        energy_bar = info_artists["energy_bar"]
        t0 = pd.Timestamp(sampled_times[0])
        t_last = pd.Timestamp(sampled_times[-1])
        total_days = (t_last - t0).days + 1

        for fi in range(n_frames):
            alive_mask = ~np.isnan(lats_p[fi])
            n_alive = int(alive_mask.sum())

            # ── Scatter: fixed n_agents slots, NaN for dead ────────────
            # NaN lon/lat → cartopy transform returns NaN display coords
            # → Agg skips rendering that path → no shuffle artefact.
            xy = np.column_stack([lons_p[fi], lons_p[fi]])  # placeholder shape
            xy = np.column_stack([lons_p[fi], lats_p[fi]])
            facecolors = [
                state_colors.get(str(states_p[fi, j]), "#cccccc")
                for j in range(n_agents)
            ]
            scatter.set_offsets(xy)
            scatter.set_facecolors(facecolors)

            # ── Track lines: per-seal 24h history ─────────────────────
            t_start = max(0, fi - track_win)
            for j in range(n_agents):
                if not alive_mask[j]:
                    track_lines[j].set_data([], [])
                    continue
                seg_lons = lons_p[t_start : fi + 1, j]
                seg_lats = lats_p[t_start : fi + 1, j]
                ok = ~np.isnan(seg_lons)
                track_lines[j].set_data(seg_lons[ok], seg_lats[ok])
                track_lines[j].set_color(
                    state_colors.get(str(states_p[fi, j]), "gray")
                )

            # ── Info panel ─────────────────────────────────────────────
            ts = pd.Timestamp(sampled_times[fi])
            day_num = (ts - t0).days + 1
            info_artists["date"].set_text(ts.strftime("%d %b %Y  %H:%M"))
            info_artists["day"].set_text(f"Day {day_num} of {total_days}")

            alive_color = (
                "green" if n_alive >= n_agents * 0.8
                else "orange" if n_alive >= n_agents * 0.5
                else "red"
            )
            info_artists["alive"].set_text(f"{n_alive} / {n_agents}")
            info_artists["alive"].set_color(alive_color)
            info_artists["alive_sub"].set_text("seals alive")

            alive_e = energies_p[fi, alive_mask]
            mean_e = float(np.mean(alive_e)) if n_alive > 0 else 0.0
            mean_e_pct = min(max(mean_e / 100_000.0, 0.0), 1.0)
            info_artists["energy_val"].set_text(
                f"{mean_e:,.0f} kJ  ({100 * mean_e_pct:.1f}%)"
            )
            energy_bar.set_width(0.84 * mean_e_pct)
            energy_bar.set_facecolor(
                "green" if mean_e_pct > 0.7 else "orange" if mean_e_pct > 0.4 else "red"
            )

            # State breakdown — one line per active state
            cnts: dict[str, int] = {}
            for j in range(n_agents):
                if alive_mask[j]:
                    s = str(states_p[fi, j])
                    cnts[s] = cnts.get(s, 0) + 1
            sc_text = "\n".join(
                f"  {s:<14} {n:>3}" for s, n in sorted(cnts.items())
            )
            info_artists["state_counts"].set_text(sc_text)

            # ── Full redraw → pipe RGB to ffmpeg ───────────────────────
            fig.canvas.draw()
            buf = np.asarray(fig.canvas.buffer_rgba())
            # Crop to the settled dimensions measured before the loop.
            # buffer_rgba() may return a slightly larger array if cartopy
            # added padding; cropping ensures every frame is exactly
            # actual_w × actual_h, which ffmpeg requires for a valid stream.
            frame = buf[:actual_h, :actual_w, :3]
            proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]

            if fi % 100 == 0:
                logger.info(
                    f"  Frame {fi}/{n_frames} ({100 * fi / n_frames:.1f}%) "
                    f"— {n_alive} alive"
                )


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seal behavior animation")
    sub = parser.add_subparsers(dest="mode", help="Animation mode")

    # ── single-seal mode ──────────────────────────────────────────────
    single = sub.add_parser("single", help="Animate one seal's track")
    single.add_argument("--seal-csv", type=Path, required=True)
    single.add_argument("--physics-file", type=Path, required=True)
    single.add_argument("--output", type=Path)
    single.add_argument("--fps", type=int, default=10)
    single.add_argument("--track-hours", type=int, default=24)
    single.add_argument("--step-hours", type=int, default=6)
    single.add_argument("--dpi", type=int, default=100)

    # ── colony mode ───────────────────────────────────────────────────
    colony = sub.add_parser("colony", help="Animate full colony simultaneously")
    colony.add_argument("--colony-csv", type=Path, required=True)
    colony.add_argument("--physics-file", type=Path, required=True)
    colony.add_argument("--output", type=Path)
    colony.add_argument("--fps", type=int, default=15)
    colony.add_argument("--step-hours", type=int, default=6)
    colony.add_argument("--dpi", type=int, default=100)

    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    config = SealAnimationConfig(
        fps=args.fps,
        step_hours=args.step_hours,
        dpi=args.dpi,
        track_hours=getattr(args, "track_hours", 24),
    )

    if args.mode == "colony":
        anim = ColonyAnimator(config)
        out = anim.create_animation(
            colony_csv=args.colony_csv,
            physics_file=args.physics_file,
            output_file=args.output,
        )
    else:
        anim_single = SealBehaviorAnimator(config)
        out = anim_single.create_animation(
            seal_csv=args.seal_csv,
            physics_file=args.physics_file,
            output_file=args.output,
        )

    print(f"\nAnimation complete: {out}")


if __name__ == "__main__":
    main()
