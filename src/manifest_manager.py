"""
Manifest file management for tracking processing metadata
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class ManifestManager:
    """
    Manage processing manifest (metadata tracking).
    """
    
    def __init__(
        self,
        manifest_path: str = "data/manifest.json",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize manifest manager.
        
        Args:
            manifest_path: Path to manifest JSON file
            logger: Logger instance
        """
        self.manifest_path = Path(manifest_path)
        self.logger = logger or logging.getLogger(__name__)
        
        # Ensure directory exists
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing manifest or create new
        if self.manifest_path.exists():
            self.manifest = self._load()
        else:
            self.manifest = {
                'created_at': datetime.now().isoformat(),
                'version': '1.0',
                'videos': []
            }
    
    def _load(self) -> Dict:
        """Load manifest from file."""
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
            self.logger.info(f"Loaded manifest with {len(manifest.get('videos', []))} videos")
            return manifest
        except Exception as e:
            self.logger.error(f"Failed to load manifest: {str(e)}")
            return {
                'created_at': datetime.now().isoformat(),
                'version': '1.0',
                'videos': []
            }
    
    def save(self):
        """Save manifest to file."""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=2)
            self.logger.info(f"Saved manifest to {self.manifest_path}")
        except Exception as e:
            self.logger.error(f"Failed to save manifest: {str(e)}")
    
    def add_video(
        self,
        video_id: str,
        metadata: Dict,
        validation: Dict,
        scenes: List[Dict]
    ):
        """
        Add video processing record to manifest.
        
        Args:
            video_id: Unique video identifier
            metadata: Video metadata from download
            validation: Validation results
            scenes: List of scene metadata
        """
        record = {
            'video_id': video_id,
            'processed_at': datetime.now().isoformat(),
            'source': metadata,
            'validation': validation,
            'scenes': scenes,
            'stats': {
                'num_scenes': len(scenes),
                'total_frames': sum(s.get('saved_frames', 0) for s in scenes)
            }
        }
        
        self.manifest['videos'].append(record)
        self.logger.debug(f"Added video to manifest: {video_id}")
    
    def get_processed_video_ids(self) -> List[str]:
        """Get list of already processed video IDs."""
        return [v['video_id'] for v in self.manifest.get('videos', [])]
    
    def is_processed(self, video_id: str) -> bool:
        """Check if video already processed."""
        return video_id in self.get_processed_video_ids()

