"""
research/commands/zscore.py  —  /<instrument>_z [window]

Where does today's level sit versus its own history?
  /kr_govt_z          -> last 1y
  /kr_govt_z 6m       -> last 6 months (any period token: 90, 2w, 3y)
  /kr_govt_z all      -> full history

Reply per column:  10Y: 4.54% | z(1y): +1.85, pct: 92%

This file is also the TEMPLATE for new research features: compute numbers with
analysis/stats.py, format one line, let render_book do the rest.
"""

from __future__ import annotations

from datetime import timedelta

from analysis.stats import percentile_rank, zscore
from research.args import parse_period
from research.render import render_book
from storage.loader import series

DEFAULT_WINDOW = "1y"


def _parse_window(args):
    if len(args) > 1:
        raise ValueError("사용법: /명령_z | /명령_z 6m | /명령_z all")
    token = args[0] if args else DEFAULT_WINDOW
    if token.lower() == "all":
        return None, "all"
    return parse_period(token)  # (days, tag)


def _z_numbers(df, col, days):
    s = series(df, col)  # ascending, NaN dropped
    if len(s) < 3:
        return None
    if days is not None:
        s = s[s.index >= s.index[-1] - timedelta(days=days)]
        if len(s) < 3:
            return None
    z = zscore(s).iloc[-1]
    if z != z:  # NaN: flat series, std = 0
        return None
    return {"current": s.iloc[-1], "z": float(z), "pct": percentile_rank(s), "n": len(s)}


def run(command: str, instrument: dict, args: list[str]) -> str:
    days, tag = _parse_window(args)

    def line(book, tenor, n):
        return (f"{book.head(tenor, book.value(n['current']))}"
                f" | z({tag}): {n['z']:+.2f}, pct: {n['pct']:.0f}%")

    return render_book(
        command, instrument,
        lambda df, col, cols, mode: _z_numbers(df, col, days),
        line, tag=f"z-score {tag}",
    )
