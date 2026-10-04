# Report-only diagnostic (after eval23): TOA dark-water offset (S2C - S2A rhot, disk median) by set and baseline; the C1 offset applied.
import sys, json, numpy as np
sys.path.insert(0, "."); sys.argv = ["anal23.py"]
src = open("anal23.py").read().split("# ---------------- section 3: the floor")[0]; exec(src)
TH = [p for p in A22.pairs_for("TH") if (sun(p["c"].get("K0")) or 0) >= 25]
T2H = [p for p in A22.pairs_for("T2H") if (sun(p["c"].get("K0")) or 0) >= 25]
T2N = [p for p in pairs23("T2N", "res23_T2N", True) if (sun(p["c"].get("K0")) or 0) >= 25 and A22.ice_ok(p)]
def d(P, name):
    out = {}
    for b in ("B08", "B8A", "B11", "B12"):
        v = [((p["c"]["K0"]["diag"].get("rhot") or {}).get(b) - (p["ref"]["diag"].get("rhot") or {}).get(b)) for p in P if p["c"].get("K0") and p["ref"] and (p["c"]["K0"]["diag"].get("rhot") or {}).get(b) is not None and (p["ref"]["diag"].get("rhot") or {}).get(b) is not None]
        out[b] = round(float(np.median(v)), 5) if v else None
    sub = [((p["c"].get("C1") or {}).get("toa_sub") or {}).get("B11") for p in P]; sub = [x for x in sub if x is not None]
    print(name, "n", len(P), "TOA S2C-S2A", out, "| C1 B11 offset applied (median)", round(float(np.median(sub)), 5) if sub else None, "| sun median", round(float(np.median([sun(p["c"]["K0"]) for p in P if p["c"].get("K0")])), 1))
d(TH, "TH25 N0511"); d([p for p in T2H if p["baseline"] == "N0511"], "T2H25 N0511"); d([p for p in T2H if p["baseline"] == "N0512"], "T2H25 N0512"); d(T2N, "T2N  N0513")
