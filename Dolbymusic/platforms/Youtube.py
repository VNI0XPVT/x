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
from cachetools import TTLCache
import pytubefix
from pytubefix import YouTube as PyTubeYT, Playlist
from pytubefix.exceptions import VideoUnavailable, LiveStreamError
from youtubesearchpython import VideosSearch

# Configuration
CACHE_MAXSIZE = 100
CACHE_TTL = 3600  # 1 hour
MAX_RETRIES = 3
MIN_REQUEST_DELAY = 1.5  # seconds

# Global caches and state
_youtube_session_cache = {}
_last_request_time = 0
video_cache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

# Client configurations
CLIENTS = ['WEB', 'ANDROID', 'IOS', 'MWEB']
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

# Utility functions
def get_random_user_agent():
    return random.choice(USER_AGENTS)

def exponential_backoff(attempt):
    max_wait = 60  # Maximum wait time in seconds
    wait_time = min(math.pow(2, attempt), max_wait)
    time.sleep(wait_time + random.uniform(0, 1))  # Add jitter

def enforce_rate_limit():
    global _last_request_time
    current_time = time.time()
    elapsed = current_time - _last_request_time
    
    if elapsed < MIN_REQUEST_DELAY:
        sleep_time = MIN_REQUEST_DELAY - elapsed
        time.sleep(sleep_time)
    
    _last_request_time = time.time()

def validate_youtube_video_id(video_id):
    if not video_id or not isinstance(video_id, str):
        return False
    if len(video_id) != 11:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', video_id))

def extract_video_id_from_url(url):
    if not url or not isinstance(url, str):
        return None
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/.*[?&]v=([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            if validate_youtube_video_id(video_id):
                return video_id
    
    return None

def cleanup_old_downloads():
    try:
        downloads_dir = os.path.join(os.getcwd(), "downloads")
        if os.path.exists(downloads_dir):
            current_time = time.time()
            for filepath in glob.glob(os.path.join(downloads_dir, "*")):
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getctime(filepath)
                    if file_age > 3600:  # 1 hour
                        try:
                            os.remove(filepath)
                        except:
                            pass
    except:
        pass

atexit.register(cleanup_old_downloads)

# Core YouTube functions
def get_yt_object(url):
    """Create YouTube object with bot avoidance strategies"""
    params = {
        'use_oauth': False,
        'allow_oauth_cache': False,
        'use_po_token': True,
        'client': random.choice(CLIENTS),
        'headers': {'User-Agent': get_random_user_agent()}
    }
    
    # Check cache first
    cached = video_cache.get(url)
    if cached:
        try:
            # Verify cached object is still valid
            _ = cached.title
            return cached
        except:
            # Cache expired, remove it
            video_cache.pop(url, None)
    
    # Try multiple approaches
    for attempt in range(MAX_RETRIES):
        try:
            enforce_rate_limit()
            
            # Rotate client for each attempt
            params['client'] = random.choice([c for c in CLIENTS if c != params.get('client')])
            
            yt = PyTubeYT(url, **params)
            
            # Test the object
            _ = yt.title
            
            # Cache successful object
            video_cache[url] = yt
            return yt
            
        except (VideoUnavailable, LiveStreamError) as e:
            raise Exception(f"Video unavailable or live stream: {str(e)}")
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                exponential_backoff(attempt)
    
    raise Exception(f"Failed to create YouTube object after {MAX_RETRIES} attempts")

def sync_download(video_id, audio=True):
    """Download YouTube video/audio with robust error handling"""
    try:
        if not validate_youtube_video_id(video_id):
            raise Exception(f"Invalid YouTube video ID: {video_id}")
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Downloading: {url}")
        
        yt = get_yt_object(url)
        
        # Stream selection with fallbacks
        if audio:
            stream = (
                yt.streams.filter(only_audio=True).order_by('abr').last() or
                yt.streams.filter(only_audio=True).first() or
                yt.streams.filter(adaptive=True, type='audio').first() or
                yt.streams.filter(progressive=True).first()
            )
            ext = "mp3"
        else:
            stream = (
                yt.streams.filter(progressive=True, file_extension='mp4')
                .order_by('resolution').desc().first() or
                yt.streams.filter(adaptive=True, type='video')
                .order_by('resolution').desc().first()
            )
            ext = "mp4"
        
        if not stream:
            raise Exception("No suitable stream found")
        
        # Create downloads directory if needed
        downloads_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Download to temp file first
        temp_path = os.path.join(downloads_dir, f"temp_{video_id}.{ext}")
        final_path = os.path.join(downloads_dir, f"{video_id}.{ext}")
        
        print(f"Downloading stream: {stream}")
        stream.download(output_path=downloads_dir, filename=f"temp_{video_id}.{ext}")
        
        # Verify download
        if not os.path.exists(temp_path):
            raise Exception("Download failed - file not created")
        
        # Rename temp file to final name
        os.rename(temp_path, final_path)
        
        return final_path
        
    except Exception as e:
        # Clean up any partial downloads
        temp_path = os.path.join(os.getcwd(), "downloads", f"temp_{video_id}.*")
        for f in glob.glob(temp_path):
            try:
                os.remove(f)
            except:
                pass
        raise Exception(f"Download error: {str(e)}")

async def get_file_with_pytubefix(video_id, audio=True):
    """Async wrapper for sync download"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        functools.partial(sync_download, video_id, audio)
    )

# YouTube API class
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        return bool(extract_video_id_from_url(link))

    async def url(self, message_1):
        messages = [message_1]
        if hasattr(message_1, "reply_to_message"):
            messages.append(message_1.reply_to_message)
        
        text = ""
        offset = None
        length = None
        
        for message in messages:
            entities = getattr(message, "entities", []) or []
            caption_entities = getattr(message, "caption_entities", []) or []
            
            if offset:
                break
                
            if entities:
                for entity in entities:
                    etype = getattr(entity, "type", "")
                    if etype == "URL":
                        text = getattr(message, "text", "") or getattr(message, "caption", "")
                        offset, length = entity.offset, entity.length
                        break
            
            if caption_entities:
                for entity in caption_entities:
                    etype = getattr(entity, "type", "")
                    if etype == "TEXT_LINK":
                        return getattr(entity, "url", None)
        
        if offset is None or not text:
            return None
            
        return text[offset:offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        if not link:
            return None, None, None, None, None
        
        video_id = extract_video_id_from_url(link)
        if not video_id:
            return None, None, None, None, None
        
        try:
            yt = get_yt_object(link)
            
            title = getattr(yt, 'title', 'Unknown Title')
            duration_sec = getattr(yt, 'length', 0)
            
            if duration_sec > 0:
                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            else:
                duration_min = "Live" if "live" in title.lower() else "0:00"
            
            thumbnail = getattr(yt, 'thumbnail_url', None)
            vidid = getattr(yt, 'video_id', None)
            
            return title, duration_min, duration_sec, thumbnail, vidid
            
        except Exception as e:
            print(f"Failed to get details: {e}")
            return None, None, None, None, None

    async def track(self, query: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(query)
        elif is_youtube_url(query):
            link = query
        else:
            try:
                search = VideosSearch(query, limit=1)
                results = search.result()
                if not results or not results.get("result"):
                    raise Exception("No results found")
                
                first = results["result"][0]
                link = first.get("link")
                if not link:
                    raise Exception("No link in search results")
                
            except Exception as e:
                print(f"Search failed: {e}")
                return {
                    "title": None,
                    "link": None,
                    "vidid": None,
                    "duration_min": None,
                    "thumb": None
                }, None
        
        title, duration_min, _, thumbnail, vidid = await self.details(link)
        
        return {
            "title": title or "Unknown Title",
            "link": link,
            "vidid": vidid,
            "duration_min": duration_min or "0:00",
            "thumb": thumbnail
        }, vidid

    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> tuple:
        try:
            if videoid:
                video_id = str(link)
            else:
                video_id = extract_video_id_from_url(link)
                if not video_id:
                    raise Exception("Could not extract video ID")
            
            want_video = bool(songvideo or video)
            file_path = await get_file_with_pytubefix(video_id, audio=not want_video)
            return file_path, True
            
        except Exception as e:
            error_msg = f"Failed to download {video_id if 'video_id' in locals() else link}: {e}"
            print(error_msg)
            raise Exception(error_msg)

# Initialize the API
YouTube = YouTubeAPI()
