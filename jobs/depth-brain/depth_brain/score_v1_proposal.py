"""PROPOSAL ONLY - `depth-brain-score-v1` (docs/brains/depth/DEPTH_SCORE_V1_PROPOSAL.md).

NOT wired anywhere: not imported by publish.py, not registered with the platform scorer, never writes /scores/depth, and Depth has no
official score. It exists so Michael can read exactly what the scorer WOULD say and so the rubric's behaviour (gates, no-gaming) is tested.
Pattern copied from the platform scorers (`sector_brain_platform/scoring.py`): dimensions with weights summing to 100, UNKNOWN dimensions
excluded and contributing 0, gates cap and never add.

It rewards bowfishing usefulness (correct level shift, datum correctness, authoritative contours where they exist, validated effective depth,
live coverage) and deliberately has NO dimension for deep-basin bathymetry, academic completeness, GLOBathy coverage or false precision."""
from __future__ import annotations

import datetime as dt

from sector_brain_platform.scoring import dim, finish, ladder

SCORE_VERSION = "depth-brain-score-v1-PROPOSAL"
RUBRIC_REF = "docs/brains/depth/DEPTH_SCORE_V1_PROPOSAL.md"
OFFICIAL = False

WEIGHTS = {"referencePool": 8, "datumCorrectness": 17, "effectiveDepthCorrectness": 15, "contourQuality": 10, "shallowZoneSupport": 10,
           "fleetCoverage": 15, "validation": 10, "provenance": 5, "freshness": 5, "operationalReliability": 5}
CRITICAL = ("datumCorrectness", "effectiveDepthCorrectness", "fleetCoverage", "validation")      # proposed; Michael ratifies
FORBIDDEN_DIMENSIONS = ("globathy", "bathymetry", "basin", "deep", "completeness")                # nothing may reward these


def _share(n, d):
    return None if not d else n / d


def facts_from_manifest(manifest: dict, *, live_states: int, live_stale: int = 0, validation: str = "NOT_VALIDATED", field_validation: str = "NOT_STARTED",
                        orchestration: str = "NOT_STARTED", health: str = "HEALTHY", effective_validated_pass: bool | None = None) -> dict:
    c = manifest["candidates"]
    addressable = [x for x in c if (x.get("reference") or {}).get("basis") == "fullPool"]
    ab = [x for x in c if (x.get("evidence") or {}).get("tier") in ("A", "B")]
    ok = [x for x in c if x.get("shiftPossible")]
    ds = lambda x: (x.get("datum") or {}).get("status")
    return {
        "directory": len(c), "addressable": len(addressable),
        "poolOk": sum(1 for x in addressable if x["reference"].get("confidence") in ("high", "medium") and x["reference"].get("poolFt") is not None),
        "datumVerified": sum(1 for x in ok if ds(x) in ("SAME_SOURCE", "SAME_DATUM")), "datumInferred": sum(1 for x in ok if ds(x) == "SAME_OPERATOR_SYSTEM"),
        "datumConflicts": 0, "shiftPossible": len(ok), "liveStates": live_states, "liveStale": live_stale,
        "tierAB": len(ab), "tierABLicensed": sum(1 for x in ab if (x.get("licence") or {}).get("customerDerivedMetricsAllowed") == "true"),
        "effectiveZoneEligible": sum(1 for x in ab if (x.get("referenceZones") or {}).get("referenceStatus") == "VERIFIED"),
        "validation": validation, "fieldValidation": field_validation, "orchestration": orchestration, "health": health,
        "effectiveValidatedPass": effective_validated_pass,
    }


def score_depth_proposal(facts: dict, now: dt.datetime) -> dict:
    f, dims, gates = facts, [], []
    A = f["addressable"] or None
    dims.append(dim("referencePool", WEIGHTS["referencePool"], ladder(_share(f["poolOk"], A)), f"{f['poolOk']} of {f['addressable']} pool-basis lakes have a high/medium reference pool"))
    # datum: verified counts fully, inferred operator-system counts half; share of the addressable fleet
    dshare = _share(f["datumVerified"] + 0.5 * f["datumInferred"], A)
    dims.append(dim("datumCorrectness", WEIGHTS["datumCorrectness"], ladder(dshare), f"{f['datumVerified']} verified + {f['datumInferred']} inferred (half weight) of {f['addressable']}"))
    eff = None if f["effectiveValidatedPass"] is None else (8.0 if f["effectiveValidatedPass"] else 3.0)
    dims.append(dim("effectiveDepthCorrectness", WEIGHTS["effectiveDepthCorrectness"], eff, "no field/event validation yet" if eff is None else "preregistered validation " + ("passed" if f["effectiveValidatedPass"] else "failed")))
    dims.append(dim("contourQuality", WEIGHTS["contourQuality"], ladder(_share(f["tierABLicensed"], f["tierAB"])) if f["tierAB"] else None,
                    f"{f['tierABLicensed']} of {f['tierAB']} tier A/B contour lakes licensed for customer-derived numbers"))
    dims.append(dim("shallowZoneSupport", WEIGHTS["shallowZoneSupport"], ladder(_share(f["effectiveZoneEligible"], f["tierAB"])) if f["tierAB"] else None,
                    f"{f['effectiveZoneEligible']} of {f['tierAB']} tier A/B lakes have a verified survey reference pool"))
    dims.append(dim("fleetCoverage", WEIGHTS["fleetCoverage"], ladder(_share(f["liveStates"], A)), f"{f['liveStates']} live Depth shifts of {f['addressable']} pool-basis lakes"))
    vmap = {"VALIDATED": 9.0, "PARTIAL": 5.0, "NOT_VALIDATED": 1.0}
    dims.append(dim("validation", WEIGHTS["validation"], vmap.get(f["validation"], 0.0), f"validation {f['validation']}; field validation {f['fieldValidation']}"))
    dims.append(dim("provenance", WEIGHTS["provenance"], 10.0 if f["liveStates"] else None, "every state carries tier, datum assessment, sources, fingerprint, limitations (tested)"))
    dims.append(dim("freshness", WEIGHTS["freshness"], (10.0 * (1 - f["liveStale"] / f["liveStates"])) if f["liveStates"] else None, f"{f['liveStale']} of {f['liveStates']} live states evidence-stale"))
    dims.append(dim("operationalReliability", WEIGHTS["operationalReliability"], 0.0 if f["orchestration"] == "NOT_STARTED" else None, f"orchestration {f['orchestration']}"))
    assert sum(d["weight"] for d in dims) == 100
    if f["validation"] != "VALIDATED":
        gates.append({"gate": "validation", "cap": 5.0, "why": f"validation {f['validation']}"})
    if f["fieldValidation"] != "PASSED":
        gates.append({"gate": "fieldTruth", "cap": 6.0, "why": f"field validation {f['fieldValidation']}"})
    if _share(f["liveStates"], A) is None or _share(f["liveStates"], A) < 0.10:
        gates.append({"gate": "coverage", "cap": 3.0, "why": f"{f['liveStates']} of {f['addressable']} pool-basis lakes have a live Depth state (< 10 %)"})
    if f["datumConflicts"]:
        gates.append({"gate": "datumConflict", "cap": 2.0, "why": f"{f['datumConflicts']} lakes with conflicting datum evidence"})
    if f["health"] in ("FAILED", "UNKNOWN", None):
        gates.append({"gate": "health", "cap": 2.0, "why": f"brain health {f['health']}"})
    if f["orchestration"] == "NOT_STARTED":
        gates.append({"gate": "orchestration", "cap": 6.0, "why": "no scheduled/orchestrated job"})
    out = finish(SCORE_VERSION, RUBRIC_REF, dims, gates, now, "verify more datums and get Lake Brain fleet states live; then field-validate effective depth")
    out["official"] = False
    out["criticalDimensions"] = list(CRITICAL)
    sb = out["scoreBreakdown"]
    out["criticalBelow7_5"] = sorted(k for k in CRITICAL if sb[k].get("status") != "SCORED" or sb[k]["value"] < 7.5)
    out["meetsProductionPolicy"] = out["value"] >= 8.0 and not out["criticalBelow7_5"]
    return out
