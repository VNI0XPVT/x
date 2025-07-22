import re
import os
import asyncio
import time
import random
from typing import Union
from urllib.parse import urlparse, parse_qs
from pytubefix import YouTube as PyTubeYT
from pytubefix.exceptions import VideoUnavailable, LiveStreamError
from youtubesearchpython import VideosSearch

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self._session_cache = {}
        self._last_request = 0
        self._request_delay = 2.0  # seconds

    async def url(self, message) -> Union[str, None]:
        """Extract YouTube URL from Pyrogram message object"""
        try:
            # Get message text or caption
            text = getattr(message, 'text', '') or getattr(message, 'caption', '')
            if not text:
                return None

            # Check entities first (for marked URLs)
            entities = getattr(message, 'entities', []) or getattr(message, 'caption_entities', [])
            for entity in entities:
                if getattr(entity, 'type', '') == "url":
                    return text[entity.offset:entity.offset + entity.length]
                elif getattr(entity, 'type', '') == "text_link":
                    return getattr(entity, 'url', None)

            # Fallback to regex search
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
        except Exception as e:
            print(f"URL extraction error: {e}")
            return None

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        """Check if YouTube link exists"""
        if videoid:
            link = self.base + str(link)
        return self._extract_video_id(link) is not None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        """Get video details"""
        if videoid:
            link = self.base + str(link)
        
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
            print(f"Failed to get details: {e}")
            return None, None, None, None, None

    async def track(self, query: str, videoid: Union[bool, str] = None):
        """Search for a track"""
        if videoid:
            link = self.base + str(query)
        elif self._is_youtube_url(query):
            link = query
        else:
            try:
                search = VideosSearch(query, limit=1)
                result = search.result()
                if not result or not result.get("result"):
                    raise Exception("No results found")
                link = result["result"][0].get("link")
            except Exception as e:
                print(f"Search failed: {e}")
                return {"title": None, "link": None, "vidid": None, "duration_min": None, "thumb": None}, None
        
        title, duration, _, thumb, vidid = await self.details(link)
        return {
            "title": title or "Unknown Title",
            "link": link,
            "vidid": vidid,
            "duration_min": duration or "0:00",
            "thumb": thumb
        }, vidid

    async def download(self, link: str, videoid: Union[bool, str] = None, is_video: bool = False):
        """Download YouTube media"""
        try:
            if videoid:
                video_id = str(link)
            else:
                video_id = self._extract_video_id(link)
                if not video_id:
                    raise Exception("Invalid YouTube URL")
            
            url = f"{self.base}{video_id}"
            yt = await self._get_yt_object(url)
            
            if is_video:
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
                ext = 'mp4'
            else:
                stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                ext = 'mp3'
            
            if not stream:
                raise Exception("No suitable stream found")
            
            # Create temp directory
            temp_dir = os.path.join(os.getcwd(), "temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{video_id}.{ext}")
            
            stream.download(output_path=temp_dir, filename=video_id)
            return temp_path, True
            
        except Exception as e:
            print(f"Download failed: {e}")
            raise Exception(f"Download error: {str(e)}")

    def _extract_video_id(self, url: str) -> Union[str, None]:
        """Extract video ID from URL"""
        if not url:
            return None
            
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
        return bool(re.match(r'^[a-zA-Z0-9_-]{11}$', video_id)) if video_id else False

    def _is_youtube_url(self, text: str) -> bool:
        """Check if text is a YouTube URL"""
        if not text:
            return False
        patterns = [
            r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'^https?://youtu\.be/[\w-]+',
            r'^https?://(?:www\.)?youtube\.com/embed/[\w-]+'
        ]
        return any(re.match(pattern, text) for pattern in patterns)

    async def _get_yt_object(self, url: str):
        """Create YouTube object with bot avoidance"""
        # Rate limiting
        current_time = time.time()
        if current_time - self._last_request < self._request_delay:
            time.sleep(self._request_delay)
        self._last_request = current_time

        # Try cached session
        if url in self._session_cache:
            try:
                if self._session_cache[url].video_id:
                    return self._session_cache[url]
            except:
                del self._session_cache[url]

        # Create new session
        yt = PyTubeYT(
            url,
            use_oauth=False,
            allow_oauth_cache=False,
            use_po_token=True,
            client=random.choice(['WEB', 'ANDROID', 'IOS']),
            headers={
                'User-Agent': random.choice([
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15'
                ])
            }
        )

        # Test connection
        if not yt.video_id:
            raise Exception("Failed to initialize YouTube object")

        self._session_cache[url] = yt
        return yt

# Initialize the API
YouTube = YouTubeAPI()
