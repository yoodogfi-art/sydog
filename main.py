import os
from dotenv import load_dotenv
from core.excel_updater import run_excel_updaters
from external_uploader.telegram_uploader import send_telegram_message

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR")


def main():
    if not BASE_DIR:
        print("[error!] BASE_DIR was not set")
        return

    print("[배치 모드] 엑셀 데이터북 일괄 갱신을 시작합니다.")
    run_excel_updaters(BASE_DIR)

    msg = "*[tasks done]*\nall excel databooks were triggered to execute the designated logic and saved."
    send_telegram_message(msg)


if __name__ == "__main__":
    main()