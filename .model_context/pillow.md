# Pillow (PIL) Model Context File - Image Saving Focus

## Overview
Pillow (PIL Fork) is the Python Imaging Library that adds image processing capabilities to Python. This context focuses on image saving, format conversion, and quality control.

**Primary Use Case**: Save images with control over format, quality, and compression.

**Official Site**: https://python-pillow.org  
**Documentation**: https://pillow.readthedocs.io/  
**PyPI**: https://pypi.org/project/Pillow/  
**License**: HPND (Historical Permission Notice and Disclaimer)

---

## Installation

```bash
# Install Pillow
pip install Pillow

# Upgrade to latest
pip install -U Pillow
```

**Version**: Pillow 10.0+ (as of 2023+)

---

## Basic Image Operations

### Opening and Saving Images

```python
from PIL import Image

# Open image
img = Image.open('input.jpg')

# Save image (default quality)
img.save('output.jpg')

# Save with format specification
img.save('output.png', 'PNG')

# Close (optional, auto-closes with context manager)
img.close()
```

### Using Context Manager (Recommended)

```python
from PIL import Image

with Image.open('input.jpg') as img:
    img.save('output.jpg')
    # Auto-closes when exiting with block
```

---

## JPEG Saving with Quality Control

### Quality Parameter

```python
from PIL import Image

img = Image.open('input.jpg')

# Save with specific quality (1-100)
# Higher = better quality, larger file
# Default is 75

# Low quality (small file)
img.save('low_quality.jpg', quality=50)

# Medium quality (default)
img.save('medium_quality.jpg', quality=75)

# High quality (recommended max)
img.save('high_quality.jpg', quality=95)

# Maximum quality (not recommended, large files)
img.save('max_quality.jpg', quality=100)
```

**Recommended Quality Values**:
- `quality=85`: Good balance (default for many applications)
- `quality=95`: High quality, recommended maximum
- `quality=75`: Default PIL value
- `quality>95`: Avoid - minimal quality gain, large files
- `quality=100`: Disables some JPEG compression, very large files

### Subsampling Control

JPEG uses chroma subsampling which can reduce quality on red/colored edges.

```python
from PIL import Image

img = Image.open('input.jpg')

# Disable subsampling for best quality
img.save('best_quality.jpg', quality=95, subsampling=0)

# Default subsampling (4:2:0)
img.save('default.jpg', quality=95, subsampling='4:2:0')

# Options:
# subsampling=0 or '4:4:4': No subsampling (best quality)
# subsampling=1 or '4:2:2': Horizontal subsampling
# subsampling=2 or '4:2:0': Both directions (default)
```

**Important**: Setting `subsampling=0` significantly improves edge sharpness at cost of ~20% larger files.

### Optimize Flag

```python
from PIL import Image

img = Image.open('input.jpg')

# Enable optimization (slower save, smaller file)
img.save('optimized.jpg', quality=85, optimize=True)

# Optimization performs multiple compression passes
# Typical savings: 5-10% smaller files
# Recommended for production use
```

### Progressive JPEG

```python
from PIL import Image

img = Image.open('input.jpg')

# Save as progressive JPEG (better for web)
img.save('progressive.jpg', quality=85, progressive=True)
```

### Quality Presets

Pillow provides named quality presets:

```python
from PIL import Image

img = Image.open('input.jpg')

# Named presets
img.save('web_low.jpg', quality='web_low')      # ~20
img.save('web_medium.jpg', quality='web_medium')  # ~40
img.save('web_high.jpg', quality='web_high')     # ~60
img.save('web_vhigh.jpg', quality='web_very_high')  # ~80
img.save('web_max.jpg', quality='web_maximum')   # ~94
img.save('low.jpg', quality='low')               # ~25
img.save('medium.jpg', quality='medium')         # ~50
img.save('high.jpg', quality='high')             # ~75
img.save('max.jpg', quality='maximum')           # ~95
```

### Keep Original Quality

```python
from PIL import Image

# When opening JPEG, preserve original quality settings
img = Image.open('input.jpg')

# Save with original quality, subsampling, and qtables
img.save('output.jpg', quality='keep')

# Only works for JPEG files
# Preserves exact compression parameters
```

---

## PNG Saving with Compression

```python
from PIL import Image

img = Image.open('input.png')

# PNG compression: 0-9
# 0 = no compression (fast, large file)
# 9 = maximum compression (slow, small file)

# No compression (fastest)
img.save('fast.png', compress_level=0)

# Default compression
img.save('default.png', compress_level=6)

# Maximum compression (smallest file)
img.save('compressed.png', compress_level=9)

# PNG is lossless - quality always perfect
# Compression only affects file size and save time
```

---

## Image Format Conversion

### Convert Between Formats

```python
from PIL import Image

# JPEG to PNG
img = Image.open('input.jpg')
img.save('output.png', 'PNG')

# PNG to JPEG
img = Image.open('input.png')
# Convert to RGB (JPEG doesn't support transparency)
if img.mode in ('RGBA', 'LA', 'P'):
    img = img.convert('RGB')
img.save('output.jpg', 'JPEG', quality=85)

# Any format to any format
img = Image.open('input.webp')
img.save('output.jpg', 'JPEG', quality=85)
```

### Format Detection

```python
from PIL import Image

img = Image.open('image.jpg')

# Get format information
print(f"Format: {img.format}")        # 'JPEG'
print(f"Mode: {img.mode}")            # 'RGB'
print(f"Size: {img.size}")            # (width, height)
print(f"Width: {img.width}")
print(f"Height: {img.height}")
```

---

## Working with NumPy Arrays

### NumPy to PIL

```python
from PIL import Image
import numpy as np

# Create numpy array (e.g., from OpenCV)
# OpenCV uses BGR, shape: (height, width, 3)
cv_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

# Convert BGR to RGB for PIL
rgb_frame = cv_frame[:, :, ::-1]  # Reverse channel order

# Create PIL Image
pil_img = Image.fromarray(rgb_frame)

# Save with PIL
pil_img.save('output.jpg', quality=85, optimize=True)
```

### PIL to NumPy

```python
from PIL import Image
import numpy as np

img = Image.open('input.jpg')

# Convert to numpy array
arr = np.array(img)

# Array properties
print(f"Shape: {arr.shape}")      # (height, width, 3)
print(f"Dtype: {arr.dtype}")      # uint8
print(f"Color order: RGB")        # PIL uses RGB
```

### Complete OpenCV to PIL Pipeline

```python
import cv2
from PIL import Image
import numpy as np

# Read with OpenCV (BGR format)
cv_frame = cv2.imread('input.jpg')

# Method 1: Convert BGR to RGB, then to PIL
rgb_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(rgb_frame)

# Method 2: Reverse channels with numpy
rgb_frame = cv_frame[:, :, ::-1]
pil_img = Image.fromarray(rgb_frame)

# Save with PIL quality control
pil_img.save('output.jpg', 'JPEG', quality=85, optimize=True)
```

---

## Image Resizing

### Basic Resize

```python
from PIL import Image

img = Image.open('input.jpg')

# Resize to specific dimensions
resized = img.resize((640, 480))  # (width, height)

# Save
resized.save('resized.jpg', quality=85)
```

### Resize with Resampling Filter

```python
from PIL import Image

img = Image.open('input.jpg')

# Resampling filters (quality, from best to worst):
# Image.LANCZOS - Best quality, slowest (recommended for downscaling)
# Image.BICUBIC - Good quality
# Image.BILINEAR - Decent quality, faster
# Image.BOX - Good for downscaling
# Image.NEAREST - Fastest, lowest quality

# Best quality resize
resized = img.resize((640, 480), Image.LANCZOS)

# Fast resize
resized = img.resize((640, 480), Image.NEAREST)

resized.save('resized.jpg', quality=85)
```

### Thumbnail (Maintains Aspect Ratio)

```python
from PIL import Image

img = Image.open('input.jpg')

# Create thumbnail (maintains aspect ratio, fits within box)
max_size = (640, 480)
img.thumbnail(max_size, Image.LANCZOS)

# Note: img is modified in-place
img.save('thumbnail.jpg', quality=85)

# Or create copy first
img = Image.open('input.jpg')
img_copy = img.copy()
img_copy.thumbnail((640, 480), Image.LANCZOS)
img_copy.save('thumbnail.jpg', quality=85)
```

### Aspect Ratio Preservation

```python
from PIL import Image

def resize_with_aspect_ratio(img, target_width=None, target_height=None):
    """Resize maintaining aspect ratio"""
    width, height = img.size
    
    if target_width and not target_height:
        # Calculate height
        aspect_ratio = height / width
        target_height = int(target_width * aspect_ratio)
    elif target_height and not target_width:
        # Calculate width
        aspect_ratio = width / height
        target_width = int(target_height * aspect_ratio)
    
    return img.resize((target_width, target_height), Image.LANCZOS)

# Usage
img = Image.open('input.jpg')
resized = resize_with_aspect_ratio(img, target_width=640)
resized.save('resized.jpg', quality=85)
```

---

## Image Modes and Color Conversion

### Understanding Image Modes

- `'RGB'` - 3 channels (Red, Green, Blue), 8-bit per channel
- `'RGBA'` - 4 channels (RGB + Alpha transparency)
- `'L'` - Grayscale, single 8-bit channel
- `'P'` - Palette mode (indexed color)
- `'CMYK'` - 4 channels (Cyan, Magenta, Yellow, Key/Black)

### Convert Between Modes

```python
from PIL import Image

img = Image.open('input.png')  # May be RGBA

# Convert to RGB (removes transparency)
rgb_img = img.convert('RGB')
rgb_img.save('output.jpg', quality=85)

# Convert to grayscale
gray_img = img.convert('L')
gray_img.save('grayscale.jpg', quality=85)

# Check mode before conversion
if img.mode in ('RGBA', 'LA', 'P'):
    img = img.convert('RGB')
img.save('output.jpg', quality=85)
```

---

## Practical Patterns for Your Project

### Pattern 1: Save OpenCV Frame with PIL

```python
import cv2
from PIL import Image

def save_frame_with_pil(cv_frame, output_path, quality=85, optimize=True):
    """
    Save OpenCV frame using PIL for better quality control.
    
    Args:
        cv_frame: numpy array from cv2.read() (BGR format)
        output_path: Output file path
        quality: JPEG quality (1-100)
        optimize: Enable JPEG optimization
    """
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
    
    # Create PIL Image
    pil_img = Image.fromarray(rgb_frame)
    
    # Save with quality control
    pil_img.save(
        output_path,
        'JPEG',
        quality=quality,
        optimize=optimize,
        subsampling=0  # Best quality
    )
```

### Pattern 2: Resize and Save

```python
import cv2
from PIL import Image

def save_resized_frame(cv_frame, output_path, target_size=(640, 480), quality=85):
    """
    Resize OpenCV frame and save with PIL.
    
    Args:
        cv_frame: numpy array from cv2.read()
        output_path: Output path
        target_size: (width, height) tuple
        quality: JPEG quality
    """
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
    
    # Create PIL Image
    pil_img = Image.fromarray(rgb_frame)
    
    # Resize
    resized = pil_img.resize(target_size, Image.LANCZOS)
    
    # Save
    resized.save(output_path, 'JPEG', quality=quality, optimize=True)
```

### Pattern 3: Batch Frame Saving

```python
import cv2
from PIL import Image
from pathlib import Path

def save_frames_batch(frames, output_dir, quality=85):
    """
    Save multiple OpenCV frames efficiently.
    
    Args:
        frames: List of (frame, filename) tuples
        output_dir: Output directory
        quality: JPEG quality
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for cv_frame, filename in frames:
        # Convert to RGB
        rgb_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        
        # Create and save
        pil_img = Image.fromarray(rgb_frame)
        output_path = output_dir / filename
        pil_img.save(
            str(output_path),
            'JPEG',
            quality=quality,
            optimize=True
        )
```

---

## Error Handling

```python
from PIL import Image
from PIL import UnidentifiedImageError
import os

def safe_save_image(img, output_path, quality=85):
    """Save image with error handling"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert mode if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Save
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        return True
        
    except UnidentifiedImageError:
        print(f"Cannot identify image format")
        return False
        
    except OSError as e:
        print(f"Cannot save image: {e}")
        return False
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
```

---

## Performance Considerations

### Save Speed vs. Quality

```python
from PIL import Image

img = Image.open('input.jpg')

# Fast save (no optimization)
img.save('fast.jpg', quality=85, optimize=False)

# Optimized save (slower, smaller file)
img.save('optimized.jpg', quality=85, optimize=True)

# Quality vs. Speed tradeoff:
# optimize=False: Faster save, 5-10% larger files
# optimize=True: Slower save, 5-10% smaller files
# Recommended: Use optimize=True for production
```

### Batch Operations

```python
from PIL import Image

# More efficient: Reuse image object
with Image.open('input.jpg') as img:
    img.save('output1.jpg', quality=85)
    img.save('output2.jpg', quality=95)
    # img auto-closes at end of with block

# Less efficient: Open multiple times
Image.open('input.jpg').save('output1.jpg', quality=85)
Image.open('input.jpg').save('output2.jpg', quality=95)
```

---

## File Size Comparison

Typical file sizes for 1920x1080 image:

**JPEG**:
- quality=50: ~200 KB
- quality=75: ~400 KB (default)
- quality=85: ~600 KB (recommended)
- quality=95: ~1.2 MB (high quality)
- quality=100: ~3 MB (not recommended)

**PNG**:
- compress_level=0: ~6 MB (lossless)
- compress_level=6: ~2 MB (lossless, default)
- compress_level=9: ~1.8 MB (lossless, max compression)

**For your project**: Use JPEG quality=85 with optimize=True for best balance.

---

## Integration with Your Video Processor

```python
import cv2
from PIL import Image
from pathlib import Path

class FrameSaver:
    """Helper class for saving video frames with PIL"""
    
    def __init__(self, quality=85, optimize=True, resize=None):
        """
        Args:
            quality: JPEG quality (1-100)
            optimize: Enable optimization
            resize: Target size as (width, height) or None
        """
        self.quality = quality
        self.optimize = optimize
        self.resize = resize
    
    def save_frame(self, cv_frame, output_path):
        """Save single OpenCV frame"""
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        
        # Create PIL Image
        pil_img = Image.fromarray(rgb_frame)
        
        # Resize if needed
        if self.resize is not None:
            pil_img = pil_img.resize(self.resize, Image.LANCZOS)
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save
        pil_img.save(
            str(output_path),
            'JPEG',
            quality=self.quality,
            optimize=self.optimize
        )

# Usage
saver = FrameSaver(quality=85, optimize=True, resize=(640, 480))

cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

if ret:
    saver.save_frame(frame, 'output/frame_001.jpg')

cap.release()
```

---

## Common Issues and Solutions

### Issue: "cannot write mode RGBA as JPEG"

**Cause**: JPEG doesn't support transparency  
**Solution**: Convert to RGB first
```python
if img.mode in ('RGBA', 'LA'):
    img = img.convert('RGB')
img.save('output.jpg')
```

### Issue: File size larger than expected

**Cause**: Not using optimization or subsampling  
**Solution**: Enable optimize and set subsampling
```python
img.save('output.jpg', quality=85, optimize=True, subsampling=0)
```

### Issue: Poor quality on colored edges

**Cause**: Chroma subsampling  
**Solution**: Set subsampling=0
```python
img.save('output.jpg', quality=95, subsampling=0)
```

---

## Summary for AI Agents

**Key Takeaways**:
1. Install with `pip install Pillow`
2. Open with `Image.open(path)`, save with `img.save(path, quality=85)`
3. JPEG quality: 85 is recommended (1-100 scale, 95 is max recommended)
4. Enable optimization: `optimize=True` (5-10% smaller files)
5. Disable subsampling for best quality: `subsampling=0`
6. Convert OpenCV (BGR) to PIL: `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)`
7. Create from numpy: `Image.fromarray(rgb_array)`
8. Resize with `img.resize((width, height), Image.LANCZOS)`
9. Thumbnail (aspect ratio): `img.thumbnail(max_size, Image.LANCZOS)`
10. Convert RGBA to RGB for JPEG: `img.convert('RGB')`
11. PNG is lossless, use `compress_level=9` for smallest file
12. Use context manager: `with Image.open(path) as img:`
13. Quality='keep' preserves original JPEG parameters
