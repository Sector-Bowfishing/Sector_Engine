"""PROPOSAL ONLY - `depth-brain-score-v2` (docs/brains/depth/DEPTH_OFFICIAL_SCORE_DECISION.md). Supersedes the v1 proposal; NOT ratified, NOT wired.

Not imported by publish.py or ops_summary.py, never writes /scores/depth, Depth has no official score. It exists so Michael can read exactly what the scorer WOULD say.
Same platform primitives as every other Brain scorer (`sector_brain_platform/scoring.py`): weights sum to 100, UNKNOWN contributes 0, gates cap and never add.

What changed from v1, and why (each is a decision for Michael in the decision doc):
  1. COVERAGE counts lakes with a defensible profiled shift path, like Lake Brain's score counts profiled lakes (not published states). Live states are measured separately
     in operationalReliability, so a Lake Brain publication gap does not read as a Depth defect.
  2. VALIDATION is split: derivationValidity (formula, inputs, provider verification, desk validation: scorable today) and interpretationValidity (field/prospective: the only
     dimension that needs field data). interpretationValidity is critical, so the 8.0 / 7.5 production policy still cannot pass before field validation.
  3. No dimension rewards absolute depth, flats, drop-offs, channels or bathymetry (a test fails if one appears); the research rubric's two out-of-mission dimensions are replaced by
     depthShareEvidence and shallowZoneActivation, which measure what Depth does claim."""
from __future__ import annotations

import datetime as dt

from sector_brain_platform.scoring import dim, finish, ladder

SCORE_VERSION = "depth-brain-score-v2-PROPOSAL"
RUBRIC_REF = "docs/brains/depth/DEPTH_OFFICIAL_SCORE_DECISION.md"
OFFICIAL = False

WEIGHTS = {"referencePool": 6, "datumCorrectness": 16, "fleetCoverage": 14, "depthShareEvidence": 8, "shallowZoneActivation": 8, "derivationValidity": 14,
           "interpretationValidity": 14, "provenance": 5, "freshness": 5, "operationalReliability": 10}
CRITICAL = ("datumCorrectness", "fleetCoverage", "derivationValidity", "interpretationValidity")        # proposed; Michael ratifies
FORBIDDEN_DIMENSIONS = ("globathy", "bathymetry", "basin", "deep", "completeness", "absolute", "morphology", "flat", "channel")


def _share(n, d):
    return None if not d else n / d


def facts_from_manifest(manifest: dict, claims: dict | None = None, *, live_states: int = 0, live_stale: int = 0, field_validation: str = "NOT_STARTED",
                        orchestration: str = "NOT_STARTED", health: str = "HEALTHY", interpretation_claims_published: bool = False) -> dict:
    c = manifest["candidates"]
    addressable = [x for x in c if (x.get("reference") or {}).get("basis") == "fullPool"]
    ok = [x for x in c if x.get("shiftPossible")]
    ds = lambda x: (x.get("datum") or {}).get("status")
    zk = lambda x: (x.get("referenceZones") or {}).get("kind", "contour") if x.get("referenceZones") else None
    # lakes with an authoritative depth-share source that is usable: tier A/B contours, or an operator elevation-area rating / survey table
    evid = [x for x in ok if (x.get("evidence") or {}).get("tier") in ("A", "B") or zk(x) == "stage-area-rating"]
    active = [x for x in evid if (x.get("referenceZones") or {}).get("referenceStatus") == "VERIFIED"]
    l2 = [k for k in ((claims or {}).get("claims") or []) if k.get("level") == 2 and k.get("status") != "WITHHELD"]
    l2_ok = [k for k in l2 if k.get("status") in ("VERIFIED", "DESK_VALIDATED", "PROVIDER_VERIFIED")]
    return {
        "directory": len(c), "addressable": len(addressable),
        "poolOk": sum(1 for x in addressable if x["reference"].get("confidence") in ("high", "medium") and x["reference"].get("poolFt") is not None),
        "datumVerified": sum(1 for x in ok if ds(x) in ("SAME_SOURCE", "SAME_DATUM")), "datumInferred": sum(1 for x in ok if ds(x) == "SAME_OPERATOR_SYSTEM"), "datumConflicts": 0,
        "shiftPossible": len(ok), "evidenceLakes": len(evid), "zonesActive": len(active),
        "l2Published": len(l2), "l2Verified": len(l2_ok),
        "liveStates": live_states, "liveStale": live_stale, "fieldValidation": field_validation, "orchestration": orchestration, "health": health,
        "interpretationClaimsPublished": interpretation_claims_published,
    }


def score_depth_proposal(facts: dict, now: dt.datetime) -> dict:
    f, dims, gates = facts, [], []
    A = f["addressable"] or None
    dims.append(dim("referencePool", WEIGHTS["referencePool"], ladder(_share(f["poolOk"], A)), f"{f['poolOk']} of {f['addressable']} pool-basis lakes have a high/medium reference pool"))
    dims.append(dim("datumCorrectness", WEIGHTS["datumCorrectness"], ladder(_share(f["datumVerified"] + 0.5 * f["datumInferred"], f["shiftPossible"])),
                    f"{f['datumVerified']} verified + {f['datumInferred']} inferred (half weight) of {f['shiftPossible']} shift-defensible lakes (quality of the datum evidence behind each shift; coverage is scored apart)"))
    dims.append(dim("fleetCoverage", WEIGHTS["fleetCoverage"], ladder(_share(f["shiftPossible"], A)), f"{f['shiftPossible']} of {f['addressable']} pool-basis lakes have a defensible profiled shift path"))
    dims.append(dim("depthShareEvidence", WEIGHTS["depthShareEvidence"], ladder(_share(f["evidenceLakes"], f["shiftPossible"])) if f["shiftPossible"] else None,
                    f"{f['evidenceLakes']} of {f['shiftPossible']} shift-defensible lakes have authoritative depth-share evidence (tier A/B contours or an operator elevation-area rating)"))
    dims.append(dim("shallowZoneActivation", WEIGHTS["shallowZoneActivation"], ladder(_share(f["zonesActive"], f["evidenceLakes"])) if f["evidenceLakes"] else None,
                    f"{f['zonesActive']} of {f['evidenceLakes']} evidence lakes have effective zones activated (verified reference + passed validation or exact rating)"))
    dims.append(dim("derivationValidity", WEIGHTS["derivationValidity"], None if not f["l2Published"] else 10.0 * f["l2Verified"] / f["l2Published"],
                    f"{f['l2Verified']} of {f['l2Published']} published Level-2 claims are VERIFIED / DESK_VALIDATED (claim_levels.json)"))
    interp = {"PASSED": 9.0, "PARTIAL": 5.0}.get(f["fieldValidation"])
    dims.append(dim("interpretationValidity", WEIGHTS["interpretationValidity"], interp, f"field validation {f['fieldValidation']}; interpretation classes published: {f['interpretationClaimsPublished']}"))
    dims.append(dim("provenance", WEIGHTS["provenance"], 10.0 if f["shiftPossible"] else None, "every state carries tier, datum assessment, sources, fingerprint, limitations (tested)"))
    dims.append(dim("freshness", WEIGHTS["freshness"], (10.0 * (1 - f["liveStale"] / f["liveStates"])) if f["liveStates"] else None, f"{f['liveStale']} of {f['liveStates']} live states evidence-stale"))
    oper = {"NOT_STARTED": 0.0, "REGISTERED_SHADOW": 3.0}.get(f["orchestration"], 6.0) + 4.0 * min(1.0, _share(f["liveStates"], f["shiftPossible"]) or 0.0)
    dims.append(dim("operationalReliability", WEIGHTS["operationalReliability"], oper, f"orchestration {f['orchestration']}; {f['liveStates']} live states of {f['shiftPossible']} shift-defensible lakes"))
    assert sum(d["weight"] for d in dims) == 100
    cov = _share(f["shiftPossible"], A)
    if cov is None or cov < 0.10:
        gates.append({"gate": "coverage", "cap": 3.0, "why": f"{f['shiftPossible']} of {f['addressable']} pool-basis lakes profiled (< 10 %)"})
    if f["datumConflicts"]:
        gates.append({"gate": "datumConflict", "cap": 2.0, "why": f"{f['datumConflicts']} lakes with conflicting datum evidence"})
    if f["health"] in ("FAILED", "UNKNOWN", None):
        gates.append({"gate": "health", "cap": 2.0, "why": f"brain health {f['health']}"})
    if f["interpretationClaimsPublished"] and f["fieldValidation"] != "PASSED":
        gates.append({"gate": "fieldTruth", "cap": 5.0, "why": "interpretation classes are published without a passed field validation"})
    out = finish(SCORE_VERSION, RUBRIC_REF, dims, gates, now, "get Lake Brain states live and orchestration registered; field-validate the interpretation classes")
    out["official"] = False
    out["criticalDimensions"] = list(CRITICAL)
    sb = out["scoreBreakdown"]
    out["criticalBelow7_5"] = sorted(k for k in CRITICAL if sb[k].get("status") != "SCORED" or sb[k]["value"] < 7.5)
    out["meetsProductionPolicy"] = out["value"] >= 8.0 and not out["criticalBelow7_5"]
    return out
