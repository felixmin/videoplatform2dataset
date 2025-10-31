# Video Dataset Processor for Deep Learning

A production-ready video processing pipeline designed for moderate-scale deep learning dataset creation (20-100 videos, 1-2 hours each). The system focuses on simplicity, maintainability, and performance using proven technologies.

## Features

- **Parallel Downloads**: Download multiple videos concurrently with progress tracking
- **Integrity Validation**: FFmpeg-based validation and black frame detection
- **Scene Detection**: Automatic scene boundary detection using PySceneDetect
- **High-Performance Decoding**: GPU-accelerated video decoding with Decord
- **Frame Extraction**: Extract frames from scenes with optional entropy-based deduplication
- **Metadata Tracking**: Comprehensive manifest system for processing history

## Installation

### Prerequisites

- Python 3.10+ (CPython) or 3.11+ (PyPy)
- FFmpeg (for video processing)
- NVIDIA GPU (optional, for GPU acceleration)

### Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install FFmpeg
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
```

### Install Decord (GPU Support)

For GPU acceleration, Decord may need special installation:

```bash
# Using conda (recommended)
conda install -c conda-forge decord

# Or build from source
pip install --no-binary decord decord
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

Edit `config.yaml` to customize settings, or use command-line arguments.

### 3. Run Pipeline

```bash
# Basic usage
python scripts/process_videos.py

# With custom config
python scripts/process_videos.py -c my_config.yaml

# With command-line overrides
python scripts/process_videos.py --num-workers 8 --enable-deduplication
```

## Configuration

The `config.yaml` file contains all settings:

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
```

## Command-Line Options

```bash
python scripts/process_videos.py [OPTIONS]

Options:
  -c, --config FILE           Configuration file (default: config.yaml)
  -u, --urls-file FILE        URLs file (overrides config)
  --num-workers N             Number of parallel download workers
  --no-scene-detection        Disable scene detection
  --enable-deduplication      Enable entropy-based deduplication
  --resolution WIDTHxHEIGHT   Output resolution (e.g., 640x480)
  --jpeg-quality N            JPEG quality 1-100
  --use-cpu                   Disable GPU acceleration
  --skip-validation           Skip integrity validation
  -v, --verbose               Verbose logging
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
│   ├── integrity_checker.py   # Video validation
│   ├── video_decoder.py       # Decord-based decoding
│   ├── scene_detector.py      # Scene detection
│   ├── frame_processor.py     # Frame extraction
│   ├── manifest_manager.py    # Metadata tracking
│   └── utils.py               # Shared utilities
├── scripts/
│   └── process_videos.py     # Main CLI script
├── data/
│   ├── raw/                   # Downloaded videos
│   ├── processed/             # Extracted frames
│   ├── urls.txt               # Input URLs
│   └── manifest.json          # Processing metadata
└── logs/
    └── processing.log         # Log file
```

## Output Structure

Processed frames are organized by video and scene:

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

## Performance

For **20 videos × 1.5 hours** (30 hours total):

| Stage | Time Estimate |
|-------|--------------|
| Download (4 workers) | 2-6 hours |
| Validation | 30-60 minutes |
| Scene Detection | 15-30 minutes |
| Frame Extraction (GPU) | 1-2 hours |
| **Total** | **4-10 hours** |

## Hardware Recommendations

- **CPU**: 6-8 cores (for parallel downloads)
- **RAM**: 16GB+
- **GPU**: NVIDIA with NVDEC (GTX 1060+) for 3-5x speedup
- **Storage**: SSD recommended (500GB+ for raw + processed)

## Troubleshooting

### Decord import fails

```bash
conda install -c conda-forge decord
```

### GPU not detected

Decord will automatically fall back to CPU if GPU is unavailable.

### FFmpeg not found

Install FFmpeg using your system package manager (see Installation section).

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
- [Decord](https://github.com/dmlc/decord) - High-performance video decoding
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) - Scene detection
- [OpenCV](https://opencv.org/) - Video processing
- [Pillow](https://python-pillow.org/) - Image processing

