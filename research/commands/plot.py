"""
research/commands/plot.py  —  /<instrument>_plot [offsets...]

Yield-curve plotting -> PNG bytes for Telegram.

Curve shape: x = tenor (1Y, 2Y, ...), one line per selected date.
Color: fresh deep green for the newest curve, fading lighter/milder as the
curve's date gets older.

Date rule (as specified):
  * calendar.py resolves ONLY the anchor ("today" = newest real row).
  * After that, offsets are POSITIONAL row steps in the file (anchor - N rows),
    NOT market-day logic. /kr_govt_plot 4 28 -> rows anchor-4 and anchor-28.
  * The default (no offsets) draws current + 1w + 1mo + 1y, resolved by as-of
    calendar-day lookback (like the snapshot buckets), since those are named
    windows rather than row offsets.

Requires the instrument to be multi-tenor (rates/points style with (N년) cols).
"""

from __future__ import annotations

import io
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")  # headless, no display
import matplotlib.pyplot as plt

from storage.loader import load_market
from research import calendar as cal
from research.args import parse_offsets
from research.columns import DATE_COL, value_columns, tenor_num as _tenor_num
from research.columns import tenor_label

# green fade: index 0 = newest (deepest), later = milder/lighter
_GREEN_FADE = ["#0B6E4F", "#2E9E6B", "#66C08A", "#A9D9B8", "#CDE8D5"]


def _tenor_label(col: str) -> str:
    return tenor_label(col, strip_suffix=False)


def _anchor_pos(df, cols, mode):
    """Newest real row position (skips a blank trailing row) via calendar."""
    return cal._first_real_pos(df, cols)


def _curve_at_pos(df, cols, pos):
    """(tenors, yields, date_str) for a positional row, skipping NaN cols."""
    tenors, vals = [], []
    for c in cols:
        v = df.iloc[pos][c]
        if v == v:  # not NaN
            tenors.append(_tenor_num(c))
            vals.append(float(v))
    date_str = df.iloc[pos][DATE_COL].strftime("%Y-%m-%d")
    order = sorted(range(len(tenors)), key=lambda i: tenors[i])
    return ([tenors[i] for i in order],
            [vals[i] for i in order],
            [_tenor_label(cols[j]) for j in
             sorted(range(len(cols)), key=lambda k: _tenor_num(cols[k]))],
            date_str)


def _asof_pos(df, cols, target_date, mode):
    idx = cal.asof_index(df, cols, target_date, mode)
    return df.index.get_loc(idx) if idx is not None else None


def plot_curves(command: str, instrument: dict, offsets: list[int]) -> tuple[bytes, str]:
    """Return (png_bytes, caption).

    offsets == []  -> default set: current, 1w, 1mo, 1y (named windows)
    offsets given  -> anchor-N positional rows, one curve each.
    """
    key = instrument.get("file", command)
    label = instrument.get("label", command)
    mode = instrument.get("date_mode", cal.DEFAULT_MODE)
    decimals = 3

    df = load_market(key)
    cols = value_columns(df, instrument.get("cols"))
    anchor = _anchor_pos(df, cols, mode)
    if anchor is None:
        raise ValueError(f"[{label}] no data to plot")

    # Build the list of (position, series_label) to draw, newest first.
    series = []
    if offsets:
        for n in offsets:
            pos = anchor + n
            if pos < df.shape[0]:
                series.append((pos, f"t-{n}"))
    else:
        anchor_date = df.iloc[anchor][DATE_COL]
        series.append((anchor, "current"))
        for days, name in [(7, "1w"), (30, "1mo"), (365, "1y")]:
            pos = _asof_pos(df, cols, anchor_date - timedelta(days=days), mode)
            if pos is not None and pos != anchor:
                series.append((pos, name))

    if not series:
        raise ValueError(f"[{label}] no rows for requested offsets")

    # Draw
    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    xticklabels = None
    for i, (pos, name) in enumerate(series):
        tenors, vals, labels, date_str = _curve_at_pos(df, cols, pos)
        if not tenors:
            continue
        color = _GREEN_FADE[min(i, len(_GREEN_FADE) - 1)]
        ax.plot(range(len(tenors)), vals, marker="o", linewidth=2,
                color=color, label=f"{name} ({date_str})")
        xticklabels = labels

    if xticklabels:
        ax.set_xticks(range(len(xticklabels)))
        ax.set_xticklabels(xticklabels)
    ax.set_ylabel("yield (%)")
    ax.set_title(f"{label} yield curve")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{v:.{decimals}f}"))
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    if offsets:
        cap = f"[{label}] " + ", ".join(n for _, n in series)
    else:
        cap = f"[{label}] current / 1w / 1mo / 1y"
    return buf.getvalue(), cap


def run(command: str, instrument: dict, args: list[str]) -> tuple[bytes, str]:
    return plot_curves(command, instrument, parse_offsets(args))
