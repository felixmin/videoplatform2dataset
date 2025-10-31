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

