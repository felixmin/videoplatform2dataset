# PySceneDetect Model Context File

## Overview
PySceneDetect (version 0.6.7, latest as of August 2025) is a Python library and command-line tool for detecting scene changes (shot boundaries) in videos. It provides multiple detection algorithms optimized for performance and accuracy.

**Primary Use Case**: Automatically detect scene transitions in videos and split them into separate clips or extract scene boundaries.

**GitHub**: https://github.com/Breakthrough/PySceneDetect  
**Documentation**: https://www.scenedetect.com  
**PyPI**: https://pypi.org/project/scenedetect/  
**License**: BSD-3-Clause

---

## Installation

```bash
# Basic installation
pip install scenedetect

# With OpenCV support (recommended)
pip install scenedetect[opencv]

# Latest development version
pip install scenedetect[opencv] --upgrade --pre
```

**Dependencies**:
- Python 3.10+ (CPython) or 3.11+ (PyPy)
- OpenCV (`cv2`) - for video decoding
- NumPy - for frame processing
- Optional: ffmpeg/mkvmerge for video splitting

---

## Quick Start Examples

### Simple Scene Detection (High-Level API)

```python
from scenedetect import detect, ContentDetector

# Detect scenes in a video
scene_list = detect('my_video.mp4', ContentDetector())

# scene_list is a list of (start, end) FrameTimecode tuples
for i, scene in enumerate(scene_list):
    print(f'Scene {i+1}: Start {scene[0].get_timecode()} / Frame {scene[0].get_frames()}, '
          f'End {scene[1].get_timecode()} / Frame {scene[1].get_frames()}')
```

### Advanced Scene Detection (SceneManager API)

```python
from scenedetect import open_video, SceneManager, ContentDetector

def find_scenes(video_path, threshold=27.0):
    # Open video
    video = open_video(video_path)
    
    # Create scene manager
    scene_manager = SceneManager()
    
    # Add detector
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    
    # Detect all scenes from current position to end
    scene_manager.detect_scenes(video, show_progress=True)
    
    # Get scene list as (start, end) timecode pairs
    return scene_manager.get_scene_list()

scenes = find_scenes('video.mp4')
```

### With Scene Callback

```python
from scenedetect import open_video, SceneManager, AdaptiveDetector
import numpy as np

def on_new_scene(frame_img: np.ndarray, frame_num: int):
    """Called on the first frame of every new scene"""
    print(f"New scene found at frame {frame_num}")
    # Process frame_img as needed

video = open_video('video.mp4')
scene_manager = SceneManager()
scene_manager.add_detector(AdaptiveDetector())
scene_manager.detect_scenes(video=video, callback=on_new_scene)
```

---

## Detection Algorithms

PySceneDetect provides 5 built-in detection algorithms. Each has specific use cases:

### 1. ContentDetector (Fast Cuts)
**Best for**: Most common use case - detecting hard cuts between scenes  
**How it works**: Converts frames to HSV color space and compares average difference across channels

```python
from scenedetect.detectors import ContentDetector

detector = ContentDetector(
    threshold=27.0,           # Threshold for scene change (lower = more sensitive)
    min_scene_len=15,         # Minimum scene length in frames
    weights=(1.0, 1.0, 1.0, 0.0),  # Weights for (hue, sat, lum, edges)
    luma_only=False,          # Use only luminance channel
    kernel_size=None          # Kernel size for edge detection (if enabled)
)
```

**Default threshold**: 27.0 (good starting point)  
**Lower threshold** (20-25): More sensitive, detects subtle changes  
**Higher threshold** (30-35): Less sensitive, only major scene changes

**Edge detection**: Set `weights=(1.0, 0.5, 1.0, 0.2)` and increase threshold to ~32

### 2. AdaptiveDetector (Handles Camera Motion)
**Best for**: Videos with fast camera movement, action scenes  
**How it works**: Uses rolling average of adjacent frame changes to avoid false positives from camera motion

```python
from scenedetect.detectors import AdaptiveDetector

detector = AdaptiveDetector(
    adaptive_threshold=3.0,   # Threshold for rolling average ratio
    min_scene_len=15,         # Minimum scene length
    window_width=2,           # Rolling average window size
    min_content_val=15.0,     # Minimum content change to consider
    weights=(1.0, 1.0, 1.0, 0.0),  # Same as ContentDetector
    luma_only=False,
    kernel_size=None
)
```

**Recommended detector** for most use cases requiring robustness.

### 3. ThresholdDetector (Fades In/Out)
**Best for**: Detecting fades to/from black, scene transitions  
**How it works**: Triggers when average pixel intensity crosses a threshold

```python
from scenedetect.detectors import ThresholdDetector

detector = ThresholdDetector(
    threshold=12.0,           # Pixel intensity threshold (0-255)
    min_scene_len=15,         # Minimum scene length
    fade_bias=0.0,            # Bias towards detecting fade in/out
    add_final_scene=True,     # Add final scene at end of video
    method='average'          # 'average' or other methods
)
```

**Typical threshold**: 12.0 for detecting black frames

### 4. HistogramDetector (Lighting Changes)
**Best for**: Videos with lighting variations  
**How it works**: Compares Y channel histograms in YCbCr color space

```python
from scenedetect.detectors import HistogramDetector

detector = HistogramDetector(
    threshold=0.05,           # Histogram correlation threshold
    bins=256,                 # Number of histogram bins
    min_scene_len=15
)
```

### 5. HashDetector (Perceptual Hashing)
**Best for**: Very fast detection, computationally efficient  
**How it works**: Uses perceptual hashing (phash) to detect frame differences

```python
from scenedetect.detectors import HashDetector

detector = HashDetector(
    threshold=16,             # Hash difference threshold
    min_scene_len=15,
    lowpass=16                # Lowpass filter size
)
```

**Note**: Converts frames to grayscale, so insensitive to color-only changes.

---

## Core API Components

### 1. open_video() - Video Input

```python
from scenedetect import open_video

# Open video file
video = open_video(
    'video.mp4',
    framerate=None,           # Override video framerate
    backend='opencv'          # Video backend: 'opencv', 'pyav', 'moviepy'
)

# Video properties
print(f"Frame rate: {video.frame_rate}")
print(f"Duration: {video.duration}")
print(f"Resolution: {video.frame_size}")

# Read frames
while True:
    frame = video.read()      # Returns np.ndarray or False at end
    if frame is False:
        break
    # Process frame

# Reset video to beginning
video.reset()

# Seek to specific frame
video.seek(frame_number)
```

### 2. SceneManager - Scene Detection Coordinator

```python
from scenedetect import SceneManager, ContentDetector, AdaptiveDetector

# Create scene manager
scene_manager = SceneManager()

# Add detectors (can add multiple)
scene_manager.add_detector(ContentDetector(threshold=27.0))
scene_manager.add_detector(AdaptiveDetector())  # Multiple detectors combine results

# Detect scenes
scene_manager.detect_scenes(
    video=video,              # VideoStream object
    duration=None,            # Stop after duration (FrameTimecode)
    end_time=None,            # Stop at specific time (FrameTimecode)
    frame_skip=0,             # Skip frames (NOT recommended, use downscale instead)
    show_progress=True,       # Show progress bar
    callback=None,            # Callback function for each scene
)

# Get results
scenes = scene_manager.get_scene_list()  # List of (start, end) tuples
cuts = scene_manager.get_cut_list()      # List of cut frames only

# Clear for reuse
scene_manager.clear()                     # Clear scenes but keep detectors
scene_manager.clear_detectors()           # Remove all detectors
```

### 3. FrameTimecode - Time Representation

```python
from scenedetect import FrameTimecode

# Create timecode
tc = FrameTimecode(timecode='00:01:30.500', fps=24.0)  # From string
tc = FrameTimecode(frames=100, fps=24.0)                # From frame number
tc = FrameTimecode(seconds=15.5, fps=24.0)              # From seconds

# Get values
frame_num = tc.get_frames()       # Frame number
seconds = tc.get_seconds()        # Seconds as float
timecode_str = tc.get_timecode()  # Formatted string "HH:MM:SS.mmm"

# Arithmetic
tc1 + tc2    # Add timecodes
tc1 - tc2    # Subtract timecodes
tc1 < tc2    # Compare timecodes
```

### 4. Scene Splitting with FFmpeg

```python
from scenedetect import detect, ContentDetector, split_video_ffmpeg

# Detect scenes
scene_list = detect('video.mp4', ContentDetector())

# Split video using ffmpeg
split_video_ffmpeg(
    'video.mp4',
    scene_list,
    output_file_template='$VIDEO_NAME-Scene-$SCENE_NUMBER.mp4',
    video_name='my_video',
    show_progress=True,
    show_output=False,
    suppress_output=True,
    hide_progress=False,
    arg_override=None         # Additional ffmpeg arguments
)
```

---

## Performance Optimization

### Downscaling for Speed

PySceneDetect supports downscaling frames before processing for significant speed improvements:

```python
from scenedetect import SceneManager, AdaptiveDetector, open_video

video = open_video('video.mp4')
scene_manager = SceneManager()

detector = AdaptiveDetector(adaptive_threshold=3.0)
scene_manager.add_detector(detector)

# Detect with downscaling
scene_manager.detect_scenes(
    video=video,
    show_progress=True,
    downscale=2              # Process at 1/2 resolution (2x2 = 4x speedup)
)

# Common downscale factors:
# downscale=2  -> 1/2 resolution (4x speedup, minimal accuracy loss)
# downscale=4  -> 1/4 resolution (16x speedup, some accuracy loss)
```

**Benchmark Performance** (1080p video):
- No downscaling: ~40-60 FPS
- 2x downscale: ~140-220 FPS
- 4x downscale: ~300-500 FPS

### Frame Skipping (Not Recommended)

```python
# Skip frames (reduces accuracy significantly)
scene_manager.detect_scenes(
    video=video,
    frame_skip=1             # Process every 2nd frame (skip 1)
)
```

**Note**: Downscaling is strongly preferred over frame skipping for performance.

---

## Statistics and Metrics

### StatsManager for Caching

```python
from scenedetect import SceneManager, ContentDetector, StatsManager

# Create stats manager for caching frame metrics
stats = StatsManager()

scene_manager = SceneManager(stats_manager=stats)
scene_manager.add_detector(ContentDetector())
scene_manager.detect_scenes(video)

# Save stats to CSV for analysis
stats.save_to_csv('video_stats.csv')

# Load stats for faster subsequent runs
stats.load_from_csv('video_stats.csv')
```

The stats file contains per-frame metrics that can be graphed to tune detector parameters.

---

## Creating Custom Detectors

```python
import typing as ty
import numpy as np
from scenedetect import FrameTimecode, SceneDetector

class CustomDetector(SceneDetector):
    """Custom scene detection algorithm"""
    
    def __init__(self, threshold=30.0, min_scene_len=15):
        self.threshold = threshold
        self.min_scene_len = min_scene_len
        self._last_frame = None
        self._last_cut = 0
    
    def process_frame(
        self,
        frame_num: int,
        frame_img: np.ndarray
    ) -> ty.List[int]:
        """
        Process a frame and return list of detected cut frame numbers.
        
        Args:
            frame_num: Current frame number
            frame_img: Current frame as np.ndarray (BGR format from OpenCV)
        
        Returns:
            List of frame numbers where cuts were detected
        """
        cuts = []
        
        if self._last_frame is not None:
            # Compute difference metric
            diff = np.mean(np.abs(frame_img - self._last_frame))
            
            # Check threshold and minimum scene length
            if diff > self.threshold and (frame_num - self._last_cut) >= self.min_scene_len:
                cuts.append(frame_num)
                self._last_cut = frame_num
        
        self._last_frame = frame_img.copy()
        return cuts
    
    def post_process(self, frame_num: int) -> ty.List[int]:
        """
        Called after the last frame. Return any pending cuts.
        
        Args:
            frame_num: Last frame number
        
        Returns:
            List of pending cut frame numbers
        """
        return []
```

---

## Command-Line Interface

PySceneDetect also provides a CLI tool:

```bash
# Basic scene detection
scenedetect -i video.mp4 detect-adaptive

# With specific threshold
scenedetect -i video.mp4 detect-adaptive --threshold 3.0

# Split video
scenedetect -i video.mp4 detect-adaptive split-video

# Save scene list
scenedetect -i video.mp4 detect-content list-scenes

# Extract images from scenes
scenedetect -i video.mp4 detect-adaptive save-images --num-images 3
```

---

## Common Patterns for Your Use Case

### Pattern 1: Extract Scene Boundaries for Frame Processing

```python
from scenedetect import open_video, SceneManager, AdaptiveDetector

def extract_scene_boundaries(video_path, threshold=27.0, downscale=2):
    """
    Extract scene boundaries efficiently.
    
    Returns:
        List of (start_frame, end_frame) tuples
    """
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(AdaptiveDetector(adaptive_threshold=threshold))
    
    # Detect with downscaling for speed
    scene_manager.detect_scenes(video, show_progress=True, downscale=downscale)
    
    # Convert to frame numbers
    scenes = []
    for scene in scene_manager.get_scene_list():
        start_frame = scene[0].get_frames()
        end_frame = scene[1].get_frames()
        scenes.append((start_frame, end_frame))
    
    return scenes
```

### Pattern 2: Optional Scene Detection

```python
def get_video_scenes(video_path, detect_scenes=True, threshold=27.0):
    """
    Get scene boundaries, or treat entire video as one scene.
    """
    if detect_scenes:
        return extract_scene_boundaries(video_path, threshold)
    else:
        # Return entire video as one scene
        import cv2
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return [(0, total_frames)]
```

---

## Important Notes and Best Practices

1. **API Stability**: PySceneDetect API is under development. Pin version to avoid breaking changes:
   ```python
   # requirements.txt
   scenedetect<0.8
   ```

2. **Detector Choice**:
   - Use **AdaptiveDetector** for most cases (handles camera motion)
   - Use **ContentDetector** for simpler/faster detection
   - Use **ThresholdDetector** for fade detection
   - Use **HashDetector** for maximum speed

3. **Performance**: 
   - Always use `downscale` parameter (2-4x) instead of `frame_skip`
   - Downscaling provides better speed/accuracy tradeoff
   - Expected performance: 140-220 FPS on 1080p with 2x downscale

4. **Threshold Tuning**:
   - Start with defaults (27.0 for Content, 3.0 for Adaptive)
   - Lower threshold = more sensitive (more scenes detected)
   - Use StatsManager to save metrics and analyze

5. **Minimum Scene Length**:
   - Default 15 frames prevents micro-scenes from noise
   - Adjust based on video content and desired granularity

6. **Video Backends**:
   - OpenCV (default): Best compatibility
   - PyAV: Better performance for some codecs
   - MoviePy: Simplest but slowest

---

## Error Handling

```python
from scenedetect import open_video, SceneManager, AdaptiveDetector
from scenedetect.video_stream import VideoOpenFailure

try:
    video = open_video('video.mp4')
except VideoOpenFailure as e:
    print(f"Failed to open video: {e}")
    # Handle error

try:
    scene_manager = SceneManager()
    scene_manager.add_detector(AdaptiveDetector())
    scene_manager.detect_scenes(video, show_progress=True)
except KeyboardInterrupt:
    print("Detection interrupted by user")
except Exception as e:
    print(f"Detection failed: {e}")
```

---

## Version Information

- **Current Version**: 0.6.7 (as of August 2025)
- **Python Support**: 3.10+ (CPython), 3.11+ (PyPy)
- **Breaking Changes**: API may change before v1.0, pin version
- **GitHub**: https://github.com/Breakthrough/PySceneDetect
- **Documentation**: https://www.scenedetect.com/docs/

---

## Summary for AI Agents

**Key Takeaways**:
1. Use `detect()` for simple cases, `SceneManager` for advanced workflows
2. **AdaptiveDetector** is the recommended default (handles camera motion)
3. Always use `downscale=2` or `downscale=4` for performance (not `frame_skip`)
4. Returns scene boundaries as `(start, end)` FrameTimecode tuples
5. Convert to frame numbers with `.get_frames()`
6. Very efficient: 140-220 FPS on 1080p video with 2x downscale
7. HSV-based algorithms, not naive pixel comparison
