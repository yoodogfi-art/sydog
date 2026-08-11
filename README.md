# Telegram Excel Automation Bot

텔레그램 봇을 통해 엑셀 데이터 자동 갱신, 전처리, 업로드 등의 작업을 원격으로 제어하는 파이썬 프로젝트입니다.

---

## 프로젝트 구조

```text
your_project_root/
│
├── config/
│   └── excel_updater.py      # 엑셀 파일 열기, 새로고침, 저장 및 종료 관리
├── core/
│   └── data_processor.py     # 데이터 전처리 로직
├── external_uploader/
│   └── notion_uploader.py    # 노션 등 외부 업로드 로직
│
├── bot_trigger.py            # 텔레그램 봇 실행 진입점 (Main)
├── .env                      # 환경 변수 설정 (TOKEN, BASE_DIR 등)
└── README.md                 # 프로젝트 문서
```
---

## 주요 기능

1. 엑셀 자동 갱신 (/update)
   - 지정된 엑셀(.xlsm) 파일을 순차적으로 열어 외부 데이터 및 애드인을 새로고침(RefreshAll)합니다.
   - VBA 및 파이썬(win32com)을 통해 안전하게 파일 저장 및 종료를 제어합니다.
2. 데이터 전처리 (/process)
   - 갱신된 엑셀 데이터를 바탕으로 필요한 가공 작업을 수행합니다.
3. 외부 업로드 (/upload)
   - 가공된 데이터를 노션(Notion) 등 외부 플랫폼에 전송합니다.
4. 전체 자동화 (/all)
   - 새로고침 ➔ 전처리 ➔ 업로드 전 과정을 순차적으로 자동 실행합니다.

---

## 시작하기

### 1. 패키지 설치
pip install python-dotenv python-telegram-bot pywin32

### 2. 환경 변수 설정 (.env)
프로젝트 루트에 .env 파일을 만들고 아래 내용을 입력하세요.
TELEGRAM_TOKEN=당신의_텔레그램_봇_토큰
BASE_DIR=엑셀_파일들이_위치한_최상위_폴더_절대경로

### 3. 봇 실행
python bot_trigger.py