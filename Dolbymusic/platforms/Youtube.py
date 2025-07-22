import re
import os
import asyncio
import functools
import tempfile
import time
import random
import json
from typing import Union
from urllib.parse import urlparse, parse_qs
from pytubefix import YouTube as PyTubeYT
from pytubefix.exceptions import VideoUnavailable, LiveStreamError
from youtubesearchpython import VideosSearch
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 5
MIN_REQUEST_DELAY = 2.0
CACHE_TTL = 3600  # 1 hour

# Enhanced client configurations
CLIENTS = ['WEB', 'ANDROID', 'IOS', 'MWEB', 'WEB_MOBILE']
USER_AGENTS = [
    # Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    # Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    # Android
    'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36',
    # iPhone
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
]

# Cache implementation
class SimpleCache:
    def __init__(self):
        self._cache = {}
    
    def get(self, key):
        entry = self._cache.get(key)
        if entry and time.time() - entry['time'] < CACHE_TTL:
            return entry['data']
        return None
    
    def set(self, key, data):
        self._cache[key] = {'data': data, 'time': time.time()}

cache = SimpleCache()

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def enforce_rate_limit():
    time.sleep(MIN_REQUEST_DELAY + random.uniform(0, 0.5))

def exponential_backoff(attempt):
    wait_time = min(2 ** attempt + random.uniform(0, 1), 30)  # Max 30 seconds
    time.sleep(wait_time)

def validate_video_id(video_id):
    return bool(re.match(r'^[a-zA-Z0-9_-]{11}$', video_id)) if video_id else False

def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match and validate_video_id(match.group(1)):
            return match.group(1)
    return None

async def create_yt_object(url):
    """Enhanced YouTube object creation with better bot avoidance"""
    cached = cache.get(url)
    if cached:
        try:
            if cached.title:  # Simple check if object is still valid
                return cached
        except:
            pass
    
    params = {
        'use_oauth': False,
        'allow_oauth_cache': False,
        'use_po_token': True,
        'client': random.choice(CLIENTS),
        'headers': {
            'User-Agent': get_random_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
        }
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            enforce_rate_limit()
            
            # Rotate client and add slight parameter variations
            params['client'] = random.choice(CLIENTS)
            if attempt > 1:
                params['use_po_token'] = random.choice([True, False])
            
            yt = PyTubeYT(url, **params)
            
            # Test with minimal API call
            if not yt.video_id:
                raise Exception("Empty video ID")
            
            cache.set(url, yt)
            return yt
            
        except (VideoUnavailable, LiveStreamError) as e:
            raise Exception(f"Video unavailable: {str(e)}")
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                exponential_backoff(attempt)
    
    raise Exception("YouTube API request blocked (bot detected)")

async def download_media(video_id, audio_only=True):
    """Robust download function with multiple fallbacks"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        yt = await create_yt_object(url)
        
        # Try multiple stream selection strategies
        strategies = [
            # Primary strategy
            lambda: yt.streams.filter(
                only_audio=audio_only,
                progressive=not audio_only
            ).order_by('abr' if audio_only else 'resolution').desc().first(),
            
            # Fallback strategy
            lambda: yt.streams.filter(
                type='audio' if audio_only else 'video',
                adaptive=True
            ).order_by('abr' if audio_only else 'resolution').desc().first(),
            
            # Last resort
            lambda: yt.streams.get_highest_resolution() if not audio_only else yt.streams.get_audio_only()
        ]
        
        stream = None
        for strategy in strategies:
            try:
                stream = strategy()
                if stream:
                    break
            except:
                continue
        
        if not stream:
            raise Exception("No suitable stream found")
        
        # Download to temp file
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, f"temp_{video_id}.{'mp3' if audio_only else 'mp4'}")
        
        stream.download(output_path=temp_dir, filename=f"temp_{video_id}")
        
        if not os.path.exists(temp_path):
            raise Exception("Download failed - file not created")
        
        return temp_path
        
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        raise Exception(f"Could not download video: {str(e)}")

class YouTubeAPI:
    def __init__(self):
        self.base_url = "https://www.youtube.com/watch?v="
    
    async def extract_url(self, message):
        """Improved URL extraction from Pyrogram messages"""
        text = getattr(message, 'text', '') or getattr(message, 'caption', '')
        if not text:
            return None
            
        # Check entities first
        entities = getattr(message, 'entities', []) or getattr(message, 'caption_entities', [])
        for entity in entities:
            if entity.type == "url":
                return text[entity.offset:entity.offset + entity.length]
            elif entity.type == "text_link":
                return entity.url
        
        # Fallback to regex
        youtube_patterns = [
            r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)',
            r'(https?://youtu\.be/[\w-]+)',
            r'(https?://(?:www\.)?youtube\.com/embed/[\w-]+)'
        ]
        for pattern in youtube_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    
    async def get_video_info(self, url_or_id):
        """Get video details with enhanced error handling"""
        video_id = extract_video_id(url_or_id) if 'youtube.com' in url_or_id else url_or_id
        if not validate_video_id(video_id):
            raise Exception("Invalid YouTube video ID")
            
        url = f"{self.base_url}{video_id}"
        
        try:
            yt = await create_yt_object(url)
            
            return {
                'title': yt.title or "Unknown Title",
                'duration': yt.length or 0,
                'thumbnail': yt.thumbnail_url,
                'video_id': yt.video_id
            }
        except Exception as e:
            logger.error(f"Failed to get video info: {str(e)}")
            raise Exception("Could not fetch video details")
    
    async def search(self, query):
        """Safe YouTube search with fallbacks"""
        try:
            search = VideosSearch(query, limit=1)
            result = search.result()
            if not result or not result.get('result'):
                raise Exception("No results found")
            
            video = result['result'][0]
            return {
                'title': video.get('title'),
                'url': video.get('link'),
                'duration': video.get('duration'),
                'video_id': video.get('id')
            }
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise Exception("YouTube search failed")
    
    async def download(
        self,
        query: str,
        is_video: bool = False,
        is_video_id: bool = False
    ) -> str:
        """Main download method with comprehensive error handling"""
        try:
            if is_video_id:
                video_id = query
            else:
                video_id = extract_video_id(query)
                if not video_id:
                    # Try search if it's not a direct URL
                    result = await self.search(query)
                    video_id = extract_video_id(result['url'])
            
            if not validate_video_id(video_id):
                raise Exception("Invalid YouTube video ID")
            
            file_path = await download_media(video_id, audio_only=not is_video)
            return file_path
            
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            raise Exception(f"Could not download media: {str(e)}")

# Initialize API
YouTube = YouTubeAPI()
