import time
import re
import os
from pyrogram.enums import MessageEntityType
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS
from Dolbymusic import app, LOGGER
from Dolbymusic.utils.formatters import get_readable_time
from Dolbymusic.utils.database import add_afk, is_afk, remove_afk

LOGGER(__name__).info("AFK Plugin Loaded")


@app.on_message(filters.command(["afk", "brb"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
async def active_afk(_, message: Message):
    if message.sender_chat:
        return
    user_id = message.from_user.id
    verifier, reasondb = await is_afk(user_id)
    if verifier:
        await remove_afk(user_id)
        try:
            afktype = reasondb["type"]
            timeafk = reasondb["time"]
            data = reasondb["data"]
            reasonafk = reasondb["reason"]
            seenago = get_readable_time((int(time.time() - timeafk)))
            
            if afktype == "text":
                send = await message.reply_text(
                    f"<blockquote>**{message.from_user.first_name}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}</blockquote>",
                    disable_web_page_preview=True,
                )
            elif afktype == "text_reason":
                send = await message.reply_text(
                    f"<blockquote>**{message.from_user.first_name}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}\n\nʀᴇᴀsᴏɴ: `{reasonafk}`</blockquote>",
                    disable_web_page_preview=True,
                )
            elif afktype == "animation":
                caption = f"<blockquote>**{message.from_user.first_name}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}"
                if str(reasonafk) != "None":
                    caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                caption += "</blockquote>"
                send = await message.reply_animation(data, caption=caption)
            elif afktype == "photo":
                caption = f"<blockquote>**{message.from_user.first_name}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}"
                if str(reasonafk) != "None":
                    caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                caption += "</blockquote>"
                photo_path = f"downloads/{user_id}.jpg"
                if os.path.exists(photo_path):
                    send = await message.reply_photo(photo=photo_path, caption=caption)
                else:
                    send = await message.reply_text(caption, disable_web_page_preview=True)
        except Exception as e:
            print(f"[AFK] Error: {e}")
            send = await message.reply_text(
                f"<blockquote>**{message.from_user.first_name}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ</blockquote>",
                disable_web_page_preview=True,
            )

    # Set new AFK status
    if len(message.command) == 1 and not message.reply_to_message:
        details = {
            "type": "text",
            "time": time.time(),
            "data": None,
            "reason": None,
        }
    elif len(message.command) > 1 and not message.reply_to_message:
        _reason = (message.text.split(None, 1)[1].strip())[:100]
        details = {
            "type": "text_reason",
            "time": time.time(),
            "data": None,
            "reason": _reason,
        }
    elif message.reply_to_message:
        if message.reply_to_message.animation:
            _data = message.reply_to_message.animation.file_id
            _reason = None
            if len(message.command) > 1:
                _reason = (message.text.split(None, 1)[1].strip())[:100]
            details = {
                "type": "animation",
                "time": time.time(),
                "data": _data,
                "reason": _reason,
            }
        elif message.reply_to_message.photo:
            await app.download_media(
                message.reply_to_message, file_name=f"downloads/{user_id}.jpg"
            )
            _reason = None
            if len(message.command) > 1:
                _reason = (message.text.split(None, 1)[1].strip())[:100]
            details = {
                "type": "photo",
                "time": time.time(),
                "data": None,
                "reason": _reason,
            }
        elif message.reply_to_message.sticker:
            if message.reply_to_message.sticker.is_animated:
                _reason = None
                if len(message.command) > 1:
                    _reason = (message.text.split(None, 1)[1].strip())[:100]
                details = {
                    "type": "text_reason" if _reason else "text",
                    "time": time.time(),
                    "data": None,
                    "reason": _reason,
                }
            else:
                await app.download_media(
                    message.reply_to_message, file_name=f"downloads/{user_id}.jpg"
                )
                _reason = None
                if len(message.command) > 1:
                    _reason = (message.text.split(None, 1)[1].strip())[:100]
                details = {
                    "type": "photo",
                    "time": time.time(),
                    "data": None,
                    "reason": _reason,
                }
        else:
            details = {
                "type": "text",
                "time": time.time(),
                "data": None,
                "reason": None,
            }
    else:
        details = {
            "type": "text",
            "time": time.time(),
            "data": None,
            "reason": None,
        }

    await add_afk(user_id, details)    
    await message.reply_text(f"<blockquote>{message.from_user.first_name} ɪs ɴᴏᴡ ᴀғᴋ!</blockquote>")


# AFK Watcher
chat_watcher_group = 5


@app.on_message(
    ~filters.me & ~filters.bot & ~filters.via_bot & ~BANNED_USERS,
    group=chat_watcher_group,
)
async def chat_watcher_func(_, message: Message):
    if message.sender_chat:
        return
    
    userid = message.from_user.id
    user_name = message.from_user.first_name
    
    # Check if message is AFK command
    if message.entities:
        possible = ["/afk", f"/afk@{app.username}", "!afk", ".afk", "/brb", "!brb", ".brb"]
        message_text = message.text or message.caption
        if message_text:
            for entity in message.entities:
                if entity.type == MessageEntityType.BOT_COMMAND:
                    command = message_text[entity.offset : entity.offset + entity.length].lower()
                    if command in possible:
                        return

    msg = ""
    replied_user_id = 0

    # Check if user is returning from AFK
    verifier, reasondb = await is_afk(userid)
    if verifier:
        await remove_afk(userid)
        try:
            afktype = reasondb["type"]
            timeafk = reasondb["time"]
            data = reasondb["data"]
            reasonafk = reasondb["reason"]
            seenago = get_readable_time((int(time.time() - timeafk)))
            
            if afktype == "text":
                msg += f"<blockquote>**{user_name[:25]}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}</blockquote>\n\n"
            elif afktype == "text_reason":
                msg += f"<blockquote>**{user_name[:25]}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}\n\nʀᴇᴀsᴏɴ: `{reasonafk}`</blockquote>\n\n"
            elif afktype == "animation":
                caption = f"<blockquote>**{user_name[:25]}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}"
                if str(reasonafk) != "None":
                    caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                caption += "</blockquote>"
                await message.reply_animation(data, caption=caption)
                return
            elif afktype == "photo":
                caption = f"<blockquote>**{user_name[:25]}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ᴡᴀs ᴀᴡᴀʏ ғᴏʀ {seenago}"
                if str(reasonafk) != "None":
                    caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                caption += "</blockquote>"
                photo_path = f"downloads/{userid}.jpg"
                if os.path.exists(photo_path):
                    await message.reply_photo(photo=photo_path, caption=caption)
                else:
                    msg += caption + "\n\n"
                return
        except Exception as e:
            print(f"[AFK WATCHER] Error: {e}")
            msg += f"<blockquote>**{user_name[:25]}** ɪs ʙᴀᴄᴋ ᴏɴʟɪɴᴇ</blockquote>\n\n"

    # Check replied user
    if message.reply_to_message:
        try:
            if message.reply_to_message.from_user:
                replied_first_name = message.reply_to_message.from_user.first_name
                replied_user_id = message.reply_to_message.from_user.id
                verifier, reasondb = await is_afk(replied_user_id)
                if verifier:
                    try:
                        afktype = reasondb["type"]
                        timeafk = reasondb["time"]
                        data = reasondb["data"]
                        reasonafk = reasondb["reason"]
                        seenago = get_readable_time((int(time.time() - timeafk)))
                        
                        if afktype == "text":
                            msg += f"<blockquote>**{replied_first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}</blockquote>\n\n"
                        elif afktype == "text_reason":
                            msg += f"<blockquote>**{replied_first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\nʀᴇᴀsᴏɴ: `{reasonafk}`</blockquote>\n\n"
                        elif afktype == "animation":
                            caption = f"<blockquote>**{replied_first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}"
                            if str(reasonafk) != "None":
                                caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                            caption += "</blockquote>"
                            await message.reply_animation(data, caption=caption)
                            return
                        elif afktype == "photo":
                            caption = f"<blockquote>**{replied_first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}"
                            if str(reasonafk) != "None":
                                caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                            caption += "</blockquote>"
                            photo_path = f"downloads/{replied_user_id}.jpg"
                            if os.path.exists(photo_path):
                                await message.reply_photo(photo=photo_path, caption=caption)
                            else:
                                msg += caption + "\n\n"
                            return
                    except Exception as e:
                        print(f"[AFK REPLY] Error: {e}")
                        msg += f"<blockquote>**{replied_first_name[:25]}** ɪs ᴀғᴋ</blockquote>\n\n"
        except:
            pass

    # Check mentioned users
    if message.entities:
        entity = message.entities
        j = 0
        for x in range(len(entity)):
            if (entity[j].type) == MessageEntityType.MENTION:
                found = re.findall("@([_0-9a-zA-Z]+)", message.text or "")
                try:
                    get_user = found[j]
                    user = await app.get_users(get_user)
                    if user.id == replied_user_id:
                        j += 1
                        continue
                except:
                    j += 1
                    continue
                    
                verifier, reasondb = await is_afk(user.id)
                if verifier:
                    try:
                        afktype = reasondb["type"]
                        timeafk = reasondb["time"]
                        data = reasondb["data"]
                        reasonafk = reasondb["reason"]
                        seenago = get_readable_time((int(time.time() - timeafk)))
                        
                        if afktype == "text":
                            msg += f"<blockquote>**{user.first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}</blockquote>\n\n"
                        elif afktype == "text_reason":
                            msg += f"<blockquote>**{user.first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\nʀᴇᴀsᴏɴ: `{reasonafk}`</blockquote>\n\n"
                        elif afktype == "animation":
                            caption = f"<blockquote>**{user.first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}"
                            if str(reasonafk) != "None":
                                caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                            caption += "</blockquote>"
                            await message.reply_animation(data, caption=caption)
                            return
                        elif afktype == "photo":
                            caption = f"<blockquote>**{user.first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}"
                            if str(reasonafk) != "None":
                                caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                            caption += "</blockquote>"
                            photo_path = f"downloads/{user.id}.jpg"
                            if os.path.exists(photo_path):
                                await message.reply_photo(photo=photo_path, caption=caption)
                            else:
                                msg += caption + "\n\n"
                            return
                    except:
                        msg += f"<blockquote>**{user.first_name[:25]}** ɪs ᴀғᴋ</blockquote>\n\n"
                        
            elif (entity[j].type) == MessageEntityType.TEXT_MENTION:
                try:
                    user_id = entity[j].user.id
                    if user_id == replied_user_id:
                        j += 1
                        continue
                    first_name = entity[j].user.first_name
                except:
                    j += 1
                    continue
                    
                verifier, reasondb = await is_afk(user_id)
                if verifier:
                    try:
                        afktype = reasondb["type"]
                        timeafk = reasondb["time"]
                        data = reasondb["data"]
                        reasonafk = reasondb["reason"]
                        seenago = get_readable_time((int(time.time() - timeafk)))
                        
                        if afktype == "text":
                            msg += f"<blockquote>**{first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}</blockquote>\n\n"
                        elif afktype == "text_reason":
                            msg += f"<blockquote>**{first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}\n\nʀᴇᴀsᴏɴ: `{reasonafk}`</blockquote>\n\n"
                        elif afktype == "animation":
                            caption = f"<blockquote>**{first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}"
                            if str(reasonafk) != "None":
                                caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                            caption += "</blockquote>"
                            await message.reply_animation(data, caption=caption)
                            return
                        elif afktype == "photo":
                            caption = f"<blockquote>**{first_name[:25]}** ɪs ᴀғᴋ sɪɴᴄᴇ {seenago}"
                            if str(reasonafk) != "None":
                                caption += f"\n\nʀᴇᴀsᴏɴ: `{reasonafk}`"
                            caption += "</blockquote>"
                            photo_path = f"downloads/{user_id}.jpg"
                            if os.path.exists(photo_path):
                                await message.reply_photo(photo=photo_path, caption=caption)
                            else:
                                msg += caption + "\n\n"
                            return
                    except:
                        msg += f"<blockquote>**{first_name[:25]}** ɪs ᴀғᴋ</blockquote>\n\n"
            j += 1
            
    if msg != "":
        try:
            await message.reply_text(msg, disable_web_page_preview=True)
        except:
            return
