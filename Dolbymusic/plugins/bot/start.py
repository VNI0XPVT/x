import time
import aiohttp
import random
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython.__future__ import VideosSearch

import config
from Dolbymusic import app
from Dolbymusic.misc import _boot_
from Dolbymusic.plugins.sudo.sudoers import sudoers_list
from Dolbymusic.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from Dolbymusic.utils.decorators.language import LanguageStart
from Dolbymusic.utils.formatters import get_readable_time
from Dolbymusic.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS
from strings import get_string


# ⭐ REAL WORKING EFFECT + REACTION SENDER (edited version)
async def send_effect_and_reaction(chat_id: int, text: str):
    token = config.BOT_TOKEN
    base = f"https://api.telegram.org/bot{token}"

    # Working Telegram effects
    effects = [
        "5104841245755180586",  # 🎉 confetti
        "5100756587481003786",  # ✨ sparkle
        "5101021359089492789",  # ❤️ hearts
        "5046509860389126442",  # 💫 lightburst
    ]

    reactions = ["❤️", "👍", "✨", "🎉", "🔥"]

    effect_id = random.choice(effects)
    reaction_emoji = random.choice(reactions)

    async with aiohttp.ClientSession() as session:

        # 1️⃣ Send message WITH effect
        payload = {
            "chat_id": chat_id,
            "text": text,
            "message_effect_id": effect_id,
            "parse_mode": "HTML"
        }

        async with session.post(f"{base}/sendMessage", json=payload) as r:
            data = await r.json()

        if not data.get("ok"):
            return

        message_id = data["result"]["message_id"]

        # Very small delay for animation sync
        await asyncio.sleep(0.05)

        # 2️⃣ Send REAL animated reaction
        react = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": [
                {"emoji": reaction_emoji}
            ]
        }

        async with session.post(f"{base}/setMessageReaction", json=react):
            pass


# ⭐ Send reaction to existing message
async def send_reaction_to_message(chat_id: int, message_id: int):
    token = config.BOT_TOKEN
    base = f"https://api.telegram.org/bot{token}"

    reactions = ["❤️", "👍", "✨", "🎉", "🔥"]
    reaction_emoji = random.choice(reactions)

    try:
        async with aiohttp.ClientSession() as session:
            await asyncio.sleep(0.2)  # Small delay for better UX
            
            react = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [
                    {"type": "emoji", "emoji": reaction_emoji}
                ],
                "is_big": True
            }

            async with session.post(f"{base}/setMessageReaction", json=react) as response:
                result = await response.json()
                if not result.get("ok"):
                    print(f"Reaction failed: {result}")
    except Exception as e:
        print(f"Failed to send reaction: {e}")


# ⭐ Send photo with effect and reaction
async def send_photo_with_effect(chat_id: int, photo_url: str, caption: str, reply_markup):
    token = config.BOT_TOKEN
    base = f"https://api.telegram.org/bot{token}"

    # Working Telegram effects
    effects = [
        "5104841245755180586",  # 🎉 confetti
        "5100756587481003786",  # ✨ sparkle
        "5101021359089492789",  # ❤️ hearts
        "5046509860389126442",  # 💫 lightburst
    ]

    reactions = ["❤️", "👍", "✨", "🎉", "🔥"]
    
    effect_id = random.choice(effects)
    reaction_emoji = random.choice(reactions)

    try:
        async with aiohttp.ClientSession() as session:
            # Send photo WITH effect
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML",
                "message_effect_id": effect_id,
                "reply_markup": reply_markup
            }

            async with session.post(f"{base}/sendPhoto", json=payload) as r:
                data = await r.json()

            if not data.get("ok"):
                print(f"Photo with effect failed: {data}")
                return None

            message_id = data["result"]["message_id"]

            # Small delay for animation sync
            await asyncio.sleep(0.15)

            # Add reaction
            react = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [
                    {"type": "emoji", "emoji": reaction_emoji}
                ],
                "is_big": True
            }

            async with session.post(f"{base}/setMessageReaction", json=react):
                pass
                
            return message_id
    except Exception as e:
        print(f"Failed to send photo with effect: {e}")
        return None



# ⭐ YOUR START PM HANDLER (EDITED)
@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)

    # Send welcome sticker
    try:
        sticker_id = "CAACAgUAAxkBAAEPx-lpGCtPD-3QqM8PFfGqEpHuNHSCYgACWRkAAm7cAAFUEmXeljsvU3s2BA"
        await app.send_sticker(chat_id=message.chat.id, sticker=sticker_id)
    except:
        pass

    if len(message.text.split()) > 1:
        # (Your existing argument handler untouched)
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_photo(
                photo=config.START_IMG_URL,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"{message.from_user.mention} checked sudo list.\nUser: {message.from_user.id}"
                )
            return

        if name[0:3] == "inf":
            # (Your whole info code unchanged)
            m = await message.reply_text("🥂")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            results = VideosSearch(query, limit=1)
            for result in (await results.next())["result"]:
                title = result["title"]
                duration = result["duration"]
                views = result["viewCount"]["short"]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                channellink = result["channel"]["link"]
                channel = result["channel"]["name"]
                link = result["link"]
                published = result["publishedTime"]
            searched_text = _["start_6"].format(
                title, duration, views, published, channellink, channel, app.mention
            )
            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text=_["S_B_8"], url=link),
                        InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_CHAT),
                    ],
                ]
            )
            await m.delete()
            await app.send_photo(
                chat_id=message.chat.id,
                photo=thumbnail,
                caption=searched_text,
                reply_markup=key,
            )

            return

    # ⭐ NORMAL /START - Simple approach with proper HTML parsing
    out = private_panel(_)
    text = _["start_2"].format(message.from_user.mention, app.mention)

    # Send photo normally with Pyrogram (supports HTML properly)
    await message.reply_photo(
        photo=config.START_IMG_URL,
        caption=text,
        reply_markup=InlineKeyboardMarkup(out),
    )

    # Send log to logger channel
    try:
        if await is_on_off(2):
            await app.send_message(
                chat_id=config.LOGGER_ID,
                text=f"<b>🚀 User Started Bot in PM</b>\n\n<b>User:</b> {message.from_user.mention}\n<b>User ID:</b> <code>{message.from_user.id}</code>\n<b>Username:</b> @{message.from_user.username or 'None'}"
            )
    except Exception as e:
        print(f"[START LOG] Error: {e}")



# ⭐ GROUP /START
@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)

    await message.reply_photo(
        photo=config.START_IMG_URL,
        caption=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
    )

    await add_served_chat(message.chat.id)
    
    # Send log to logger channel
    if await is_on_off(2):
        await app.send_message(
            chat_id=config.LOGGER_ID,
            text=f"<b>📍 /start in Group</b>\n\n<b>Group:</b> {message.chat.title}\n<b>Group ID:</b> <code>{message.chat.id}</code>\n<b>By:</b> {message.from_user.mention}\n<b>User ID:</b> {message.from_user.id}"
        )



# ⭐ GROUP WELCOME with REAL EFFECT + REAL REACTION
@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:

        language = await get_lang(message.chat.id)
        _ = get_string(language)

        if await is_banned_user(member.id):
            try:
                await message.chat.ban_member(member.id)
            except:
                pass

        if member.id == app.id:
            try:
                out = start_panel(_)

                caption = _["start_3"].format(
                    message.from_user.first_name,
                    app.mention,
                    message.chat.title,
                    app.mention,
                )

                # Send welcome message in group
                await message.reply_text(
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(out),
                )

                await add_served_chat(message.chat.id)
                
                # Send log to logger channel
                if await is_on_off(2):
                    await app.send_message(
                        chat_id=config.LOGGER_ID,
                        text=f"<b>✨ Bot Added to New Group</b>\n\n<b>Group:</b> {message.chat.title}\n<b>Group ID:</b> <code>{message.chat.id}</code>\n<b>Added by:</b> {message.from_user.mention}\n<b>User ID:</b> {message.from_user.id}"
                    )
            except Exception as e:
                print(f"[WELCOME] Error: {e}")
            
            return

