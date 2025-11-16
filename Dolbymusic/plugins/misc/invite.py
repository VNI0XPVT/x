from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

from Dolbymusic import app
from config import BANNED_USERS


@app.on_message(filters.video_chat_started & filters.group & ~BANNED_USERS, group=10)
async def video_chat_started_handler(client, message: Message):
    """Notify when someone starts a video chat"""
    try:
        user = message.from_user
        chat_title = message.chat.title
        
        notification = f"""<blockquote>
<b>ᴠɪᴅᴇᴏ ᴄʜᴀᴛ sᴛᴀʀᴛᴇᴅ</b>
➖➖➖➖➖➖➖➖➖➖
<b>sᴛᴀʀᴛᴇᴅ ʙʏ:</b> {user.mention}
<b>ᴜsᴇʀ ɪᴅ:</b> <code>{user.id}</code>
<b>ɢʀᴏᴜᴘ:</b> {chat_title}
➖➖➖➖➖➖➖➖➖➖
<i>ᴊᴏɪɴ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ɴᴏᴡ!</i>
</blockquote>"""
        
        await message.reply_text(notification)
    except Exception as e:
        print(f"[VC START] Error: {e}")


@app.on_message(filters.video_chat_ended & filters.group & ~BANNED_USERS, group=10)
async def video_chat_ended_handler(client, message: Message):
    """Notify when someone ends a video chat"""
    try:
        user = message.from_user
        chat_title = message.chat.title
        duration = message.video_chat_ended.duration
        
        # Convert duration to readable format
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"
        
        notification = f"""<blockquote>
<b>ᴠɪᴅᴇᴏ ᴄʜᴀᴛ ᴇɴᴅᴇᴅ</b>
➖➖➖➖➖➖➖➖➖➖
<b>ᴇɴᴅᴇᴅ ʙʏ:</b> {user.mention}
<b>ᴜsᴇʀ ɪᴅ:</b> <code>{user.id}</code>
<b>ᴅᴜʀᴀᴛɪᴏɴ:</b> {duration_str}
<b>ɢʀᴏᴜᴘ:</b> {chat_title}
➖➖➖➖➖➖➖➖➖➖
</blockquote>"""
        
        await message.reply_text(notification)
    except Exception as e:
        print(f"[VC END] Error: {e}")


@app.on_message(filters.video_chat_members_invited & filters.group & ~BANNED_USERS, group=10)
async def video_chat_invite_handler(client, message: Message):
    """Notify when someone invites members to video chat"""
    try:
        inviter = message.from_user
        invited_users = message.video_chat_members_invited.users
        
        # Send notification for each invited user
        for invited_user in invited_users:
            notification = f"<blockquote>🥂 {inviter.mention} ɪɴᴠɪᴛᴇᴅ {invited_user.mention} ᴛᴏ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ</blockquote>"
            await message.reply_text(notification)
            
    except Exception as e:
        print(f"[VC INVITE] Error: {e}")
