# Supporting Libraries Model Context File
# PyYAML, argparse, tqdm, pathlib

## Overview
This document covers essential supporting libraries for the video processing project: configuration management (PyYAML), CLI argument parsing (argparse), progress bars (tqdm), and path handling (pathlib).

---

# PyYAML - Configuration File Handling

## Overview
PyYAML is a YAML parser and emitter for Python, used for reading and writing configuration files.

**PyPI**: https://pypi.org/project/PyYAML/  
**Documentation**: https://pyyaml.org/wiki/PyYAMLDocumentation

## Installation
```bash
pip install PyYAML
```

## Basic Usage

### Reading YAML Files

```python
import yaml

# Load from file
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# config is now a Python dict
print(config['video_quality'])
print(config['output_dir'])
```

### Writing YAML Files

```python
import yaml

config = {
    'video_quality': 'best[height<=1080]',
    'output_dir': 'data/processed',
    'scene_detection': {
        'enabled': True,
        'threshold': 27.0
    },
    'output_resolution': [640, 480]
}

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)
```

### Error Handling

```python
import yaml

try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    print("Config file not found")
    config = {}
except yaml.YAMLError as e:
    print(f"Error parsing YAML: {e}")
    config = {}
```

### Safe vs. Unsafe Loading

```python
import yaml

# ALWAYS use safe_load (secure, recommended)
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Never use load() without Loader (security risk)
# yaml.load(f)  # DON'T USE THIS

# Only use full_load if you need advanced features
with open('config.yaml', 'r') as f:
    config = yaml.full_load(f)
```

### Example Config Structure

```yaml
# config.yaml
input:
  urls_file: "data/urls.txt"
  max_downloads: 10

output:
  base_dir: "data/processed"
  format: "jpeg"
  resolution: [640, 480]

scene_detection:
  enabled: true
  detector: "adaptive"
  threshold: 27.0
  min_scene_length: 15

processing:
  jpeg_quality: 85
  parallel: false
```

Reading nested config:
```python
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Access nested values
urls_file = config['input']['urls_file']
enabled = config['scene_detection']['enabled']
resolution = config['output']['resolution']  # Returns list [640, 480]
```

---

# argparse - Command-Line Argument Parsing

## Overview
argparse is Python's standard library for creating command-line interfaces with arguments, options, and help text.

**Documentation**: https://docs.python.org/3/library/argparse.html  
**Built-in**: No installation needed

## Basic Usage

### Simple Argument Parser

```python
import argparse

parser = argparse.ArgumentParser(description='Video processing tool')

# Positional argument
parser.add_argument('input', help='Input video file')

# Optional argument with flag
parser.add_argument('-o', '--output', help='Output directory')

# Parse arguments
args = parser.parse_args()

print(f"Input: {args.input}")
print(f"Output: {args.output}")
```

Usage:
```bash
python script.py video.mp4 --output frames/
```

### Common Argument Types

```python
import argparse

parser = argparse.ArgumentParser()

# String (default)
parser.add_argument('--name', type=str, help='Name')

# Integer
parser.add_argument('--count', type=int, default=10, help='Count')

# Float
parser.add_argument('--threshold', type=float, default=27.0, help='Threshold')

# Boolean flag
parser.add_argument('--verbose', action='store_true', help='Verbose output')
parser.add_argument('--no-cache', action='store_true', help='Disable cache')

# Choice from list
parser.add_argument('--format', choices=['jpeg', 'png', 'video'], default='jpeg')

# Multiple values
parser.add_argument('--files', nargs='+', help='Multiple files')

args = parser.parse_args()
```

### Complete Example for Video Processor

```python
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Process YouTube videos for ML datasets',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Configuration file
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file'
    )
    
    # Input/Output
    parser.add_argument(
        '-u', '--urls-file',
        type=str,
        help='File containing video URLs'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        help='Output directory'
    )
    
    # Scene detection
    parser.add_argument(
        '--no-scene-detection',
        action='store_true',
        help='Disable scene detection'
    )
    
    parser.add_argument(
        '--scene-threshold',
        type=float,
        help='Scene detection threshold'
    )
    
    parser.add_argument(
        '--scene-detector',
        type=str,
        choices=['content', 'adaptive', 'threshold'],
        help='Scene detector type'
    )
    
    # Frame extraction
    parser.add_argument(
        '--resolution',
        type=str,
        metavar='WIDTHxHEIGHT',
        help='Output resolution (e.g., 640x480)'
    )
    
    parser.add_argument(
        '--jpeg-quality',
        type=int,
        choices=range(1, 101),
        metavar='[1-100]',
        help='JPEG quality'
    )
    
    # Boolean flags
    parser.add_argument(
        '--flat-structure',
        action='store_true',
        help='Use flat folder structure'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    return parser.parse_args()

# Usage
args = parse_arguments()

if args.resolution:
    width, height = map(int, args.resolution.split('x'))
    print(f"Resolution: {width}x{height}")
```

### Argument Groups

```python
import argparse

parser = argparse.ArgumentParser()

# Create argument groups for organization
input_group = parser.add_argument_group('input options')
input_group.add_argument('--urls', help='URL file')
input_group.add_argument('--max-downloads', type=int, help='Max downloads')

output_group = parser.add_argument_group('output options')
output_group.add_argument('--output-dir', help='Output directory')
output_group.add_argument('--format', choices=['jpeg', 'video'], help='Format')

args = parser.parse_args()
```

### Mutually Exclusive Arguments

```python
import argparse

parser = argparse.ArgumentParser()

# Only one of these can be specified
group = parser.add_mutually_exclusive_group()
group.add_argument('--scenes', action='store_true', help='Extract by scene')
group.add_argument('--time', action='store_true', help='Extract by time')

args = parser.parse_args()
```

---

# tqdm - Progress Bars

## Overview
tqdm provides fast, extensible progress bars for Python loops and iterables.

**PyPI**: https://pypi.org/project/tqdm/  
**Documentation**: https://tqdm.github.io/  
**GitHub**: https://github.com/tqdm/tqdm

## Installation
```bash
pip install tqdm
```

## Basic Usage

### Simple Loop Progress Bar

```python
from tqdm import tqdm
import time

# Wrap any iterable with tqdm
for i in tqdm(range(100)):
    time.sleep(0.01)  # Simulate work
```

### With Description

```python
from tqdm import tqdm

for i in tqdm(range(100), desc="Processing"):
    pass  # Do work

# Output: Processing: 45%|████████      | 45/100 [00:02<00:02, 20.5it/s]
```

### Custom Units

```python
from tqdm import tqdm

urls = ['url1', 'url2', 'url3']

for url in tqdm(urls, desc="Downloading videos", unit="video"):
    # Download video
    pass

# Output: Downloading videos: 2/3 videos [00:10<00:05, 5.2s/video]
```

### Manual Progress Updates

```python
from tqdm import tqdm
import time

# Create progress bar
pbar = tqdm(total=100, desc="Processing")

for i in range(10):
    # Do work
    time.sleep(0.1)
    
    # Update progress
    pbar.update(10)  # Increment by 10

pbar.close()
```

### File Download Progress

```python
from tqdm import tqdm

def download_with_progress(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as f, tqdm(
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
        desc=filename
    ) as pbar:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                pbar.update(len(chunk))
```

### Nested Progress Bars

```python
from tqdm import tqdm

videos = ['video1.mp4', 'video2.mp4', 'video3.mp4']

# Outer progress bar for videos
for video in tqdm(videos, desc="Videos", position=0):
    
    # Inner progress bar for frames
    for frame in tqdm(range(100), desc=f"Frames ({video})", position=1, leave=False):
        # Process frame
        pass
```

### Progress Bar for Video Processing

```python
from tqdm import tqdm
import cv2

def process_video_with_progress(video_path):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Create progress bar
    with tqdm(total=total_frames, desc="Extracting frames", unit="frame") as pbar:
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame
            # ...
            
            frame_count += 1
            pbar.update(1)
    
    cap.release()
    return frame_count
```

### With Context Manager

```python
from tqdm import tqdm

items = list(range(100))

with tqdm(total=len(items), desc="Processing") as pbar:
    for item in items:
        # Process item
        pbar.update(1)
        
        # Optional: Update description
        pbar.set_description(f"Processing item {item}")
```

### Disable Progress Bar (for quiet mode)

```python
from tqdm import tqdm

def process_items(items, show_progress=True):
    # Disable if show_progress is False
    for item in tqdm(items, desc="Processing", disable=not show_progress):
        # Process item
        pass
```

---

# pathlib - Modern Path Handling

## Overview
pathlib provides object-oriented filesystem paths. Part of Python standard library (Python 3.4+).

**Documentation**: https://docs.python.org/3/library/pathlib.html  
**Built-in**: No installation needed

## Basic Usage

### Creating Paths

```python
from pathlib import Path

# Current directory
current = Path.cwd()

# Home directory
home = Path.home()

# Specific path
path = Path('/data/videos')
path = Path('data/videos')  # Relative path

# Join paths with /
path = Path('data') / 'videos' / 'scene_001'
# Result: data/videos/scene_001
```

### Path Properties

```python
from pathlib import Path

path = Path('/data/videos/video1.mp4')

print(path.name)          # 'video1.mp4'
print(path.stem)          # 'video1' (without extension)
print(path.suffix)        # '.mp4'
print(path.parent)        # Path('/data/videos')
print(path.parts)         # ('/', 'data', 'videos', 'video1.mp4')

# Check if absolute
print(path.is_absolute())  # True

# Convert to string
path_str = str(path)
```

### Creating Directories

```python
from pathlib import Path

# Create directory
output_dir = Path('data/processed')
output_dir.mkdir()  # Creates 'data/processed', fails if 'data' doesn't exist

# Create with parents
output_dir.mkdir(parents=True)  # Creates 'data' and 'processed'

# Create if doesn't exist (no error if exists)
output_dir.mkdir(parents=True, exist_ok=True)
```

### Checking Path Existence

```python
from pathlib import Path

path = Path('video.mp4')

# Check if exists
if path.exists():
    print("Path exists")

# Check if file
if path.is_file():
    print("It's a file")

# Check if directory
if path.is_dir():
    print("It's a directory")
```

### Listing Files

```python
from pathlib import Path

# List all items in directory
data_dir = Path('data')
for item in data_dir.iterdir():
    print(item)

# List only files
for file in data_dir.iterdir():
    if file.is_file():
        print(file)

# Glob pattern matching
for video in data_dir.glob('*.mp4'):
    print(video)

# Recursive glob
for video in data_dir.rglob('*.mp4'):  # Finds .mp4 in subdirectories too
    print(video)
```

### Reading and Writing Files

```python
from pathlib import Path

path = Path('config.txt')

# Read text
content = path.read_text()

# Write text
path.write_text('Hello, world!')

# Read bytes
data = path.read_bytes()

# Write bytes
path.write_bytes(b'Binary data')
```

### Practical Examples for Video Processor

```python
from pathlib import Path

def setup_project_structure():
    """Create project directories"""
    base = Path('.')
    
    # Create directories
    (base / 'data' / 'raw').mkdir(parents=True, exist_ok=True)
    (base / 'data' / 'processed').mkdir(parents=True, exist_ok=True)
    (base / 'logs').mkdir(exist_ok=True)
    
    # Create URLs file if doesn't exist
    urls_file = base / 'data' / 'urls.txt'
    if not urls_file.exists():
        urls_file.write_text('# Add YouTube URLs here, one per line\n')

def get_scene_output_path(video_name, scene_idx, frame_idx, flat_structure=False):
    """Generate output path for frame"""
    base = Path('data/processed')
    
    if flat_structure:
        # Flat: data/processed/video1_scene_001_frame_0001.jpg
        filename = f'{video_name}_scene_{scene_idx:03d}_frame_{frame_idx:04d}.jpg'
        return base / 'scenes' / filename
    else:
        # Hierarchical: data/processed/video1/scene_001/frame_0001.jpg
        return base / video_name / f'scene_{scene_idx:03d}' / f'frame_{frame_idx:04d}.jpg'

def find_video_files(directory):
    """Find all video files in directory"""
    video_dir = Path(directory)
    
    extensions = ['.mp4', '.avi', '.mkv', '.mov', '.webm']
    
    video_files = []
    for ext in extensions:
        video_files.extend(video_dir.glob(f'*{ext}'))
    
    return video_files
```

### Path Manipulation

```python
from pathlib import Path

# Change extension
path = Path('video.mp4')
new_path = path.with_suffix('.avi')  # Path('video.avi')

# Change name
new_path = path.with_name('new_video.mp4')  # Path('new_video.mp4')

# Change stem (keep extension)
new_path = path.with_stem('processed')  # Path('processed.mp4')

# Resolve to absolute path
abs_path = path.resolve()

# Relative path from another path
rel_path = path.relative_to('/data')
```

---

# Integration Example

Here's how these libraries work together in the video processor:

```python
import argparse
import yaml
from pathlib import Path
from tqdm import tqdm

def main():
    # 1. Parse command-line arguments
    parser = argparse.ArgumentParser(description='Video processor')
    parser.add_argument('-c', '--config', default='config.yaml')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    
    # 2. Load YAML configuration
    config_path = Path(args.config)
    with config_path.open('r') as f:
        config = yaml.safe_load(f)
    
    # 3. Setup paths using pathlib
    output_dir = Path(config['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    urls_file = Path(config['urls_file'])
    
    # 4. Read URLs
    urls = []
    with urls_file.open('r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    
    # 5. Process with progress bar
    for url in tqdm(urls, desc="Downloading videos", unit="video", disable=not args.verbose):
        # Download and process video
        pass
    
    print("Processing complete!")

if __name__ == '__main__':
    main()
```

---

# Summary for AI Agents

**PyYAML**:
- Use `yaml.safe_load(f)` to read config files
- Use `yaml.dump(dict, f)` to write configs
- Returns/accepts Python dicts
- Always use safe_load, never load() without Loader

**argparse**:
- Built-in Python library for CLI
- Use `add_argument()` to define options
- Use `action='store_true'` for boolean flags
- Use `choices=[]` to restrict values
- Parse with `parser.parse_args()`

**tqdm**:
- Wrap iterables: `tqdm(iterable, desc="text")`
- Manual updates: `pbar.update(n)`
- Disable with `disable=not show_progress`
- Use `unit` parameter for custom units
- Supports nested progress bars

**pathlib**:
- Use `Path()` instead of string paths
- Join with `/`: `Path('data') / 'videos'`
- Create dirs: `path.mkdir(parents=True, exist_ok=True)`
- Check existence: `path.exists()`, `path.is_file()`
- Glob patterns: `path.glob('*.mp4')`
- Properties: `path.name`, `path.stem`, `path.suffix`
