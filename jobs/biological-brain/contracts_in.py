"""Biological CONSUMPTION contracts for specialist Brain states (provisional until each upstream Brain publishes).

Biological never calculates environmental truth. It validates what a specialist published, and anything it does not recognise,
cannot verify, or that is stale or only modelled becomes UNKNOWN. Ownership:
  * Depth owns environmental depth; Biological owns species depth PREFERENCE; Intelligence matches the two.
  * Vegetation owns the actual plant state; Biological owns species vegetation association.
  * Lake owns pool level, trend and (when published) tributary discharge; lake pool trend is NOT tributary discharge.
  * Water Temp owns temperature and trend; Clarity owns clarity.
Shapes follow the upstream sessions' own documents (Depth: docs/brains/depth/DEPTH_STATE_CONTRACT.md; Vegetation: proposed classes/tiers).
"""
from __future__ import annotations

import datetime as dt

import features as ft

CONTRACTS_VERSION = "biological-input-contracts-v1"
UNKNOWN = "UNKNOWN"

# ---------------------------------------------------------------- Water Temp / Lake sanity
TEMP_F_RANGE = (28.0, 110.0)
TREND_F_MAX = 25.0


def sane_temperature(current_f, trend_f) -> tuple:
    """(currentTempF, trend24hF) with implausible values dropped to None (a sensor/model fault is UNKNOWN, not a fish signal)."""
    cur = float(current_f) if isinstance(current_f, (int, float)) and not isinstance(current_f, bool) and TEMP_F_RANGE[0] <= current_f <= TEMP_F_RANGE[1] else None
    tr = float(trend_f) if isinstance(trend_f, (int, float)) and not isinstance(trend_f, bool) and abs(trend_f) <= TREND_F_MAX else None
    return cur, tr


def lake_trend(value) -> str:
    return value if value in ft.STAGE_TRENDS else UNKNOWN


# ---------------------------------------------------------------- Depth
DEPTH_EDGES_FT = (3.0, 6.0, 10.0)                     # the contour-share edges the Depth Brain can publish
M_TO_FT = 3.28084
# Biological depth classes in feet: LT_0_5M [0, 1.64) · M0_5_1_5 [1.64, 4.92) · M1_5_3 [4.92, 9.84) · GT_3M [9.84, inf)
DEPTH_CLASS_FT = {"LT_0_5M": (0.0, 0.5 * M_TO_FT), "M0_5_1_5": (0.5 * M_TO_FT, 1.5 * M_TO_FT), "M1_5_3": (1.5 * M_TO_FT, 3.0 * M_TO_FT), "GT_3M": (3.0 * M_TO_FT, float("inf"))}
MAX_DEPTH_STATE_AGE_H = 48.0


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def normalize_depth(state: dict | None, now: dt.datetime) -> dict:
    """Depth Brain `sector-brain-depth-state-v1` -> {status, shares, sharesBasis, shift...}. Shares are used only when they are valid for the CURRENT level."""
    if not isinstance(state, dict) or state.get("stateSchema") != "sector-brain-depth-state-v1":
        return {"status": "NOT_PUBLISHED", "reason": "no recognised Depth state"}
    fr = state.get("freshness") or {}
    if fr.get("stale"):
        return {"status": "STALE", "reason": "Depth state reports itself stale"}
    gen = (state.get("provenance") or {}).get("generatedAt") or fr.get("generatedAt")
    try:
        age = (now - dt.datetime.fromisoformat(str(gen).replace("Z", "+00:00"))).total_seconds() / 3600.0
    except Exception:
        return {"status": "STALE", "reason": "no generatedAt"}
    if age > MAX_DEPTH_STATE_AGE_H:
        return {"status": "STALE", "reason": f"state is {age:.0f} h old"}
    ed = state.get("effectiveDepth") or {}
    if ed.get("mode") not in ("shiftOnly", "zoned"):
        return {"status": "PUBLISHED", "mode": ed.get("mode", "unknown"), "shares": None, "sharesBasis": None, "reason": "effective depth is unknown/refused by the Depth Brain"}
    out = {"status": "DEGRADED" if ed.get("confidence") == "LOW" else "PUBLISHED", "mode": ed["mode"], "shiftFt": _num(ed.get("shiftFt")),
           "uncertaintyFt": _num(ed.get("uncertaintyFt")), "confidence": ed.get("confidence"), "resolvable": bool(ed.get("resolvable")),
           "shares": None, "sharesBasis": None}
    ez, rz = state.get("effectiveZones") or {}, state.get("referenceZones") or {}
    if ez.get("available") is True and all(isinstance(ez.get(k), dict) for k in ("shareUnder3Ft", "share3To6Ft", "share6To10Ft")):
        out["shares"] = {"under3": ez["shareUnder3Ft"], "3to6": ez["share3To6Ft"], "6to10": ez["share6To10Ft"]}        # (lo, hi) bounds
        out["sharesBasis"] = "effective"
    elif out["resolvable"] is False and all(_num(rz.get(k)) is not None for k in ("shareUnder3Ft", "share3To6Ft", "share6To10Ft")):
        # the level is within the shift uncertainty of the reference pool, so the survey's reference shares still describe today
        pt = lambda x: {"lo": float(x), "hi": float(x)}                                                                 # noqa: E731
        out["shares"] = {"under3": pt(rz["shareUnder3Ft"]), "3to6": pt(rz["share3To6Ft"]), "6to10": pt(rz["share6To10Ft"])}
        out["sharesBasis"] = "reference(level not resolvably different)"
    return out


def _bnd(x):
    return (float(x["lo"]), float(x["hi"])) if isinstance(x, dict) and "lo" in x and "hi" in x else None


def depth_availability(depth: dict, depth_class: str) -> dict:
    """Bounds on the share of lake surface in a Biological depth class, from 3/6/10 ft contour shares. The classes straddle the share edges, so the answer is
    a LOWER and UPPER bound, never an interpolated point. UNKNOWN if the Depth Brain cannot support shares for today's level."""
    if depth.get("status") not in ("PUBLISHED", "DEGRADED") or not depth.get("shares"):
        return {"state": UNKNOWN, "reason": depth.get("reason") or "no depth shares valid for the current level"}
    u3, m36, m610 = (_bnd(depth["shares"][k]) for k in ("under3", "3to6", "6to10"))
    if None in (u3, m36, m610):
        return {"state": UNKNOWN, "reason": "malformed share bounds"}
    deeper_lo = max(0.0, 1.0 - (u3[1] + m36[1] + m610[1]))
    deeper_hi = min(1.0, 1.0 - (u3[0] + m36[0] + m610[0]))
    lo_hi = {"LT_0_5M": (0.0, u3[1]),                       # [0,1.64) is inside [0,3): the lower bound cannot be resolved
             "M0_5_1_5": (0.0, min(1.0, u3[1] + m36[1])),    # [1.64,4.92) straddles the 3 ft edge and lies inside [0,6)
             "M1_5_3": (0.0, min(1.0, m36[1] + m610[1])),    # [4.92,9.84) straddles the 6 ft edge and lies inside [3,10)
             "GT_3M": (deeper_lo, min(1.0, deeper_hi + m610[1]))}.get(depth_class)
    if lo_hi is None:
        return {"state": UNKNOWN, "reason": f"unknown depth class {depth_class!r}"}
    return {"state": "BOUNDED", "lower": round(lo_hi[0], 4), "upper": round(lo_hi[1], 4), "basis": depth.get("sharesBasis"), "confidence": depth.get("confidence")}


# ---------------------------------------------------------------- Vegetation
VEG_CLASSES = ("EMERGENT", "FLOATING", "SUBMERGED", "FLOODED_TERRESTRIAL", "NONE_SIGNIFICANT", "UNKNOWN")
VEG_DENSITY = ("NONE", "SCATTERED", "MODERATE", "DENSE")
VEG_OBSERVED_TIERS = ("OBSERVED_SATELLITE", "OBSERVED_SURVEY")          # PRIOR_MAPPED / SEASONAL_EXPECTATION / POTENTIAL_HABITAT never count as presence
MAX_VEG_AGE_DAYS = 45.0                                                  # engineering default: an observation older than this is not "current"; not a biological threshold


def vegetation_habitat_state(cell: dict | None, habitat_class: str, now: dt.datetime, max_age_days: float = MAX_VEG_AGE_DAYS) -> dict:
    """TRUE / FALSE / UNKNOWN for `shallowVegetatedHabitat` or `floodedVegetation` from one Vegetation cell/segment. A model, prior, expectation or
    refusal is never presence; a stale observation is UNKNOWN."""
    if habitat_class not in ("shallowVegetatedHabitat", "floodedVegetation"):
        return {"state": UNKNOWN, "reason": f"{habitat_class} is not a vegetation-owned habitat class"}
    if not isinstance(cell, dict):
        return {"state": UNKNOWN, "reason": "no vegetation state published for this area"}
    cls, tier = cell.get("class"), cell.get("tier")
    if cls not in VEG_CLASSES or cls == "UNKNOWN":
        return {"state": UNKNOWN, "reason": "vegetation class unknown or unrecognised (refusal)"}
    if tier not in VEG_OBSERVED_TIERS:
        return {"state": UNKNOWN, "reason": f"evidence tier {tier!r} is not an observation"}
    try:
        age = (now - dt.datetime.fromisoformat(str(cell.get("observedAt")).replace("Z", "+00:00"))).total_seconds() / 86400.0
    except Exception:
        return {"state": UNKNOWN, "reason": "no observation date"}
    if age < 0 or age > max_age_days:
        return {"state": UNKNOWN, "reason": f"observation is {age:.0f} days old" if age >= 0 else "observation date in the future"}
    dens = cell.get("density")
    if cls == "NONE_SIGNIFICANT":
        return {"state": "FALSE", "reason": "observed clear of cover", "ageDays": round(age, 1), "confidence": cell.get("confidence")}
    if habitat_class == "floodedVegetation":
        ok = cls == "FLOODED_TERRESTRIAL"
    else:
        ok = cls in ("SUBMERGED", "EMERGENT", "FLOATING") and dens not in (None, "NONE") and dens in VEG_DENSITY
    if cls in ("SUBMERGED", "EMERGENT", "FLOATING") and dens not in VEG_DENSITY and habitat_class == "shallowVegetatedHabitat":
        return {"state": UNKNOWN, "reason": "density missing or unrecognised"}
    return {"state": "TRUE" if ok else "FALSE", "class": cls, "density": dens, "surfaceTopped": cell.get("surfaceTopped"), "ageDays": round(age, 1), "confidence": cell.get("confidence"),
            "reason": f"{cls} {dens or ''} observed {age:.0f} d ago ({tier})".replace("  ", " ")}
