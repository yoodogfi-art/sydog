# Telegram Excel Automation Bot

텔레그램 봇을 통해 엑셀 데이터 자동 갱신, 전처리, 업로드 등의 작업을 원격으로 제어하는 파이썬 프로젝트입니다.

---

## 프로젝트 구조

1. 폴더 구조 및 모듈 배치 (텍스트 구조도)
봇이 전체 시스템의 뼈대(관제탑, 코어, 외부 연동)를 한눈에 파악할 수 있도록 적어줍니다.
```text
data_management/
├── ingestion/                  ← NEW: how data gets refreshed
│   ├── base.py                 provider interface (ProviderUpdater, RefreshResult)
│   ├── excel_updater.py        your 30s logic, wrapped as a provider (+ polling variant)
│   ├── api_updater.py          example non-Excel provider (REST)
│   ├── registry.py             maps providers→updaters, dispatcher (refresh_all/one)
│   └── processor.py            raw Excel → processed CSV (was core/data_processor)
├── storage/                    ← NEW: where data lives + how it's read
│   └── loader.py               single load path; market vs macro folders split
├── analysis/                   ← NEW: statistics over full series
│   ├── align.py                as-of joins (daily market ↔ monthly macro)
│   └── stats.py                z-score, vol, beta, corr, OLS, percentile
├── research/                   ← presentation (mostly unchanged)
│   ├── query_engine.py         now loads via storage.loader
│   ├── formatters.py           pluggable display styles
│   └── telegram_handlers.py    snapshot/spec commands
├── bot/                        ← NEW home for the control surface
│   ├── app.py                  entrypoint (replaces bot_trigger.py)
│   └── update_handlers.py      /update, /update_one → dispatcher
├── config/                     ← the registries you edit
│   ├── instruments.py          command → style
│   └── sheet_keys.py           sheet name → canonical key
│   └── paths.py 
├── core/                       ← kept for back-compat (old import path still works)
└── main.py                     batch entrypoint (uses same dispatcher)
``` 