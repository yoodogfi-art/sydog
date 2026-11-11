"""
research/telegram_handlers.py

Wires research commands into the Telegram bot. bot/app.py calls
register_research_handlers(app).

There is nothing feature-specific here: every command comes from
research/registry.py (COMMAND_KINDS) x config/instruments.py (INSTRUMENTS +
GROUPS). See _send for the reply shapes a command can return.
"""

import asyncio

from telegram import InputMediaPhoto, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.instruments import INSTRUMENTS, GROUPS
from research.registry import COMMAND_KINDS, iter_commands, run_group


async def _run(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


async def _send(bot, chat_id, reply):
    """str -> message | (png, caption) -> photo | list of (png, caption) -> album |
    any other list -> each item sent in order, as separate messages."""
    if isinstance(reply, str):
        await bot.send_message(chat_id=chat_id, text=reply)
    elif isinstance(reply, tuple):
        png, caption = reply
        await bot.send_photo(chat_id=chat_id, photo=png, caption=caption)
    elif all(isinstance(item, tuple) for item in reply):
        media = [InputMediaPhoto(media=png, caption=caption) for png, caption in reply]
        await bot.send_media_group(chat_id=chat_id, media=media)
    else:
        for item in reply:
            await _send(bot, chat_id, item)


def _make_handler(name, kind, target):
    target_type, payload = target

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        args = context.args or []
        try:
            if target_type == "group":
                reply = await _run(run_group, kind, payload, INSTRUMENTS, args)
            else:
                reply = await _run(kind.run, name, payload, args)
        except FileNotFoundError:
            reply = f"[{name}] processed file not found yet."
        except ValueError as e:
            reply = str(e)
        except Exception as e:  # noqa: BLE001
            reply = f"[{name}] {kind.error_word}: {e}"

        await _send(context.bot, chat_id, reply)

    return handler


def register_research_handlers(app: Application):
    for tg_cmd, name, kind, target in iter_commands(INSTRUMENTS, GROUPS):
        app.add_handler(CommandHandler(tg_cmd, _make_handler(name, kind, target)))


def research_help_lines() -> list[str]:
    """One /help line per command kind (used by bot/app.py)."""
    return [k.help for k in COMMAND_KINDS]
