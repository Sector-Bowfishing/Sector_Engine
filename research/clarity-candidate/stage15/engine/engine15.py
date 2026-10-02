"""Stage 15 product layer over the unchanged Stage 14 engine: answer15(m0, m3, sen2cor, sun_elev, platform) ->
the Stage 14 numeric answer plus the Stage 15 state, authority and display (semantics15.json, frozen and hashed)."""
import json, math, os, sys
D = os.path.dirname(os.path.abspath(__file__))
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage14/engine"); sys.path.insert(0, f"{S}/stage15/analysis")
import engine14 as E14
from lib14 import harm, valid, features, state_of
from lib15 import product
SEM = json.load(open(f"{D}/semantics15.json"))
P = {"bands": {k: tuple(v) for k, v in SEM["bands"].items() if v}, "floor": SEM["floor"], "algal": SEM["algal"],
     "tier3_allowed": SEM["tier3_allowed"], "algal_feet": SEM["algal_feet_shown"]}
TB3 = {k: tuple(v) for k, v in E14.P["tier3_bands"].items()}


def answer15(m0, m3, sen2cor, sun_elev, platform):
    a = E14.answer(m0, m3, sen2cor, sun_elev, platform)
    ndci = None
    if a["tier"] in (1, 2):
        refl = harm(dict(m0 if a["tier"] == 1 else m3), platform)
        ndci = features(refl, sun_elev)[0]["F_ndci"]
    st3 = state_of(a["p"], TB3) if a["tier"] == 3 and a["p"] is not None else None
    o = product(a["tier"], a["p"], platform, ndci, P, st3)
    o.update({"p": a["p"], "hard": a["hard"], "feet14": a["feet"], "interval_ft": a["interval_ft"], "ndci": ndci, "state14": a["state"]})
    o["feet_shown"] = (10 ** a["p"]) if (o["display"] in ("exact", "approx") and a["p"] is not None and (a["feet"] is not None or a["tier"] == 3)) else None
    return o
