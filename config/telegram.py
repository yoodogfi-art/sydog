"""
config/telegram.py  —  the bot token and WHO automatic messages go to.

Replies to a typed command always go back to the chat that asked; this module
is only about the messages nobody asked for — the scheduled refresh report, the
daily brief, the startup ping. Those fan out to every chat listed here.

.env keys
---------
  TELEGRAM_TOKEN     bot token from @BotFather
  TELEGRAM_CHAT_ID   one id, or several separated by ',' or ';'
  TELEGRAM_CHAT_IDS  optional second key, merged with the above

  TELEGRAM_CHAT_ID=123456789,-1001234567890

A group id is negative and a supergroup/channel id starts with -100, so the
minus sign is part of the id — never strip it. To find a chat's id, add the bot
to it and send /chatid.

The bot must already be a member of every chat it sends to: Telegram has no way
for a bot to join on its own. For a channel it must be an admin.
"""

from config.env import get

TOKEN = get("TELEGRAM_TOKEN")


def _parse(*values: str | None) -> list[str]:
    """Split ','/';'-separated ids from several env vars into one ordered list."""
    out: list[str] = []
    for value in values:
        for part in (value or "").replace(";", ",").split(","):
            part = part.strip()
            if part and part not in out:   # dedupe: a repeat would double-send
                out.append(part)
    return out


CHAT_IDS = _parse(get("TELEGRAM_CHAT_ID"), get("TELEGRAM_CHAT_IDS"))

# The first id is the primary chat, used where exactly one target makes sense.
PRIMARY = CHAT_IDS[0] if CHAT_IDS else None

