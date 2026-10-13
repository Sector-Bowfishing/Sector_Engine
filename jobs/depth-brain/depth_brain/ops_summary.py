"""Engine-side Ops summary for the Depth registry node (`/brains/depth`). Pure; every number is computed from the candidate manifest,
the research-maturity inputs and the run itself - nothing is hardcoded for Ops to echo.

Ops owns presentation; this module only makes the canonical truth available in fields Ops already types
(`blockers[]`, `readinessCounts`, `breakdowns{str:{str:num}}`) plus additive objects (`fleet`, `research`, `orchestration`, ...).
`research.maturity` is a RESEARCH number: `official` is always false and `scoreStatus` is NOT_ESTABLISHED (no /scores/depth exists)."""
from __future__ import annotations

from collections import Counter

from . import contract as C
from . import maturity as M


def primary_blocker(fm: dict) -> str:
    return (f"datum coverage: {fm['plausibleBlockedByDatum']} lakes with an acceptable pool and a verified level binding lack a provable "
            f"datum relationship; only {fm['shiftPossible']} of {fm['totalLakes']} lakes have a defensible shift")


def registry_extras(manifest: dict, live_lake_states: int, rep: dict | None = None, inputs: dict | None = None) -> dict:
    cands = manifest["candidates"]
    ev = M.evaluate(manifest, inputs)
    fm = ev["fleet"]
    awaiting = max(0, fm["shiftPossible"] - live_lake_states)
    ab = [x for x in cands if x["evidence"]["tier"] in ("A", "B")]
    blockers = [
        primary_blocker(fm),
        f"Lake fleet-state expansion: {awaiting} defensible-shift lakes await a live Lake Brain state ({live_lake_states} live)",
        "Field validation not started (preregistered, tooling ready); validation NOT_VALIDATED",
        f"Licensing: {fm['tierAB'] - fm['licenceAllowedAB']} of {fm['tierAB']} tier A/B contour lakes lack customer-derived-use permission",
        f"Survey reference pools unverified or unvalidated: effective zones withheld for {fm['referenceZoneLakes'] - fm['effectiveZoneEligible']} contour lakes",
        "Orchestration not started (not approved for scheduling); no official score (shadow)",
    ]
    return {
        "directoryLakeCount": fm["totalLakes"],
        "fleet": {k: fm[k] for k in ("totalLakes", "shiftPossible", "pilotVerified", "highConfidence", "mediumConfidence", "blocked", "verifiedDatum",
                                      "inferredOperatorSystem", "plausibleBlockedByDatum", "tierAB", "referenceZoneLakes", "effectiveZoneEligible")},
        "breakdowns": {
            "rollout": dict(Counter(x["rollout"] for x in cands)),
            "datumStatus": dict(Counter(x["datum"]["status"] for x in cands)),
            "evidenceTier": dict(Counter(x["evidence"]["tier"] for x in cands)),
            "contourLicence": {"customerDerivedAllowed": fm["licenceAllowedAB"], "notAllowed": fm["tierAB"] - fm["licenceAllowedAB"]},
        },
        "research": {"maturity": ev["overall"], "official": False, "rubricVersion": ev["rubricVersion"], "criticalBelowThreshold": ev["criticalBelowThreshold"],
                     "meetsProductionPolicy": ev["meetsProductionPolicy"],
                     "note": "research-only rubric; Depth has no official score and no /scores/depth node"},
        "scoreStatus": "NOT_ESTABLISHED",
        "shadow": True,
        "primaryBlocker": primary_blocker(fm),
        "lakeDependency": {"liveLakeStates": live_lake_states, "defensibleShiftLakes": fm["shiftPossible"], "awaitingLakeBrain": awaiting,
                           "note": "Lake Brain owns the level; Depth consumes states/lake"},
        "orchestration": {"status": "NOT_STARTED", "registered": False, "scheduled": False, "note": "shadow CLI only"},
        "fieldValidation": {"status": "NOT_STARTED", "plan": "docs/brains/depth/DEPTH_FIELD_VALIDATION_PLAN.md"},
        "contractVersion": C.STATE_SCHEMA,
        "manifestVersion": manifest.get("manifestVersion"),
        "lastDryRun": {"evaluated": (rep or {}).get("evaluated"), "unavailable": (rep or {}).get("unavailable")} if rep else None,
        "statusBasis": ("Shadow foundation: effective-depth shift only. No official score, no field validation, not scheduled. "
                        f"{fm['shiftPossible']} of {fm['totalLakes']} lakes have a defensible shift; {live_lake_states} have a live Lake Brain level."),
        "blockers": blockers,
    }
