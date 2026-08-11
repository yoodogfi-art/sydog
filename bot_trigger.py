import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from core.data_processor import process_excel_data

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="데이터 전처리를 시작합니다.")

    try:
        # 전처리 함수를 별도 스레드에서 안전하게 실행
        loop = asyncio.get_running_loop()
        processed_files = await loop.run_in_executor(None, process_excel_data, BASE_DIR)

        if processed_files:
            file_list_str = "\n".join([f"- {f}" for f in processed_files])
            msg = f"[완료] 총 {len(processed_files)}개 파일 전처리가 완료되었습니다.\n\n[처리된 파일 목록]\n{file_list_str}"
        else:
            msg = "[알림] 처리된 파일이 없습니다."

        await context.bot.send_message(chat_id=chat_id, text=msg)

    except Exception as e:
        print(f"[에러 발생]: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"[에러 발생]\n{str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    help_text = (
        "사용 가능한 명령어 목록:\n"
        "/process - 데이터 전처리 실행\n"
        "/help - 명령어 목록 보기"
    )
    await context.bot.send_message(chat_id=chat_id, text=help_text)


def main():
    if not TELEGRAM_TOKEN or not BASE_DIR:
        print("[에러] .env 파일 설정 확인 필요")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("process", process_command))
    app.add_handler(CommandHandler("help", help_command))

    print("텔레그램 봇이 대기 중입니다.")
    app.run_polling()


if __name__ == "__main__":
    main()