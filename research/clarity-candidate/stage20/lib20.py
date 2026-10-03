"""Stage 20 library (PREREGISTRATION_STAGE20.md sections 3-6): frozen engine pieces, corrections, splits, pair metrics."""
import json, math, os, sys, hashlib, pickle
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
for p in (f"{S}/stage14/analysis", f"{S}/stage16/analysis"):
    if p not in sys.path: sys.path.insert(0, p)
from lib14 import harm, valid, features, hard_std, CLASSES
from lib16 import gate, posterior, CONTAINS
import models13_lib as L
G = pickle.load(open(f"{S}/stage14/engine/frozen_gbm.pkl", "rb"))
_R = json.load(open(f"{S}/stage16/engine/rule16.json"))
POST1 = {int(b): tuple(v) for b, v in _R["post1"].items()}; POST2 = {int(b): tuple(v) for b, v in _R["post2"].items()}
T1, T2 = _R["t1"], _R["t2"]
SB = json.load(open(f"{S}/stage20/srf20.json"))["sbaf_S2C_to_S2A"]
VIS = ("B02", "B03", "B04", "B05")
FEATS = L.FEATS6 + ["F_kd"]


def pick(m0, m3):
    """tier and band dict as the engine picks them (tier 1 M0 valid, else tier 2 M3), else (None, None)."""
    if valid(m0): return 1, m0
    if valid(m3): return 2, m3
    return None, None


def c_none(a): return dict(a)
def c_stage12(a): return harm(dict(a), "sentinel-2c")


def c_sbaf(a):
    v = dict(a)
    for b, c in SB.items():
        if isinstance(a.get(b), (int, float)):
            v[b] = c["g"] * a[b] + (c.get("k", 0) * (a.get("B06", 0) - a.get("B04", 0)) if b == "B05" else 0)
    return v


def c_param(par):
    def f(a):
        v = dict(a)
        for b, c in par.items():
            if isinstance(a.get(b), (int, float)):
                v[b] = c["g"] * a[b] + c.get("o", 0) + (c.get("k", 0) * (a.get("B06", 0) - a.get("B04", 0)) if b == "B05" else 0)
        return v
    return f


def predict(a, sun):
    F, q = features(a, sun)
    return float(G.predict(np.array([[F[k] for k in FEATS]]))[0]), F


def state(p, tier):
    st, conf, w = gate(p, POST2 if tier == 2 else POST1, T1, T2, boundary_only=(tier == 2))
    return st, conf


def scene(m0, m3, sza, corr=None):
    tier, a = pick(m0, m3)
    if tier is None or sza is None: return None
    a = corr(a) if corr else dict(a)
    sun = 90.0 - sza
    p, F = predict(a, sun); st, conf = state(p, tier)
    return {"tier": tier, "a": {b: a.get(b) for b in ("B01", "B02", "B03", "B04", "B05", "B06", "B07", "B8A")}, "p": p, "F": F, "state": st, "conf": conf, "hard": hard_std(p)}


def split(keys_counts, force_derivation=()):
    """section 3: whole units; forced keys first; then md5 order, each to the split with fewer site-pairs (tie -> derivation)."""
    d, h, nd, nh = set(), set(), 0, 0
    for k in force_derivation:
        if k in keys_counts: d.add(k); nd += keys_counts[k]
    for k in sorted([k for k in keys_counts if k not in d], key=lambda k: hashlib.md5(f"stage20|{k}".encode()).hexdigest()):
        if nd <= nh: d.add(k); nd += keys_counts[k]
        else: h.add(k); nh += keys_counts[k]
    return d, h


def pair_metrics(pairs, floor=None, tandem=True):
    """pairs: [{'c': scene, 'r': scene}] both valid. -> section 4/6 quantities and the bar verdicts."""
    n = len(pairs)
    if not n: return {"n": 0}
    rb = {}
    for b in VIS:
        v = [math.log10(x["c"]["a"][b] / x["r"]["a"][b]) for x in pairs if x["c"]["a"].get(b, 0) > 0.001 and x["r"]["a"].get(b, 0) > 0.001]
        rb[b] = {"n": len(v), "median": float(np.median(v)) if v else None, "iqr": [float(np.percentile(v, 25)), float(np.percentile(v, 75))] if v else None}
    dp = [x["c"]["p"] - x["r"]["p"] for x in pairs]
    both = [x for x in pairs if x["c"]["state"] and x["r"]["state"]]
    ov = [bool(CONTAINS[x["c"]["state"]] & CONTAINS[x["r"]["state"]]) for x in both]
    jump = [abs(x["c"]["hard"] - x["r"]["hard"]) >= 2 for x in pairs]
    fd = {f: float(np.median([x["c"]["F"][f] - x["r"]["F"][f] for x in pairs if math.isfinite(x["c"]["F"][f]) and math.isfinite(x["r"]["F"][f])] or [float("nan")])) for f in FEATS}
    conf = [x["c"]["conf"] - x["r"]["conf"] for x in both if x["c"]["conf"] is not None and x["r"]["conf"] is not None]
    out = {"n": n, "band_log_ratio": rb, "dp_median": float(np.median(dp)), "dp_iqr": [float(np.percentile(dp, 25)), float(np.percentile(dp, 75))],
           "dp_mean": float(np.mean(dp)), "n_states": len(both), "state_overlap": float(np.mean(ov)) if ov else None, "jump_rate": float(np.mean(jump)),
           "feature_diff_median": fd, "posterior_diff_median": float(np.median(conf)) if conf else None,
           "unknown_c": float(np.mean([x["c"]["state"] is None for x in pairs])), "unknown_r": float(np.mean([x["r"]["state"] is None for x in pairs]))}
    sp_lim = 0.0128 if tandem else 0.0212
    ov_lim = 0.95 if tandem else min(0.95, (floor or {}).get("state_overlap", 0.95) - 0.03)
    j_lim = 0.02 if tandem else (floor or {}).get("jump_rate", 0.0) + 0.02
    out["bars"] = {"spectral": all(rb[b]["median"] is not None and abs(rb[b]["median"]) <= sp_lim for b in VIS), "visibility": abs(out["dp_median"]) <= 0.03,
                   "state": (out["state_overlap"] is not None and out["state_overlap"] >= ov_lim), "harm": out["jump_rate"] <= j_lim,
                   "limits": {"spectral": sp_lim, "state": ov_lim, "harm": j_lim}}
    out["bars"]["all"] = all(out["bars"][k] for k in ("spectral", "visibility", "state", "harm"))
    out["gating"] = n >= 15
    return out
