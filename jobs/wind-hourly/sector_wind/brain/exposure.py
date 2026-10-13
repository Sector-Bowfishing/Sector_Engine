"""Bank-impact vocabulary: DIRECT / CROSS / PROTECTED (+ HIGH FETCH tag). Geometry + frozen-CEM chop class only.

Convention (verified by tests; docs/wind-research/WIND_BANK_EXPOSURE_RESEARCH.md):
  * Wind direction is the bearing the wind blows FROM (270 = west wind).
  * Fetch looks INTO the wind: from the bank toward the FROM bearing over open water to the first land.
  * A bank FACES the bearing from the bank toward its adjacent water (anchor -> standoff). A bank on the NE shore faces SW.
  * alpha = angle between the wind-FROM bearing and the facing bearing. Wind from SW hits the shore that faces SW (the NE shore).

Labels are MODELED. Nothing here is field-validated (BWIS B3/D2 = 0) and the label never says "measured".
Orientation alone is a weak predictor of high exposure (AUC 0.70, research G5); the label therefore also requires the
fetch-driven chop class, and PROTECTED is granted by either land upwind (alpha > 90) or a low chop class -- but never when the fetch model says HIGH."""
from __future__ import annotations

import math

LABELS = ("DIRECT", "CROSS", "PROTECTED", "UNKNOWN")
DIRECT_MAX_DEG, CROSS_MAX_DEG = 45.0, 90.0
MIN_LABEL_MPH = 3.0          # below this the wind direction is not meaningful: no labels
HIGH_FETCH_CHOP_CLASS = 4    # frozen CEM chop class >= 4 (Hm0 >= 6 in)


def bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Initial great-circle bearing from a=(lat, lon) to b, degrees clockwise from north."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angdiff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def facing_deg(bank: dict) -> float | None:
    """Bearing from the bank (shoreline anchor) toward the water (30 m standoff point). None when either point is missing."""
    a, s = bank.get("anchor"), bank.get("standoff")
    if not a or not s or tuple(a) == tuple(s):
        return None
    return bearing_deg((a[0], a[1]), (s[0], s[1]))


def label_bank(wind_from_deg: float | None, speed_mph: float | None, facing: float | None, chop_class: int | None,
               below_resolution: bool = False) -> dict:
    """One bank. Returns {'label', 'alphaDeg', 'highFetch', 'reason'}. UNKNOWN never reads as PROTECTED."""
    if below_resolution or facing is None or chop_class is None:
        return {"label": "UNKNOWN", "alphaDeg": None, "highFetch": None,
                "reason": "belowResolution" if below_resolution else ("noFacing" if facing is None else "noChopClass")}
    if wind_from_deg is None or speed_mph is None or speed_mph < MIN_LABEL_MPH:
        return {"label": "UNKNOWN", "alphaDeg": None, "highFetch": None, "reason": "windTooLightForDirection"}
    alpha = angdiff(wind_from_deg, facing)
    high = chop_class >= HIGH_FETCH_CHOP_CLASS
    if alpha > CROSS_MAX_DEG:
        if high:
            # Conservative: the fetch model says long open water while the facing says lee. Facing is the weaker signal
            # (research AUC 0.70; narrow arms/creek mouths misestimate it), so never call this PROTECTED.
            return {"label": "CROSS", "alphaDeg": round(alpha), "highFetch": True, "reason": "longFetchOverridesFacing"}
        return {"label": "PROTECTED", "alphaDeg": round(alpha), "highFetch": False, "reason": "windComesOverLand"}
    if chop_class <= 1:
        return {"label": "PROTECTED", "alphaDeg": round(alpha), "highFetch": False, "reason": "shortFetch"}
    if alpha <= DIRECT_MAX_DEG:
        return {"label": "DIRECT", "alphaDeg": round(alpha), "highFetch": high, "reason": "windBlowsOntoBank"}
    return {"label": "CROSS", "alphaDeg": round(alpha), "highFetch": high, "reason": "windSkimsAlongBank"}


def label_shares(labels: list[dict]) -> dict:
    n = len(labels)
    if not n:
        return {}
    c = {k: 0 for k in LABELS}
    for x in labels:
        c[x["label"]] += 1
    known = n - c["UNKNOWN"]
    return {"banks": n, "unknownPct": round(100.0 * c["UNKNOWN"] / n, 1),
            "directPct": round(100.0 * c["DIRECT"] / n, 1), "crossPct": round(100.0 * c["CROSS"] / n, 1),
            "protectedPct": round(100.0 * c["PROTECTED"] / n, 1),
            "highFetchPct": round(100.0 * sum(1 for x in labels if x["highFetch"]) / n, 1),
            "knownBanks": known}
