# yt-dlp Model Context File

## Overview
yt-dlp is a feature-rich command-line audio/video downloader with support for thousands of sites. It is a fork of youtube-dl with active maintenance and many improvements.

**Primary Use Case**: Download videos and audio from YouTube and 1000+ other websites programmatically.

**GitHub**: https://github.com/yt-dlp/yt-dlp  
**Documentation**: https://github.com/yt-dlp/yt-dlp#readme  
**PyPI**: https://pypi.org/project/yt-dlp/  
**License**: Unlicense (public domain)

---

## Installation

```bash
# Install with pip
pip install yt-dlp

# Install with default dependencies (recommended)
pip install "yt-dlp[default]"

# Install with additional features
pip install "yt-dlp[default,curl-cffi]"  # With browser impersonation

# Update to latest version
pip install -U yt-dlp

# Install nightly build (most recent fixes)
pip install -U --pre "yt-dlp[default]"
```

**Dependencies**:
- Python 3.10+ (CPython) or 3.11+ (PyPy)
- Optional but recommended: `ffmpeg` and `ffprobe` (for format merging/conversion)

---

## Python API Quick Start

### Basic Video Download

```python
import yt_dlp

# Simplest download
with yt_dlp.YoutubeDL() as ydl:
    ydl.download(['https://www.youtube.com/watch?v=VIDEO_ID'])
```

### Download with Options

```python
import yt_dlp

ydl_opts = {
    'format': 'best',                    # Quality selection
    'outtmpl': '%(title)s.%(ext)s',     # Output filename template
    'quiet': True,                       # Suppress console output
    'no_warnings': True,                 # Suppress warnings
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download(['https://www.youtube.com/watch?v=VIDEO_ID'])
```

### Extract Video Information

```python
import yt_dlp

ydl_opts = {'quiet': True}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info('https://www.youtube.com/watch?v=VIDEO_ID', download=False)
    
    # Access video metadata
    title = info.get('title')
    duration = info.get('duration')
    uploader = info.get('uploader')
    formats = info.get('formats')
    
    print(f"Title: {title}")
    print(f"Duration: {duration} seconds")
```

---

## Core API - YoutubeDL Class

### Constructor Options Dictionary

The `YoutubeDL` class accepts an options dictionary. Here are the most important options:

#### Video Selection & Format

```python
ydl_opts = {
    # Format selection (see FORMAT SELECTION section)
    'format': 'best',                           # or 'worst', 'bestvideo+bestaudio', etc.
    'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',  # Max 1080p
    
    # Video quality shortcuts
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
    
    # Playlist options
    'noplaylist': True,                         # Download only video, not playlist
    'playliststart': 1,                         # Start index
    'playlistend': 5,                           # End index
    'playlist_items': '1-5,8,11-13',           # Specific items
    
    # Video filters
    'match_filter': 'duration < 600',           # Only videos under 10 minutes
    'age_limit': 18,                            # Age restriction
    'date': '20230101',                         # Videos from specific date
}
```

#### Output & Filesystem

```python
ydl_opts = {
    # Output template (see OUTPUT TEMPLATE section)
    'outtmpl': '%(title)s.%(ext)s',            # Default
    'outtmpl': '%(uploader)s/%(title)s-%(id)s.%(ext)s',  # Organized
    'outtmpl': '/path/to/folder/%(title)s.%(ext)s',  # Absolute path
    
    # Filesystem options
    'paths': {'home': '/download/path'},        # Base download directory
    'restrictfilenames': True,                  # ASCII-only filenames
    'windowsfilenames': True,                   # Windows-compatible names
    
    # Overwrite behavior
    'nooverwrites': True,                       # Don't overwrite files
    'overwrites': True,                         # Overwrite all files
    'continue': True,                           # Resume downloads (default)
}
```

#### Download Options

```python
ydl_opts = {
    # Rate limiting
    'ratelimit': 50000,                         # Bytes per second (50 KB/s)
    'throttledratelimit': 100000,              # Min rate before re-extraction
    
    # Retries
    'retries': 10,                              # Number of retries (default)
    'fragment_retries': 10,                     # Fragment-specific retries
    
    # External downloader
    'external_downloader': 'aria2c',            # Use aria2c instead of built-in
    'external_downloader_args': ['-x', '16', '-s', '16'],  # aria2c args
    
    # Network options
    'proxy': 'http://proxy.example.com:8080',   # HTTP/SOCKS proxy
    'socket_timeout': 30,                       # Timeout in seconds
}
```

#### Post-Processing

```python
ydl_opts = {
    # Audio extraction
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',               # mp3, aac, wav, m4a, etc.
        'preferredquality': '192',             # bitrate in kbps
    }],
    
    # Video conversion
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',               # Convert to mp4
    }],
    
    # Embed metadata
    'postprocessors': [{
        'key': 'FFmpegMetadata',
        'add_metadata': True,
    }],
    
    # Embed thumbnail
    'writethumbnail': True,
    'postprocessors': [{
        'key': 'EmbedThumbnail',
    }],
}
```

#### Progress & Logging

```python
ydl_opts = {
    # Console output
    'quiet': True,                              # Suppress output
    'no_warnings': True,                        # Suppress warnings
    'verbose': True,                            # Verbose output
    
    # Progress hooks
    'progress_hooks': [my_hook_function],       # Custom progress tracking
    
    # Logging
    'logger': my_logger_object,                 # Custom logger
}
```

### Progress Hook Example

```python
def progress_hook(d):
    """Custom progress hook for tracking downloads"""
    if d['status'] == 'downloading':
        # d['downloaded_bytes']
        # d['total_bytes']
        # d['speed']
        # d['eta']
        print(f"Downloading: {d.get('_percent_str', 'N/A')}")
    
    elif d['status'] == 'finished':
        print(f"Download complete: {d['filename']}")
    
    elif d['status'] == 'error':
        print(f"Error downloading: {d.get('filename')}")

ydl_opts = {
    'progress_hooks': [progress_hook],
}
```

---

## YoutubeDL Methods

### Key Methods

```python
import yt_dlp

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    # Download videos
    ydl.download([url1, url2, url3])
    
    # Extract info without downloading
    info = ydl.extract_info(url, download=False)
    
    # Download with info dict
    ydl.download_with_info_dict(info)
    
    # Get video filename
    filename = ydl.prepare_filename(info)
    
    # Add post-processor
    ydl.add_post_processor(post_processor_instance)
```

### extract_info() Return Value

```python
info = ydl.extract_info(url, download=False)

# Common fields in info dict:
{
    'id': 'VIDEO_ID',
    'title': 'Video Title',
    'uploader': 'Channel Name',
    'uploader_id': 'channel_id',
    'upload_date': '20231025',
    'description': 'Video description...',
    'duration': 600,                    # seconds
    'view_count': 1000000,
    'like_count': 50000,
    'thumbnail': 'https://...',
    'formats': [...],                   # List of available formats
    'format_id': 'best',
    'ext': 'mp4',
    'filesize': 50000000,              # bytes
    'width': 1920,
    'height': 1080,
    'fps': 30,
    'vcodec': 'h264',
    'acodec': 'aac',
    'abr': 128,                        # audio bitrate kbps
    'vbr': 2000,                       # video bitrate kbps
    # Many more fields available
}
```

---

## Format Selection

yt-dlp uses a sophisticated format selection system.

### Format Selection String Syntax

```python
# Basic selections
'best'                          # Best quality (video+audio)
'worst'                         # Worst quality
'bestvideo'                     # Best video-only
'bestaudio'                     # Best audio-only
'bestvideo+bestaudio'           # Best video + best audio (merged)

# Quality filters
'best[height<=1080]'            # Max 1080p
'best[height>=720]'             # Min 720p
'bestvideo[height<=720]'        # Video max 720p
'best[filesize<50M]'            # Max 50MB file size

# Format preferences
'bestvideo[ext=mp4]+bestaudio[ext=m4a]'     # Prefer mp4/m4a
'best[ext=mp4]/best[ext=webm]/best'         # Fallback chain

# Codec filters
'bestvideo[vcodec^=av01]+bestaudio'         # Prefer AV1 codec
'bestvideo[vcodec=h264]+bestaudio[acodec=aac]'  # Specific codecs

# Multiple conditions
'bestvideo[height<=1080][fps<=30]+bestaudio'

# Complex examples
'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]'
```

### Format Sorting

```python
ydl_opts = {
    'format_sort': [
        'quality',      # Prefer higher quality
        'res:1080',     # Prefer 1080p
        'fps',          # Prefer higher fps
        'codec:h264',   # Prefer h264 codec
        'size',         # Prefer larger file
    ]
}
```

---

## Output Template

Customize output filenames using templates:

```python
ydl_opts = {
    # Available fields:
    'outtmpl': '%(title)s.%(ext)s',                    # Title + extension
    'outtmpl': '%(uploader)s - %(title)s.%(ext)s',     # Uploader + title
    'outtmpl': '%(id)s.%(ext)s',                       # Video ID
    'outtmpl': '%(upload_date)s - %(title)s.%(ext)s',  # Date + title
    
    # With path
    'outtmpl': '/videos/%(uploader)s/%(title)s.%(ext)s',
    
    # Sanitization
    'outtmpl': '%(title).100s.%(ext)s',                # Limit title to 100 chars
    
    # Conditional fields
    'outtmpl': '%(title)s-%(id)s.%(ext)s',
}
```

Common template fields:
- `%(title)s` - Video title
- `%(id)s` - Video ID
- `%(ext)s` - File extension
- `%(uploader)s` - Uploader/channel name
- `%(upload_date)s` - Upload date (YYYYMMDD)
- `%(duration)s` - Duration in seconds
- `%(height)s` - Video height (e.g., 1080)
- `%(width)s` - Video width (e.g., 1920)
- `%(resolution)s` - Resolution string (e.g., "1920x1080")

---

## Common Patterns for Your Use Case

### Pattern 1: Download Multiple Videos from File

```python
import yt_dlp

def download_videos_from_file(urls_file, output_dir='downloads'):
    """Download videos from a file containing URLs"""
    
    # Read URLs
    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    ydl_opts = {
        'format': 'best[height<=1080]',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            try:
                print(f"Downloading: {url}")
                ydl.download([url])
            except Exception as e:
                print(f"Failed to download {url}: {e}")
```

### Pattern 2: Download with Progress Tracking

```python
import yt_dlp
from tqdm import tqdm

class ProgressTracker:
    def __init__(self):
        self.pbar = None
    
    def __call__(self, d):
        if d['status'] == 'downloading':
            if self.pbar is None:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                self.pbar = tqdm(total=total, unit='B', unit_scale=True)
            
            downloaded = d.get('downloaded_bytes', 0)
            self.pbar.update(downloaded - self.pbar.n)
        
        elif d['status'] == 'finished':
            if self.pbar:
                self.pbar.close()
                self.pbar = None

def download_with_progress(url, output_path):
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'progress_hooks': [ProgressTracker()],
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
```

### Pattern 3: Get Video Info Before Downloading

```python
import yt_dlp

def get_video_info(url):
    """Extract video metadata without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),
            'uploader': info.get('uploader'),
            'upload_date': info.get('upload_date'),
            'view_count': info.get('view_count'),
            'formats': len(info.get('formats', [])),
            'best_format': info.get('format'),
            'filesize': info.get('filesize'),
        }

# Usage
info = get_video_info('https://www.youtube.com/watch?v=VIDEO_ID')
print(f"Title: {info['title']}")
print(f"Duration: {info['duration']} seconds")
```

### Pattern 4: Download Multiple Videos in Batch

```python
import yt_dlp
from pathlib import Path

def batch_download(urls, output_dir='downloads', quality='best[height<=1080]'):
    """
    Download multiple videos with proper error handling
    
    Args:
        urls: List of video URLs
        output_dir: Output directory
        quality: Format selection string
    
    Returns:
        List of downloaded file paths
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    ydl_opts = {
        'format': quality,
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    downloaded_files = []
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            try:
                # Get info first
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'video')
                
                print(f"Downloading: {title}")
                
                # Download
                ydl.download([url])
                
                # Get filename
                filename = ydl.prepare_filename(info)
                downloaded_files.append(filename)
                
                print(f"Saved: {filename}")
                
            except Exception as e:
                print(f"Error downloading {url}: {e}")
    
    return downloaded_files
```

### Pattern 5: Sanitize Filenames

```python
import yt_dlp
import os

def sanitize_filename(filename):
    """Remove invalid filename characters"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()

def download_with_clean_filename(url, output_dir):
    """Download with sanitized filename"""
    ydl_opts = {
        'format': 'best',
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Get info
        info = ydl.extract_info(url, download=False)
        title = sanitize_filename(info.get('title', 'video'))
        ext = info.get('ext', 'mp4')
        
        # Set output template
        ydl_opts['outtmpl'] = os.path.join(output_dir, f'{title}.{ext}')
        
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
            ydl2.download([url])
            
        return os.path.join(output_dir, f'{title}.{ext}')
```

---

## Error Handling

```python
import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

def safe_download(url, ydl_opts):
    """Download with comprehensive error handling"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            return True
            
    except DownloadError as e:
        print(f"Download failed: {e}")
        return False
        
    except ExtractorError as e:
        print(f"Could not extract video info: {e}")
        return False
        
    except KeyboardInterrupt:
        print("Download interrupted by user")
        return False
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
```

---

## Supported Sites

yt-dlp supports 1000+ sites including:
- YouTube (all features including live streams, playlists, channels)
- Vimeo
- Dailymotion
- Twitch
- Facebook
- Twitter/X
- Instagram
- TikTok
- Reddit
- And many more...

Check supported sites:
```bash
yt-dlp --list-extractors
```

---

## Command-Line to Python Conversion

Many command-line options have Python API equivalents:

```bash
# Command-line:
yt-dlp -f "best[height<=720]" -o "%(title)s.%(ext)s" URL

# Python equivalent:
ydl_opts = {
    'format': 'best[height<=720]',
    'outtmpl': '%(title)s.%(ext)s',
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([URL])
```

Use the helper script to convert CLI to API:
```python
# From yt-dlp repository
python devscripts/cli_to_api.py "yt-dlp -f best URL"
```

---

## Performance Considerations

1. **Parallel Downloads**: Use external downloader for speed
   ```python
   ydl_opts = {
       'external_downloader': 'aria2c',
       'external_downloader_args': ['-x', '16', '-s', '16'],  # 16 connections
   }
   ```

2. **Rate Limiting**: Avoid getting blocked
   ```python
   ydl_opts = {
       'ratelimit': 1000000,  # 1 MB/s limit
   }
   ```

3. **Retry Logic**: Handle network issues
   ```python
   ydl_opts = {
       'retries': 10,
       'fragment_retries': 10,
   }
   ```

---

## Important Notes

1. **Copyright**: Only download videos you have rights to download
2. **Terms of Service**: Respect website terms of service
3. **Rate Limiting**: Don't hammer servers with requests
4. **ffmpeg**: Required for format merging and post-processing
5. **Updates**: yt-dlp updates frequently, keep it updated

---

## Best Practices for Your Project

1. **Sanitize filenames** from video titles
2. **Handle errors gracefully** with try/except
3. **Use progress hooks** for long downloads
4. **Extract info first** before downloading (check duration, size, etc.)
5. **Limit quality** to save bandwidth/storage (`best[height<=1080]`)
6. **Organize files** using output templates with directories
7. **Log downloads** to avoid re-downloading
8. **Batch process** with proper error handling

---

## Summary for AI Agents

**Key Takeaways**:
1. Use `YoutubeDL` class with options dictionary
2. `download([urls])` for downloading, `extract_info(url, download=False)` for metadata
3. Format selection: `'best[height<=1080]'` for quality limits
4. Output template: `'outtmpl': 'path/%(title)s.%(ext)s'`
5. Progress hooks for tracking: `'progress_hooks': [function]`
6. Always use `with` context manager
7. Handle errors with try/except (DownloadError, ExtractorError)
8. Requires ffmpeg for merging formats and post-processing
9. Very actively maintained, update regularly
10. Supports 1000+ websites, not just YouTube
