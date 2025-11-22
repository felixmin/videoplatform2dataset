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

# Override download workers and enable deduplication
python scripts/process_videos.py --num-workers 8 --enable-deduplication

# Skip validation and disable scene detection
python scripts/process_videos.py --skip-validation --no-scene-detection

# Custom resolution and quality
python scripts/process_videos.py --resolution 512x512 --jpeg-quality 90

# Enable motion analysis and stabilization
python scripts/process_videos.py --analyze-motion --stabilize-video

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

### Pipeline Flow (src/pipeline.py:20-347)
The main pipeline orchestrates 5 sequential stages:

1. **Download Stage** - Parallel video downloads via `ParallelVideoDownloader`
2. **Validation Stage** - FFmpeg-based integrity checking via `IntegrityChecker`
3. **Scene Detection Stage** - PySceneDetect integration via `SceneDetector`
4. **Motion Analysis & Stabilization Stage (Optional)** - Camera motion detection and video stabilization via `MotionAnalyzer`
5. **Frame Extraction Stage** - FFmpeg batch extraction via `FrameProcessorFFmpeg`

Each video is processed individually through stages 2-5. The pipeline uses filesystem checks to skip already-processed videos (looks for existing frame directories).

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
- **Critical fallback:** If scene detection returns 0 scenes, pipeline automatically treats entire video as one scene (src/pipeline.py:169-175)
- This prevents data loss when scene detection fails

**MotionAnalyzer** (src/motion_analyzer.py)
- Uses FFmpeg's libvidstab for camera motion detection and video stabilization
- **Single-pass analysis:** Generates .trf file with per-frame transformation data via vidstabdetect
- **Per-scene aggregation:** Calculates max_trans (translation) and max_angle (rotation) metrics per scene
- **Scene classification:** Labels scenes as "static", "moving", or "uncertain" based on configurable thresholds
- **Optional stabilization:** Creates stabilized video via vidstabtransform using .trf data
- **Post-stabilization verification:** Re-analyzes stabilized video to measure improvement
- **Optimization:** Uses 360p downscaling for 4-10x speedup with negligible accuracy impact
- **TRF Format Support:** Handles both verbose format (local motion vectors) and simple format (global transforms)
- **Robust aggregation:** Uses median of local motion vectors to ignore moving objects (outliers)
- Returns scene metadata: `[{'scene_idx': int, 'start_frame': int, 'end_frame': int, 'max_trans': float, 'max_angle': float, 'label': str, 'stabilized_*': float (if stabilization enabled)}]`

**FrameProcessorFFmpeg** (src/frame_processor_ffmpeg.py)
- **5-10x faster than OpenCV** due to single-pass FFmpeg extraction
- **Single FFmpeg call per video** using `filter_complex` with `split` + `select` filters
- All scenes extracted in one pass: `[0:v]scale?,split=N -> per-scene select -> direct output`
- No I/O contention, no re-decoding, no temp folders, no hardlinks
- GPU acceleration support via NVDEC (hwaccel parameter) and CUDA scaling (scale_cuda)
- Returns scene metadata: `[{'scene_idx': int, 'start_frame': int, 'end_frame': int, 'saved_frames': int, 'output_dir': str}]`

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
- `flat_structure`: Changes output structure (hierarchical vs flat)
- `detect_scenes`: Can be disabled to treat videos as single scene
- `downscale_factor`: Scene detection downscaling (2 = good balance, 4 = faster but may miss scenes, 1 = slower but most accurate)
- `output_resolution`: Tuple [width, height] or null for original
- `use_gpu`: Enable GPU acceleration (auto-falls back to CPU on error)
- `analyze_motion`: Enable camera motion detection (default: false)
- `stabilize_video`: Enable video stabilization before frame extraction (requires analyze_motion, default: false)
- `motion_thresholds`: Dict with max_trans_low/high and max_angle_low/high for scene classification

### Critical Implementation Details

**GPU Acceleration Status:**
GPU support is ENABLED by default and stable. The code automatically falls back to CPU if GPU fails for ANY reason (src/frame_processor_ffmpeg.py:273-292). This includes format errors, device issues, or any FFmpeg failure when GPU is enabled. To disable GPU explicitly, use `--use-cpu` flag or set `use_gpu: false` in config.yaml.

**Verifying GPU is Working:**
Check logs during frame extraction stage:
- GPU working: Logs will show FFmpeg commands with `-hwaccel cuda` and successful processing
- CPU fallback: Logs will show "GPU run failed for <video>, falling back to CPU" followed by successful CPU processing
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
Processing skip decisions are based on filesystem checks (src/pipeline.py:120-142):
- Hierarchical: Checks `{output_dir}/{video_name}/scene_*/frame_0000.jpg`
- Flat: Checks `{output_dir}/scenes/{video_name}_scene_*/frame_0000.jpg`

**Motion Analysis Pipeline Integration:**
Motion analysis is integrated as Stage 3.5 between scene detection and frame extraction (src/pipeline.py:185-308):
1. Run vidstabdetect on original video → generates .trf file
2. Parse .trf file using regex to extract local motion vectors (handles verbose format)
3. Aggregate per-scene metrics using median (robust to outliers)
4. Classify scenes as static/moving/uncertain based on thresholds
5. If stabilization enabled:
   - Run vidstabtransform to create stabilized video
   - Update `processing_video_path` and `output_video_name` to use stabilized version
   - Run post-stabilization analysis to measure improvement
   - Merge post-stabilization metrics into scene metadata
6. Extract frames from `processing_video_path` (original or stabilized)
7. Write CSV with scene motion metadata to same folder as frames
8. Clean up temporary files (.trf, stabilized video)

**TRF File Format Handling:**
The motion analyzer supports two TRF formats:
- **Verbose format** (common): `Frame N (List M [(LM dx dy x y size contrast ...)])`
  - Uses regex: `r"\(LM\s+(-?\d+)\s+(-?\d+)"` to extract local motion vectors
  - Aggregates using `np.median()` to compute global camera motion
- **Simple format** (older): `frame_num dx dy da ...`
  - Direct parsing of space-separated values

**CSV Output Location:**
CSV is written AFTER frame extraction to ensure it lands in the correct folder (src/pipeline.py:282-303):
- Uses `output_video_name` which reflects whether stabilized video was used
- Hierarchical: `{output_dir}/{output_video_name}/scenes.csv`
- Flat: `{output_dir}/scenes/{output_video_name}_scenes.csv`
- Dynamic fieldnames based on metadata keys (includes stabilized_* columns if present)

**FFmpeg Command Pattern:**
Frame extraction uses filter_complex to extract all scenes in one pass:
```bash
ffmpeg -i input.mp4 -filter_complex "[0:v]scale=W:H,split=N[v0][v1]...[vN-1];[v0]select='between(n,start0,end0)'[o0];[v1]select='between(n,start1,end1)'[o1];..." -map [o0] scene0/frame_%04d.jpg -map [o1] scene1/frame_%04d.jpg ...
```
This extracts all scenes simultaneously in a single decode pass, eliminating I/O contention.

**Error Suppression:**
OpenCV h264 warnings are suppressed via FilteredStderr context manager to reduce log noise.

## Data Flow

Input: `data/urls.txt` (one URL per line)
↓
Download: `data/raw/{video_id}.mp4`
↓
Process: Validation → Scene Detection → Motion Analysis & Stabilization (optional) → Frame Extraction
↓
Output:
- Frames: `data/processed/{video_name}/scene_{N}/frame_{M}.jpg`
- Motion CSV: `data/processed/{video_name}/scenes.csv` (if --analyze-motion enabled)
- Metadata: `data/manifest.json`

## Performance Considerations

- FFmpeg frame extraction is 5-10x faster than OpenCV per-frame reading
- **Single-pass extraction**: All scenes extracted in one FFmpeg call using filter_complex (no I/O contention, no re-decoding)
- **GPU acceleration (NVDEC/CUDA)**: 3-5x additional speedup for frame extraction via FFmpeg hardware decoding and scaling
  - Automatically enabled by default (`use_gpu: true` in config.yaml)
  - Robust fallback: If GPU run fails for ANY reason (format errors, device issues, etc.), automatically retries with CPU
  - No frames lost: CPU fallback ensures frames are always extracted even if GPU fails
  - Verify GPU usage: Check FFmpeg logs for "hwaccel cuda" and "scale_cuda" messages, or "GPU run failed" for fallback
- Parallel downloads limited by network bandwidth, not CPU
- Scene detection is CPU-bound; downscale_factor trades accuracy for speed
- Default JPEG quality reduced from 95→75 for imperceptible quality loss but faster encoding
- **Motion analysis optimization**: Uses 360p downscaling for 4-10x speedup with negligible accuracy impact
- **Stabilization overhead**: Requires two additional FFmpeg passes (detection + transformation) per video
- **Median aggregation**: Using median of local motion vectors is robust to moving objects (outliers) in scene

### Processing Time Estimates (1-hour video, ~75 scenes)

| Stage | Time (CPU) | Time (GPU) |
|-------|-----------|-----------|
| Download | 5-10 min | 5-10 min |
| Validation (skip recommended) | 2-4 min | 2-4 min |
| Scene Detection | 20-40 sec | 20-40 sec |
| Motion Analysis (if enabled) | 15-30 sec | 15-30 sec |
| Stabilization (if enabled) | 1-3 min | 1-3 min |
| Post-Stabilization Analysis (if enabled) | 15-30 sec | 15-30 sec |
| Frame Extraction | 3-6 min | 45-90 sec |
| **Total (skip validation, no motion)** | **9-12 min** | **2-3 min** |
| **Total (skip validation, motion + stabilization)** | **12-17 min** | **4-8 min** |

## Testing

No test suite currently exists. Manual testing via:
```bash
# Test with single video
echo "https://youtube.com/watch?v=VIDEOID" > test_urls.txt
python scripts/process_videos.py -u test_urls.txt --output-dir /tmp/test
```
