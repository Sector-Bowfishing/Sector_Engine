"""Practical surface claim: CALM / MODERATE / ROUGH / UNKNOWN (validation prep; no new physics, no wave model).

Predicted (from the existing frozen chop classes, unchanged):  Protected(1) + Ripple(2) -> CALM;  Light chop(3) + Moderate chop(4) -> MODERATE;  Rough(5) -> ROUGH.
UNKNOWN when the geometry cannot support a call: POINT_ONLY tier, bank below resolution, no current wind, or the physical estimate sits on a
class boundary (`confidence == "boundary"` in the bank row: lo/hi chop classes disagree).
Observed (field schema v2 `roughnessObserved`): calm + light -> CALM; choppy -> MODERATE; rough -> ROUGH.
`agreement()` scores a set of (predicted, observed) pairs. It reports numbers only: acceptance lines are for Michael to freeze BEFORE the first session."""
from __future__ import annotations

PRODUCT = ("CALM", "MODERATE", "ROUGH")
_PRED = {1: "CALM", 2: "CALM", 3: "MODERATE", 4: "MODERATE", 5: "ROUGH"}
_OBS = {"calm": "CALM", "light": "CALM", "choppy": "MODERATE", "rough": "ROUGH"}


def predicted_class(chop_class, confidence="firm", tier="AUDITED", below_resolution=False, wind_available=True) -> str:
    if tier == "POINT_ONLY" or below_resolution or not wind_available or chop_class not in _PRED or confidence == "boundary":
        return "UNKNOWN"
    return _PRED[chop_class]


def observed_class(roughness) -> str | None:
    return _OBS.get(roughness)


def agreement(pairs: list[tuple[str, str]]) -> dict:
    """pairs: (predicted, observed). UNKNOWN predictions are counted as coverage loss, never as right or wrong."""
    called = [(p, o) for p, o in pairs if p in PRODUCT and o in PRODUCT]
    n_all, n = len([1 for _, o in pairs if o in PRODUCT]), len(called)
    idx = {c: i for i, c in enumerate(PRODUCT)}
    conf = {p: {o: 0 for o in PRODUCT} for p in PRODUCT}
    for p, o in called:
        conf[p][o] += 1
    exact = sum(p == o for p, o in called)
    within1 = sum(abs(idx[p] - idx[o]) <= 1 for p, o in called)
    under = sum(1 for p, o in called if o == "ROUGH" and p == "CALM")            # the dangerous miss: told calm, it was rough
    obs_rough = sum(1 for _, o in called if o == "ROUGH")
    return {"observations": n_all, "called": n, "unknownShare": round(1 - n / n_all, 3) if n_all else None,
            "exact": round(exact / n, 3) if n else None, "withinOne": round(within1 / n, 3) if n else None,
            "roughCalledCalm": under, "roughObserved": obs_rough, "confusion(pred->obs)": conf}
