"""Stage 12 Part 2 held-out validation on the saved tandem water pixels (leave-one-pair-out):
- Sen2Cor production path: frozen P2 route on BOA S2A vs BOA S2C raw vs BOA-harmonised S2C (all bands);
- TOA residual band differences after harmonisation (V-full: all bands; V-op: operational bands only);
- BOA residual band differences. Up to 4,000 water pixels per pair (seed 12). Writes validate_npz.json."""
import json, math, sys, collections, numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage12/harm"); sys.path.insert(0, f"{S}/stage10/frozen")
import fit_harm as H
import p2 as P2
TR = {f"{p['tile']}_{p['day']}": p for p in json.load(open(f"{S}/stage11/tandem/tandem_results.json"))["pairs"]}
LOPO = json.load(open(f"{S}/stage12/harm/harm_lopo.json"))
PROD = json.load(open(f"{S}/stage12/harm/harm_prod.json"))
out = {"pairs": {}}
def resid(A, Ch, bands):
    r = {}
    for b in bands:
        ok = np.isfinite(A[b]) & np.isfinite(Ch[b]) & (A[b] > 0.0005)
        if ok.sum() < 20: continue
        r[b] = {"ratio": float(np.median(Ch[b][ok] / A[b][ok])), "diff": float(np.median(Ch[b][ok] - A[b][ok])), "n": int(ok.sum())}
    return r
for p in H.PAIRS:
    co = LOPO[p]; sun = TR[p]["sun"]
    At, Ct = H.arrays(p, "toa"); Ab, Cb = H.arrays(p, "boa")
    rec = {"toa_raw": resid(At, Ct, H.BANDS), "toa_vfull": resid(At, H.apply(Ct, co["toa"], H.BANDS), H.BANDS),
           "toa_vop": resid(At, H.apply(Ct, co["toa"], H.OPERATIONAL_TOA), H.BANDS),
           "boa_raw": resid(Ab, Cb, H.BANDS), "boa_h": resid(Ab, H.apply(Cb, co["boa"], H.BANDS), H.BANDS)}
    Ch = H.apply(Cb, co["boa"], H.BANDS)
    n = Ab["B04"].size; idx = np.random.default_rng(12).choice(n, min(4000, n), replace=False)
    paths = collections.defaultdict(list)
    for i in idx:
        for tag, D in (("A", Ab), ("C", Cb), ("Ch", Ch)):
            raw = {"blue": float(D["B02"][i]), "green": float(D["B03"][i]), "red": float(D["B04"][i]), "re1": float(D["B05"][i])}
            if not all(math.isfinite(v) for v in raw.values()): paths[tag].append(None); continue
            paths[tag].append(P2.route(raw, sun, float(D["B11"][i]))["path"])
    ok = [j for j in range(len(idx)) if all(paths[t][j] is not None for t in ("A", "C", "Ch"))]
    rec["p2_flip_raw"] = float(np.mean([paths["A"][j] != paths["C"][j] for j in ok]))
    rec["p2_flip_harmonised"] = float(np.mean([paths["A"][j] != paths["Ch"][j] for j in ok]))
    rec["p2_paths"] = {t: dict(collections.Counter(paths[t][j] for j in ok)) for t in ("A", "C", "Ch")}
    rec["n_pixels"] = len(ok)
    out["pairs"][p] = rec
    print(p, len(ok), f"flip raw {rec['p2_flip_raw']:.3f} harmonised {rec['p2_flip_harmonised']:.3f}", flush=True)
P = out["pairs"]
out["p2_flip_mean_raw"] = float(np.mean([v["p2_flip_raw"] for v in P.values()]))
out["p2_flip_mean_harmonised"] = float(np.mean([v["p2_flip_harmonised"] for v in P.values()]))
out["p2_flip_median_harmonised"] = float(np.median([v["p2_flip_harmonised"] for v in P.values()]))
def pool(key):
    r = {}
    for b in H.BANDS:
        v = [P[p][key][b] for p in P if b in P[p][key]]
        if v: r[b] = {"ratio_median_over_pairs": float(np.median([x["ratio"] for x in v])), "diff_median_over_pairs": float(np.median([x["diff"] for x in v]))}
    return r
out["residual"] = {k: pool(k) for k in ("toa_raw", "toa_vfull", "toa_vop", "boa_raw", "boa_h")}
json.dump(out, open(f"{S}/stage12/harm/validate_npz.json", "w"), indent=1)
print("mean flip raw", round(out["p2_flip_mean_raw"], 3), "harmonised", round(out["p2_flip_mean_harmonised"], 3), "median", round(out["p2_flip_median_harmonised"], 3))
for k in ("toa_raw", "toa_vfull", "boa_raw", "boa_h"):
    print(k, {b: (round(v["ratio_median_over_pairs"], 3), round(v["diff_median_over_pairs"], 5)) for b, v in out["residual"][k].items() if b in ("B02", "B04", "B05", "B8A", "B11", "B12")})
