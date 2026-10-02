"""Stage 13 shared definitions, fixed by PREREGISTRATION_STAGE13.md (features section 2, switch section 3, QAA-switch
section 4, classes, folds, regions)."""
import json, math, sys, os, random, collections
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D13 = f"{S}/stage13"
sys.path.insert(0, f"{S}/stage12/analysis")
from common12 import load12, fold, cls, cname, CLASSES, dog, ndci, gunt, champ, FT      # Stage 11/12 definitions
FL = 1e-4
f = lambda v: max(v, FL) if v is not None and math.isfinite(v) else FL

# ---------------- section 2 features
FEATS6 = ["F_red", "F_ndci", "F_bg", "F_gr", "F_re", "F_bright"]
def features(a, sun):
    r = {k: a.get(k) for k in ("B01", "B02", "B03", "B04", "B05", "B06", "B8A")}
    F = {"F_red": math.log10(f(r["B04"])), "F_ndci": (f(r["B05"]) - f(r["B04"])) / (f(r["B05"]) + f(r["B04"])),
         "F_bg": math.log10(f(r["B02"]) / f(r["B03"])), "F_gr": math.log10(f(r["B03"]) / f(r["B04"])),
         "F_re": math.log10(f(r["B06"]) / f(r["B04"])), "F_bright": math.log10(f(np.mean([r[k] for k in ("B02", "B03", "B04", "B05")])))}
    q = qaa_switch(a, sun)
    F["F_kd"] = math.log10(q["kd492"]) if q.get("kd492") else float("nan")
    return F, q

# ---------------- section 3 Dogliotti 2015 red/NIR switch
def t_red(r665): r = max(r665, 0.0); return 228.1 * r / max(1e-6, 1 - r / 0.1641)
def t_nir(r865): r = max(r865, 0.0); return 3078.9 * r / max(1e-6, 1 - r / 0.2112)
def t_switch(r665, r865):
    if r665 < 0.05 or r865 is None or not math.isfinite(r865): return t_red(r665), 0.0
    if r665 > 0.07: return t_nir(r865), 1.0
    w = (r665 - 0.05) / 0.02; return (1 - w) * t_red(r665) + w * t_nir(r865), w

# ---------------- section 4 QAA-switch Secchi (new; not P1)
LAM = {"B01": 443.0, "B02": 492.0, "B03": 560.0, "B04": 665.0, "B05": 704.0, "B06": 740.0}
AW = {"B01": 0.00715, "B02": 0.0212, "B03": 0.0632, "B04": 0.4156, "B05": 0.702, "B06": 2.726}
BBW = {k: 0.00111 * (500.0 / l) ** 4.32 for k, l in LAM.items()}
G0, G1 = 0.089, 0.1245
VIS4 = ("B01", "B02", "B03", "B04")
def qaa_switch(a, sun):
    if sun is None or sun < 20: return {"why": "sun"}
    R = {}
    for k in LAM:
        v = a.get(k)
        if v is None or not math.isfinite(v): return {"why": f"missing {k}"}
        R[k] = v / math.pi
    if any(R[k] <= 0 for k in VIS4): return {"why": "Rrs<=0"}
    rrs = {k: v / (0.52 + 1.7 * v) for k, v in R.items()}
    u = {k: (-G0 + math.sqrt(max(G0 ** 2 + 4 * G1 * v, 0))) / (2 * G1) for k, v in rrs.items()}
    if R["B04"] < 0.0015:
        ref = "B03"; x = math.log10((rrs["B01"] + rrs["B02"]) / (rrs["B03"] + 5 * rrs["B04"] ** 2 / rrs["B02"]))
        a0 = AW["B03"] + 10 ** (-1.146 - 1.366 * x - 0.469 * x * x)
    elif R["B06"] < 0.004:
        ref = "B04"; a0 = AW["B04"] + 0.39 * (R["B04"] / (R["B01"] + R["B02"])) ** 1.14
    else:
        ref = "B06"
        if R["B06"] <= 0: return {"why": "Rrs740<=0"}
        a0 = AW["B06"]
    u0 = u[ref]
    if not (0 < u0 < 1): return {"why": "u", "ref": ref}
    bbp0 = u0 * a0 / (1 - u0) - BBW[ref]
    if bbp0 <= 0: return {"why": "bbp<=0", "ref": ref}
    eta = 2.0 * (1 - 1.2 * math.exp(-0.9 * rrs["B01"] / rrs["B03"]))
    if eta < 0: eta = 0.0
    th = 90.0 - sun; kd = {}
    for k in VIS4:
        if not (0 < u[k] < 1): return {"why": "u", "ref": ref}
        bb = BBW[k] + bbp0 * (LAM[ref] / LAM[k]) ** eta
        ak = (1 - u[k]) * bb / u[k]
        if ak < 0.9 * AW[k]: return {"why": "a<aw", "ref": ref}
        kd[k] = (1 + 0.005 * th) * ak + 4.259 * (1 - 0.265 * BBW[k] / bb) * (1 - 0.52 * math.exp(-10.8 * ak)) * bb
    tr = min(VIS4, key=lambda k: kd[k])
    arg = abs(0.14 - R[tr]) / 0.013
    if arg <= 1: return {"why": "Zsd<=0", "ref": ref}
    z = math.log(arg) / (2.5 * kd[tr]) * FT
    out = {"ref": ref, "kd492": kd["B02"], "band": tr}
    if not (0.2 <= z <= 25): return {**out, "why": "range"}
    return {**out, "zsd_ft": z}

# ---------------- classes, metrics, bootstrap, regions
def cidx(ft): return None if ft is None else cls(ft)
def class_metrics(true, pred):
    """true/pred: lists of class indices (pred None = no answer = miss)."""
    out = {}
    for c, name in enumerate(CLASSES):
        tp = sum(1 for t, p in zip(true, pred) if t == c and p == c); nt = sum(1 for t in true if t == c); npred = sum(1 for p in pred if p == c)
        out[name] = {"recall": tp / nt if nt else None, "precision": tp / npred if npred else None, "n": nt}
    out["balanced_accuracy"] = float(np.mean([out[n]["recall"] for n in CLASSES if out[n]["recall"] is not None]))
    ans = [(t, p) for t, p in zip(true, pred) if p is not None]
    out["answered"] = len(ans) / len(true) if true else None
    out["two_class_errors"] = sum(1 for t, p in ans if abs(t - p) >= 2) / len(ans) if ans else None
    # quadratic weighted kappa on answered rows
    if ans:
        K = 4; O = np.zeros((K, K))
        for t, p in ans: O[t, p] += 1
        E = np.outer(O.sum(1), O.sum(0)) / O.sum(); Wt = np.array([[(i - j) ** 2 / (K - 1) ** 2 for j in range(K)] for i in range(K)])
        out["qwk"] = float(1 - (Wt * O).sum() / (Wt * E).sum())
    return out
def lake_boot_diff(rows, fn, B=2000, seed=12):
    by = collections.defaultdict(list)
    for r in rows: by[r["lake"]].append(r)
    L = sorted(by); g = random.Random(seed); v = []
    for _ in range(B):
        smp = [x for _ in L for x in by[L[g.randrange(len(L))]]]
        try:
            y = fn(smp)
        except Exception:
            y = None
        if y is not None and math.isfinite(y): v.append(y)
    v.sort(); return [round(v[int(.025 * len(v))], 4), round(v[int(.975 * len(v)) - 1], 4)] if len(v) > 100 else None
REGION = {}
for s in "CT ME MA NH RI VT NY NJ PA DE MD DC".split(): REGION[s] = 0
for s in "VA WV NC SC GA FL AL MS TN KY".split(): REGION[s] = 1
for s in "OH IN IL MI WI MN IA MO".split(): REGION[s] = 2
for s in "ND SD NE KS OK TX AR LA".split(): REGION[s] = 3
def region(state): return REGION.get(state, 4)
