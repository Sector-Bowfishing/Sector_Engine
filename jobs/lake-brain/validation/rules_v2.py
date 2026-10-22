"""Lake Brain rules v2 — pure-Python mirror of the Swift rules (`lake-level-rules-v2`, `doy15-percentile-v2`).

Mirrors brains/lake/runtime/LakeBrain/{LakeLevelBaseline,LakeLevelClassifier}.swift. It is checked against the Swift rules on the shared
fixture contracts/conformance/lake_rules_v2.json (test_rules_v2.py here; LakeRulesV2Tests.swift there) BEFORE it is used for the hold-out
protocol (holdout_v2.py). Specification: docs/brains/LAKE_BRAIN_RULES_V2_PREREGISTRATION.md section 1. Nothing here may be tuned to results.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np

# ---- constants (== Swift LakeLevelBaseline / LakeLevelClassifier) -------------------------------------------------------------------------------
WINDOW_DAYS = 7
MAX_BASIS_REGULATED = 30
MAX_BASIS_NATURAL = 60
COMPLETE_YEAR_DAYS = 329
SUFFICIENT_YEARS = 5
LIMITED_YEARS = 2
PROVISIONAL_YEARS, STANDARD_YEARS, FULL_YEARS = 5, 10, 15
MIN_RATE_SAMPLES = 20
RATE_YEARS = 30                                   # rate climatology: every year in the last 30 (partial years included), unchanged from v1
GRID = (0, 2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100)
G = {p: i for i, p in enumerate(GRID)}
STABLE_FLOOR_REGULATED = 0.10
STABLE_FLOOR_NATURAL = 0.05
RAPID_FLOOR = 0.25
_CUM = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)

TIER_NONE, TIER_PROVISIONAL, TIER_STANDARD, TIER_FULL = "NONE", "PROVISIONAL", "STANDARD", "FULL"


# ---- rounding / calendar ------------------------------------------------------------------------------------------------------------------------
def round_half_away(x, nd: int):
    """Swift `(x * 10^nd).rounded() / 10^nd` (round half away from zero); works on floats and ndarrays."""
    f = 10.0 ** nd
    return np.sign(x) * np.floor(np.abs(x) * f + 0.5) / f


def r2(x):
    return round_half_away(x, 2)


def doy365(d: dt.date) -> int:
    """Day of year on a 365-day calendar; Feb 29 shares Feb 28's index (Swift LakeLevelCalendar.doy365)."""
    day = 28 if (d.month == 2 and d.day == 29) else d.day
    return _CUM[d.month - 1] + day


# ---- R1: tiers and gating -----------------------------------------------------------------------------------------------------------------------
def tier(basis_years: int) -> str:
    return TIER_FULL if basis_years >= FULL_YEARS else TIER_STANDARD if basis_years >= STANDARD_YEARS \
        else TIER_PROVISIONAL if basis_years >= PROVISIONAL_YEARS else TIER_NONE


def baseline_status(basis_years: int, has_daily: bool = True) -> str:
    return "SUFFICIENT" if basis_years >= SUFFICIENT_YEARS else "LIMITED" if basis_years >= LIMITED_YEARS else ("INSUFFICIENT" if has_daily else "NONE")


def basis_cap(regulated: bool) -> int:
    return MAX_BASIS_REGULATED if regulated else MAX_BASIS_NATURAL


def historical_state(current: float, p02: float, p10: float, p90: float, p98: float, tier_: str):
    """-> (state, flags). VERY_UNUSUAL only at tier FULL; PROVISIONAL carries `historicalProvisional`."""
    if tier_ == TIER_NONE:
        return "INSUFFICIENT_HISTORY", []
    raw = "VERY_UNUSUAL" if (current < p02 or current > p98) else "UNUSUAL" if (current < p10 or current > p90) else "NORMAL"
    if raw == "VERY_UNUSUAL" and tier_ != TIER_FULL:
        raw = "UNUSUAL"
    return raw, (["historicalProvisional"] if tier_ == TIER_PROVISIONAL else [])


# ---- R2: trend ----------------------------------------------------------------------------------------------------------------------------------
def trend(delta24h, delta72h=None, rate_p95=None, regulated: bool = True):
    """-> (label, rapid_threshold_ft or None, flags).  `rate_p95` = seasonal p95 of |Δ24h| (None = no rate baseline)."""
    if delta24h is None:
        return "UNKNOWN", None, []
    flags = []
    a = abs(delta24h)
    if rate_p95 is not None and not (isinstance(rate_p95, float) and math.isnan(rate_p95)):
        rapid = max(rate_p95, RAPID_FLOOR)
    else:
        rapid = RAPID_FLOOR
        flags.append("rateBaselineLimited")
    if a > rapid:
        return ("RISING_RAPIDLY" if delta24h > 0 else "FALLING_RAPIDLY"), rapid, flags
    if delta72h is not None:
        mean = delta72h / 3
    else:
        mean = delta24h
        flags.append("trend24hFallback")
    floor = STABLE_FLOOR_REGULATED if regulated else STABLE_FLOOR_NATURAL
    if abs(mean) <= floor:
        return "STABLE", rapid, flags
    return ("RISING" if mean > 0 else "FALLING"), rapid, flags


# ---- baseline (doy15-percentile-v2), vectorised and Swift-exact ----------------------------------------------------------------------------------
_GRID = np.array(GRID, dtype=float)
_WIN = np.array([[((doy - 1 + off) % 365 + 365) % 365 for off in range(-WINDOW_DAYS, WINDOW_DAYS + 1)] for doy in range(1, 366)])   # (365, 15) 0-based doy


def quantile_rows(M: np.ndarray, ps: np.ndarray = _GRID) -> np.ndarray:
    """Type-7 quantiles of each row of M (NaN = absent), Swift `LakeBaselineBuilder.quantile` arithmetic; NaN row if empty."""
    S = np.sort(M, axis=1)                                          # NaN sorts last
    n = np.sum(~np.isnan(M), axis=1)
    out = np.full((M.shape[0], len(ps)), np.nan)
    ok = n > 0
    if not ok.any():
        return out
    h = (n[ok, None].astype(float) - 1.0) * ps[None, :] / 100.0
    lo = np.floor(h).astype(int)
    hi = np.minimum(lo + 1, n[ok, None] - 1)
    Sok = S[ok]
    a = np.take_along_axis(Sok, lo, axis=1)
    b = np.take_along_axis(Sok, hi, axis=1)
    out[ok] = a + (h - lo) * (b - a)
    return out


def grid_round(q: np.ndarray) -> np.ndarray:
    return round_half_away(q, 3)


def dense_year(dates_values: dict) -> np.ndarray:
    """(365, 2) array: level samples (all of one calendar year) by doy365 (slot 1 holds Feb 29's value, which shares Feb 28's index)."""
    A = np.full((365, 2), np.nan)
    for d, v in dates_values.items():
        i = doy365(d) - 1
        if np.isnan(A[i, 0]):
            A[i, 0] = v
        else:
            A[i, 1] = v
    return A


def level_grid(year_arrays: list) -> tuple:
    """year_arrays: list of (365,2) -> (levelQ (365,23) NaN where no sample, n (365,))."""
    if not year_arrays:
        return np.full((365, len(GRID)), np.nan), np.zeros(365, dtype=int)
    V = np.concatenate(year_arrays, axis=1)                         # (365, 2*Y)
    W = V[_WIN].reshape(365, -1)                                    # (365, 15*2*Y)
    n = np.sum(~np.isnan(W), axis=1)
    return grid_round(quantile_rows(W)), n


class Baseline:
    """Result of `build_baseline` — the Swift LakeLevelBaseline fields the rules read."""
    __slots__ = ("complete_years", "basis_years", "status", "tier", "level_q", "level_n", "rate_q", "rate_n", "n_daily")

    def p(self, doy: int, p: int):
        return self.level_q[doy - 1, G[p]]


def build_baseline(daily: dict, today: dt.date, regulated: bool = True, with_rates: bool = True, _cache: dict | None = None) -> Baseline:
    """Swift `LakeBaselineBuilder.build`. `daily` = {date: ft}. Only rows with date <= today are used. `_cache` may hold dense per-year arrays."""
    rows = {d: v for d, v in daily.items() if d <= today}
    cy = today.year
    by_year: dict = {}
    for d, v in rows.items():
        by_year.setdefault(d.year, {})[d] = v
    per_year = {y: len(m) for y, m in by_year.items()}
    complete = sorted(y for y, n in per_year.items() if y < cy and n >= COMPLETE_YEAR_DAYS)
    basis = complete[-basis_cap(regulated):]
    b = Baseline()
    b.complete_years, b.basis_years = complete, basis
    b.n_daily = len(rows)
    b.status = baseline_status(len(basis), bool(rows))
    b.tier = tier(len(basis))
    cache = _cache if _cache is not None else {}
    def lev(y):
        k = ("L", y)
        if k not in cache:
            cache[k] = dense_year(by_year[y])
        return cache[k]
    if len(basis) >= LIMITED_YEARS:
        b.level_q, b.level_n = level_grid([lev(y) for y in basis])
    else:
        b.level_q, b.level_n = np.full((365, len(GRID)), np.nan), np.zeros(365, dtype=int)
    b.rate_q, b.rate_n = np.full((365, len(GRID)), np.nan), np.zeros(365, dtype=int)
    if with_rates:
        rate_years = [y for y in sorted(per_year) if y > cy - RATE_YEARS]
        arrs = []
        for y in rate_years:
            k = ("R", y)
            if k not in cache:
                A = np.full((365, 2), np.nan)
                for d, v in by_year[y].items():
                    pv = rows.get(d - dt.timedelta(days=1))
                    if pv is None:
                        continue
                    i = doy365(d) - 1
                    x = abs(v - pv)
                    if np.isnan(A[i, 0]):
                        A[i, 0] = x
                    else:
                        A[i, 1] = x
                cache[k] = A
            arrs.append(cache[k])
        if arrs:
            V = np.concatenate(arrs, axis=1)
            W = V[_WIN].reshape(365, -1)
            n = np.sum(~np.isnan(W), axis=1)
            q = grid_round(quantile_rows(W))
            q[n < MIN_RATE_SAMPLES] = np.nan
            b.rate_q, b.rate_n = q, n
    return b
