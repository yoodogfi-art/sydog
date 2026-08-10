import os
import requests
from dotenv import load_dotenv

load_dotenv()


def send_telegram_message(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[텔레그램 경고] 토큰 또는 챗 ID가 설정되지 않았습니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"[텔레그램 전송 실패]: {response.text}")
    except Exception as e:
        print(f"[텔레그램 에러]: {e}")