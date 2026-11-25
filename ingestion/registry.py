"""
ingestion/registry.py

Maps each provider to the updater that knows how to refresh it, and provides a
dispatcher that runs them uniformly. THIS is the file you edit to add a provider
(alongside writing its updater class if it needs a new mechanism).

The bot and main.py call `refresh_all()` or `refresh_one(name)` — they never
know whether a provider is Excel, API, or anything else.
"""

from __future__ import annotations

from config.paths import EXTRA_BOOKS, RAW_DIR

from ingestion.base import RefreshResult
from ingestion.excel_updater import ExcelAddinUpdater, ExcelPollingUpdater  # noqa: F401
from ingestion.api_updater import ApiUpdater  # noqa: F401

EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")
EXCEL_WAIT_S = 30   # the proven fixed wait for the add-in to finish


def build_updaters() -> list:
    """Construct the list of provider updaters. Add entries here.

    Auto-discovers local Excel databooks in RAW_DIR, each wrapped in the
    fixed-wait ExcelAddinUpdater, then adds every book listed in EXTRA_BOOKS
    (.env) — books that must refresh but live outside RAW_DIR, e.g. a shared
    network drive. Paths belong in .env, never here.
    """
    updaters = []

    # 1. Auto-discovered local Excel books -> fixed 30s wait (proven)
    if RAW_DIR.exists():
        for f in sorted(RAW_DIR.iterdir()):
            if (f.is_file() and f.suffix.lower() in EXCEL_SUFFIXES
                    and not f.name.startswith("~$")):
                updaters.append(ExcelAddinUpdater(name=f.stem, file_path=f,
                                                  wait_s=EXCEL_WAIT_S))

    # 2. Books outside RAW_DIR (EXTRA_BOOKS in .env, ';'-separated).
    #    An unreachable network path is skipped, not an error.
    for book in EXTRA_BOOKS:
        if book.exists():
            updaters.append(ExcelAddinUpdater(name=book.stem, file_path=book,
                                              wait_s=EXCEL_WAIT_S))

    # 3. Other mechanisms need no path config, just a line here:
    #    ExcelPollingUpdater(...)  for variable-latency books
    #    ApiUpdater(...)           for REST providers

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