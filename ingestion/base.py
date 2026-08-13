"""
ingestion/base.py

The provider-abstraction interface. EVERY way of refreshing source data —
Excel add-in, REST API, web scrape, whatever a future provider needs — is a
subclass of ProviderUpdater implementing one method: refresh().

Why this exists
---------------
Refresh *behavior* varies per provider (the 30-second Excel wait is correct for
ONE provider, not a universal rule). Instead of piling `if provider == ...`
branches into one updater function, each provider gets its own small class that
implements the same interface. The dispatcher and the bot never learn a single
provider-specific detail — they just call .refresh() and read the result.

Contract
--------
refresh() -> RefreshResult
    Do whatever this provider needs to bring its source data up to date, then
    return a RefreshResult. MUST NOT raise for expected failures (timeout, stale
    data) — capture those in RefreshResult.ok=False so the dispatcher can report
    them uniformly. May raise only for genuinely unexpected/programmer errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RefreshResult:
    """Uniform outcome of a refresh, whatever the provider mechanism was."""
    name: str                       # provider/databook identifier
    ok: bool                        # did the refresh succeed + verify?
    detail: str = ""                # human-readable status ("A3 일치 (2026-08-12)")
    verified_date: Optional[str] = None   # the date we confirmed, if any
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None

    def duration_s(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def telegram_line(self) -> str:
        mark = ":D" if self.ok else "!!"
        d = f" ({self.duration_s():.0f}s)" if self.finished_at else ""
        return f"{mark} `{self.name}`: {self.detail}{d}"


class ProviderUpdater:
    """Base class. Subclass per provider mechanism and implement refresh().

    Common config (name, timeout, verification cell) lives here so subclasses
    stay tiny. Subclasses set attributes in __init__ and override refresh().
    """

    def __init__(self, name: str):
        self.name = name

    def refresh(self) -> RefreshResult:  # pragma: no cover - interface
        raise NotImplementedError(
            f"{type(self).__name__} must implement refresh()."
        )

    # helper so subclasses build results consistently
    def _result(self, ok: bool, detail: str = "", verified_date=None,
                started=None) -> RefreshResult:
        return RefreshResult(
            name=self.name, ok=ok, detail=detail,
            verified_date=verified_date,
            started_at=started or datetime.now(),
            finished_at=datetime.now(),
        )