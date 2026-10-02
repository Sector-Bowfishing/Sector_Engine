"""Stage 11 Part A (PREREGISTRATION_STAGE11.md section 3): the champion's Secchi error, split exactly into a
radiometric-and-retrieval part and a conversion part, then attributed inside each part by satellite-observable blocks
(lake-held-out Shapley R^2). Writes part_a.json."""
import json, math, itertools, collections, sys
import numpy as np
from common import *

rows = load()
A = [x for x in rows if x.get("turb") is not None and x["turb"] >= 0 and x["fnu"] is not None and x["secchi"] and x["secchi"] > 0]
def terms(x):
    eT = math.log10(max(x["fnu"], 0.1) / max(x["turb"], 0.1))
    eC = math.log10(champ(x["turb"]) / x["secchi"])
    eS = math.log10(x["champ"] / x["secchi"])
    return eS, eT, eC
for x in A:
    x["eS"], x["eT"], x["eC"] = terms(x)
res = {"rows_with_turbidity": len(A), "lakes": len({x["lake"] for x in A})}
def split(R):
    eS = np.array([x["eS"] for x in R]); a = -0.637 * np.array([x["eT"] for x in R]); b = np.array([x["eC"] for x in R])
    v = eS.var()
    return {"n": len(R), "lakes": len({x["lake"] for x in R}), "var_eS": round(float(v), 4), "identity_max_err": round(float(np.max(np.abs(eS - a - b))), 6),
            "var_radiometric_term": round(float(a.var()), 4), "var_conversion_term": round(float(b.var()), 4), "cov2": round(float(2 * np.cov(a, b, bias=True)[0, 1]), 4),
            "share_radiometric": round(float(np.cov(a, eS, bias=True)[0, 1] / v), 3), "share_conversion": round(float(np.cov(b, eS, bias=True)[0, 1] / v), 3),
            "median_abs_eS": round(float(np.median(np.abs(eS))), 3), "median_abs_if_perfect_turbidity": round(float(np.median(np.abs(b))), 3),
            "median_abs_if_perfect_conversion": round(float(np.median(np.abs(a))), 3),
            "median_eT": round(float(np.median([x["eT"] for x in R])), 3), "median_abs_eT": round(float(np.median(np.abs([x["eT"] for x in R]))), 3),
            "median_eC": round(float(np.median(b)), 3)}
res["split_dt0"] = split([x for x in A if x["dt"] == 0])
res["split_dt_le1"] = split(A)
res["split_by_set_dt0"] = {s: split([x for x in A if x["dt"] == 0 and x["set"] == s]) for s in ("G", "N", "F", "E") if sum(1 for x in A if x["dt"] == 0 and x["set"] == s) >= 10}
res["split_by_unit_dt0"] = {u: split([x for x in A if x["dt"] == 0 and x.get("turbUnit") == u]) for u in ("NTU", "FNU") if sum(1 for x in A if x["dt"] == 0 and x.get("turbUnit") == u) >= 10}
res["share_ci_dt0"] = lake_boot([x for x in A if x["dt"] == 0], lambda R: split(R)["share_radiometric"])

# 2. the best achievable conversion: lake-held-out refits on in-situ turbidity (and chlorophyll)
def cv_conv(R, use_chl):
    R = [x for x in R if (x.get("chl") is not None and x["chl"] > 0) or not use_chl]
    errs = []
    for k in range(5):
        tr = [x for x in R if fold(x["lake"]) != k]; te = [x for x in R if fold(x["lake"]) == k]
        if len(tr) < 20 or not te: continue
        X = lambda x: [1.0, math.log10(max(x["turb"], 0.1))] + ([math.log10(max(x["chl"], 0.1))] if use_chl else [])
        b = np.linalg.lstsq(np.array([X(x) for x in tr]), np.array([math.log10(x["secchi"]) for x in tr]), rcond=None)[0]
        errs += [float(np.dot(b, X(x)) - math.log10(x["secchi"])) for x in te]
    return {"n": len(errs), "median_abs_log": round(float(np.median(np.abs(errs))), 3) if errs else None,
            "champion_formula_on_same_rows": round(float(np.median(np.abs([x["eC"] for x in R]))), 3) if R else None}
D0 = [x for x in A if x["dt"] == 0]
res["best_conversion"] = {"turbidity_only": cv_conv(D0, False), "turbidity_and_chl": cv_conv(D0, True)}

# 3. attribution inside each part: lake-held-out R^2 of linear models on the blocks, Shapley over blocks
def feats_block(x, blk):
    if blk == "AC/aerosol":
        return [math.log10(max(x["aot"], 0.01)) if x.get("aot") is not None else 0.0, 1.0 if x.get("aot") is None else 0.0]
    if blk == "glint":
        g = x.get("glint_deg"); sw = x["raw"].get("swir16")
        return [g / 30.0 if g is not None else 1.0, 1.0 if g is None else 0.0, sw * 100 if sw is not None else 0.0]
    if blk == "adjacency":
        d = x.get("dist_nonwater_m")
        return [math.log10(max(d, 10.0)) if d is not None else 2.0, 1.0 if d is None else 0.0]
    if blk == "platform":
        p = x.get("platform") or ""
        return [1.0 if p.endswith("2b") else 0.0, 1.0 if p.endswith("2c") else 0.0]
    if blk == "water type":
        return [1.0 if x["owt"] == t else 0.0 for t in ("algal", "sediment", "mixed", "unsupported")]
BLOCKS = ["AC/aerosol", "glint", "adjacency", "platform", "water type"]
def cv_r2(R, target, blks):
    y = np.array([x[target] for x in R]); pred = np.zeros(len(R)); base = np.zeros(len(R))
    for k in range(5):
        tr = [i for i, x in enumerate(R) if fold(x["lake"]) != k]; te = [i for i, x in enumerate(R) if fold(x["lake"]) == k]
        if not te: continue
        mu = y[tr].mean(); base[te] = mu
        if not blks:
            pred[te] = mu; continue
        X = np.array([[1.0] + sum((feats_block(R[i], b) for b in blks), []) for i in range(len(R))])
        lam = 1e-3 * np.eye(X.shape[1]); lam[0, 0] = 0
        beta = np.linalg.solve(X[tr].T @ X[tr] + lam, X[tr].T @ y[tr])
        pred[te] = X[te] @ beta
    return 1 - float(((y - pred) ** 2).sum() / ((y - base) ** 2).sum())
def shapley(R, target):
    vals = {}
    for m in range(len(BLOCKS) + 1):
        for comb in itertools.combinations(BLOCKS, m):
            vals[frozenset(comb)] = cv_r2(R, target, list(comb))
    n = len(BLOCKS); out = {}
    for b in BLOCKS:
        s = 0.0
        for m in range(n):
            for comb in itertools.combinations([c for c in BLOCKS if c != b], m):
                w = math.factorial(m) * math.factorial(n - m - 1) / math.factorial(n)
                s += w * (vals[frozenset(comb) | {b}] - vals[frozenset(comb)])
        out[b] = round(s, 4)
    out["_total_cv_R2"] = round(vals[frozenset(BLOCKS)], 4)
    return out
res["shapley_eT_dt0"] = shapley(D0, "eT")
res["shapley_eC_dt0"] = shapley(D0, "eC")
res["shapley_eS_dt0"] = shapley(D0, "eS")
# 4. the attribution table: share of Var(eS)
sp = res["split_dt0"]; sr, sc = sp["share_radiometric"], sp["share_conversion"]
tab = {}
for b in BLOCKS:
    tab[f"radiometric: {b}"] = round(sr * max(0.0, res["shapley_eT_dt0"][b]), 3)
tab["radiometric: unexplained (match-up, instrument, residual)"] = round(sr * (1 - max(0.0, res["shapley_eT_dt0"]["_total_cv_R2"])), 3)
tab["conversion: water type"] = round(sc * max(0.0, res["shapley_eC_dt0"]["water type"]), 3)
tab["conversion: other blocks"] = round(sc * max(0.0, sum(max(0.0, res["shapley_eC_dt0"][b]) for b in BLOCKS if b != "water type")), 3)
tab["conversion: unexplained (Secchi-turbidity scatter, CDOM, algae not typed)"] = round(sc * (1 - max(0.0, res["shapley_eC_dt0"]["_total_cv_R2"])), 3)
res["attribution_share_of_var_eS"] = dict(sorted(tab.items(), key=lambda kv: -kv[1]))
ranked = list(res["attribution_share_of_var_eS"].items())
res["primary"] = ranked[0][0] if ranked[0][1] >= 1.25 * ranked[1][1] else f"shared between {ranked[0][0]} and {ranked[1][0]}"
# e_T and e_C by water type, platform, adjacency band
def grp(R, key):
    g = collections.defaultdict(list)
    for x in R: g[key(x)].append(x)
    return {k: {"n": len(v), "lakes": len({x['lake'] for x in v}), "median_eT": round(float(np.median([x['eT'] for x in v])), 3),
                "median_abs_eT": round(float(np.median(np.abs([x['eT'] for x in v]))), 3),
                "median_eC": round(float(np.median([x['eC'] for x in v])), 3), "median_abs_eC": round(float(np.median(np.abs([x['eC'] for x in v]))), 3),
                "median_eS": round(float(np.median([x['eS'] for x in v])), 3), "median_abs_eS": round(float(np.median(np.abs([x['eS'] for x in v]))), 3)}
            for k, v in sorted(g.items(), key=lambda kv: str(kv[0])) if len(v) >= 10}
res["by_owt_dt0"] = grp(D0, lambda x: x["owt"])
res["by_insitu_type_dt0"] = grp([x for x in D0 if x["insitu_type"]], lambda x: x["insitu_type"])
res["by_platform_dt0"] = grp(D0, lambda x: x.get("platform"))
res["by_adjacency_dt0"] = grp([x for x in D0 if x.get("dist_nonwater_m") is not None], lambda x: "<100 m" if x["dist_nonwater_m"] < 100 else "100-300 m" if x["dist_nonwater_m"] < 300 else ">=300 m")
res["by_secchi_class_dt0"] = grp(D0, lambda x: ("clear >=6", "normal 3-6", "stained 2-3", "limited <2")[cls(x["secchi"])])
json.dump(res, open(f"{D11}/analysis/part_a.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in ("rows_with_turbidity", "lakes", "split_dt0", "share_ci_dt0", "best_conversion", "attribution_share_of_var_eS", "primary")}, indent=1))
