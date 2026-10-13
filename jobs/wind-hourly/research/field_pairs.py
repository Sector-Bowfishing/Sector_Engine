"""Select candidate bank pairs for the field pack from geometry only (no forecasts, no H2).
  A. MIRROR pairs: shores at opposite ends of one open-water run. Wind FROM theta: A (downwind shore) long fetch, B (upwind shore) land at its back;
     reverse the wind and the roles swap -> one pair tests the model in BOTH directions with the same two banks.
  B. COVE-vs-POINT pairs: <= 1.5 km apart, A exposed to theta, B a true cove (short fetch from most directions): the 'is this cove sheltered?' question.
  python research/field_pairs.py OUT.json"""
import base64, gzip, glob, json, math, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind import bowfishing as BF
from sector_wind.brain import estimate as ES
from sector_wind.brain import exposure as EX
from sector_wind.brain import fleet as FL
from sector_wind.brain.state import decode_fetch_table
from matched_bank_validation import audited_tables, ENGINE, load_poly

REGISTRY = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/wind-brain/registry/")
AXES = {"SW-NE": 225, "S-N": 180, "W-E": 270, "NW-SE": 315}
LAKES = [("Guntersville|AL", "pilot"), ("Wheeler|AL", "pilot"), ("Wilson|AL", "pilot"), ("Pickwick Lake|TN", "pilot"), ("Lake Hartwell|SC", "pilot (ESTIMATED geometry)"),
         ("Mille Lacs Lake|MN", "open natural lake"), ("Lake McConaughy|NE", "plains reservoir"), ("Toledo Bend Reservoir|TX", "large southern reservoir (ESTIMATED geometry)"),
         ("Lake Maurepas|LA", "shallow coastal lake")]


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 6371000 * 2 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


def dest(p, brg, d):
    la, lo = math.radians(p[0]), math.radians(p[1]); b = math.radians(brg); r = d / 6371000
    la2 = math.asin(math.sin(la) * math.cos(r) + math.cos(la) * math.sin(r) * math.cos(b))
    lo2 = lo + math.atan2(math.sin(b) * math.sin(r) * math.cos(la), math.cos(r) - math.sin(la) * math.sin(la2))
    return (math.degrees(la2), math.degrees(lo2))


def describe(banks, T, i, theta, tier, mph):
    eff = BF.nine_ray(T[i], theta); u = mph * 0.44704
    c = BF.chop_class(BF.cem(u, eff, 6 * 3600)); fac = EX.facing_deg(banks[i])
    if tier == "AUDITED":
        lab = EX.label_bank(theta, mph, fac, c)
    else:
        lab = EX.label_bank_estimated(theta, mph, fac, c, BF.chop_class(BF.cem(u, eff * EX.ESTIMATED_FETCH_MARGIN, 6 * 3600)))
    return {"bankId": banks[i]["id"], "anchor": banks[i]["anchor"], "standoff": banks[i]["standoff"], "facingDeg": None if fac is None else round(fac),
            "effectiveFetchM": round(eff), "predictedHm0In": round(BF.cem(u, eff, 6 * 3600) / 0.0254, 1), "label": lab["label"], "highFetch": lab["highFetch"], "reason": lab["reason"]}


def pick(lake_id, kind):
    man = FL.tier_for(lake_id); tier = man["tier"]
    if tier == "AUDITED":
        A = audited_tables()[lake_id]; banks, T = A["banks"], A["table"]
    else:
        # ESTIMATED lakes: the published Lake Registry v1 analysis polygon (current geometry asset; the older engine polygons put banks >300 m from the registry shoreline)
        reg = {l["lakeId"]: l for l in json.load(open(REGISTRY + "lakes.v1.json"))["lakes"]}[lake_id]
        j = json.load(open(REGISTRY + "geom/" + reg["lakeKey"] + ".geojson"))
        g = j["features"][0]["geometry"] if j.get("type") == "FeatureCollection" else (j["geometry"] if j.get("type") == "Feature" else j)
        from shapely.geometry import shape
        obj = ES.build_estimated_table(ES.clean_geometry(shape(g)), lake_id); banks, T = decode_fetch_table(obj)
    idx = [i for i, b in enumerate(banks) if not b.get("belowResolution") and EX.facing_deg(b) is not None]
    mx = float(np.percentile([BF.nine_ray(T[i], t) for i in idx[::max(1, len(idx) // 400)] for t in (225, 180, 270, 315, 45, 0, 90, 135)], 95))
    hi = max(1200.0, min(3000.0, 0.5 * mx)); lo = 300.0
    out = []
    for ax, th in AXES.items():
        rev = (th + 180) % 360
        F = {i: (BF.nine_ray(T[i], th), BF.nine_ray(T[i], rev)) for i in idx}
        A = [i for i in idx if F[i][0] >= hi and F[i][1] <= lo]
        Bc = [i for i in idx if F[i][0] <= lo and F[i][1] >= hi]
        cands = []
        for a in A[::max(1, len(A) // 300)]:
            target = dest(banks[a]["anchor"], th, F[a][0])
            best = min(Bc, key=lambda b: hav(banks[b]["anchor"], target), default=None)
            if best is None:
                continue
            if hav(banks[best]["anchor"], target) > 0.3 * F[a][0] + 400:
                continue
            dist = hav(banks[a]["anchor"], banks[best]["anchor"])
            if dist > 12000:
                continue                                    # one boat run: keep pairs within 12 km
            direct = EX.angdiff(th, EX.facing_deg(banks[a])) <= EX.DIRECT_MAX_DEG
            cands.append((direct, min(F[a][0], F[best][1]), a, best))
        cands.sort(reverse=True)
        used = []
        for _dir, sc, a, b in cands:
            if all(hav(banks[a]["anchor"], banks[u[0]]["anchor"]) > 1500 for u in used):
                used.append((a, b, sc))
            if len(used) >= 2:
                break
        for a, b, sc in used:
            out.append({"type": "MIRROR", "axis": ax, "windFromDeg_forAasExposed": th, "windFromDeg_reversed": rev, "distanceM": round(hav(banks[a]["anchor"], banks[b]["anchor"])),
                        "A": {k: describe(banks, T, a, th, tier, 12) for k in ("at12",)} | {"at15": describe(banks, T, a, th, tier, 15), "reverse12": describe(banks, T, a, rev, tier, 12)},
                        "B": {k: describe(banks, T, b, th, tier, 12) for k in ("at12",)} | {"at15": describe(banks, T, b, th, tier, 15), "reverse12": describe(banks, T, b, rev, tier, 12)}})
    # SUBTLE: both exposed, predicted wave height (12 mph) differs by 1.25-2.5x within 3 km (tests ordering, not just land-vs-water)
    th = 225
    ex = [i for i in idx if 400 <= BF.nine_ray(T[i], th) <= 6000]
    hm = lambda f: BF.cem(12 * 0.44704, f, 6 * 3600) / 0.0254
    sub, seen = [], []
    for a in ex[::max(1, len(ex) // 250)]:
        for b in ex[::max(1, len(ex) // 250)]:
            d = hav(banks[a]["anchor"], banks[b]["anchor"]); fa, fb = BF.nine_ray(T[a], th), BF.nine_ray(T[b], th)
            if 800 <= d <= 3000 and 1.25 <= hm(fa) / hm(fb) <= 2.5 and hm(fb) >= 2.0 and EX.angdiff(th, EX.facing_deg(banks[a])) <= 45 and EX.angdiff(th, EX.facing_deg(banks[b])) <= 45:
                sub.append((min(fa, fb), a, b, d))
    sub.sort(reverse=True)
    for sc, a, b, d in sub[:1]:
        out.append({"type": "SUBTLE_ORDERING", "axis": "SW-NE", "windFromDeg_forAasExposed": th, "windFromDeg_reversed": None, "distanceM": round(d),
                    "A": {"at12": describe(banks, T, a, th, tier, 12), "at15": describe(banks, T, a, th, tier, 15)},
                    "B": {"at12": describe(banks, T, b, th, tier, 12), "at15": describe(banks, T, b, th, tier, 15)}})
    # cove vs point
    def cove(i):
        v = [BF.nine_ray(T[i], d) for d in range(0, 360, 45)]
        return sum(x <= 400 for x in v) >= 7
    coves = [i for i in idx if cove(i)]
    for ax, th in list(AXES.items())[:2]:
        pts = [i for i in idx if BF.nine_ray(T[i], th) >= hi]
        best = None
        for a in pts[::max(1, len(pts) // 250)]:
            for b in coves[::max(1, len(coves) // 400)]:
                d = hav(banks[a]["anchor"], banks[b]["anchor"])
                if 300 <= d <= 1500:
                    sc = BF.nine_ray(T[a], th) / max(BF.nine_ray(T[b], th), 30)
                    if best is None or sc > best[0]:
                        best = (sc, a, b, d)
        if best:
            sc, a, b, d = best
            out.append({"type": "COVE_vs_POINT", "axis": ax, "windFromDeg_forAasExposed": th, "windFromDeg_reversed": None, "distanceM": round(d),
                        "A": {"at12": describe(banks, T, a, th, tier, 12), "at15": describe(banks, T, a, th, tier, 15)},
                        "B": {"at12": describe(banks, T, b, th, tier, 12), "at15": describe(banks, T, b, th, tier, 15)}})
    return {"lake": lake_id, "kind": kind, "tier": tier, "geometryConfidence": man["geometryConfidence"], "banksUsable": len(idx), "hiFetchThresholdM": hi, "pairs": out}


if __name__ == "__main__":
    res = []
    for lid, kind in LAKES:
        try:
            r = pick(lid, kind)
        except Exception as e:
            r = {"lake": lid, "kind": kind, "error": repr(e)[:200], "pairs": []}
        res.append(r); print(lid, r.get("tier"), len(r["pairs"]), r.get("error", ""), flush=True)
    json.dump(res, open(sys.argv[1], "w"), indent=1)
