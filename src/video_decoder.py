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

