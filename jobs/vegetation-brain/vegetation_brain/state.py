"""VegetationState builder: fleet candidate + LakeObservation + optional upstream Brain context -> `/lakes/{k}/states/vegetation`.

Pure; no I/O. Vegetation publishes only plant/environment state. It does NOT own and never recomputes: depth (Depth), water
level (Lake), optical water state (Clarity), temperature (Water Temp), surface disturbance (Wind), fish preference
(Biological), the recommendation (Intelligence). Upstream states are consumed by reference with their own confidence.

Hard rules enforced here and in tests:
  * SUBMERGED vegetation is never observed: `submergedVegetation.observed` is always False.
  * `potentialHabitat` always carries potentialOnly=True and observed=False, and refuses GLOBathy/modeled depth.
  * Density stays NOT_CALIBRATED until the pre-registered density gate passes.
  * Seasonal state stays UNKNOWN until the pre-registered seasonal back-test gate passes.
  * Unreliable evidence is UNKNOWN with reason codes, never "no vegetation".
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime

from . import contract as C
from . import observer as O
from .language import assert_clean, headline

STALE_AFTER_HOURS = 72.0
CONFIDENCE_BASE = {"SATELLITE_PERSISTENCE": 0.65, "SATELLITE_ACCEPTED_PASS": 0.50, "SATELLITE_SINGLE_PASS": 0.35, "SURVEY": 0.70, "NONE": 0.0}
VALIDATION_CAP = {"NOT_VALIDATED": 0.45, "RESEARCH": 0.50, "CALIBRATION": 0.55, "PARTIAL": 0.75, "VALIDATED": 0.95}
# Canfield et al. 1985 (J. Aquat. Plant Manage. 23:25-28): log10(MDC_m) = a * log10(Secchi_m) + b ; 95 % CI 46-236 % of the prediction.
CANFIELD = {"pooled": (0.61, 0.26), "florida": (0.42, 0.41)}
CANFIELD_CI = (0.46, 2.36)
ALLOWED_POTENTIAL_DEPTH_TIERS = ("A", "B", "C")
ALLOWED_POTENTIAL_DEPTH_KINDS = ("measured", "contour")
M_TO_FT = 3.28084

LIMITATIONS = [
    "SHADOW / internal: no customer surface consumes this state.",
    "V1 observes SURFACE-REACHING vegetation only (floating-leaf beds, mats, emergent belts, surface-topped canopy).",
    "Submerged vegetation is NOT observable with Sentinel-2 at fleet scale and is never reported as observed.",
    "Plant type is not classified (typeBasis NOT_CLASSIFIED); no species identification is possible from multispectral imagery.",
    "Cells touching the lake edge are not claimed (shore-adjacent) because bank vegetation cannot be separated from aquatic vegetation; claims are INTERIOR-ONLY (about half of mapped floating-leaf beds lie in the unclaimed shore band in the validation lakes).",
    "A single clear-looking scene can be wrong (a burst of false cells); presence needs an accepted pass and, where possible, persistence over >= 3 accepted scenes.",
    "Where truth is presence-only (e.g. Florida point surveys) recall has been low (< 0.35); treat PRESENT/NOT_OBSERVED there as unvalidated evidence, not a map.",
    "Density is not calibrated; only presence and counts are published.",
    "Algal blooms and floating plant mats can share a spectrum; ambiguity is not yet resolved.",
    "Observer v0.3 is NOT validated: on held-out lakes v0.2 failed the lake-level NLA gates, recovered few Florida/Minnesota surface points, and its haze guard is effectively off (no validated haze rule).",
]


# ------------------------------------------------------------------------------------- potential habitat
def canfield_ceiling_ft(secchi_m: float, model: str = "pooled") -> dict:
    a, b = CANFIELD[model]
    mdc_m = 10 ** (a * math.log10(secchi_m) + b)
    return {"model": f"canfield-1985-{model}", "secchiM": round(secchi_m, 2), "centralFt": round(mdc_m * M_TO_FT, 1),
            "lowFt": round(mdc_m * CANFIELD_CI[0] * M_TO_FT, 1), "highFt": round(mdc_m * CANFIELD_CI[1] * M_TO_FT, 1),
            "ciNote": "95 % CI is 46-236 % of the prediction (r2 0.56 pooled); a soft prior, not a boundary"}


def assert_allowed_potential_basis(kind: str | None, tier: str | None) -> None:
    """Modeled bathymetry (e.g. GLOBathy) may NOT underpin potential habitat. Only measured/contour depth of tier A/B/C may."""
    if kind not in ALLOWED_POTENTIAL_DEPTH_KINDS or tier not in ALLOWED_POTENTIAL_DEPTH_TIERS:
        raise ValueError(f"depth evidence kind={kind!r} tier={tier!r} cannot support potential habitat (modeled/proxy depth is forbidden)")


def potential_habitat(depth: dict | None, clarity: dict | None, lake: dict | None) -> dict:
    out = {"potentialOnly": True, "observed": False,
           "meaning": "Where submerged vegetation COULD grow given measured depth and clarity. Not an observation of any plant.",
           "headline": C.LANGUAGE["POTENTIAL"]}
    reasons = []
    if not depth:
        reasons.append("DEPTH_BRAIN_UNAVAILABLE")
    else:
        try:
            assert_allowed_potential_basis(depth.get("evidenceKind"), depth.get("tier"))
        except ValueError:
            reasons.append("DEPTH_EVIDENCE_NOT_ALLOWED")
    secchi = (clarity or {}).get("secchiM")
    if secchi is None or not isinstance(secchi, (int, float)) or secchi <= 0:
        reasons.append("CLARITY_UNAVAILABLE")
    if reasons:
        out.update({"status": "NOT_EVALUATED", "reasons": reasons, "basis": []})
        return out
    ceil = canfield_ceiling_ft(float(secchi), "florida" if (clarity or {}).get("region") == "FL" else "pooled")
    out.update({"status": "EVALUATED", "basis": ["depth:" + depth["evidenceKind"] + ":tier" + depth["tier"], "clarity:secchi",
                                                  "canfield-1985"],
                "maxColonizationDepthFt": ceil,
                "depthEvidence": {"tier": depth["tier"], "evidenceKind": depth["evidenceKind"]},
                "clarityConfidence": (clarity or {}).get("confidence"), "poolAnomalyFt": (lake or {}).get("poolAnomalyFt"),
                "reasons": []})
    return out


# ------------------------------------------------------------------------------------- confidence
def confidence(kind: str, validation_state: str, *, coverage: float, geometry_conf: str, persistence_n: int,
               clarity_conf: float | None = None, surface_disturbed: bool = False, fallback: bool = False) -> dict:
    """Rule-based, NOT statistically calibrated (basis says so). Capped by the validation state."""
    base = CONFIDENCE_BASE.get(kind, 0.0)
    reasons = []
    score = base * (0.5 + 0.5 * max(0.0, min(1.0, coverage)))
    if fallback:
        score *= 0.8
        reasons.append("low-coverage fallback pass")
    gmul = {"HIGH": 1.0, "MEDIUM": 0.9, "LOW": 0.6, "MISSING": 0.0}.get(geometry_conf, 0.8)
    if gmul < 1.0:
        reasons.append(f"geometry confidence {geometry_conf}")
    score *= gmul
    if clarity_conf is not None and clarity_conf < 0.5:
        score *= 0.9
        reasons.append("low optical-water confidence from Clarity")
    if surface_disturbed:
        score *= 0.85
        reasons.append("surface disturbed (Wind)")
    cap = VALIDATION_CAP[validation_state]
    if score > cap:
        reasons.append(f"capped by validation state {validation_state}")
        score = cap
    score = round(score, 2)
    level = "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW" if score > 0 else "NONE"
    return {"level": level, "score": score, "basis": "RULE_BASED_NOT_CALIBRATED", "reasons": reasons, "validationState": validation_state}


# ------------------------------------------------------------------------------------- state
def input_fingerprint(cand: dict, obs, ctx: dict, manifest_version: str) -> str:
    key = [cand.get("lakeId"), cand.get("tier"), cand.get("geometryConfidence"), manifest_version, C.BRAIN_VERSION,
           getattr(obs, "scene_ids", None), getattr(obs, "evidence_kind", None), getattr(obs, "plant_cells", None),
           getattr(obs, "observed_share_pct", None), str(getattr(obs, "observed_on", None)),
           sorted(((ctx or {}).get("wind") or {}).items()), ((ctx or {}).get("clarity") or {}).get("secchiM"),
           ((ctx or {}).get("depth") or {}).get("tier")]
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_state(cand: dict, obs, now: datetime, *, validation: dict | None = None, context: dict | None = None,
                manifest_version: str = "unversioned", brain_version: str = C.BRAIN_VERSION) -> tuple[dict, dict]:
    """cand: fleet candidate (fleet.observability row). obs: observer.LakeObservation or None (never observed).
    context: {lake, depth, clarity, temp, wind, seasonal, density}. validation: {state, ...}."""
    ctx = context or {}
    vstate = (validation or {}).get("state", "NOT_VALIDATED")
    lid = cand["lakeId"]
    blocked = cand.get("readiness") == "BLOCKED"
    now_iso = C.iso(now)

    pres, pres_reason = ("UNKNOWN", "NO_GEOMETRY" if cand["tier"] == "UNKNOWN" else "NO_SCENE")
    if blocked:
        pres, pres_reason = "UNKNOWN", (cand.get("reasons") or ["BLOCKED"])[0]
    elif obs is not None:
        pres, pres_reason = O.presence(obs)
        if getattr(obs, "evidence_kind", None) == "SATELLITE_SINGLE_PASS":
            # never expose a single un-accepted pass: one scene produced 39 false cells in production scoring (note 06)
            pres, pres_reason = "UNKNOWN", "PASS_NOT_ACCEPTED"

    observed_on = getattr(obs, "observed_on", None)
    age_days = (now.date() - observed_on).days if observed_on else None
    stale = age_days is None or age_days > C.OBSERVATION_MAX_AGE_DAYS
    fresh_obs = age_days is not None and age_days <= C.OBSERVATION_FRESH_DAYS
    kind_ev = getattr(obs, "evidence_kind", "NONE") if obs is not None else "NONE"
    wind = ctx.get("wind") or {}
    clarity = ctx.get("clarity") or {}
    conf = confidence(kind_ev, vstate, coverage=getattr(obs, "coverage", 0.0) if obs is not None else 0.0,
                      geometry_conf=cand.get("geometryConfidence", "MISSING"), persistence_n=getattr(obs, "n_accepted", 0) if obs is not None else 0,
                      clarity_conf=clarity.get("confidence"), surface_disturbed=bool(wind.get("surfaceDisturbed")),
                      fallback=bool(getattr(obs, "low_coverage_fallback", False)))
    if pres == "UNKNOWN":
        conf = {**conf, "level": "NONE", "score": 0.0}

    cov_class, cov_note = "NOT_CALIBRATED", "density gate (prereg section 6) not passed: presence and counts only"
    dens = ctx.get("density") or {}
    if dens.get("gatePassed") and obs is not None and getattr(obs, "read_cells", 0):
        share = obs.plant_cells / obs.read_cells
        lo, hi = dens["thresholds"]["moderate"], dens["thresholds"]["dense"]
        cov_class = "DENSE" if share >= hi else "MODERATE" if share >= lo else "SPARSE"
        cov_note = f"classified with calibrated thresholds {dens['thresholds']}"

    seasonal = ctx.get("seasonal") or {}
    if seasonal.get("gatePassed") and seasonal.get("state") in C.SEASONAL_STATES:
        sst = {"state": seasonal["state"], "basis": seasonal.get("basis", "LAKE_SPECIFIC_CLIMATOLOGY"), "backtestGate": "PASSED"}
    else:
        sst = {"state": "UNKNOWN", "basis": "NONE", "backtestGate": "NOT_PASSED",
               "reason": "seasonal states require the pre-registered multi-year back-test (prereg section 7); no calendar rule is used"}

    surface = {
        "status": pres, "statusReason": pres_reason, "coverageClass": cov_class, "coverageNote": cov_note,
        "observedPlantCells": getattr(obs, "plant_cells", None) if obs is not None else None,
        "readInteriorCells": getattr(obs, "read_cells", None) if obs is not None else None,
        "interiorCells": getattr(obs, "interior_cells", None) if obs is not None else None,
        "broadType": "SURFACE_REACHING_MIXED" if pres == "PRESENT" else "UNKNOWN", "typeBasis": "NOT_CLASSIFIED",
        "observedAt": f"{observed_on.isoformat()}" if observed_on else None, "ageDays": age_days,
        "source": {"collection": (ctx.get("collection") or "sentinel-2-c1-l2a"), "sceneIds": list(getattr(obs, "scene_ids", []) or []),
                   "sourceId": getattr(obs, "source_id", "vegetation-observer")},
        "observedAreaKm2": (round(obs.observed_area_km2, 3) if getattr(obs, "observed_area_km2", None) is not None else None),
        "confidence": conf,
    }
    surface = {k: v for k, v in surface.items() if v is not None or k in ("observedAt", "ageDays")}

    observation = {
        "evidenceKind": kind_ev, "persistence": getattr(obs, "persistence", "NOT_APPLICABLE") if obs is not None else "NOT_APPLICABLE",
        "acceptedScenes": getattr(obs, "n_accepted", 0) if obs is not None else 0,
        "cloudState": _cloud_state(obs), "refusalShares": {k: round(v, 3) for k, v in (getattr(obs, "refusal_shares", {}) or {}).items()},
        "isolatedCellsDropped": getattr(obs, "isolated_dropped", 0) if obs is not None else 0,
        "lowCoverageFallback": bool(getattr(obs, "low_coverage_fallback", False)) if obs is not None else False,
        "notes": list(getattr(obs, "notes", []) or []),
    }

    ph = potential_habitat(ctx.get("depth"), ctx.get("clarity"), ctx.get("lake"))
    head = headline(pres, vstate, stale=stale)
    assert_clean(head)
    state: dict = {
        "lakeId": lid, "brainId": C.BRAIN_ID, "slot": C.SLOT, "schemaVersion": C.SCHEMA_VERSION, "stateSchema": C.STATE_SCHEMA,
        "kind": "observed" if pres in ("PRESENT", "NOT_OBSERVED") else "unavailable",
        "headline": head, "modelVersion": C.MODEL_ID, "brainVersion": brain_version, "generatedAt": now_iso,
        "surfaceVegetation": surface,
        "submergedVegetation": {"status": "NOT_OBSERVABLE", "observed": False,
                                "reason": "Sentinel-2 cannot reliably observe submerged vegetation at fleet scale; clarity does not rescue it (research)"},
        "seasonalState": sst,
        "observation": observation,
        "potentialHabitat": ph,
        "context": {"consumed": _consumed(ctx), "note": "Upstream states are read-only context with their own confidence; Vegetation does not recompute them."},
        "validation": {"state": vstate, "ref": "/validation/vegetation",
                       "note": "Vegetation begins NOT_VALIDATED; see docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md"},
        "geometry": {"tier": cand["tier"], "geometryConfidence": cand.get("geometryConfidence"), "areaKm2": cand.get("areaKm2"),
                     "reasons": list(cand.get("reasons") or []), "source": "lake-registry (canonical)"},
        "forIntelligence": {"presence": pres, "broadType": surface["broadType"], "coverageClass": cov_class,
                            "seasonalState": sst["state"], "observationAgeDays": age_days, "evidenceKind": kind_ev,
                            "confidence": conf["level"], "stale": stale, "limitationsRef": "limitations",
                            "separation": "Vegetation publishes plant state only. Habitat value vs shootability/obstruction is Intelligence's synthesis."},
        "claimMaturity": {k: dict(v) for k, v in C.CLAIMS.items()},
        "limitations": list(LIMITATIONS),
        "freshness": _freshness(now, observed_on, stale, pres),
    }
    fp = input_fingerprint(cand, obs, ctx, manifest_version)
    state["provenance"] = {"brainId": C.BRAIN_ID, "brainVersion": brain_version, "modelVersion": C.MODEL_ID, "generatedAt": now_iso,
                           "sources": [{"sourceType": ("sharedEvidence" if getattr(obs, "source_id", None) == C.SHARED_SOURCE_ID else "satellite"),
                                        "sourceId": (C.SHARED_SOURCE_ID if getattr(obs, "source_id", None) == C.SHARED_SOURCE_ID else "sentinel-2-l2a"),
                                        "lastObservationAt": surface.get("observedAt")},
                                       {"sourceType": "geometry", "sourceId": "sector-lake-registry", "version": cand.get("geometryVersion")}],
                           "qualityFlags": sorted(set((cand.get("reasons") or []) + ([] if pres != "UNKNOWN" else ["noReliableObservation"]))),
                           "validationRef": "/validation/vegetation", "inputFingerprint": fp, "readiness": None}
    readiness = _readiness(cand, obs, pres, stale)
    state["provenance"]["readiness"] = readiness
    meta = {"readiness": readiness, "kind": state["kind"], "stale": bool(stale), "presence": pres, "fresh": bool(fresh_obs),
            "evidenceKind": kind_ev, "ageDays": age_days, "plantCells": getattr(obs, "plant_cells", None) if obs is not None else None}
    return state, meta


def _readiness(cand, obs, pres, stale) -> str:
    if cand.get("readiness") == "BLOCKED":
        return "BLOCKED"
    if obs is None:
        return "PROFILED"
    if pres == "UNKNOWN" or stale:
        return "DEGRADED"
    return "CALIBRATION"


def _cloud_state(obs) -> str:
    if obs is None or getattr(obs, "evidence_kind", "NONE") == "NONE":
        return "UNKNOWN"
    cov = getattr(obs, "coverage", 0.0)
    return "CLEAR" if cov >= 0.9 else "PARTLY_CLOUDY" if cov >= 0.5 else "CLOUDY"


def _consumed(ctx: dict) -> dict:
    out = {}
    for k in ("lake", "depth", "clarity", "temp", "wind"):
        v = ctx.get(k)
        out[k] = {"consumed": bool(v), **({"confidence": v.get("confidence")} if v and "confidence" in v else {})}
    return out


def _freshness(now: datetime, observed_on, stale: bool, pres: str) -> dict:
    out = {"generatedAt": C.iso(now), "refreshReason": "scheduled", "stale": False, "evidenceStale": bool(stale)}
    if observed_on:
        out["sourceObservationAt"] = observed_on.isoformat()
    rs = []
    if stale:
        rs.append("observation older than OBSERVATION_MAX_AGE_DAYS or absent")
    if pres == "UNKNOWN":
        rs.append("no reliable observation this run")
    if rs:
        out["staleReasons"] = rs
    return out


def plan(published: dict | None, cand: dict, obs, ctx: dict | None, manifest_version: str) -> dict:
    """Fingerprint first: PUBLISH only when a material input changed; page views and clocks never trigger recompute.
    Material inputs: the observation (scene ids / evidence kind / plant cells), registry geometry tier and version, wind flag, Clarity
    Secchi, Depth tier, manifest and Brain versions. Unchanged => SKIP (no work)."""
    fp = input_fingerprint(cand, obs, ctx or {}, manifest_version)
    if not published:
        return {"action": "PUBLISH", "reasons": ["no published Vegetation state"], "fingerprint": fp}
    if (published.get("provenance") or {}).get("inputFingerprint") != fp:
        return {"action": "PUBLISH", "reasons": ["input fingerprint changed"], "fingerprint": fp}
    return {"action": "SKIP", "reasons": ["inputs unchanged"], "fingerprint": fp}
