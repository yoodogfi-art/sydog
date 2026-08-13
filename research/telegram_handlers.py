"""
research/telegram_handlers.py

Wires the query engine into the Telegram bot. Import register_research_handlers
into bot/app.py and call it with your Application instance.

One command per instrument, argument-driven — no two-step prompts, no state:
  /kr_govt                      -> default snapshot (1d/1w/1mo/1y)
  /kr_govt 6m                   -> trailing-period change (14, 6m, 2w, 1y)
  /kr_govt 20260115 20260216    -> date-range change (space form)
  /kr_govt 20260115-20260216    -> date-range change (dash form)
  /fx  (group)                  -> same, applied to each member

Commands are generated automatically from config.instruments (INSTRUMENTS +
GROUPS). Adding an instrument = one registry line; the handler is generic.
"""

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from research import query_engine as qe
from config.instruments import INSTRUMENTS, GROUPS


async def _run(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


def _make_handler(command: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        args = context.args or []
        try:
            if command in GROUPS:
                text = await _run(qe.query_group, GROUPS[command], INSTRUMENTS, args)
            else:
                text = await _run(qe.query, command, INSTRUMENTS[command], args)
        except FileNotFoundError:
            text = f"[{command}] processed file not found yet."
        except ValueError as e:
            text = str(e)
        except Exception as e:  # noqa: BLE001
            text = f"[{command}] error: {e}"
        await context.bot.send_message(chat_id=chat_id, text=text)
    return handler


def register_research_handlers(app: Application):
    for cmd in list(INSTRUMENTS.keys()) + list(GROUPS.keys()):
        app.add_handler(CommandHandler(cmd, _make_handler(cmd)))