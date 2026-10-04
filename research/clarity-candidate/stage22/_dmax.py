# Report-only: the strongest |Spearman| any allowed scene-level x reached for any member pair on TD+T2D (D eligibility needed >= 0.4).
import sys, itertools, json, numpy as np
sys.path.insert(0, ".")
import _anal22_lib as A
from scipy.stats import spearmanr
fam = ["A", "C1", "C2", "C3"]; rows = []
for P in (A.pairs_for("TD"), A.pairs_for("T2D")):
    for p in P:
        R_ = A.scene(p["ref"]); d0 = ((p["c"].get("K0") or {}).get("diag") or {})
        if not R_: continue
        x = {"sun": 90 - d0["sza"] if d0.get("sza") is not None else None, "rhogref": d0.get("rhog_ref"), "aot": d0.get("aot_550")}
        sub = (p["c"].get("C1") or {}).get("toa_sub") or {}; x["m_C"] = (sub["B11"] - A.C21["alpha"]) / A.C21["beta"] if sub.get("B11") is not None else None
        dps = {}
        for v in fam:
            vv, corr = A.VERS[v]; C_ = A.scene(p["c"].get(vv), corr); dps[v] = (C_["p"] - R_["p"]) if C_ else None
        rows.append({"x": x, "dp": dps})
out = []
for xn in ("sun", "rhogref", "aot", "m_C"):
    for m1, m2 in itertools.combinations(fam, 2):
        v = [(r["x"][xn], r["dp"][m1] - r["dp"][m2]) for r in rows if r["x"][xn] is not None and r["dp"][m1] is not None and r["dp"][m2] is not None]
        if len(v) >= 20: out.append((abs(float(spearmanr([a for a, b in v], [b for a, b in v]).correlation)), xn, m1, m2, len(v)))
out.sort(reverse=True); print("DMAX", json.dumps(out[:6]))
