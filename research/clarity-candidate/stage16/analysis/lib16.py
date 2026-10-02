"""Stage 16 reliability gate (PREREGISTRATION_STAGE16.md sections 2-3, 5C). Posterior class probabilities from three
monotone boundary logistics; single state only when its posterior >= tau1; adjacent pair when >= tau2; else Unknown."""
import math, sys
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage14/analysis"); sys.path.insert(0, f"{S}/stage15/analysis")
from lib14 import hard_std, logit_fit, CLASSES
from lib15 import CONTAINS, op_score, op_summary
LB = {6: math.log10(6), 3: math.log10(3), 2: math.log10(2)}
SINGLE = ["Clear", "Normal", "Stained", "Limited"]
PAIR = {(0, 1): "Clear-to-Normal", (1, 2): "Normal-to-Stained", (2, 3): "Stained-to-Limited"}
sig = lambda z: 1 / (1 + math.exp(-max(-60, min(60, z))))


def fit_post(pairs):
    """pairs [(p, y)] -> {b: (alpha, beta)} fitted on all rows."""
    out = {}
    for b, lb in LB.items():
        a, be = logit_fit([p - lb for p, y in pairs], [1.0 if y >= lb else 0.0 for p, y in pairs])
        out[b] = (a, be)
    return out


def posterior(p, P):
    p6 = sig(P[6][0] + P[6][1] * (p - LB[6])); p3 = max(sig(P[3][0] + P[3][1] * (p - LB[3])), p6); p2 = max(sig(P[2][0] + P[2][1] * (p - LB[2])), p3)
    return [p6, p3 - p6, p2 - p3, 1 - p2]


def gate(p, P, t1, t2, boundary_only=False):
    """-> (state or None, issued posterior, withheld state)."""
    pi = posterior(p, P); hc = hard_std(p)
    best = max(range(4), key=lambda c: pi[c])
    pairs = {k: pi[k[0]] + pi[k[1]] for k in PAIR}
    bp = max(pairs, key=pairs.get)
    if not boundary_only and pi[best] >= t1:
        st, conf = SINGLE[best], pi[best]
    elif pairs[bp] >= t2:
        st, conf = PAIR[bp], pairs[bp]
    else:
        return None, None, PAIR[bp] if pairs[bp] >= pi[best] else SINGLE[best]
    if hc not in CONTAINS[st]:                       # consistency with the displayed feet
        k = tuple(sorted({hc, list(CONTAINS[st])[0] if len(CONTAINS[st]) == 1 else min(CONTAINS[st], key=lambda c: abs(c - hc))}))
        if k in PAIR: st, conf = PAIR[k], pi[k[0]] + pi[k[1]]
        else: return None, None, st
    return st, conf, None


def product16(tier, p, platform, ndci, st3, R):
    """R: {post1, post2, t1, t2, t2opt, tier3_allowed}. Stage 15 tier 3, algal modifier and S2C rules unchanged."""
    o = {"tier": tier, "state": "Unknown / Low Authority", "authority": "none", "display": "none", "floor_D": None, "withheld": None,
         "algal": None, "s2c": platform == "sentinel-2c", "conf": None}
    if tier == 0 or p is None: return o
    if tier == 3:
        if st3 in R["tier3_allowed"]: o.update(state=st3, authority="lower", display="approx" if platform != "sentinel-2c" else "state-only")
        else: o["withheld"] = st3
        return o
    opt = R["t2opt"] if tier == 2 else "T1"
    P = R["post2"] if opt in ("T2-B", "T2-D") else R["post1"]
    st, conf, w = gate(p, P, R["t1"], R["t2"], boundary_only=(opt == "T2-D"))
    if st is None: o["withheld"] = w; return o
    o.update(state=st, conf=conf, authority="lower" if opt == "T2-C" else "full", display="exact")
    if ndci is not None and ndci > 0.03: o["algal"] = "modifier"; o["display"] = "approx"
    if o["s2c"]: o["authority"] = "lower"; o["display"] = "state-only"
    return o


def evidence(o):
    """Section 5C."""
    if o["state"] not in CONTAINS: return "unavailable"
    if o["authority"] == "lower": return "weak"
    if o["tier"] == 1 and not o["s2c"] and not o["algal"] and (o["conf"] or 0) >= 0.90: return "strong"
    return "moderate"
