"""
main.py  —  batch/headless entrypoint (no Telegram polling).

For scheduled runs (Task Scheduler, run_databook.bat). Refreshes all providers,
rebuilds the CSVs, then sends the daily brief. Uses the same ingestion
dispatcher and the same research engine as the bot, so a scheduled run and a
typed command can never disagree.

Two messages go out: the refresh report (did the data arrive?) and the brief
(what moved?). They are separate because the first is plumbing and the second
is the thing worth reading.

  python main.py              refresh + process + brief
  python main.py --no-brief   refresh + process only
"""
import sys

from config.paths import RAW_DIR
from ingestion.processor import process_excel_data
from ingestion.registry import refresh_all
from external_uploader.telegram_uploader import send_telegram_message


def main(send_brief: bool = True):
    print("[배치] 데이터 provider 일괄 갱신 시작.")
    results = refresh_all()
    if not results:
        print("갱신할 provider 없음.")
        return

    lines = [r.telegram_line() for r in results]
    ok = sum(1 for r in results if r.ok)

    processed = process_excel_data(RAW_DIR)
    summary = (f"*[배치 갱신 완료]* {ok}/{len(results)} 성공, "
               f"CSV {len(processed)}개 전처리\n" + "\n".join(lines))
    # Unmapped sheets and failed workbooks are silent data loss: report them.
    if processed.warnings or processed.errors:
        summary += "\n" + "\n".join(f"!! {m}" for m in
                                    processed.warnings + processed.errors)
    print(summary)
    send_telegram_message(summary)

    if not send_brief:
        return
    # The brief reads the CSVs just written, so it must come after processing.
    # A failure here must not make the refresh itself look broken.
    try:
        from research.commands.brief import build
        text = build()
        print("\n" + text)
        send_telegram_message(text)
    except Exception as e:  # noqa: BLE001
        print(f"[브리프 실패] {e}")
        send_telegram_message(f"*[브리프 실패]* {e}")


if __name__ == "__main__":
    main(send_brief="--no-brief" not in sys.argv)