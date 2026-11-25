"""
research/commands/brief.py  —  /brief [1y|3y|all] [z-threshold]

The one message that answers "what moved?" without being asked. Every other
command needs you to already suspect something; this one scans everything and
reports only what is worth your attention.

  /brief            -> overnight curve, headline spreads, extremes vs 1y
  /brief 3y         -> same, but z-scores measured against 3 years
  /brief 3y 1.5     -> loosen the extreme threshold from 2.0 sigma

Sections
--------
  커브      국고/UST overnight and 1w moves by tenor, in bp
  스프레드   every entry in config/spreads.py: level, 1d, z
  이례치     anything past ±threshold sigma — the part you would otherwise miss
  시장      FX swap points (KRW funding)
  매크로    latest CPI / 산생 print

main.py sends this after the scheduled refresh, so the batch run now says
something instead of only reporting file counts.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from analysis.stats import percentile_rank, zscore
from config.instruments import INSTRUMENTS
from config.spreads import SPREADS
from research.args import parse_period
from research.commands.spread import spread_series
from research.render import load_book
from storage.loader import series

DEFAULT_WINDOW = "1y"
DEFAULT_SIGMA = 2.0
MAX_ALERTS = 12

# Books whose level moves are quoted in bp rather than their own unit.
_RATE_STYLES = {"rates"}

# What the 시장 section shows, in order.
MARKET = ["fx_usd", "fx_eur", "fx_jpy", "fx_cny"]
MACRO = ["cpi", "ind_prod"]
CURVES = ["kr_govt", "us_govt"]


def _chg(s: pd.Series, days: int) -> float | None:
    """Change over the last `days` calendar days, in the series' own unit."""
    prior = s[s.index <= s.index[-1] - timedelta(days=days)]
    return None if prior.empty else float(s.iloc[-1] - prior.iloc[-1])


def _bp(v) -> str:
    return "n/a" if v is None else f"{round(v * 100):+d}"


def _num(v, decimals=2) -> str:
    return "n/a" if v is None else f"{v:+,.{decimals}f}"


def _z_of(s: pd.Series, days: int | None) -> tuple[float, float] | None:
    """(z, percentile) over the window, or None when the series cannot support it."""
    win = s if days is None else s[s.index >= s.index[-1] - timedelta(days=days)]
    if len(win) < 20 or win.std() == 0 or pd.isna(win.std()):
        return None
    z = zscore(win).iloc[-1]
    if pd.isna(z):
        return None
    return float(z), percentile_rank(win)


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------
def _curve_lines() -> list[str]:
    out = []
    for name in CURVES:
        inst = INSTRUMENTS.get(name)
        if not inst:
            continue
        try:
            book = load_book(name, inst)
        except FileNotFoundError:
            continue
        cells = []
        asof = None
        for col in book.cols:
            s = series(book.df, col)
            if len(s) < 2:
                continue
            asof = s.index[-1]
            cells.append(f"{book.label_for(col)} {s.iloc[-1]:.2f} "
                         f"({_bp(_chg(s, 1))}/{_bp(_chg(s, 7))})")
        if cells:
            stamp = f" {asof:%m-%d}" if asof is not None else ""
            out.append(f"*{book.label}*{stamp}  _lvl (1d/1w, bp)_")
            out.append("  " + " · ".join(cells))
    return out


def _spread_lines(days: int | None, tag: str) -> list[str]:
    out = []
    for name, spec in SPREADS.items():
        try:
            s, _ = spread_series(name)
        except Exception:  # noqa: BLE001  a missing book must not kill the brief
            continue
        zp = _z_of(s, days)
        ztxt = "" if zp is None else f" | z {zp[0]:+.2f}"
        d1 = _chg(s, 1)
        out.append(f"  {spec['label']}: {s.iloc[-1]:.0f}bp "
                   f"({'n/a' if d1 is None else f'{d1:+.0f}'}){ztxt}")
    return out


def _alert_lines(days: int | None, tag: str, sigma: float) -> list[str]:
    """Everything past +/- sigma, biggest |z| first. This is the point of the brief."""
    hits: list[tuple[float, str]] = []

    for name, spec in SPREADS.items():
        try:
            s, _ = spread_series(name)
        except Exception:  # noqa: BLE001
            continue
        zp = _z_of(s, days)
        if zp and abs(zp[0]) >= sigma:
            hits.append((abs(zp[0]),
                         f"  {spec['label']}: {s.iloc[-1]:.0f}bp "
                         f"z {zp[0]:+.2f}, pct {zp[1]:.0f}%"))

    for name, inst in INSTRUMENTS.items():
        try:
            book = load_book(name, inst)
        except FileNotFoundError:
            continue
        for col in book.cols:
            s = series(book.df, col)
            zp = _z_of(s, days)
            if zp and abs(zp[0]) >= sigma:
                hits.append((abs(zp[0]),
                             f"  {book.label} {book.label_for(col)}: "
                             f"{book.value(s.iloc[-1])} z {zp[0]:+.2f}, pct {zp[1]:.0f}%"))

    hits.sort(key=lambda h: -h[0])
    if not hits:
        return [f"  ±{sigma:g}σ 이탈 없음 ({tag})"]
    lines = [h[1] for h in hits[:MAX_ALERTS]]
    if len(hits) > MAX_ALERTS:
        lines.append(f"  … 외 {len(hits) - MAX_ALERTS}건")
    return lines


# A percent change off a near-zero base is noise, not information: FX swap
# points sit at -0.9, so a 0.1 move would print as +11%.
_PCT_MIN_BASE = 1.0


def _sector_lines(period: str = "1m", n: int = 3) -> list[str]:
    """Best and worst n sectors vs KOSPI. Full table lives behind /sectors."""
    from research.commands.sectors import rank
    try:
        rows, _, tag = rank(period)
    except Exception:  # noqa: BLE001  the brief must survive a missing book
        return []
    ranked = sorted((r for r in rows if not r["size"] and r["rel"] is not None),
                    key=lambda r: -r["rel"])
    if len(ranked) < 2 * n:
        return []

    def side(items):
        return " · ".join(f"{r['name']} {r['rel']:+.0f}pp" for r in items)

    return [f"*섹터* _{tag} vs KOSPI_",
            f"  상위: {side(ranked[:n])}",
            f"  하위: {side(ranked[-n:][::-1])}"]


def _market_lines(names: list[str]) -> list[str]:
    out = []
    for name in names:
        inst = INSTRUMENTS.get(name)
        if not inst:
            continue
        try:
            book = load_book(name, inst)
        except FileNotFoundError:
            continue
        if not book.cols:
            continue
        s = series(book.df, book.cols[0])     # headline column only
        if len(s) < 2:
            continue
        d1 = _chg(s, 1)
        if inst.get("style") in _RATE_STYLES:
            move = f"{_bp(d1)}bp"
        elif d1 is None:
            move = "n/a"
        else:
            prior = s.iloc[-1] - d1
            move = (f"{d1:+,.2f} ({d1 / prior * 100:+.2f}%)"
                    if abs(prior) >= _PCT_MIN_BASE else f"{d1:+,.2f}")
        out.append(f"  {book.label}: {book.value(s.iloc[-1])}  {move}")
    return out


def _macro_lines(names: list[str]) -> list[str]:
    """Monthly prints carried forward on a daily index, so a 1d delta is always
    zero. What matters is the value and when it last actually moved."""
    out = []
    for name in names:
        inst = INSTRUMENTS.get(name)
        if not inst:
            continue
        try:
            book = load_book(name, inst)
        except FileNotFoundError:
            continue
        for col in book.cols:
            s = series(book.df, col)
            if len(s) < 2:
                continue
            changed = s[s.diff() != 0]
            stamp = f"  _{changed.index[-1]:%Y-%m-%d} 발표_" if len(changed) else ""
            out.append(f"  {book.label} {book.label_for(col)}: "
                       f"{book.value(s.iloc[-1])}{stamp}")
    return out


# ---------------------------------------------------------------------------
def build(window: str = DEFAULT_WINDOW, sigma: float = DEFAULT_SIGMA) -> str:
    days, tag = (None, "all") if window.lower() == "all" else parse_period(window)

    blocks = [["*[데일리 브리프]*  z-window " + tag]]
    blocks.append(_curve_lines())
    blocks.append(["*스프레드*  _lvl (1d)_"] + _spread_lines(days, tag))
    blocks.append([f"*이례치*  _|z| ≥ {sigma:g}_"] + _alert_lines(days, tag, sigma))
    blocks.append(["*시장*"] + _market_lines(MARKET))
    macro = _macro_lines(MACRO)
    if macro:
        blocks.append(["*매크로*"] + macro)

    return "\n\n".join("\n".join(b) for b in blocks if b)


def run(command: str, instrument: dict, args: list[str]) -> str:
    """command/instrument unused: /brief is a fixed-name command."""
    if len(args) > 2:
        raise ValueError("사용법: /brief | /brief 3y | /brief 3y 1.5")
    window = args[0] if args else DEFAULT_WINDOW
    try:
        sigma = float(args[1]) if len(args) > 1 else DEFAULT_SIGMA
    except ValueError:
        raise ValueError(f"'{args[1]}'는 숫자가 아닙니다. 예: /brief 1y 1.5") from None
    return build(window, sigma)
