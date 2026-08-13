"""
bot/app.py  —  Telegram bot entrypoint (the control surface).

The control surface. It builds the app, registers handler groups from each
feature package, and runs polling. It knows NOTHING about provider mechanisms,
data formats, or statistics — it only wires feature modules to Telegram. Adding
a feature = import its register_* function and call it here.
"""

import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from bot.update_handlers import register_update_handlers
from research.telegram_handlers import register_research_handlers

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
from config.paths import RAW_DIR


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="멍멍🐶! (pong)")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "명령어:\n"
        "/update - 전체 데이터 provider 갱신\n"
        "/update_one <name> - 특정 provider 갱신\n"
        "/process - 갱신된 엑셀 → CSV 전처리\n"
        "/<instrument> - 스냅샷 (예: /kr_govt, /usdkrw, /fx)\n"
        "/<instrument>_spec - 기간 지정 조회\n"
        "/ping - 생존 확인\n"
        "/help - 도움말"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def _startup(application):
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if chat_id:
        try:
            await application.bot.send_message(chat_id=chat_id, text="왈왈!🐶 (출동 준비 완료)")
        except Exception:
            pass


def main():
    if not TELEGRAM_TOKEN:
        print("[에러] TELEGRAM_TOKEN 미설정")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(_startup).build()

    # feature packages register their own handlers
    register_update_handlers(app)       # /update, /update_one   (ingestion)
    register_research_handlers(app)     # /<instrument>, *_spec   (research)

    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("help", help_command))

    print("텔레그램 봇 대기 중.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()