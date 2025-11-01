"""
Video processing pipeline - core orchestration logic.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from .downloader import ParallelVideoDownloader
from .integrity_checker import IntegrityChecker
from .scene_detector import SceneDetector
from .frame_processor import FrameProcessor
from .manifest_manager import ManifestManager
from .utils import format_time


def run_pipeline(config: Dict, skip_validation: bool = False, use_cpu: bool = False) -> Dict:
    """
    Execute the complete video processing pipeline.
    
    Args:
        config: Configuration dictionary
        skip_validation: Skip integrity validation
        use_cpu: Use CPU instead of GPU
        
    Returns:
        Dictionary with processing statistics and exit code (0 = success, 1 = failure)
    """
    logger = logging.getLogger(__name__)
    
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
        num_workers=config.get('frame_workers'),
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
    
    urls = downloader.read_urls_from_file(config['urls_file'])
    
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
            # Check if already processed by looking at filesystem
            video_name = Path(video_path).stem
            output_dir = Path(config['output_dir'])
            if config.get('flat_structure', False):
                # Flat structure: check for scenes directory
                processed_dir = output_dir / "scenes"
                if processed_dir.exists():
                    # Check if we have scenes for this video
                    scene_dirs = [d for d in processed_dir.iterdir() if d.is_dir() and video_name in d.name]
                    if scene_dirs and any((d / "frame_0000.jpg").exists() for d in scene_dirs):
                        logger.info(f"Skipping already processed: {video_id} (frames found in {processed_dir})")
                        continue
            else:
                # Hierarchical structure: check for video-specific directory
                video_output_dir = output_dir / video_name
                if video_output_dir.exists():
                    # Check if we have scene directories with frames
                    scene_dirs = [d for d in video_output_dir.iterdir() if d.is_dir() and d.name.startswith("scene_")]
                    if scene_dirs and any((d / "frame_0000.jpg").exists() for d in scene_dirs):
                        logger.info(f"Skipping already processed: {video_id} (frames found in {video_output_dir})")
                        continue
            
            # Stage 2: Validate
            if not skip_validation:
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
                from .video_decoder import VideoDecoder
                decoder = VideoDecoder(video_path, use_gpu=not use_cpu)
                scenes = [(0, decoder.num_frames)]
            
            stats['total_scenes'] += len(scenes)
            
            # Stage 4: Frame Extraction
            logger.info(f"Extracting frames: {video_id}")
            scene_metadata = frame_processor.process_video(
                video_path,
                scenes,
                flat_structure=config.get('flat_structure', False),
                use_gpu=not use_cpu
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
    
    stats['exit_code'] = 0 if stats['failed'] == 0 else 1
    return stats

