import os
from PIL import ImageDraw, Image, ImageFont, ImageChops
from pyrogram import filters
from pyrogram.types import ChatMemberUpdated, Message, InlineKeyboardMarkup, InlineKeyboardButton
from logging import getLogger

from config import BANNED_USERS, LOGGER_ID
from Dolbymusic import app, LOGGER as BOT_LOGGER
from Dolbymusic.utils.database import get_welcome, set_welcome, remove_welcome
from Dolbymusic.utils.decorators import AdminActual

LOGGER = getLogger(__name__)
BOT_LOGGER(__name__).info("Welcome Plugin Loaded")


class temp:
    MELCOW = {}


def circle(pfp, size=(450, 450)):
    pfp = pfp.resize(size, Image.LANCZOS).convert("RGBA")
    bigsize = (pfp.size[0] * 3, pfp.size[1] * 3)
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(pfp.size, Image.LANCZOS)
    mask = ImageChops.darker(mask, pfp.split()[-1])
    pfp.putalpha(mask)
    return pfp


def welcomepic(pic, user, chatname, id, uname):
    background = Image.open("Dolbymusic/assets/wel2.png")
    pfp = Image.open(pic).convert("RGBA")
    pfp = circle(pfp)
    pfp = pfp.resize((447, 447))
    draw = ImageDraw.Draw(background)
    font = ImageFont.truetype('Dolbymusic/assets/font.ttf', size=40)
    welcome_font = ImageFont.truetype('Dolbymusic/assets/font.ttf', size=60)
    draw.text((730, 250), f'STATUS: MEMBER', fill=(255, 255, 255), font=font)
    draw.text((730, 330), f'ID: {id}', fill=(255, 255, 255), font=font)
    draw.text((730, 380), f"USERNAME : {uname}", fill=(255, 255, 255), font=font)
    pfp_position = (151, 139)
    background.paste(pfp, pfp_position, pfp)
    background.save(f"downloads/welcome#{id}.png")
    return f"downloads/welcome#{id}.png"


@app.on_chat_member_updated(filters.group, group=-3)
async def greet_group(_, member: ChatMemberUpdated):
    chat_id = member.chat.id
    
    # Check if welcome is enabled
    welcome_enabled = await get_welcome(chat_id)
    if not welcome_enabled:
        return
    
    if (
        not member.new_chat_member
        or member.new_chat_member.status in {"banned", "left", "restricted"}
        or member.old_chat_member
    ):
        return
    
    user = member.new_chat_member.user if member.new_chat_member else member.from_user
    
    try:
        pic = await app.download_media(
            user.photo.big_file_id, file_name=f"downloads/pp{user.id}.png"
        )
    except AttributeError:
        pic = "Dolbymusic/assets/wel2.png"
    
    if (temp.MELCOW).get(f"welcome-{member.chat.id}") is not None:
        try:
            await temp.MELCOW[f"welcome-{member.chat.id}"].delete()
        except Exception as e:
            LOGGER.error(e)
    
    try:
        welcomeimg = welcomepic(
            pic, user.first_name, member.chat.title, user.id, user.username or "None"
        )
        temp.MELCOW[f"welcome-{member.chat.id}"] = await app.send_photo(
            member.chat.id,
            photo=welcomeimg,
            caption=f"""<blockquote>
𝐖ᴇʟᴄᴏᴍᴇ 𝐓ᴏ {member.chat.title}
➖➖➖➖➖➖➖➖➖➖➖
𝐍ᴀᴍᴇ ✧ {user.mention}
𝐈ᴅ ✧ {user.id}
𝐔sᴇʀɴᴀᴍᴇ ✧ @{user.username or 'None'}
➖➖➖➖➖➖➖➖➖➖➖
𝐏ʟᴇᴀsᴇ 𝐅ᴏʟʟᴏᴡ 𝐓ʜᴇ 𝐆ʀᴏᴜᴘ 𝐑ᴜʟᴇs​
𝐒ᴛᴀʏ 𝐂ᴏɴɴᴇᴄᴛᴇᴅ
</blockquote>
""",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"⦿ ᴀᴅᴅ ᴍᴇ ⦿", url=f"https://t.me/{app.username}?startgroup=true")]])
        )
    except Exception as e:
        LOGGER.error(f"[WELCOME] Error: {e}")
    
    try:
        os.remove(f"downloads/welcome#{user.id}.png")
        os.remove(f"downloads/pp{user.id}.png")
    except Exception:
        pass


@app.on_message(filters.new_chat_members & filters.group, group=-1)
async def bot_wel(_, message: Message):
    for u in message.new_chat_members:
        if u.id == app.me.id:
            try:
                await app.send_message(LOGGER_ID, f"""<blockquote><b>NEW GROUP</b>
➖➖➖➖➖➖➖➖➖➖➖➖
<b>NAME:</b> {message.chat.title}
<b>ID:</b> <code>{message.chat.id}</code>
<b>USERNAME:</b> @{message.chat.username or 'None'}
➖➖➖➖➖➖➖➖➖➖➖➖</blockquote>""")
            except Exception as e:
                LOGGER.error(f"[BOT WELCOME] Error: {e}")


@app.on_message(filters.command("welcome") & filters.group & ~BANNED_USERS)
@AdminActual
async def welcome_command(client, message: Message, _):
    usage = "<blockquote><b>ᴜsᴀɢᴇ:</b>\n/welcome [on|off]</blockquote>"
    
    if len(message.command) < 2:
        return await message.reply(usage)
    
    chat_id = message.chat.id
    state = message.text.split(None, 1)[1].strip().lower()
    
    if state == "on":
        await set_welcome(chat_id, True)
        await message.reply("<blockquote>✅ Wᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ <b>ᴇɴᴀʙʟᴇᴅ</b> ғᴏʀ ᴛʜɪs ᴄʜᴀᴛ.</blockquote>")
    elif state == "off":
        await remove_welcome(chat_id)
        await message.reply("<blockquote>❌ Wᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ <b>ᴅɪsᴀʙʟᴇᴅ</b> ғᴏʀ ᴛʜɪs ᴄʜᴀᴛ.</blockquote>")
    else:
        await message.reply(usage)
