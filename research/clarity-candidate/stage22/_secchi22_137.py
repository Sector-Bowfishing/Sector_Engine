"""Stage 21 PREREGISTRATION section 6 (adapted from the Stage 20 validation script): Secchi validation after the K2 freeze. S2C rows use the Stage 22 re-runs (res22_truth): A raw, B_stage12, K2 (Stage 21), C1, C3 (the frozen Stage 22 candidate), K1. Originally: Stage 20 PREREGISTRATION section 7: Secchi validation AFTER the freeze (never used to choose). Every eligible S2C
truth row: development S2C anchors (outer-fold predictions, fold posteriors exactly as dev16), Stage 14/15 certification
S2C rows and Stage 16 fresh S2C rows (production model, frozen rule16 gate); the S2A/B rows of the same pools as reference.
Variants for S2C: C0 (none), B (Stage 12), the selected Stage 20 correction (and the other candidates, reported). All
S2C products are issued at FULL authority for the comparison (the product16 S2C line off); the as-shipped lower-authority
Stage 12 product is also scored. Writes secchi21.json."""
import json, os, sys, math, glob, csv, hashlib, collections
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage20", f"{S}/stage16/analysis", f"{S}/stage14/analysis"]
import lib20 as L20
from lib16 import fit_post, product16, op_score, op_summary, CONTAINS
from lib14 import dev_rows, fit_gbm, fold, features, valid, harm, cls, hard_std
import models13_lib as ML
F = json.load(open(f"{S}/stage22/FREEZE_STAGE22.json"))
assert hashlib.sha256(open(f"{S}/stage22/PREREGISTRATION_STAGE22.md", "rb").read()).hexdigest() == F["prereg_sha256"]
assert hashlib.sha256(open(f"{S}/stage22/cand22.json", "rb").read()).hexdigest() == F["cand22_sha256"]
B5 = json.load(open(f"{S}/stage21/corr21.json"))["b05_l2w"]; SEL = json.load(open(f"{S}/stage22/cand22.json"))["selected"]
K2F = L20.c_param({"B05": {"g": B5["g"], "k": B5["k"]}})
CORR = {"A": ("K0", L20.c_none), "B_stage12": ("K0", L20.c_stage12), "K2": ("K1", K2F), "C1": ("C1", L20.c_none), "C3": ("C1", K2F), "K1": ("K1", L20.c_none)}
RS = {}
for f_ in glob.glob(f"{S}/stage22/_res_truth137/*.json"):
    r_ = json.load(open(f_)); kind = os.path.basename(f_)[:-5].split("__")[1]
    for c_ in r_.get("crops", []):
        for pid, pt in (c_.get("points") or {}).items(): RS[(kind, pid)] = pt
def s2c_sample(kind, pid):
    pt = RS.get((kind, pid)) or {}
    return L20.pick(pt.get("M0"), pt.get("M3"))
E14 = json.load(open(f"{S}/stage14/engine/frozen_engine.json")); IQ = E14["interval_q"]
RULE = {"post1": L20.POST1, "post2": L20.POST2, "t1": L20.T1, "t2": L20.T2, "t2opt": "T2-D", "tier3_allowed": ["Clear"]}
FEATS = L20.FEATS


def prod(tier, p, F_, R, platform="sentinel-2a"):
    return product16(tier, p, platform, F_.get("F_ndci"), None, R)


def row(pool, rid, lake, tier, p, F_, y, ft, platform, R, variant, shipped=False):
    o = prod(tier, p, F_, R, "sentinel-2c" if shipped else "sentinel-2a"); c = cls(ft)
    sc, oc, h, sv = op_score(o, c, ft)
    return {"pool": pool, "id": rid, "lake": lake, "tier": tier, "platform": platform, "variant": variant, "p": p, "y": y, "secchi": ft, "c": c, "o": o, "score": sc,
            "outcome": oc, "harmful": h, "severe": sv, "covered": (p + IQ[0] <= y <= p + IQ[1])}


ROWS = []
# ---------------- development (outer folds, fold posteriors as dev16)
ALL, T1, T2, REST = dev_rows(); TT = T1 + T2
rows12 = {x["id"]: x for x in json.load(open(f"{S}/stage12/analysis/rows12.json"))}
T2RAW = {}
for f_ in glob.glob(f"{S}/stage13/coverage/res/*.json"):
    for c in json.load(open(f_)).get("crops", []):
        for pid, p in (c.get("points") or {}).items(): T2RAW[pid] = p
inner = lambda x: fold(x["lake"], 20) % 4
for k in range(5):
    tr = [x for x in T1 if fold(x["lake"]) != k]; ip = []
    for j in range(4):
        g = fit_gbm([x for x in tr if inner(x) != j]); ite = [x for x in TT if fold(x["lake"]) != k and inner(x) == j]
        ip += list(zip([float(v) for v in g.predict(np.array([ML.f7(x) for x in ite]))], [x["y"] for x in ite], [x["tier"] for x in ite]))
    R = {"post1": fit_post([(p, y) for p, y, t in ip if t == 1]), "post2": fit_post([(p, y) for p, y, t in ip if t == 2]), "t1": L20.T1, "t2": L20.T2, "t2opt": "T2-D", "tier3_allowed": ["Clear"]}
    gk = fit_gbm(tr)
    for x in [x for x in TT if fold(x["lake"]) == k]:
        if x["platform"] != "sentinel-2c":
            p = float(gk.predict(np.array([ML.f7(x)]))[0]); ROWS.append(row("dev", x["id"], x["lake"], x["tier"], p, x["F"], x["y"], x["secchi"], x["platform"], R, "ref"))
            continue
        if any(s2c_sample(k_, x["id"])[0] is None for k_ in ("K0", "K1", "C1")): continue
        for vn, (kind, f) in CORR.items():
            tier_, raw = s2c_sample(kind, x["id"])
            Fx, _ = features(f(dict(raw)), x["sun_elev"]); p = float(gk.predict(np.array([[Fx[q] for q in FEATS]]))[0])
            ROWS.append(row("dev", x["id"], x["lake"], tier_, p, Fx, x["y"], x["secchi"], x["platform"], R, vn))
            if vn == "B_stage12":
                ROWS.append(row("dev", x["id"], x["lake"], tier_, p, Fx, x["y"], x["secchi"], x["platform"], R, "B_shipped", shipped=True))
                ROWS[-1]["reproduces_dev15_p"] = None
    print("dev fold", k, flush=True)
# reproduction check: recomputed Stage-12 S2C predictions vs dev15 rows
D15 = {r["id"]: r for r in json.load(open(f"{S}/stage15/analysis/dev15_rows.json"))}
rep = [abs(r["p"] - D15[r["id"]]["p"]) for r in ROWS if r["pool"] == "dev" and r["variant"] == "B_stage12" and r["id"] in D15 and D15[r["id"]].get("p") is not None]
repro = {"n": len(rep), "max_abs_diff": max(rep) if rep else None}
# ---------------- certification (Stage 14 sample + Stage 15 rows; production model)
TR = json.load(open(f"{S}/stage14/unseal/truth14.json")); C = f"{S}/stage14/cert"
smp = [dict(r, part="NLA" if r["src"].startswith("NLA") else "SYKE") for r in csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv"))] + [dict(r, part="WQP") for r in csv.DictReader(open(f"{C}/wqp_sample.csv"))]
OUTS = sorted(glob.glob(f"{S}/stage12/cert/out_*.csv")) + [f"{S}/stage13/cert/out13_c1.csv", f"{S}/stage13/cert/out13_legacy.csv", f"{C}/out_wqp_c1.csv", f"{C}/out_wqp_legacy.csv"]
want = {(r["id"], r["item"]) for r in smp}; X = {}
for pth in OUTS:
    if "discarded" in pth: continue
    for r in csv.DictReader(open(pth)):
        k_ = (r["id"], r.get("item"))
        if k_ in want and not r.get("error"):
            try: nv = int(float(r.get("n_valid") or 0))
            except ValueError: continue
            if k_ not in X or nv > X[k_][0]: X[k_] = (nv, r)
A = {}
for f_ in glob.glob(f"{C}/res_ns/*.json") + glob.glob(f"{C}/res_wqp/*.json"):
    r = json.load(open(f_))
    for c in r.get("crops", []):
        for pid, pt in (c.get("points") or {}).items(): A[(pid, r["item"])] = pt
gf = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None


def score_pool(pool, samples):
    for rid, lake, plat, pt, sun, ft in samples:
        if sun is None or not ft: continue
        y = math.log10(ft)
        if plat != "sentinel-2c":
            tier, a = L20.pick(pt.get("M0"), pt.get("M3"))
            if tier is None: continue
            p, Fx = L20.predict(dict(a), sun); ROWS.append(row(pool, rid, lake, tier, p, Fx, y, ft, plat, RULE, "ref")); continue
        if any(s2c_sample(k_, rid)[0] is None for k_ in ("K0", "K1", "C1")): continue
        for vn, (kind, f) in CORR.items():
            tier, a = s2c_sample(kind, rid); b = f(dict(a)); p, Fx = L20.predict(b, sun)
            ROWS.append(row(pool, rid, lake, tier, p, Fx, y, ft, plat, RULE, vn))
            if vn == "B_stage12": ROWS.append(row(pool, rid, lake, tier, p, Fx, y, ft, plat, RULE, "B_shipped", shipped=True))


cs = []
for r in smp:
    t = TR.get(r["id"]) or {}
    xr = X.get((r["id"], r["item"]), (0, {}))[1]; pt = A.get((r["id"], r["item"])) or {}
    plat = r.get("platform") or xr.get("platform") or ""
    cs.append((r["id"], r["lake"], plat, pt, gf(xr, "sun_elev") if xr else None, t.get("secchi_ft")))
score_pool("cert", cs)
# ---------------- Stage 16 fresh
D = f"{S}/stage16/fresh"; TRf = json.load(open(f"{D}/truth16.json")); smpf = list(csv.DictReader(open(f"{D}/fresh_sample.csv"))); Xf = {}
for r in csv.DictReader(open(f"{D}/out_fresh_c1.csv")):
    k_ = (r["id"], r.get("item"))
    if not r.get("error"):
        try: nv = int(float(r.get("n_valid") or 0))
        except ValueError: continue
        if k_ not in Xf or nv > Xf[k_][0]: Xf[k_] = (nv, r)
Af = {}
for f_ in glob.glob(f"{D}/res_fresh/*.json"):
    r = json.load(open(f_))
    for c in r.get("crops", []):
        for pid, pt in (c.get("points") or {}).items(): Af[(pid, r["item"])] = pt
fs = []
for r in smpf:
    t = TRf.get(r["id"]) or {}; xr = Xf.get((r["id"], r["item"]), (0, {}))[1]
    fs.append((r["id"], r["lake"], r["platform"], Af.get((r["id"], r["item"])) or {}, gf(xr, "sun_elev") if xr else None, t.get("secchi_ft")))
score_pool("fresh", fs)


# ---------------- summaries
def summ(rs):
    if not rs: return {"n": 0}
    s = op_summary(rs); shown = [r for r in rs if r["o"]["state"] in CONTAINS]
    return {"n": len(rs), "lakes": len({r["lake"] for r in rs}), "classes": dict(collections.Counter(L20.CLASSES[r["c"]] for r in rs)),
            "feet_abs_err_median": float(np.median([abs(10 ** r["p"] - r["secchi"]) for r in rs])), "log_abs_err_median": float(np.median([abs(r["p"] - r["y"]) for r in rs])),
            "signed_log_bias_median": float(np.median([r["p"] - r["y"] for r in rs])), "operational": s["balanced"], "overall_mean": s["overall_mean"],
            "per_class": {n: v["mean"] for n, v in s["per_class"].items()}, "per_class_n": {n: v["n"] for n, v in s["per_class"].items()},
            "harmful": s["harmful_rate"], "severe": s["severe_rate"], "interval_coverage": float(np.mean([r["covered"] for r in rs])),
            "unknown_share": 1 - len(shown) / len(rs), "hard_class_acc": float(np.mean([hard_std(r["p"]) == r["c"] for r in rs]))}


out = {"selected": SEL, "dev_reproduction_check": repro, "pools": {}}
for pool in ("dev", "cert", "fresh", "all"):
    rs = [r for r in ROWS if pool == "all" or r["pool"] == pool]
    out["pools"][pool] = {"S2AB_reference": summ([r for r in rs if r["variant"] == "ref"]),
                          **{v: summ([r for r in rs if r["platform"] == "sentinel-2c" and r["variant"] == v]) for v in list(CORR) + ["B_shipped"]}}
a = out["pools"]["all"]; s2 = a[SEL]; ref = a["S2AB_reference"]
out["full_authority_checks"] = {"harmful_le_ref_plus_0.05": s2["harmful"] <= ref["harmful"] + 0.05, "severe_le_0.02": s2["severe"] <= 0.02,
                                "bias_within_0.05_of_ref": abs(s2["signed_log_bias_median"] - ref["signed_log_bias_median"]) <= 0.05}
out["full_authority_checks"]["PASSED"] = all(out["full_authority_checks"].values())
json.dump(out, open(f"{S}/stage22/secchi22_137.json", "w"), indent=1, default=str)
json.dump(ROWS, open(f"{S}/stage22/secchi22_rows_137.json", "w"), default=str)
print("dev reproduction", repro)
for pool, v in out["pools"].items():
    for k, s in v.items():
        if s.get("n"): print(pool, k, "n", s["n"], "op", round(s["operational"], 3), "bias", round(s["signed_log_bias_median"], 3), "harm", round(s["harmful"], 3), "sev", round(s["severe"], 3),
                             "cov", round(s["interval_coverage"], 3), "ft", round(s["feet_abs_err_median"], 2), {n: (m if m is None else round(m, 2)) for n, m in s["per_class"].items()})
print("CHECKS", out["full_authority_checks"])
