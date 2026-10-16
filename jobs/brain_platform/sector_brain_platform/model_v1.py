"""Sector Brain Model v1 — the shared closed vocabularies and pure validators (docs/brains/platform/).

Additive: nothing here changes a live registry value or a published node. It defines the canonical semantics, the
legacy -> v1 mapping, and the invariants every Brain and the platform publisher can test against.

Two axes that must never be conflated:
  claim LEVEL     (1 provider/observed, 2 deterministic derivation, 3 Sector-derived/predictive) - WHAT KIND of claim it is; fixed by construction.
  claim MATURITY  (NOT_VALIDATED ... VALIDATED)                                                  - HOW FAR the claim has been tested; changes over time.
Validation never changes a claim's level.
"""
from __future__ import annotations

MODEL_VERSION = "sector-brain-model-v1"

# ---- claims ---------------------------------------------------------------------------------------------------------
CLAIM_LEVELS = (1, 2, 3)
CLAIM_LEVEL_NAMES = {1: "PROVIDER_OBSERVED", 2: "DETERMINISTIC_DERIVATION", 3: "SECTOR_DERIVED_PREDICTIVE"}

CLAIM_MATURITY = ("NOT_ASSESSED", "UNAVAILABLE", "NOT_OBSERVABLE", "PROVIDER_VERIFIED", "DETERMINISTIC_VERIFIED", "DESK_VALIDATED",
                  "PROPOSED", "CALIBRATION", "NOT_VALIDATED", "VALIDATED", "WITHHELD")
# Which maturities make sense at which level. A claim may use only a subset; it need not use them all. The point is that a
# Level 1 claim cannot be "CALIBRATION" (a provider reading is not calibrated by us) and a Level 3 claim cannot be PROVIDER_VERIFIED.
# The "not a verdict" states (the claim was not assessed / cannot be / is held back) are legal at every level.
_NO_VERDICT = ("NOT_ASSESSED", "UNAVAILABLE", "NOT_OBSERVABLE", "WITHHELD")
MATURITY_BY_LEVEL = {
    1: _NO_VERDICT + ("PROVIDER_VERIFIED",),
    2: _NO_VERDICT + ("DETERMINISTIC_VERIFIED", "DESK_VALIDATED", "VALIDATED"),
    3: _NO_VERDICT + ("DESK_VALIDATED", "PROPOSED", "CALIBRATION", "NOT_VALIDATED", "VALIDATED"),
}
# Maturities that certify a claim as customer-grade evidence (used by minimum-maturity dependency checks).
MATURITY_RANK = {"NOT_ASSESSED": 0, "UNAVAILABLE": 0, "NOT_OBSERVABLE": 0, "WITHHELD": 0, "NOT_VALIDATED": 1, "PROPOSED": 2,
                 "CALIBRATION": 3, "DESK_VALIDATED": 4, "PROVIDER_VERIFIED": 5, "DETERMINISTIC_VERIFIED": 5, "VALIDATED": 6}

VALIDATION_STATUS = ("NOT_STARTED", "NOT_VALIDATED", "CALIBRATION", "DESK_VALIDATED", "VALIDATED", "FAILED", "WITHHELD")

# ---- unknown policy ---------------------------------------------------------------------------------------------------
# UNKNOWN is a valid answer. It is not 0, false, poor or failed. These are the distinguishable ways to say "no value".
UNKNOWN_KINDS = ("UNKNOWN", "NOT_ASSESSED", "UNAVAILABLE", "NOT_OBSERVABLE", "WITHHELD")

# ---- Brain lifecycle (brain-level; NOT claim maturity) -----------------------------------------------------------------
LIFECYCLE = ("RESEARCH", "PROFILED", "SHADOW", "CALIBRATION", "PRODUCTION_READY", "PRODUCTION")
# Off-ladder conditions are kept out of the ladder, as in the live readiness vocabulary.
LIFECYCLE_CONDITIONS = ("BLOCKED", "DEGRADED", "RETIRED")
# Legacy -> v1. LOSSY by design and therefore reported, never silently applied: see LIFECYCLE_MODEL.md section 4.
LEGACY_LIFECYCLE_MAP = {
    "DISCOVERED": "RESEARCH", "IN_PROGRESS": "RESEARCH", "RESEARCH": "RESEARCH", "RESEARCH_CANDIDATE": "RESEARCH",
    "PROFILED": "PROFILED",
    "SHADOW": "SHADOW", "CANDIDATE": "SHADOW",
    "CALIBRATION": "CALIBRATION", "BETA": "CALIBRATION", "REVIEW": "CALIBRATION",
    "VALIDATED": "PRODUCTION_READY", "PRODUCTION_READY": "PRODUCTION_READY",
    "PRODUCTION": "PRODUCTION", "ACTIVE_PRODUCTION": "PRODUCTION", "PRODUCTION_EVIDENCE": "PRODUCTION",
}
# Legacy values whose mapping loses information and needs a human look before any live migration.
LEGACY_LIFECYCLE_AMBIGUOUS = ("BETA", "REVIEW", "IN_PROGRESS", "VALIDATED", "PRODUCTION_EVIDENCE")

# ---- execution ------------------------------------------------------------------------------------------------------
# `executionType` is WHY a Brain runs. It is deliberately not `executionMode`, which is the existing /jobs field
# (SCHEDULED | MANUAL | EVENT_DRIVEN | DISABLED) describing HOW a job record is triggered.
EXECUTION_TYPES = ("PROVIDER_INGESTION", "DEPENDENCY_DRIVEN", "PROSPECTIVE_VALIDATION", "MAINTENANCE", "MANUAL_SHADOW")
# A recurring schedule survives only for one of these reasons (EXECUTION_MODEL.md section 3).
SCHEDULE_REASONS = {"PROVIDER_INGESTION": "provider changes on cadence", "PROSPECTIVE_VALIDATION": "timed snapshots are the evidence",
                    "TIME_INVALIDATION": "state becomes invalid purely from elapsed time", "MAINTENANCE": "cheap health/maintenance"}
JOB_EXECUTION_MODES = ("SCHEDULED", "MANUAL", "EVENT_DRIVEN", "DISABLED")        # the existing /jobs vocabulary, unchanged

# ---- dependencies ---------------------------------------------------------------------------------------------------
DEPENDENCY_REQUIREMENT = ("REQUIRED", "OPTIONAL")
DEPENDENCY_FALLBACK = ("DEGRADE", "WITHHOLD", "SKIP", "USE_LAST_GOOD")

# ---- scoring semantics (names, not values) --------------------------------------------------------------------------
# Six different things people call "score". Never publish one of them under the bare word.
SCORE_FIELDS = {
    "researchMaturity": "research maturity: how far the science/evidence has progressed (rubric-defined, owner-assessed)",
    "underlyingScore": "computed capability before any gate cap (today's `uncapped`)",
    "canonicalScore": "the published truth at /scores/{brainId} (today's `value`)",
    "displayedScore": "what Ops shows: canonical after gate caps (equals canonicalScore unless an Ops-only cap is documented)",
    "claimMaturity": "per-claim maturity summary (counts by CLAIM_MATURITY)",
    "customerReadiness": "whether customers consume this Brain's output: NONE | INTERNAL | PILOT | CUSTOMER",
}
CUSTOMER_READINESS = ("NONE", "INTERNAL", "PILOT", "CUSTOMER")
SCORE_STATUS = ("COMPUTED", "FROZEN", "UNSCORED", "WITHHELD")
PRODUCTION_OVERALL_MIN = 8.0
PRODUCTION_CRITICAL_MIN = 7.5

# ---- helpers ------------------------------------------------------------------------------------------------------------


class ModelError(ValueError):
    pass


def validate_claim(claim: dict) -> dict:
    """A claim record: {id, level, maturity, ...}. Raises ModelError when the two axes are conflated or out of vocabulary."""
    lvl, mat = claim.get("level"), claim.get("maturity")
    if lvl not in CLAIM_LEVELS or isinstance(lvl, bool):
        raise ModelError(f"claim {claim.get('id')!r}: level must be one of {CLAIM_LEVELS}, got {lvl!r}")
    if mat not in CLAIM_MATURITY:
        raise ModelError(f"claim {claim.get('id')!r}: maturity {mat!r} is not in the closed vocabulary")
    if mat not in MATURITY_BY_LEVEL[lvl]:
        raise ModelError(f"claim {claim.get('id')!r}: maturity {mat} is not meaningful at level {lvl}")
    return claim


def advance_maturity(claim: dict, new_maturity: str) -> dict:
    """Return the claim with a new maturity. The level never changes: validation does not promote a claim between levels."""
    out = validate_claim({**claim, "maturity": new_maturity})
    if out["level"] != claim["level"]:
        raise ModelError("claim level is immutable")
    return out


def maturity_summary(claims: list[dict]) -> dict:
    """{maturity: count} over validated claims, for the compact control summary."""
    out: dict[str, int] = {}
    for c in claims:
        validate_claim(c)
        out[c["maturity"]] = out.get(c["maturity"], 0) + 1
    return out


def map_legacy_lifecycle(value: str) -> tuple[str, bool]:
    """-> (v1 lifecycle or condition, ambiguous). ValueError for a value in neither vocabulary (never guessed)."""
    if value in LIFECYCLE or value in LIFECYCLE_CONDITIONS:      # off-ladder conditions (BLOCKED/DEGRADED/RETIRED) pass through
        return value, False
    if value not in LEGACY_LIFECYCLE_MAP:
        raise ModelError(f"unknown lifecycle value {value!r}")
    return LEGACY_LIFECYCLE_MAP[value], value in LEGACY_LIFECYCLE_AMBIGUOUS


def lifecycle_index(value: str) -> int:
    return LIFECYCLE.index(value)


def production_ready(overall: float | None, critical: dict[str, float | None]) -> tuple[bool, list[str]]:
    """The production policy, unchanged: overall >= 8.0 AND every required critical dimension >= 7.5. Unknown never passes."""
    why = []
    if overall is None:
        why.append("overall maturity unknown")
    elif overall < PRODUCTION_OVERALL_MIN:
        why.append(f"overall {overall} < {PRODUCTION_OVERALL_MIN}")
    for name, v in sorted(critical.items()):
        if v is None:
            why.append(f"critical dimension {name} unknown")
        elif v < PRODUCTION_CRITICAL_MIN:
            why.append(f"critical dimension {name} {v} < {PRODUCTION_CRITICAL_MIN}")
    return (not why), why


def known(value) -> bool:
    """True when a value is a real value. None/absent = unknown. 0 and False are real values and are known."""
    return value is not None


def unknown_marker(kind: str = "UNKNOWN", reason: str | None = None) -> dict:
    if kind not in UNKNOWN_KINDS:
        raise ModelError(f"not an unknown kind: {kind!r}")
    return {"unknown": kind, **({"reason": reason} if reason else {})}


def bounded_workers(requested, n_items: int, cap: int = 16) -> int:
    """A thread/process-pool size that can never be zero (ThreadPoolExecutor(max_workers=0) raises; a runner that computes its worker
    count from a config or an empty work list must clamp). 1 <= result <= cap, and never more workers than items (min 1)."""
    try:
        r = int(requested)
    except (TypeError, ValueError):
        r = 1
    return max(1, min(r if r > 0 else 1, cap, max(1, int(n_items))))
