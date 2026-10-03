"""Stage 20 PREREGISTRATION section 5: fit C2/C3 on the DERIVATION tandem pairs (D1, E vs A) and select the simplest
candidate meeting every authority-lift bar on D1 (tandem thresholds) and D2 (operational thresholds, Stage 19 floor).
Reads derivation rows only (plus the FLOOR pairs). Writes harm20.json (all candidates + the selection) and freezes it in
FREEZE_STAGE20.json. No Secchi value is read."""
import json, os, sys, math, hashlib, datetime
import numpy as np
from scipy.stats import theilslopes
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage20")
import lib20 as L20
F = json.load(open(f"{S}/stage20/FREEZE_STAGE20.json"))
assert hashlib.sha256(open(f"{S}/stage20/PREREGISTRATION_STAGE20.md", "rb").read()).hexdigest() == F["prereg_sha256"]
assert hashlib.sha256(open(f"{S}/stage20/srf20.json", "rb").read()).hexdigest() == F["srf20_sha256"]
PAIRS = json.load(open(f"{S}/stage20/pairs20.json"))
D1 = [x for x in PAIRS if x.get("split") == "D1"]; D2 = [x for x in PAIRS if x.get("split") == "D2"]; FL = [x for x in PAIRS if x.get("split") == "FLOOR"]
FB = ("B01", "B02", "B03", "B04", "B05", "B06")


def sc(s, corr=None): return L20.scene(s["m0"], s["m3"], s["sza"], corr) if s else None


def pairs_of(rows, ckey, corr):
    out = []
    for x in rows:
        c, r = sc(x.get(ckey), corr), sc(x.get("ref"))
        if c and r: out.append({"c": c, "r": r, "x": x})
    return out


# ---- floor (S2B vs S2A, no correction)
floor = L20.pair_metrics(pairs_of(FL, "c", None), tandem=True)
floor = {"n": floor["n"], "state_overlap": floor["state_overlap"], "jump_rate": floor["jump_rate"], "dp_median": floor["dp_median"]}
# ---- fit C2 / C3 on D1 (E vs A), engine-picked band dicts
raw = pairs_of(D1, "e", None)
C2, C3 = {}, {}
for b in FB:
    v = [(x["c"]["a"][b], x["r"]["a"][b]) for x in raw if (x["c"]["a"].get(b) or 0) > 0.001 and (x["r"]["a"].get(b) or 0) > 0.001]
    if len(v) < 5: continue
    C2[b] = {"g": float(10 ** (-np.median([math.log10(c / r) for c, r in v])))}
    e, a = np.array([c for c, r in v]), np.array([r for c, r in v]); sl, ic, _, _ = theilslopes(a, e); C3[b] = {"g": float(sl), "o": float(ic)}
    if b == "B05":
        d = np.array([x["c"]["a"]["B06"] - x["c"]["a"]["B04"] for x in raw if (x["c"]["a"].get(b) or 0) > 0.001 and (x["r"]["a"].get(b) or 0) > 0.001])
        res = a - (sl * e + ic); C3[b]["k"] = float(np.dot(d, res) / np.dot(d, d)) if np.dot(d, d) > 0 else 0.0
CANDS = [("C0", L20.c_none), ("C1", L20.c_sbaf), ("C2", L20.c_param(C2)), ("C3", L20.c_param(C3))]
rep = {"floor": floor, "n_D1_raw_pairs": len(raw), "C2": C2, "C3": C3, "derivation": {}}
sel = None
for name, f in CANDS + [("B_stage12", L20.c_stage12)]:
    m1 = L20.pair_metrics(pairs_of(D1, "e", f), tandem=True); m2 = L20.pair_metrics(pairs_of(D2, "c", f), floor=floor, tandem=False)
    ok = m1.get("bars", {}).get("all", False) and m2.get("bars", {}).get("all", False)
    rep["derivation"][name] = {"D1": m1, "D2": m2, "meets_all": ok}
    if sel is None and ok and name != "B_stage12": sel = name
if sel is None:
    pooled = {n: abs(float(np.median([x["c"]["p"] - x["r"]["p"] for x in pairs_of(D1, "e", f) + pairs_of(D2, "c", f)]))) for n, f in CANDS}
    sel = min(pooled, key=pooled.get); rep["fallback_pooled_abs_dp"] = pooled; rep["selection_rule"] = "fallback: smallest pooled derivation |median dp| (no candidate met every bar)"
else:
    rep["selection_rule"] = "simplest candidate meeting every bar on D1 and D2"
rep["selected"] = sel
rep["selected_params"] = {"C0": {}, "C1": L20.SB, "C2": C2, "C3": C3}[sel]
json.dump(rep, open(f"{S}/stage20/harm20.json", "w"), indent=1, default=str)
F["harm20_sha256"] = hashlib.sha256(open(f"{S}/stage20/harm20.json", "rb").read()).hexdigest()
F["selection_frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(F, open(f"{S}/stage20/FREEZE_STAGE20.json", "w"), indent=1)
print("floor", floor, "| D1 raw pairs", len(raw))
for n, v in rep["derivation"].items():
    print(n, "D1 n", v["D1"].get("n"), "dp", round(v["D1"].get("dp_median", float("nan")), 4), "ov", v["D1"].get("state_overlap"), v["D1"].get("bars", {}).get("all"),
          "| D2 n", v["D2"].get("n"), "dp", round(v["D2"].get("dp_median", float("nan")), 4), "ov", v["D2"].get("state_overlap"), v["D2"].get("bars", {}).get("all"))
print("SELECTED", sel, rep["selection_rule"])
