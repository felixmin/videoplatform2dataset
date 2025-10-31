"""
High-performance video decoder using OpenCV
"""

import logging
import numpy as np
import cv2
import os
import sys
from pathlib import Path
from typing import Optional, Tuple, List
from contextlib import contextmanager

# Set OpenCV to only show errors (suppresses warnings including h264)
# Try multiple methods for different OpenCV versions
try:
    # OpenCV 4.x
    if hasattr(cv2, 'utils') and hasattr(cv2.utils, 'setLogLevel'):
        cv2.utils.setLogLevel(cv2.utils.LOG_LEVEL_ERROR)
    elif hasattr(cv2, 'setLogLevel'):
        # Some versions use direct setLogLevel
        cv2.setLogLevel(1)  # ERROR level
except (AttributeError, TypeError):
    # Fallback: warnings will be filtered by FilteredStderr
    pass


class FilteredStderr:
    """Filter stderr to suppress h264 warnings."""
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        
    def write(self, message):
        # Filter out h264 mmco warnings (keep other messages)
        msg_lower = message.lower()
        if 'h264' in msg_lower and 'mmco: unref short failure' in msg_lower:
            return  # Suppress this message
        self.original_stderr.write(message)
    
    def flush(self):
        self.original_stderr.flush()
    
    def __getattr__(self, name):
        return getattr(self.original_stderr, name)


@contextmanager
def suppress_stderr():
    """Context manager to suppress stderr (for OpenCV h264 warnings)."""
    # Use filtered stderr instead of devnull to allow other important messages
    old_stderr = sys.stderr
    try:
        sys.stderr = FilteredStderr(old_stderr)
        yield
    finally:
        sys.stderr = old_stderr


class VideoDecoder:
    """
    Video decoder using OpenCV (cv2) with the same API as Decord-based decoder.
    """
    
    def __init__(
        self,
        video_path: str,
        use_gpu: bool = True,  # Kept for API compatibility, but OpenCV will use CPU
        gpu_id: int = 0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize video decoder.
        
        Args:
            video_path: Path to video file
            use_gpu: Kept for API compatibility (OpenCV VideoCapture uses CPU by default)
            gpu_id: Kept for API compatibility
            logger: Logger instance
        """
        self.video_path = Path(video_path)
        self.logger = logger or logging.getLogger(__name__)
        
        # Open video with OpenCV (suppress warnings during init)
        try:
            with suppress_stderr():
                self.cap = cv2.VideoCapture(str(video_path))
                
                if not self.cap.isOpened():
                    raise IOError(f"Cannot open video file: {video_path}")
                
                # Cache video properties
                self._fps = self.cap.get(cv2.CAP_PROP_FPS)
                self._num_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self._width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self._height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # If frame count is unreliable, we'll need to count manually
            if self._num_frames <= 0:
                self.logger.warning(f"Frame count unreliable for {video_path}, will count manually if needed")
            
            self.logger.debug(f"Opened video: {video_path} ({self._width}x{self._height}, {self._fps} fps, {self._num_frames} frames)")
            
        except Exception as e:
            self.logger.error(f"Failed to open video {video_path}: {str(e)}")
            if hasattr(self, 'cap'):
                self.cap.release()
            raise
    
    @property
    def fps(self) -> float:
        """Get video FPS."""
        return self._fps if self._fps > 0 else 30.0  # Default to 30 if unknown
    
    @property
    def num_frames(self) -> int:
        """Get total number of frames."""
        if self._num_frames > 0:
            return self._num_frames
        # Fallback: count frames if property is unreliable
        return self._count_frames()
    
    def _count_frames(self) -> int:
        """Count total frames by reading through video."""
        with suppress_stderr():
            current_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            count = 0
            while True:
                ret = self.cap.read()[0]
                if not ret:
                    break
                count += 1
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
        self._num_frames = count
        return count
    
    @property
    def duration(self) -> float:
        """Get video duration in seconds."""
        return self.num_frames / self.fps if self.fps > 0 else 0.0
    
    @property
    def resolution(self) -> Tuple[int, int]:
        """Get video resolution (width, height)."""
        return (self._width, self._height)
    
    def __len__(self) -> int:
        """Total number of frames."""
        return self.num_frames
    
    def _read_frame_at(self, index: int) -> np.ndarray:
        """
        Read frame at specific index and convert to RGB.
        
        Args:
            index: Frame index
        
        Returns:
            Frame as numpy array (H, W, C) in RGB format
        """
        # Suppress OpenCV stderr warnings (h264 messages)
        with suppress_stderr():
            # Seek to frame
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ret, frame = self.cap.read()
        
        if not ret:
            raise IndexError(f"Cannot read frame {index} from video")
        
        # Convert BGR to RGB (OpenCV uses BGR, we want RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame_rgb
    
    def __getitem__(self, index: int) -> np.ndarray:
        """
        Get frame at specific index.
        
        Args:
            index: Frame index
        
        Returns:
            Frame as numpy array (H, W, C) in RGB format
        """
        if index < 0 or index >= self.num_frames:
            raise IndexError(f"Frame index {index} out of range [0, {self.num_frames})")
        
        return self._read_frame_at(index)
    
    def get_batch(self, indices: List[int]) -> np.ndarray:
        """
        Get multiple frames efficiently.
        
        Args:
            indices: List of frame indices (can be unsorted)
        
        Returns:
            Batch of frames as numpy array (N, H, W, C) in RGB format
        """
        if not indices:
            return np.array([])
        
        # Sort indices for more efficient sequential reading
        sorted_indices = sorted(set(indices))
        frames = []
        
        for idx in sorted_indices:
            frame = self._read_frame_at(idx)
            frames.append(frame)
        
        # Reorder to match original index order (handle duplicates)
        result = []
        frame_dict = {idx: frame for idx, frame in zip(sorted_indices, frames)}
        for idx in indices:
            result.append(frame_dict[idx])
        
        return np.array(result)
    
    def get_frame_range(self, start: int, end: int) -> np.ndarray:
        """
        Get consecutive range of frames (more efficient than get_batch for sequential access).
        
        Args:
            start: Start frame index
            end: End frame index (exclusive)
        
        Returns:
            Frames as numpy array (N, H, W, C) in RGB format
        """
        if start >= end:
            return np.array([])
        
        # Suppress OpenCV stderr warnings (h264 messages) during frame reading
        with suppress_stderr():
            # Seek to start
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            
            frames = []
            for _ in range(end - start):
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
        
        return np.array(frames)
    
    def seek(self, frame_idx: int):
        """Seek to specific frame index."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    
    def __del__(self):
        """Cleanup: release video capture."""
        if hasattr(self, 'cap'):
            self.cap.release()
