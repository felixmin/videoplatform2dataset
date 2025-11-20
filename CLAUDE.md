# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A video processing pipeline for creating deep learning datasets from video platforms (YouTube). Processes 20-100 videos (1-2 hours each) through parallel downloading, integrity validation, scene detection, and frame extraction.

## Essential Commands

### Running the Pipeline
```bash
# Basic usage with default config.yaml settings
python scripts/process_videos.py

# With custom URLs file and output directory
python scripts/process_videos.py -u /path/to/urls.txt --output-dir /path/to/output

# Override workers and enable deduplication
python scripts/process_videos.py --num-workers 8 --enable-deduplication --frame-workers 4

# Skip validation and disable scene detection
python scripts/process_videos.py --skip-validation --no-scene-detection

# Custom resolution and quality
python scripts/process_videos.py --resolution 512x512 --jpeg-quality 90

# Verbose logging
python scripts/process_videos.py -v
```

### Dependencies
```bash
# Install all dependencies
pip install -r requirements.txt

# FFmpeg is required for frame extraction
sudo apt-get install ffmpeg  # Ubuntu/Debian
brew install ffmpeg          # macOS
```

## Architecture

### Pipeline Flow (src/pipeline.py:20-225)
The main pipeline orchestrates 4 sequential stages:

1. **Download Stage** - Parallel video downloads via `ParallelVideoDownloader`
2. **Validation Stage** - FFmpeg-based integrity checking via `IntegrityChecker`
3. **Scene Detection Stage** - PySceneDetect integration via `SceneDetector`
4. **Frame Extraction Stage** - FFmpeg batch extraction via `FrameProcessorFFmpeg`

Each video is processed individually through stages 2-4. The pipeline uses filesystem checks to skip already-processed videos (looks for existing frame directories).

### Component Responsibilities

**ParallelVideoDownloader** (src/downloader.py)
- Multiprocessing-based parallel downloads using yt-dlp
- Progress tracking via shared Manager.dict() for real-time updates across workers
- Module-level `_download_single_worker()` function required for multiprocessing pickling
- Filesystem-based skip logic (checks file existence and size)

**IntegrityChecker** (src/integrity_checker.py)
- Primary: FFmpeg decode-to-null test for corruption detection
- Fallback: OpenCV-based frame reading if FFmpeg unavailable
- Black frame detection via VideoDecoder sampling
- Returns validation dict: `{'is_valid': bool, 'method': str, 'error': str, ...}`

**SceneDetector** (src/scene_detector.py)
- Wraps PySceneDetect with three detector types: content, adaptive, threshold
- Returns list of (start_frame, end_frame) tuples
- Uses downscale_factor for performance optimization
- **Critical fallback:** If scene detection returns 0 scenes, pipeline automatically treats entire video as one scene (src/pipeline.py:166-171)
- This prevents data loss when scene detection fails

**FrameProcessorFFmpeg** (src/frame_processor_ffmpeg.py)
- **5-10x faster than OpenCV** due to batch FFmpeg extraction
- Parallel scene processing via ThreadPoolExecutor
- FFmpeg select filter for frame range extraction: `-vf "select='between(n,start,end)'"`
- GPU acceleration support via NVDEC (hwaccel parameter)
- Returns scene metadata: `[{'scene_id': int, 'start_frame': int, 'end_frame': int, 'saved_frames': int, 'output_path': str}]`

**ManifestManager** (src/manifest_manager.py)
- Tracks processing metadata in JSON format (reporting/logging only)
- Processing decisions are based on filesystem, NOT manifest

### Logging System

**Configuration:** All logging is configured via `setup_logging()` in src/utils.py:48, which sets up the root logger.

**Output locations:**
- **Console:** Always outputs to stderr with timestamps and module names
- **File:** Logs to `logs/processing.log` (or path specified in config.yaml)
- Both outputs include: timestamp, module name, log level, message

**Module loggers:** Each module uses `logging.getLogger(__name__)` which automatically inherits the root logger's configuration. This means all logs from all modules go to both console and file.

**Viewing logs:**
```bash
# Real-time log following
tail -f logs/processing.log

# Search logs
grep "ERROR" logs/processing.log
grep "scene detection" logs/processing.log
```

**VideoDecoder** (src/video_decoder.py)
- OpenCV-based video decoding wrapper
- Used only for frame counting and black frame sampling
- NOT used for frame extraction (replaced by FFmpeg)

### Configuration System

All settings in `config.yaml` can be overridden via CLI arguments. The CLI parsing in `scripts/process_videos.py:100-169` uses `apply_cli_overrides()` to merge config with arguments.

**The config.yaml file is extensively documented** with comments explaining:
- Which component uses each setting
- What it does and trade-offs
- Example values and when to adjust them
- See config.yaml for complete documentation of all settings

**Key config values:**
- `num_workers`: Parallel download workers (multiprocessing)
- `frame_workers`: Parallel scene extraction workers (threading)
- `flat_structure`: Changes output structure (hierarchical vs flat)
- `detect_scenes`: Can be disabled to treat videos as single scene
- `downscale_factor`: Scene detection downscaling (4 = good balance, 8 = faster but may miss scenes, 2 = slower but more accurate)
- `output_resolution`: Tuple [width, height] or null for original

### Critical Implementation Details

**GPU Acceleration Status:**
GPU support is ENABLED by default and stable. The code automatically falls back to CPU if GPU is unavailable (src/frame_processor_ffmpeg.py:100-148). To disable GPU explicitly, use `--use-cpu` flag or set `use_gpu: false` in config.yaml.

**Verifying GPU is Working:**
Check logs during frame extraction stage:
- GPU working: Logs will show FFmpeg commands with `-hwaccel cuda`
- CPU fallback: Logs will show "GPU acceleration failed, retrying with CPU"
- To force CPU-only: Use `--use-cpu` flag

**Multiprocessing Worker Functions:**
Worker functions for multiprocessing.Pool MUST be at module level for pickling. See `_download_single_worker()` in src/downloader.py:53.

**Progress Tracking:**
Shared state via Manager.dict() requires reassignment for nested updates:
```python
current = progress_dict[idx]
current['field'] = value
progress_dict[idx] = current  # Required for sync
```

**Skip Logic:**
Processing skip decisions are based on filesystem checks (src/pipeline.py:116-138):
- Hierarchical: Checks `{output_dir}/{video_name}/scene_*/frame_0000.jpg`
- Flat: Checks `{output_dir}/scenes/{video_name}_scene_*/frame_0000.jpg`

**FFmpeg Command Pattern:**
Frame extraction uses select filter for precise frame ranges:
```bash
ffmpeg -i input.mp4 -vf "select='between(n,start,end)',scale=W:H" -qscale:v Q output_%04d.jpg
```

**Error Suppression:**
OpenCV h264 warnings are suppressed via FilteredStderr context manager to reduce log noise.

## Data Flow

Input: `data/urls.txt` (one URL per line)
↓
Download: `data/raw/{video_id}.mp4`
↓
Process: Validation → Scene Detection → Frame Extraction
↓
Output: `data/processed/{video_name}/scene_{N}/frame_{M}.jpg`
Metadata: `data/manifest.json`

## Performance Considerations

- FFmpeg frame extraction is 5-10x faster than OpenCV per-frame reading
- **GPU acceleration (NVDEC)**: 3-5x additional speedup for frame extraction via FFmpeg hardware decoding
  - Automatically enabled by default (`use_gpu: true` in config.yaml)
  - Graceful fallback: If GPU unavailable or FFmpeg lacks CUDA support, auto-retries with CPU (src/frame_processor_ffmpeg.py:143-148)
  - Verify GPU usage: Check FFmpeg logs for "hwaccel cuda" messages
- Parallel downloads limited by network bandwidth, not CPU
- Scene detection is CPU-bound; downscale_factor trades accuracy for speed
- Frame extraction parallelism is I/O-bound; too many workers causes disk contention
- Default JPEG quality reduced from 95→75 for imperceptible quality loss but faster encoding

### Processing Time Estimates (1-hour video, ~75 scenes)

| Stage | Time (CPU) | Time (GPU) |
|-------|-----------|-----------|
| Download | 5-10 min | 5-10 min |
| Validation (skip recommended) | 2-4 min | 2-4 min |
| Scene Detection | 20-40 sec | 20-40 sec |
| Frame Extraction | 3-6 min | 45-90 sec |
| **Total (skip validation)** | **9-12 min** | **2-3 min** |

## Testing

No test suite currently exists. Manual testing via:
```bash
# Test with single video
echo "https://youtube.com/watch?v=VIDEOID" > test_urls.txt
python scripts/process_videos.py -u test_urls.txt --output-dir /tmp/test
```
