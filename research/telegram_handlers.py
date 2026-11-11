"""
research/telegram_handlers.py

Wires research commands into the Telegram bot. bot/app.py calls
register_research_handlers(app).

There is nothing feature-specific here: every command comes from
research/registry.py (COMMAND_KINDS) x config/instruments.py (INSTRUMENTS +
GROUPS). A reply that is a string is sent as a message; a (png, caption) tuple
is sent as a photo.
"""

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.instruments import INSTRUMENTS, GROUPS
from research.registry import COMMAND_KINDS, iter_commands, run_group


async def _run(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


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

        if isinstance(reply, tuple):
            png, caption = reply
            await context.bot.send_photo(chat_id=chat_id, photo=png, caption=caption)
        else:
            await context.bot.send_message(chat_id=chat_id, text=reply)

    return handler


def register_research_handlers(app: Application):
    for tg_cmd, name, kind, target in iter_commands(INSTRUMENTS, GROUPS):
        app.add_handler(CommandHandler(tg_cmd, _make_handler(name, kind, target)))


def research_help_lines() -> list[str]:
    """One /help line per command kind (used by bot/app.py)."""
    return [k.help for k in COMMAND_KINDS]
