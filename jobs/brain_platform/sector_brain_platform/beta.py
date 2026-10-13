"""Beta Readiness (docs/brains/scoring/beta-readiness-v1.json): can this lake be trusted in a controlled beta?

Separate from Brain scores (never averaged from them). Hard blockers decide NOT_READY; warnings make a lake
CANDIDATE; READY needs neither. Every blocker traces to a published Brain fact. Unknown stays unknown and
counts as a blocker (a lake with no published slot is not ready).
"""
from __future__ import annotations

import datetime as dt

from .enums import READINESS_LADDER
from .timeutil import iso

BETA_VERSION = "beta-readiness-v1"
REQUIRED_SLOTS = ("lake", "waterTemp", "waterClarity", "wind")
MIN_SLOT_READINESS = "CALIBRATION"        # on the ladder; below this a slot is a blocker
WARN_BELOW_READINESS = "VALIDATED"        # below this a slot is a warning
MIN_KNOWLEDGE_MEDIAN = 5.0                # species-v2 median below this is a warning (not a blocker)


def _rank(r: str | None) -> int:
    return READINESS_LADDER.index(r) if r in READINESS_LADDER else -1


def beta_readiness(lake_id: str, fleet_row: dict | None, intel_state: dict | None, validation: dict, health: dict,
                   source_stale: dict | None, now: dt.datetime) -> dict:
    slots = ((fleet_row or {}).get("slots") or {})
    readiness = ((fleet_row or {}).get("readiness") or {})
    blockers, warnings, supporting = [], [], {}
    for slot in REQUIRED_SLOTS:
        s = slots.get(slot) or {}
        r = readiness.get(slot) or s.get("readiness")
        supporting[slot] = {k: s.get(k) for k in ("readiness", "kind", "stateType", "stale", "evidenceStale", "generatedAt", "lastUpdatedAt") if s.get(k) is not None}
        if r and "readiness" not in supporting[slot]:
            supporting[slot]["readiness"] = r
        if not s:
            blockers.append({"code": "SLOT_NOT_PUBLISHED", "slot": slot, "why": f"no {slot} state published for this lake"})
            continue
        if s.get("stale"):
            blockers.append({"code": "SLOT_STALE", "slot": slot, "why": f"{slot} state is stale (Engine time rule)"})
        if s.get("evidenceStale"):
            blockers.append({"code": "EVIDENCE_STALE", "slot": slot, "why": f"{slot} brain reports its evidence is stale"})
        if (s.get("kind") or "").lower() == "unavailable":
            blockers.append({"code": "VALUE_UNAVAILABLE", "slot": slot, "why": f"{slot} value unavailable"})
        if _rank(r) < _rank(MIN_SLOT_READINESS):
            blockers.append({"code": "READINESS_BELOW_MINIMUM", "slot": slot, "why": f"{slot} readiness {r or 'absent'} < {MIN_SLOT_READINESS}"})
        elif _rank(r) < _rank(WARN_BELOW_READINESS):
            warnings.append({"code": "READINESS_NOT_VALIDATED", "slot": slot, "why": f"{slot} readiness {r} < {WARN_BELOW_READINESS}"})
    # Intelligence evaluation
    intel = intel_state or {}
    if (intel.get("kind") or "").lower() != "evaluated":
        blockers.append({"code": "NO_INTELLIGENCE_EVALUATION", "slot": "intelligence", "why": "no normalized Sector Intelligence evaluation for this lake"})
        supporting["intelligence"] = {"kind": intel.get("kind")} if intel else {}
    else:
        supporting["intelligence"] = {"kind": "evaluated", "evaluationVersion": intel.get("evaluationVersion"), "generatedAt": intel.get("generatedAt"),
                                      "inputsFresh": (intel.get("synthesis") or {}).get("inputsFresh"), "degradedInputs": intel.get("degradedInputs")}
        for slot in intel.get("degradedInputs") or []:
            if slot in REQUIRED_SLOTS or slot == "biology":
                warnings.append({"code": "INTELLIGENCE_INPUT_DEGRADED", "slot": slot, "why": f"Intelligence saw a degraded {slot} input in its last evaluation"})
        bio = ((intel.get("inputs") or {}).get("biology")) or {}
        km = bio.get("knowledgeMedian")
        if km is not None and km < MIN_KNOWLEDGE_MEDIAN:
            warnings.append({"code": "SPECIES_KNOWLEDGE_LOW", "slot": "biology", "why": f"species knowledge median {km} / 10 < {MIN_KNOWLEDGE_MEDIAN} (species-v2)"})
        if bio.get("status") == "NOT_PUBLISHED":
            warnings.append({"code": "NO_SPECIES_PRESENCE", "slot": "biology", "why": "no species presence published for this lake"})
    # validation of the synthesis path and health of the required brains
    vi = (validation.get("sector-intelligence") or {}).get("status")
    if vi != "VALIDATED":
        blockers.append({"code": "SYNTHESIS_NOT_VALIDATED", "slot": "intelligence", "why": f"Sector Intelligence validation is {vi or 'absent'}"})
    for bid, slot in (("lake-brain", "lake"), ("water-temp", "waterTemp"), ("water-clarity", "waterClarity"), ("wind", "wind")):
        if (health.get(bid) or {}).get("status") == "FAILED":
            blockers.append({"code": "BRAIN_FAILED", "slot": slot, "why": f"{bid} health FAILED"})
        vs = (validation.get(bid) or {}).get("status")
        if vs in (None, "NOT_VALIDATED"):
            warnings.append({"code": "BRAIN_NOT_VALIDATED", "slot": slot, "why": f"{bid} validation {vs or 'absent'}"})
    for sid, stale in (source_stale or {}).items():
        if stale:
            warnings.append({"code": "SOURCE_STALE", "why": f"source {sid} is past its stale threshold"})
    state = "NOT_READY" if blockers else ("CANDIDATE" if warnings else "READY")
    return {"lakeId": lake_id, "betaReadiness": state, "betaReadinessVersion": BETA_VERSION, "rubric": "docs/brains/scoring/beta-readiness-v1.json",
            "blockers": blockers, "warnings": warnings, "supportingBrainStates": supporting, "updatedAt": iso(now),
            "note": "Hard blockers decide NOT_READY; warnings make CANDIDATE; READY needs neither. Not a customer rollout decision."}
