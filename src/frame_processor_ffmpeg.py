"""
ABOUTME: FFmpeg-based frame extraction for faster video processing
ABOUTME: Uses single-pass FFmpeg with filter_complex to extract all scenes at once
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict

from .utils import ensure_dir


class FrameProcessorFFmpeg:
    """
    Extract and process frames from video scenes using FFmpeg.
    
    New design:
    - Single FFmpeg invocation per video
    - Uses filter_complex: [0:v]scale?,split -> per-scene select -> per-scene outputs
    - No temp all_frames folder, no hardlinks, no per-scene ffmpeg calls
    """
    
    def __init__(
        self,
        output_dir: str = "data/processed",
        output_resolution: Optional[Tuple[int, int]] = None,
        jpeg_quality: int = 85,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize FFmpeg frame processor.
        
        Args:
            output_dir: Output directory
            output_resolution: Target (width, height) or None
            jpeg_quality: JPEG quality (1-100)
            logger: Logger instance
        """
        self.output_dir = ensure_dir(output_dir)
        self.output_resolution = output_resolution
        self.jpeg_quality = jpeg_quality
        self.logger = logger or logging.getLogger(__name__)
        
        # GPU / profiling stats
        self.ffmpeg_supports_cuda = False
        self.gpu_attempts = 0
        self.gpu_successes = 0
        self.gpu_failures = 0
        self.cpu_fallbacks = 0
        self.profiling_data: List[Dict] = []
        
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Verify FFmpeg is installed and check for CUDA/NVENC support."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5,
                check=True,
            )
            self.logger.debug("FFmpeg is available")
            
            cuda_check = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                timeout=5,
                text=True,
            )
            out = cuda_check.stdout
            if "h264_nvenc" in out or "hevc_nvenc" in out:
                self.ffmpeg_supports_cuda = True
                self.logger.debug(
                    "FFmpeg has NVIDIA NVENC/NVDEC (CUDA) support compiled in."
                )
            else:
                self.ffmpeg_supports_cuda = False
                self.logger.debug(
                    "FFmpeg does not appear to have CUDA (NVENC) support compiled in."
                )
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg not found. Please install it, e.g. `apt-get install ffmpeg`."
            )
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or b"").decode("utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg version check failed: {msg}")
        except Exception as e:
            raise RuntimeError(f"FFmpeg check failed: {str(e)}")
    
    # ----------------- core single-pass logic -----------------
    
    def _build_scene_dirs(
        self,
        video_name: str,
        scenes: List[Tuple[int, int]],
        flat_structure: bool,
    ) -> List[Path]:
        """Create and return per-scene output directories."""
        scene_dirs: List[Path] = []
        for scene_idx, _ in enumerate(scenes):
            if flat_structure:
                scene_dir = (
                    self.output_dir / "scenes" / f"{video_name}_scene_{scene_idx:03d}"
                )
            else:
                scene_dir = (
                    self.output_dir / video_name / f"scene_{scene_idx:03d}"
                )
            ensure_dir(scene_dir)
            scene_dirs.append(scene_dir)
        return scene_dirs
    
    def _build_filter_complex(
        self,
        scenes: List[Tuple[int, int]],
        resolution: Optional[Tuple[int, int]],
        use_gpu_scale: bool,
    ) -> str:
        """
        Build filter_complex graph:
        - optional scale/scale_cuda
        - split=N
        - per-branch select='between(n, start, end-1)'
        
        Produces labels [o0], [o1], ... for each scene.
        
        Note: Assumes all scenes are valid (end > start). Invalid scenes should be
        filtered out before calling this method.
        """
        n_scenes = len(scenes)
        parts = []
        
        # Input -> scale? -> split
        if resolution is not None:
            w, h = resolution
            scale_name = "scale_cuda" if use_gpu_scale else "scale"
            # [0:v]scale=WxH,split=N[v0][v1]...[vN-1]
            split_outputs = "".join(f"[v{i}]" for i in range(n_scenes))
            parts.append(
                f"[0:v]{scale_name}={w}:{h},split={n_scenes}{split_outputs}"
            )
        else:
            # [0:v]split=N[v0][v1]...[vN-1]
            split_outputs = "".join(f"[v{i}]" for i in range(n_scenes))
            parts.append(f"[0:v]split={n_scenes}{split_outputs}")
        
        # Per-scene select
        for i, (start, end) in enumerate(scenes):
            # end_frame is exclusive – use end-1 in between(n, start, end-1)
            parts.append(
                f"[v{i}]select='between(n,{start},{end-1})'[o{i}]"
            )
        
        return ";".join(parts)
    
    def _run_ffmpeg_single_pass(
        self,
        video_path: str,
        scenes: List[Tuple[int, int]],
        scene_dirs: List[Path],
        use_gpu: bool,
    ) -> List[Dict]:
        """
        Run a single FFmpeg process with filter_complex to extract all scenes.
        
        Returns per-scene metadata list.
        """
        video_name = Path(video_path).stem
        n_scenes = len(scenes)
        
        if n_scenes == 0:
            self.logger.warning(f"No scenes provided for {video_name}")
            return []
        
        # Base cmd
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
        gpu_enabled = False
        
        # Hardware acceleration (decode)
        if use_gpu and self.ffmpeg_supports_cuda:
            self.gpu_attempts += 1
            cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
            gpu_enabled = True
            self.logger.debug(
                f"Attempting GPU acceleration for {video_name} (single-pass)"
            )
        elif use_gpu:
            self.logger.debug(
                f"GPU requested but FFmpeg lacks CUDA support; using CPU for {video_name}"
            )
        
        cmd.extend(["-i", video_path])
        
        # Build filter_complex (scale? + split + select)
        filter_complex = self._build_filter_complex(
            scenes,
            self.output_resolution,
            use_gpu_scale=gpu_enabled,
        )
        cmd.extend(["-filter_complex", filter_complex])
        
        # Map each scene output label [o{i}] to its scene dir
        # Each output needs format specification for image sequences
        qscale = max(1, 31 - self.jpeg_quality // 3)  # rough mapping 1–100 → 1–31
        for i, scene_dir in enumerate(scene_dirs):
            pattern = scene_dir / "frame_%04d.jpg"
            cmd.extend([
                "-map", f"[o{i}]",
                "-vsync", "vfr",  # Variable frame rate - only output selected frames
                "-q:v", str(qscale),  # JPEG quality
                "-f", "image2",  # Image sequence format
                str(pattern)
            ])
        
        start_wall = time.time()
        start_cpu = time.process_time()
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3600,
            )
        except subprocess.TimeoutExpired:
            wall_time = time.time() - start_wall
            self.logger.error(
                f"FFmpeg timeout processing {video_name} after {wall_time:.2f}s"
            )
            return self._empty_scene_metadata(scenes, "ffmpeg timeout")
        except Exception as e:
            wall_time = time.time() - start_wall
            self.logger.error(
                f"FFmpeg error processing {video_name} after {wall_time:.2f}s: {e}"
            )
            return self._empty_scene_metadata(scenes, str(e))
        
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore")
            stderr_lower = stderr.lower()
            
            # Strip banner-ish lines to get a concise error
            error_lines = []
            for line in stderr.split("\n"):
                s = line.strip()
                if not s:
                    continue
                sl = s.lower()
                if any(
                    x in sl
                    for x in [
                        "ffmpeg version",
                        "copyright",
                        "configuration:",
                        "built with",
                        "libdir=",
                        "incdir=",
                    ]
                ):
                    continue
                error_lines.append(s)
            
            actual_error = (
                "\n".join(error_lines[:3])
                if error_lines
                else (stderr.strip()[:200] if stderr.strip() else "Unknown error")
            )
            
            # If GPU was enabled and FFmpeg failed, retry once on CPU
            # No need for keyword matching - any failure with GPU enabled should fallback
            if gpu_enabled:
                self.gpu_failures += 1
                self.cpu_fallbacks += 1
                self.logger.warning(
                    f"GPU run failed for {video_name}, falling back to CPU. "
                    f"Error: {actual_error[:200]}"
                )
                # retry once without GPU
                return self._run_ffmpeg_single_pass(
                    video_path, scenes, scene_dirs, use_gpu=False
                )
            
            # If we get here, either GPU was not enabled or CPU run also failed
            self.logger.warning(
                f"FFmpeg single-pass extraction failed for {video_name}: {actual_error}"
            )
            return self._empty_scene_metadata(scenes, actual_error)
        
        # Success: compute per-scene frame counts
        scene_metadata: List[Dict] = []
        total_frames = 0
        
        for scene_idx, (start_frame, end_frame) in enumerate(scenes):
            scene_dir = scene_dirs[scene_idx]
            frame_files = list(scene_dir.glob("frame_*.jpg"))
            saved = len(frame_files)
            total_frames += saved
            
            scene_metadata.append(
                {
                    "scene_idx": scene_idx,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "total_frames": end_frame - start_frame,
                    "selected_frames": saved,
                    "saved_frames": saved,
                    "output_dir": str(scene_dir),
                    "deduplication_enabled": False,
                }
            )
            
            self.logger.debug(
                f"{video_name} scene {scene_idx}: {saved} frames in {scene_dir}"
            )
        
        wall_time = time.time() - start_wall
        cpu_time = time.process_time() - start_cpu
        iowait_approx = max(0.0, wall_time - cpu_time)
        fps = total_frames / wall_time if wall_time > 0 else 0.0
        
        self.profiling_data.append(
            {
                "wall_time": wall_time,
                "cpu_time": cpu_time,
                "iowait_approx": iowait_approx,
                "frame_count": total_frames,
                "scene_size": total_frames,
                "fps": fps,
            }
        )
        
        if gpu_enabled:
            self.gpu_successes += 1
            self.logger.debug(
                f"GPU acceleration successful for {video_name}: {total_frames} frames"
            )
        
        self.logger.info(
            f"Processed {video_name} (single-pass): {total_frames} frames in "
            f"{wall_time:.2f}s ({fps:.1f} fps)"
        )
        
        return scene_metadata
    
    def _empty_scene_metadata(
        self,
        scenes: List[Tuple[int, int]],
        error: str,
    ) -> List[Dict]:
        """Return metadata list with error information for each scene."""
        meta: List[Dict] = []
        for i, (start, end) in enumerate(scenes):
            meta.append(
                {
                    "scene_idx": i,
                    "start_frame": start,
                    "end_frame": end,
                    "total_frames": end - start,
                    "selected_frames": 0,
                    "saved_frames": 0,
                    "output_dir": "",
                    "deduplication_enabled": False,
                    "error": error,
                }
            )
        return meta
    
    # ----------------- public API -----------------
    
    def process_video(
        self,
        video_path: str,
        scenes: List[Tuple[int, int]],
        flat_structure: bool = False,
        use_gpu: bool = True,
    ) -> List[Dict]:
        """
        Process all scenes in a video in a single FFmpeg pass.
        
        Args:
            video_path: Path to video file
            scenes: List of (start_frame, end_frame) tuples
            flat_structure: Use flat folder structure
            use_gpu: Use GPU acceleration if available (auto-falls back to CPU)
        
        Returns:
            List of scene metadata dicts
        """
        video_name = Path(video_path).stem
        
        # reset stats
        self.gpu_attempts = 0
        self.gpu_successes = 0
        self.gpu_failures = 0
        self.cpu_fallbacks = 0
        self.profiling_data = []
        
        # Filter out invalid scenes (end <= start)
        valid_scenes = []
        valid_scene_indices = []
        for i, (start, end) in enumerate(scenes):
            if end <= start:
                self.logger.warning(
                    f"Scene {i} has non-positive length ({start}, {end}), skipping"
                )
                continue
            valid_scenes.append((start, end))
            valid_scene_indices.append(i)
        
        if len(valid_scenes) == 0:
            self.logger.warning(f"No valid scenes for {video_name}")
            return self._empty_scene_metadata(scenes, "no valid scenes")
        
        self.logger.info(
            f"Processing {len(valid_scenes)} scenes from {video_name} "
            f"(FFmpeg single-pass, GPU={'enabled' if use_gpu else 'disabled'})"
        )
        
        # Build scene dirs only for valid scenes
        scene_dirs = self._build_scene_dirs(video_name, valid_scenes, flat_structure)
        scene_metadata = self._run_ffmpeg_single_pass(
            video_path, valid_scenes, scene_dirs, use_gpu
        )
        
        # Map back to original scene indices for metadata
        # Create a full metadata list with empty entries for invalid scenes
        full_metadata = []
        valid_idx = 0
        for i, (start, end) in enumerate(scenes):
            if i in valid_scene_indices:
                # Update scene_idx to match original index
                meta = scene_metadata[valid_idx].copy()
                meta['scene_idx'] = i
                full_metadata.append(meta)
                valid_idx += 1
            else:
                # Invalid scene - add empty metadata
                full_metadata.append({
                    'scene_idx': i,
                    'start_frame': start,
                    'end_frame': end,
                    'total_frames': end - start,
                    'selected_frames': 0,
                    'saved_frames': 0,
                    'output_dir': '',
                    'deduplication_enabled': False,
                    'error': 'invalid scene (end <= start)',
                })
        
        scene_metadata = full_metadata
        
        # GPU stats logging
        if self.gpu_attempts > 0:
            gpu_success_rate = (
                self.gpu_successes / self.gpu_attempts * 100.0
                if self.gpu_attempts > 0
                else 0.0
            )
            if self.gpu_failures > 0:
                self.logger.warning(
                    f"GPU usage for {video_name}: {self.gpu_successes}/{self.gpu_attempts} "
                    f"successful ({gpu_success_rate:.1f}%), "
                    f"{self.gpu_failures} failures, {self.cpu_fallbacks} CPU fallbacks"
                )
            else:
                self.logger.info(
                    f"GPU usage for {video_name}: {self.gpu_successes}/{self.gpu_attempts} "
                    f"successful ({gpu_success_rate:.1f}%)"
                )
        
        # Profiling summary
        if self.profiling_data:
            p = self.profiling_data[0]  # single entry
            self.logger.info(
                f"FFmpeg profiling for {video_name}: total={p['wall_time']:.1f}s "
                f"(cpu={p['cpu_time']:.1f}s, iowait≈{p['iowait_approx']:.1f}s), "
                f"avg_speed={p['fps']:.1f} fps"
            )
        
        return scene_metadata
