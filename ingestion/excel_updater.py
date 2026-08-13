"""
ingestion/excel_updater.py

Concrete ProviderUpdater for databooks that refresh via an Excel add-in on open.
This is your ORIGINAL logic — subprocess open, fixed wait, COM grab, A3 verify,
save/close — moved verbatim into the provider interface. The 30-second wait is
correct HERE, for this provider's known refresh behavior. It is no longer "the
main logic"; it's one provider's implementation.

Two updater flavors are provided:
  ExcelAddinUpdater  — fixed wait (your current, reliable approach)
  ExcelPollingUpdater — adaptive: polls the verify cell until it matches or a
                        timeout ceiling is hit. Use for future providers whose
                        refresh time is variable. Same verify logic, used as the
                        exit condition instead of a fixed sleep.

Both are Windows/COM only and import win32com lazily so the rest of the system
(engine, analysis, tests) imports fine on any OS.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

from ingestion.base import ProviderUpdater, RefreshResult


def _get_excel_app():
    import win32com.client  # lazy: only needed on the Windows box
    return win32com.client.GetActiveObject("Excel.Application")


def _co_init():
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass


class ExcelAddinUpdater(ProviderUpdater):
    """Fixed-wait Excel refresh — your proven approach for KOFR-style books."""

    def __init__(self, name: str, file_path, wait_s: int = 30,
                 verify_cell: str = "A3", verify_sheet_index: int = 1):
        super().__init__(name)
        self.file_path = Path(file_path)
        self.wait_s = wait_s
        self.verify_cell = verify_cell
        self.verify_sheet_index = verify_sheet_index

    def refresh(self) -> RefreshResult:
        started = datetime.now()
        _co_init()

        if not self.file_path.exists():
            return self._result(False, f"파일 없음: {self.file_path}", started=started)

        # 1. open (add-in refreshes on open) — API-block workaround via `start`
        subprocess.Popen(["start", "", str(self.file_path)], shell=True)

        # 2. fixed wait — bounded, predictable for THIS provider
        time.sleep(self.wait_s)

        # 3. grab workbook, verify, save/close
        try:
            excel = _get_excel_app()
        except Exception as e:  # noqa: BLE001
            return self._result(False, f"Excel 객체 실패: {e}", started=started)

        target = self.file_path.name
        wb = None
        for w in excel.Workbooks:
            if w.Name.lower() == target.lower():
                wb = w
                break
        if wb is None:
            return self._result(False, "열린 워크북에서 파일 못 찾음", started=started)

        today = time.strftime("%Y-%m-%d")
        val = str(wb.Sheets(self.verify_sheet_index).Range(self.verify_cell).Value)
        ok = today in val
        detail = f"{self.verify_cell} {'일치' if ok else '불일치'} ({val})"

        wb.Save()
        wb.Close(SaveChanges=True)

        return self._result(ok, detail, verified_date=val, started=started)


class ExcelPollingUpdater(ExcelAddinUpdater):
    """Adaptive-wait variant for providers with VARIABLE refresh latency.

    Same open + verify, but instead of one fixed sleep it polls the verify cell
    every `poll_s` seconds until today's date appears or `timeout_s` is reached.
    Proceeds the moment data is fresh — no wasted time, no under-waiting.
    """

    def __init__(self, name, file_path, timeout_s: int = 120, poll_s: int = 5,
                 verify_cell="A3", verify_sheet_index=1):
        super().__init__(name, file_path, wait_s=0,
                         verify_cell=verify_cell,
                         verify_sheet_index=verify_sheet_index)
        self.timeout_s = timeout_s
        self.poll_s = poll_s

    def refresh(self) -> RefreshResult:
        started = datetime.now()
        _co_init()

        if not self.file_path.exists():
            return self._result(False, f"파일 없음: {self.file_path}", started=started)

        subprocess.Popen(["start", "", str(self.file_path)], shell=True)

        target = self.file_path.name
        today = time.strftime("%Y-%m-%d")
        deadline = time.time() + self.timeout_s
        last_val = None

        while time.time() < deadline:
            time.sleep(self.poll_s)
            try:
                excel = _get_excel_app()
                wb = next((w for w in excel.Workbooks
                           if w.Name.lower() == target.lower()), None)
                if wb is None:
                    continue
                last_val = str(wb.Sheets(self.verify_sheet_index)
                               .Range(self.verify_cell).Value)
                if today in last_val:
                    wb.Save()
                    wb.Close(SaveChanges=True)
                    return self._result(True, f"{self.verify_cell} 일치 ({last_val})",
                                        verified_date=last_val, started=started)
            except Exception:
                continue  # workbook not ready yet; keep polling

        return self._result(False, f"타임아웃 {self.timeout_s}s (마지막: {last_val})",
                            started=started)