"""
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
    # 밀린 메시지 폭탄 방지 옵션 적용
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
"""
# 🐕🐕왈왈🐶🐶

import os
import sys
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from core.data_processor import process_excel_data
from core.excel_updater import run_excel_updaters

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

current_task_name = None


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_task_name
    chat_id = update.effective_chat.id
    if current_task_name:
        await context.bot.send_message(chat_id=chat_id, text=f"이미 작업 중입니다: {current_task_name}")
        return

    current_task_name = "엑셀 일괄 업데이트"
    await context.bot.send_message(chat_id=chat_id, text=f"{current_task_name}을 시작합니다.")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_excel_updaters, BASE_DIR)
        await context.bot.send_message(chat_id=chat_id, text="[완료] 업데이트 작업이 종료되었습니다.")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"[에러]\n{str(e)}")
    finally:
        current_task_name = None


async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_task_name
    chat_id = update.effective_chat.id
    if current_task_name:
        await context.bot.send_message(chat_id=chat_id, text=f"이미 작업 중입니다: {current_task_name}")
        return

    current_task_name = "데이터 전처리"
    await context.bot.send_message(chat_id=chat_id, text=f"{current_task_name}를 시작합니다.")

    try:
        loop = asyncio.get_running_loop()
        processed_files = await loop.run_in_executor(None, process_excel_data, BASE_DIR)
        msg = f"[완료] 전처리 완료. 총 {len(processed_files)}개 파일." if processed_files else "[알림] 처리된 파일 없음."
        await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"[에러]\n{str(e)}")
    finally:
        current_task_name = None


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_task_name
    status = current_task_name if current_task_name else "현재 진행 중인 작업 없음"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"[상태 확인]: {status}")


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="멍멍🐶! (pong)")


async def dir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"현재 작업 경로: {BASE_DIR}")


async def shutdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="깽...🐶 (퇴근합니다)")
    await asyncio.sleep(1)
    os._exit(0)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "사용 가능한 명령어 목록:\n"
        "/update - 엑셀 데이터북 일괄 업데이트 실행\n"
        "/process - 데이터 전처리 실행\n"
        "/task - 현재 진행 중인 작업 확인\n"
        "/ping - 봇 생존 여부 확인 (왈왈)\n"
        "/dir - 현재 작업 경로 확인\n"
        "/shutdown - 봇 프로세스 안전 종료\n"
        "/help - 명령어 목록 보기"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


async def send_startup_bark(application):
    try:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if chat_id:
            await application.bot.send_message(chat_id=chat_id, text="왈왈!🐶 (출동 준비 완료)")
    except Exception:
        pass


def main():
    if not TELEGRAM_TOKEN or not BASE_DIR:
        print("[에러] .env 파일 설정 확인 필요")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(send_startup_bark).build()

    app.add_handler(CommandHandler("update", update_command))
    app.add_handler(CommandHandler("process", process_command))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("dir", dir_command))
    app.add_handler(CommandHandler("shutdown", shutdown_command))
    app.add_handler(CommandHandler("help", help_command))

    print("텔레그램 봇이 대기 중입니다. (밀린 메시지 무시 설정 완료)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()