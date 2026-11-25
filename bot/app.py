"""
bot/app.py  —  Telegram bot entrypoint (the control surface).

The control surface. It builds the app, registers handler groups from each
feature package, and runs polling. It knows NOTHING about provider mechanisms,
data formats, or statistics — it only wires feature modules to Telegram. Adding
a feature = import its register_* function and call it here.
"""

# use app.py to activate the telegram bot (sydog)

import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from bot.config_handlers import register_config_handlers
from bot.update_handlers import register_update_handlers
from research.telegram_handlers import register_research_handlers, research_help_lines
from config.instruments import INSTRUMENTS, GROUPS
from config import telegram as tg

TELEGRAM_TOKEN = tg.TOKEN


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="멍멍🐶! (pong)")


async def broadcast(bot, text: str, parse_mode=None):
    """Send to every configured chat. One failure never blocks the rest."""
    for chat_id in tg.CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        except Exception as e:  # noqa: BLE001
            print(f"[브로드캐스트 실패] {chat_id}: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [
        "명령어:",
        "/update - 전체 데이터 갱신 + CSV 전처리",
        "/update_one <name> - 특정 provider 갱신 + CSV 전처리",
        "/process - CSV 전처리만 실행",
        *research_help_lines(),
        "instruments: " + ", ".join(list(INSTRUMENTS) + list(GROUPS)),
        "/ping - 생존 확인",
        "/config - 설정/경로/데이터 신선도 점검",
        "/chatid - 이 대화방의 chat_id (자동 발송 대상 추가용)",
        "/help - 도움말",
    ]
    text = "\n".join(lines)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def _startup(application):
    # Every configured chat, so each room sees the bot came back up.
    await broadcast(application.bot, "왈왈!🐶 (출동 준비 완료)")


def main():
    if not TELEGRAM_TOKEN:
        print("[에러] TELEGRAM_TOKEN 미설정")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(_startup).build()

    # feature packages register their own handlers
    register_update_handlers(app)       # /update, /update_one   (ingestion)
    register_research_handlers(app)     # /<instrument>, *_spec   (research)

    register_config_handlers(app)       # /config, /chatid       (diagnostics)

    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("help", help_command))

    print("텔레그램 봇 대기 중.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()