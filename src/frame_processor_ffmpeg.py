"""
ABOUTME: FFmpeg-based frame extraction for faster video processing
ABOUTME: Replaces OpenCV with FFmpeg batch extraction, ~5-10x speedup
"""

import os
import logging
import subprocess
import time
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

from .utils import ensure_dir


class FrameProcessorFFmpeg:
    """
    Extract and process frames from video scenes using FFmpeg.
    Much faster than OpenCV due to batch extraction and less memory copying.
    """
    
    def __init__(
        self,
        output_dir: str = "data/processed",
        output_resolution: Optional[Tuple[int, int]] = None,
        jpeg_quality: int = 85,
        num_workers: Optional[int] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize FFmpeg frame processor.
        
        Args:
            output_dir: Output directory
            output_resolution: Target (width, height) or None
            jpeg_quality: JPEG quality (1-100)
            num_workers: Number of parallel workers (None = auto-detect)
            logger: Logger instance
        """
        self.output_dir = ensure_dir(output_dir)
        self.output_resolution = output_resolution
        self.jpeg_quality = jpeg_quality
        # Default to 8 workers (increased from 4 for better parallelism)
        self.num_workers = num_workers or min(8, cpu_count())
        self.logger = logger or logging.getLogger(__name__)
        
        # Track GPU usage statistics
        self.gpu_attempts = 0
        self.gpu_successes = 0
        self.gpu_failures = 0
        self.cpu_fallbacks = 0
        
        # Track profiling statistics
        self.profiling_data = []  # List of (wall_time, cpu_time, frame_count, scene_size)
        
        # Check FFmpeg availability
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Verify FFmpeg is installed and accessible."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg returned non-zero exit code")
            self.logger.debug("FFmpeg is available")
            
            # Check if FFmpeg supports CUDA (optional, for GPU acceleration)
            version_output = result.stdout.decode('utf-8', errors='ignore').lower()
            self.ffmpeg_supports_cuda = 'cuda' in version_output or 'nvenc' in version_output
            if not self.ffmpeg_supports_cuda:
                self.logger.debug("FFmpeg does not appear to have CUDA support compiled in")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Please install it: apt-get install ffmpeg")
        except Exception as e:
            raise RuntimeError(f"FFmpeg check failed: {str(e)}")
    
    def _extract_scene_with_ffmpeg(
        self,
        video_path: str,
        start_frame: int,
        end_frame: int,
        output_dir: Path,
        resolution: Optional[Tuple[int, int]] = None,
        quality: int = 85,
        use_gpu: bool = True
    ) -> int:
        """
        Extract frames from a scene using FFmpeg (with optional GPU acceleration).
        
        Args:
            video_path: Path to video file
            start_frame: Start frame index (inclusive)
            end_frame: End frame index (exclusive)
            output_dir: Directory to save frames
            resolution: Target (width, height) or None
            quality: JPEG quality (1-100)
            use_gpu: Use GPU-accelerated decoding if available
        
        Returns:
            Number of frames extracted
        """
        ensure_dir(output_dir)
        
        # Build FFmpeg command with GPU support
        cmd = ['ffmpeg']
        gpu_enabled = False
        
        # Add GPU hardware acceleration if requested
        if use_gpu:
            # Check if FFmpeg supports CUDA before attempting
            if not getattr(self, 'ffmpeg_supports_cuda', False):
                self.logger.debug(
                    f"GPU requested but FFmpeg doesn't support CUDA, using CPU for scene [{start_frame}-{end_frame}]"
                )
                gpu_enabled = False
            else:
                self.gpu_attempts += 1
                # Try NVIDIA NVDEC (H.264 supported on most NVIDIA GPUs)
                cmd.extend(['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])
                gpu_enabled = True
                self.logger.debug(f"Attempting GPU acceleration for scene [{start_frame}-{end_frame}]")
        else:
            # Log when CPU is used directly (not as fallback)
            self.logger.debug(f"Using CPU-only FFmpeg for scene [{start_frame}-{end_frame}]")
        
        cmd.extend(['-i', video_path])
        
        # Add video filter for frame range selection and resizing
        filters = []
        
        # Select frame range: select='between(n,start,end)'
        filters.append(f"select='between(n,{start_frame},{end_frame-1})'")
        
        # Add scaling if needed
        if resolution:
            w, h = resolution
            # Use GPU-accelerated scaling if available
            if gpu_enabled:
                filters.append(f"scale_cuda={w}:{h}")
            else:
                filters.append(f"scale={w}:{h}")
        
        filter_str = ','.join(filters)
        
        cmd.extend([
            '-hide_banner',  # Suppress version/banner output
            '-loglevel', 'error',  # Only show errors, not warnings/info
            '-vf', filter_str,
            '-vsync', 'vfr',  # Variable frame rate - only output selected frames
            '-q:v', str(max(1, 31 - quality // 3)),  # Convert quality to qscale (1-31, lower=better)
            '-start_number', '0',  # Start numbering from 0
            str(output_dir / 'frame_%04d.jpg')
        ])
        
        # Start profiling
        start_wall = time.time()
        start_cpu = time.process_time()
        scene_size = end_frame - start_frame
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minute timeout per scene
            )
            
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                stderr_lower = stderr.lower()
                
                # Extract actual error message (skip version/banner output)
                error_lines = []
                for line in stderr.split('\n'):
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    line_lower = line_stripped.lower()
                    # Skip version/banner lines
                    if any(x in line_lower for x in ['ffmpeg version', 'copyright', 'configuration:', 'built with', 'libdir=', 'incdir=']):
                        continue
                    # Collect actual error lines
                    error_lines.append(line_stripped)
                
                # Get actual error (first few meaningful lines, or fallback to truncated stderr)
                if error_lines:
                    actual_error = '\n'.join(error_lines[:3])
                else:
                    # If all lines were banner, just show a short snippet
                    actual_error = stderr.strip()[:200] if stderr.strip() else "Unknown error"
                
                # Check if it's a GPU-related error and retry with CPU
                gpu_error_keywords = [
                    'cuda', 'hwaccel', 'nvenc', 'nvdec',
                    'hardware acceleration', 'hwaccel_device',
                    'not found', 'not available', 'not supported',
                    'no device', 'device not found', 'cannot find',
                    'invalid argument', 'unknown option'
                ]
                
                has_gpu_error = any(keyword in stderr_lower for keyword in gpu_error_keywords)
                
                if gpu_enabled and has_gpu_error:
                    self.gpu_failures += 1
                    self.cpu_fallbacks += 1
                    self.logger.warning(
                        f"GPU acceleration failed for scene [{start_frame}-{end_frame}], falling back to CPU. "
                        f"Error: {actual_error[:200]}"
                    )
                    return self._extract_scene_with_ffmpeg(
                        video_path, start_frame, end_frame, output_dir,
                        resolution, quality, use_gpu=False
                    )
                
                # Log error (without version banner)
                error_preview = actual_error[:500] if actual_error else "Unknown error (check FFmpeg output)"
                self.logger.warning(
                    f"FFmpeg extraction failed for scene [{start_frame}-{end_frame}]: {error_preview}"
                )
                return 0
            
            # Count extracted frames
            frame_files = list(output_dir.glob('frame_*.jpg'))
            frame_count = len(frame_files)
            
            # Calculate profiling metrics
            wall_time = time.time() - start_wall
            cpu_time = time.process_time() - start_cpu
            iowait_approx = max(0, wall_time - cpu_time)
            fps = frame_count / wall_time if wall_time > 0 else 0
            
            # Store profiling data
            self.profiling_data.append({
                'wall_time': wall_time,
                'cpu_time': cpu_time,
                'iowait_approx': iowait_approx,
                'frame_count': frame_count,
                'scene_size': scene_size,
                'fps': fps
            })
            
            # Log profiling at DEBUG level (detailed per-scene)
            self.logger.debug(
                f"Scene [{start_frame}-{end_frame}]: {frame_count} frames in {wall_time:.2f}s "
                f"(cpu={cpu_time:.2f}s, iowait≈{iowait_approx:.2f}s, {fps:.1f} fps)"
            )
            
            # Log GPU success if GPU was enabled
            if gpu_enabled:
                self.gpu_successes += 1
                self.logger.debug(f"GPU acceleration successful for scene [{start_frame}-{end_frame}]: {frame_count} frames")
            
            return frame_count
            
        except subprocess.TimeoutExpired:
            wall_time = time.time() - start_wall
            self.logger.error(f"FFmpeg timeout extracting scene from {video_path} after {wall_time:.2f}s")
            return 0
        except Exception as e:
            wall_time = time.time() - start_wall
            self.logger.error(f"FFmpeg extraction error after {wall_time:.2f}s: {str(e)}")
            return 0
    
    def process_scene(
        self,
        video_path: str,
        scene: Tuple[int, int],
        scene_idx: int,
        video_name: str,
        flat_structure: bool = False,
        use_gpu: bool = True
    ) -> Dict:
        """
        Extract frames from a scene.
        
        Args:
            video_path: Path to video file
            scene: (start_frame, end_frame)
            scene_idx: Scene index
            video_name: Video name for folder
            flat_structure: Use flat folder structure
            use_gpu: Use GPU-accelerated FFmpeg
        
        Returns:
            Scene processing metadata
        """
        start_frame, end_frame = scene
        
        # Determine output directory
        if flat_structure:
            scene_dir = self.output_dir / "scenes" / f"{video_name}_scene_{scene_idx:03d}"
        else:
            scene_dir = self.output_dir / video_name / f"scene_{scene_idx:03d}"
        
        # Extract frames using FFmpeg (with GPU acceleration)
        saved_count = self._extract_scene_with_ffmpeg(
            video_path,
            start_frame,
            end_frame,
            scene_dir,
            self.output_resolution,
            self.jpeg_quality,
            use_gpu=use_gpu
        )
        
        metadata = {
            'scene_idx': scene_idx,
            'start_frame': start_frame,
            'end_frame': end_frame,
            'total_frames': end_frame - start_frame,
            'selected_frames': end_frame - start_frame,
            'saved_frames': saved_count,
            'output_dir': str(scene_dir),
            'deduplication_enabled': False
        }
        
        self.logger.debug(
            f"Processed scene {scene_idx}: {saved_count} frames saved to {scene_dir}"
        )
        
        return metadata
    
    def _process_single_scene(
        self,
        video_path: str,
        scene: Tuple[int, int],
        scene_idx: int,
        video_name: str,
        flat_structure: bool,
        use_gpu: bool
    ) -> Dict:
        """
        Process a single scene (worker function for parallel processing).
        
        Args:
            video_path: Path to video file
            scene: (start_frame, end_frame) tuple
            scene_idx: Scene index
            video_name: Video name for folder
            flat_structure: Use flat folder structure
            use_gpu: Use GPU-accelerated FFmpeg
        
        Returns:
            Scene metadata dict
        """
        try:
            return self.process_scene(
                video_path,
                scene,
                scene_idx,
                video_name,
                flat_structure,
                use_gpu=use_gpu
            )
        except Exception as e:
            self.logger.error(f"Error processing scene {scene_idx}: {str(e)}")
            start_frame, end_frame = scene
            return {
                'scene_idx': scene_idx,
                'start_frame': start_frame,
                'end_frame': end_frame,
                'total_frames': end_frame - start_frame,
                'selected_frames': 0,
                'saved_frames': 0,
                'output_dir': '',
                'deduplication_enabled': False,
                'error': str(e)
            }
    
    def process_video(
        self,
        video_path: str,
        scenes: List[Tuple[int, int]],
        flat_structure: bool = False,
        use_gpu: bool = True
    ) -> List[Dict]:
        """
        Process all scenes in a video with optional parallel processing.

        Args:
            video_path: Path to video file
            scenes: List of (start_frame, end_frame) tuples
            flat_structure: Use flat folder structure
            use_gpu: Use GPU acceleration if available (auto-falls back to CPU on error)

        Returns:
            List of scene metadata dicts
        """
        video_name = Path(video_path).stem
        
        # Reset GPU statistics and profiling for this video
        self.gpu_attempts = 0
        self.gpu_successes = 0
        self.gpu_failures = 0
        self.cpu_fallbacks = 0
        self.profiling_data = []
        
        self.logger.info(
            f"Processing {len(scenes)} scenes from {video_name} "
            f"(FFmpeg, workers={self.num_workers}, GPU={'enabled' if use_gpu else 'disabled'})"
        )
        
        scene_metadata = []
        
        # Use parallel processing if we have multiple scenes and workers
        if len(scenes) > 1 and self.num_workers > 1:
            # Prepare arguments for each scene
            scene_args = [
                (video_path, scene, scene_idx, video_name, flat_structure, use_gpu)
                for scene_idx, scene in enumerate(scenes)
            ]
            
            # Process scenes in parallel
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                # Submit all tasks
                future_to_scene = {
                    executor.submit(self._process_single_scene, *args): idx
                    for idx, args in enumerate(scene_args)
                }
                
                # Collect results with progress bar
                scene_results = [None] * len(scenes)
                
                for future in tqdm(
                    as_completed(future_to_scene),
                    total=len(scenes),
                    desc=f"Processing {video_name}",
                    unit="scene"
                ):
                    scene_idx = future_to_scene[future]
                    try:
                        scene_results[scene_idx] = future.result()
                    except Exception as e:
                        self.logger.error(f"Error processing scene {scene_idx}: {str(e)}")
                        start_frame, end_frame = scenes[scene_idx]
                        scene_results[scene_idx] = {
                            'scene_idx': scene_idx,
                            'start_frame': start_frame,
                            'end_frame': end_frame,
                            'total_frames': end_frame - start_frame,
                            'selected_frames': 0,
                            'saved_frames': 0,
                            'output_dir': '',
                            'deduplication_enabled': False,
                            'error': str(e)
                        }
                
                scene_metadata = scene_results
        else:
            # Sequential processing (single scene or single worker)
            for scene_idx, scene in enumerate(tqdm(
                scenes, 
                desc=f"Processing {video_name}", 
                unit="scene"
            )):
                metadata = self.process_scene(
                    video_path,
                    scene,
                    scene_idx,
                    video_name,
                    flat_structure,
                    use_gpu=use_gpu
                )
                scene_metadata.append(metadata)
        
        total_frames = sum(m.get('saved_frames', 0) for m in scene_metadata)
        self.logger.info(f"Processed {video_name}: {total_frames} frames extracted")
        
        # Log GPU usage statistics
        if self.gpu_attempts > 0:
            gpu_success_rate = (self.gpu_successes / self.gpu_attempts * 100) if self.gpu_attempts > 0 else 0
            if self.gpu_failures > 0:
                self.logger.warning(
                    f"GPU usage for {video_name}: {self.gpu_successes}/{self.gpu_attempts} successful "
                    f"({gpu_success_rate:.1f}%), {self.gpu_failures} failures, {self.cpu_fallbacks} CPU fallbacks"
                )
            else:
                self.logger.info(
                    f"GPU usage for {video_name}: {self.gpu_successes}/{self.gpu_attempts} successful "
                    f"({gpu_success_rate:.1f}%)"
                )
        
        # Log profiling summary
        if self.profiling_data:
            total_wall = sum(p['wall_time'] for p in self.profiling_data)
            total_cpu = sum(p['cpu_time'] for p in self.profiling_data)
            total_iowait = sum(p['iowait_approx'] for p in self.profiling_data)
            avg_fps = sum(p['fps'] for p in self.profiling_data) / len(self.profiling_data) if self.profiling_data else 0
            
            # Calculate percentiles for wall time
            wall_times = sorted([p['wall_time'] for p in self.profiling_data])
            p50 = wall_times[len(wall_times) // 2] if wall_times else 0
            p95 = wall_times[int(len(wall_times) * 0.95)] if wall_times else 0
            
            self.logger.info(
                f"FFmpeg profiling for {video_name}: "
                f"total={total_wall:.1f}s (cpu={total_cpu:.1f}s, iowait≈{total_iowait:.1f}s), "
                f"avg={p50:.2f}s/scene (p95={p95:.2f}s), "
                f"avg_speed={avg_fps:.1f} fps"
            )
        
        return scene_metadata

