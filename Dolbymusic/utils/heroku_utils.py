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
        # Check for environment variable first (set by heroku_start.py)
        env_path = os.environ.get('DOLBYMUSIC_DOWNLOADS_DIR')
        if env_path and os.path.exists(env_path):
            return env_path
            
        # Try to use /tmp directory on Heroku (ephemeral but writable)
        if os.path.exists('/tmp'):
            download_dir = '/tmp/dolbymusic_downloads'
        else:
            # Fallback to local downloads directory
            download_dir = os.path.join(os.getcwd(), 'downloads')
        
        os.makedirs(download_dir, exist_ok=True)
        
        # Verify it's writable
        test_file = os.path.join(download_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        
        return download_dir
    except Exception as e:
        logger.warning(f"Could not create download directory: {e}")
        # Last resort - use system temp directory
        return tempfile.gettempdir()

def get_safe_cache_path():
    """Get a safe cache path that works on Heroku"""
    try:
        # Check for environment variable first 
        env_path = os.environ.get('DOLBYMUSIC_CACHE_DIR')
        if env_path and os.path.exists(env_path):
            return env_path
            
        # Try standard cache directory
        cache_dir = os.path.join(os.getcwd(), 'cache')
        if not os.path.exists(cache_dir):
            # Try /tmp on Heroku
            if os.path.exists('/tmp'):
                cache_dir = '/tmp/dolbymusic_cache'
            
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    except Exception as e:
        logger.warning(f"Could not create cache directory: {e}")
        return tempfile.gettempdir()

def safe_file_path(filename, file_type="download"):
    """Create a safe file path for Heroku deployment"""
    try:
        if file_type == "cache":
            base_dir = get_safe_cache_path()
        else:
            base_dir = get_safe_download_path()
            
        return os.path.join(base_dir, filename)
    except Exception as e:
        logger.error(f"Error creating safe file path: {e}")
        return os.path.join(tempfile.gettempdir(), filename)

def cleanup_temp_files(max_age_hours=1):
    """Clean up temporary files older than specified hours"""
    try:
        # Clean download directory
        download_dir = get_safe_download_path()
        _cleanup_directory(download_dir, max_age_hours)
        
        # Clean cache directory  
        cache_dir = get_safe_cache_path()
        _cleanup_directory(cache_dir, max_age_hours)
        
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")

def _cleanup_directory(directory, max_age_hours):
    """Clean up files in a specific directory"""
    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filepath in Path(directory).glob("*"):
            if filepath.is_file():
                try:
                    file_age = current_time - filepath.stat().st_ctime
                    if file_age > max_age_seconds:
                        filepath.unlink()
                        logger.info(f"Cleaned up old file: {filepath}")
                except Exception as e:
                    logger.warning(f"Could not remove file {filepath}: {e}")
    except Exception as e:
        logger.warning(f"Error cleaning directory {directory}: {e}")

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

def safe_open_file(filepath, mode="r", encoding=None):
    """Safely open a file with proper error handling"""
    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(filepath)
        if parent_dir:
            ensure_directory_exists(parent_dir)
            
        if encoding:
            return open(filepath, mode, encoding=encoding)
        else:
            return open(filepath, mode)
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        raise
    except PermissionError:
        logger.error(f"Permission denied accessing: {filepath}")
        raise
    except Exception as e:
        logger.error(f"Error opening file {filepath}: {e}")
        raise
