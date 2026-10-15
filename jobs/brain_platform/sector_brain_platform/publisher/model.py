"""Publisher V1 vocabulary: modes, results, reason codes, the artifact envelope constants."""
from __future__ import annotations

from enum import Enum

ENVELOPE_ID = "publish-artifact-v1"            # one section (one schema, one scope)
ENVELOPE_V2 = "publish-artifact-v2"            # one logical artifact with several sections: ONE plan, ONE publication record
LINEAGE_ID = "brain-lineage-v1"
PUBLISHER_IDENTITY = "orchestrator-publisher"      # an identity CLASS, never a credential or account name
DEFAULT_SCOPE = "default"


class PublisherMode(Enum):
    """There is deliberately NO live member. A mode that can mutate production does not exist in this code base yet; adding one is the
    separately approved cutover change (docs/architecture/publisher/PUBLISHER_V1_CUTOVER_REQUIREMENTS.md)."""
    SHADOW = "SHADOW"          # evaluate, persist artifact + publication history, hand the plan to the ShadowSink
    DRY_RUN = "DRY_RUN"        # evaluate only: no history writes, no sink call


class Result(str, Enum):
    SKIP = "SKIP"                              # verified output fingerprint equals the baseline: nothing to publish
    SHADOW_READY = "SHADOW_READY"              # valid and changed: the atomic plan was rendered; NOT sent anywhere live
    REJECTED = "REJECTED"                      # identity / schema / authorization / lifecycle policy refused it
    FAILED_VALIDATION = "FAILED_VALIDATION"    # structurally invalid (shape, lineage, values, fingerprint)
    # No PUBLISHED member: shadow mode must never claim a publication.


RECORD_STATUS = {Result.SHADOW_READY: "SHADOW", Result.SKIP: "SKIPPED_UNCHANGED", Result.REJECTED: "REJECTED", Result.FAILED_VALIDATION: "REJECTED"}

REVIEW_STATUSES = ("UNREVIEWED", "PARTIAL", "REVIEWED", "NOT_APPLICABLE")
FRESHNESS_STATUSES = ("FRESH", "STALE", "EXPIRED", "UNAVAILABLE", "UNKNOWN")
OPS = ("SET", "DELETE")

# code -> Result class. One table so a reason can never be reported under two results.
CODES = {
    # shape / structure -> FAILED_VALIDATION
    "MALFORMED": Result.FAILED_VALIDATION, "LINEAGE_MISSING": Result.FAILED_VALIDATION, "LINEAGE_INCOMPLETE": Result.FAILED_VALIDATION,
    "INVALID_PATH": Result.FAILED_VALIDATION, "OVERLAPPING_PATHS": Result.FAILED_VALIDATION, "OVERSIZE": Result.FAILED_VALIDATION,
    "NULL_VALUE": Result.FAILED_VALIDATION, "NULL_IN_VALUE": Result.FAILED_VALIDATION, "EMPTY_VALUE": Result.FAILED_VALIDATION,
    "ILLEGAL_KEY": Result.FAILED_VALIDATION, "NON_FINITE": Result.FAILED_VALIDATION, "INVALID_DELETE": Result.FAILED_VALIDATION,
    "INVALID_LIFECYCLE": Result.FAILED_VALIDATION, "INVALID_STATUS": Result.FAILED_VALIDATION, "INVALID_FRESHNESS": Result.FAILED_VALIDATION,
    "FRESHNESS_MISSING": Result.FAILED_VALIDATION, "STATUS_INCONSISTENT": Result.FAILED_VALIDATION, "FINGERPRINT_MISMATCH": Result.FAILED_VALIDATION,
    "RELEASE_UNRESOLVED": Result.FAILED_VALIDATION, "VALUE_TYPE": Result.FAILED_VALIDATION, "ARTIFACT_REF_INVALID": Result.FAILED_VALIDATION,
    # identity / authorization / policy -> REJECTED
    "UNKNOWN_BRAIN": Result.REJECTED, "IDENTITY_MISMATCH": Result.REJECTED, "UNKNOWN_SCHEMA": Result.REJECTED, "SCHEMA_BRAIN_MISMATCH": Result.REJECTED,
    "PATH_NOT_AUTHORIZED": Result.REJECTED, "CROSS_DOMAIN_PATH": Result.REJECTED, "RESERVED_PATH": Result.REJECTED,
    "DELETE_NOT_PERMITTED": Result.REJECTED, "LIFECYCLE_NOT_AUTHORIZED": Result.REJECTED, "ARTIFACT_ID_CONFLICT": Result.REJECTED,
    "ARTIFACT_OLDER_THAN_BASELINE": Result.REJECTED, "BASELINE_ORDER_UNKNOWN": Result.REJECTED, "ARTIFACT_FROM_FUTURE": Result.REJECTED,
    "BRAIN_NODE_REPLACEMENT": Result.REJECTED, "NAMESPACE_VIOLATION": Result.REJECTED, "ARTIFACT_NOT_FOUND": Result.REJECTED,
    "ARTIFACT_HASH_MISMATCH": Result.REJECTED, "ARTIFACT_BINDING_MISMATCH": Result.REJECTED,
    "PLATFORM_DERIVED_PATH": Result.REJECTED, "SET_DELETE_CONFLICT": Result.REJECTED, "DELETE_REASON_INVALID": Result.REJECTED,
    "SECTION_NOT_ALLOWED": Result.REJECTED, "DUPLICATE_SECTION": Result.FAILED_VALIDATION, "PROJECTION_CONFLICT": Result.REJECTED,
}


class Violation(dict):
    """{code, detail, path?}. A dict so it serialises into the publication record unchanged."""

    def __init__(self, code: str, detail: str, path: str | None = None):
        assert code in CODES, code
        super().__init__(code=code, detail=detail)
        if path is not None:
            self["path"] = path


class Rejected(Exception):
    """Raised inside a validation stage; carries every violation found IN THAT STAGE. Later stages are not run."""

    def __init__(self, violations: list[Violation]):
        super().__init__("; ".join(f"{v['code']}: {v['detail']}" for v in violations))
        self.violations = violations

    @property
    def result(self) -> Result:
        # REJECTED outranks FAILED_VALIDATION if a stage produced both
        return Result.REJECTED if any(CODES[v["code"]] is Result.REJECTED for v in self.violations) else Result.FAILED_VALIDATION


class LiveCapabilityRefused(TypeError):
    """The shadow Publisher was handed something that could mutate a live database."""
