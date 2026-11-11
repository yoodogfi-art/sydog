"""
research/commands/query.py  —  /<instrument> [period | date range]

  /kr_govt                      -> snapshot: current + 1d/1w/1mo/1y
  /kr_govt 6m   (14, 2w, 1y)    -> change over a trailing period
  /kr_govt 20260115 20260216    -> change over a date range (or 20260115-20260216)
"""

from __future__ import annotations

from research import numbers as nb
from research.args import parse_query_args
from research.render import render_book


# ---- line formats -----------------------------------------------------------
def _snapshot_line(book, tenor, n):
    d = [book.delta(n[k], n[f"{k}_base"]) for k in ("d1", "w1", "m1", "y1")]
    return (f"{book.head(tenor, book.value(n['current']))}"
            f" | 1d: {d[0]}, 1w: {d[1]}, 1mo: {d[2]}, 1y: {d[3]}")


def _delta_line(book, tenor, n):
    return f"{book.head(tenor, book.value(n['current']))} | Δ: {book.delta(n['delta'], n['base'])}"


# ---- the three query kinds ----------------------------------------------------
def snapshot(command: str, instrument: dict) -> str:
    return render_book(command, instrument, nb.snapshot_numbers, _snapshot_line)


def period(command: str, instrument: dict, days: int, tag: str) -> str:
    return render_book(
        command, instrument,
        lambda df, col, cols, mode: nb.period_numbers(df, col, cols, mode, days),
        _delta_line, tag=tag, multi_empty="no data in range",
    )


def spec(command: str, instrument: dict, start_date, end_date) -> str:
    return render_book(
        command, instrument,
        lambda df, col, cols, mode: nb.spec_numbers(df, col, cols, mode, start_date, end_date),
        _delta_line, tag=f"{start_date:%Y%m%d}-{end_date:%Y%m%d}",
        multi_empty="no data in range", single_empty="no data in range",
    )


# ---- entry point ------------------------------------------------------------
def run(command: str, instrument: dict, args: list[str]) -> str:
    kind, payload = parse_query_args(args)
    if kind == "snapshot":
        return snapshot(command, instrument)
    if kind == "period":
        days, tag = payload
        return period(command, instrument, days, tag)
    s, e = payload  # "range"
    return spec(command, instrument, s, e)
