"""Bowfishing Wind Engine build: 32-scenario bank matrix (atlases), scenario summaries, ranking examples, QA.

  python research/bowfishing_build.py atlas      # all banks x {5,10,15,20 mph} x 8 directions, 4 lakes -> WIND_ATLAS_<LAKE>.json.gz
  python research/bowfishing_build.py qa         # speed monotonicity, fetch sanity, direction-flip ordering
  python research/bowfishing_build.py examples   # lake progressions + Guntersville worked example

Static matrix assumption (frozen in BWIS v1): steady wind for 6 h, identical history for every bank, research surface
model = frozen M0 (M4 failed its promotion rule), so memory contribution = 0. Wind only."""
import gzip, json, os, random, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
import numpy as np
from sector_wind import bowfishing as BF

OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/bowfishing")
PAIRS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/score-acceleration/network_pairs.json")


def atlas():
    os.makedirs(OUT, exist_ok=True); summary = {}
    for lake in BF.LAKES:
        L = BF.load_lake(lake); recs = []; summ = {}
        for dname, deg in BF.DIRS8.items():
            pct = BF.lake_percentiles(L, deg)
            for mph in BF.SPEEDS_MPH:
                u = mph * BF.MPH; ranks = Counter(); surf = Counter(); fetches = []
                for i, b in enumerate(L["banks"]):
                    r = BF.evaluate_bank(L, i, u, deg)
                    if r["exposureRank"] != "UNKNOWN":
                        r["relativeLakePercentile"] = pct[i]; fetches.append(r["effectiveFetchM"]); surf[r["predictedSurfaceLabel"]] += 1
                    ranks[r["exposureRank"]] += 1
                    recs.append({"bankId": b["id"], "windFrom": dname, "windFromDeg": deg, "speedMph": mph,
                                 **{k: r.get(k) for k in ("effectiveFetchM", "directFetchM", "effectiveFetchRays", "predictedHm0M", "predictedSurfaceClass",
                                                          "predictedSurfaceLabel", "predictedTextureClass", "exposureRank", "relativeLakePercentile", "confidence", "reason")},
                                 "geometryFlags": {"belowResolution": bool(b.get("belowResolution")), "region": b.get("region")}})
                n = sum(ranks.values())
                summ[f"{mph}mph|{dname}"] = {"banks": n, "exposurePct": {k: round(100 * ranks[k] / n, 1) for k in list(BF.RANK.values()) + ["UNKNOWN"]},
                                             "surfacePct": {k: round(100 * surf[k] / max(sum(surf.values()), 1), 1) for k in BF.CHOP.values()},
                                             "medianFetchM": round(float(np.median(fetches))), "p90FetchM": round(float(np.percentile(fetches, 90)))}
        meta = {"lake": lake, "banks": len(L["banks"]), "scenarios": 32, "records": len(recs), "tableSha256": L["tableSha256"], "assetSha256": L["assetSha256"],
                "assumption": "steady 6 h wind, identical history, frozen CEM (M0), frozen P map; internal research artifact",
                "candidate": "wind-candidate-2026.10.stage2-baseline"}
        with gzip.open(os.path.join(OUT, f"WIND_ATLAS_{lake.upper()}.json.gz"), "wt") as f:
            json.dump({"meta": meta, "scenarioSummary": summ, "records": recs}, f)
        summary[lake] = {"meta": meta, "scenarioSummary": summ}
        print(lake, meta["banks"], "banks", meta["records"], "records", flush=True)
    json.dump(summary, open(os.path.join(OUT, "atlas_summary.json"), "w"), indent=1)


def qa():
    res = {}
    mono_fail = 0; mono_n = 0; fetch_flags = 0; fetch_n = 0
    for lake in BF.LAKES:
        L = BF.load_lake(lake)
        ok = [i for i, b in enumerate(L["banks"]) if not b.get("belowResolution")]
        for deg in BF.DIRS8.values():
            for i in ok:
                prev = None
                for mph in BF.SPEEDS_MPH:
                    r = BF.evaluate_bank(L, i, mph * BF.MPH, deg); mono_n += 1
                    if prev and (r["predictedSurfaceClass"] < prev[0] or r["predictedHm0M"] < prev[1] - 1e-9):
                        mono_fail += 1
                    prev = (r["predictedSurfaceClass"], r["predictedHm0M"])
            # fetch sanity: sample pairs; >=3x longer fetch must not be calmer at 15 mph
            rnd = random.Random(7 + deg)
            for _ in range(2000):
                a, b = rnd.sample(ok, 2)
                ra, rb = BF.evaluate_bank(L, a, 15 * BF.MPH, deg), BF.evaluate_bank(L, b, 15 * BF.MPH, deg)
                lo, hi = (ra, rb) if ra["effectiveFetchM"] < rb["effectiveFetchM"] else (rb, ra)
                if hi["effectiveFetchM"] >= 3 * lo["effectiveFetchM"]:
                    fetch_n += 1; fetch_flags += hi["predictedSurfaceClass"] < lo["predictedSurfaceClass"]
    res["speedMonotonicity"] = {"checks": mono_n, "violations": mono_fail}
    res["fetchSanity"] = {"pairsChecked": fetch_n, "flags": fetch_flags}
    # direction flips: network pairs (canonical) + seeded random pairs with >=20% Hm0 contrast in both of a reversed direction pair
    net = json.load(open(PAIRS)); flip = {"canonical": [0, 0], "random": [0, 0]}; detail = []
    for lake in BF.LAKES:
        L = BF.load_lake(lake); idx = {b["id"]: i for i, b in enumerate(L["banks"])}
        cands = [(c["a"], c["b"]) for c in net[lake]["top"]]
        ok = [i for i, b in enumerate(L["banks"]) if not b.get("belowResolution")]
        rnd = random.Random(11); extra = []
        while len(extra) < 200:
            a, b = rnd.sample(ok, 2)
            if BF.km(L["banks"][a]["anchor"], L["banks"][b]["anchor"]) > 3000:
                continue
            extra.append((L["banks"][a]["id"], L["banks"][b]["id"]))
        for kind, pairs in (("canonical", cands), ("random", extra)):
            for a, b in pairs:
                for d1 in (0, 45, 90, 135):
                    for mph in BF.SPEEDS_MPH:
                        for deg in (d1, d1 + 180):
                            ra, rb = BF.evaluate_bank(L, idx[a], mph * BF.MPH, deg), BF.evaluate_bank(L, idx[b], mph * BF.MPH, deg)
                            ha, hb = ra["predictedHm0M"], rb["predictedHm0M"]
                            if max(ha, hb) <= 0 or abs(ha - hb) / max(ha, hb) < 0.2:
                                continue
                            exposed, protected = (ra, rb) if ha > hb else (rb, ra)
                            ranked_ok = (protected["predictedSurfaceClass"], protected["predictedHm0M"], protected["effectiveFetchM"]) < \
                                        (exposed["predictedSurfaceClass"], exposed["predictedHm0M"], exposed["effectiveFetchM"])
                            # physical protection = shorter effective fetch for this wind
                            phys_ok = protected["effectiveFetchM"] < exposed["effectiveFetchM"]
                            flip[kind][0] += 1; flip[kind][1] += ranked_ok and phys_ok
                        if kind == "canonical" and mph == 15:
                            e1 = BF.evaluate_bank(L, idx[a], mph * BF.MPH, d1)["predictedHm0M"] > BF.evaluate_bank(L, idx[b], mph * BF.MPH, d1)["predictedHm0M"]
                            e2 = BF.evaluate_bank(L, idx[a], mph * BF.MPH, d1 + 180)["predictedHm0M"] > BF.evaluate_bank(L, idx[b], mph * BF.MPH, d1 + 180)["predictedHm0M"]
                            detail.append({"lake": lake, "a": a, "b": b, "dir": d1, "aExposed": e1, "aExposedReversed": e2, "flips": e1 != e2})
    res["directionOrdering"] = {k: {"comparisons": v[0], "passRate": round(v[1] / v[0], 4) if v[0] else None} for k, v in flip.items()}
    res["canonicalFlips"] = {"pairDirections": len(detail), "flipped": sum(d["flips"] for d in detail), "detail": detail}
    json.dump(res, open(os.path.join(OUT, "qa.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "canonicalFlips"}, indent=1), res["canonicalFlips"]["flipped"], "/", res["canonicalFlips"]["pairDirections"])


def sector_of(L, ids):
    """Coarse geography label for a set of banks: region names (frozen asset field) by count."""
    c = Counter(L["banks"][i].get("region") or "unnamed shore" for i in ids)
    return [f"{k} ({v})" for k, v in c.most_common(4)]


def examples():
    out = {}
    for lake in BF.LAKES:
        L = BF.load_lake(lake); idx = {b["id"]: i for i, b in enumerate(L["banks"])}; lk = {}
        for dname in ("SW", "N"):
            deg = BF.DIRS8[dname]
            for mph in BF.SPEEDS_MPH:
                R = BF.rank_banks_for_wind(L, mph * BF.MPH, deg, top=3)
                allr = R["all"]; cnt = Counter(r["predictedSurfaceLabel"] for r in allr)
                worst = [r for r in allr if r["exposureRank"] in ("HIGH_EXPOSURE", "EXTREME_EXPOSURE")]
                prot = [r for r in allr if r["predictedSurfaceClass"] <= 2]
                hi_ids = [idx[r["bankId"]] for r in sorted(allr, key=lambda r: -r["predictedHm0M"])[:max(1, len(allr) // 10)]]
                lo_ids = [idx[r["bankId"]] for r in allr[:max(1, len(allr) // 10)]]
                e = {"banks": len(allr), "surfacePct": {k: round(100 * cnt[k] / len(allr), 1) for k in BF.CHOP.values()},
                     "protectedOrRipplePct": round(100 * len(prot) / len(allr), 1), "highOrExtremePct": round(100 * len(worst) / len(allr), 1),
                     "mostAffectedSectors(top10% Hm0)": sector_of(L, hi_ids), "mostProtectedSectors(bottom10%)": sector_of(L, lo_ids),
                     "worst": [{k: r[k] for k in ("bankId", "anchor", "effectiveFetchM", "predictedHm0In", "predictedSurfaceLabel", "exposureRank", "confidence", "reason", "relativeLakePercentile")} for r in R["worst"]],
                     "best": [{k: r[k] for k in ("bankId", "anchor", "effectiveFetchM", "predictedHm0In", "predictedSurfaceLabel", "exposureRank", "confidence", "reason", "relativeLakePercentile")} for r in R["best"]]}
                if worst:
                    w = R["worst"][0]
                    e["worstAlternatives"] = BF.nearby_alternatives(L, allr, w)
                lk[f"{dname}|{mph}"] = e
        out[lake] = lk
        print(lake, "done", flush=True)
    json.dump(out, open(os.path.join(OUT, "examples.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    {"atlas": atlas, "qa": qa, "examples": examples}[sys.argv[1]]()
