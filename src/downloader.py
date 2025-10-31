"""
Enhanced video downloader with parallel processing.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import yt_dlp
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

from .utils import ensure_dir, sanitize_filename


def _download_single_worker(args):
    """
    Worker function for parallel downloads (must be at module level for pickling).
    
    Args:
        args: Tuple of (url, download_dir, video_format, video_quality)
    
    Returns:
        (success, filepath, metadata)
    """
    url, download_dir, video_format, video_quality = args
    
    try:
        ydl_opts = {
            'format': video_quality,
            'merge_output_format': video_format,
            'outtmpl': str(download_dir / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id', 'unknown')
            title = sanitize_filename(info.get('title', 'video'))
            duration = info.get('duration', 0)
            
            # Download
            ydl.download([url])
            
            # Get filename
            filename = ydl.prepare_filename(info)
            
            # Extract metadata
            metadata = {
                'video_id': video_id,
                'title': title,
                'url': url,
                'duration': duration,
                'width': info.get('width'),
                'height': info.get('height'),
                'fps': info.get('fps'),
                'filesize': info.get('filesize'),
            }
            
            if os.path.exists(filename):
                return True, filename, metadata
            else:
                return False, None, None
                
    except Exception as e:
        return False, None, None


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
        Download multiple videos in parallel.
        
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
        
        # Prepare arguments for worker function
        download_args = [
            (url, self.download_dir, self.video_format, self.video_quality)
            for url in urls
        ]
        
        # Use multiprocessing pool
        with Pool(processes=self.num_workers) as pool:
            # Map downloads with progress bar
            results_iterator = tqdm(
                pool.imap(_download_single_worker, download_args),
                total=len(urls),
                desc="Downloading videos",
                unit="video"
            )
            for idx, (success, filepath, metadata) in enumerate(results_iterator):
                if success and filepath and metadata:
                    metadata['filepath'] = filepath
                    # Log after download
                    self.logger.info(f"Downloaded: {metadata.get('title', 'unknown')} ({metadata.get('video_id', 'unknown')})")
                    results.append(metadata)
                else:
                    # Log failure
                    failed_url = urls[idx] if idx < len(urls) else 'unknown'
                    self.logger.error(f"Failed to download: {failed_url}")
        
        self.logger.info(
            f"Download complete: {len(results)}/{len(urls)} videos successful"
        )
        
        return results

