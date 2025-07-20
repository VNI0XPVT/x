"""
Heroku-specific utilities for file and path management
"""

import os
import time
import tempfile
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_safe_download_path():
    """Get a safe download path that works on Heroku"""
    try:
        # Try to use /tmp directory on Heroku (ephemeral but writable)
        if os.path.exists('/tmp'):
            download_dir = '/tmp/dolbymusic_downloads'
        else:
            # Fallback to local downloads directory
            download_dir = os.path.join(os.getcwd(), 'downloads')
        
        os.makedirs(download_dir, exist_ok=True)
        return download_dir
    except Exception as e:
        logger.warning(f"Could not create download directory: {e}")
        # Last resort - use system temp directory
        return tempfile.gettempdir()

def safe_file_path(filename):
    """Create a safe file path for Heroku deployment"""
    try:
        download_dir = get_safe_download_path()
        return os.path.join(download_dir, filename)
    except Exception as e:
        logger.error(f"Error creating safe file path: {e}")
        return os.path.join(tempfile.gettempdir(), filename)

def cleanup_temp_files(max_age_hours=1):
    """Clean up temporary files older than specified hours"""
    try:
        download_dir = get_safe_download_path()
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filepath in Path(download_dir).glob("*"):
            if filepath.is_file():
                file_age = current_time - filepath.stat().st_ctime
                if file_age > max_age_seconds:
                    try:
                        filepath.unlink()
                        logger.info(f"Cleaned up old file: {filepath}")
                    except Exception as e:
                        logger.warning(f"Could not remove file {filepath}: {e}")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")

def ensure_directory_exists(path):
    """Ensure a directory exists, with proper error handling"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except PermissionError:
        logger.error(f"Permission denied creating directory: {path}")
        return False
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        return False
