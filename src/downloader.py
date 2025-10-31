"""
Enhanced video downloader with parallel processing.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import yt_dlp
from tqdm import tqdm
from multiprocessing import Pool, cpu_count, Manager
from contextlib import contextmanager

from .utils import ensure_dir, sanitize_filename


class SilentLogger:
    """Logger that discards all messages."""
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass


@contextmanager
def suppress_stdout_stderr():
    """Context manager to suppress stdout and stderr."""
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


def format_bytes(bytes_count: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f}{unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f}PB"


def _download_single_worker(args):
    """
    Worker function for parallel downloads (must be at module level for pickling).
    
    Args:
        args: Tuple of (url, download_dir, video_format, video_quality, progress_dict, url_idx)
    
    Returns:
        (success, filepath, metadata)
    """
    url, download_dir, video_format, video_quality, progress_dict, url_idx = args
    
    try:
        # Initialize progress tracking for this video
        progress_dict[url_idx] = {
            'status': 'starting',
            'title': '',
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'speed': 0,
            'percent': 0.0
        }
        
        def progress_hook(d):
            """Progress hook that updates shared progress dict."""
            # Reassign for Manager.dict() sync (nested updates don't sync properly)
            current = progress_dict.get(url_idx, {})
            if d['status'] == 'downloading':
                progress_dict[url_idx] = {
                    **current,
                    'status': 'downloading',
                    'title': current.get('title', ''),
                    'downloaded_bytes': d.get('downloaded_bytes', 0),
                    'total_bytes': d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0),
                    'speed': d.get('speed', 0),
                    'percent': d.get('_percent_str', '0%').strip('%') or '0'
                }
            elif d['status'] == 'finished':
                progress_dict[url_idx] = {
                    **current,
                    'status': 'finished',
                    'downloaded_bytes': current.get('total_bytes', 0),
                    'percent': '100'
                }
        
        ydl_opts = {
            'format': video_quality,
            'merge_output_format': video_format,
            'outtmpl': str(download_dir / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'logger': SilentLogger(),
            'progress_hooks': [progress_hook],
        }
        
        # Suppress all yt-dlp output completely
        with suppress_stdout_stderr():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                video_id = info.get('id', 'unknown')
                title = sanitize_filename(info.get('title', 'video'))
                duration = info.get('duration', 0)
                
                # Update progress dict with title immediately (for display)
                # IMPORTANT: Reassign entire dict entry for Manager.dict() sync
                current = progress_dict.get(url_idx, {})
                progress_dict[url_idx] = {
                    **current,
                    'title': title[:50] + ('...' if len(title) > 50 else ''),
                    'status': 'connecting'  # Status while we check file existence
                }
                
                # Get filename before download
                filename = ydl.prepare_filename(info)
                
                # Check if file already exists
                file_exists = os.path.exists(filename)
                if file_exists:
                    file_size = os.path.getsize(filename)
                    expected_size = info.get('filesize') or info.get('filesize_approx', 0)
                    
                    # If we have expected size, check if file is complete (within 1% tolerance)
                    # If no expected size, assume file is complete if it exists
                    if expected_size == 0 or abs(file_size - expected_size) / max(expected_size, 1) < 0.01:
                        # Reassign for Manager.dict() sync
                        current = progress_dict.get(url_idx, {})
                        progress_dict[url_idx] = {
                            **current,
                            'status': 'skipped',
                            'title': title[:50] + ('...' if len(title) > 50 else ''),
                            'downloaded_bytes': file_size,
                            'total_bytes': file_size if expected_size == 0 else expected_size,
                            'percent': '100'
                        }
                        # File already exists and appears complete, skip download
                        skip_download = True
                    else:
                        # File exists but size doesn't match, re-download
                        skip_download = False
                        os.remove(filename)  # Remove incomplete file
                else:
                    skip_download = False
                
                if not skip_download:
                    # Update progress with title and size
                    # Reassign for Manager.dict() sync
                    total_size = info.get('filesize') or info.get('filesize_approx', 0)
                    current = progress_dict.get(url_idx, {})
                    progress_dict[url_idx] = {
                        **current,
                        'status': 'downloading',
                        'title': title[:50] + ('...' if len(title) > 50 else ''),
                        'total_bytes': total_size
                    }
                    
                    # Download (all output suppressed)
                    ydl.download([url])
                    
                    # Mark as completed after download
                    progress_dict[url_idx]['status'] = 'completed'
        
        # Verify file exists
        if not os.path.exists(filename):
            progress_dict[url_idx]['status'] = 'failed'
            return False, None, None
        
        # Extract metadata (info already extracted above)
        metadata = {
            'video_id': video_id,
            'title': title,
            'url': url,
            'duration': duration,
            'width': info.get('width'),
            'height': info.get('height'),
            'fps': info.get('fps'),
            'filesize': info.get('filesize') or os.path.getsize(filename),
        }
        
        return True, filename, metadata
                
    except Exception as e:
        if url_idx in progress_dict:
            progress_dict[url_idx]['status'] = 'failed'
        return False, None, None


def _update_progress_bar(pbar: tqdm, progress_dict: Dict, total_videos: int):
    """Update progress bar with current download status."""
    # Convert Manager.dict() to regular dict for faster iteration
    # (Manager.dict() can be slow to iterate)
    try:
        dict_copy = dict(progress_dict)
    except:
        dict_copy = {}
    
    completed = sum(1 for v in dict_copy.values() if v.get('status') in ('completed', 'finished', 'skipped'))
    active = sum(1 for v in dict_copy.values() if v.get('status') == 'downloading')
    failed = sum(1 for v in dict_copy.values() if v.get('status') == 'failed')
    skipped = sum(1 for v in dict_copy.values() if v.get('status') == 'skipped')
    
    # Calculate total progress
    total_downloaded = sum(v.get('downloaded_bytes', 0) for v in dict_copy.values())
    total_size = sum(v.get('total_bytes', 0) for v in dict_copy.values())
    
    # Calculate combined speed from all active downloads
    total_speed = sum(v.get('speed', 0) for v in dict_copy.values() if v.get('status') == 'downloading')
    
    # Get active downloads info with speeds (sorted by speed, descending)
    # Include both 'downloading' and 'connecting' status for display
    active_downloads = []
    for v in dict_copy.values():
        status = v.get('status', '')
        if status in ('downloading', 'connecting'):
            title = v.get('title', '')[:25]  # Shorter title for cleaner display
            # Add if we have a title OR if status is connecting (show connecting even without title yet)
            if title or status == 'connecting':
                percent = float(v.get('percent', 0))
                speed = v.get('speed', 0)
                active_downloads.append({
                    'title': title or 'Video',
                    'percent': percent,
                    'speed': speed,
                    'status': status
                })
    
    # Sort by speed (descending), then by status (downloading first) to show fastest/active downloads first
    active_downloads.sort(key=lambda x: (x['speed'], x['status'] == 'downloading'), reverse=True)
    
    # Update progress bar description with status counts
    status_parts = []
    if active > 0:
        status_parts.append(f"{active} active")
    if skipped > 0:
        status_parts.append(f"{skipped} skipped")
    status_parts.append(f"{completed} done")
    if failed > 0:
        status_parts.append(f"{failed} failed")
    
    desc = f"Downloading [{', '.join(status_parts)}]"
    pbar.set_description(desc)
    
    # Update progress (always use video count for simplicity, show bytes in description)
    pbar.total = total_videos
    pbar.n = completed + failed
    
    # Build postfix with detailed information
    postfix_parts = []
    
    # Overall progress (bytes and percentage) - show if we have size info
    if total_size > 0:
        overall_percent = (total_downloaded / total_size) * 100 if total_size > 0 else 0
        postfix_parts.append(f"{format_bytes(total_downloaded)}/{format_bytes(total_size)} ({overall_percent:.1f}%)")
    elif total_downloaded > 0:
        # Show downloaded bytes even if we don't know total size yet
        postfix_parts.append(f"{format_bytes(total_downloaded)} downloaded")
    
    # Combined speed if we have active downloads with speed
    if total_speed > 0:
        speed_str = format_bytes(int(total_speed)) + '/s'
        postfix_parts.append(f"Speed: {speed_str}")
    
    # Show active download(s) - always show at least titles
    if active_downloads:
        # Show top 1-2 active downloads (already sorted above)
        top_download = active_downloads[0]
        if top_download['speed'] > 0:
            speed_str = format_bytes(int(top_download['speed'])) + '/s'
            postfix_parts.append(f"{top_download['title']} ({top_download['percent']:.0f}%, {speed_str})")
        elif top_download['percent'] > 0:
            postfix_parts.append(f"{top_download['title']} ({top_download['percent']:.0f}%)")
        elif top_download['status'] == 'connecting':
            postfix_parts.append(f"{top_download['title']} (connecting...)")
        else:
            # Just starting - show title
            postfix_parts.append(f"{top_download['title']} (starting...)")
        
        if len(active_downloads) > 1:
            # Show additional info about other downloads
            other_count = len(active_downloads) - 1
            if other_count == 1:
                # If only one more, show it
                other = active_downloads[1]
                if other['speed'] > 0:
                    speed_str = format_bytes(int(other['speed'])) + '/s'
                    postfix_parts.append(f"{other['title']} ({other['percent']:.0f}%, {speed_str})")
                elif other['percent'] > 0:
                    postfix_parts.append(f"{other['title']} ({other['percent']:.0f}%)")
                elif other['status'] == 'connecting':
                    postfix_parts.append(f"{other['title']} (connecting...)")
                else:
                    postfix_parts.append(f"{other['title']} (starting...)")
            else:
                # Multiple others - show count
                postfix_parts.append(f"+{other_count} more")
    else:
        # No active downloads showing progress yet, but might have titles in progress_dict
        # Check for starting/connecting downloads (even without title yet)
        starting = [v for v in dict_copy.values() 
                   if v.get('status') in ('starting', 'connecting')]
        if starting:
            # Show first starting download (with or without title)
            first = starting[0]
            first_title = first.get('title', '')
            if first_title:
                status_text = 'connecting...' if first.get('status') == 'connecting' else 'starting...'
                postfix_parts.append(f"{first_title[:25]} ({status_text})")
            elif len(starting) > 0:
                # No title yet, but we know something is starting
                postfix_parts.append("Connecting to videos...")
    
    # Always set postfix (even if empty, it clears previous state)
    postfix_str = ' | '.join(postfix_parts) if postfix_parts else ''
    pbar.set_postfix_str(postfix_str)
    
    # Debug: Log if postfix should be showing but isn't (only in debug mode)
    # Uncomment to debug: print(f"DEBUG: postfix_parts={postfix_parts}, postfix_str='{postfix_str}', progress_dict={dict(progress_dict)}")


class ParallelVideoDownloader:
    """
    Download videos from URLs with parallel processing.
    """
    
    def __init__(
        self,
        download_dir: str = "data/raw",
        video_format: str = "mp4",
        video_quality: str = "best[height<=1080]",
        num_workers: int = 4,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize parallel video downloader.
        
        Args:
            download_dir: Directory to save downloaded videos
            video_format: Desired video format
            video_quality: Quality filter string
            num_workers: Number of parallel download processes
            logger: Logger instance
        """
        self.download_dir = ensure_dir(download_dir)
        self.video_format = video_format
        self.video_quality = video_quality
        self.num_workers = min(num_workers, cpu_count())
        self.logger = logger or logging.getLogger(__name__)
        
    def read_urls_from_file(self, urls_file: str) -> List[str]:
        """Read URLs from text file (one per line)."""
        urls = []
        try:
            with open(urls_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)
            self.logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
        except FileNotFoundError:
            self.logger.error(f"URLs file not found: {urls_file}")
            raise
        
        return urls
    
    def download_videos_parallel(
        self, 
        urls: List[str],
        max_downloads: Optional[int] = None
    ) -> List[Dict]:
        """
        Download multiple videos in parallel with unified progress display.
        
        Args:
            urls: List of video URLs
            max_downloads: Maximum number to download (None = all)
        
        Returns:
            List of metadata dicts for successful downloads
        """
        if max_downloads:
            urls = urls[:max_downloads]
        
        self.logger.info(f"Starting parallel download of {len(urls)} videos with {self.num_workers} workers")
        
        results = []
        
        # Create shared progress dictionary
        manager = Manager()
        progress_dict = manager.dict()
        
        # Prepare arguments for worker function (include progress dict and index)
        download_args = [
            (url, self.download_dir, self.video_format, self.video_quality, progress_dict, idx)
            for idx, url in enumerate(urls)
        ]
        
        # Create progress bar (starts with video count, switches to bytes when available)
        # Use dynamic_ncols to fit terminal width, include postfix in display
        pbar = tqdm(
            total=len(urls),
            desc="Downloading",
            unit="video",
            miniters=1,
            mininterval=0.1,  # Update more frequently for smoother display
            dynamic_ncols=True,
            bar_format='{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {postfix}]'
        )
        
        # Use multiprocessing pool
        pool = Pool(processes=self.num_workers)
        
        # Start downloads asynchronously
        async_results = [pool.apply_async(_download_single_worker, (args,)) for args in download_args]
        
        # Update progress bar in a loop
        completed_downloads = set()
        try:
            while len(completed_downloads) < len(async_results):
                # Update progress bar (refresh display)
                _update_progress_bar(pbar, progress_dict, len(urls))
                pbar.refresh()  # Force refresh to ensure display updates
                
                # Check for completed downloads
                for idx, async_result in enumerate(async_results):
                    if idx not in completed_downloads and async_result.ready():
                        completed_downloads.add(idx)
                        try:
                            success, filepath, metadata = async_result.get(timeout=1)
                            if success and filepath and metadata:
                                metadata['filepath'] = filepath
                                # Check if this was skipped
                                was_skipped = progress_dict[idx].get('status') == 'skipped'
                                if was_skipped:
                                    self.logger.info(f"Skipped (already exists): {metadata.get('title', 'unknown')} ({metadata.get('video_id', 'unknown')})")
                                else:
                                    self.logger.info(f"Downloaded: {metadata.get('title', 'unknown')} ({metadata.get('video_id', 'unknown')})")
                                results.append(metadata)
                            else:
                                failed_url = urls[idx] if idx < len(urls) else 'unknown'
                                self.logger.error(f"Failed to download: {failed_url}")
                        except Exception as e:
                            self.logger.error(f"Error getting result for download {idx}: {e}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.logger.warning("Download interrupted by user")
            pool.terminate()
            pool.join()
            pbar.close()
            raise
        finally:
            pool.close()
            pool.join()
            pbar.close()
        
        # Final update
        _update_progress_bar(pbar, progress_dict, len(urls))
        
        self.logger.info(
            f"Download complete: {len(results)}/{len(urls)} videos successful"
        )
        
        return results
