# Video Dataset Processor for Deep Learning

A production-ready video processing pipeline designed for moderate-scale deep learning dataset creation (20-100 videos, 1-2 hours each). The system focuses on simplicity, maintainability, and performance using proven technologies.

## Features

- **Parallel Downloads**: Download multiple videos concurrently with detailed progress tracking (speed, titles, per-video status)
- **Smart Skipping**: Automatically skips already downloaded videos and already processed videos (filesystem-based checks)
- **Integrity Validation**: FFmpeg-based validation (optional, with OpenCV fallback) and black frame detection
- **Scene Detection**: Automatic scene boundary detection using PySceneDetect
- **Video Decoding**: Fast video frame extraction using OpenCV (h264 warnings suppressed)
- **Parallel Frame Extraction**: Multi-threaded frame extraction from multiple scenes
- **Frame Extraction**: Extract frames from scenes with optional entropy-based deduplication
- **Metadata Tracking**: Comprehensive manifest system for processing history (reporting/logging only)

## Installation

### Prerequisites

- Python 3.10+ (CPython) or 3.11+ (PyPy)
- FFmpeg (optional, for enhanced video validation - OpenCV fallback available)

### Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# FFmpeg (optional but recommended for better validation)
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
```


## Quick Start

### 1. Create URLs File

Create `data/urls.txt` with one URL per line:

```
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
https://www.youtube.com/watch?v=VIDEO_ID_3
```

### 2. Configure (Optional)

Edit `config.yaml` for default settings. All settings can be overridden via command-line arguments.

### 3. Run Pipeline

```bash
# Basic usage (uses config.yaml defaults)
python scripts/process_videos.py

# With custom default config
python scripts/process_videos.py -c my_config.yaml

# Override specific settings via CLI
python scripts/process_videos.py --num-workers 8 --enable-deduplication --output-dir /path/to/output

# Override input URLs and output directory
python scripts/process_videos.py -u /path/to/urls.txt --output-dir /path/to/output
```

## Configuration

The `config.yaml` file contains default settings. **All settings can be overridden via command-line arguments**:

```yaml
# Input/Output
urls_file: "data/urls.txt"
download_dir: "data/raw"
output_dir: "data/processed"

# Download Settings
video_quality: "best[height<=1080]"
num_workers: 4

# Scene Detection
detect_scenes: true
scene_detector: "adaptive"
scene_threshold: 3.0

# Frame Extraction
output_resolution: [640, 480]
jpeg_quality: 85
enable_deduplication: false
frame_workers: 4  # Number of parallel workers for frame extraction

# Folder Structure
flat_structure: false  # true = all scenes in one folder, false = hierarchical
```

## Command-Line Options

All settings from `config.yaml` can be overridden via CLI arguments:

```bash
python scripts/process_videos.py [OPTIONS]

Configuration:
  -c, --config FILE           Default configuration file (default: config.yaml)
  
Input/Output:
  -u, --urls-file FILE        URLs file path
  --download-dir DIR          Directory to download videos to
  --output-dir DIR            Directory to save processed frames
  --manifest-path PATH        Path to manifest JSON file

Download Settings:
  --video-quality QUALITY     Video quality filter (e.g., "best[height<=1080]")
  --max-downloads N           Maximum number of videos to download
  --num-workers N             Number of parallel download workers

Validation:
  --black-threshold N         Pixel intensity threshold for black frames (0-255)
  --max-black-ratio RATIO     Max ratio of black frames before flagging (0.0-1.0)
  --skip-validation           Skip integrity validation

Scene Detection:
  --no-scene-detection        Disable scene detection (treat video as single scene)
  --scene-detector TYPE       Scene detector type (content, adaptive, threshold)
  --scene-threshold FLOAT     Scene detection threshold
  --min-scene-length N        Minimum frames per scene
  --downscale-factor N       Downscale factor for faster detection

Frame Extraction:
  --resolution WIDTHxHEIGHT    Output resolution (e.g., 640x480)
  --jpeg-quality N            JPEG quality 1-100
  --enable-deduplication      Enable entropy-based frame deduplication
  --entropy-percentile FLOAT  Keep frames above this entropy percentile (0.0-100.0)
  --frame-workers N           Number of parallel workers for frame extraction

Folder Structure:
  --flat-structure            Use flat structure (all scenes in one folder)

Performance:
  --use-cpu                   Use CPU instead of GPU (currently uses CPU decoding)

Logging:
  --log-level LEVEL           Logging level (DEBUG, INFO, WARNING, ERROR)
  --log-file PATH             Log file path
  -v, --verbose               Verbose logging (sets log level to DEBUG)

Examples:
  # Override output directory and workers
  python scripts/process_videos.py --output-dir /path/to/output --num-workers 8
  
  # Use different URLs file and skip validation
  python scripts/process_videos.py -u /path/to/urls.txt --skip-validation
  
  # Custom resolution and quality
  python scripts/process_videos.py --resolution 512x512 --jpeg-quality 90
```

## Project Structure

```
video_dataset_processor/
├── README.md
├── requirements.txt
├── config.yaml
├── src/
│   ├── __init__.py
│   ├── downloader.py          # Parallel video downloads
│   ├── integrity_checker.py   # Video validation (FFmpeg + OpenCV)
│   ├── video_decoder.py       # OpenCV-based video decoding
│   ├── scene_detector.py      # Scene detection
│   ├── frame_processor.py     # Frame extraction
│   ├── manifest_manager.py    # Metadata tracking
│   ├── pipeline.py            # Core pipeline orchestration
│   └── utils.py               # Shared utilities
├── scripts/
│   └── process_videos.py     # CLI entry point
├── data/
│   ├── raw/                   # Downloaded videos
│   ├── processed/             # Extracted frames
│   ├── urls.txt               # Input URLs
│   └── manifest.json          # Processing metadata
└── logs/
    └── processing.log         # Log file
```

## Output Structure

Processed frames are organized by video and scene. By default (hierarchical structure):

```
data/processed/
├── video_001/
│   ├── scene_000/
│   │   ├── frame_0000.jpg
│   │   ├── frame_0001.jpg
│   │   └── ...
│   └── scene_001/
│       └── ...
└── video_002/
    └── ...
```

With `flat_structure: true`, all scenes are in a single `scenes/` folder:
```
data/processed/scenes/
├── video_001_scene_000/
├── video_001_scene_001/
└── ...
```

## How It Works

- **Automatic Resumption**: The pipeline automatically skips videos that are already downloaded (checks file existence and size) and videos that are already processed (checks for existing frame directories). No need to manually track progress.
- **Manifest**: The `manifest.json` file is generated for reporting and logging purposes only. Processing decisions are based on filesystem checks.

## Performance

For **20 videos × 1.5 hours** (30 hours total):

| Stage | Time Estimate |
|-------|--------------|
| Download (4 workers) | 2-6 hours |
| Validation | 30-60 minutes |
| Scene Detection | 15-30 minutes |
| Frame Extraction | 2-4 hours |
| **Total** | **4-10 hours** |

## Hardware Recommendations

- **CPU**: 6-8 cores (for parallel downloads and video decoding)
- **RAM**: 16GB+
- **Storage**: SSD recommended (500GB+ for raw + processed)

## Troubleshooting

### OpenCV installation issues

If `opencv-python` fails to install:

```bash
# Try the headless version (no GUI dependencies)
pip install opencv-python-headless

# Or install from conda
conda install -c conda-forge opencv
```

### FFmpeg not found

FFmpeg is optional. If not installed, the pipeline will use OpenCV-based integrity checking (less comprehensive but still functional). To enable FFmpeg validation, install it using your system package manager (see Installation section).

### Out of memory

- Reduce `num_workers` in config
- Lower `output_resolution`
- Enable `enable_deduplication` to reduce frame count

## License

This project uses various open-source libraries. See individual library licenses for details.

## Contributing

This is a production-ready implementation. For improvements:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Acknowledgments

Built with:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading
- [OpenCV](https://opencv.org/) - Video decoding and processing
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) - Scene detection
- [Pillow](https://python-pillow.org/) - Image processing

