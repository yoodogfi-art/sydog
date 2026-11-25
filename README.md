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
│   └── processor.py            raw Excel → processed CSV, returns ProcessResult
│                               (.files / .warnings / .errors — warnings reach the user)
├── storage/                    ← NEW: where data lives + how it's read
│   └── loader.py               single load path; market vs macro folders split
├── analysis/                   ← statistics over full series (no UI, no transport)
│   ├── align.py                as-of joins — used by /spread to join two books
│   ├── stats.py                z-score, vol, beta, corr, OLS, percentile
│   └── curve_fit.py            KTB curve models (LINEAR/SPLINE/NS/NSS) + forwards
├── research/                   ← Telegram research commands
│   ├── registry.py             ★ list of command kinds ("", "_plot", "_z") — add features here
│   ├── commands/               one file per command kind
│   │   ├── query.py            /kr_govt [6m | 20260115 20260216]
│   │   ├── plot.py             /kr_govt_plot [4 28]        curve: x = tenor
│   │   ├── timeseries.py       /kr_govt_ts [5y] [3Y 10Y]   history: x = date
│   │   ├── spread.py           /spread [card_3y] [3y] [chart]  two books, as-of joined
│   │   ├── brief.py            /brief [3y] [2.0]  curve + spreads + |z| outliers
│   │   ├── sectors.py          KOSPI 섹터 랭킹 — DORMANT (equity, out of FI scope)
│   │   ├── forward.py          /forward [20260115]  (4 model charts + forward table)
│   │   └── zscore.py           /kr_govt_z [1y | all]   ← template for new features
│   ├── style.py                one chart look (palette, Korean font, axes)
│   ├── render.py               numbers → text reply (multi-row vs single, one copy)
│   ├── numbers.py              pure math: current value, deltas
│   ├── columns.py              tenor labels, value columns
│   ├── calendar.py             which rows are real market days
│   ├── args.py                 argument parsing (6m, date ranges, offsets)
│   ├── formatters.py           pluggable display styles (rates/fx/index/points)
│   └── telegram_handlers.py    generic wiring, generated from registry.py
├── bot/                        ← the control surface
│   ├── app.py                  entrypoint; wires feature packages to Telegram
│   ├── update_handlers.py      /update, /update_one → dispatcher
│   └── config_handlers.py      /config, /chatid — runtime self-check
├── config/                     ← the registries you edit
│   ├── instruments.py          command → style / file / cols / labels
│   ├── spreads.py              ★ /spread entries: long leg - short leg, in bp
│   ├── telegram.py             token + chat id LIST for automatic messages
│   ├── sheet_keys.py           sheet name → canonical key
│   └── paths.py                ★ the ONLY module that reads paths from .env
└── main.py                     batch entrypoint: refresh -> process -> send /brief
                                (--no-brief to skip the second message)
``` 




## .env

```ini
RAW_DIR=C:\Users\User\databook_raw
PROCESSED_DIR=C:\Users\User\databook_processed
MACRO_DIR=C:\Users\User\databook_macro
EXTRA_BOOKS=Z:\...\KR__KOFR_DATABOOK.xlsm      ; separated, optional

TELEGRAM_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789,-1001234567890        # comma-separated = fan out
```

### Sending to more than one chat

Automatic messages — the scheduled refresh report, the daily brief, the
startup ping — go to **every** id in `TELEGRAM_CHAT_ID`. A reply to a typed
command still goes only to the chat that asked.

1. Add the bot to the second room. A bot cannot join by itself; for a
   channel it must be an admin.
2. Send `/chatid` there — it replies with the id and whether it is already
   registered.
3. Append it to `TELEGRAM_CHAT_ID`, comma-separated, and restart the bot.

Group ids are negative and supergroup/channel ids start with `-100`: the
minus sign is part of the id. One unreachable chat never blocks the others —
the sender reports the outcome per chat.
