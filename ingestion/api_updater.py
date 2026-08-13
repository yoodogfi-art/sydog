"""
ingestion/api_updater.py

Example of a NON-Excel provider mechanism, to prove the interface holds for
anything. A provider that exposes a REST endpoint needs no 30-second wait, no
COM, no mouse — it fetches, writes a CSV, done. Same refresh() contract.

This is a template: adapt the fetch + parse to a real provider (Bloomberg,
central bank API, data vendor). The point is that adding it touches ONLY this
file plus one registry line — never the dispatcher, never the bot.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ingestion.base import ProviderUpdater


class ApiUpdater(ProviderUpdater):
    """Fetch a series from an HTTP endpoint and write it to PROCESSED_DIR.

    Deliberately dependency-light: uses `requests` lazily so import is safe
    everywhere. Replace `_parse` with the provider's real response shape.
    """

    def __init__(self, name: str, url: str, out_csv, params: dict | None = None,
                 timeout_s: int = 30):
        super().__init__(name)
        self.url = url
        self.out_csv = Path(out_csv)
        self.params = params or {}
        self.timeout_s = timeout_s

    def refresh(self):
        started = datetime.now()
        try:
            import requests
            resp = requests.get(self.url, params=self.params, timeout=self.timeout_s)
            resp.raise_for_status()
            rows = self._parse(resp.json())
        except Exception as e:  # noqa: BLE001
            return self._result(False, f"API 실패: {e}", started=started)

        if not rows:
            return self._result(False, "빈 응답", started=started)

        self._write_csv(rows)
        latest = rows[0].get("일자", "?")
        return self._result(True, f"{len(rows)} rows, latest {latest}",
                            verified_date=latest, started=started)

    # ---- adapt these two to the real provider ---------------------------
    def _parse(self, payload) -> list[dict]:
        """Turn the provider's JSON into a list of {일자, <col>: value} dicts,
        newest first. Override per provider."""
        return payload if isinstance(payload, list) else []

    def _write_csv(self, rows: list[dict]):
        import csv
        self.out_csv.parent.mkdir(parents=True, exist_ok=True)
        headers = list(rows[0].keys())
        with self.out_csv.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            w.writerows(rows)