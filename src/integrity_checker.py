"""
Video integrity checking using FFmpeg and frame analysis
"""

import subprocess
import logging
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict

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
            decoder = VideoDecoder(video_path, use_gpu=False, logger=self.logger)
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
    ) -> Dict:
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

