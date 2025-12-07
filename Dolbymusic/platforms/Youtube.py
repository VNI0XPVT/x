import asyncio
import os
import re
from typing import Union, Optional
import httpx

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch


def time_to_seconds(time_str):
    """Convert time string (MM:SS or HH:MM:SS) to seconds"""
    if not time_str or time_str == "None":
        return 0
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0])


# API Configuration
API_BASE_URL = "https://youtubify.me"
API_KEY = "b8e7dc72a27d42719e73b46901ff24ad"
ENABLE_STREAMING = True
MAX_DOWNLOAD_SIZE_MB = 48
STREAM_MODE_DURATION_THRESHOLD = 1200


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    # ------------------------------------------------------------------------------------
    # UNIVERSAL FIX – FILTER OUT BROKEN RESULTS FROM youtubesearchpython
    # ------------------------------------------------------------------------------------
    async def safe_results(self, results):
        """Return only valid search results and skip corrupted ones."""
        try:
            raw = (await results.next()).get("result", [])
        except Exception:
            return []

        safe = []
        for r in raw:
            try:
                channel_id = r.get("channel", {}).get("id")
                if not channel_id:
                    continue  # SKIP corrupt entries
                safe.append(r)
            except:
                continue

        return safe

    # ------------------------------------------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    # ------------------------------------------------------------------------------------
    # FIXED DETAILS()
    # ------------------------------------------------------------------------------------
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        safe = await self.safe_results(results)
        if not safe:
            return None, None, 0, None, None

        result = safe[0]

        title = result["title"]
        duration_min = result["duration"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        duration_sec = time_to_seconds(duration_min)

        return title, duration_min, duration_sec, thumbnail, vidid

    # ------------------------------------------------------------------------------------
    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        safe = await self.safe_results(results)
        if not safe:
            return None
        return safe[0]["title"]

    # ------------------------------------------------------------------------------------
    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        safe = await self.safe_results(results)
        if not safe:
            return None
        return safe[0]["duration"]

    # ------------------------------------------------------------------------------------
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        safe = await self.safe_results(results)
        if not safe:
            return None
        return safe[0]["thumbnails"][0]["url"].split("?")[0]

    # ------------------------------------------------------------------------------------
    # FIXED TRACK()
    # ------------------------------------------------------------------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        safe = await self.safe_results(results)
        if not safe:
            return None, None

        result = safe[0]

        track_details = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, result["id"]

    # ------------------------------------------------------------------------------------
    # FIXED SLIDER()
    # ------------------------------------------------------------------------------------
    async def slider(self, link, query_type, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        results = VideosSearch(link, limit=10)
        safe = await self.safe_results(results)

        if not safe or query_type >= len(safe):
            return None, None, None, None

        result = safe[query_type]
        title = result["title"]
        duration = result["duration"]
        thumb = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]

        return title, duration, thumb, vidid

    # ------------------------------------------------------------------------------------
    # STREAM / PLAYBACK URL BUILDERS
    # ------------------------------------------------------------------------------------
    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1]
        stream_url = f"{API_BASE_URL}/download/video?video_id={vid}&mode=stream&max_res=720&api_key={API_KEY}"
        return 1, stream_url

    async def stream_url(self, link: str, videoid=False, video=False):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1]

        if video:
            return f"{API_BASE_URL}/download/video?video_id={vid}&max_res=720&api_key={API_KEY}"
        return f"{API_BASE_URL}/download/audio?video_id={vid}&api_key={API_KEY}"

    # ------------------------------------------------------------------------------------
    # PLAYLIST PARSE
    # ------------------------------------------------------------------------------------
    async def playlist(self, link, limit, user_id, videoid=False):
        if videoid:
            link = self.listbase + link
        link = link.split("&")[0]

        playlist_id = link.split("list=")[-1] if "list=" in link else ""

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"{API_BASE_URL}/playlist"
                params = {"playlist_id": playlist_id, "limit": limit, "api_key": API_KEY}
                r = await client.get(url, params=params)
                if r.status_code == 200:
                    return r.json().get("video_ids", [])
        except:
            pass

        return []

    # ------------------------------------------------------------------------------------
    # DOWNLOAD FUNCTION (UNCHANGED BUT CLEANED)
    # ------------------------------------------------------------------------------------
    async def download(
        self,
        link: str,
        mystic,
        video=False,
        videoid=False,
        songaudio=False,
        songvideo=False,
        format_id=False,
        title=False,
    ):
        if videoid:
            link = self.base + link

        vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1]

        # USE STREAMING MODE FOR LONG VIDEOS
        duration_seconds = 0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{API_BASE_URL}/info", params={"video_id": vid, "api_key": API_KEY})
                if r.status_code == 200:
                    duration_str = r.json().get("duration", "0:0")
                    parts = duration_str.split(":")
                    if len(parts) == 3:
                        duration_seconds = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_seconds = int(parts[0])*60 + int(parts[1])
                    else:
                        duration_seconds = int(parts[0])
        except:
            pass

        # Stream for long videos
        if ENABLE_STREAMING and duration_seconds > STREAM_MODE_DURATION_THRESHOLD:
            if video:
                return f"{API_BASE_URL}/download/video?video_id={vid}&max_res=720&api_key={API_KEY}"
            return f"{API_BASE_URL}/download/audio?video_id={vid}&api_key={API_KEY}"

        # -----------------------------------------------------------------------------
        # SHORT VIDEO DOWNLOADS
        # -----------------------------------------------------------------------------

        async def api_download_audio():
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
                    url = f"{API_BASE_URL}/download/audio"
                    params = {"video_id": vid, "mode": "download", "no_redirect": "1", "api_key": API_KEY}

                    info = await client.get(f"{API_BASE_URL}/info", params={"video_id": vid, "api_key": API_KEY})
                    file_title = info.json().get("title", vid) if info.status_code == 200 else vid

                    safe_title = re.sub(r'[<>:"/\\|?*]', '', file_title)[:100]
                    filepath = f"downloads/{safe_title}.mp3"

                    os.makedirs("downloads", exist_ok=True)

                    async with client.stream("GET", url, params=params) as r:
                        if r.status_code != 200:
                            return None
                        with open(filepath, "wb") as f:
                            async for chunk in r.aiter_bytes(1024*128):
                                f.write(chunk)

                    return filepath
            except:
                return None

        async def api_download_video():
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
                    url = f"{API_BASE_URL}/download/video"
                    params = {"video_id": vid, "mode": "download", "no_redirect": "1", "max_res": "720", "api_key": API_KEY}

                    info = await client.get(f"{API_BASE_URL}/info", params={"video_id": vid, "api_key": API_KEY})
                    file_title = info.json().get("title", vid) if info.status_code == 200 else vid

                    safe_title = re.sub(r'[<>:"/\\|?*]', '', file_title)[:100]
                    filepath = f"downloads/{safe_title}.mp4"

                    os.makedirs("downloads", exist_ok=True)

                    async with client.stream("GET", url, params=params) as r:
                        if r.status_code != 200:
                            return None
                        with open(filepath, "wb") as f:
                            async for chunk in r.aiter_bytes(1024*128):
                                f.write(chunk)

                    return filepath
            except:
                return None

        # Custom song downloads
        if songvideo or songaudio:
            if songvideo:
                return await api_download_video()
            else:
                return await api_download_audio()

        # Standard downloads
        if video:
            f = await api_download_video()
            return (f, True)
        else:
            f = await api_download_audio()
            return (f, True)
