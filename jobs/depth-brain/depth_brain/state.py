"""DepthState builder: manifest candidate + Lake Brain state -> `/lakes/{k}/states/depth` payload (pure; no I/O).

Depth never reads raw level feeds and never computes a level. It reads Lake Brain's published `states/lake`
(currentElevationFt, datum, observationTime, sourceCapability, kind) and combines it with the audited, static
reference record. Unknown stays absent; every refusal carries reason codes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from . import contract as C
from . import zones as Z
from .datum import DatumAssessment, assess, normalize_datum
from .shift import LevelObservation, ReferencePool, ShiftResult, compute_shift


def _assessment_from_manifest(rec: dict) -> DatumAssessment:
    a = rec.get("datum") or {}
    return DatumAssessment(a.get("status", "UNKNOWN"), float(a.get("sigmaFt", 0.0)), float(a.get("conversionFt", 0.0)), list(a.get("reasons") or []))


def level_from_lake_state(ls: dict | None) -> LevelObservation | None:
    if not ls:
        return None
    return LevelObservation(
        elevation_ft=ls.get("currentElevationFt"), unit=ls.get("unit", "ft"), datum=ls.get("datum"),
        observed_at=C.parse_iso(ls.get("observationTime")), capability=ls.get("sourceCapability"), kind=ls.get("kind"),
        lake_difference_ft=ls.get("differenceFromNormalPoolFt"))


def reference_from_candidate(rec: dict) -> ReferencePool:
    r = rec.get("reference") or {}
    return ReferencePool(pool_ft=r.get("poolFt"), basis=r.get("basis"), confidence=r.get("confidence"), datum=r.get("datum"),
                         datum_verified=bool(r.get("datumVerified")), source=r.get("source"), assessment=_assessment_from_manifest(rec))


def input_fingerprint(rec: dict, ls: dict | None, manifest_version: str) -> str:
    key = [rec.get("lakeId"), (rec.get("reference") or {}).get("poolFt"), (rec.get("datum") or {}).get("status"), manifest_version, C.BRAIN_VERSION,
           (ls or {}).get("observationTime"), (ls or {}).get("currentElevationFt"), (ls or {}).get("kind"), (ls or {}).get("sourceCapability")]
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]


def plan(published: dict | None, rec: dict, ls: dict | None, manifest_version: str) -> dict:
    """Orchestrator-facing: PUBLISH when the input fingerprint changed; page views never trigger recompute."""
    fp = input_fingerprint(rec, ls, manifest_version)
    if not published:
        return {"action": "PUBLISH", "reasons": ["no published Depth state"], "fingerprint": fp}
    if (published.get("provenance") or {}).get("inputFingerprint") != fp:
        return {"action": "PUBLISH", "reasons": ["input fingerprint changed (Lake Brain observation, reference, datum, manifest or Depth version)"], "fingerprint": fp}
    return {"action": "SKIP", "reasons": ["inputs unchanged"], "fingerprint": fp}


def _facts(res: ShiftResult, rec: dict) -> list[str]:
    if res.mode != "shiftOnly":
        return []
    s = res.shift_ft
    if abs(s) < 0.05:
        move = "at its reference pool"
    elif s < 0:
        move = f"{abs(s):.1f} ft below its reference pool"
    else:
        move = f"{s:.1f} ft above its reference pool"
    out = [f"The lake is {move}; depths measured at the reference pool should be read as about {s:+.1f} ft (+/- {res.sigma_ft:.1f} ft). "
           f"This is a shift, not a measured depth for any particular spot."]
    if not res.resolvable:
        out.append("The shift is within the uncertainty of the reference and level inputs; treat it as unresolved.")
    return out


def _effective_zones(z, res, ref) -> dict:
    """Shift the zones relative to the SURVEY reference pool. The state's shift is against the directory pool; when the survey pool differs it is
    re-based (`shift_survey = shift + refPool - surveyPool`) - valid only if the survey pool is in the same datum as the Depth reference."""
    if z.reference_status != "VERIFIED" or z.reference_pool_ft is None:
        return Z.effective_zones(z, res.shift_ft, res.sigma_ft)            # withheld by zones.py (SURVEY_REFERENCE_POOL_UNVERIFIED)
    sd, rd = normalize_datum(z.reference_pool_datum), normalize_datum(ref.datum)
    if sd is None or rd is None or sd != rd:
        return {"available": False, "reason": "SURVEY_REFERENCE_DATUM_NOT_COMPATIBLE"}
    return Z.effective_zones(z, res.shift_ft + (ref.pool_ft - z.reference_pool_ft), res.sigma_ft)


def build_state(rec: dict, lake_state: dict | None, now: datetime, *, manifest_version: str = "unversioned", brain_version: str = C.BRAIN_VERSION) -> tuple[dict, dict]:
    """-> (state payload, meta). meta carries readiness / kind / stale for the publisher's fleet rows."""
    lid = rec["lakeId"]
    ref = reference_from_candidate(rec)
    lvl = level_from_lake_state(lake_state)
    res = compute_shift(lvl, ref, now, (rec.get('levelSource') or {}).get('datum')) if rec.get("shiftPossible", False) else ShiftResult("unknown", reasons=["CANDIDATE_BLOCKED"] + list(rec.get("blockedReasons") or []))
    if rec.get("shiftPossible", False) and lake_state is None:
        res = ShiftResult("unknown", reasons=["LAKE_STATE_MISSING"])
    ok = res.mode == "shiftOnly"
    ev = rec.get("evidence") or {}
    tier = ev.get("tier", "UNKNOWN")

    eff = res.as_dict()
    eff["note"] = "shift of reference depths; absolute depth requires a reference depth that this record does not claim" if ok else "no shift defended"
    state: dict = {
        "lakeId": lid, "brainId": C.BRAIN_ID, "slot": C.SLOT, "schemaVersion": C.SCHEMA_VERSION, "stateSchema": C.STATE_SCHEMA,
        "kind": "observed" if ok else "unavailable",
        "reference": {k: v for k, v in {
            "referencePoolFt": ref.pool_ft, "referencePoolBasis": ref.basis, "referencePoolConfidence": ref.confidence,
            "referencePoolDatum": ref.datum, "referencePoolSource": ref.source,
            "datumAssessment": (ref.assessment.as_dict() if ref.assessment else None)}.items() if v is not None},
        "effectiveDepth": eff,
        "coverage": {k: v for k, v in {
            "sourceTier": tier, "researchTier": ev.get("researchTier"), "evidenceKind": ev.get("kind", "unknown"),
            "depthEvidence": ("none: lake-level stage-area (hypsometry) only" if ev.get("hypsometryOnly") else ev.get("bestSource")),
            "contourCoverage": ev.get("coverage"), "knownAreaShare": ev.get("coverage"),
            "unknownAreaShare": (round(1 - ev["coverage"], 3) if ev.get("coverage") is not None else None),
            "contourIntervalFt": ev.get("intervalFt"), "surveyYear": ev.get("surveyYear")}.items() if v is not None},
    }
    if lvl is not None and lvl.elevation_ft is not None:
        state["level"] = {k: v for k, v in {
            "currentElevationFt": lvl.elevation_ft, "datum": normalize_datum(lvl.datum) or lvl.datum,
            "observedAt": C.iso(lvl.observed_at) if lvl.observed_at else None, "sourceCapability": lvl.capability,
            "levelDeltaFromReferenceFt": (round(res.shift_ft, 2) if ok else None),
            "sourceBrain": "lake-brain", "lakeBrainDifferenceFromNormalPoolFt": lvl.lake_difference_ft,
            "lakeBrainGuideFt": (lake_state or {}).get("guideFt"), "lakeBrainDifferenceFromGuideFt": (lake_state or {}).get("differenceFromGuideFt"),
            "sourceBrainVersion": ((lake_state or {}).get("provenance") or {}).get("brainVersion")}.items() if v is not None}

    # Contour zones: only for tier A/B/C lakes whose manifest carries supported cumulative shares.
    zr = rec.get("referenceZones")
    if zr and ok and tier in ("A", "B", "C"):
        z = Z.ReferenceZones({float(k): v for k, v in zr["cumulative"].items()}, zr.get("intervalFt"), zr.get("coverage"), tier, zr.get("source", "?"),
                             zr.get("surveyYear"), zr.get("referencePoolFt"), zr.get("referencePoolDatum"), zr.get("referenceStatus", "UNVERIFIED"), zr.get("flags") or [])
        state["referenceZones"] = {"evidenceKind": "contour", "tier": tier, "source": z.source, **Z.reference_state(z),
                                   "support": {"contourIntervalFt": z.interval_ft, "coverage": z.coverage, "surveyYear": z.survey_year},
                                   "basis": "share of the surveyed surface at the survey reference pool"}
        eff_z = _effective_zones(z, res, ref)
        state["effectiveZones"] = eff_z
        if eff_z.get("available"):
            eff["mode"] = "zoned"
    if ok:
        state["facts"] = _facts(res, rec)

    limitations = ["Depth Brain is SHADOW / internal: no customer surface consumes this state.",
                   "A shift is not an absolute depth. Reference depths exist only where real contour evidence is listed under coverage."]
    if not ok:
        limitations.append("No shift is published for this lake this run (see effectiveDepth.reasons).")
    lic = rec.get("licence") or {}
    licence_blocked = tier in ("A", "B", "C") and lic.get("customerDerivedMetricsAllowed") == "false"
    if licence_blocked:
        limitations.append("Contour source terms do not (yet) permit customer-facing derived numbers: internal / shadow use only.")
    if tier in ("D", "UNKNOWN"):
        limitations.append("No measured or contour depth evidence for this lake: depth zones, flats and drop-offs are unknown, and modeled bathymetry is not used.")
    if ok and "pool" in C.SIGMA_ASSUMED:
        limitations.append("Uncertainty components (pool, level, datum) are research estimates, not instrument specifications.")
    state["limitations"] = limitations

    stale_input = (lake_state or {}).get("freshness", {}).get("stale") is True
    evidence_stale = (res.evidence_stale or stale_input) if ok else True
    fresh = {"generatedAt": C.iso(now), "refreshReason": "scheduled", "stale": False, "evidenceStale": bool(evidence_stale)}
    if lvl is not None and lvl.observed_at is not None:
        fresh["sourceObservationAt"] = C.iso(lvl.observed_at)
    reasons = []
    if res.evidence_stale:
        reasons.append(f"Lake Brain level observation is {res.level_age_hours:.1f} h old (> {C.LEVEL_FRESH_HOURS:g} h)")
    if stale_input:
        reasons.append("Lake Brain state is flagged stale")
    if not ok:
        reasons.append("no defended shift: " + ", ".join(res.reasons))
    if reasons:
        fresh["staleReasons"] = reasons
    state["freshness"] = fresh

    flags = list(res.flags)
    if licence_blocked:
        flags.append("contourLicenceInternalOnly")
    if not ok:
        flags.append("shiftUnavailable")
    datum_prov = {k: v for k, v in {
        "status": (rec.get("datum") or {}).get("status"), "confidence": (rec.get("datum") or {}).get("evidenceConfidence") or ("high" if (rec.get("datum") or {}).get("status") in ("SAME_SOURCE", "SAME_DATUM") else None),
        "basis": (rec.get("datum") or {}).get("basis"), "evidenceUrls": (rec.get("datum") or {}).get("evidenceUrls")}.items() if v}
    lic = rec.get("licence") or {}
    state["provenance"] = {
        "brainId": C.BRAIN_ID, "brainVersion": brain_version, "modelVersion": C.MODEL_ID,
        "processingVersion": f"{C.MODEL_ID} @ manifest {manifest_version}", "generatedAt": C.iso(now),
        "sources": [{"sourceType": "brainState", "sourceId": "lake-brain/states/lake", "lastObservationAt": fresh.get("sourceObservationAt")},
                    {"sourceType": "referencePool", "sourceId": ref.source or "engine-directory:fullPoolFt"}],
        "inputAgeHours": (round(res.level_age_hours, 2) if res.level_age_hours is not None else None),
        "readiness": None, "qualityFlags": flags, "validationRef": "/validation/depth",
        "inputFingerprint": input_fingerprint(rec, lake_state, manifest_version)}
    if datum_prov:
        state["provenance"]["datumEvidence"] = datum_prov
    if lic and lic.get("customerDerivedMetricsAllowed") not in (None, "n/a"):
        state["provenance"]["licence"] = {"classes": lic.get("classes"), "customerDerivedMetricsAllowed": lic.get("customerDerivedMetricsAllowed")}
    else:
        state["provenance"]["licence"] = {"contourData": "none used", "note": "shift-only state: level from the Lake Brain state (operator feed) and the directory reference pool; no third-party depth/contour data is involved"}
    if state["provenance"]["inputAgeHours"] is None:
        del state["provenance"]["inputAgeHours"]

    if ok:
        readiness = "DEGRADED" if evidence_stale else "CALIBRATION"
    elif not rec.get("shiftPossible", False):
        readiness = "BLOCKED"
    else:
        readiness = "DEGRADED"
    state["provenance"]["readiness"] = readiness
    meta = {"readiness": readiness, "kind": state["kind"], "stale": bool(evidence_stale), "mode": eff["mode"], "tier": tier,
            "shiftFt": (round(res.shift_ft, 2) if ok else None), "reasons": list(res.reasons)}
    return state, meta


def brain_plan(published_fingerprints: dict, manifest: dict, lake_states: dict, published_registry_version: str | None = None) -> dict:
    """Brain-level orchestrator verdict (contract section 11): PUBLISH when any evaluable lake's input fingerprint changed, a lake lost/gained a state,
    or the Depth version changed; else SKIP. Pure; reads nothing. Not registered with the orchestrator (shadow)."""
    mv = manifest.get("manifestVersion", "unversioned")
    reasons, changed = [], []
    if published_registry_version != C.BRAIN_VERSION:
        reasons.append(f"Depth version {published_registry_version!r} -> {C.BRAIN_VERSION!r}")
    for rec in manifest["candidates"]:
        lid = rec["lakeId"]
        ls = lake_states.get(lid)
        if ls is None and rec.get("rollout") != "PILOT_VERIFIED" and lid not in published_fingerprints:
            continue                                            # never evaluated and nothing to evaluate
        if published_fingerprints.get(lid) != input_fingerprint(rec, ls, mv):
            changed.append(lid)
    if changed:
        reasons.append(f"{len(changed)} lake(s) with a changed input fingerprint")
    return {"action": "PUBLISH" if reasons else "SKIP", "reasons": reasons or ["inputs unchanged"], "lakes": sorted(changed)}
