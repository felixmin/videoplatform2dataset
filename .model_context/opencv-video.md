# OpenCV (cv2) Model Context File - Video Processing Focus

## Overview
OpenCV (Open Source Computer Vision Library) is a comprehensive computer vision and image processing library. This context focuses on video frame extraction functionality.

**Primary Use Case**: Read videos, extract frames, manipulate video properties, and process video data.

**Official Site**: https://opencv.org  
**Documentation**: https://docs.opencv.org/  
**PyPI**: https://pypi.org/project/opencv-python/  
**License**: Apache 2.0

---

## Installation

```bash
# Main package (no GUI support)
pip install opencv-python

# Full package (with GUI and contrib modules)
pip install opencv-contrib-python

# Headless (for servers, no GUI)
pip install opencv-python-headless
```

**For this project**: Use `opencv-python` (main package is sufficient for video frame extraction).

---

## Video Reading Basics

### Opening a Video

```python
import cv2

# Open video file
cap = cv2.VideoCapture('video.mp4')

# Check if opened successfully
if not cap.isOpened():
    print("Error opening video")
    exit()

# Always release when done
cap.release()
```

### Video Properties

```python
import cv2

cap = cv2.VideoCapture('video.mp4')

# Get video properties
fps = cap.get(cv2.CAP_PROP_FPS)                      # Frames per second
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # Total frame count
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))       # Frame width
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))     # Frame height
codec = int(cap.get(cv2.CAP_PROP_FOURCC))            # Codec (FourCC code)

print(f"FPS: {fps}")
print(f"Total Frames: {total_frames}")
print(f"Resolution: {width}x{height}")

cap.release()
```

Common video properties (use with `cap.get()`):
- `cv2.CAP_PROP_FPS` - Frame rate
- `cv2.CAP_PROP_FRAME_COUNT` - Total frames
- `cv2.CAP_PROP_FRAME_WIDTH` - Frame width
- `cv2.CAP_PROP_FRAME_HEIGHT` - Frame height
- `cv2.CAP_PROP_POS_FRAMES` - Current frame position (0-indexed)
- `cv2.CAP_PROP_POS_MSEC` - Current position in milliseconds
- `cv2.CAP_PROP_FOURCC` - 4-character codec code

---

## Frame Extraction

### Basic Frame-by-Frame Reading

```python
import cv2

cap = cv2.VideoCapture('video.mp4')
frame_count = 0

while True:
    # Read next frame
    ret, frame = cap.read()
    
    # ret is True if frame read successfully
    # frame is numpy array (BGR format)
    if not ret:
        break  # End of video
    
    # Process frame here
    print(f"Frame {frame_count}: shape {frame.shape}")
    frame_count += 1

cap.release()
print(f"Total frames processed: {frame_count}")
```

### Extract All Frames to Images

```python
import cv2
import os

def extract_all_frames(video_path, output_dir):
    """Extract all frames from video and save as images"""
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error opening video: {video_path}")
        return 0
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Save frame
        output_path = os.path.join(output_dir, f'frame_{frame_count:05d}.jpg')
        cv2.imwrite(output_path, frame)
        
        frame_count += 1
    
    cap.release()
    return frame_count

# Usage
num_frames = extract_all_frames('video.mp4', 'frames/')
print(f"Extracted {num_frames} frames")
```

### Extract Frames from Specific Range

```python
import cv2
import os

def extract_frame_range(video_path, start_frame, end_frame, output_dir):
    """Extract frames from start_frame to end_frame"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    
    # Seek to start frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    frame_idx = start_frame
    extracted = 0
    
    while frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        
        output_path = os.path.join(output_dir, f'frame_{extracted:05d}.jpg')
        cv2.imwrite(output_path, frame)
        
        frame_idx += 1
        extracted += 1
    
    cap.release()
    return extracted
```

### Extract Every Nth Frame

```python
import cv2
import os

def extract_every_nth_frame(video_path, n, output_dir):
    """Extract every Nth frame (e.g., n=30 extracts 1 frame per second at 30fps)"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    
    frame_count = 0
    extracted = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Extract every nth frame
        if frame_count % n == 0:
            output_path = os.path.join(output_dir, f'frame_{extracted:05d}.jpg')
            cv2.imwrite(output_path, frame)
            extracted += 1
        
        frame_count += 1
    
    cap.release()
    return extracted

# Extract 1 frame per second from 30fps video
extracted = extract_every_nth_frame('video.mp4', 30, 'frames/')
```

---

## Image Saving with Quality Control

### JPEG with Quality Parameter

```python
import cv2

# Read frame
cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    # Save with different quality levels
    # Quality: 0-100, where 95 is recommended max, 85 is default
    
    # High quality
    cv2.imwrite('frame_high.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    # Medium quality (default)
    cv2.imwrite('frame_medium.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    
    # Low quality (smaller file)
    cv2.imwrite('frame_low.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
    
    # Simple save (uses default quality 95)
    cv2.imwrite('frame_default.jpg', frame)

cap.release()
```

### PNG with Compression

```python
import cv2

ret, frame = cap.read()

if ret:
    # PNG compression: 0-9, where 0 = no compression, 9 = max compression
    cv2.imwrite('frame.png', frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
```

---

## Frame Resizing

### Resize Frame

```python
import cv2

cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    # Resize to specific dimensions
    resized = cv2.resize(frame, (640, 480))  # (width, height)
    
    # Resize by scale factor
    scale_factor = 0.5
    width = int(frame.shape[1] * scale_factor)
    height = int(frame.shape[0] * scale_factor)
    resized = cv2.resize(frame, (width, height))
    
    # Resize with interpolation method
    resized = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_AREA)
    
    cv2.imwrite('resized_frame.jpg', resized)

cap.release()
```

**Interpolation methods**:
- `cv2.INTER_LINEAR` - Bilinear (default, good for enlarging)
- `cv2.INTER_AREA` - Area-based (best for shrinking)
- `cv2.INTER_CUBIC` - Bicubic (slower, higher quality)
- `cv2.INTER_NEAREST` - Nearest neighbor (fastest, lowest quality)

### Maintain Aspect Ratio

```python
import cv2

def resize_with_aspect_ratio(frame, target_width=None, target_height=None):
    """Resize frame while maintaining aspect ratio"""
    height, width = frame.shape[:2]
    
    if target_width is not None:
        # Calculate height to maintain aspect ratio
        aspect_ratio = height / width
        new_height = int(target_width * aspect_ratio)
        return cv2.resize(frame, (target_width, new_height), interpolation=cv2.INTER_AREA)
    
    elif target_height is not None:
        # Calculate width to maintain aspect ratio
        aspect_ratio = width / height
        new_width = int(target_height * aspect_ratio)
        return cv2.resize(frame, (new_width, target_height), interpolation=cv2.INTER_AREA)
    
    return frame

# Usage
cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    resized = resize_with_aspect_ratio(frame, target_width=640)
    cv2.imwrite('resized.jpg', resized)

cap.release()
```

---

## Seeking in Videos

### Seek to Specific Frame

```python
import cv2

cap = cv2.VideoCapture('video.mp4')

# Seek to frame 100
cap.set(cv2.CAP_PROP_POS_FRAMES, 100)

# Read that frame
ret, frame = cap.read()

if ret:
    cv2.imwrite('frame_100.jpg', frame)

cap.release()
```

### Seek to Specific Time

```python
import cv2

cap = cv2.VideoCapture('video.mp4')

# Seek to 30 seconds (30000 milliseconds)
cap.set(cv2.CAP_PROP_POS_MSEC, 30000)

ret, frame = cap.read()

if ret:
    cv2.imwrite('frame_at_30s.jpg', frame)

cap.release()
```

---

## Pattern for Your Project

### Extract Frames from Scene Boundaries

```python
import cv2
import os
from pathlib import Path

def extract_scene_frames(
    video_path,
    scene_boundaries,
    output_dir,
    resolution=None,
    jpeg_quality=85
):
    """
    Extract frames from video based on scene boundaries.
    
    Args:
        video_path: Path to video file
        scene_boundaries: List of (start_frame, end_frame) tuples
        output_dir: Output directory
        resolution: Target resolution as (width, height) or None
        jpeg_quality: JPEG quality (1-100)
    
    Returns:
        Total number of frames extracted
    """
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    # Get original resolution
    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    total_extracted = 0
    
    for scene_idx, (start_frame, end_frame) in enumerate(scene_boundaries):
        # Create scene directory
        scene_dir = Path(output_dir) / f'scene_{scene_idx:03d}'
        scene_dir.mkdir(parents=True, exist_ok=True)
        
        # Seek to start frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        frame_idx = start_frame
        scene_frame_count = 0
        
        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Resize if needed
            if resolution is not None:
                frame = cv2.resize(
                    frame,
                    resolution,
                    interpolation=cv2.INTER_AREA
                )
            
            # Save frame
            output_path = scene_dir / f'frame_{scene_frame_count:04d}.jpg'
            cv2.imwrite(
                str(output_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
            )
            
            frame_idx += 1
            scene_frame_count += 1
            total_extracted += 1
        
        print(f"Scene {scene_idx}: Extracted {scene_frame_count} frames")
    
    cap.release()
    return total_extracted

# Usage
scene_boundaries = [
    (0, 100),      # Scene 1: frames 0-100
    (100, 250),    # Scene 2: frames 100-250
    (250, 500),    # Scene 3: frames 250-500
]

total = extract_scene_frames(
    'video.mp4',
    scene_boundaries,
    'output/frames',
    resolution=(640, 480),
    jpeg_quality=85
)

print(f"Total frames extracted: {total}")
```

---

## Frame Format and Color Spaces

### Understanding Frame Format

```python
import cv2
import numpy as np

cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    # Frame is numpy array
    print(f"Type: {type(frame)}")           # <class 'numpy.ndarray'>
    print(f"Shape: {frame.shape}")          # (height, width, 3)
    print(f"Data type: {frame.dtype}")      # uint8
    print(f"Color order: BGR")              # OpenCV uses BGR, not RGB!
    
    # Access pixel
    height, width, channels = frame.shape
    pixel = frame[100, 200]  # pixel at row 100, col 200
    b, g, r = pixel          # Blue, Green, Red values (0-255)

cap.release()
```

### Convert Color Spaces

```python
import cv2

cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    # BGR to RGB (for libraries like PIL/Pillow)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # BGR to Grayscale
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # BGR to HSV
    frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Save grayscale
    cv2.imwrite('frame_gray.jpg', frame_gray)

cap.release()
```

---

## Error Handling

```python
import cv2

def safe_video_read(video_path):
    """Read video with error handling"""
    
    cap = cv2.VideoCapture(video_path)
    
    # Check if opened
    if not cap.isOpened():
        raise IOError(f"Cannot open video file: {video_path}")
    
    try:
        # Get properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if fps == 0 or total_frames == 0:
            raise ValueError(f"Invalid video properties: {video_path}")
        
        # Read frames
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame
            frame_count += 1
        
        return frame_count
        
    finally:
        # Always release
        cap.release()
```

---

## Performance Tips

1. **Use `cv2.INTER_AREA` for downscaling** - Best quality for shrinking images
2. **JPEG quality 85 is good default** - Balance between file size and quality
3. **Read frames sequentially** - Seeking is slow, sequential reading is fast
4. **Release VideoCapture** - Always call `cap.release()` when done
5. **Batch save operations** - Reduce I/O overhead by processing multiple frames

---

## Integration with PIL/Pillow

```python
import cv2
from PIL import Image

cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    # OpenCV (BGR) to PIL (RGB)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(frame_rgb)
    
    # Save with PIL (better JPEG control)
    pil_image.save('frame.jpg', 'JPEG', quality=85, optimize=True)
    
    # PIL to OpenCV
    import numpy as np
    frame_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

cap.release()
```

---

## Common Issues and Solutions

### Issue: `cap.read()` returns `ret=False` immediately

**Cause**: Video codec not supported, or file corrupted  
**Solution**: Install ffmpeg, or convert video to supported format

### Issue: `cap.get(cv2.CAP_PROP_FRAME_COUNT)` returns 0

**Cause**: Some video formats don't expose frame count  
**Solution**: Count frames manually or use duration * fps as estimate

### Issue: Seeking to specific frame is slow

**Cause**: Video codec requires sequential decoding  
**Solution**: Use sequential reading when extracting multiple frames

### Issue: Colors look wrong in saved images

**Cause**: OpenCV uses BGR, other libraries use RGB  
**Solution**: Convert color space before saving with non-OpenCV libraries

---

## Summary for AI Agents

**Key Takeaways**:
1. Use `cv2.VideoCapture(path)` to open videos
2. `cap.read()` returns `(ret, frame)` where frame is numpy array (BGR format)
3. Get properties with `cap.get(cv2.CAP_PROP_*)` constants
4. Seek with `cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)`
5. Resize with `cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)`
6. Save with `cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])`
7. Always call `cap.release()` when done
8. Frame shape is `(height, width, channels)` where channels=3 (BGR)
9. Use `cv2.INTER_AREA` for downscaling (best quality)
10. Sequential frame reading is much faster than seeking
11. OpenCV frames are BGR format, not RGB (convert if needed)
