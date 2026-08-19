"""
research/formatters.py

Each display *style* is a formatter registered here. The engine computes raw
numbers (current value + deltas) and hands them to the formatter named by the
instrument's `style`. To add a new display type, write a function and add it to
FORMATTERS — no engine edit, no config edit beyond referencing the style name.

A formatter receives a Bucket and returns the change-string for one lookback,
plus a value-string for the headline. Formatters never touch files or dates;
they are pure display.

Contract
--------
value_str(value, decimals)            -> "3.11%"  / "1426.73"
delta_str(delta, base, decimals)      -> "+10bp"  / "-10 (-0.04%)"  / "n/a"

`delta`  = new - old (raw float in the instrument's native unit)
`base`   = the older value, used as % denominator where relevant
"""

from __future__ import annotations


# ---- rates: value in %, change in bp --------------------------------------
def _rates_value(value, decimals):
    return f"{value:.{decimals}f}%"

def _rates_delta(delta, base, decimals):
    if delta is None:
        return "n/a"
    return f"{round(delta * 100):+d}bp"


# ---- fx: level, change in level + % ---------------------------------------
def _fx_value(value, decimals):
    return f"{value:.{decimals}f}"

def _fx_delta(delta, base, decimals):
    if delta is None or base in (None, 0):
        return "n/a"
    pct = (delta / base) * 100
    return f"{delta:+.{decimals}f} ({pct:+.2f}%)"


# ---- index: level, change in points + % (same math as fx, own style key) --
def _index_value(value, decimals):
    return f"{value:.{decimals}f}"

def _index_delta(delta, base, decimals):
    if delta is None or base in (None, 0):
        return "n/a"
    pct = (delta / base) * 100
    return f"{delta:+.{decimals}f} ({pct:+.2f}%)"


# ---- points: level, change in points only (no %) --------------------------
def _points_value(value, decimals):
    return f"{value:.{decimals}f}"

def _points_delta(delta, base, decimals):
    if delta is None:
        return "n/a"
    return f"{delta:+.{decimals}f}"


# ---------------------------------------------------------------------------
# Registry: style name -> (value_fn, delta_fn, default_decimals, default_multi_row)
# ---------------------------------------------------------------------------
FORMATTERS = {
    "rates": {
        "value": _rates_value,
        "delta": _rates_delta,
        "decimals": 2,
        "multi_row": True,
    },
    "fx": {
        "value": _fx_value,
        "delta": _fx_delta,
        "decimals": 2,
        "multi_row": False,
    },
    "index": {
        "value": _index_value,
        "delta": _index_delta,
        "decimals": 2,
        "multi_row": False,
    },
    "points": {
        "value": _points_value,
        "delta": _points_delta,
        "decimals": 2,
        "multi_row": True,
    },
}


def get_style(style: str):
    if style not in FORMATTERS:
        raise KeyError(
            f"unknown style '{style}'. Known: {list(FORMATTERS)}. "
            f"Register it in research/formatters.py."
        )
    return FORMATTERS[style]