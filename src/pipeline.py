"""
Video processing pipeline - core orchestration logic.
"""

import csv
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from .downloader import ParallelVideoDownloader
from .integrity_checker import IntegrityChecker
from .scene_detector import SceneDetector
from .frame_processor import FrameProcessor
from .frame_processor_ffmpeg import FrameProcessorFFmpeg
from .manifest_manager import ManifestManager
from .motion_analyzer import MotionAnalyzer
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
    
    # Use FFmpeg-based frame processor (5-10x faster than OpenCV)
    frame_processor = FrameProcessorFFmpeg(
        output_dir=config['output_dir'],
        output_resolution=tuple(config['output_resolution']) if config.get('output_resolution') else None,
        jpeg_quality=config.get('jpeg_quality', 85),
        logger=logger
    )
    
    manifest = ManifestManager(
        manifest_path=config.get('manifest_path', 'data/manifest.json'),
        logger=logger
    )

    # Initialize motion analyzer if enabled
    motion_analyzer = MotionAnalyzer(logger=logger) if config.get('analyze_motion', False) else None

    # Stage 1: Download
    logger.info("=" * 60)
    logger.info("STAGE 1: DOWNLOADING VIDEOS")
    logger.info("=" * 60)
    print("\n" + "=" * 60)
    print("STAGE 1: DOWNLOADING VIDEOS")
    print("=" * 60)
    
    urls = downloader.read_urls_from_file(config['urls_file'])
    print(f"Found {len(urls)} video URLs to download")
    
    downloaded = downloader.download_videos_parallel(
        urls,
        max_downloads=config.get('max_downloads')
    )
    
    logger.info(f"Downloaded {len(downloaded)} videos")
    print(f"✓ Downloaded {len(downloaded)} videos")
    
    # Process each video
    stats = {
        'downloaded': len(downloaded),
        'validated': 0,
        'processed': 0,
        'total_scenes': 0,
        'total_frames': 0,
        'failed': 0
    }
    
    print("\n" + "=" * 60)
    print("STAGE 2-4: PROCESSING VIDEOS")
    print("=" * 60)
    
    for idx, video_meta in enumerate(downloaded, 1):
        video_path = video_meta['filepath']
        video_id = video_meta['video_id']
        
        print(f"\n[{idx}/{len(downloaded)}] Processing: {video_id}")
        
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
                        print(f"  → Skipping (already processed)")
                        continue
            else:
                # Hierarchical structure: check for video-specific directory
                video_output_dir = output_dir / video_name
                if video_output_dir.exists():
                    # Check if we have scene directories with frames
                    scene_dirs = [d for d in video_output_dir.iterdir() if d.is_dir() and d.name.startswith("scene_")]
                    if scene_dirs and any((d / "frame_0000.jpg").exists() for d in scene_dirs):
                        logger.info(f"Skipping already processed: {video_id} (frames found in {video_output_dir})")
                        print(f"  → Skipping (already processed)")
                        continue
            
            # Stage 2: Validate
            if not skip_validation:
                print(f"  [Stage 2] Validating...")
                logger.info(f"Validating: {video_id}")
                validation = validator.validate_video(video_path)
                
                if not validation['is_valid']:
                    logger.warning(f"Video failed validation: {video_id}")
                    print(f"  ✗ Validation failed")
                    manifest.add_video(video_id, video_meta, validation, [])
                    stats['failed'] += 1
                    continue
                
                stats['validated'] += 1
                print(f"  ✓ Validation passed")
            else:
                validation = {'is_valid': True, 'skipped': True}
                print(f"  → Validation skipped")
            
            # Stage 3: Scene Detection
            if scene_detector:
                print(f"  [Stage 3] Detecting scenes...")
                logger.info(f"Detecting scenes: {video_id}")
                scenes = scene_detector.detect_scenes(video_path, show_progress=False)

                # Fallback: if scene detection found nothing, treat entire video as one scene
                if not scenes:
                    logger.warning(f"Scene detection found 0 scenes in {video_id}, treating entire video as one scene")
                    print(f"  ⚠ Scene detection found 0 scenes, treating entire video as one scene")
                    from .video_decoder import VideoDecoder
                    decoder = VideoDecoder(video_path, use_gpu=not use_cpu)
                    scenes = [(0, decoder.num_frames)]
            else:
                # Treat entire video as one scene
                from .video_decoder import VideoDecoder
                decoder = VideoDecoder(video_path, use_gpu=not use_cpu)
                scenes = [(0, decoder.num_frames)]

            stats['total_scenes'] += len(scenes)
            print(f"  ✓ Found {len(scenes)} scene(s)")

            # Stage 3.5: Motion Analysis & Stabilization
            processing_video_path = video_path  # Default to original
            scene_motion_metadata = []
            output_video_name = Path(video_path).stem  # Track which video we're extracting from

            if motion_analyzer:
                print(f"  [Stage 3.5] Analyzing motion...")
                logger.info(f"Analyzing camera motion: {video_id}")

                trf_path = Path(video_path).parent / f"{Path(video_path).stem}.trf"

                if motion_analyzer.run_vidstab_detect(str(video_path), str(trf_path)):
                    # Parse transformation data
                    motion_data = motion_analyzer.parse_trf(str(trf_path))

                    # Check if we actually got valid motion data
                    has_valid_motion = len(motion_data.get('dx', [])) > 0

                    if has_valid_motion:
                        # Analyze scenes and assign labels
                        thresholds = config.get('motion_thresholds', {})
                        scene_motion_metadata = motion_analyzer.analyze_scenes(scenes, motion_data, thresholds)

                        # Display original motion summary
                        static_count = sum(1 for s in scene_motion_metadata if s['label'] == 'static')
                        moving_count = sum(1 for s in scene_motion_metadata if s['label'] == 'moving')
                        uncertain_count = sum(1 for s in scene_motion_metadata if s['label'] == 'uncertain')
                        print(f"    Original: Static={static_count}, Moving={moving_count}, Uncertain={uncertain_count}")

                        # Stabilization if enabled
                        if config.get('stabilize_video', False):
                            print(f"  [Stage 3.5] Stabilizing video...")
                            logger.info(f"Stabilizing video: {video_id}")

                            stabilized_path = Path(video_path).parent / f"{Path(video_path).stem}_stabilized.mp4"

                            if motion_analyzer.stabilize_video(str(video_path), str(trf_path), str(stabilized_path)):
                                processing_video_path = str(stabilized_path)
                                output_video_name = Path(stabilized_path).stem  # Update output folder name
                                print(f"  ✓ Video stabilized")

                                # Post-stabilization analysis
                                print(f"  [Stage 3.5] Analyzing stabilization result...")
                                post_trf_path = Path(video_path).parent / f"{Path(video_path).stem}_post.trf"

                                if motion_analyzer.run_vidstab_detect(str(stabilized_path), str(post_trf_path)):
                                    post_motion_data = motion_analyzer.parse_trf(str(post_trf_path))

                                    if len(post_motion_data.get('dx', [])) > 0:
                                        post_metrics = motion_analyzer.analyze_scenes(scenes, post_motion_data, thresholds)

                                        # Merge post-stabilization metrics into metadata
                                        for i, meta in enumerate(scene_motion_metadata):
                                            if i < len(post_metrics):
                                                meta['stabilized_max_trans'] = post_metrics[i]['max_trans']
                                                meta['stabilized_max_angle'] = post_metrics[i]['max_angle']
                                                meta['stabilized_label'] = post_metrics[i]['label']

                                        # Display post-stabilization summary
                                        post_static = sum(1 for s in post_metrics if s['label'] == 'static')
                                        post_moving = sum(1 for s in post_metrics if s['label'] == 'moving')
                                        post_uncertain = sum(1 for s in post_metrics if s['label'] == 'uncertain')
                                        print(f"    Stabilized: Static={post_static}, Moving={post_moving}, Uncertain={post_uncertain}")

                                    # Cleanup post TRF
                                    if post_trf_path.exists():
                                        post_trf_path.unlink()
                            else:
                                logger.warning(f"Stabilization failed for {video_id}, using original video")
                                print(f"  ⚠ Stabilization failed, using original video")
                    else:
                        logger.warning(f"No valid motion data parsed for {video_id}")
                        print(f"  ⚠ No motion data found, skipping stabilization")

                    # Cleanup TRF file
                    if trf_path.exists():
                        trf_path.unlink()
                else:
                    logger.warning(f"Motion analysis failed for {video_id}")
                    print(f"  ⚠ Motion analysis failed")

            # Stage 4: Frame Extraction
            print(f"  [Stage 4] Extracting frames...")
            logger.info(f"Extracting frames: {video_id}")
            scene_metadata = frame_processor.process_video(
                processing_video_path,
                scenes,
                flat_structure=config.get('flat_structure', False),
                use_gpu=not use_cpu
            )

            frames_extracted = sum(s['saved_frames'] for s in scene_metadata)
            stats['total_frames'] += frames_extracted
            stats['processed'] += 1
            print(f"  ✓ Extracted {frames_extracted} frames")

            # Write CSV after frame extraction (so it's in the same folder as frames)
            if scene_motion_metadata:
                # Use output_video_name (which reflects whether we used stabilized video)
                if config.get('flat_structure', False):
                    # Flat: CSV goes in scenes folder
                    csv_path = Path(config['output_dir']) / "scenes" / f"{output_video_name}_scenes.csv"
                else:
                    # Hierarchical: CSV goes in video folder
                    csv_path = Path(config['output_dir']) / output_video_name / "scenes.csv"

                csv_path.parent.mkdir(parents=True, exist_ok=True)

                # Dynamic fieldnames based on what's in the metadata
                if scene_motion_metadata:
                    fieldnames = list(scene_motion_metadata[0].keys())

                    with open(csv_path, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(scene_motion_metadata)

                    logger.info(f"Written scene metadata to {csv_path}")
                    print(f"  ✓ Motion metadata saved to {csv_path.name}")

            # Cleanup stabilized video if created
            if processing_video_path != video_path and Path(processing_video_path).exists():
                Path(processing_video_path).unlink()
                logger.debug(f"Cleaned up stabilized video: {processing_video_path}")

            # Update manifest
            manifest.add_video(video_id, video_meta, validation, scene_metadata)
            manifest.save()
            
        except Exception as e:
            logger.error(f"Failed to process {video_id}: {str(e)}", exc_info=True)
            print(f"  ✗ Error: {str(e)}")
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
    
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Videos downloaded:  {stats['downloaded']}")
    print(f"Videos validated:   {stats['validated']}")
    print(f"Videos processed:   {stats['processed']}")
    print(f"Total scenes:       {stats['total_scenes']}")
    print(f"Total frames:       {stats['total_frames']}")
    print(f"Failed:             {stats['failed']}")
    print(f"Total time:         {format_time(elapsed)}")
    print("=" * 60)
    
    stats['exit_code'] = 0 if stats['failed'] == 0 else 1
    return stats

