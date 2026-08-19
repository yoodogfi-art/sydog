"""
research/args.py

Independent argument-grammar for instrument commands. Pulled out so /kr_govt,
/kr_govt_plot, and future commands share ONE parser instead of each handler
re-implementing the grammar.

Two grammars live here:

parse_query_args(args)  -> for value commands (/kr_govt ...)
    []                       -> ("snapshot", None)
    ["6m"] / ["14"]          -> ("period", days:int)          trailing window
    ["20260115","20260216"]  -> ("range", (start, end))       date range, space
    ["20260115-20260216"]    -> ("range", (start, end))       date range, dash

parse_offsets(args)     -> for plot commands (/kr_govt_plot ...)
    []            -> []                 (caller supplies its default set)
    ["4"]         -> [4]                (anchor - 4 rows)
    ["4","28"]    -> [4, 28]            (multiple offsets)
    Each must be a non-negative integer (row offset, NOT a period token).

Period tokens (14, 6m, 2w, 1y) are parsed by parse_period below.
"""

from __future__ import annotations

import re
import pandas as pd

_DATE_RE = re.compile(r"^\d{8}$")
_PERIOD_RE = re.compile(r"^(\d+)\s*([dwmy]?)$", re.IGNORECASE)
_UNIT_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


def parse_period(token: str):
    """'14'->(14,'14d'), '6m'->(180,'6m'), '2w'->(14,'2w'). Bare number=days."""
    m = _PERIOD_RE.match(token.strip())
    if not m:
        raise ValueError(f"기간 형식 오류: '{token}' (예: 14, 6m, 2w, 1y)")
    n = int(m.group(1))
    unit = (m.group(2) or "d").lower()
    return n * _UNIT_DAYS[unit], (f"{n}{unit}" if unit != "d" else f"{n}d")


def _two_dates(a: str, b: str):
    start = pd.to_datetime(a, format="%Y%m%d")
    end = pd.to_datetime(b, format="%Y%m%d")
    return (start, end) if start <= end else (end, start)


def parse_query_args(args: list[str]):
    """Grammar for value commands. Returns (kind, payload)."""
    if not args:
        return "snapshot", None

    if len(args) == 1 and "-" in args[0]:
        parts = [p.strip() for p in args[0].split("-")]
        if len(parts) == 2 and all(_DATE_RE.match(p) for p in parts):
            return "range", _two_dates(parts[0], parts[1])

    if len(args) == 2 and _DATE_RE.match(args[0]) and _DATE_RE.match(args[1]):
        return "range", _two_dates(args[0], args[1])

    if len(args) == 1:
        days, tag = parse_period(args[0])
        return "period", (days, tag)

    raise ValueError(
        "사용법: /명령 | /명령 6m | /명령 20260115 20260216"
    )


def parse_offsets(args: list[str]) -> list[int]:
    """Grammar for plot commands: a list of non-negative integer row offsets.
    'anchor - N rows'. Empty list means the caller uses its default set."""
    offsets = []
    for a in args:
        a = a.strip()
        if not a.isdigit():
            raise ValueError(f"오프셋은 정수여야 합니다: '{a}' (예: /kr_govt_plot 4 28)")
        offsets.append(int(a))
    return offsets