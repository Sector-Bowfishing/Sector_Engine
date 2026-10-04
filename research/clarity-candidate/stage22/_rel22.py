# Report-only (after the freeze): is the seasonal/sun effect the SIZE of the glint transferred, or its SHARE of the water signal?
import sys, json, numpy as np
sys.path.insert(0, ".")
import _anal22_lib as A
out = {}
for grp, sets in (("derivation", ("TD", "T2D")), ("held-out", ("TH", "T2H", "S"))):
    rows = [r for s in sets for r in A.mech(A.pairs_for(s))]
    def strat(name, f):
        g = [r for r in rows if f(r)]
        def m(fn):
            v = [fn(r) for r in g]; v = [x for x in v if x is not None and np.isfinite(x)]; return round(float(np.median(v)), 4) if v else None
        drg = lambda r: (r["rhog_c"].get("B04") - r["rhog_ref"].get("B04")) if r["rhog_c"].get("B04") is not None and r["rhog_ref"].get("B04") is not None else None
        ws = lambda r: r["rhos_ref"].get("B04")
        out[f"{grp}|{name}"] = {"n": len(g), "dp": m(lambda r: r["dp"]), "dp_C1": m(lambda r: r["dp_C1"]), "d_rhog_B04": m(drg),
                                "ref_rhos_B04": m(ws), "rel_rhog_share": m(lambda r: drg(r) / ws(r) if drg(r) is not None and ws(r) and ws(r) > 0 else None)}
    strat("winter", lambda r: r["season"] == "winter"); strat("warm", lambda r: r["season"] != "winter")
    strat("sun<25", lambda r: r["sun_c"] < 25); strat("sun25-40", lambda r: 25 <= r["sun_c"] < 40); strat("sun>=40", lambda r: r["sun_c"] >= 40)
for k, v in out.items(): print(k, v)
json.dump(out, open("rel22.json", "w"), indent=1)
