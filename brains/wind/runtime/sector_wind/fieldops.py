"""Field operations (Stage 3A Track C): where and when to collect, and the blind session packet.

  python -m sector_wind.fieldops opportunities --store local:$MIRROR [--predictions field/evaluated/*.jsonl] [--nights 2]
  python -m sector_wind.fieldops packet --store local:$MIRROR --lake guntersville --night 2026-10-09 [--block 01] [--pairs 6] [--practice]

Nothing here changes the Candidate. The planner's per-bank numbers are a PLANNING ESTIMATE from the
frozen formulas (NBM wind at the bank, 9-ray ±12° fetch, steady-state CEM Hm0, frozen class and
texture boundaries). The prediction that is SCORED is always the app's Candidate re-evaluated as of
the record time by `wind-eval`. Geometry types here are a planner heuristic for pair diversity; the
observer records their own on the form.

Blinding: the OBSERVER-SHEET has only pair id, neutral X/Y, bank id, coordinates, navigation links,
order and time window. Exposure, fetch, Hm0, class and which bank is expected calmer exist only in
the SEALED-KEY, which the observer must not open."""
from __future__ import annotations

import argparse
import base64
import csv
import glob
import gzip
import hashlib
import json
import math
import os
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np

from .interp import CutoutIndex, blend, blend_wind
from .sample import circular_error, iso, parse_iso

CANDIDATE = "wind-candidate-2026.10.stage2-baseline"
IOS = os.environ.get("SECTOR_WIND_IOS", os.path.expanduser("~/Desktop/Development/iOS/sector-wind"))
FIELD = os.environ.get("SECTOR_WIND_FIELD", os.path.expanduser("~/Desktop/Sector Handoffs/Wind/field"))
GEOM_CACHE = os.path.expanduser("~/Library/Caches/sector-wind/fetch-build/nhd")
NAMES = {"guntersville": "Guntersville", "wheeler": "Wheeler", "wilson": "Wilson", "pickwick": "Pickwick"}
LOCAL_TZ_OFFSET_H = -5        # CDT through 2026-11-01; the packet prints UTC as the authority
CHOP_IN = [1, 3, 6, 12]       # frozen class boundaries (inches, Hm0_mid)
TEXTURE_FLOOR = {"T1": 1, "T2": 2, "T3": 2, "T4": 3}
WIND_BINS = [(0, 2, "<2"), (2, 4, "2-4"), (4, 6.5, "4-6.5"), (6.5, 9, "6.5-9")]
GEOMETRY_TYPES = ["open main lake", "cove", "behind a point", "island-shielded", "creek arm"]
NIGHT_BLOCKS = [(1, 4), (3, 6), (5, 8)]      # UTC hour blocks inside the rubric night 01-08 UTC (3 h sessions)
PAIR_MIN_M, PAIR_MAX_M = 300, 1500
TIE = 0.20                    # frozen: pairs with < 20% Hm0 contrast are excluded from concordance
PREFERRED_RATIO = 2.0         # planner preference only (informative pairs); never a scoring rule
BOAT_MS = 4.5                 # ~10 mph night running speed for the time estimate
OBS_MIN = 8                   # minutes on station per bank (class, texture, photo, optional handheld)
UNSAFE_MS = 9.0               # above the top stratum (6.5-9 m/s): not planned


# ── fetch tables + frozen formulas ───────────────────────────────────────────────────────────

def load_table(lake):
    p = os.path.join(IOS, f"Sector/Assets.xcassets/FishIntel/Wind/{NAMES[lake]}WindFetch.dataset/{lake}.windfetch.json.gz")
    o = json.load(gzip.open(p))
    T = np.frombuffer(base64.b64decode(o["tableBase64"]), dtype="<u2").reshape(len(o["banks"]), 120).astype(float) * 10
    return o, T


def mean12(T, theta):
    b = int(round(theta / 3.0)) % 120
    return T[:, [(b + k) % 120 for k in range(-4, 5)]].mean(axis=1)


def cem_hm0(u, x):
    """Frozen CEM II-2-36/37 steady fetch-limited Hm0 (m). No duration limit here: planning estimate."""
    if u is None or u <= 0 or x <= 0:
        return 0.0
    g = 9.80665
    us = u * (0.001 * (1.1 + 0.035 * u)) ** 0.5
    return min(4.13e-2 * (g * x / us ** 2) ** 0.5 * us ** 2 / g, 2.115e2 * us ** 2 / g)


def chop_class(hm0_m):
    inch = float(hm0_m) / 0.0254
    return 1 + sum(int(inch >= c) for c in CHOP_IN)


def texture(u):
    return "T1" if u < 1.0 else "T2" if u < 3.0 else "T3" if u < 5.5 else "T4"


def wind_bin(u):
    return next((lab for lo, hi, lab in WIND_BINS if lo <= u < hi), ">9 (not planned)")


def quadrant(d):
    return None if d is None else ["N", "E", "S", "W"][int(((d + 45) % 360) // 90)]


# ── geometry heuristic (planner diversity only) ──────────────────────────────────────────────

class LakeGeometry:
    """Island rings from the cached NHD polygon the fetch table was built from (same source)."""
    def __init__(self, lake):
        self.islands = None
        p = os.path.join(GEOM_CACHE, f"{lake}.geojson")
        if not os.path.exists(p):
            return
        from shapely.geometry import shape, MultiPolygon
        from shapely.ops import unary_union, transform
        from shapely.strtree import STRtree
        from pyproj import Transformer
        j = json.load(open(p))
        wgs = unary_union([shape(f["geometry"]) for f in j["features"]])
        self.to = Transformer.from_crs(4326, 32616, always_xy=True).transform
        utm = transform(self.to, wgs).buffer(0)
        polys = list(utm.geoms) if isinstance(utm, MultiPolygon) else [utm]
        rings = [r for p in polys for r in p.interiors]
        self.islands = STRtree(rings) if rings else None
        self.rings = rings

    def ray_ends_on_island(self, lat, lon, theta, dist):
        if not self.islands or dist <= 0:
            return False
        from shapely.geometry import Point
        x, y = self.to(lon, lat)
        th = math.radians(theta)
        end = Point(x + dist * math.sin(th), y + dist * math.cos(th))
        idx = self.islands.query(end.buffer(30))
        return any(self.rings[i].distance(end) <= 30 for i in idx)


def geometry_type(row, theta, bank_meta, geo: LakeGeometry, lat, lon):
    b = int(round(theta / 3.0)) % 120
    eff = float(np.mean([row[(b + k) % 120] for k in range(-4, 5)]))
    near = [float(np.mean([row[(b + s + k) % 120] for k in range(-4, 5)])) for s in range(-20, 21, 5)]
    # island-shielded: the wind-direction ray ends on an island AND the island actually cuts the fetch
    # (the ±60° neighbourhood has at least twice the effective fetch)
    if geo and eff < 1500 and eff < 0.5 * max(near) and geo.ray_ends_on_island(lat, lon, theta, row[b]):
        return "island-shielded"
    mx, med = float(row.max()), float(np.median(row))
    if mx < 800:
        return "cove"
    if bank_meta.get("basinClass") in ("minorTributary", "largeTributaryArm"):
        return "creek arm"
    im = int(np.argmax(row))
    if row[(im + 60) % 120] >= 0.5 * mx and row[(im + 30) % 120] < 0.15 * mx and row[(im - 30) % 120] < 0.15 * mx:
        return "creek arm"
    if eff < 0.33 * max(near):
        return "behind a point"
    if med >= 1500:
        return "open main lake"
    return "other"


# ── forecast access ──────────────────────────────────────────────────────────────────────────

def newest_cycle(store, lake, now, back=8):
    t = now.replace(minute=0, second=0, microsecond=0)
    for k in range(back + 1):
        c = store.get_json(f"nbm/{lake}/{t - timedelta(hours=k):%Y%m%d%H}.json.gz")
        if c:
            return c
    return None


def lake_hour(c, valid_iso, tol_min=90):
    """The step valid at that hour, or the nearest step within 90 min (NBM is 3-hourly beyond +24 h)."""
    t = parse_iso(valid_iso)
    best = min(c["steps"], key=lambda s: abs((parse_iso(s["validTime"]) - t).total_seconds()), default=None)
    if best is None or abs((parse_iso(best["validTime"]) - t).total_seconds()) > tol_min * 60:
        return None
    return best


def lake_median(step):
    sp = [x for x in step["speedMS"] if x is not None]
    uv = [(-s * math.sin(math.radians(d)), -s * math.cos(math.radians(d))) for s, d in zip(step["speedMS"], step["dirFromDeg"])
          if s is not None and d is not None]
    if not sp:
        return None, None
    u = float(np.median([a for a, _ in uv])) if uv else 0.0; v = float(np.median([b for _, b in uv])) if uv else 0.0
    return float(np.median(sp)), (math.degrees(math.atan2(-u, -v)) + 360) % 360


# ── coverage gaps (counts only; never accuracy) ──────────────────────────────────────────────

def current_coverage(pred_paths):
    rows = []
    for p in pred_paths or []:
        for path in glob.glob(p):
            rows += [json.loads(l) for l in open(path) if l.strip()]
    rows = [r for r in rows if "practice" not in (r.get("tags") or [])]
    n = len(rows)
    share = lambda c: {k: (v / n if n else 0.0) for k, v in c.items()}
    return {"n": n,
            "wind": share(Counter(wind_bin(r["windMS"]) for r in rows if r.get("windMS") is not None)),
            "quadrant": share(Counter(quadrant(r.get("dirFromDeg")) for r in rows)),
            "lake": share(Counter(r["lake"] for r in rows)),
            "geometry": Counter(r.get("geometryType") for r in rows),
            "nights": Counter((r.get("createdAtUTC") or "")[:10] for r in rows)}


def gap(share, target):
    return max(0.0, target - share) / target


# ── opportunities ────────────────────────────────────────────────────────────────────────────

def candidate_pairs(o, T, theta, u_by_bank, geo, max_pairs=400, seed=0):
    """All informative pairs a short boat ride apart for wind FROM theta: Hm0 contrast >= 20% (frozen
    tie rule) required; ratio >= 2 preferred. Planning estimate from the frozen formulas."""
    ok = np.array([not b["belowResolution"] for b in o["banks"]])
    m = mean12(T, theta)
    lat = np.array([b["standoff"][0] if b["standoff"] else np.nan for b in o["banks"]])
    lon = np.array([b["standoff"][1] if b["standoff"] else np.nan for b in o["banks"]])
    c = math.cos(math.radians(float(np.nanmean(lat))))
    idx = np.where(ok)[0]
    hm0 = np.array([cem_hm0(u_by_bank[i], m[i]) if ok[i] else 0.0 for i in range(len(m))])
    pcls = np.array([max(chop_class(hm0[i]), TEXTURE_FLOOR[texture(u_by_bank[i])]) for i in range(len(m))])
    rng = random.Random(seed)
    out = []
    for i in rng.sample(list(idx), min(2500, len(idx))):
        d = np.hypot((lat[idx] - lat[i]) * 111320, (lon[idx] - lon[i]) * 111320 * c)
        near = idx[(d >= PAIR_MIN_M) & (d <= PAIR_MAX_M)]
        if len(near) == 0 or hm0[i] <= 0:
            continue
        j = int(near[np.argmin(hm0[near])])
        ratio = hm0[i] / hm0[j] if hm0[j] > 0 else float("inf")
        if (hm0[i] - hm0[j]) / hm0[i] < TIE:
            continue
        out.append({"i": i, "j": j, "ratio": ratio, "classDiffers": bool(pcls[i] > pcls[j]), "distM": float(np.hypot((lat[i] - lat[j]) * 111320, (lon[i] - lon[j]) * 111320 * c))})
    out.sort(key=lambda p: -min(p["ratio"], 50))
    return out[:max_pairs], m, hm0, lat, lon


def bank_winds(c, valid_iso, lat, lon, grid):
    step = lake_hour(c, valid_iso)
    if step is None:
        return None, None
    ci = CutoutIndex(grid["cells"], grid["lat"], grid["lon"], grid["nx"])
    us, ds = [], []
    for a, b in zip(lat, lon):
        if np.isnan(a):
            us.append(None); ds.append(None); continue
        wt = ci.weights(float(a), float(b))
        s, d = blend_wind(step["speedMS"], step["dirFromDeg"], wt)
        us.append(s); ds.append(d)
    return us, ds


def opportunities(store, pred_paths=None, nights=2, now=None):
    now = now or datetime.now(timezone.utc)
    cov = current_coverage(pred_paths)
    breezy_share = cov["wind"].get("4-6.5", 0) + cov["wind"].get("6.5-9", 0)
    out = {"generatedAt": iso(now), "coverage": {k: (dict(v) if isinstance(v, Counter) else v) for k, v in cov.items()}, "windows": []}
    for lake in NAMES:
        c = newest_cycle(store, lake, now)
        if not c:
            continue
        o, T = load_table(lake)
        geo = LakeGeometry(lake)
        grid = store.get_json(c["grid"])
        day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for dd in range(0, nights + 1):
            for h0, h1 in NIGHT_BLOCKS:
                hours = [day0 + timedelta(days=dd, hours=h) for h in range(h0, h1 + 1)]
                if hours[0] <= now:
                    continue
                steps = [lake_hour(c, iso(h)) for h in hours]
                if any(s is None for s in steps):
                    continue
                med = [lake_median(s) for s in steps]
                speeds = [m[0] for m in med]; dirs = [m[1] for m in med]
                u = float(np.median(speeds)); d0 = dirs[len(dirs) // 2]
                spread = max(circular_error(x, d0) for x in dirs) if u >= 1.0 else None
                stable = 1.0 if spread is None or spread <= 22.5 else max(0.0, 1 - (spread - 22.5) / 45)
                mid = iso(hours[len(hours) // 2])
                lat = np.array([b["standoff"][0] if b["standoff"] else np.nan for b in o["banks"]])
                lon = np.array([b["standoff"][1] if b["standoff"] else np.nan for b in o["banks"]])
                ub, _ = bank_winds(c, mid, lat, lon, grid)
                ub = [x if x is not None else 0.0 for x in ub]
                pairs, m, hm0, _, _ = candidate_pairs(o, T, d0, ub, geo, max_pairs=150)
                # informative = above the frozen tie rule, ratio >= 2 AND a different predicted class (a calm
                # night gives every bank class 1: those pairs can only tie, so they carry no exposure information)
                strong = [p for p in pairs if p["ratio"] >= PREFERRED_RATIO and p["classDiffers"]]
                gtypes = Counter(geometry_type(T[p["i"]], d0, o["banks"][p["i"]], geo, lat[p["i"]], lon[p["i"]]) for p in pairs[:60]) + \
                    Counter(geometry_type(T[p["j"]], d0, o["banks"][p["j"]], geo, lat[p["j"]], lon[p["j"]]) for p in pairs[:60])
                wb = wind_bin(u)
                if wb.startswith(">9"):
                    value, why = 0.0, "forecast above 9 m/s: outside the strata and unsafe; not planned"
                else:
                    g_wind = gap(cov["wind"].get(wb, 0), 0.10)
                    if wb in ("4-6.5", "6.5-9") and breezy_share < 1 / 3:
                        g_wind += 0.5          # protocol §D: at least a third of sessions on 4-9 m/s nights
                    g_quad = gap(cov["quadrant"].get(quadrant(d0), 0), 0.25) if u >= 1.0 else 0.0
                    g_lake = gap(cov["lake"].get(lake, 0), 0.25)
                    g_geom = sum(gap(min(cov["geometry"].get(t, 0), 5) / 5, 1.0) for t in GEOMETRY_TYPES if gtypes.get(t)) / len(GEOMETRY_TYPES)
                    pair_term = min(1.0, len(strong) / 12) if u >= 1.0 else 0.0     # calm: pairs tie; surface obs still useful
                    night_used = cov["nights"].get(iso(hours[0])[:10], 0) / max(cov["n"], 1)
                    g_night = 1.0 if night_used < 0.15 else 0.0
                    value = round(stable * (1.2 * g_wind + 0.8 * g_quad + 0.6 * g_lake + 1.0 * g_geom + 1.4 * pair_term) * g_night, 3)
                    why = (f"wind bin {wb} (gap {g_wind:.2f}), quadrant {quadrant(d0) if u >= 1 else 'calm'} (gap {g_quad:.2f}), "
                           f"lake gap {g_lake:.2f}, geometry types reachable {dict(gtypes)}, informative pairs {len(strong)}, "
                           f"direction spread {spread if spread is None else round(spread)}°")
                out["windows"].append({"lake": lake, "nightOf": (hours[0] + timedelta(hours=LOCAL_TZ_OFFSET_H)).strftime("%Y-%m-%d"),
                                       "blockUTC": f"{iso(hours[0])} -> {iso(hours[-1])}", "nbmInit": c["initTime"],
                                       "leadHours": round((hours[0] - parse_iso(c["initTime"])).total_seconds() / 3600),
                                       "medianWindMS": round(u, 2), "medianWindMph": round(u / 0.44704, 1), "dirFromDeg": round(d0),
                                       "directionSpreadDeg": None if spread is None else round(spread), "windBin": wb,
                                       "informativePairs": len(strong), "pairsAboveTie": len(pairs),
                                       "geometryTypesReachable": dict(gtypes), "value": value, "why": why})
    out["windows"].sort(key=lambda w: (-w["value"], w["leadHours"]))
    return out


# ── packet ───────────────────────────────────────────────────────────────────────────────────

def _route(pairs, lat, lon, c):
    """Greedy nearest-neighbour cluster: start at the most informative pair, then add the nearest
    pair (by midpoint) within 4 km of the cluster. Keeps a realistic boat session."""
    if not pairs:
        return []
    mid = lambda p: ((lat[p["i"]] + lat[p["j"]]) / 2, (lon[p["i"]] + lon[p["j"]]) / 2)
    dist = lambda a, b: math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * c)
    route = [pairs[0]]; used = {pairs[0]["i"], pairs[0]["j"]}
    rest = pairs[1:]
    while rest:
        last = mid(route[-1])
        rest = [p for p in rest if p["i"] not in used and p["j"] not in used]
        near = [p for p in rest if dist(mid(p), last) <= 4000]
        if not near:
            break
        nxt = min(near, key=lambda p: dist(mid(p), last) / min(p["ratio"], 10))
        route.append(nxt); used |= {nxt["i"], nxt["j"]}
        rest.remove(nxt)
    return route


def packet(store, lake, night, block=None, n_pairs=6, practice=False, seed=None, now=None):
    now = now or datetime.now(timezone.utc)
    nd = datetime.fromisoformat(night).replace(tzinfo=timezone.utc)
    h0, h1 = next((b for b in NIGHT_BLOCKS if block is None or b[0] == int(block)), NIGHT_BLOCKS[0])
    start = nd + timedelta(days=1, hours=h0)          # the night of local date `night` = early UTC hours of the next date
    end = nd + timedelta(days=1, hours=h1)
    mid = start + timedelta(hours=(h1 - h0) // 2)
    c = newest_cycle(store, lake, now)
    if not c or lake_hour(c, iso(mid)) is None:
        raise SystemExit(f"no archived NBM cycle covers {iso(mid)} for {lake}; packets need a forecast (run closer to the night)")
    o, T = load_table(lake)
    geo = LakeGeometry(lake)
    grid = store.get_json(c["grid"])
    u_l, d_l = lake_median(lake_hour(c, iso(mid)))
    lat = np.array([b["standoff"][0] if b["standoff"] else np.nan for b in o["banks"]])
    lon = np.array([b["standoff"][1] if b["standoff"] else np.nan for b in o["banks"]])
    ub, db = bank_winds(c, iso(mid), lat, lon, grid)
    ub0 = [x if x is not None else 0.0 for x in ub]
    seed = seed if seed is not None else int(hashlib.sha256(f"{lake}|{night}|{h0}".encode()).hexdigest()[:8], 16)
    pairs, m, hm0, _, _ = candidate_pairs(o, T, d_l, ub0, geo, max_pairs=300, seed=seed)
    cc = math.cos(math.radians(float(np.nanmean(lat))))
    # diversity: prefer pairs whose exposed/protected geometry types differ, and informative ratios
    for p in pairs:
        p["gA"] = geometry_type(T[p["i"]], d_l, o["banks"][p["i"]], geo, lat[p["i"]], lon[p["i"]])
        p["gB"] = geometry_type(T[p["j"]], d_l, o["banks"][p["j"]], geo, lat[p["j"]], lon[p["j"]])
    pairs.sort(key=lambda p: -(min(p["ratio"], 10) + (3 if p["classDiffers"] else 0) + (2 if p["gA"] != p["gB"] else 0)
                               + (1 if p["ratio"] >= PREFERRED_RATIO else 0)))
    route = _route(pairs, lat, lon, cc)[:n_pairs]
    rng = random.Random(seed)
    tag = "PRACTICE" if practice else "COUNTED"
    folder = os.path.join(FIELD, "plans", f"{night}-{lake}" + ("-PRACTICE" if practice else ""))
    if os.path.exists(os.path.join(folder, "SEALED-KEY.json")):
        raise SystemExit(f"{folder} already has a sealed key; packets are never overwritten (delete it deliberately first)")
    os.makedirs(folder, exist_ok=True)
    sheet, key, links = [], [], []
    t_cursor = start
    prev = None
    order = 0
    for n, p in enumerate(route, 1):
        pid = f"{lake[:2].upper()}{night.replace('-', '')}-P{n}"
        banks = [(p["i"], "A"), (p["j"], "B")]; rng.shuffle(banks)
        for lab, (k, role) in zip(("X", "Y"), banks):
            order += 1
            if prev is not None:
                t_cursor += timedelta(seconds=math.hypot((lat[k] - lat[prev]) * 111320, (lon[k] - lon[prev]) * 111320 * cc) / BOAT_MS)
            prev = k
            b = o["banks"][k]
            sheet.append({"order": order, "pairId": pid, "bank": lab, "bankId": b["id"], "lat": round(float(lat[k]), 6), "lon": round(float(lon[k]), 6),
                          "targetTimeUTC": t_cursor.strftime("%H:%M"), "appleMaps": f"https://maps.apple.com/?ll={lat[k]:.6f},{lon[k]:.6f}&q={pid}-{lab}"})
            links.append(f"{order:2d}. {pid} {lab}  https://maps.apple.com/?ll={lat[k]:.6f},{lon[k]:.6f}&q={pid}-{lab}")
            t_cursor += timedelta(minutes=OBS_MIN)
            u = ub[k]
            pc = int(chop_class(hm0[k]))
            tx = texture(u) if u is not None else None
            key.append({"pairId": pid, "bank": lab, "role": role, "bankId": b["id"], "fetchM": round(float(m[k])), "hm0M": round(float(hm0[k]), 4),
                        "chopClass": pc, "texturePrediction": tx, "predictedClass": int(max(pc, TEXTURE_FLOOR[tx])) if tx else None,
                        "windMS": None if u is None else round(u, 2), "dirFromDeg": None if db[k] is None else round(db[k]),
                        "geometryType": p["gA"] if role == "A" else p["gB"], "geometryTypeSource": "planner heuristic (diversity only; the observer records their own)"})
    diags = []
    for n, p in enumerate(route, 1):
        pid = f"{lake[:2].upper()}{night.replace('-', '')}-P{n}"
        A = next(e for e in key if e["pairId"] == pid and e["role"] == "A"); Bk = next(e for e in key if e["pairId"] == pid and e["role"] == "B")
        r = lambda x, y: round(x / y, 3) if (x and y) else None
        diags.append({"pairId": pid, "bankA": A["bankId"], "bankB": Bk["bankId"], "bankALabel": A["bank"], "bankBLabel": Bk["bank"],
                      "fetchA": A["fetchM"], "fetchB": Bk["fetchM"], "fetchRatio": r(A["fetchM"], Bk["fetchM"]),
                      "hm0A": A["hm0M"], "hm0B": Bk["hm0M"], "hm0Ratio": r(A["hm0M"], Bk["hm0M"]),
                      "texturePredictionA": A["texturePrediction"], "texturePredictionB": Bk["texturePrediction"],
                      "predictedClassA": A["predictedClass"], "predictedClassB": Bk["predictedClass"],
                      "windA": A["windMS"], "windB": Bk["windMS"],
                      "windDifference": round(A["windMS"] - Bk["windMS"], 2) if A["windMS"] is not None and Bk["windMS"] is not None else None,
                      "geometryTypeA": A["geometryType"], "geometryTypeB": Bk["geometryType"], "boatDistanceM": round(p["distM"]),
                      "tieExcluded": (A["hm0M"] - Bk["hm0M"]) / A["hm0M"] < TIE if A["hm0M"] else True})
    lead = lake_hour(c, iso(mid))["leadHours"]
    minutes = round((t_cursor - start).total_seconds() / 60)
    used = lake_hour(c, iso(mid))
    sealed = {"SEALED": "Scorer only. The observer must not open this file before the session is scored.",
              "candidateId": CANDIDATE, "forecastInit": c["initTime"], "validTime": iso(mid), "forecastStepValid": used["validTime"],
              "leadHours": used["leadHours"],
              "windowUTC": [iso(start), iso(end)], "lake": lake, "lakeWindMS": round(u_l, 2), "lakeWindFromDeg": round(d_l),
              "geometryVersion": o["geometryVersion"], "status": tag, "estimateNote": "planning estimate (steady CEM, NBM at bank, frozen boundaries); "
              "the SCORED prediction is wind-eval as of each record time", "pairs": diags, "banks": key}
    json.dump(sealed, open(os.path.join(folder, "SEALED-KEY.json"), "w"), indent=1)
    with open(os.path.join(folder, "OBSERVER-SHEET.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sheet[0])); w.writeheader(); w.writerows(sheet)
    open(os.path.join(folder, "MAP-LINKS.txt"), "w").write("\n".join(links) + "\n")
    local = lambda t: (t + timedelta(hours=LOCAL_TZ_OFFSET_H)).strftime("%a %b %d %I:%M %p")
    readme = f"""SECTOR WIND FIELD SESSION — {lake.title()} — night of {night}  [{tag}]
{'=' * 72}
Window: {iso(start)} -> {iso(end)} UTC  ({local(start)} -> {local(end)} CDT)
Pairs: {len(route)}  ·  Banks: {len(sheet)}  ·  Estimated time on the water: ~{minutes} min plus the run to the first bank
Forecast used to plan: NBM init {c['initTime']} (+{lead} h). The plan does not tell you what the water will do.

BEFORE YOU GO
  - Read the five surface classes aloud (form: Diagnostics > Developer > Wind > Wind field observation).
  - Phone charged, GPS on, bow lights working. Handheld anemometer: note its height above the water.
  - Do NOT open SEALED-KEY.json. Give it to the scorer (or leave it on the computer).

ON THE WATER (in OBSERVER-SHEET.csv order)
  1. Navigate with the Apple Maps link. The form shows the nearest bank and its distance; > 300 m warns.
  2. Look at the water 5–30 m off the bank. Choose the class FIRST, then texture (required), shelter seen.
  3. Photo, then optional handheld wind with its height. Save. Only then does the Candidate show.
  4. Visit X and Y of the same pair within 60 minutes of each other. Pair ID goes in the form.
  {'5. Tag EVERY record "practice". Practice records never count.' if practice else '5. Do not tag these practice. If you saw a prediction before choosing, say so in the form (unblinded is kept, flagged).'}

AFTER
  - Export from the form (share sheet) into: Sector Handoffs/Wind/field/raw/{night}-<observer>/
  - Do not edit records after export. Re-evaluation (wind-eval) and QA run from the raw export.

SAFETY: Planned only below 9 m/s (about 20 mph). If it is rougher than you are comfortable in, skip the bank and
note "skipped: conditions". A skipped bank is better than a bad night.
"""
    open(os.path.join(folder, "SESSION-README.txt"), "w").write(readme)
    return {"folder": folder, "pairs": len(route), "banks": len(sheet), "minutes": minutes, "lakeWindMS": round(u_l, 2),
            "dirFromDeg": round(d_l), "leadHours": lead, "status": tag}


def main(argv=None):
    from .store import open_store
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["opportunities", "packet"])
    ap.add_argument("--store", required=True)
    ap.add_argument("--predictions", action="append")
    ap.add_argument("--nights", type=int, default=2)
    ap.add_argument("--lake"); ap.add_argument("--night"); ap.add_argument("--block", default=None)
    ap.add_argument("--pairs", type=int, default=6); ap.add_argument("--practice", action="store_true")
    ap.add_argument("--json", default=None); ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args(argv)
    store = open_store(a.store)
    if a.cmd == "opportunities":
        r = opportunities(store, a.predictions, a.nights)
        print(f"FIELD OPPORTUNITIES (records so far: {r['coverage']['n']}; ranked by validation information value, not wind)")
        for w in r["windows"][:a.top]:
            print(f"  {w['value']:5.2f}  {w['lake']:<12} night of {w['nightOf']}  {w['blockUTC'][11:16]}-{w['blockUTC'][-9:-4]} UTC  "
                  f"{w['medianWindMph']:4.1f} mph {('from %3d°' % w['dirFromDeg']) if w['medianWindMS'] >= 1 else '(calm) '} (+{w['leadHours']} h)  bin {w['windBin']:<6} pairs {w['informativePairs']:3d}")
            print(f"         {w['why']}")
    else:
        r = packet(store, a.lake, a.night, a.block, a.pairs, a.practice)
        print(json.dumps(r, indent=1))
    if a.json:
        json.dump(r, open(a.json, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
