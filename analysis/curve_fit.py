"""
analysis/curve_fit.py

KTB curve fitting and forward rates. Pure math: no files, no Telegram, no charts.

Models (each returns a continuously compounded zero-rate function zero(t)):
  LINEAR : bootstrap + linear zero interpolation (reprices the market, error ~ 0)
  SPLINE : fixed-knot natural cubic spline on zero rates (price least squares)
  NS     : Nelson-Siegel (4 parameters)
  NSS    : Nelson-Siegel-Svensson (6 parameters)

Input is a list of bond dicts. par_bond() builds one from a tenor and its yield,
for sources like kr_govt.csv that quote yields by tenor rather than by issue.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq, least_squares

MODELS = ["LINEAR", "SPLINE", "NS", "NSS"]
SPLINE_KNOTS = [0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30, 50]

# forward grid (months): monthly up to 1y, then quarterly up to 3y
GRID_MONTHS = list(range(1, 13)) + list(range(15, 37, 3))


# ---------------------------------------------------------------------------
# Bond cash flows and prices
# ---------------------------------------------------------------------------
def is_eom(d: date) -> bool:
    return (d + timedelta(days=1)).month != d.month


def coupon_schedule(mat: date, val: date):
    eom = is_eom(mat)
    dates, k = [], 0
    while True:
        d = mat - relativedelta(months=6 * k)
        if eom:
            d = d + relativedelta(day=31)
        if d <= val:
            return sorted(dates), d
        dates.append(d)
        k += 1


def build_cashflows(b: dict, val: date) -> None:
    if b["coupon"] == 0:
        b["zero"] = True
        b["cf_dates"] = [b["maturity"]]
        b["cf_amt"] = np.array([100.0])
    else:
        b["zero"] = False
        dates, prev = coupon_schedule(b["maturity"], val)
        amt = np.full(len(dates), b["coupon"] / 2.0)
        amt[-1] += 100.0
        b["w"] = (dates[0] - val).days / (dates[0] - prev).days
        b["cf_dates"] = dates
        b["cf_amt"] = amt
    b["cf_t"] = np.array([(d - val).days / 365.0 for d in b["cf_dates"]])
    b["t_mat"] = b["cf_t"][-1]


def dirty_from_yield(b: dict, y: float) -> float:
    """y: decimal, semi-annual compounding."""
    if b["zero"]:
        return 100.0 / (1 + y / 2) ** (2 * b["cf_t"][0])
    n = np.arange(len(b["cf_amt"]))
    return float(np.sum(b["cf_amt"] / (1 + y / 2) ** (b["w"] + n)))


def yield_from_dirty(b: dict, p: float) -> float:
    return brentq(lambda y: dirty_from_yield(b, y) - p, -0.2, 1.0)


def par_bond(tenor_years: int, yield_pct: float, val: date) -> dict:
    """A synthetic bond for one quoted tenor: coupon = yield, matures exactly
    tenor_years after val. Modified duration comes from a +/-1bp bump."""
    b = {
        "coupon": yield_pct,
        "maturity": val + relativedelta(years=tenor_years),
        "tenor": tenor_years,
        "yield_pct": yield_pct,
        "fit": {},
    }
    build_cashflows(b, val)
    y = yield_pct / 100
    b["mkt_dirty"] = dirty_from_yield(b, y)
    up, down = dirty_from_yield(b, y + 1e-4), dirty_from_yield(b, y - 1e-4)
    b["mod_dur"] = -(up - down) / (2e-4 * b["mkt_dirty"])
    return b


class Universe:
    """All cash flows in one array, for fast repricing."""

    def __init__(self, bonds):
        self.bonds = bonds
        self.t = np.concatenate([b["cf_t"] for b in bonds])
        self.a = np.concatenate([b["cf_amt"] for b in bonds])
        self.idx = np.concatenate([np.full(len(b["cf_t"]), i) for i, b in enumerate(bonds)])
        self.mkt = np.array([b["mkt_dirty"] for b in bonds])
        self.dur = np.array([max(b["mod_dur"], 0.05) for b in bonds])

    def prices(self, zero_fn):
        df = np.exp(-zero_fn(self.t) * self.t)
        return np.bincount(self.idx, weights=self.a * df, minlength=len(self.bonds))

    def resid_bp(self, zero_fn):
        """Price error / (P x MD), approximately the yield error in bp."""
        return (self.prices(zero_fn) - self.mkt) / (self.mkt * self.dur) * 1e4

    def cc_yield_range(self):
        by = sorted(self.bonds, key=lambda b: b["mod_dur"])
        cc = lambda y: 2 * np.log(1 + y / 200)
        return (cc(by[0]["yield_pct"]), cc(by[-1]["yield_pct"]),
                float(np.mean([cc(b["yield_pct"]) for b in self.bonds])))


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
def _ns_load(t, tau):
    x = np.maximum(np.asarray(t, dtype=float), 1e-8) / tau
    f1 = (1 - np.exp(-x)) / x
    return f1, f1 - np.exp(-x)


def fit_ns(U):
    y_s, y_l, _ = U.cc_yield_range()

    def make(p):
        b0, b1, b2, t1 = p

        def z(t):
            f1, f2 = _ns_load(t, t1)
            return b0 + b1 * f1 + b2 * f2
        return z

    lb, ub = [-0.10, -0.30, -0.30, 0.05], [0.20, 0.30, 0.30, 15.0]
    best = None
    for t1 in (0.5, 1.0, 2.0, 4.0, 8.0):
        r = least_squares(lambda p: U.resid_bp(make(p)), [y_l, y_s - y_l, 0.0, t1],
                          bounds=(lb, ub))
        if best is None or r.cost < best.cost:
            best = r
    return make(best.x)


def fit_nss(U):
    y_s, y_l, _ = U.cc_yield_range()

    def make(p):
        b0, b1, b2, b3, t1, t2 = p

        def z(t):
            f1, f2 = _ns_load(t, t1)
            _, f3 = _ns_load(t, t2)
            return b0 + b1 * f1 + b2 * f2 + b3 * f3
        return z

    lb = [-0.10, -0.30, -0.30, -0.30, 0.05, 0.50]
    ub = [0.20, 0.30, 0.30, 0.30, 10.0, 40.0]
    best = None
    for t1 in (0.5, 1.5, 3.0):
        for t2 in (5.0, 10.0, 20.0):
            r = least_squares(lambda p: U.resid_bp(make(p)),
                              [y_l, y_s - y_l, 0.0, 0.0, t1, t2], bounds=(lb, ub))
            if best is None or r.cost < best.cost:
                best = r
    return make(best.x)


def fit_spline(U):
    t_mats = np.array([b["t_mat"] for b in U.bonds])
    t_max = t_mats.max()
    knots, last = [], 0.0
    for k in [x for x in SPLINE_KNOTS if x < t_max] + [t_max]:
        if np.any((t_mats > last) & (t_mats <= k + 1e-9)):
            knots.append(float(k))
            last = k
    if knots[0] > t_mats.min():
        knots.insert(0, float(t_mats.min()))
    knots = np.array(sorted(set(knots)))
    _, _, y_avg = U.cc_yield_range()

    def make(z):
        if len(knots) < 2:
            return lambda t: np.full_like(np.asarray(t, dtype=float), z[0])
        cs = CubicSpline(knots, z, bc_type="natural")
        return lambda t: cs(np.clip(np.asarray(t, dtype=float), knots[0], knots[-1]))

    r = least_squares(lambda z: U.resid_bp(make(z)), np.full(len(knots), y_avg))
    return make(r.x)


def fit_linear(U):
    """Bootstrap: solve each maturity's zero rate in order to reprice the market."""
    groups = {}
    for i, b in enumerate(U.bonds):
        groups.setdefault(round(b["t_mat"], 8), []).append(i)

    K, Z = [], []

    def make(Kx, Zx):
        Kx, Zx = np.array(Kx), np.array(Zx)
        return lambda t: np.interp(np.asarray(t, dtype=float), Kx, Zx)

    for tg in sorted(groups):
        ids = groups[tg]

        def f(x):
            zf = make(K + [tg], Z + [x])
            err = 0.0
            for i in ids:
                b = U.bonds[i]
                p = float(np.sum(b["cf_amt"] * np.exp(-zf(b["cf_t"]) * b["cf_t"])))
                err += (p - b["mkt_dirty"]) / (b["mkt_dirty"] * max(b["mod_dur"], 0.05))
            return err

        try:
            x = brentq(f, -0.2, 0.5)
        except ValueError:
            x = Z[-1] if Z else 0.03
        K.append(tg)
        Z.append(x)

    return make(K, Z)


FITTERS = {"LINEAR": fit_linear, "SPLINE": fit_spline, "NS": fit_ns, "NSS": fit_nss}


# ---------------------------------------------------------------------------
# Forwards
# ---------------------------------------------------------------------------
def mlabel(m: int) -> str:
    return f"{m // 12}y" if m % 12 == 0 else f"{m}m"


def build_forwards(zero_fn, val: date) -> pd.DataFrame:
    """Forward matrix in % (semi-annual): start months x end months."""
    pts = [0] + GRID_MONTHS
    d = {m: val + relativedelta(months=m) for m in pts}
    t = {m: (d[m] - val).days / 365.0 for m in pts}
    DF = {m: (1.0 if m == 0 else float(np.exp(-zero_fn(np.array([t[m]]))[0] * t[m])))
          for m in pts}

    starts = GRID_MONTHS[:-1]
    ends = GRID_MONTHS[1:]
    matrix = pd.DataFrame(index=[mlabel(m) for m in starts],
                          columns=[mlabel(m) for m in ends], dtype=float)
    for s in starts:
        for e in ends:
            if e > s:
                tau = t[e] - t[s]
                matrix.loc[mlabel(s), mlabel(e)] = \
                    2 * ((DF[s] / DF[e]) ** (1 / (2 * tau)) - 1) * 100
    return matrix


def fit_curves(bonds: list[dict], val: date, models=MODELS) -> dict:
    """Fit every model. Writes each bond's fitted yield to b["fit"][model] and
    returns {model: {"rmse", "max_abs", "matrix"}}."""
    U = Universe(bonds)
    out = {}
    for m in models:
        zero_fn = FITTERS[m](U)
        for b, price in zip(bonds, U.prices(zero_fn)):
            y = yield_from_dirty(b, price) * 100
            b["fit"][m] = {"yield": y, "err": (y - b["yield_pct"]) * 100}
        errs = np.array([b["fit"][m]["err"] for b in bonds])
        out[m] = {
            "rmse": float(np.sqrt(np.mean(errs ** 2))),
            "max_abs": float(np.max(np.abs(errs))),
            "matrix": build_forwards(zero_fn, val),
        }
    return out
