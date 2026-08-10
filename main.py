import os
from dotenv import load_dotenv
from config.excel_updater import run_excel_updaters
from external_uploader.telegram_uploader import send_telegram_message
# from external_uploader.notion_uploader import log_to_notion

# 환경변수(.env) 로드
load_dotenv()
BASE_DIR = os.getenv("BASE_DIR")

def main():
    if not BASE_DIR:
        print("[error!] BASE_DIR was not set")
        return

# 1. 엑셀 데이터북 일괄 실행 및 자동 갱신 (VBA 연동)
    run_excel_updaters(BASE_DIR)

    # 2. 결과 알림 전송 (텔레그램)
    msg = "*[tasks done]*\n all excel databooks were triggered to execute the designated logic and saved."
    send_telegram_message(msg)

    # (추후 분석 결과가 나올 경우 노션이나 드롭박스 연동 코드는 여기에 추가)
    # log_to_notion("Databook_Batch", "성공")

if __name__ == "__main__":
    main()