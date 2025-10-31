# Video Dataset Processor for Deep Learning: Production-Ready Implementation Plan

## Executive Summary

This document provides a complete implementation plan for a robust, efficient video processing pipeline designed for moderate-scale deep learning dataset creation (20-100 videos, 1-2 hours each). The system focuses on **simplicity, maintainability, and performance** using proven technologies without over-engineering for distributed computing.

---

## I. Architecture Overview

### Core Design Principles

1. **Simple but Robust**: Use mature libraries with straightforward APIs
2. **Fast I/O**: Hardware-accelerated decoding with Decord
3. **Quality First**: Automated integrity checks and corruption detection
4. **Maintainable**: Clear folder structure, comprehensive metadata tracking
5. **Scalable to Medium**: Handles 20-100 videos efficiently on a single workstation

### Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Download** | yt-dlp | Industry standard, reliable, extensive format support |
| **Parallel Execution** | Python multiprocessing | Simple, sufficient for 4-8 concurrent tasks |
| **Video I/O** | Decord (with NVDEC) | 3-5x faster than OpenCV, GPU-accelerated, random access |
| **Scene Detection** | PySceneDetect | Mature, optimized algorithms, 140-220 FPS processing |
| **Frame Extraction** | Decord → NumPy | Direct NumPy output, no BGR/RGB conversion needed |
| **Image Saving** | Pillow (PIL) | Superior quality control vs OpenCV |
| **Integrity Check** | FFmpeg subprocess | Gold standard for corruption detection |
| **Configuration** | PyYAML | Human-readable, easy to modify |
| **CLI** | argparse | Python standard library |
| **Progress** | tqdm | Visual feedback for long operations |
| **Metadata** | JSON/CSV | Simple, universally compatible |

***

## II. Project Structure

```
video_dataset_processor/
│
├── README.md                          # Complete documentation
├── requirements.txt                   # Python dependencies
├── config.yaml                        # Default configuration
├── .gitignore                        
│
├── src/                              
│   ├── __init__.py
│   ├── downloader.py                 # yt-dlp wrapper with parallel downloads
│   ├── integrity_checker.py          # FFmpeg validation + black frame detection
│   ├── video_decoder.py              # Decord-based video reading
│   ├── scene_detector.py             # PySceneDetect wrapper
│   ├── frame_processor.py            # Frame extraction and deduplication
│   ├── manifest_manager.py           # Metadata tracking (JSON/CSV)
│   └── utils.py                      # Shared utilities
│
├── scripts/                          
│   └── process_videos.py             # Main CLI entry point
│
├── data/                             
│   ├── raw/                          # Downloaded videos
│   ├── processed/                    # Output frames/clips
│   │   ├── video_001/
│   │   │   ├── scene_000/
│   │   │   │   ├── frame_0000.jpg
│   │   │   │   └── ...
│   │   │   └── scene_001/
│   │   └── video_002/
│   ├── urls.txt                      # Input URL list
│   └── manifest.json                 # Processing metadata
│
└── logs/                             
    └── processing.log
```

***

## III. Pipeline Stages (Detailed)

### Stage 1: Parallel Video Acquisition

**Module**: `downloader.py`

**Objective**: Download multiple videos concurrently with progress tracking and error handling.

**Implementation**:

```python
"""
Enhanced video downloader with parallel processing
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import yt_dlp
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

from .utils import ensure_dir, sanitize_filename


class ParallelVideoDownloader:
    """
    Download videos from URLs with parallel processing.
    """
    
    def __init__(
        self,
        download_dir: str = "data/raw",
        video_format: str = "mp4",
        video_quality: str = "best[height<=1080]",
        num_workers: int = 4,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize parallel video downloader.
        
        Args:
            download_dir: Directory to save downloaded videos
            video_format: Desired video format
            video_quality: Quality filter string
            num_workers: Number of parallel download processes
            logger: Logger instance
        """
        self.download_dir = ensure_dir(download_dir)
        self.video_format = video_format
        self.video_quality = video_quality
        self.num_workers = min(num_workers, cpu_count())
        self.logger = logger or logging.getLogger(__name__)
        
    def read_urls_from_file(self, urls_file: str) -> List[str]:
        """Read URLs from text file (one per line)."""
        urls = []
        try:
            with open(urls_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)
            self.logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
        except FileNotFoundError:
            self.logger.error(f"URLs file not found: {urls_file}")
            raise
        
        return urls
    
    def _download_single(self, url: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Download a single video.
        
        Returns:
            (success, filepath, metadata)
        """
        try:
            ydl_opts = {
                'format': self.video_quality,
                'merge_output_format': self.video_format,
                'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info
                info = ydl.extract_info(url, download=False)
                video_id = info.get('id', 'unknown')
                title = sanitize_filename(info.get('title', 'video'))
                duration = info.get('duration', 0)
                
                self.logger.info(f"Downloading: {title} ({video_id})")
                
                # Download
                ydl.download([url])
                
                # Get filename
                filename = ydl.prepare_filename(info)
                
                # Extract metadata
                metadata = {
                    'video_id': video_id,
                    'title': title,
                    'url': url,
                    'duration': duration,
                    'width': info.get('width'),
                    'height': info.get('height'),
                    'fps': info.get('fps'),
                    'filesize': info.get('filesize'),
                }
                
                if os.path.exists(filename):
                    self.logger.info(f"Downloaded: {filename}")
                    return True, filename, metadata
                else:
                    self.logger.error(f"Download completed but file not found: {filename}")
                    return False, None, None
                    
        except Exception as e:
            self.logger.error(f"Failed to download {url}: {str(e)}")
            return False, None, None
    
    def download_videos_parallel(
        self, 
        urls: List[str],
        max_downloads: Optional[int] = None
    ) -> List[Dict]:
        """
        Download multiple videos in parallel.
        
        Args:
            urls: List of video URLs
            max_downloads: Maximum number to download (None = all)
        
        Returns:
            List of metadata dicts for successful downloads
        """
        if max_downloads:
            urls = urls[:max_downloads]
        
        self.logger.info(f"Starting parallel download of {len(urls)} videos with {self.num_workers} workers")
        
        results = []
        
        # Use multiprocessing pool
        with Pool(processes=self.num_workers) as pool:
            # Map downloads with progress bar
            for success, filepath, metadata in tqdm(
                pool.imap(self._download_single, urls),
                total=len(urls),
                desc="Downloading videos",
                unit="video"
            ):
                if success and filepath and metadata:
                    metadata['filepath'] = filepath
                    results.append(metadata)
        
        self.logger.info(
            f"Download complete: {len(results)}/{len(urls)} videos successful"
        )
        
        return results
```

**Key Features**:
- Parallel downloads using `multiprocessing.Pool` (4-8 workers typical)
- Automatic metadata extraction (video ID, title, duration, resolution, FPS)
- Progress tracking with tqdm
- Comprehensive error handling per video
- Returns structured metadata for manifest

***

### Stage 2: Video Integrity Validation

**Module**: `integrity_checker.py`

**Objective**: Detect corrupted videos and blank/black frames before processing.

**Implementation**:

```python
"""
Video integrity checking using FFmpeg and frame analysis
"""

import subprocess
import logging
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

from .video_decoder import VideoDecoder


class IntegrityChecker:
    """
    Check video file integrity and detect problematic content.
    """
    
    def __init__(
        self,
        black_threshold: int = 20,
        max_black_ratio: float = 0.5,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize integrity checker.
        
        Args:
            black_threshold: Pixel intensity threshold for black frames (0-255)
            max_black_ratio: Maximum ratio of black frames before flagging video
            logger: Logger instance
        """
        self.black_threshold = black_threshold
        self.max_black_ratio = max_black_ratio
        self.logger = logger or logging.getLogger(__name__)
    
    def check_ffmpeg_integrity(self, video_path: str) -> Tuple[bool, str]:
        """
        Check video integrity using FFmpeg decode-to-null test.
        
        Args:
            video_path: Path to video file
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Run FFmpeg to decode entire video to null output
            cmd = [
                'ffmpeg',
                '-v', 'error',           # Only show errors
                '-i', video_path,         # Input file
                '-f', 'null',             # Output to null
                '-'                       # Stdout
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minute timeout
            )
            
            # Check return code
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                self.logger.warning(f"FFmpeg integrity check failed for {video_path}: {error_msg[:200]}")
                return False, error_msg
            
            # Check stderr for critical errors
            stderr = result.stderr.decode('utf-8', errors='ignore')
            critical_errors = ['corrupt', 'invalid', 'error', 'failed']
            
            if any(err in stderr.lower() for err in critical_errors):
                self.logger.warning(f"FFmpeg detected issues in {video_path}: {stderr[:200]}")
                return False, stderr
            
            self.logger.info(f"FFmpeg integrity check passed: {video_path}")
            return True, ""
            
        except subprocess.TimeoutExpired:
            error_msg = "FFmpeg integrity check timeout"
            self.logger.error(f"{error_msg}: {video_path}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"FFmpeg integrity check exception: {str(e)}"
            self.logger.error(f"{error_msg}: {video_path}")
            return False, error_msg
    
    def detect_black_frames(
        self, 
        video_path: str,
        sample_rate: int = 30
    ) -> Tuple[float, int, int]:
        """
        Detect ratio of black/blank frames in video.
        
        Args:
            video_path: Path to video file
            sample_rate: Check every Nth frame (faster sampling)
        
        Returns:
            (black_ratio, num_black, total_sampled)
        """
        try:
            decoder = VideoDecoder(video_path)
            total_frames = len(decoder)
            
            # Sample frames
            sample_indices = range(0, total_frames, sample_rate)
            
            black_count = 0
            
            for idx in sample_indices:
                frame = decoder[idx]
                
                # Convert to grayscale
                if len(frame.shape) == 3:
                    # RGB to grayscale: 0.299*R + 0.587*G + 0.114*B
                    gray = np.dot(frame[...,:3], [0.299, 0.587, 0.114])
                else:
                    gray = frame
                
                # Check average pixel intensity
                avg_intensity = np.mean(gray)
                
                if avg_intensity < self.black_threshold:
                    black_count += 1
            
            total_sampled = len(list(sample_indices))
            black_ratio = black_count / total_sampled if total_sampled > 0 else 0.0
            
            self.logger.debug(
                f"Black frame detection: {black_count}/{total_sampled} "
                f"({black_ratio:.1%}) - {video_path}"
            )
            
            return black_ratio, black_count, total_sampled
            
        except Exception as e:
            self.logger.error(f"Black frame detection failed for {video_path}: {str(e)}")
            return 0.0, 0, 0
    
    def validate_video(
        self, 
        video_path: str,
        check_black_frames: bool = True
    ) -> Dict[str, any]:
        """
        Complete validation check for video.
        
        Args:
            video_path: Path to video file
            check_black_frames: Whether to run black frame detection
        
        Returns:
            Dictionary with validation results
        """
        self.logger.info(f"Validating: {video_path}")
        
        results = {
            'video_path': video_path,
            'ffmpeg_valid': False,
            'ffmpeg_error': '',
            'black_ratio': 0.0,
            'black_frames': 0,
            'sampled_frames': 0,
            'is_valid': False
        }
        
        # FFmpeg integrity check
        ffmpeg_valid, ffmpeg_error = self.check_ffmpeg_integrity(video_path)
        results['ffmpeg_valid'] = ffmpeg_valid
        results['ffmpeg_error'] = ffmpeg_error
        
        if not ffmpeg_valid:
            self.logger.warning(f"Video failed FFmpeg check: {video_path}")
            return results
        
        # Black frame detection
        if check_black_frames:
            black_ratio, black_count, sampled = self.detect_black_frames(video_path)
            results['black_ratio'] = black_ratio
            results['black_frames'] = black_count
            results['sampled_frames'] = sampled
            
            if black_ratio > self.max_black_ratio:
                self.logger.warning(
                    f"Video has {black_ratio:.1%} black frames (threshold: {self.max_black_ratio:.1%}): {video_path}"
                )
                return results
        
        # All checks passed
        results['is_valid'] = True
        self.logger.info(f"Video validation passed: {video_path}")
        return results
```

**Key Features**:
- FFmpeg decode-to-null test (gold standard)
- Black/blank frame detection with configurable threshold
- Sampling for faster validation (check every Nth frame)
- Detailed error reporting
- Returns structured validation results

***

### Stage 3: High-Performance Video Decoding

**Module**: `video_decoder.py`

**Objective**: Fast, random-access video reading using Decord with GPU acceleration.

**Implementation**:

```python
"""
High-performance video decoder using Decord
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
import decord
from decord import VideoReader, cpu, gpu


decord.bridge.set_bridge('numpy')  # Use NumPy as output format


class VideoDecoder:
    """
    Fast video decoder using Decord with optional GPU acceleration.
    """
    
    def __init__(
        self,
        video_path: str,
        use_gpu: bool = True,
        gpu_id: int = 0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize video decoder.
        
        Args:
            video_path: Path to video file
            use_gpu: Use GPU acceleration if available
            gpu_id: GPU device ID
            logger: Logger instance
        """
        self.video_path = Path(video_path)
        self.logger = logger or logging.getLogger(__name__)
        
        # Set device context
        if use_gpu:
            try:
                ctx = gpu(gpu_id)
                self.logger.debug(f"Using GPU {gpu_id} for decoding")
            except:
                ctx = cpu(0)
                self.logger.warning(f"GPU not available, falling back to CPU")
        else:
            ctx = cpu(0)
        
        # Open video
        try:
            self.reader = VideoReader(str(video_path), ctx=ctx)
            self.logger.debug(f"Opened video: {video_path}")
        except Exception as e:
            self.logger.error(f"Failed to open video {video_path}: {str(e)}")
            raise
    
    @property
    def fps(self) -> float:
        """Get video FPS."""
        return self.reader.get_avg_fps()
    
    @property
    def num_frames(self) -> int:
        """Get total number of frames."""
        return len(self.reader)
    
    @property
    def duration(self) -> float:
        """Get video duration in seconds."""
        return self.num_frames / self.fps if self.fps > 0 else 0.0
    
    @property
    def resolution(self) -> Tuple[int, int]:
        """Get video resolution (width, height)."""
        # Get first frame to determine resolution
        frame = self.reader[0]
        height, width = frame.shape[:2]
        return (width, height)
    
    def __len__(self) -> int:
        """Total number of frames."""
        return self.num_frames
    
    def __getitem__(self, index: int) -> np.ndarray:
        """
        Get frame at specific index.
        
        Args:
            index: Frame index
        
        Returns:
            Frame as numpy array (H, W, C) in RGB format
        """
        return self.reader[index].asnumpy()
    
    def get_batch(self, indices: List[int]) -> np.ndarray:
        """
        Get multiple frames efficiently.
        
        Args:
            indices: List of frame indices
        
        Returns:
            Batch of frames as numpy array (N, H, W, C) in RGB format
        """
        return self.reader.get_batch(indices).asnumpy()
    
    def get_frame_range(self, start: int, end: int) -> np.ndarray:
        """
        Get consecutive range of frames.
        
        Args:
            start: Start frame index
            end: End frame index (exclusive)
        
        Returns:
            Frames as numpy array (N, H, W, C) in RGB format
        """
        indices = list(range(start, end))
        return self.get_batch(indices)
    
    def seek(self, frame_idx: int):
        """Seek to specific frame index."""
        self.reader.seek(frame_idx)
```

**Key Features**:
- Decord-based with automatic GPU detection
- Direct NumPy output (RGB format, no conversion needed)
- Fast random access (`decoder[index]`)
- Efficient batch reading (`get_batch()`)
- Properties for metadata (FPS, resolution, duration)

***

### Stage 4: Scene Detection

**Module**: `scene_detector.py`

**Objective**: Detect scene boundaries using PySceneDetect with optimized settings.

**Implementation** (same as before, already well-designed):

```python
"""
Scene detection module using PySceneDetect
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional
from scenedetect import detect, ContentDetector, AdaptiveDetector, ThresholdDetector
from scenedetect import open_video, SceneManager


class SceneDetector:
    """
    Detect scene changes in videos using PySceneDetect.
    """
    
    def __init__(
        self,
        detector_type: str = "adaptive",
        threshold: float = 3.0,  # For adaptive
        min_scene_length: int = 15,
        downscale_factor: int = 2,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize scene detector.
        
        Args:
            detector_type: "content", "adaptive", or "threshold"
            threshold: Detection threshold
            min_scene_length: Minimum scene length in frames
            downscale_factor: Downscale for faster processing
            logger: Logger instance
        """
        self.detector_type = detector_type.lower()
        self.threshold = threshold
        self.min_scene_length = min_scene_length
        self.downscale_factor = downscale_factor
        self.logger = logger or logging.getLogger(__name__)
        
        valid_detectors = ["content", "adaptive", "threshold"]
        if self.detector_type not in valid_detectors:
            raise ValueError(f"Invalid detector_type: {detector_type}")
    
    def _create_detector(self):
        """Create detector instance."""
        if self.detector_type == "content":
            return ContentDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_length
            )
        elif self.detector_type == "adaptive":
            return AdaptiveDetector(
                adaptive_threshold=self.threshold,
                min_scene_len=self.min_scene_length
            )
        elif self.detector_type == "threshold":
            return ThresholdDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_length
            )
    
    def detect_scenes(
        self, 
        video_path: str,
        show_progress: bool = True
    ) -> List[Tuple[int, int]]:
        """
        Detect scenes in video.
        
        Args:
            video_path: Path to video file
            show_progress: Show progress bar
        
        Returns:
            List of (start_frame, end_frame) tuples
        """
        try:
            self.logger.info(
                f"Detecting scenes: {Path(video_path).name} "
                f"(detector={self.detector_type}, threshold={self.threshold})"
            )
            
            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(self._create_detector())
            
            # Detect with downscaling
            scene_manager.detect_scenes(
                video=video,
                show_progress=show_progress,
                downscale=self.downscale_factor
            )
            
            # Convert to frame numbers
            scenes = []
            for scene in scene_manager.get_scene_list():
                start_frame = scene[0].get_frames()
                end_frame = scene[1].get_frames()
                scenes.append((start_frame, end_frame))
            
            self.logger.info(f"Detected {len(scenes)} scenes in {Path(video_path).name}")
            
            return scenes
            
        except Exception as e:
            self.logger.error(f"Scene detection failed for {video_path}: {str(e)}")
            raise
```

***

### Stage 5: Frame Processing & Optional Deduplication

**Module**: `frame_processor.py`

**Objective**: Extract frames from scenes with optional entropy-based deduplication.

**Implementation**:

```python
"""
Frame extraction and optional deduplication
"""

import os
import logging
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from PIL import Image
from tqdm import tqdm
from scipy.stats import entropy

from .video_decoder import VideoDecoder
from .utils import ensure_dir


class FrameProcessor:
    """
    Extract and process frames from video scenes.
    """
    
    def __init__(
        self,
        output_dir: str = "data/processed",
        output_resolution: Optional[Tuple[int, int]] = None,
        jpeg_quality: int = 85,
        enable_deduplication: bool = False,
        entropy_percentile: float = 50.0,  # Keep frames above this percentile
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize frame processor.
        
        Args:
            output_dir: Output directory
            output_resolution: Target (width, height) or None
            jpeg_quality: JPEG quality (1-100)
            enable_deduplication: Enable entropy-based deduplication
            entropy_percentile: Percentile threshold for frame selection
            logger: Logger instance
        """
        self.output_dir = ensure_dir(output_dir)
        self.output_resolution = output_resolution
        self.jpeg_quality = jpeg_quality
        self.enable_deduplication = enable_deduplication
        self.entropy_percentile = entropy_percentile
        self.logger = logger or logging.getLogger(__name__)
    
    def _calculate_frame_entropy(self, frame: np.ndarray) -> float:
        """
        Calculate entropy of frame (information content).
        
        Args:
            frame: Frame as numpy array (H, W, C)
        
        Returns:
            Entropy value
        """
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = np.dot(frame[...,:3], [0.299, 0.587, 0.114])
        else:
            gray = frame
        
        # Calculate histogram
        hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
        
        # Normalize
        hist = hist / hist.sum()
        
        # Calculate entropy
        return entropy(hist + 1e-10)  # Add small value to avoid log(0)
    
    def _select_keyframes(
        self,
        decoder: VideoDecoder,
        start_frame: int,
        end_frame: int
    ) -> List[int]:
        """
        Select keyframes based on entropy.
        
        Args:
            decoder: VideoDecoder instance
            start_frame: Scene start frame
            end_frame: Scene end frame
        
        Returns:
            List of selected frame indices
        """
        frame_indices = list(range(start_frame, end_frame))
        
        if not self.enable_deduplication or len(frame_indices) < 10:
            return frame_indices
        
        # Calculate entropy for all frames
        entropies = []
        for idx in frame_indices:
            frame = decoder[idx]
            ent = self._calculate_frame_entropy(frame)
            entropies.append(ent)
        
        # Select frames above percentile threshold
        threshold = np.percentile(entropies, self.entropy_percentile)
        selected = [
            frame_indices[i] 
            for i, ent in enumerate(entropies) 
            if ent >= threshold
        ]
        
        self.logger.debug(
            f"Entropy deduplication: {len(selected)}/{len(frame_indices)} frames selected "
            f"(threshold={threshold:.2f})"
        )
        
        return selected
    
    def process_scene(
        self,
        decoder: VideoDecoder,
        scene: Tuple[int, int],
        scene_idx: int,
        video_name: str,
        flat_structure: bool = False
    ) -> Dict:
        """
        Extract frames from a scene.
        
        Args:
            decoder: VideoDecoder instance
            scene: (start_frame, end_frame)
            scene_idx: Scene index
            video_name: Video name for folder
            flat_structure: Use flat folder structure
        
        Returns:
            Scene processing metadata
        """
        start_frame, end_frame = scene
        
        # Determine output directory
        if flat_structure:
            scene_dir = self.output_dir / "scenes" / f"{video_name}_scene_{scene_idx:03d}"
        else:
            scene_dir = self.output_dir / video_name / f"scene_{scene_idx:03d}"
        
        ensure_dir(scene_dir)
        
        # Select frames
        if self.enable_deduplication:
            selected_indices = self._select_keyframes(decoder, start_frame, end_frame)
        else:
            selected_indices = list(range(start_frame, end_frame))
        
        # Extract and save frames
        saved_count = 0
        
        for local_idx, frame_idx in enumerate(selected_indices):
            # Get frame
            frame = decoder[frame_idx]  # Already RGB from Decord
            
            # Create PIL Image
            pil_img = Image.fromarray(frame)
            
            # Resize if needed
            if self.output_resolution is not None:
                pil_img = pil_img.resize(self.output_resolution, Image.LANCZOS)
            
            # Save
            output_path = scene_dir / f"frame_{local_idx:04d}.jpg"
            pil_img.save(
                str(output_path),
                'JPEG',
                quality=self.jpeg_quality,
                optimize=True,
                subsampling=0  # Best quality
            )
            
            saved_count += 1
        
        metadata = {
            'scene_idx': scene_idx,
            'start_frame': start_frame,
            'end_frame': end_frame,
            'total_frames': end_frame - start_frame,
            'selected_frames': len(selected_indices),
            'saved_frames': saved_count,
            'output_dir': str(scene_dir),
            'deduplication_enabled': self.enable_deduplication
        }
        
        self.logger.debug(
            f"Processed scene {scene_idx}: {saved_count} frames saved to {scene_dir}"
        )
        
        return metadata
    
    def process_video(
        self,
        video_path: str,
        scenes: List[Tuple[int, int]],
        flat_structure: bool = False,
        use_gpu: bool = True
    ) -> List[Dict]:
        """
        Process all scenes in a video.
        
        Args:
            video_path: Path to video file
            scenes: List of (start_frame, end_frame) tuples
            flat_structure: Use flat folder structure
            use_gpu: Use GPU for decoding
        
        Returns:
            List of scene metadata dicts
        """
        video_name = Path(video_path).stem
        
        self.logger.info(
            f"Processing {len(scenes)} scenes from {video_name} "
            f"(deduplication={self.enable_deduplication})"
        )
        
        # Open video with Decord
        decoder = VideoDecoder(video_path, use_gpu=use_gpu, logger=self.logger)
        
        scene_metadata = []
        
        for scene_idx, scene in enumerate(tqdm(
            scenes, 
            desc=f"Processing {video_name}", 
            unit="scene"
        )):
            metadata = self.process_scene(
                decoder,
                scene,
                scene_idx,
                video_name,
                flat_structure
            )
            scene_metadata.append(metadata)
        
        total_frames = sum(m['saved_frames'] for m in scene_metadata)
        self.logger.info(f"Processed {video_name}: {total_frames} frames extracted")
        
        return scene_metadata
```

**Key Features**:
- Decord for fast frame extraction (already RGB)
- Optional entropy-based deduplication
- Pillow for high-quality JPEG saving
- Flexible folder structure (flat or hierarchical)
- Comprehensive metadata tracking

***

### Stage 6: Manifest Management

**Module**: `manifest_manager.py`

**Objective**: Track all processing metadata in JSON format.

**Implementation**:

```python
"""
Manifest file management for tracking processing metadata
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class ManifestManager:
    """
    Manage processing manifest (metadata tracking).
    """
    
    def __init__(
        self,
        manifest_path: str = "data/manifest.json",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize manifest manager.
        
        Args:
            manifest_path: Path to manifest JSON file
            logger: Logger instance
        """
        self.manifest_path = Path(manifest_path)
        self.logger = logger or logging.getLogger(__name__)
        
        # Ensure directory exists
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing manifest or create new
        if self.manifest_path.exists():
            self.manifest = self._load()
        else:
            self.manifest = {
                'created_at': datetime.now().isoformat(),
                'version': '1.0',
                'videos': []
            }
    
    def _load(self) -> Dict:
        """Load manifest from file."""
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
            self.logger.info(f"Loaded manifest with {len(manifest.get('videos', []))} videos")
            return manifest
        except Exception as e:
            self.logger.error(f"Failed to load manifest: {str(e)}")
            return {
                'created_at': datetime.now().isoformat(),
                'version': '1.0',
                'videos': []
            }
    
    def save(self):
        """Save manifest to file."""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=2)
            self.logger.info(f"Saved manifest to {self.manifest_path}")
        except Exception as e:
            self.logger.error(f"Failed to save manifest: {str(e)}")
    
    def add_video(
        self,
        video_id: str,
        metadata: Dict,
        validation: Dict,
        scenes: List[Dict]
    ):
        """
        Add video processing record to manifest.
        
        Args:
            video_id: Unique video identifier
            metadata: Video metadata from download
            validation: Validation results
            scenes: List of scene metadata
        """
        record = {
            'video_id': video_id,
            'processed_at': datetime.now().isoformat(),
            'source': metadata,
            'validation': validation,
            'scenes': scenes,
            'stats': {
                'num_scenes': len(scenes),
                'total_frames': sum(s.get('saved_frames', 0) for s in scenes)
            }
        }
        
        self.manifest['videos'].append(record)
        self.logger.debug(f"Added video to manifest: {video_id}")
    
    def get_processed_video_ids(self) -> List[str]:
        """Get list of already processed video IDs."""
        return [v['video_id'] for v in self.manifest.get('videos', [])]
    
    def is_processed(self, video_id: str) -> bool:
        """Check if video already processed."""
        return video_id in self.get_processed_video_ids()
```

***

### Stage 7: Main Orchestrator

**Module**: `scripts/process_videos.py`

**Implementation**:

```python
#!/usr/bin/env python3
"""
Main video processing pipeline orchestrator
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.downloader import ParallelVideoDownloader
from src.integrity_checker import IntegrityChecker
from src.scene_detector import SceneDetector
from src.frame_processor import FrameProcessor
from src.manifest_manager import ManifestManager
from src.utils import setup_logging, load_config, format_time


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Video dataset processor for deep learning",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('-c', '--config', type=str, default='config.yaml',
                       help='Configuration file path')
    parser.add_argument('-u', '--urls-file', type=str,
                       help='URLs file (overrides config)')
    parser.add_argument('--num-workers', type=int,
                       help='Number of parallel download workers')
    parser.add_argument('--no-scene-detection', action='store_true',
                       help='Disable scene detection (treat video as single scene)')
    parser.add_argument('--enable-deduplication', action='store_true',
                       help='Enable entropy-based frame deduplication')
    parser.add_argument('--resolution', type=str,
                       help='Output resolution WIDTHxHEIGHT (e.g., 640x480)')
    parser.add_argument('--jpeg-quality', type=int,
                       help='JPEG quality 1-100')
    parser.add_argument('--use-cpu', action='store_true',
                       help='Disable GPU acceleration')
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip integrity validation (not recommended)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose logging')
    
    return parser.parse_args()


def main():
    """Main pipeline execution."""
    args = parse_arguments()
    
    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)
    
    # Override config with CLI args
    if args.urls_file:
        config['urls_file'] = args.urls_file
    if args.num_workers:
        config['num_workers'] = args.num_workers
    if args.no_scene_detection:
        config['detect_scenes'] = False
    if args.enable_deduplication:
        config['enable_deduplication'] = True
    if args.resolution:
        w, h = map(int, args.resolution.split('x'))
        config['output_resolution'] = [w, h]
    if args.jpeg_quality:
        config['jpeg_quality'] = args.jpeg_quality
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else config.get('log_level', 'INFO')
    logger = setup_logging(config.get('log_file'), log_level)
    
    logger.info("=" * 60)
    logger.info("VIDEO DATASET PROCESSOR")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Initialize components
    downloader = ParallelVideoDownloader(
        download_dir=config['download_dir'],
        video_quality=config['video_quality'],
        num_workers=config.get('num_workers', 4),
        logger=logger
    )
    
    validator = IntegrityChecker(
        black_threshold=config.get('black_threshold', 20),
        max_black_ratio=config.get('max_black_ratio', 0.5),
        logger=logger
    )
    
    scene_detector = SceneDetector(
        detector_type=config.get('scene_detector', 'adaptive'),
        threshold=config.get('scene_threshold', 3.0),
        min_scene_length=config.get('min_scene_length', 15),
        downscale_factor=config.get('downscale_factor', 2),
        logger=logger
    ) if config.get('detect_scenes', True) else None
    
    frame_processor = FrameProcessor(
        output_dir=config['output_dir'],
        output_resolution=tuple(config['output_resolution']) if config.get('output_resolution') else None,
        jpeg_quality=config.get('jpeg_quality', 85),
        enable_deduplication=config.get('enable_deduplication', False),
        entropy_percentile=config.get('entropy_percentile', 50.0),
        logger=logger
    )
    
    manifest = ManifestManager(
        manifest_path=config.get('manifest_path', 'data/manifest.json'),
        logger=logger
    )
    
    # Stage 1: Download
    logger.info("=" * 60)
    logger.info("STAGE 1: DOWNLOADING VIDEOS")
    logger.info("=" * 60)
    
    urls = downloader.read_urls_from_file(
        args.urls_file or config['urls_file']
    )
    
    downloaded = downloader.download_videos_parallel(
        urls,
        max_downloads=config.get('max_downloads')
    )
    
    logger.info(f"Downloaded {len(downloaded)} videos")
    
    # Process each video
    stats = {
        'downloaded': len(downloaded),
        'validated': 0,
        'processed': 0,
        'total_scenes': 0,
        'total_frames': 0,
        'failed': 0
    }
    
    for video_meta in downloaded:
        video_path = video_meta['filepath']
        video_id = video_meta['video_id']
        
        try:
            # Check if already processed
            if manifest.is_processed(video_id):
                logger.info(f"Skipping already processed: {video_id}")
                continue
            
            # Stage 2: Validate
            if not args.skip_validation:
                logger.info(f"Validating: {video_id}")
                validation = validator.validate_video(video_path)
                
                if not validation['is_valid']:
                    logger.warning(f"Video failed validation: {video_id}")
                    manifest.add_video(video_id, video_meta, validation, [])
                    stats['failed'] += 1
                    continue
                
                stats['validated'] += 1
            else:
                validation = {'is_valid': True, 'skipped': True}
            
            # Stage 3: Scene Detection
            if scene_detector:
                logger.info(f"Detecting scenes: {video_id}")
                scenes = scene_detector.detect_scenes(video_path, show_progress=False)
            else:
                # Treat entire video as one scene
                from src.video_decoder import VideoDecoder
                decoder = VideoDecoder(video_path, use_gpu=not args.use_cpu)
                scenes = [(0, decoder.num_frames)]
            
            stats['total_scenes'] += len(scenes)
            
            # Stage 4: Frame Extraction
            logger.info(f"Extracting frames: {video_id}")
            scene_metadata = frame_processor.process_video(
                video_path,
                scenes,
                flat_structure=config.get('flat_structure', False),
                use_gpu=not args.use_cpu
            )
            
            frames_extracted = sum(s['saved_frames'] for s in scene_metadata)
            stats['total_frames'] += frames_extracted
            stats['processed'] += 1
            
            # Update manifest
            manifest.add_video(video_id, video_meta, validation, scene_metadata)
            manifest.save()
            
        except Exception as e:
            logger.error(f"Failed to process {video_id}: {str(e)}", exc_info=True)
            stats['failed'] += 1
    
    # Summary
    elapsed = time.time() - start_time
    
    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Videos downloaded:  {stats['downloaded']}")
    logger.info(f"Videos validated:   {stats['validated']}")
    logger.info(f"Videos processed:   {stats['processed']}")
    logger.info(f"Total scenes:       {stats['total_scenes']}")
    logger.info(f"Total frames:       {stats['total_frames']}")
    logger.info(f"Failed:             {stats['failed']}")
    logger.info(f"Total time:         {format_time(elapsed)}")
    logger.info("=" * 60)
    
    sys.exit(0 if stats['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
```

***

## IV. Configuration File

**config.yaml**:

```yaml
# Video Dataset Processor Configuration

# Input/Output
urls_file: "data/urls.txt"
download_dir: "data/raw"
output_dir: "data/processed"
manifest_path: "data/manifest.json"

# Download Settings
video_quality: "best[height<=1080]"
max_downloads: null  # null = all videos
num_workers: 4  # Parallel download workers

# Validation Settings
black_threshold: 20  # Pixel intensity threshold for black frames
max_black_ratio: 0.5  # Max ratio of black frames before flagging

# Scene Detection Settings
detect_scenes: true
scene_detector: "adaptive"  # "content", "adaptive", or "threshold"
scene_threshold: 3.0  # For adaptive detector
min_scene_length: 15  # Minimum frames per scene
downscale_factor: 2  # Downscale for faster detection

# Frame Extraction Settings
output_resolution: [640, 480]  # [width, height] or null for original
jpeg_quality: 85  # 1-100
enable_deduplication: false  # Entropy-based frame selection
entropy_percentile: 50.0  # Keep frames above this percentile

# Folder Structure
flat_structure: false  # true = all scenes in one folder

# Performance
use_gpu: true  # Enable GPU acceleration (Decord, NVDEC)

# Logging
log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
log_file: "logs/processing.log"
```

***

## V. Dependencies

**requirements.txt**:

```
# Core video processing
yt-dlp>=2024.8.0
decord>=0.6.0
scenedetect[opencv]>=0.6.2

# Image processing
opencv-python>=4.8.0
Pillow>=10.0.0
numpy>=1.24.0

# Scientific computing
scipy>=1.10.0

# Configuration and CLI
PyYAML>=6.0
tqdm>=4.65.0

# Optional: GPU acceleration
# pynvcodec  # Uncomment if using NVIDIA GPUs
```

***

## VI. Usage Examples

### Basic Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Create URLs file
cat > data/urls.txt << EOF
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
https://www.youtube.com/watch?v=VIDEO_ID_3
EOF

# Run with default config
python scripts/process_videos.py

# Run with custom config
python scripts/process_videos.py -c my_config.yaml
```

### Advanced Usage

```bash
# Use 8 parallel download workers
python scripts/process_videos.py --num-workers 8

# Disable scene detection (treat each video as single scene)
python scripts/process_videos.py --no-scene-detection

# Enable entropy-based deduplication
python scripts/process_videos.py --enable-deduplication

# Custom resolution
python scripts/process_videos.py --resolution 320x240

# Disable GPU (use CPU only)
python scripts/process_videos.py --use-cpu

# Verbose logging
python scripts/process_videos.py -v

# Combined options
python scripts/process_videos.py \
    --num-workers 8 \
    --enable-deduplication \
    --resolution 640x480 \
    --jpeg-quality 90 \
    -v
```

***

## VII. Performance Expectations

For **20 videos × 1.5 hours** (30 hours total):

| Stage | Time Estimate | Notes |
|-------|--------------|-------|
| **Download** (4 workers) | 2-6 hours | Depends on bandwidth |
| **Validation** (FFmpeg) | 30-60 minutes | Fast integrity checks |
| **Scene Detection** (2x downscale) | 15-30 minutes | PySceneDetect @ 140-220 FPS |
| **Frame Extraction** (GPU) | 1-2 hours | Decord @ 200-400 FPS |
| **Total** | **4-10 hours** | Single workstation |

**Hardware Recommendations**:
- CPU: 6-8 cores (for parallel downloads)
- RAM: 16GB+
- GPU: NVIDIA with NVDEC (GTX 1060+) for 3-5x speedup
- Storage: SSD recommended (500GB+ for raw + processed)

***

## VIII. Troubleshooting

### Common Issues

**1. Decord import fails**
```bash
# Install from conda-forge (recommended)
conda install -c conda-forge decord

# Or build from source
pip install --no-binary decord decord
```

**2. GPU not detected**
```python
# Check Decord GPU support
import decord
print(decord.gpu(0))  # Should not raise exception
```

**3. FFmpeg not found**
```bash
# Install FFmpeg
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**4. Out of memory during processing**
- Reduce `num_workers` in config
- Lower `output_resolution`
- Enable `enable_deduplication` to reduce frame count
- Process videos in smaller batches

***

## IX. Next Steps & Extensions

### Phase 1 (Current): Core Pipeline
- ✅ Parallel downloads
- ✅ Integrity validation
- ✅ Scene detection
- ✅ Frame extraction
- ✅ Basic manifest

### Phase 2 (Future): Quality Improvements
- Advanced deduplication (SSIM-based)
- Motion-based keyframe selection
- Automatic quality scoring
- Dataset statistics and visualization

### Phase 3 (Future): Scale-Up
- Resume capability (read manifest to skip processed)
- Multi-machine processing (simple job splitting)
- Cloud storage integration (S3/GCS)
- Web dashboard for monitoring

---

This implementation plan provides a **production-ready, maintainable pipeline** optimized for your scale (20-100 videos) with clear paths for future expansion. All model context files are ready to guide your implementation agents!