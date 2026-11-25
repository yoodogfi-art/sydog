"""
bot/update_handlers.py

Telegram handlers for data-refresh commands. These call the ingestion dispatcher
(refresh_all / refresh_one) and NEVER know a provider's mechanism. Adding a
provider changes ingestion/registry.py only — these handlers are untouched.
"""

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ingestion.registry import refresh_all, refresh_one
from ingestion.processor import process_excel_data
from config.paths import RAW_DIR   # importing this loads .env

# One refresh at a time: the Excel add-in drives a real Excel instance, so two
# overlapping passes fight over the same workbooks.
_busy = {"task": None}


async def _run(fn, *a):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *a)


async def _process_and_report(bot, chat_id):
    """Rebuild the CSVs from the raw Excel files and report the result.

    The report carries the processor's warnings too — an unmapped sheet writes to
    the wrong CSV name, so it has to reach the user, not stdout.
    """
    if not RAW_DIR.exists():
        await bot.send_message(chat_id=chat_id, text=f"[에러] raw 경로 없음: {RAW_DIR}")
        return
    await bot.send_message(chat_id=chat_id, text="데이터 전처리 시작.")
    try:
        processed = await _run(process_excel_data, RAW_DIR)
        head = (f"[완료] {len(processed)}개 파일 전처리." if processed
                else "[알림] 처리된 파일 없음.")
        body = "\n".join(processed.telegram_lines())
        await bot.send_message(chat_id=chat_id,
                               text=f"{head}\n\n{body}" if body else head)
    except Exception as e:  # noqa: BLE001
        await bot.send_message(chat_id=chat_id, text=f"[에러]\n{e}")


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
        # Commands read the CSVs, so a refresh isn't finished until they're rebuilt.
        await _process_and_report(context.bot, chat_id)
    finally:
        _busy["task"] = None


async def update_one_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text="사용법: /update_one <provider_name>")
        return
    if _busy["task"]:
        await context.bot.send_message(chat_id=chat_id, text=f"이미 작업 중: {_busy['task']}")
        return

    name = context.args[0]
    _busy["task"] = f"{name} 갱신"
    try:
        await context.bot.send_message(chat_id=chat_id, text=f"{name} 갱신 시작.")
        res = await _run(refresh_one, name)
        if res is None:
            await context.bot.send_message(chat_id=chat_id, text=f"provider '{name}' 없음.")
            return
        await context.bot.send_message(chat_id=chat_id, text=res.telegram_line(),
                                       parse_mode="Markdown")
        await _process_and_report(context.bot, chat_id)
    finally:
        _busy["task"] = None


async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if _busy["task"]:
        await context.bot.send_message(chat_id=chat_id, text=f"이미 작업 중: {_busy['task']}")
        return
    _busy["task"] = "데이터 전처리"
    try:
        await _process_and_report(context.bot, chat_id)
    finally:
        _busy["task"] = None


def register_update_handlers(app: Application):
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("update_one", update_one_command))
    app.add_handler(CommandHandler("process", process_command))