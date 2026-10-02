"""Stage 14 library (PREREGISTRATION_STAGE14.md sections 2-3, 6, 8). Development rows exactly as Stage 13 coverage13.py
builds them; bands, product states, decision-quality metrics, rubrics."""
import json, math, glob, collections, sys
import numpy as np
from scipy.optimize import minimize
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage13/analysis")
from common13 import *            # features, t_red, t_switch, class_metrics, lake_boot_diff, region, fold, cls, cname, CLASSES
import models13_lib as L
L3, L2, L6 = math.log10(3), math.log10(2), math.log10(6)
STATES = ["Clear", "Normal", "Normal-to-Stained", "Stained", "Stained-to-Limited", "Limited"]
CONTAINS = {"Clear": {0}, "Normal": {1}, "Normal-to-Stained": {1, 2}, "Stained": {2}, "Stained-to-Limited": {2, 3}, "Limited": {3}}
HARD_STATE = {0: "Clear", 1: "Normal", 2: "Stained", 3: "Limited"}
VR = json.load(open(f"{S}/stage12/harm/score_tandem.json"))["production_vrhow_coef"]


def harm(p, platform):
    if platform != "sentinel-2c": return p
    q = dict(p)
    for b, c in VR.items():
        if isinstance(p.get(b), (int, float)):
            v = c["g"] * p[b] + c["o"]
            if b == "B05": v += c["k"] * (p.get("B06", 0) - p.get("B04", 0))
            q[b] = v
    return q


def valid(p): return bool(p) and p.get("n", 0) >= 5 and not p.get("rejected") and all(isinstance(p.get(b), (int, float)) and math.isfinite(p[b]) for b in ("B02", "B03", "B04", "B05"))


def prep(x, a):
    y = dict(x); y["aco"] = a; y["F"], y["q"] = features(a, x["sun_elev"])
    if x.get("secchi"): y["y"] = math.log10(x["secchi"]); y["c"] = cls(x["secchi"])
    return y


def c3s(x):
    s = x["sen2cor"]; red, re1 = max(s["red"], 0.001), max(s["re1"], 0.001); lr = math.log10(red); a = 1.0 if (re1 - red) / (re1 + red) > 0 else 0.0
    return [1 - a, (1 - a) * lr, a, a * lr]


def dev_rows():
    """Stage 13 development rows: tier1 (E13), tier2 (M3 where tier 1 has no disk), rest (tier 3 candidates)."""
    rows12 = {x["id"]: x for x in json.load(open(f"{S}/stage12/analysis/rows12.json"))}
    ALL = [x for x in rows12.values() if x["processed"] and not x["gunt"] and x["secchi"] and x["secchi"] > 0]
    T2 = {}
    for f_ in glob.glob(f"{S}/stage13/coverage/res/*.json"):
        for c in json.load(open(f_)).get("crops", []):
            for pid, p in (c.get("points") or {}).items(): T2[pid] = p
    t1 = [prep(x, x["aco"]) for x in ALL if x["aco_valid"]]
    t2 = [prep(x, harm(T2[x["id"]]["M3"], x["platform"])) for x in ALL if not x["aco_valid"] and valid((T2.get(x["id"]) or {}).get("M3"))]
    ids = {x["id"] for x in t1} | {x["id"] for x in t2}
    rest = [x for x in ALL if x["id"] not in ids]
    for x in t1: x["tier"] = 1
    for x in t2: x["tier"] = 2
    for x in rest: x["tier"] = 3
    return ALL, t1, t2, rest


# ---------------- fits
def fit_gbm(tr): return L.gbm().fit(np.array([L.f7(x) for x in tr]), np.array([x["y"] for x in tr]))
def pred_gbm(g, te): return [float(v) for v in g.predict(np.array([L.f7(x) for x in te]))] if te else []
def fit_lin(tr): return L.ols([L.f6(x) for x in tr], [x["y"] for x in tr])
def pred_lin(b, te): return [float(np.dot(b, L.f6(x))) for x in te]
def fit_c3s(tr): return np.linalg.lstsq(np.array([c3s(x) for x in tr]), np.array([math.log10(x["secchi"]) for x in tr]), rcond=None)[0]
def pred_c3s(b, te): return [float(np.dot(b, c3s(x))) for x in te]


# ---------------- section 2 bands
def logit_fit(d, z):
    d, z = np.asarray(d, float), np.asarray(z, float)
    def nll(t):
        e = t[0] + t[1] * d; return float(np.sum(np.logaddexp(0, e) - z * e))
    r = minimize(nll, [0.0, 10.0], method="BFGS"); return float(r.x[0]), float(r.x[1])


def bands_from(pairs, floor=0.05, win=0.30):
    """pairs: [(p, y)] log10 ft. Returns {b: (lo, hi)} absolute log10 edges for b in (3 ft, 2 ft), plus the fit."""
    out, fit = {}, {}
    for name, b in (("3ft", L3), ("2ft", L2)):
        sel = [(p - b, 1.0 if y >= b else 0.0) for p, y in pairs if abs(p - b) <= win]
        a, be = logit_fit([s[0] for s in sel], [s[1] for s in sel]) if len(sel) >= 20 else (0.0, float("inf"))
        if not math.isfinite(be) or be <= 0:
            dlo, dhi = -floor, floor
        else:
            dlo, dhi = (-math.log(2) - a) / be, (math.log(2) - a) / be
        dlo, dhi = min(dlo, -floor), max(dhi, floor)          # floors: >= 0.05 each side, band contains b
        out[name] = (b + dlo, b + dhi); fit[name] = {"alpha": a, "beta": be, "n": len(sel), "d_lo": dlo, "d_hi": dhi}
    return out, fit


def hard_std(p): return 0 if p >= L6 else 1 if p >= L3 else 2 if p >= L2 else 3


def state_of(p, bands, hard=hard_std):
    in3 = bands["3ft"][0] <= p <= bands["3ft"][1]; in2 = bands["2ft"][0] <= p <= bands["2ft"][1]
    if in3 and in2: return "Normal-to-Stained" if abs(p - L3) <= abs(p - L2) else "Stained-to-Limited"
    if in3: return "Normal-to-Stained"
    if in2: return "Stained-to-Limited"
    return HARD_STATE[hard(p)]


# ---------------- section 3 decision quality
def decision(true, states):
    """true: class idx list; states: state names or None (no answer at ACOLITE authority)."""
    out = {}
    for c, name in enumerate(CLASSES):
        rows = [(t, s) for t, s in zip(true, states) if t == c]; ans = [(t, s) for t, s in rows if s]
        cor = sum(1 for t, s in ans if t in CONTAINS[s])
        inc = [(t, s) for t, s in zip(true, states) if s and c in CONTAINS[s]]
        out[name] = {"n": len(rows), "answered": len(ans), "authority_share": len(ans) / len(rows) if rows else None,
                     "decision_recall": cor / len(ans) if ans else None,
                     "decision_precision": sum(1 for t, s in inc if t in CONTAINS[s]) / len(inc) if inc else None, "n_states_including": len(inc),
                     "single_class_share": sum(1 for t, s in ans if len(CONTAINS[s]) == 1) / len(ans) if ans else None}
    ans = [(t, s) for t, s in zip(true, states) if s]
    out["balanced"] = float(np.mean([out[n]["decision_recall"] for n in CLASSES if out[n]["decision_recall"] is not None]))
    out["specificity"] = sum(1 for t, s in ans if len(CONTAINS[s]) == 1) / len(ans) if ans else None
    out["answered"] = len(ans) / len(true) if true else None
    out["by_state"] = {st: {"n": sum(1 for t, s in ans if s == st), "precision": (sum(1 for t, s in ans if s == st and t in CONTAINS[s]) / max(1, sum(1 for t, s in ans if s == st)))}
                       for st in STATES}
    return out


def bal_decision(rows, key="state"):
    d = decision([r["c"] for r in rows], [r[key] for r in rows]); return d["balanced"]


# ---------------- section 8 product rubric
def product_rubric(recs):
    """recs: dicts with c (true idx), state (ACOLITE-authority state or None), ft (displayed feet or None), secchi, insitu_type, turb."""
    caps = {}
    d = decision([r["c"] for r in recs], [r["state"] for r in recs])
    for c, name in enumerate(CLASSES):
        x = d[name]; rec_, pre, sh = x["decision_recall"], x["decision_precision"], x["authority_share"]
        if rec_ is None or pre is None: v = "NOT"
        elif rec_ >= 0.75 and pre >= 0.75 and sh >= 0.70: v = "SUPPORTED"
        elif rec_ >= 0.60 and pre >= 0.60 and sh >= 0.50: v = "PARTIAL"
        else: v = "NOT"
        caps[name] = {**{k: x[k] for k in ("n", "decision_recall", "decision_precision", "authority_share", "single_class_share")}, "verdict": v}
    for t, key in (("algae", ("algal", "mixed")), ("sediment", ("sediment",))):
        sub = [r for r in recs if r["insitu_type"] in key and r["state"]]
        if not sub: caps[t] = {"n": 0, "verdict": "NOT"}; continue
        acc = float(np.mean([r["c"] in CONTAINS[r["state"]] for r in sub]))
        const = max(float(np.mean([r["c"] in CONTAINS[st] for r in sub])) for st in STATES)
        fts = [r["ft"] - r["secchi"] for r in sub if r["ft"] is not None]; ms = float(np.median(fts)) if fts else None
        if t == "algae":
            v = "SUPPORTED" if acc >= const + 0.10 and ms is not None and abs(ms) <= 1.0 else "PARTIAL" if acc >= const + 0.05 else "NOT"
            caps[t] = {"n": len(sub), "decision_acc": acc, "constant": const, "median_signed_ft": ms, "verdict": v}
        else:
            bright = [r for r in sub if (r["turb"] or 0) >= 20]; bc = sum(1 for r in bright if r["state"] == "Clear") / len(bright) if bright else None
            v = "SUPPORTED" if bc is not None and bc <= 0.05 and acc >= const + 0.10 else "PARTIAL" if bc is not None and bc <= 0.15 else "NOT"
            caps[t] = {"n": len(sub), "decision_acc": acc, "constant": const, "bright_called_clear": bc, "bright_n": len(bright), "verdict": v}
    caps["bottom-risk"] = {"verdict": "NOT"}
    pts = sum(1.0 if v["verdict"] == "SUPPORTED" else 0.5 if v["verdict"] == "PARTIAL" else 0 for v in caps.values())
    return caps, {"points_of_7": pts, "score_of_10": int(round(pts / 7 * 10 + 1e-9))}


BAR = {"clear": 1.5, "normal": 1.0, "stained": 0.75, "limited": 0.75}
def authorise(pairs_by_class):
    """Stage 12 rule: {class idx: [(p, y, secchi)]} -> authorised class names."""
    ok = []
    for c, name in enumerate(CLASSES):
        sub = pairs_by_class.get(c, [])
        if len(sub) < 10: continue
        if np.median([abs(p - y) for p, y, s in sub]) <= 0.15 and abs(np.median([10 ** p - s for p, y, s in sub])) <= BAR[name]: ok.append(name)
    return ok
