"""Stage 16 product: the unchanged Stage 14 engine + the frozen reliability gate (rule16.json) + the unchanged Stage 15
tier-3, algal-modifier and S2C rules. answer16(m0, m3, sen2cor, sun_elev, platform) -> state, authority, display, evidence."""
import json, math, os, sys
D = os.path.dirname(os.path.abspath(__file__))
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage14/engine"); sys.path.insert(0, f"{S}/stage16/analysis")
import engine14 as E14
from lib14 import harm, features, state_of
from lib16 import product16, evidence
RULE = json.load(open(f"{D}/rule16.json"))
R = {"post1": {int(b): tuple(v) for b, v in RULE["post1"].items()}, "post2": {int(b): tuple(v) for b, v in RULE["post2"].items()},
     "t1": RULE["t1"], "t2": RULE["t2"], "t2opt": RULE["t2opt"], "tier3_allowed": RULE["tier3_allowed"]}
TB3 = {k: tuple(v) for k, v in E14.P["tier3_bands"].items()}


def answer16(m0, m3, sen2cor, sun_elev, platform):
    a = E14.answer(m0, m3, sen2cor, sun_elev, platform)
    ndci = None
    if a["tier"] in (1, 2):
        ndci = features(harm(dict(m0 if a["tier"] == 1 else m3), platform), sun_elev)[0]["F_ndci"]
    st3 = state_of(a["p"], TB3) if a["tier"] == 3 and a["p"] is not None else None
    o = product16(a["tier"], a["p"], platform, ndci, st3, R)
    o.update({"p": a["p"], "hard": a["hard"], "ndci": ndci, "interval_ft": a["interval_ft"], "evidence": evidence(o)})
    o["feet_shown"] = (10 ** a["p"]) if (o["display"] in ("exact", "approx") and a["p"] is not None) else None
    return o
