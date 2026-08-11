import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from core.data_processor import process_excel_data
from core.excel_updater import run_excel_updaters

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="엑셀 데이터북 일괄 업데이트를 시작합니다.")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_excel_updaters, BASE_DIR)
        await context.bot.send_message(chat_id=chat_id, text="[완료] 모든 엑셀 데이터북 업데이트 작업이 종료되었습니다.")
    except Exception as e:
        print(f"[업데이트 에러 발생]: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"[에러 발생]\n{str(e)}")


async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="데이터 전처리를 시작합니다.")

    try:
        loop = asyncio.get_running_loop()
        processed_files = await loop.run_in_executor(None, process_excel_data, BASE_DIR)

        if processed_files:
            file_list_str = "\n".join([f"- {f}" for f in processed_files])
            msg = f"[완료] 총 {len(processed_files)}개 파일 전처리가 완료되었습니다.\n\n[처리된 파일 목록]\n{file_list_str}"
        else:
            msg = "[알림] 처리된 파일이 없습니다."

        await context.bot.send_message(chat_id=chat_id, text=msg)

    except Exception as e:
        print(f"[전처리 에러 발생]: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"[에러 발생]\n{str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    help_text = (
        "사용 가능한 명령어 목록:\n"
        "/update - 엑셀 데이터북 일괄 업데이트 실행\n"
        "/process - 데이터 전처리 실행\n"
        "/help - 명령어 목록 보기"
    )
    await context.bot.send_message(chat_id=chat_id, text=help_text)


def main():
    if not TELEGRAM_TOKEN or not BASE_DIR:
        print("[에러] .env 파일 설정 확인 필요")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 명령어 매핑
    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("process", process_command))
    app.add_handler(CommandHandler("help", help_command))

    print("텔레그램 봇이 대기 중입니다. (밀린 메시지 무시 설정 완료)")
    # 💡 밀린 메시지 폭탄 방지 옵션 적용
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()