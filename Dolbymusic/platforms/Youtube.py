import re
import os
import asyncio
import functools
from typing import Union
from urllib.parse import urlparse, parse_qs

try:
    from pytubefix import YouTube, Playlist
    PYTUBEFIX_AVAILABLE = True
except ImportError:
    PYTUBEFIX_AVAILABLE = False
    print("Warning: pytubefix not available, YouTube functionality may be limited")

try:
    from youtubesearchpython.__future__ import VideosSearch
    YOUTUBE_SEARCH_AVAILABLE = True
except ImportError:
    YOUTUBE_SEARCH_AVAILABLE = False
    print("Warning: youtubesearchpython not available, search functionality may be limited")

YOUTUBE_URL_RE = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
)

def is_youtube_url(text: str) -> bool:
    if not isinstance(text, str):
        return False
    return bool(YOUTUBE_URL_RE.match(text.strip()))

async def get_file_with_pytubefix(video_id, audio=True):
    if not PYTUBEFIX_AVAILABLE:
        raise Exception("pytubefix not available")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(sync_download, video_id, audio))

def sync_download(video_id, audio=True):
    from pytubefix import YouTube as PyTubeYT
    url = f"https://www.youtube.com/watch?v={video_id}"
    yt = PyTubeYT(url)
    os.makedirs("downloads", exist_ok=True)
    if audio:
        stream = yt.streams.filter(only_audio=True).first()
        ext = "mp3"
    else:
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        ext = "mp4"
    if stream is None:
        raise Exception("No suitable stream found for download")
    file_path = f"downloads/{video_id}.{ext}"
    stream.download(output_path="downloads", filename=f"{video_id}.{ext}")
    return file_path

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        return is_youtube_url(link)

    async def url(self, message_1) -> Union[str, None]:
        messages = [message_1]
        if hasattr(message_1, "reply_to_message") and getattr(message_1, "reply_to_message", None):
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            entities = getattr(message, "entities", None) or []
            caption_entities = getattr(message, "caption_entities", None) or []
            if offset:
                break
            if entities:
                for entity in entities:
                    etype = getattr(entity, "type", None)
                    if hasattr(etype, "name"):
                        etype = etype.name
                    if etype == "URL":
                        text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
                        offset, length = entity.offset, entity.length
                        break
            if caption_entities:
                for entity in caption_entities:
                    etype = getattr(entity, "type", None)
                    if hasattr(etype, "name"):
                        etype = etype.name
                    if etype == "TEXT_LINK":
                        return getattr(entity, "url", None)
        if offset is None or not text:
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        if not link or not isinstance(link, str):
            return None, None, None, None, None
        if "&" in link:
            link = link.split("&")[0]
        try:
            if not PYTUBEFIX_AVAILABLE:
                raise Exception("pytubefix not available")
            from pytubefix import YouTube as PyTubeYT
            yt = PyTubeYT(link)
            title = yt.title
            duration_sec = getattr(yt, "length", None)
            if duration_sec is not None:
                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            else:
                duration_min = None
            thumbnail = yt.thumbnail_url
            vidid = yt.video_id
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            print(f"Failed to fetch details: {e}")
            return None, None, None, None, None

    async def track(self, query: str, videoid: Union[bool, str] = None):
        link = None
        if videoid:
            link = self.base + str(query)
        elif is_youtube_url(query):
            link = query
        else:
            try:
                if not YOUTUBE_SEARCH_AVAILABLE:
                    raise Exception("youtubesearchpython not available")
                from youtubesearchpython.__future__ import VideosSearch
                search = VideosSearch(query, limit=1)
                results = await search.next()
                if not results or "result" not in results or not results["result"]:
                    raise Exception("No YouTube results found")
                first = results["result"][0]
                link = first.get("link")
            except Exception as e:
                print(f"Failed to search YouTube: {e}")
                return {
                    "title": None,
                    "link": None,
                    "vidid": None,
                    "duration_min": None,
                    "thumb": None
                }, None
        
        title, duration_min, duration_sec, thumbnail, vidid = await self.details(link)
        if not vidid:
            return {
                "title": None,
                "link": None,
                "vidid": None,
                "duration_min": None,
                "thumb": None
            }, None
        
        track_details = {
            "title": title,
            "link": link,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + str(link)
        if "&" in link:
            link = link.split("&")[0]
        try:
            if not PYTUBEFIX_AVAILABLE:
                raise Exception("pytubefix not available")
            from pytubefix import Playlist as PyTubePlaylist
            pl = PyTubePlaylist(link)
            ids = [video.video_id for video in pl.videos[:limit]]
            return ids
        except Exception as e:
            print(f"Failed to fetch playlist: {e}")
            return []

    async def slider(self, query: str, query_type: int, videoid: Union[bool, str] = None):
        try:
            if not YOUTUBE_SEARCH_AVAILABLE:
                raise Exception("youtubesearchpython not available")
            from youtubesearchpython.__future__ import VideosSearch
            search = VideosSearch(query, limit=10)
            results = await search.next()
            if not results or "result" not in results or not results["result"]:
                raise Exception("No YouTube results found")
            result = results["result"]
            if query_type >= len(result):
                raise Exception("Requested index out of search result range")
            first = result[query_type]
            title = first.get("title")
            duration_min = first.get("duration")
            vidid = first.get("id")
            thumbnail = first.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
            return title, duration_min, thumbnail, vidid
        except Exception as e:
            print(f"Failed to slider-search YouTube: {e}")
            return None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        """Get video title"""
        title, _, _, _, _ = await self.details(link, videoid)
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        """Get video duration"""
        _, duration_min, _, _, _ = await self.details(link, videoid)
        return duration_min

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        """Get video thumbnail"""
        _, _, _, thumbnail, _ = await self.details(link, videoid)
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Download video and return path"""
        try:
            if videoid:
                video_id = str(link)
            else:
                # Extract video ID from URL
                if "&" in link:
                    link = link.split("&")[0]
                url_data = urlparse(link)
                if url_data.hostname and "youtube" in url_data.hostname:
                    query = parse_qs(url_data.query)
                    video_id = query.get("v", [None])[0]
                elif url_data.hostname == "youtu.be":
                    video_id = url_data.path[1:]
                else:
                    video_id = link

            if not PYTUBEFIX_AVAILABLE:
                return 0, "pytubefix not available"
            
            file_path = await get_file_with_pytubefix(video_id, audio=False)
            return 1, file_path
        except Exception as e:
            print(f"Failed to download video: {e}")
            return 0, str(e)

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        """Get available formats for a video"""
        try:
            if not PYTUBEFIX_AVAILABLE:
                return [], link
            
            if videoid:
                link = self.base + str(link)
            if "&" in link:
                link = link.split("&")[0]
            
            loop = asyncio.get_event_loop()
            formats_available = await loop.run_in_executor(None, self._get_formats_sync, link)
            return formats_available, link
        except Exception as e:
            print(f"Failed to get formats: {e}")
            return [], link

    def _get_formats_sync(self, link):
        """Synchronous helper for getting formats"""
        try:
            from pytubefix import YouTube as PyTubeYT
            yt = PyTubeYT(link)
            formats_available = []
            
            for stream in yt.streams:
                if stream.mime_type:
                    format_info = {
                        "format": f"{stream.resolution or 'audio'} - {stream.mime_type}",
                        "filesize": stream.filesize or 0,
                        "format_id": str(stream.itag),
                        "ext": stream.mime_type.split('/')[-1] if stream.mime_type else "unknown",
                        "format_note": stream.resolution or "audio",
                        "yturl": link,
                    }
                    formats_available.append(format_info)
            
            return formats_available
        except Exception as e:
            print(f"Error getting formats: {e}")
            return []

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
        """Download audio/video from YouTube"""
        try:
            if videoid:
                video_id = str(link)
            else:
                # Extract video ID from URL
                if "&" in link:
                    link = link.split("&")[0]
                url_data = urlparse(link)
                if url_data.hostname and "youtube" in url_data.hostname:
                    query = parse_qs(url_data.query)
                    video_id = query.get("v", [None])[0]
                elif url_data.hostname == "youtu.be":
                    video_id = url_data.path[1:]
                else:
                    video_id = link

            if not PYTUBEFIX_AVAILABLE:
                raise Exception("pytubefix not available")

            # Determine if we want audio or video
            want_video = bool(songvideo or video)
            file_path = await get_file_with_pytubefix(video_id, audio=not want_video)
            
            return file_path, True
        except Exception as e:
            print(f"Failed to download: {e}")
            return None, False

YouTube = YouTubeAPI()

# Simple test when run directly
if __name__ == "__main__":
    import asyncio
    
    async def test():
        yt = YouTubeAPI()
        print("YouTube API created successfully")
        
        # Test URL validation
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = await yt.exists(test_url)
        print(f"URL test: {test_url} -> {result}")
        
        # Test details (only if dependencies are available)
        if PYTUBEFIX_AVAILABLE:
            print("Testing video details...")
            try:
                title, duration_min, duration_sec, thumbnail, vidid = await yt.details(test_url)
                print(f"Title: {title or 'N/A'}")
                print(f"Duration: {duration_min or 'N/A'}")
                print(f"Video ID: {vidid or 'N/A'}")
            except Exception as e:
                print(f"Details test failed: {e}")
        else:
            print("Skipping details test - pytubefix not available")
    
    asyncio.run(test())
