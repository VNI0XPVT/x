import re
import os
import asyncio
import time
import random
from typing import Union, Optional
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

class YouTubeAPI:
    def __init__(self):
        self.base_url = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self._session_cache = {}
        self._last_request = 0
        self._request_delay = 2.5  # More conservative delay
        
        # Enhanced client configurations
        self.clients = ['WEB', 'ANDROID', 'IOS', 'MWEB', 'WEB_MOBILE']
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
            'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36'
        ]

    async def url(self, message) -> Optional[str]:
        """Extract YouTube URL from Pyrogram message with enhanced detection"""
        try:
            text = getattr(message, 'text', '') or getattr(message, 'caption', '')
            if not text:
                return None

            # Check entities first
            entities = getattr(message, 'entities', []) or getattr(message, 'caption_entities', [])
            for entity in entities:
                if getattr(entity, 'type', '') == "url":
                    url = text[entity.offset:entity.offset + entity.length]
                    if self._is_youtube_url(url):
                        return url
                elif getattr(entity, 'type', '') == "text_link":
                    url = getattr(entity, 'url', '')
                    if self._is_youtube_url(url):
                        return url

            # Enhanced regex pattern
            youtube_pattern = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)[\w-]+)'
            match = re.search(youtube_pattern, text)
            return match.group(0) if match else None

        except Exception as e:
            logger.error(f"URL extraction error: {e}")
            return None

    async def download(
        self,
        query: str,
        mystic=None,
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: Optional[str] = None,
        title: Optional[str] = None
    ) -> tuple:
        """Fixed download method with proper parameter handling"""
        try:
            # Determine if we're using video ID or need to search
            if videoid:
                video_id = query
            else:
                video_id = self._extract_video_id(query)
                if not video_id:
                    # Perform search if it's not a direct URL
                    search_result = await self._search_youtube(query)
                    video_id = self._extract_video_id(search_result['url'])

            if not self._validate_video_id(video_id):
                raise Exception("Invalid YouTube video ID")

            # Determine if we want video or audio
            want_video = video or songvideo
            url = f"{self.base_url}{video_id}"
            
            # Get YouTube object with bot avoidance
            yt = await self._get_yt_object(url)
            
            # Stream selection with multiple fallbacks
            if want_video:
                stream = (
                    yt.streams.filter(progressive=True, file_extension='mp4')
                    .order_by('resolution').desc().first() or
                    yt.streams.filter(adaptive=True, type='video')
                    .order_by('resolution').desc().first() or
                    yt.streams.get_highest_resolution()
                )
                ext = 'mp4'
            else:
                stream = (
                    yt.streams.filter(only_audio=True)
                    .order_by('abr').desc().first() or
                    yt.streams.filter(adaptive=True, type='audio')
                    .order_by('abr').desc().first() or
                    yt.streams.get_audio_only()
                )
                ext = 'mp3'

            if not stream:
                raise Exception("No suitable stream found")

            # Create temp directory
            temp_dir = os.path.join(os.getcwd(), "temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{video_id}.{ext}")
            
            # Download with progress if mystic is provided
            if mystic:
                await mystic.edit("📥 Downloading...")
                
            stream.download(output_path=temp_dir, filename=video_id)
            
            if not os.path.exists(temp_path):
                raise Exception("Download failed - file not created")

            return temp_path, True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise Exception(f"Failed to download: {str(e)}")

    async def _search_youtube(self, query: str) -> dict:
        """Enhanced YouTube search with better error handling"""
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
            logger.error(f"Search failed: {e}")
            raise Exception("YouTube search failed")

    async def _get_yt_object(self, url: str):
        """Create YouTube object with advanced bot avoidance"""
        # Rate limiting
        current_time = time.time()
        if current_time - self._last_request < self._request_delay:
            delay = self._request_delay - (current_time - self._last_request)
            time.sleep(delay + random.uniform(0, 0.3))  # Add jitter
        self._last_request = time.time()

        # Try cached session first
        if url in self._session_cache:
            try:
                if self._session_cache[url].video_id:
                    return self._session_cache[url]
            except:
                del self._session_cache[url]

        # Create new session with random configuration
        params = {
            'use_oauth': False,
            'allow_oauth_cache': False,
            'use_po_token': True,
            'client': random.choice(self.clients),
            'headers': {
                'User-Agent': random.choice(self.user_agents),
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com'
            }
        }

        # Try multiple times with different configurations
        for attempt in range(3):
            try:
                yt = PyTubeYT(url, **params)
                # Test the connection
                if not yt.video_id:
                    raise Exception("Empty video ID")
                
                self._session_cache[url] = yt
                return yt
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < 2:
                    time.sleep(2 ** attempt)  # Exponential backoff
                # Rotate client for next attempt
                params['client'] = random.choice(
                    [c for c in self.clients if c != params['client']]
                )

        raise Exception("YouTube API request blocked (bot detected)")

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Robust video ID extraction"""
        if not url:
            return None
            
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match and self._validate_video_id(match.group(1)):
                return match.group(1)
        return None

    def _validate_video_id(self, video_id: str) -> bool:
        """Validate YouTube video ID format"""
        return bool(re.match(r'^[a-zA-Z0-9_-]{11}$', video_id)) if video_id else False

    def _is_youtube_url(self, text: str) -> bool:
        """Check if text is a YouTube URL"""
        if not text:
            return False
        patterns = [
            r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)[\w-]+'
        ]
        return any(re.search(pattern, text) for pattern in patterns)

# Initialize the API
YouTube = YouTubeAPI()
