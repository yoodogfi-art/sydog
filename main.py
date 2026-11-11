"""
main.py  —  batch/headless entrypoint (no Telegram polling).

For scheduled runs (Task Scheduler, .bat). Refreshes all providers, then
optionally runs processing. Uses the same ingestion dispatcher as the bot, so
batch and interactive paths share one code path.
"""
import os
from dotenv import load_dotenv

from config.paths import RAW_DIR
from ingestion.processor import process_excel_data
from ingestion.registry import refresh_all
from external_uploader.telegram_uploader import send_telegram_message

load_dotenv()


def main():
    print("[배치] 데이터 provider 일괄 갱신 시작.")
    results = refresh_all()
    if not results:
        print("갱신할 provider 없음.")
        return

    lines = [r.telegram_line() for r in results]
    ok = sum(1 for r in results if r.ok)
    processed = process_excel_data(str(RAW_DIR))
    summary = (f"*[배치 갱신 완료]* {ok}/{len(results)} 성공, "
               f"CSV {len(processed)}개 전처리\n" + "\n".join(lines))
    print(summary)
    send_telegram_message(summary)


if __name__ == "__main__":
    main()