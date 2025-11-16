from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode

import config

from ..logging import LOGGER


class AyushSolo(Client):
    def __init__(self):
        LOGGER(__name__).info(f"Booting Bot...")
        super().__init__(
            name="Dolbymusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            parse_mode=ParseMode.HTML,
            max_concurrent_transmissions=7,
        )

    async def start(self):
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            LOGGER(__name__).info(f"Attempting to send message to LOGGER_ID: {config.LOGGER_ID}")
            await self.send_message(config.LOGGER_ID, "Bot Started")
        except errors.ChannelInvalid:
            LOGGER(__name__).error(
                "Bot has failed to access the log group/channel. Make sure that you have added your bot to your log group/channel."
            )
            exit()
        except errors.PeerIdInvalid:
            LOGGER(__name__).error(
                "Bot has failed to access the log group/channel. Make sure that you have added your bot to your log group/channel."
            )
            exit()
        except Exception as ex:
            LOGGER(__name__).error(
                f"Bot has failed to access the log group/channel.\n  Reason : {type(ex).__name__}: {ex}"
            )
            exit()

        try:
            LOGGER(__name__).info(f"Checking admin status in LOGGER_ID: {config.LOGGER_ID}")
            a = await self.get_chat_member(config.LOGGER_ID, self.id)
            LOGGER(__name__).info(f"Bot status in logger group: {a.status}")
            if a.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error(
                    f"Please promote your bot as an admin in your log group/channel. Current status: {a.status}"
                )
                exit()
        except Exception as ex:
            LOGGER(__name__).error(f"Failed to check admin status: {type(ex).__name__}: {ex}")
            exit()
            
        LOGGER(__name__).info(f"Music Bot Started as {self.name}")

    async def stop(self):
        await super().stop()
