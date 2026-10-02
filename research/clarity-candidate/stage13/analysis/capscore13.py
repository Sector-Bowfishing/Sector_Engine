"""Stage 13 section 11: the Stage 12 section 5 rubrics, verbatim, applied to BEST with the section 8 tiers
(capability_rows13.json from coverage13.py). Writes capability13.json."""
import json, math, collections
from common13 import *
import numpy as np
M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]
rows = [r for r in json.load(open(f"{D13}/analysis/capability_rows13.json"))]
out = {"engine": ENG, "rows": len(rows)}
n = len(rows)
out["shares"] = {"unknown": round(sum(r["pred"] == "unknown" for r in rows) / n, 3),
                 "class_only_feet_withheld": round(sum(r["pred"] != "unknown" and not r["feet"] for r in rows) / n, 3),
                 "feet_published": round(sum(r["feet"] for r in rows) / n, 3)}
labs = CLASSES + ["unknown"]
out["confusion"] = {t: {p: sum(1 for r in rows if r["true"] == t and r["pred"] == p) for p in labs} for t in CLASSES}
def rp(c):
    tp = sum(1 for r in rows if r["true"] == c and r["pred"] == c); nt = sum(1 for r in rows if r["true"] == c); npred = sum(1 for r in rows if r["pred"] == c)
    return (tp / nt if nt else None, tp / npred if npred else None, nt)
def feetstats(sub):
    pub = [r for r in sub if r["feet"]]
    if not pub: return {"n_published": 0, "coverage": 0.0}
    lg = [abs(math.log10(r["ft"] / r["secchi"])) for r in pub]; sg = [r["ft"] - r["secchi"] for r in pub]
    return {"n_published": len(pub), "coverage": round(len(pub) / len(sub), 3), "median_abs_log": round(float(np.median(lg)), 3), "median_signed_ft": round(float(np.median(sg)), 2)}
S = lambda v: 1.0 if v == "SUPPORTED" else 0.5 if v == "PARTIAL" else 0.0
feet, klass = {}, {}
for c in CLASSES:
    sub = [r for r in rows if r["true"] == c]
    if not sub:
        feet[c] = {"n_published": 0, "verdict": "NOT"}; klass[c] = {"n": 0, "verdict": "NOT"}; continue
    f = feetstats(sub); feet_v = "NOT"
    if f["n_published"]:
        ms, lg, cov = f["median_signed_ft"], f["median_abs_log"], f["coverage"]
        bars = {"clear": ((-1.5, 1.5), 0.15, (-2.5, 2.5), 0.20), "normal": ((-1.0, 1.0), 0.15, (-1.5, 1.5), 0.20),
                "stained": ((-0.75, 0.75), 0.15, (-1.0, 1.0), 0.20), "limited": ((-0.75, 0.75), 0.20, (-1.0, 1.0), 0.25)}[c]
        if (c != "clear" or f["n_published"] >= 40) and bars[0][0] <= ms <= bars[0][1] and lg <= bars[1] and cov >= 0.70: feet_v = "SUPPORTED"
        elif bars[2][0] <= ms <= bars[2][1] and lg <= bars[3] and cov >= 0.50: feet_v = "PARTIAL"
    feet[c] = {**f, "verdict": feet_v}
    rec, prec, nt = rp(c); unk = sum(1 for r in sub if r["pred"] == "unknown") / len(sub)
    if c == "clear": v = "SUPPORTED" if rec >= 0.60 and prec >= 0.75 and unk <= 0.30 else "PARTIAL" if rec >= 0.40 and prec >= 0.60 else "NOT"
    elif c == "normal": v = "SUPPORTED" if rec >= 0.60 and prec >= 0.60 else "PARTIAL" if rec >= 0.50 and prec >= 0.40 else "NOT"
    elif c == "stained": v = "SUPPORTED" if rec >= 0.60 and prec >= 0.60 else "PARTIAL" if rec >= 0.40 and prec >= 0.40 else "NOT"
    else:
        called_clear = sum(1 for r in sub if r["pred"] == "clear") / len(sub)
        lt3 = sum(1 for r in sub if r["pred"] in ("stained", "limited", "unknown")) / len(sub)
        ge4 = sum(1 for r in sub if r["ft"] is not None and r["ft"] >= 4) / len(sub)
        v = "SUPPORTED" if rec >= 0.60 and prec >= 0.50 and called_clear <= 0.10 else "PARTIAL" if lt3 >= 0.60 and ge4 <= 0.10 else "NOT"
    klass[c] = {"n": nt, "recall": round(rec, 3), "precision": round(prec, 3) if prec is not None else None, "unknown": round(unk, 3), "verdict": v}
for t, key in (("algae", ("algal", "mixed")), ("sediment", ("sediment",))):
    sub = [r for r in rows if r["insitu_type"] in key]
    if not sub:
        feet[t] = {"n": 0, "verdict": "NOT"}; klass[t] = {"n": 0, "verdict": "NOT"}; continue
    f = feetstats(sub); fv = "NOT"
    if f["n_published"]:
        if abs(f["median_signed_ft"]) <= 1.0 and f["median_abs_log"] <= 0.15 and f["coverage"] >= 0.70: fv = "SUPPORTED"
        elif abs(f["median_signed_ft"]) <= 1.5 and f["median_abs_log"] <= 0.20 and f["coverage"] >= 0.50: fv = "PARTIAL"
    feet[t] = {**f, "n": len(sub), "verdict": fv}
    acc = float(np.mean([r["true"] == r["pred"] for r in sub])); const = max(collections.Counter(r["true"] for r in sub).values()) / len(sub)
    ms = float(np.median([r["ft"] - r["secchi"] for r in sub if r["ft"] is not None])) if any(r["ft"] is not None for r in sub) else None
    if t == "algae":
        v = "SUPPORTED" if acc >= const + 0.10 and ms is not None and abs(ms) <= 1.0 else "PARTIAL" if acc >= const + 0.05 else "NOT"
        klass[t] = {"n": len(sub), "class_acc": round(acc, 3), "constant": round(const, 3), "median_signed_ft": ms, "verdict": v}
    else:
        bright = [r for r in sub if (r["turb"] or 0) >= 20]
        bc = sum(1 for r in bright if r["pred"] == "clear") / len(bright) if bright else None
        v = "SUPPORTED" if bc is not None and bc <= 0.05 and acc >= const + 0.10 else "PARTIAL" if bc is not None and bc <= 0.15 else "NOT"
        klass[t] = {"n": len(sub), "class_acc": round(acc, 3), "constant": round(const, 3), "bright_called_clear": bc, "bright_n": len(bright), "verdict": v}
feet["bottom-risk"] = {"verdict": "NOT"}; klass["bottom-risk"] = {"verdict": "NOT"}
out["exact_feet"] = feet; out["clarity_class"] = klass
for name, d in (("EXACT_FEET_CAPABILITY", feet), ("CLARITY_CLASS_CAPABILITY", klass)):
    tot = sum(S(v["verdict"]) for v in d.values()); out[name] = {"points_of_7": tot, "score_of_10": int(round(tot / 7 * 10 + 1e-9))}
json.dump(out, open(f"{D13}/analysis/capability13.json", "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in ("engine", "shares", "EXACT_FEET_CAPABILITY", "CLARITY_CLASS_CAPABILITY")}, indent=1))
for c in feet: print(c, feet[c].get("verdict"), klass[c].get("verdict"), feet[c], klass[c])
