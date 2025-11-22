#!/usr/bin/env python3
"""
Main video processing pipeline orchestrator
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import setup_logging, load_config
from src.pipeline import run_pipeline


def parse_arguments():
    """Parse command-line arguments."""
    # Default config path relative to repo root (parent of scripts/)
    repo_root = Path(__file__).parent.parent
    default_config = repo_root / 'config.yaml'
    
    parser = argparse.ArgumentParser(
        description="Video dataset processor for deep learning",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Configuration file
    parser.add_argument('-c', '--config', type=str, default=str(default_config),
                       help='Default configuration file path (all settings can be overridden via CLI)')
    
    # Input/Output paths
    parser.add_argument('-u', '--urls-file', type=str,
                       help='URLs file path (overrides config)')
    parser.add_argument('--download-dir', type=str,
                       help='Directory to download videos to (overrides config)')
    parser.add_argument('--output-dir', type=str,
                       help='Directory to save processed frames (overrides config)')
    parser.add_argument('--manifest-path', type=str,
                       help='Path to manifest JSON file (overrides config)')
    
    # Download settings
    parser.add_argument('--video-quality', type=str,
                       help='Video quality filter (e.g., "best[height<=1080]")')
    parser.add_argument('--max-downloads', type=int,
                       help='Maximum number of videos to download (null = all)')
    parser.add_argument('--num-workers', type=int,
                       help='Number of parallel download workers')
    
    # Validation settings
    parser.add_argument('--black-threshold', type=int,
                       help='Pixel intensity threshold for black frames (0-255)')
    parser.add_argument('--max-black-ratio', type=float,
                       help='Maximum ratio of black frames before flagging (0.0-1.0)')
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip integrity validation (not recommended)')
    
    # Scene detection settings
    parser.add_argument('--no-scene-detection', action='store_true',
                       help='Disable scene detection (treat video as single scene)')
    parser.add_argument('--scene-detector', type=str, choices=['content', 'adaptive', 'threshold'],
                       help='Scene detector type')
    parser.add_argument('--scene-threshold', type=float,
                       help='Scene detection threshold')
    parser.add_argument('--min-scene-length', type=int,
                       help='Minimum frames per scene')
    parser.add_argument('--downscale-factor', type=int,
                       help='Downscale factor for faster scene detection')
    
    # Frame extraction settings
    parser.add_argument('--resolution', type=str,
                       help='Output resolution WIDTHxHEIGHT (e.g., 640x480)')
    parser.add_argument('--jpeg-quality', type=int,
                       help='JPEG quality 1-100')
    parser.add_argument('--enable-deduplication', action='store_true',
                       help='Enable entropy-based frame deduplication')
    parser.add_argument('--entropy-percentile', type=float,
                       help='Keep frames above this entropy percentile (0.0-100.0)')

    # Motion analysis and stabilization
    parser.add_argument('--analyze-motion', action='store_true',
                       help='Enable camera motion analysis (generates scenes.csv)')
    parser.add_argument('--stabilize-video', action='store_true',
                       help='Stabilize video before frame extraction (requires --analyze-motion)')
    parser.add_argument('--max-trans-low', type=float,
                       help='Max translation threshold for static label (pixels)')
    parser.add_argument('--max-trans-high', type=float,
                       help='Max translation threshold for moving label (pixels)')
    parser.add_argument('--max-angle-low', type=float,
                       help='Max rotation threshold for static label (radians)')
    parser.add_argument('--max-angle-high', type=float,
                       help='Max rotation threshold for moving label (radians)')

    # Folder structure
    parser.add_argument('--flat-structure', action='store_true',
                       help='Use flat structure (all scenes in one folder)')

    # Performance
    parser.add_argument('--use-cpu', action='store_true',
                       help='Disable GPU acceleration (use CPU only)')
    
    # Logging
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--log-file', type=str,
                       help='Log file path')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose logging (sets log level to DEBUG)')
    
    return parser.parse_args()


def apply_cli_overrides(args, config):
    """
    Apply command-line argument overrides to config dictionary.
    
    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary to modify
    """
    # Input/Output paths
    if args.urls_file:
        config['urls_file'] = args.urls_file
    if args.download_dir:
        config['download_dir'] = args.download_dir
    if args.output_dir:
        config['output_dir'] = args.output_dir
    if args.manifest_path:
        config['manifest_path'] = args.manifest_path
    
    # Download settings
    if args.video_quality:
        config['video_quality'] = args.video_quality
    if args.max_downloads is not None:
        config['max_downloads'] = args.max_downloads
    if args.num_workers:
        config['num_workers'] = args.num_workers
    
    # Validation settings
    if args.black_threshold is not None:
        config['black_threshold'] = args.black_threshold
    if args.max_black_ratio is not None:
        config['max_black_ratio'] = args.max_black_ratio
    
    # Scene detection settings
    if args.no_scene_detection:
        config['detect_scenes'] = False
    if args.scene_detector:
        config['scene_detector'] = args.scene_detector
    if args.scene_threshold is not None:
        config['scene_threshold'] = args.scene_threshold
    if args.min_scene_length is not None:
        config['min_scene_length'] = args.min_scene_length
    if args.downscale_factor is not None:
        config['downscale_factor'] = args.downscale_factor
    
    # Frame extraction settings
    if args.resolution:
        w, h = map(int, args.resolution.split('x'))
        config['output_resolution'] = [w, h]
    if args.jpeg_quality:
        config['jpeg_quality'] = args.jpeg_quality
    if args.enable_deduplication:
        config['enable_deduplication'] = True
    if args.entropy_percentile is not None:
        config['entropy_percentile'] = args.entropy_percentile
    
    # Motion analysis and stabilization
    if args.analyze_motion:
        config['analyze_motion'] = True
    if args.stabilize_video:
        config['stabilize_video'] = True
    # Update motion thresholds if provided
    if 'motion_thresholds' not in config:
        config['motion_thresholds'] = {}
    if args.max_trans_low is not None:
        config['motion_thresholds']['max_trans_low'] = args.max_trans_low
    if args.max_trans_high is not None:
        config['motion_thresholds']['max_trans_high'] = args.max_trans_high
    if args.max_angle_low is not None:
        config['motion_thresholds']['max_angle_low'] = args.max_angle_low
    if args.max_angle_high is not None:
        config['motion_thresholds']['max_angle_high'] = args.max_angle_high

    # Folder structure
    if args.flat_structure:
        config['flat_structure'] = True

    # Performance
    if args.use_cpu:
        config['use_gpu'] = False

    # Logging
    if args.log_level:
        config['log_level'] = args.log_level
    if args.log_file:
        config['log_file'] = args.log_file


def main():
    """CLI entry point for video processing pipeline."""
    args = parse_arguments()
    
    # Load default config
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: Default config file not found: {args.config}")
        sys.exit(1)
    
    # Override config with CLI args (all config values can be overridden)
    apply_cli_overrides(args, config)
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else config.get('log_level', 'INFO')
    setup_logging(config.get('log_file'), log_level)
    
    # Run the pipeline
    stats = run_pipeline(
        config=config,
        skip_validation=args.skip_validation,
        use_cpu=args.use_cpu
    )
    
    sys.exit(stats['exit_code'])


if __name__ == '__main__':
    main()

