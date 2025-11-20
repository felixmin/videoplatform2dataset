"""
ABOUTME: FFmpeg-based frame extraction for faster video processing
ABOUTME: Replaces OpenCV with FFmpeg batch extraction, ~5-10x speedup
"""

import os
import logging
import subprocess
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
        self.num_workers = num_workers or min(4, cpu_count())
        self.logger = logger or logging.getLogger(__name__)
        
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
            # Try NVIDIA NVDEC (H.264 supported on most NVIDIA GPUs)
            cmd.extend(['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])
            gpu_enabled = True
        
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
            '-vf', filter_str,
            '-vsync', 'vfr',  # Variable frame rate - only output selected frames
            '-q:v', str(max(1, 31 - quality // 3)),  # Convert quality to qscale (1-31, lower=better)
            '-start_number', '0',  # Start numbering from 0
            str(output_dir / 'frame_%04d.jpg')
        ])
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minute timeout per scene
            )
            
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                # Check if it's a GPU-related error and retry with CPU
                if gpu_enabled and ('cuda' in stderr.lower() or 'hwaccel' in stderr.lower() or 'not found' in stderr.lower()):
                    self.logger.debug(f"GPU acceleration failed, retrying with CPU: {stderr[:500]}")
                    return self._extract_scene_with_ffmpeg(
                        video_path, start_frame, end_frame, output_dir,
                        resolution, quality, use_gpu=False
                    )
                
                # Log full error for debugging
                error_msg = stderr.strip()
                if len(error_msg) > 1000:
                    error_msg = error_msg[:1000] + "... (truncated)"
                self.logger.warning(
                    f"FFmpeg extraction failed for scene [{start_frame}-{end_frame}]:\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Error: {error_msg}"
                )
                return 0
            
            # Count extracted frames
            frame_files = list(output_dir.glob('frame_*.jpg'))
            return len(frame_files)
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"FFmpeg timeout extracting scene from {video_path}")
            return 0
        except Exception as e:
            self.logger.error(f"FFmpeg extraction error: {str(e)}")
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
        
        self.logger.info(
            f"Processing {len(scenes)} scenes from {video_name} "
            f"(FFmpeg, workers={self.num_workers})"
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
        
        return scene_metadata

