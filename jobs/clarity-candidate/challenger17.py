"""The frozen Stage 17 challenger for live use: inverse-uncertainty weighting of frozen scene predictions over +-10 days,
no rain rule, Sentinel-2C off (research/clarity-candidate/stage18/engine/challenger17.json).

A line-for-line port of build() in research/clarity-candidate/stage17/analysis/dev17.py for the frozen variant
(M-iuw, W = 10, H0, S-off). `check_fixtures()` runs it on golden/challenger17_fixtures.json, the frozen dev17 code's own
outputs on every development event, and must match all of them exactly before the job writes anything.

Live windows are one-sided: at a pass, only that pass and earlier ones exist. The research windows were two-sided around
an observation date; every scene is stored, so a two-sided answer can be rebuilt later for scoring."""
import json, os
import numpy as np

ROOT = os.environ["CLARITY_RESEARCH_ROOT"]
from lib16 import gate, CONTAINS   # noqa: E402  (research path set by the caller)

WINDOW_DAYS = 10
MAX_NEIGHBOURS = 3


class Challenger:
    def __init__(self):
        CH = json.load(open(f"{ROOT}/stage18/engine/challenger17.json"))
        R16 = json.load(open(f"{ROOT}/stage16/engine/rule16.json"))
        self.sig = {int(k): v for k, v in CH["sigma_tier"].items()}
        self.kappa = CH["kappa_per_day"]
        self.post1 = {int(b): tuple(v) for b, v in R16["post1"].items()}
        self.post2 = {int(b): tuple(v) for b, v in R16["post2"].items()}
        self.cal = {"n2": {int(b): tuple(v) for b, v in CH["posteriors_n2"].items()},
                    "n3": {int(b): tuple(v) for b, v in CH["posteriors_n3"].items()}}
        self.t1, self.t2 = R16["t1"], R16["t2"]

    def scene_state(self, s):
        P = self.post2 if s["tier"] == 2 else self.post1
        return gate(s["p"], P, self.t1, self.t2, boundary_only=(s["tier"] == 2))[0]

    def build(self, scenes, base):
        """scenes: [{p, tier (1|2), platform, adt (|days| to the target date), anchor}] inside the window, anchor first, then
        neighbours nearest first. base: the Stage 16 product, returned when no full-authority scene contributes."""
        full = [s for s in scenes if s["platform"] != "sentinel-2c"]
        if not full:
            return dict(base, n_full=0, agree=0, consensus=False)
        use = list(full)
        v = np.array([self.sig[s["tier"]] ** 2 + self.kappa * s["adt"] for s in use]); p = np.array([s["p"] for s in use]); w = 1 / v
        pc = float(np.sum(w * p) / np.sum(w))
        n = len(use); allt2 = all(s["tier"] == 2 for s in use)
        if n == 1:
            Pp = self.post2 if allt2 else self.post1
        else:
            Pp = self.cal["n2" if n == 2 else "n3"]
        st, conf, wh = gate(pc, Pp, self.t1, self.t2, boundary_only=allt2)
        o = {"tier": 1 if not allt2 else 2, "state": st or "Unknown / Low Authority", "authority": "full" if st else "none",
             "display": "exact" if st else "none", "floor_D": None, "withheld": None if st else wh, "algal": None, "s2c": False,
             "conf": conf, "p": pc}
        states = [self.scene_state(s) for s in use]
        agree = sum(1 for x in states if st and x and CONTAINS[x] >= CONTAINS[st])
        disjoint = any(st and x and not (CONTAINS[x] & CONTAINS[st]) for x in states)
        o.update(n_full=len(full), n_use=n, agree=agree, disjoint=disjoint, consensus=True, s2c_used=len(use) - len(full))
        o["sigma_log10"] = float(np.sqrt(1 / np.sum(w)))      # the weighted mean's standard error (not part of the frozen rule)
        return o

    @staticmethod
    def evidence(o):
        if o["state"] not in CONTAINS: return "unavailable"
        if o["authority"] == "lower": return "weak"
        strong = (o["authority"] == "full" and (o.get("conf") or 0) >= 0.90 and o.get("agree", 0) >= 2 and not o.get("disjoint", False))
        return "strong" if strong else "moderate"


def select_neighbours(anchor, history):
    """Stage 17 section 2, one-sided: earlier passes of the same point with a valid production-gated Sen2Cor disk
    (n_valid >= 5), not the anchor item, within WINDOW_DAYS; nearest |dt| then lowest scene cloud; unique items; <= 3."""
    out, seen = [], set()
    cands = [h for h in history if h["item"] != anchor["item"] and (h.get("n_valid") or 0) >= 5 and not h.get("readout_error")
             and 0 <= anchor["day"] - h["day"] <= WINDOW_DAYS]
    for h in sorted(cands, key=lambda h: (anchor["day"] - h["day"], h["scene_cloud"] if h.get("scene_cloud") is not None else 100.0)):
        if h["item"] in seen: continue
        seen.add(h["item"]); out.append(h)
        if len(out) == MAX_NEIGHBOURS: break
    return out


def scene_list(anchor, neighbours):
    """Contributing scenes in dev17's order: the anchor (tier 1-2 only), then neighbours (tier 1-2 with a sun elevation)."""
    sc = []
    if anchor.get("tier") in (1, 2) and anchor.get("p") is not None:
        sc.append({"p": anchor["p"], "tier": anchor["tier"], "platform": anchor["platform"], "adt": 0, "anchor": True})
    for n in neighbours:
        if n.get("tier") in (1, 2) and n.get("p") is not None and n.get("sun_elev") is not None:
            sc.append({"p": n["p"], "tier": n["tier"], "platform": n["platform"], "adt": abs(anchor["day"] - n["day"]), "anchor": False})
    return sc


def check_fixtures(ch=None):
    ch = ch or Challenger()
    F = json.load(open(f"{ROOT}/golden/challenger17_fixtures.json"))["fixtures"]
    bad = 0
    for f in F:
        o = ch.build(f["scenes"], f["base"]); o.pop("sigma_log10", None)
        if json.loads(json.dumps(o, default=str)) != f["out"] or ch.evidence(o) != f["evidence"]: bad += 1
    return {"events": len(F), "mismatched": bad, "pass": bad == 0 and len(F) > 1000}
