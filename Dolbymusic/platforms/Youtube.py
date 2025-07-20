import re
import os
import asyncio
import functools
import tempfile
import atexit
import glob
from typing import Union
from urllib.parse import urlparse, parse_qs

# Cleanup function for downloaded files
def cleanup_old_downloads():
    """Clean up old downloaded files to save disk space"""
    try:
        downloads_dir = os.path.join(os.getcwd(), "downloads")
        if os.path.exists(downloads_dir):
            # Remove files older than 1 hour
            import time
            current_time = time.time()
            for filepath in glob.glob(os.path.join(downloads_dir, "*")):
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getctime(filepath)
                    if file_age > 3600:  # 1 hour in seconds
                        try:
                            os.remove(filepath)
                        except:
                            pass  # Ignore errors during cleanup
    except:
        pass  # Ignore cleanup errors

def validate_youtube_video_id(video_id):
    """Validate YouTube video ID format"""
    if not video_id or not isinstance(video_id, str):
        return False
    # YouTube video IDs are exactly 11 characters, alphanumeric plus - and _
    if len(video_id) != 11:
        return False
    # Check if it contains only valid characters
    valid_chars = re.match(r'^[a-zA-Z0-9_-]+$', video_id)
    return bool(valid_chars)

def extract_video_id_from_url(url):
    """Extract video ID from YouTube URL safely"""
    if not url or not isinstance(url, str):
        return None
    
    # Handle different YouTube URL formats
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

# Register cleanup function to run on exit
atexit.register(cleanup_old_downloads)

try:
    from pytubefix import YouTube, Playlist
    PYTUBEFIX_AVAILABLE = True
except ImportError:
    PYTUBEFIX_AVAILABLE = False
    print("Warning: pytubefix not available, YouTube functionality may be limited")

try:
    from youtubesearchpython import VideosSearch
    YOUTUBE_SEARCH_AVAILABLE = True
except ImportError:
    YOUTUBE_SEARCH_AVAILABLE = False
    print("Warning: youtube-search-python not available, search functionality may be limited")

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
    try:
        # Import Heroku utilities
        from Dolbymusic.utils.heroku_utils import get_safe_download_path, safe_file_path
    except ImportError:
        # Fallback if heroku_utils not available
        def get_safe_download_path():
            downloads_dir = os.path.join(os.getcwd(), "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            return downloads_dir
        
        def safe_file_path(filename):
            return os.path.join(get_safe_download_path(), filename)
    
    try:
        # Validate video_id first
        if not validate_youtube_video_id(video_id):
            raise Exception(f"Invalid YouTube video ID: {video_id}")
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Attempting to download: {url}")
        
        # Try multiple approaches to avoid bot detection
        yt = None
        approaches = [
            # Approach 1: Use po_token and WEB client
            lambda: PyTubeYT(url, use_po_token=True, client='WEB'),
            # Approach 2: Use WEB client without po_token
            lambda: PyTubeYT(url, client='WEB'),
            # Approach 3: Use different client (ANDROID)
            lambda: PyTubeYT(url, client='ANDROID'),
            # Approach 4: Default approach
            lambda: PyTubeYT(url)
        ]
        
        last_error = None
        for i, approach in enumerate(approaches, 1):
            try:
                print(f"Download trying approach {i}...")
                yt = approach()
                # Test if we can access basic properties
                _ = yt.title
                print(f"Download approach {i} successful!")
                break
            except Exception as e:
                print(f"Download approach {i} failed: {e}")
                last_error = e
                continue
        
        if yt is None:
            raise Exception(f"All download approaches failed. Last error: {last_error}")
        
        # Get safe download directory
        downloads_dir = get_safe_download_path()
        
        if audio:
            stream = yt.streams.filter(only_audio=True).first()
            ext = "mp3"
        else:
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            ext = "mp4"
            
        if stream is None:
            raise Exception("No suitable stream found for download")
            
        # Use safe file path
        filename = f"{video_id}.{ext}"
        file_path = safe_file_path(filename)
        
        # Download with error handling
        stream.download(output_path=downloads_dir, filename=filename)
        
        # Verify file was created
        if not os.path.exists(file_path):
            raise Exception(f"Download failed - file not created: {file_path}")
            
        return file_path
    except Exception as e:
        raise Exception(f"Download error: {str(e)}")

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
            
            # Try multiple approaches to avoid bot detection
            yt = None
            approaches = [
                # Approach 1: Use po_token and WEB client
                lambda: PyTubeYT(link, use_po_token=True, client='WEB'),
                # Approach 2: Use WEB client without po_token
                lambda: PyTubeYT(link, client='WEB'),
                # Approach 3: Use different client (ANDROID)
                lambda: PyTubeYT(link, client='ANDROID'),
                # Approach 4: Default approach
                lambda: PyTubeYT(link)
            ]
            
            last_error = None
            for i, approach in enumerate(approaches, 1):
                try:
                    print(f"Details trying approach {i}...")
                    yt = approach()
                    # Test if we can access basic properties
                    _ = yt.title
                    print(f"Details approach {i} successful!")
                    break
                except Exception as e:
                    print(f"Details approach {i} failed: {e}")
                    last_error = e
                    continue
            
            if yt is None:
                raise Exception(f"All approaches failed. Last error: {last_error}")
            
            title = yt.title or "Unknown Title"
            duration_sec = getattr(yt, "length", None)
            
            # Handle duration formatting more robustly
            if duration_sec is not None and duration_sec > 0:
                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            else:
                # Check if this might be a live stream
                if title and ("live" in title.lower() or "streaming" in title.lower() or "🔴" in title):
                    duration_min = "Live"
                    duration_sec = 0
                else:
                    # Default for videos with unknown duration
                    duration_min = "0:00"
                    duration_sec = 0
            
            thumbnail = yt.thumbnail_url
            vidid = yt.video_id
            
            # Validate video ID - but be more flexible
            if not vidid or not isinstance(vidid, str) or len(vidid) != 11:
                print(f"Warning: Unusual video ID format: {vidid}")
                # Don't fail completely - some videos might have non-standard IDs
                # but still be playable
                
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
                    print("WARNING: youtube-search-python not available!")
                    raise Exception("youtube-search-python not available")
                from youtubesearchpython import VideosSearch
                print(f"Searching YouTube for: {query}")
                search = VideosSearch(query, limit=1)
                results = search.result()
                print(f"Search results: {results}")
                if not results or "result" not in results or not results["result"]:
                    raise Exception("No YouTube results found")
                first = results["result"][0]
                link = first.get("link")
                print(f"Found link: {link}")
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
        print(f"Track details - Link: {link}, Video ID: {vidid}, Title: {title}")
        
        # Check if we got at least title and link - don't fail completely on missing vidid
        if not title and not link:
            print(f"No valid details found for link: {link}")
            return {
                "title": None,
                "link": None,
                "vidid": None,
                "duration_min": None,
                "thumb": None
            }, None
        
        # If duration_min is None but we have duration_sec, create duration_min
        if duration_min is None and duration_sec is not None and duration_sec > 0:
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
        
        # For live streams or videos without duration, set a default
        if duration_min is None:
            # Try to detect if it's actually a live stream
            if title and ("live" in title.lower() or "streaming" in title.lower()):
                duration_min = "Live"
            else:
                # Default duration for regular videos that might have missing duration info
                duration_min = "0:00"
        
        track_details = {
            "title": title or "Unknown Title",
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
                raise Exception("youtube-search-python not available")
            from youtubesearchpython import VideosSearch
            search = VideosSearch(query, limit=10)
            results = search.result()
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
                # Extract video ID from URL using our enhanced function
                video_id = extract_video_id_from_url(link)
                
                # Fallback to original logic if extract function fails
                if not video_id:
                    if "&" in link:
                        link = link.split("&")[0]
                    url_data = urlparse(link)
                    if url_data.hostname and "youtube" in url_data.hostname:
                        query = parse_qs(url_data.query)
                        potential_id = query.get("v", [None])[0]
                        if validate_youtube_video_id(potential_id):
                            video_id = potential_id
                    elif url_data.hostname == "youtu.be":
                        potential_id = url_data.path[1:]
                        if validate_youtube_video_id(potential_id):
                            video_id = potential_id
                    else:
                        # Last resort - assume the link is a video ID
                        if validate_youtube_video_id(link):
                            video_id = link

            # Final validation check
            if not video_id or not validate_youtube_video_id(video_id):
                return 0, f"Could not extract valid video ID from: {link}"

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
            
            # Try multiple approaches to avoid bot detection
            yt = None
            approaches = [
                # Approach 1: Use po_token and WEB client
                lambda: PyTubeYT(link, use_po_token=True, client='WEB'),
                # Approach 2: Use WEB client without po_token
                lambda: PyTubeYT(link, client='WEB'),
                # Approach 3: Use different client (ANDROID)
                lambda: PyTubeYT(link, client='ANDROID'),
                # Approach 4: Default approach
                lambda: PyTubeYT(link)
            ]
            
            last_error = None
            for i, approach in enumerate(approaches, 1):
                try:
                    print(f"Formats trying approach {i}...")
                    yt = approach()
                    # Test if we can access basic properties
                    _ = yt.title
                    print(f"Formats approach {i} successful!")
                    break
                except Exception as e:
                    print(f"Formats approach {i} failed: {e}")
                    last_error = e
                    continue
            
            if yt is None:
                raise Exception(f"All approaches failed. Last error: {last_error}")
            
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
            print(f"Download called with - Link: {link}, VideoID: {videoid}")
            
            if videoid:
                video_id = str(link)
            else:
                # Extract video ID from URL using our enhanced function
                video_id = extract_video_id_from_url(link)
                
                # Fallback to original logic if extract function fails
                if not video_id:
                    if "&" in link:
                        link = link.split("&")[0]
                    url_data = urlparse(link)
                    if url_data.hostname and "youtube" in url_data.hostname:
                        query = parse_qs(url_data.query)
                        potential_id = query.get("v", [None])[0]
                        if validate_youtube_video_id(potential_id):
                            video_id = potential_id
                    elif url_data.hostname == "youtu.be":
                        potential_id = url_data.path[1:]
                        if validate_youtube_video_id(potential_id):
                            video_id = potential_id
                    else:
                        # Last resort - assume the link is a video ID
                        if validate_youtube_video_id(link):
                            video_id = link

            print(f"Extracted video ID: {video_id}")
            
            # Final validation check
            if not video_id or not validate_youtube_video_id(video_id):
                raise Exception(f"Could not extract valid video ID from: {link}")

            if not PYTUBEFIX_AVAILABLE:
                raise Exception("pytubefix not available")

            # Determine if we want audio or video
            want_video = bool(songvideo or video)
            file_path = await get_file_with_pytubefix(video_id, audio=not want_video)
            
            return file_path, True
        except Exception as e:
            error_msg = f"Failed to download {video_id}: {e}"
            print(error_msg)
            raise Exception(error_msg)  # Raise exception instead of returning None

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
