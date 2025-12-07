import asyncio
import os
import time
from typing import Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Voice

import config
from Dolbymusic import app
from Dolbymusic.utils.formatters import (
    check_duration,
    convert_bytes,
    get_readable_time,
    seconds_to_min,
)


class TeleAPI:
    def __init__(self):
        self.chars_limit = 4096
        self.sleep = 5

    async def send_split_text(self, message, string):
        n = self.chars_limit
        out = [(string[i : i + n]) for i in range(0, len(string), n)]
        j = 0
        for x in out:
            if j <= 2:
                j += 1
                await message.reply_text(x, disable_web_page_preview=True)
        return True

    async def get_link(self, message):
        return message.link

    async def get_filename(self, file, audio: Union[bool, str] = None):
        try:
            file_name = file.file_name
            if file_name is None:
                file_name = "ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ"
        except:
            file_name = "ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ"
        return file_name

    async def get_duration(self, filex, file_path):
        try:
            dur = seconds_to_min(filex.duration)
        except:
            try:
                dur = await asyncio.get_event_loop().run_in_executor(
                    None, check_duration, file_path
                )
                dur = seconds_to_min(dur)
            except:
                return "Unknown"
        return dur

    async def get_filepath(
        self,
        audio: Union[bool, str] = None,
        video: Union[bool, str] = None,
    ):
        if audio:
            try:
                file_name = (
                    audio.file_unique_id
                    + "."
                    + (
                        (audio.file_name.split(".")[-1])
                        if (not isinstance(audio, Voice))
                        else "ogg"
                    )
                )
            except:
                file_name = audio.file_unique_id + "." + "ogg"
            file_name = os.path.join(os.path.realpath("downloads"), file_name)
        if video:
            try:
                file_name = (
                    video.file_unique_id + "." + (video.file_name.split(".")[-1])
                )
            except:
                file_name = video.file_unique_id + "." + "mp4"
            file_name = os.path.join(os.path.realpath("downloads"), file_name)
        return file_name

    async def download(self, _, message, mystic, fname):
        """
        Download Telegram media with safe handling for NoneType mystic.
        Prevents crashes:
        - mystic.id → NoneType error
        - mystic.edit_text → NoneType error
        """

        # ------------------------------------------------------------------
        # FIX 1: Ensure mystic ALWAYS exists
        # ------------------------------------------------------------------
        if mystic is None:
            try:
                mystic = await message.reply_text("Downloading...")
            except:
                mystic = None  # still allow flow

        lower = [0, 8, 17, 38, 64, 77, 96]
        higher = [5, 10, 20, 40, 66, 80, 99]
        checker = [5, 10, 20, 40, 66, 80, 99]
        speed_counter = {}

        if os.path.exists(fname):
            return True

        async def down_load():
            async def progress(current, total):
                # If mystic failed to create, skip UI updates safely
                if mystic is None:
                    return

                if current == total:
                    return

                current_time = time.time()
                start_time = speed_counter.get(message.id, current_time)
                check_time = max(current_time - start_time, 1)

                upl = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="ᴄᴀɴᴄᴇʟ",
                                callback_data="stop_downloading",
                            ),
                        ]
                    ]
                )

                percentage = current * 100 / total
                percentage_int = int(percentage)

                speed = current / check_time
                eta = int((total - current) / max(speed, 1))
                eta = get_readable_time(eta)

                total_size = convert_bytes(total)
                completed_size = convert_bytes(current)
                speed = convert_bytes(speed)

                # Progress update logic
                for counter in range(7):
                    low = lower[counter]
                    high = higher[counter]
                    check = checker[counter]

                    if low < percentage_int <= high:
                        if high == check:
                            if mystic:
                                try:
                                    await mystic.edit_text(
                                        text=_["tg_1"].format(
                                            app.mention,
                                            total_size,
                                            completed_size,
                                            percentage_int,
                                            speed,
                                            eta,
                                        ),
                                        reply_markup=upl,
                                    )
                                except:
                                    pass
                            checker[counter] = 100

            speed_counter[message.id] = time.time()

            try:
                await app.download_media(
                    message.reply_to_message,
                    file_name=fname,
                    progress=progress,
                )

                elapsed = get_readable_time(
                    int(time.time() - speed_counter.get(message.id, time.time()))
                )

                if mystic:
                    try:
                        await mystic.edit_text(_["tg_2"].format(elapsed))
                    except:
                        pass

            except Exception:
                if mystic:
                    try:
                        await mystic.edit_text(_["tg_3"])
                    except:
                        pass

        # ------------------------------------------------------------------
        # FIX 2: Safe lyrical dictionary key
        # ------------------------------------------------------------------
        lyrical_key = mystic.id if mystic else message.id

        task = asyncio.create_task(down_load())
        config.lyrical[lyrical_key] = task

        await task

        verify = config.lyrical.get(lyrical_key)
        if not verify:
            return False

        config.lyrical.pop(lyrical_key, None)
        return True
