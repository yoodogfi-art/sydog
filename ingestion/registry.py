"""
ingestion/registry.py

Maps each provider to the updater that knows how to refresh it, and provides a
dispatcher that runs them uniformly. THIS is the file you edit to add a provider
(alongside writing its updater class if it needs a new mechanism).

The bot and main.py call `refresh_all()` or `refresh_one(name)` — they never
know whether a provider is Excel, API, or anything else.
"""

from __future__ import annotations

import os
from pathlib import Path

from config.paths import RAW_DIR, PROCESSED_DIR

from ingestion.base import RefreshResult
from ingestion.excel_updater import ExcelAddinUpdater, ExcelPollingUpdater
from ingestion.api_updater import ApiUpdater

# Where local databook Excel files live (RAW_DIR from .env).


# External must-refresh files (e.g. the shared Z: drive book).
Z_KOFR = Path(r"Z:/자산운용/301. 펀드운용업무/전략운용본부/FX 관리/data/KR__KOFR_DATABOOK.xlsm")


def build_updaters() -> list:
    """Construct the list of provider updaters. Add entries here.

    Auto-discovers local Excel databooks in RAW_DIR (your current behavior),
    each wrapped in the fixed-wait ExcelAddinUpdater, plus any explicit external
    or non-Excel providers.
    """
    updaters = []

    # 1. Auto-discovered local Excel books -> fixed 30s wait (proven)
    if RAW_DIR.exists():
        for f in RAW_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in (".xlsx", ".xlsm", ".xls") \
                    and not f.name.startswith("~$"):
                updaters.append(ExcelAddinUpdater(name=f.stem, file_path=f, wait_s=30))

    # 2. External required Excel book (Z: drive)
    if Z_KOFR.exists():
        updaters.append(ExcelAddinUpdater(name=Z_KOFR.stem, file_path=Z_KOFR, wait_s=30))

    # 3. Example: a variable-latency Excel provider -> adaptive polling
    # updaters.append(ExcelPollingUpdater(name="slow_book",
    #                 file_path=RAW_DIR / "slow_book.xlsm", timeout_s=120))

    # 4. Example: a REST API provider -> no wait, no COM
    # updaters.append(ApiUpdater(name="bok_base_rate",
    #                 url="https://ecos.bok.or.kr/api/...",
    #                 out_csv=Path(os.getenv("PROCESSED_DIR",
    #                              r"C:\Users\User\databook_processed")) / "bok_base.csv"))

    return updaters


def refresh_all() -> list[RefreshResult]:
    results = []
    for u in build_updaters():
        try:
            results.append(u.refresh())
        except Exception as e:  # noqa: BLE001  (interface should catch, but be safe)
            results.append(RefreshResult(name=u.name, ok=False,
                                         detail=f"unexpected: {e}"))
    return results


def refresh_one(name: str) -> RefreshResult | None:
    for u in build_updaters():
        if u.name == name:
            try:
                return u.refresh()
            except Exception as e:  # noqa: BLE001
                return RefreshResult(name=name, ok=False, detail=f"unexpected: {e}")
    return None