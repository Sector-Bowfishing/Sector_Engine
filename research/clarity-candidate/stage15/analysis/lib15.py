"""Stage 15 display/authority layer and operational rubric (PREREGISTRATION_STAGE15.md sections 2-6). The numeric
prediction p is never changed; this only decides the state, authority and what is displayed."""
import math, sys
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage14/analysis")
from lib14 import hard_std, CLASSES, HARD_STATE, L6, L3, L2, logit_fit, bands_from
CONTAINS = {"Clear": {0}, "Clear-to-Normal": {0, 1}, "Normal": {1}, "Normal-to-Stained": {1, 2}, "Stained": {2}, "Stained-to-Limited": {2, 3}, "Limited": {3}}
BOUNDS = {"6ft": L6, "3ft": L3, "2ft": L2}
NAME = {"6ft": "Clear-to-Normal", "3ft": "Normal-to-Stained", "2ft": "Stained-to-Limited"}


def band6_from(pairs, floor=0.05, win=0.30):
    """The Stage 14 2:1-odds method at the 6 ft boundary."""
    sel = [(p - L6, 1.0 if y >= L6 else 0.0) for p, y in pairs if abs(p - L6) <= win]
    a, be = logit_fit([s[0] for s in sel], [s[1] for s in sel]) if len(sel) >= 20 else (0.0, float("inf"))
    dlo, dhi = ((-math.log(2) - a) / be, (math.log(2) - a) / be) if math.isfinite(be) and be > 0 else (-floor, floor)
    dlo, dhi = min(dlo, -floor), max(dhi, floor)
    return (L6 + dlo, L6 + dhi), {"alpha": a, "beta": be, "n": len(sel), "d_lo": dlo, "d_hi": dhi}


def base_state(p, bands):
    """bands: {name: (lo, hi)} for the boundaries in use; nearer boundary wins on overlap; else the hard class."""
    hits = [k for k, (lo, hi) in bands.items() if lo <= p <= hi]
    if hits: return NAME[min(hits, key=lambda k: abs(p - BOUNDS[k]))]
    return HARD_STATE[hard_std(p)]


def soften(state, p, bands):
    if len(CONTAINS[state]) == 2: return state
    if state == "Clear": return "Clear-to-Normal" if "6ft" in bands else "Clear"
    if state == "Limited": return "Stained-to-Limited"
    opts = ["6ft", "3ft"] if state == "Normal" else ["3ft", "2ft"]
    opts = [o for o in opts if o in bands] or ["3ft"]
    return NAME[min(opts, key=lambda k: abs(p - BOUNDS[k]))]


def product(tier, p, platform, ndci, P, st3=None):
    """P: semantics parameters {bands, floor: {T, D} | None, algal: {moderate, strong}: behaviour, s2c_lower, tier3_allowed}.
    Returns state, authority (full / lower / none), display (exact / approx / floor / state-only / none), floor_D, withheld."""
    o = {"tier": tier, "state": "Unknown / Low Authority", "authority": "none", "display": "none", "floor_D": None, "withheld": None, "algal": None, "s2c": platform == "sentinel-2c"}
    if tier == 0 or p is None: return o
    fl = P.get("floor")
    if tier == 3:
        if st3 in P["tier3_allowed"]:
            o.update(state=st3, authority="lower", display="approx")
            if fl and p >= math.log10(fl["T"]): o.update(display="floor", floor_D=fl["D"])
            if o["s2c"] and o["display"] == "approx": o["display"] = "state-only"
        else:
            o["withheld"] = st3
        return o
    st = base_state(p, P["bands"]); o.update(state=st, authority="full", display="exact")
    if fl and p >= math.log10(fl["T"]): o.update(state="Clear", display="floor", floor_D=fl["D"])
    lvl = None if ndci is None or ndci <= 0.03 else ("strong" if ndci > 0.10 else "moderate")
    if lvl:
        beh = P["algal"][lvl]; o["algal"] = f"{lvl}:{beh}"
        if beh == "modifier":
            if o["display"] == "exact": o["display"] = "approx"
        elif beh == "soften":
            ns = soften(o["state"], p, P["bands"])
            o.update(state=ns, authority="lower"); o["display"] = "approx" if (ns != "Clear" or o["display"] != "floor") else "floor"
            if ns != "Clear": o["floor_D"] = None
        elif beh == "withhold":
            o.update(withheld=o["state"], state="Unknown / Low Authority", authority="none", display="approx" if P.get("algal_feet") else "none", floor_D=None)
    if o["s2c"] and o["authority"] in ("full", "lower"):
        o["authority"] = "lower"
        if o["display"] in ("exact", "approx"): o["display"] = "state-only"
    return o


def op_score(o, c, ft):
    """Section 6. c: true class index; ft: true Secchi ft. Returns (score, outcome, harmful, severe)."""
    st = o["state"]
    if st not in CONTAINS:      # Unknown
        w = o.get("withheld")
        if w in CONTAINS and c in CONTAINS[w]: return 0.25, "unknown_missed_right", False, False
        return 0.5, "unknown_appropriate", False, False
    hit = c in CONTAINS[st]; dist = min(abs(c - k) for k in CONTAINS[st])
    if o["display"] == "floor" and o["authority"] == "full":
        if ft >= o["floor_D"]: return 1.0, "floor_correct", False, False
        if ft >= 6: return 0.75, "floor_clear_below", False, False
        return 0.0, "harmful", True, dist >= 2
    if o["authority"] == "lower":
        if o["display"] == "floor" and hit: return (0.75, "lower_correct", False, False)
        return (0.75, "lower_correct", False, False) if hit else (0.25, "lower_wrong", False, False)
    if hit: return (1.0, "correct_single", False, False) if len(CONTAINS[st]) == 1 else (0.9, "correct_boundary", False, False)
    return 0.0, "harmful", True, dist >= 2


def op_summary(rows):
    """rows: dicts with c, score, outcome, harmful, severe."""
    import numpy as np, collections
    per = {}
    for k, n in enumerate(CLASSES):
        sub = [r for r in rows if r["c"] == k]
        per[n] = {"n": len(sub), "mean": float(np.mean([r["score"] for r in sub])) if sub else None, "outcomes": dict(collections.Counter(r["outcome"] for r in sub))}
    bal = float(np.mean([v["mean"] for v in per.values() if v["mean"] is not None]))
    return {"per_class": per, "balanced": bal, "score_of_10": int(round(10 * bal + 1e-9)), "overall_mean": float(np.mean([r["score"] for r in rows])),
            "harmful_rate": float(np.mean([r["harmful"] for r in rows])), "severe_rate": float(np.mean([r["severe"] for r in rows])),
            "outcomes": dict(collections.Counter(r["outcome"] for r in rows)), "n": len(rows)}
