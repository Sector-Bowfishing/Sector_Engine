"""Bowfishing Wind Engine (research): wind speed x direction x fetch x history -> bank surface + exposure + ranking.
Wind only — no clarity, temperature, fish, moon or tournament inputs. Internal research output; no user-facing labels.

Physics is the FROZEN Candidate (CEM EM 1110-2-1100 II-2-36..39, frozen duration rule, frozen class bounds), mirrored in
Python and verified identical to the app's Swift `wind-cem` (Stage 3E check: max |dHm0| = 0 over 43,138 rows).
Optional wave memory (M4) is applied only if it passed its own pre-registered promotion rule.
Definitions (exposure rank, P map, ranking, alternatives) are frozen in docs/intelligence/wind/bowfishing/WIND_BOWFISHING_SCORE_V1.md.

  python -m sector_wind.bowfishing check        # mirror vs wind-cem on a grid
"""
from __future__ import annotations

import base64, gzip, json, math, os, struct
import numpy as np

G = 9.80665
NB = 120
MPH = 0.44704
CHOP_BOUNDS_M = (0.0254, 0.0762, 0.1524, 0.3048)
CHOP = {1: "Protected", 2: "Ripple", 3: "Light chop", 4: "Moderate chop", 5: "Rough"}
TEXTURE_UPPER = (1.0, 3.0, 5.5)
TEXTURE = {1: "Glassy", 2: "Rippled", 3: "Textured", 4: "Broken"}
TEX_FLOOR = {1: 1, 2: 2, 3: 2, 4: 3}
RANK = {1: "PROTECTED", 2: "LOW_EXPOSURE", 3: "MODERATE_EXPOSURE", 4: "HIGH_EXPOSURE", 5: "EXTREME_EXPOSURE"}
LAKES = {"guntersville": "Guntersville", "wheeler": "Wheeler", "wilson": "Wilson", "pickwick": "Pickwick"}
DIRS8 = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}
SPEEDS_MPH = (5, 10, 15, 20)
STEADY_H = 6.0


# ── frozen physics ───────────────────────────────────────────────────────────────────────────

def ustar(u):
    return u * math.sqrt(0.001 * (1.1 + 0.035 * u))


def cem(u, x, t_s=None):
    if u <= 0 or x <= 0:
        return 0.0
    us = ustar(u); xd = x
    if t_s is not None:
        xd = min(xd, 5.23e-3 * (G * t_s / us) ** 1.5 * us * us / G)
    return min(4.13e-2 * math.sqrt(G * xd / (us * us)) * us * us / G, 2.115e2 * us * us / G)


def tp(u, x, t_s=None):
    if u <= 0 or x <= 0:
        return 0.0
    us = ustar(u); xd = x
    if t_s is not None:
        xd = min(xd, 5.23e-3 * (G * t_s / us) ** 1.5 * us * us / G)
    h = 4.13e-2 * math.sqrt(G * xd / (us * us)) * us * us / G
    if h > 2.115e2 * us * us / G:
        return 2.398e2 * us / G
    return 0.651 * (G * xd / (us * us)) ** (1 / 3) * us / G


def chop_class(h):
    return 1 + sum(h >= b for b in CHOP_BOUNDS_M)


def texture_class(u):
    return 1 if u < TEXTURE_UPPER[0] else 2 if u < TEXTURE_UPPER[1] else 3 if u < TEXTURE_UPPER[2] else 4


def surface_p(h, u):
    """Frozen scoring map P = max(chop class, texture floor)."""
    return max(chop_class(h), TEX_FLOOR[texture_class(u)])


def nine_ray(row, theta):
    b = int(round(theta / 3.0)) % NB
    return float(np.mean([row[(b + k) % NB] for k in range(-4, 5)]))


def rays(row, theta):
    b = int(round(theta / 3.0)) % NB
    return [float(row[(b + k) % NB]) for k in range(-4, 5)]


def decision_class(u, fetch_m, duration_h=STEADY_H):
    """Surface class P for steady wind u (m/s) over fetch (m) — the BWIS D1 / matrix definition."""
    return surface_p(cem(u, fetch_m, duration_h * 3600), u)


# ── geometry ─────────────────────────────────────────────────────────────────────────────────

# load_lake() (reads the app's fetch-table assets) is research-only: sector_wind_research.bowfishing_assets.


def km(a, b):
    return 6371000 * 2 * math.asin(math.sqrt(math.sin(math.radians(b[0] - a[0]) / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2))


def geometry_reason(r9, eff):
    """Plain reason from the 9 rays (±12°) — what limits this bank's fetch for this wind."""
    mn, mx = min(r9), max(r9)
    if eff < 250:
        return f"sheltered: land within {int(mx)} m on every upwind ray (cove/lee shore)"
    if mn < 0.25 * eff and mx > 2 * eff:
        return f"partially shielded: some upwind rays blocked at {int(mn)} m by a point or island, others open to {mx / 1000:.1f} km"
    if eff >= 3000:
        return f"long open fetch: {eff / 1000:.1f} km of unobstructed water upwind"
    return f"moderate open fetch: about {eff / 1000:.1f} km of water upwind"


# ── wave memory (only if promoted) ───────────────────────────────────────────────────────────

def group_speed(tp_s):
    return G * tp_s / (4 * math.pi) if tp_s > 0 else 0.0


# ── bank evaluation / ranking ────────────────────────────────────────────────────────────────

def evaluate_bank(L, i, speed_ms, dir_from, duration_h=STEADY_H, hist_hm0=None):
    b = L["banks"][i]
    if b.get("belowResolution"):
        return {"bankId": b["id"], "exposureRank": "UNKNOWN", "confidence": "unknown", "reason": "bank below fetch-raster resolution: fetch unknown (never treated as sheltered)"}
    row = L["table"][i]; r9 = rays(row, dir_from); eff = float(np.mean(r9)); direct = float(row[int(round(dir_from / 3.0)) % NB])
    h_static = cem(speed_ms, eff, duration_h * 3600)
    h = max(h_static, hist_hm0) if hist_hm0 is not None else h_static
    lo, hi = cem(max(0, speed_ms - 1), eff * 0.7, duration_h * 3600), cem(speed_ms + 1, eff * 1.3, duration_h * 3600)
    p = surface_p(h, speed_ms)
    return {"bankId": b["id"], "anchor": b["anchor"], "region": b.get("region"), "windFromDeg": dir_from, "speedMS": speed_ms,
            "effectiveFetchM": round(eff, 1), "directFetchM": round(direct, 1), "effectiveFetchRays": [round(x) for x in r9],
            "predictedHm0M": round(h, 4), "predictedHm0In": round(h / 0.0254, 2), "chopClass": chop_class(h), "predictedSurfaceClass": p,
            "predictedSurfaceLabel": CHOP[p], "predictedTextureClass": texture_class(speed_ms),
            "exposureRank": RANK[chop_class(h)], "memoryContributionM": round(h - h_static, 4),
            "predictedHm0RangeIn": [round(lo / 0.0254, 2), round(hi / 0.0254, 2)],     # the ±1 m/s × 0.7-1.3 fetch range behind `confidence`
            "confidence": "firm" if chop_class(lo) == chop_class(hi) else "boundary",
            "reason": geometry_reason(r9, eff)}


def lake_percentiles(L, dir_from):
    ok = [i for i, b in enumerate(L["banks"]) if not b.get("belowResolution")]
    eff = np.array([nine_ray(L["table"][i], dir_from) for i in ok])
    order = eff.argsort().argsort()
    return {i: round(100.0 * o / max(len(ok) - 1, 1), 1) for i, o in zip(ok, order)}


def rank_banks_for_wind(L, speed_ms, dir_from, recent_history=None, duration_h=STEADY_H, top=5):
    """Best protected / moderate / worst exposed banks for this wind. recent_history: per-bank prior Hm0 (memory) or None."""
    pct = lake_percentiles(L, dir_from)
    res = []
    for i, b in enumerate(L["banks"]):
        if b.get("belowResolution"):
            continue
        r = evaluate_bank(L, i, speed_ms, dir_from, duration_h, (recent_history or {}).get(b["id"]))
        r["relativeLakePercentile"] = pct[i]; res.append(r)
    res.sort(key=lambda r: (r["predictedSurfaceClass"], r["predictedHm0M"], r["effectiveFetchM"]))
    mid = [r for r in res if r["exposureRank"] == "MODERATE_EXPOSURE"]
    return {"best": res[:top], "moderate": mid[:top], "worst": res[::-1][:top], "all": res}


def nearby_alternatives(L, ranked_all, bank, radii=(2000, 5000, 10000), n=3):
    """For a HIGH/EXTREME bank: same-lake banks within 2/5/10 km with a lower surface class, or >= 50% shorter fetch and no worse class."""
    out = []
    for rad in radii:
        c = [r for r in ranked_all if r["bankId"] != bank["bankId"] and km(r["anchor"], bank["anchor"]) <= rad and
             (r["predictedSurfaceClass"] < bank["predictedSurfaceClass"] or
              (r["effectiveFetchM"] <= 0.5 * bank["effectiveFetchM"] and r["predictedSurfaceClass"] <= bank["predictedSurfaceClass"]))]
        c.sort(key=lambda r: (km(r["anchor"], bank["anchor"]), r["predictedSurfaceClass"]))
        if c:
            out = [{**{k: r[k] for k in ("bankId", "effectiveFetchM", "predictedSurfaceLabel", "exposureRank", "reason")},
                    "distanceM": round(km(r["anchor"], bank["anchor"])), "radiusM": rad} for r in c[:n]]
            break
    return out
