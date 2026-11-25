"""
external_uploader/telegram_uploader.py  —  outbound Telegram for the headless
paths (main.py). The bot process replies through python-telegram-bot instead;
this is the plain-HTTP sender for when no bot loop is running.

Sends to every chat in config.telegram.CHAT_IDS. One chat failing — bot kicked
from a group, wrong id, chat deleted — must never stop the others, so each send
is independent and the per-chat outcome is returned rather than raised.
"""

import requests

from config.telegram import CHAT_IDS, TOKEN

API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_S = 20


def _post(chat_id: str, message: str, parse_mode: str | None) -> tuple[bool, str]:
    payload = {"chat_id": chat_id, "text": message}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(API.format(token=TOKEN), json=payload, timeout=TIMEOUT_S)
    except Exception as e:  # noqa: BLE001  network/DNS
        return False, f"{type(e).__name__}: {e}"
    if r.status_code == 200:
        return True, "ok"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def send_telegram_message(message: str, parse_mode: str | None = "Markdown",
                          chat_ids=None) -> dict[str, str]:
    """Send one message to every configured chat. Returns {chat_id: outcome}.

    Markdown is best-effort: a stray '_' or '*' in a label makes Telegram reject
    the whole message, which would silently kill the daily brief. On a parse
    failure the same text is re-sent unformatted rather than lost.
    """
    targets = list(chat_ids) if chat_ids is not None else CHAT_IDS
    if not TOKEN:
        print("[텔레그램 경고] TELEGRAM_TOKEN 미설정")
        return {}
    if not targets:
        print("[텔레그램 경고] TELEGRAM_CHAT_ID 미설정")
        return {}

    results: dict[str, str] = {}
    for chat_id in targets:
        ok, detail = _post(chat_id, message, parse_mode)
        if not ok and parse_mode and "can't parse entities" in detail.lower():
            ok, detail = _post(chat_id, message, None)
            detail = "ok (plain)" if ok else detail
        results[chat_id] = detail
        if not ok:
            print(f"[텔레그램 전송 실패] {chat_id}: {detail}")
    sent = sum(1 for d in results.values() if d.startswith("ok"))
    print(f"[텔레그램] {sent}/{len(targets)}개 채팅 전송")
    return results
