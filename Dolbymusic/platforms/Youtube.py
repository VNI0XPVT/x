import re
import os
import asyncio
import time
import random
from typing import Union, Optional, Dict, Tuple
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
        self._request_delay = 2.5
        
        # Client configurations
        self.clients = ['WEB', 'ANDROID', 'IOS', 'MWEB', 'WEB_MOBILE']
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15'
        ]

    async def url(self, message) -> Optional[str]:
        """Extract YouTube URL from Pyrogram message"""
        try:
            text = getattr(message, 'text', '') or getattr(message, 'caption', '')
            if not text:
                return None

            # Check entities first
            entities = getattr(message, 'entities', []) or getattr(message, 'caption_entities', [])
            for entity in entities:
                if getattr(entity, 'type', '') == "url":
                    return text[entity.offset:entity.offset + entity.length]
                elif getattr(entity, 'type', '') == "text_link":
                    return getattr(entity, 'url', None)

            # Fallback to regex
            youtube_pattern = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)[\w-]+'
            match = re.search(youtube_pattern, text)
            return match.group(0) if match else None
        except Exception as e:
            logger.error(f"URL extraction error: {e}")
            return None

    async def track(self, query: str, videoid: Union[bool, str] = False) -> Tuple[Dict, Optional[str]]:
        """Get track information - either from URL or search"""
        try:
            if videoid:
                link = self.base_url + str(query)
            elif self._is_youtube_url(query):
                link = query
            else:
                # Perform search
                search_result = await self._search(query)
                link = search_result['url']

            # Get video details
            title, duration, _, thumbnail, vidid = await self.details(link)
            
            return {
                "title": title or "Unknown Title",
                "link": link,
                "vidid": vidid,
                "duration_min": duration or "0:00",
                "thumb": thumbnail
            }, vidid
            
        except Exception as e:
            logger.error(f"Failed to get track info: {e}")
            return {
                "title": None,
                "link": None,
                "vidid": None,
                "duration_min": None,
                "thumb": None
            }, None

    async def details(self, link: str, videoid: Union[bool, str] = False) -> Tuple:
        """Get video details"""
        if videoid:
            link = self.base_url + str(link)
        
        video_id = self._extract_video_id(link)
        if not video_id:
            return None, None, None, None, None
        
        try:
            yt = await self._get_yt_object(link)
            title = getattr(yt, 'title', 'Unknown Title')
            duration = getattr(yt, 'length', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration > 0 else "0:00"
            thumbnail = getattr(yt, 'thumbnail_url', None)
            return title, duration_str, duration, thumbnail, video_id
        except Exception as e:
            logger.error(f"Failed to get details: {e}")
            return None, None, None, None, None

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
    ) -> Tuple[str, bool]:
        """Download YouTube media with all required parameters"""
        try:
            # Determine video ID
            if videoid:
                video_id = str(query)
            else:
                video_id = self._extract_video_id(query)
                if not video_id:
                    search_result = await self._search(query)
                    video_id = self._extract_video_id(search_result['url'])

            if not self._validate_video_id(video_id):
                raise Exception("Invalid YouTube video ID")

            # Determine if we want video
            want_video = video or songvideo
            url = f"{self.base_url}{video_id}"
            
            # Get YouTube object
            yt = await self._get_yt_object(url)
            
            # Stream selection
            if want_video:
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
                ext = 'mp4'
            else:
                stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                ext = 'mp3'

            if not stream:
                raise Exception("No suitable stream found")

            # Download to temp file
            temp_dir = os.path.join(os.getcwd(), "temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{video_id}.{ext}")
            
            if mystic:
                await mystic.edit("📥 Downloading...")
                
            stream.download(output_path=temp_dir, filename=video_id)
            
            if not os.path.exists(temp_path):
                raise Exception("Download failed - file not created")

            return temp_path, True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise Exception(f"Failed to download: {str(e)}")

    async def _search(self, query: str) -> Dict:
        """Perform YouTube search"""
        try:
            search = VideosSearch(query, limit=1)
            result = search.result()
            if not result or not result.get("result"):
                raise Exception("No results found")
            
            video = result["result"][0]
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
        """Create YouTube object with bot avoidance"""
        # Rate limiting
        current_time = time.time()
        if current_time - self._last_request < self._request_delay:
            time.sleep(self._request_delay)
        self._last_request = current_time

        # Try cached session first
        if url in self._session_cache:
            try:
                if self._session_cache[url].video_id:
                    return self._session_cache[url]
            except:
                del self._session_cache[url]

        # Create new session with random configuration
        yt = PyTubeYT(
            url,
            use_oauth=False,
            allow_oauth_cache=False,
            use_po_token=True,
            client=random.choice(self.clients),
            headers={
                'User-Agent': random.choice(self.user_agents),
                'Accept-Language': 'en-US,en;q=0.9'
            }
        )

        # Test connection
        if not yt.video_id:
            raise Exception("Failed to initialize YouTube object")

        self._session_cache[url] = yt
        return yt

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match and self._validate_video_id(match.group(1)):
                return match.group(1)
        return None

    def _validate_video_id(self, video_id: str) -> bool:
        """Validate YouTube video ID format"""
        return bool(re.match(r'^[a-zA-Z0-9_-]{11}$', video_id))

    def _is_youtube_url(self, text: str) -> bool:
        """Check if text is a YouTube URL"""
        if not text:
            return False
        patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+'
        ]
        return any(re.search(pattern, text) for pattern in patterns)

# Initialize the API
YouTube = YouTubeAPI()
