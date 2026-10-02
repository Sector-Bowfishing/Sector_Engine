"""Stage 14 frozen production candidate (PREREGISTRATION_STAGE14.md sections 1, 2, 6): C-gbm single continuous engine.
answer(m0, m3, sen2cor, sun_elev, platform) -> tier, prediction, exact feet (when authorised), two-thirds interval,
product state, hard class, authority. Parameters in frozen_engine.json + frozen_gbm.pkl (both hashed in the freeze)."""
import json, math, os, pickle, sys
import numpy as np
D = os.path.dirname(os.path.abspath(__file__))
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage14/analysis")
from lib14 import harm, valid, features, state_of, hard_std, CLASSES, HARD_STATE, CONTAINS, c3s
import models13_lib as L
P = json.load(open(f"{D}/frozen_engine.json"))
G = pickle.load(open(f"{D}/frozen_gbm.pkl", "rb"))
BANDS = {k: tuple(v) for k, v in P["bands"].items()}
B3 = np.array(P["tier3_c3s_coef"])


def answer(m0, m3, sen2cor, sun_elev, platform):
    for tier, a in ((1, m0), (2, m3)):
        if valid(a):
            a = harm({k: v for k, v in a.items()}, platform)
            F, q = features(a, sun_elev)
            p = float(G.predict(np.array([[F[k] for k in L.FEATS6 + ["F_kd"]]]))[0])
            hc = hard_std(p); st = state_of(p, BANDS)
            feet = 10 ** p if CLASSES[hc] in P["feet_authorised"] else None
            return {"tier": tier, "authority": "ACOLITE", "p": p, "hard": hc, "state": st, "feet": feet,
                    "interval_ft": [10 ** (p + P["interval_q"][0]), 10 ** (p + P["interval_q"][1])]}
    if sen2cor and all(isinstance(sen2cor.get(k), (int, float)) for k in ("red", "re1")):
        p = float(np.dot(B3, c3s({"sen2cor": sen2cor}))); st = state_of(p, {k: tuple(v) for k, v in P["tier3_bands"].items()})
        if st in P["tier3_allowed_states"]:
            hc = list(CONTAINS[st])[0] if len(CONTAINS[st]) == 1 else None
            feet = 10 ** p if hc is not None and CLASSES[hc] in P["tier3_feet_for"] else None
            return {"tier": 3, "authority": "low", "p": p, "hard": hard_std(p), "state": st, "feet": feet, "interval_ft": None}
        return {"tier": 3, "authority": "low", "p": p, "hard": hard_std(p), "state": "Unknown / Low Authority", "feet": None, "interval_ft": None}
    return {"tier": 0, "authority": None, "p": None, "hard": None, "state": "Unknown / Low Authority", "feet": None, "interval_ft": None}
