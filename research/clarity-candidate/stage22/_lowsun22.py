# Report-only: C3's visibility bias by S2C sun elevation (derivation and held out).
import sys, numpy as np
sys.path.insert(0, ".")
import _anal22_lib as A
for grp, sets in (("derivation", ("TD", "T2D")), ("held-out", ("TH", "T2H", "S"))):
    rows = []
    for s in sets:
        for p in A.pairs_for(s):
            R_ = A.scene(p["ref"]); d0 = ((p["c"].get("K0") or {}).get("diag") or {})
            vv, corr = A.VERS["C3"]; C_ = A.scene(p["c"].get(vv), corr); K_ = A.scene(p["c"].get("K0"))
            if R_ and C_ and K_ and d0.get("sza") is not None: rows.append((90 - d0["sza"], C_["p"] - R_["p"], K_["p"] - R_["p"]))
    for lo, hi in ((0, 25), (25, 40), (40, 91)):
        g = [r for r in rows if lo <= r[0] < hi]
        if g: print(grp, f"sun {lo}-{hi}", "n", len(g), "raw", round(float(np.median([x[2] for x in g])), 3), "C3", round(float(np.median([x[1] for x in g])), 3))
print("EXIT")
