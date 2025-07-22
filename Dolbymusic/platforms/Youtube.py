import re
import os
import asyncio
import functools
import tempfile
import atexit
import glob
import time
import random
import math
from typing import Union
from urllib.parse import urlparse, parse_qs
import pytubefix
from pytubefix import YouTube as PyTubeYT, Playlist
from pytubefix.exceptions import VideoUnavailable, LiveStreamError
from youtubesearchpython import VideosSearch

# Configuration
CACHE_MAXSIZE = 100
CACHE_TTL = 3600  # 1 hour cache lifetime
MAX_RETRIES = 3
MIN_REQUEST_DELAY = 1.5  # seconds

# Global caches and state
_youtube_session_cache = {}
_last_request_time = 0
video_cache = {}  # Simple dict cache with manual TTL handling

# Client configurations
CLIENTS = ['WEB', 'ANDROID', 'IOS', 'MWEB']
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

def get_cache_entry(url):
    """Manual cache getter with TTL check"""
    entry = video_cache.get(url)
    if entry:
        if time.time() - entry['timestamp'] < CACHE_TTL:
            return entry['data']
        del video_cache[url]  # Remove expired entry
    return None

def set_cache_entry(url, data):
    """Manual cache setter with size limit"""
    if len(video_cache) >= CACHE_MAXSIZE:
        # Remove oldest entry if cache is full
        oldest_key = min(video_cache.keys(), key=lambda k: video_cache[k]['timestamp'])
        del video_cache[oldest_key]
    video_cache[url] = {'data': data, 'timestamp': time.time()}

# [Keep all other utility functions the same...]

def get_yt_object(url):
    """Create YouTube object with bot avoidance strategies"""
    # Check manual cache first
    cached = get_cache_entry(url)
    if cached:
        try:
            _ = cached.title  # Test if cached object is still valid
            return cached
        except:
            pass  # Cache expired or invalid
    
    params = {
        'use_oauth': False,
        'allow_oauth_cache': False,
        'use_po_token': True,
        'client': random.choice(CLIENTS),
        'headers': {'User-Agent': get_random_user_agent()}
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            enforce_rate_limit()
            params['client'] = random.choice([c for c in CLIENTS if c != params.get('client')])
            
            yt = PyTubeYT(url, **params)
            _ = yt.title  # Test the object
            
            # Cache successful object
            set_cache_entry(url, yt)
            return yt
            
        except (VideoUnavailable, LiveStreamError) as e:
            raise Exception(f"Video unavailable or live stream: {str(e)}")
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                exponential_backoff(attempt)
    
    raise Exception(f"Failed to create YouTube object after {MAX_RETRIES} attempts")

# [Keep all other functions the same...]

class YouTubeAPI:
    # [Keep all YouTubeAPI methods the same...]
    pass

# Initialize the API
YouTube = YouTubeAPI()
