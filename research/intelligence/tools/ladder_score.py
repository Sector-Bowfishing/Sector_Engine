"""Score the facts against the pre-registered rubric. Stdlib only. Run: python3 -I ladder_score.py"""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(here, "..", "data", "decision_readiness_rubric_r1.json")))
FACTS = json.load(open(os.path.join(here, "..", "data", "decision_readiness_facts.json")))
W = {d["id"]: d["weight"] for d in R["dimensions"]}
assert sum(W.values()) == 100


def score(scores):
    s = {k: v[0] for k, v in scores.items()}
    assert set(s) == set(W), set(W) ^ set(s)
    unc = sum(s[k] * W[k] for k in W) / 100
    caps = []
    if s["validation"] < 5: caps.append(("validation<5", 5.0))
    elif s["validation"] < 8: caps.append(("validation<8", 7.0))
    if s["confidence"] < 5: caps.append(("noConfidencePropagation", 6.0))
    cap = min([c for _, c in caps], default=10.0)
    return round(unc, 1), round(min(unc, cap), 1), caps, s


out = {}
for name, f in FACTS.items():
    unc, val, caps, s = score(f["scores"])
    out[name] = {"label": f["label"], "uncapped": unc, "value": val, "caps": caps, "dims": s}
    print(f"{name:28s} uncapped {unc:4.1f}  displayed {val:4.1f}  caps {[c[0] for c in caps]}")
    print("   " + "  ".join(f"{k}={s[k]}" for k in W))
json.dump(out, open(os.path.join(here, "..", "data", "decision_readiness_scores.json"), "w"), indent=1)
