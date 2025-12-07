import asyncio
import os
import re
from typing import Union, Optional
import httpx

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message


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

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS USING YOUR OWN API
    # -------------------------------------------------------------------------
    async def _search_first(self, query: str) -> Optional[dict]:
        """
        Call /search on your API:
        Returns dict with {id, title, url} or None.
        Works for:
        - plain text: "pal pal"
        - URLs
        - video IDs
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.get(
                    f"{API_BASE_URL}/search",
                    params={"q": query, "api_key": API_KEY},
                )
                if r.status_code != 200:
                    return None
                data = r.json()
                vid = data.get("id")
                if not vid:
                    return None
                return {
                    "id": vid,
                    "title": data.get("title") or vid,
                    "url": data.get("url") or f"https://www.youtube.com/watch?v={vid}",
                }
        except Exception:
            return None

    async def _info(self, video_id: str) -> dict:
        """
        Call /info to get metadata like duration/title/thumbnail.
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.get(
                    f"{API_BASE_URL}/info",
                    params={"video_id": video_id, "api_key": API_KEY},
                )
                if r.status_code != 200:
                    return {}
                return r.json() or {}
        except Exception:
            return {}

    # -------------------------------------------------------------------------
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
        return text[offset: offset + length]

    # -------------------------------------------------------------------------
    # DETAILS
    # -------------------------------------------------------------------------
    async def details(self, link: str, videoid: Union[bool, str] = None):
        """
        Returns: title, duration_min (str), duration_sec (int), thumbnail, vidid
        """
        # We can just use /search with whatever user typed: query, URL or ID
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        search = await self._search_first(link)
        if not search:
            return None, None, 0, None, None

        vidid = search["id"]
        info = await self._info(vidid)

        title = info.get("title") or search["title"]
        duration_min = info.get("duration")
        if not duration_min:
            duration_sec = 0
        else:
            duration_sec = time_to_seconds(duration_min)

        thumbnail = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

        return title, duration_min, duration_sec, thumbnail, vidid

    # -------------------------------------------------------------------------
    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        search = await self._search_first(link)
        if not search:
            return None

        info = await self._info(search["id"])
        return info.get("title") or search["title"]

    # -------------------------------------------------------------------------
    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        search = await self._search_first(link)
        if not search:
            return None
        info = await self._info(search["id"])
        return info.get("duration")

    # -------------------------------------------------------------------------
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        search = await self._search_first(link)
        if not search:
            return None
        vidid = search["id"]
        info = await self._info(vidid)
        return info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

    # -------------------------------------------------------------------------
    # TRACK
    # -------------------------------------------------------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None):
        """
        Used by /play etc.
        Returns (track_details dict, vidid)
        """
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        search = await self._search_first(link)
        if not search:
            return None, None

        vidid = search["id"]
        info = await self._info(vidid)

        title = info.get("title") or search["title"]
        duration_min = info.get("duration")
        thumb = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

        track_details = {
            "title": title,
            "link": search["url"],
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumb,
        }
        return track_details, vidid

    # -------------------------------------------------------------------------
    # SLIDER
    # (We just return the best match; query_type is ignored safely)
    # -------------------------------------------------------------------------
    async def slider(self, link, query_type, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        search = await self._search_first(link)
        if not search:
            return None, None, None, None

        vidid = search["id"]
        info = await self._info(vidid)

        title = info.get("title") or search["title"]
        duration = info.get("duration")
        thumb = info.get("thumbnail") or f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

        return title, duration, thumb, vidid

    # -------------------------------------------------------------------------
    # STREAM / PLAYBACK URL BUILDERS (unchanged)
    # -------------------------------------------------------------------------
    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        # We can still extract ID locally, since /download endpoints expect video_id
        if "v=" in link:
            vid = link.split("v=")[-1].split("&")[0]
        else:
            vid = link.split("/")[-1].split("?")[0]

        stream_url = f"{API_BASE_URL}/download/video?video_id={vid}&mode=stream&max_res=720&api_key={API_KEY}"
        return 1, stream_url

    async def stream_url(self, link: str, videoid=False, video=False):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        if "v=" in link:
            vid = link.split("v=")[-1].split("&")[0]
        else:
            vid = link.split("/")[-1].split("?")[0]

        if video:
            return f"{API_BASE_URL}/download/video?video_id={vid}&max_res=720&api_key={API_KEY}"
        return f"{API_BASE_URL}/download/audio?video_id={vid}&api_key={API_KEY}"

    # -------------------------------------------------------------------------
    # PLAYLIST PARSE (unchanged, still uses your API)
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # DOWNLOAD FUNCTION (same behavior, just uses your API)
    # -------------------------------------------------------------------------
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

        if "v=" in link:
            vid = link.split("v=")[-1].split("&")[0]
        else:
            vid = link.split("/")[-1].split("?")[0]

        # USE STREAMING MODE FOR LONG VIDEOS
        duration_seconds = 0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{API_BASE_URL}/info", params={"video_id": vid, "api_key": API_KEY})
                if r.status_code == 200:
                    duration_str = r.json().get("duration", "0:0")
                    parts = duration_str.split(":")
                    if len(parts) == 3:
                        duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_seconds = int(parts[0]) * 60 + int(parts[1])
                    else:
                        duration_seconds = int(parts[0])
        except:
            pass

        # Stream for long videos
        if ENABLE_STREAMING and duration_seconds > STREAM_MODE_DURATION_THRESHOLD:
            if video:
                return f"{API_BASE_URL}/download/video?video_id={vid}&max_res=720&api_key={API_KEY}"
            return f"{API_BASE_URL}/download/audio?video_id={vid}&api_key={API_KEY}"

        # ---------------------------------------------------------------------
        # SHORT VIDEO DOWNLOADS
        # ---------------------------------------------------------------------
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
                            async for chunk in r.aiter_bytes(1024 * 128):
                                f.write(chunk)

                    return filepath
            except:
                return None

        async def api_download_video():
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
                    url = f"{API_BASE_URL}/download/video"
                    params = {
                        "video_id": vid,
                        "mode": "download",
                        "no_redirect": "1",
                        "max_res": "720",
                        "api_key": API_KEY,
                    }

                    info = await client.get(f"{API_BASE_URL}/info", params={"video_id": vid, "api_key": API_KEY})
                    file_title = info.json().get("title", vid) if info.status_code == 200 else vid

                    safe_title = re.sub(r'[<>:"/\\|?*]', '', file_title)[:100]
                    filepath = f"downloads/{safe_title}.mp4"

                    os.makedirs("downloads", exist_ok=True)

                    async with client.stream("GET", url, params=params) as r:
                        if r.status_code != 200:
                            return None
                        with open(filepath, "wb") as f:
                            async for chunk in r.aiter_bytes(1024 * 128):
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
