"""Stage 20 PREREGISTRATION section 6 (held-out) + root-cause decomposition (sections 4-5 of the stage brief).
Requires the frozen selection (harm20.json hash in FREEZE_STAGE20.json). For every held-out stratum H1 (tandem, E vs A),
H2 (2025 N0511), H3 (2026 N0512), H4 (Stage 19 S2C neighbours) and for every correction (C0, B Stage 12, C1, C2, C3):
reflectance, feature, visibility, state, posterior and harm-proxy differences; the authority-lift bar on the selected
correction. Root cause on ALL tandem pairs (descriptive): TOA (rhot), surface (rhos) and L2W band ratios for S2C as
distributed (C) and re-calibrated to nominal (E), against the band-response expectation; NIR/SWIR dark offsets.
Writes eval20.json. No Secchi value is read."""
import json, os, sys, math, hashlib, collections
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage20")
import lib20 as L20
F = json.load(open(f"{S}/stage20/FREEZE_STAGE20.json"))
for k, p in (("prereg_sha256", "PREREGISTRATION_STAGE20.md"), ("srf20_sha256", "srf20.json"), ("harm20_sha256", "harm20.json")):
    assert hashlib.sha256(open(f"{S}/stage20/{p}", "rb").read()).hexdigest() == F[k], p
H = json.load(open(f"{S}/stage20/harm20.json")); SEL = H["selected"]; floor = H["floor"]
PAIRS = json.load(open(f"{S}/stage20/pairs20.json"))
CORR = {"C0": L20.c_none, "B_stage12": L20.c_stage12, "C1": L20.c_sbaf, "C2": L20.c_param(H["C2"]), "C3": L20.c_param(H["C3"])}
sc = lambda s, corr=None: L20.scene(s["m0"], s["m3"], s["sza"], corr) if s else None


def pairs_of(rows, ckey, corr):
    out = []
    for x in rows:
        c, r = sc(x.get(ckey), corr), sc(x.get("ref"))
        if c and r: out.append({"c": c, "r": r, "x": x})
    return out


STRATA = {"H1": ("e", True), "H2": ("c", False), "H3": ("c", False), "H4": ("c", False)}
out = {"selected": SEL, "floor": floor, "strata": {}, "pooled": {}}
for st, (ck, tandem) in STRATA.items():
    rows = [x for x in PAIRS if x.get("split") == st]
    out["strata"][st] = {n: L20.pair_metrics(pairs_of(rows, ck, f), floor=floor, tandem=tandem) for n, f in CORR.items()}
    if st == "H1":
        out["strata"]["H1"]["C_as_distributed_C0"] = L20.pair_metrics(pairs_of(rows, "c", None), tandem=True)
        out["strata"]["H1"]["C_as_distributed_B"] = L20.pair_metrics(pairs_of(rows, "c", L20.c_stage12), tandem=True)
        out["strata"]["H1_geo"] = {g: {n: L20.pair_metrics(pairs_of([x for x in rows if x["geo"] == g], "e", f), tandem=True) for n, f in CORR.items()} for g in ("US", "global")}
for n, f in CORR.items():
    allp = [p for st, (ck, t) in STRATA.items() for p in pairs_of([x for x in PAIRS if x.get("split") == st], ck, f)]
    d = [p["c"]["p"] - p["r"]["p"] for p in allp]
    out["pooled"][n] = {"n": len(d), "dp_median": float(np.median(d)) if d else None, "dp_mean": float(np.mean(d)) if d else None}
gating = [st for st in STRATA if out["strata"][st][SEL].get("gating")]
lift = ("H1" in gating and len(gating) >= 2 and all(out["strata"][st][SEL]["bars"]["all"] for st in gating) and abs(out["pooled"][SEL]["dp_median"]) <= 0.03)
out["lift"] = {"gating_strata": gating, "per_stratum": {st: out["strata"][st][SEL].get("bars") for st in STRATA}, "pooled_dp": out["pooled"][SEL]["dp_median"],
               "preferred_pooled_le_0.02": abs(out["pooled"][SEL]["dp_median"]) <= 0.02, "PASSED": bool(lift)}
# ---- root cause (all tandem pairs, descriptive)
B = [x for x in PAIRS if x["set"] == "B" and x.get("ref") and x.get("c") and x.get("e")]
srf = json.load(open(f"{S}/stage20/srf20.json"))["S2C_mtd_vs_S2A_mtd"]["band_ratio_pctl"]
def lev(x, k, level, b):
    d = (x[k].get("diag") or {}); v = (d.get(level) or {}).get(b) if level != "L2W" else ((x[k].get("m0") or {}).get(b) if (x[k].get("m0") or {}).get("n", 0) >= 5 else None)
    return v if isinstance(v, (int, float)) and math.isfinite(v) else None
rc = {}
for level in ("rhot", "rhos", "L2W"):
    rc[level] = {}
    for b in ("B01", "B02", "B03", "B04", "B05", "B06", "B07", "B8A", "B11", "B12"):
        for k in ("c", "e"):
            v = [(lev(x, k, level, b), lev(x, "ref", level, b)) for x in B]; v = [(c, a) for c, a in v if c is not None and a is not None]
            lr = [math.log10(c / a) for c, a in v if c > 0.001 and a > 0.001]
            rc[level][f"{b}_{k}"] = {"n": len(v), "log_ratio_median": float(np.median(lr)) if lr else None, "ratio_median": 10 ** float(np.median(lr)) if lr else None,
                                     "diff_median": float(np.median([c - a for c, a in v])) if v else None}
out["root_cause"] = {"levels": rc, "srf_expected_boa_ratio_median": {b: srf[b][2] for b in srf}}
# magnitude dependence of the L2W (E vs A) red/B05 ratio, and by baseline (N9905 vs N9906)
def mag(rows, k):
    v = [(lev(x, k, "L2W", "B04"), lev(x, "ref", "L2W", "B04"), lev(x, k, "L2W", "B05"), lev(x, "ref", "L2W", "B05")) for x in rows]
    v = [t for t in v if None not in t and min(t) > 0.001]
    if len(v) < 6: return {"n": len(v)}
    v.sort(key=lambda t: t[1]); th = len(v) // 3
    return {"n": len(v), **{nm: {"B04": float(np.median([math.log10(t[0] / t[1]) for t in g])), "B05": float(np.median([math.log10(t[2] / t[3]) for t in g])), "red_max": g[-1][1]}
                            for nm, g in (("dark", v[:th]), ("mid", v[th:2 * th]), ("bright", v[2 * th:]))}}
out["root_cause"]["magnitude_E"] = mag(B, "e"); out["root_cause"]["magnitude_C"] = mag(B, "c")
out["root_cause"]["by_baseline"] = {bl: {lvl: {b: (lambda lr: float(np.median(lr)) if lr else None)([math.log10(lev(x, "c", lvl, b) / lev(x, "ref", lvl, b)) for x in B if x["c"]["baseline"] == bl and lev(x, "c", lvl, b) and lev(x, "ref", lvl, b) and lev(x, "c", lvl, b) > 0.001 and lev(x, "ref", lvl, b) > 0.001])
                                              for b in ("B02", "B04", "B05")} for lvl in ("rhot", "L2W")} for bl in sorted({x["c"]["baseline"] for x in B})}
# geometry dependence of the E vs A visibility difference (all tandem pairs, selected correction)
allB = pairs_of(B, "e", CORR[SEL])
out["root_cause"]["dp_by_sun"] = {k: (lambda d: {"n": len(d), "median": float(np.median(d)) if d else None})([p["c"]["p"] - p["r"]["p"] for p in allB if fn(90 - p["x"]["e"]["sza"])])
                                   for k, fn in (("sun<20", lambda s: s < 20), ("sun 20-35", lambda s: 20 <= s < 35), ("sun>=35", lambda s: s >= 35))}
# C-gbm response decomposition: which feature carries the difference (E raw vs A, all tandem pairs)
raw = pairs_of(B, "e", None)
out["root_cause"]["feature_diff_E_raw_all"] = {f: float(np.median([p["c"]["F"][f] - p["r"]["F"][f] for p in raw if math.isfinite(p["c"]["F"][f]) and math.isfinite(p["r"]["F"][f])])) for f in L20.FEATS} if raw else None
json.dump(out, open(f"{S}/stage20/eval20.json", "w"), indent=1, default=str)
for st in STRATA:
    for n in CORR:
        m = out["strata"][st][n]
        if m.get("n"): print(st, n, "n", m["n"], "dp", round(m["dp_median"], 4), "ov", m["state_overlap"] and round(m["state_overlap"], 3), "jump", round(m["jump_rate"], 3),
                             {b: (v["median"] and round(v["median"], 4)) for b, v in m["band_log_ratio"].items()}, "bars", m["bars"]["all"], m["bars"])
print("pooled", out["pooled"]); print("LIFT", out["lift"])
for lvl in ("rhot", "rhos", "L2W"): print(lvl, {k: round(v["ratio_median"], 4) for k, v in rc[lvl].items() if v["ratio_median"]})
print("baseline", out["root_cause"]["by_baseline"]); print("magnitude E", out["root_cause"]["magnitude_E"]); print("magnitude C", out["root_cause"]["magnitude_C"])
