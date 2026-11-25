from notion_client import Client

from config.env import get

notion_token = get("NOTION_API_KEY")
database_id = get("NOTION_DATABASE_ID")

notion = Client(auth=notion_token) if notion_token else None

def log_to_notion(file_name, status):
    if not notion or not database_id:
        print("[노션 경고] API Key 또는 Database ID가 설정되지 않았습니다.")
        return

    try:
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "파일명": {
                    "title": [{"text": {"content": file_name}}]
                },
                "상태": {
                    "select": {"name": status}
                }
            }
        )
        print(f"[노션 기록 성공]: {file_name} - {status}")
    except Exception as e:
        print(f"[노션 기록 실패]: {e}")