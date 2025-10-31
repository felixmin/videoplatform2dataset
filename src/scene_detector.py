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

