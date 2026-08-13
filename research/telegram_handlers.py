"""
research/telegram_handlers.py

Wires the query engine into the Telegram bot. Import register_research_handlers
into bot_trigger.py and call it with your Application instance.

Commands generated automatically from config.instruments:
  /kr_govt        -> snapshot
  /kr_govt_spec   -> prompts for a date range, then prints spec
  /usdkrw, /usdjpy, /fx (group), plus *_spec variants

The _spec two-step: on /<name>_spec we store a pending request keyed by
chat_id, reply asking for "yyyymmdd-yyyymmdd", and a plain-text message
handler picks up the next message from that chat and runs the spec.
"""

import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from research import query_engine as qe
from config.instruments import INSTRUMENTS, GROUPS

# chat_id -> command key awaiting a date range (e.g. "kr_govt")
_pending_spec: dict[int, str] = {}


async def _run(fn, *args):
    """Run blocking engine calls off the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


# ---------------------------------------------------------------------------
# Snapshot handler factory
# ---------------------------------------------------------------------------
def _make_snapshot_handler(command: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        try:
            if command in GROUPS:
                text = await _run(qe.snapshot_group, GROUPS[command], INSTRUMENTS)
            else:
                text = await _run(qe.snapshot, command, INSTRUMENTS[command])
        except FileNotFoundError:
            text = f"[{command}] processed file not found yet."
        except Exception as e:  # noqa: BLE001
            text = f"[{command}] error: {e}"
        await context.bot.send_message(chat_id=chat_id, text=text)
    return handler


# ---------------------------------------------------------------------------
# Spec prompt handler factory
# ---------------------------------------------------------------------------
def _make_spec_handler(command: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        _pending_spec[chat_id] = command
        await context.bot.send_message(
            chat_id=chat_id,
            text='type "yyyymmdd-yyyymmdd".',
        )
    return handler


# ---------------------------------------------------------------------------
# Free-text handler: catches the date-range reply after a *_spec command
# ---------------------------------------------------------------------------
async def _spec_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    command = _pending_spec.get(chat_id)
    if command is None:
        return  # not awaiting anything from this chat; ignore silently

    text = (update.message.text or "").strip()
    try:
        start, end = qe.parse_spec_range(text)
    except ValueError as e:
        await context.bot.send_message(chat_id=chat_id, text=str(e))
        return  # keep pending so they can retry

    _pending_spec.pop(chat_id, None)

    try:
        if command in GROUPS:
            parts = []
            for m in GROUPS[command]:
                parts.append(await _run(qe.spec, m, INSTRUMENTS[m], start, end))
            out = "\n".join(parts)
        else:
            out = await _run(qe.spec, command, INSTRUMENTS[command], start, end)
    except FileNotFoundError:
        out = f"[{command}] processed file not found yet."
    except Exception as e:  # noqa: BLE001
        out = f"[{command}] error: {e}"

    await context.bot.send_message(chat_id=chat_id, text=out)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_research_handlers(app: Application):
    commands = list(INSTRUMENTS.keys()) + list(GROUPS.keys())

    for cmd in commands:
        app.add_handler(CommandHandler(cmd, _make_snapshot_handler(cmd)))
        app.add_handler(CommandHandler(f"{cmd}_spec", _make_spec_handler(cmd)))

    # Plain text (non-command) -> possible spec reply. Registered last.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _spec_reply_handler)
    )