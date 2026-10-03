"""Stage 20 EXPLORATORY (not pre-registered; no verdict uses it): S2C re-calibrated to nominal AND with the additive
top-of-atmosphere B8A/B11/B12 water offset removed before ACOLITE (offsets from derivation pairs D1 only), against S2A,
reported separately on D1 and H1; with and without the physics band adjustment (C1) on top. Writes explore20.json."""
import json, os, sys, math
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage20")
import lib20 as L20
P = [x for x in json.load(open(f"{S}/stage20/pairs20.json")) if x["set"] == "B" and x.get("ref") and x.get("e")]
def samp(resfile, key):
    if not os.path.exists(resfile): return None
    r = json.load(open(resfile))
    for c in r.get("crops", []):
        p = (c.get("points") or {}).get(key); d = (c.get("diag") or {}).get(key)
        if p is not None: return {"m0": p.get("M0"), "m3": p.get("M3"), "sza": (d or {}).get("sza"), "diag": d}
    return None
for x in P:
    key = next(k for k in [f"{x['site']}|{a}|{c}" for a, c in [(None, None)]] if False) if False else None
    lc = x["e"]["l1c"]; r = f"{S}/stage20/res_x20/X_{lc}.json"
    if os.path.exists(r):
        js = json.load(open(r))
        for c in js["crops"]:
            for k in (c.get("points") or {}):
                if k.split("|S2A_")[0] == x["site"]: x["x"] = samp(r, k)
out = {}
for sp in ("D1", "H1", "all"):
    rows = [x for x in P if (sp == "all" or x["split"] == sp) and x.get("x")]
    out[sp] = {}
    for name, ck, corr in (("E_C0", "e", None), ("E_C2", "e", L20.c_param(json.load(open(f"{S}/stage20/harm20.json"))["C2"])), ("X_C0", "x", None), ("X_C1", "x", L20.c_sbaf), ("E_B", "e", L20.c_stage12)):
        pr = []
        for x in rows:
            c, r_ = (L20.scene(x[ck]["m0"], x[ck]["m3"], x[ck]["sza"], corr) if x.get(ck) else None), L20.scene(x["ref"]["m0"], x["ref"]["m3"], x["ref"]["sza"])
            if c and r_: pr.append({"c": c, "r": r_})
        m = L20.pair_metrics(pr, tandem=True)
        out[sp][name] = {k: m.get(k) for k in ("n", "dp_median", "dp_iqr", "state_overlap", "jump_rate")} | {"bands": {b: v["median"] for b, v in (m.get("band_log_ratio") or {}).items()}, "bars": m.get("bars")}
json.dump(out, open(f"{S}/stage20/explore20.json", "w"), indent=1, default=str)
for sp, v in out.items():
    for n, m in v.items(): print(sp, n, "n", m["n"], "dp", m["dp_median"] and round(m["dp_median"], 4), "ov", m["state_overlap"] and round(m["state_overlap"], 3), "jump", m["jump_rate"] and round(m["jump_rate"], 3), {b: (q and round(10 ** q, 3)) for b, q in m["bands"].items()})
