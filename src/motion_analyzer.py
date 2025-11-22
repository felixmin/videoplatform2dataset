"""
Motion Analysis and Stabilization Module

Uses FFmpeg's libvidstab (vidstabdetect/vidstabtransform) to:
1. Detect camera motion in videos
2. Classify scenes as static/moving/uncertain
3. Optionally stabilize videos before frame extraction

Architecture:
- Single pass motion analysis generates .trf file with per-frame transformations
- Per-scene aggregation of motion metrics (max translation, max rotation)
- Optional second pass for video stabilization
"""

import subprocess
import logging
import numpy as np
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class MotionAnalyzer:
    """Analyzes camera motion in videos using FFmpeg's vidstab library."""

    def __init__(self, logger=None):
        """
        Initialize the motion analyzer.

        Args:
            logger: Optional logger instance. If None, creates a new logger.
        """
        self.logger = logger or logging.getLogger(__name__)
        self._check_vidstab()

    def _check_vidstab(self):
        """Verify FFmpeg has libvidstab support."""
        try:
            # Check filters for vidstabdetect
            result = subprocess.run(
                ["ffmpeg", "-filters"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "vidstabdetect" not in result.stdout:
                self.logger.error("FFmpeg missing 'libvidstab'. Motion analysis will fail.")
                self.logger.error("Install via: sudo apt-get install ffmpeg (if standard repo has it) or compile with --enable-libvidstab")
        except Exception as e:
            self.logger.warning(f"Could not verify libvidstab support: {e}")

    def run_vidstab_detect(self, video_path: str, output_trf_path: str) -> bool:
        """
        Run FFmpeg vidstabdetect to generate transform file.

        This analyzes the entire video in one pass and generates a lightweight
        text file containing per-frame transformation data (translations, rotations).

        OPTIMIZATION: Downscales video to 360p height during analysis for 4-10x speedup.
        Motion detection accuracy is not significantly affected by resolution.

        Args:
            video_path: Path to input video file
            output_trf_path: Path where .trf file will be saved

        Returns:
            True if successful, False otherwise
        """
        # Build filter chain: scale to 360p -> vidstabdetect
        # scale=-2:360 maintains aspect ratio with height=360
        # show=0 disables verbose debug output in TRF file (gives us parseable numeric format)
        vf_chain = f"scale=-2:360,vidstabdetect=shakiness=5:accuracy=5:stepsize=6:mincontrast=0.3:show=0:result={output_trf_path}"

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path),
            "-vf", vf_chain,
            "-f", "null", "-"
        ]

        try:
            self.logger.info(f"Running motion analysis on {Path(video_path).name}...")
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Motion analysis failed: {e}")
            if e.stderr:
                self.logger.error(f"FFmpeg stderr: {e.stderr.decode('utf-8', errors='ignore')}")
            return False

    def parse_trf(self, trf_path: str) -> Dict[str, np.ndarray]:
        """
        Parse vidstab .trf file. Handles both 'Simple' and 'Verbose' formats.

        Verbose Format (common with libvidstab):
        Frame N (List M [(LM dx dy x y size contrast ...)])

        Simple Format (older versions):
        frame_num dx dy da ...

        We compute global camera motion by aggregating local motion vectors using median.

        Args:
            trf_path: Path to .trf file

        Returns:
            Dictionary with keys 'dx', 'dy', 'da' containing numpy arrays
        """
        dx, dy, da = [], [], []

        try:
            with open(trf_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith("VID.STAB"):
                        continue

                    # Check for Verbose Format: "Frame 123 (List 35 [(LM ...)])"
                    frame_match = re.search(r"Frame\s+(\d+)", line)
                    if frame_match:
                        # Extract all (LM dx dy ...) vectors using regex
                        # Pattern: (LM followed by two integers (dx, dy)
                        vectors = re.findall(r"\(LM\s+(-?\d+)\s+(-?\d+)", line)

                        if vectors:
                            # Calculate global motion as median of local vectors
                            # Median is robust to moving objects (outliers)
                            dx_vals = [float(v[0]) for v in vectors]
                            dy_vals = [float(v[1]) for v in vectors]

                            dx.append(np.median(dx_vals))
                            dy.append(np.median(dy_vals))
                            da.append(0.0)  # Rotation hard to estimate from raw vectors
                        else:
                            # Frame exists but list is empty -> No motion
                            dx.append(0.0)
                            dy.append(0.0)
                            da.append(0.0)
                        continue

                    # Fallback: Simple Table Format (frame dx dy da ...)
                    parts = line.split()
                    try:
                        val_dx = float(parts[1])
                        val_dy = float(parts[2])
                        val_da = float(parts[3])
                        dx.append(val_dx)
                        dy.append(val_dy)
                        da.append(val_da)
                    except (IndexError, ValueError):
                        continue

            if not dx:
                self.logger.warning(f"No valid motion data found in {trf_path}")

            return {
                "dx": np.array(dx),
                "dy": np.array(dy),
                "da": np.array(da)
            }
        except Exception as e:
            self.logger.error(f"Failed to parse TRF file: {e}")
            return {"dx": np.array([]), "dy": np.array([]), "da": np.array([])}

    def analyze_scenes(
        self,
        scenes: List[Tuple[int, int]],
        motion_data: Dict[str, np.ndarray],
        thresholds: Dict
    ) -> List[Dict]:
        """
        Aggregate motion metrics per scene and assign labels.

        For each scene, calculates:
        - max_trans: Maximum Euclidean translation distance (pixels)
        - max_angle: Maximum absolute rotation (radians)

        Labels are assigned based on thresholds:
        - "static": Both metrics below low thresholds
        - "moving": Either metric above high thresholds
        - "uncertain": In between

        Args:
            scenes: List of (start_frame, end_frame) tuples
            motion_data: Dictionary with dx, dy, da arrays from parse_trf()
            thresholds: Dictionary with threshold values

        Returns:
            List of dictionaries with scene metadata and motion labels
        """
        results = []
        dx = motion_data.get("dx", np.array([]))
        dy = motion_data.get("dy", np.array([]))
        da = motion_data.get("da", np.array([]))

        total_frames = len(dx)

        if total_frames == 0:
            self.logger.warning("No motion data available for scene analysis")
            # Return unknown labels for all scenes
            for scene_idx, (start, end) in enumerate(scenes):
                results.append({
                    "scene_idx": scene_idx,
                    "start_frame": start,
                    "end_frame": end,
                    "max_trans": 0.0,
                    "max_angle": 0.0,
                    "label": "unknown"
                })
            return results

        for scene_idx, (start, end) in enumerate(scenes):
            # Safety clip to valid frame range
            s = max(0, start)
            e = min(end, total_frames)

            if e <= s:
                results.append({
                    "scene_idx": scene_idx,
                    "start_frame": start,
                    "end_frame": end,
                    "max_trans": 0.0,
                    "max_angle": 0.0,
                    "label": "unknown"
                })
                continue

            # Calculate metrics for this scene slice
            scene_dx = dx[s:e]
            scene_dy = dy[s:e]
            scene_da = da[s:e]

            # Euclidean translation distance
            trans = np.sqrt(scene_dx**2 + scene_dy**2)

            max_trans = float(np.max(trans)) if len(trans) > 0 else 0.0
            max_angle = float(np.max(np.abs(scene_da))) if len(scene_da) > 0 else 0.0

            # Labeling logic based on thresholds
            label = "uncertain"
            is_static_trans = max_trans <= thresholds.get('max_trans_low', 10.0)
            is_static_angle = max_angle <= thresholds.get('max_angle_low', 0.02)

            is_moving_trans = max_trans >= thresholds.get('max_trans_high', 50.0)
            is_moving_angle = max_angle >= thresholds.get('max_angle_high', 0.1)

            if is_static_trans and is_static_angle:
                label = "static"
            elif is_moving_trans or is_moving_angle:
                label = "moving"

            results.append({
                "scene_idx": scene_idx,
                "start_frame": start,
                "end_frame": end,
                "max_trans": round(max_trans, 2),
                "max_angle": round(max_angle, 4),
                "label": label
            })

        return results

    def stabilize_video(self, input_path: str, trf_path: str, output_path: str) -> bool:
        """
        Run vidstabtransform to create a stabilized video.

        Uses the transformation data from vidstabdetect to stabilize the video.
        This is a second FFmpeg pass that applies smoothing to reduce camera shake.

        Args:
            input_path: Path to original video
            trf_path: Path to .trf file from vidstabdetect
            output_path: Path where stabilized video will be saved

        Returns:
            True if successful, False otherwise
        """
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-vf", f"vidstabtransform=input={trf_path}:smoothing=30:interpol=bicubic",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",  # High quality intermediate
            "-c:a", "copy",
            str(output_path)
        ]

        try:
            self.logger.info(f"Stabilizing video to {Path(output_path).name}...")
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Stabilization failed: {e}")
            if e.stderr:
                self.logger.error(f"FFmpeg stderr: {e.stderr.decode('utf-8', errors='ignore')}")
            return False
