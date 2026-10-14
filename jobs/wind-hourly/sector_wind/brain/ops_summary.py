"""Wind progress summary for Sector Ops (`wind-ops-summary-v1`) - PREPARED, NOT PUBLISHED.

Engine owns the truth, Ops owns presentation: every value here is derived from an input (the reliability audit, the canonical scorer result, the
geometry manifest, the frozen contract constants); nothing is typed in. A missing input yields null + a reason, never 0 or 'ok'.
Proposed Engine path (needs the prerequisite branch + a Sector_Ops schema entry): `/brains/wind/opsSummary` (registry, additive) mirrored to
`/control/overview/brains/wind.opsSummary`. Ops renders it verbatim."""
from __future__ import annotations

from datetime import datetime, timezone

from . import contract as C
from . import exposure as EX
from . import fleet as FL
from . import tonight as TN

SCHEMA = "wind-ops-summary-v1"
CATEGORIES = ("TIME", "FIELD", "PREREQUISITE_BRANCH", "MICHAEL", "LAKE_IDENTITY", "VALIDATION")


def _unknown(reason):
    return {"value": None, "unknownReason": reason}


def coverage_from_manifest(manifest: dict | None = None, readiness: list[dict] | None = None) -> dict:
    """Counts straight from the committed manifest (tiers, blockers); the six-way category split needs the readiness rows when supplied."""
    m = manifest or FL.load_manifest()
    lakes = list(m["lakes"].values())
    out = {"directoryLakes": len(lakes), "audited": sum(v["tier"] == "AUDITED" for v in lakes), "estimated": sum(v["tier"] == "ESTIMATED" for v in lakes),
           "pointOnly": sum(v["tier"] == "POINT_ONLY" for v in lakes), "blocked": sum(bool(v["blockers"]) and v["tier"] in ("AUDITED", "ESTIMATED") for v in lakes),
           "labelEligible": sum(FL.exposure_allowed(v) for v in lakes), "customerVisibleExposure": 0,
           "note": "eligible = may carry conservative bank words if/when released; nothing is customer-visible"}
    if readiness:
        from collections import Counter
        c = Counter(r["category"] for r in readiness)
        out["categories"] = {k: c.get(k, 0) for k in ("AUDITED", "ESTIMATED_HIGH_GEOMETRY", "ESTIMATED_MEDIUM_GEOMETRY", "LOW_GEOMETRY", "POINT_ONLY", "NO_GEOMETRY", "BLOCKED")}
    return out


def build(now: datetime, *, rescore: dict | None, reliability: dict | None, frozen_score: dict | None, coverage: dict | None, field: dict | None = None,
          dual_logging: str = "NOT_STARTED", customer_switch: str = "NOT_APPROVED", prerequisite_branch: dict | None = None, tests: dict | None = None) -> dict:
    cert = bw = None
    if rescore:
        c = rescore["certification"]
        cert = {"value": c["new"], "raw": c["newRaw"], "basis": "COMPUTED_FROM_FROZEN_RUBRIC_V1", "computedAt": rescore.get("computedAt"),
                "caps": [x["cap"] for x in c["caps"]], "capRules": [x["rule"] for x in c["caps"]],
                "dimensions": {k: {"points": v["points"], "weight": v["weight"]} for k, v in c["dimensions"].items()},
                "changedSincePublished": {k: v for k, v in c["dimensionsChanged"].items()} if frozen_score and frozen_score.get("value") is not None else None}
        bw = {"value": rescore["bwis"]["new"], "total": rescore["bwis"]["newTotal"], "definition": "BWIS v1 (frozen)"}
    published = None
    if frozen_score:
        published = {"value": frozen_score.get("value"), "basis": frozen_score.get("basis"), "updatedAt": frozen_score.get("updatedAt"),
                     "differsFromComputed": bool(cert and frozen_score.get("value") is not None and abs(cert["value"] - frozen_score["value"]) > 1e-9),
                     "explanation": "the published block can differ from the canonical scorer: the scorer result moves with valid live days, while the published value comes from the frozen-scores.json baked into the deployed brain-orchestrator image. The refresh is approved and the generated file is committed on feat/wind-brain-adoption; it becomes durable only once the orchestrator lineage carries it."}
    rel = _unknown("no reliability audit supplied")
    if reliability:
        s = reliability["summary"] if "summary" in reliability else reliability
        valid_days = [d["date"] for d in reliability.get("days", []) if d.get("valid")]
        rel = {"asOf": s["asOf"], "validArchiveDays": s["validArchiveDays"], "validBrainPublishDays": s["validBrainPublishDays"], "target": 30,
               "lastValidArchiveDay": valid_days[-1] if valid_days else None, "invalidArchiveDays": s["invalidArchiveDays"],
               "executions": s["executions"], "failedExecutions": s["failedExecutions"], "staleStates": s["staleStatesLogged"],
               "freshnessHoursAfterInit": s["freshnessHoursAfterInit"], "projectedArchiveGate": s["projectedArchiveGate"],
               "projectedBrainPublishGate": s["projectedBrainPublishGate"], "projectionAssumption": s["projectionAssumption"],
               "progress": f"{s['validArchiveDays']} / 30 valid archive days"}
    blockers = [
        {"id": "live-days", "category": "TIME", "text": "30 valid live archive days not yet reached", "since": None},
        {"id": "h2", "category": "TIME", "text": f"H2 holdout sealed until {C.iso(C.H2_SEALED_UNTIL)[:10]}"},
        {"id": "bank-pairs", "category": "FIELD", "text": "no physical bank-pair observations (certification dimensions 6 and 7 earn 0)"},
        {"id": "over-water", "category": "FIELD", "text": "no over-water wind reference (certification cap 7)"},
        {"id": "customer-provider", "category": "MICHAEL", "text": "customer provider switch and ESTIMATED visibility are undecided"},
        {"id": "identity", "category": "LAKE_IDENTITY", "text": "six audited lakes carry a lake-identity risk (Lake Brain)"},
        {"id": "validation-v2", "category": "VALIDATION", "text": "independent bank validation v2 and rule set v2 not yet evidenced"}]
    if prerequisite_branch is not None and not prerequisite_branch.get("merged", False):
        blockers.append({"id": "prereq-branch", "category": "PREREQUISITE_BRANCH", "text": f"{prerequisite_branch.get('name')} not merged; Wind cannot be wired, published or deployed"})
    return {
        "schema": SCHEMA, "generatedAt": C.iso(now), "brainId": C.BRAIN_ID, "brainVersion": C.BRAIN_VERSION,
        "lifecycle": {"status": "CALIBRATION", "candidatePromoted": False, "shadow": True},
        "certification": cert or _unknown("scorer result not supplied"), "bwis": bw or _unknown("scorer result not supplied"), "publishedScore": published or _unknown("no published score block"),
        "reliability": rel, "coverage": coverage or _unknown("no manifest supplied"),
        "providers": {"customer": {"id": "open-meteo-best-match", "status": "ACTIVE_PRODUCTION"}, "candidate": {"id": "nbm-v5.0 + rtma-ru", "status": "RESEARCH_CANDIDATE", "promoted": False},
                      "dualLogging": dual_logging, "customerSwitch": customer_switch},
        "tonightContract": {"schema": TN.SCHEMA, "rulesVersion": EX.RULES_VERSION, "rulesFingerprint": EX.rules_fingerprint(), "published": False,
                            "withheldClaims": ["layDown", "rising", "gust", "overWaterSpeed", "directionBelow5mph"]},
        "fieldValidation": field or {"status": "NOT_STARTED", "pairsCollected": 0, "target": {"pairs": 40, "independentLakes": 2, "quadrants": 3}, "preregistration": "WIND_BANK_VALIDATION_V2_PREREG.md"},
        "h2": {"status": "SEALED", "sealedUntil": C.iso(C.H2_SEALED_UNTIL), "runnerHasRun": False, "oneShot": True},
        "tests": tests or _unknown("not supplied"), "blockers": blockers, "blockerCategories": list(CATEGORIES),
    }
