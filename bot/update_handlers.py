"""
bot/update_handlers.py

Telegram handlers for data-refresh commands. These call the ingestion dispatcher
(refresh_all / refresh_one) and NEVER know a provider's mechanism. Adding a
provider changes ingestion/registry.py only — these handlers are untouched.
"""

import os
import asyncio

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ingestion.registry import refresh_all, refresh_one
from ingestion.processor import process_excel_data
from config.paths import RAW_DIR

# ensure .env is loaded even if this module is imported before app.py runs it
load_dotenv()

_busy = {"task": None}


async def _run(fn, *a):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *a)


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if _busy["task"]:
        await context.bot.send_message(chat_id=chat_id, text=f"이미 작업 중: {_busy['task']}")
        return
    _busy["task"] = "전체 갱신"
    await context.bot.send_message(chat_id=chat_id, text="데이터 일괄 갱신 시작.")
    try:
        results = await _run(refresh_all)
        lines = [r.telegram_line() for r in results] or ["갱신할 provider 없음."]
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines),
                                       parse_mode="Markdown")
    finally:
        _busy["task"] = None


async def update_one_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text="사용법: /update_one <provider_name>")
        return
    name = context.args[0]
    await context.bot.send_message(chat_id=chat_id, text=f"{name} 갱신 시작.")
    res = await _run(refresh_one, name)
    if res is None:
        await context.bot.send_message(chat_id=chat_id, text=f"provider '{name}' 없음.")
    else:
        await context.bot.send_message(chat_id=chat_id, text=res.telegram_line(),
                                       parse_mode="Markdown")


async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if _busy["task"]:
        await context.bot.send_message(chat_id=chat_id, text=f"이미 작업 중: {_busy['task']}")
        return
    if not RAW_DIR.exists():
        await context.bot.send_message(chat_id=chat_id, text=f"[에러] raw 경로 없음: {RAW_DIR}")
        return
    _busy["task"] = "데이터 전처리"
    await context.bot.send_message(chat_id=chat_id, text="데이터 전처리 시작.")
    try:
        processed = await _run(process_excel_data, str(RAW_DIR))
        if processed:
            body = "\n".join(f"- {p}" for p in processed)
            msg = f"[완료] {len(processed)}개 파일 전처리.\n\n{body}"
        else:
            msg = "[알림] 처리된 파일 없음."
        await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"[에러]\n{e}")
    finally:
        _busy["task"] = None


def register_update_handlers(app: Application):
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("update_one", update_one_command))
    app.add_handler(CommandHandler("process", process_command))