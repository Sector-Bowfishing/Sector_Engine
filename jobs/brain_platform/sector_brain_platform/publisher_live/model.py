"""Live vocabulary. Kept separate from the SHADOW `Result` on purpose: the shadow enum has no PUBLISHED member and must never gain one."""
from __future__ import annotations

from enum import Enum


class LiveResult(str, Enum):
    PUBLISHED = "PUBLISHED"                      # applied, read back, heads advanced
    RECOVERED = "RECOVERED"                      # an earlier attempt had applied it; verified by readback and finalised (idempotent retry)
    SKIP = "SKIP"                                # unchanged against the baseline: nothing written, no score signal
    REJECTED = "REJECTED"                        # identity / schema / path / lifecycle policy (from the shared validators)
    FAILED_VALIDATION = "FAILED_VALIDATION"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"            # no LiveAuthorization for this Brain (fail closed)
    BASELINE_UNRECONCILED = "BASELINE_UNRECONCILED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"  # live state is not what the baseline says (someone else wrote, or an interrupted publication)
    LOCK_BUSY = "LOCK_BUSY"
    APPLY_FAILED = "APPLY_FAILED"                # definitive: nothing (or only non-authoritative chunks) landed; previous release stays authoritative
    READBACK_MISMATCH = "READBACK_MISMATCH"      # applied but the authoritative read disagrees: the Brain is QUARANTINED
    QUARANTINED = "QUARANTINED"
    ROLLED_BACK = "ROLLED_BACK"


# Scientific-eligibility lane for LIVE publication. A structurally valid artifact whose lifecycle is RESEARCH or SHADOW is experimental or candidate output and is NEVER written to
# canonical Brain intelligence; BLOCKED and RETIRED are not publishable states either. (The shadow lane keeps recording such artifacts; this only guards the live one.)
LIVE_LIFECYCLES = ("PROFILED", "CALIBRATION", "PRODUCTION_READY", "PRODUCTION", "DEGRADED")

# RTDB publication-record statuses (live). SHADOW's "SHADOW" never appears in a live database.
COMPLETE, PARTIAL = "COMPLETE", "PARTIAL"
LIVE_MODE = "LIVE"


class LiveError(RuntimeError):
    pass


class NotAuthorized(LiveError):
    pass


class RtdbDefiniteFailure(LiveError):
    """The write was refused or failed in a way that proves nothing was applied (e.g. HTTP 4xx before commit)."""


class RtdbAmbiguousFailure(LiveError):
    """Transport/5xx after the request left: the update MAY have been applied. Never assume either way; read back."""


class NoRollbackTarget(LiveError):
    pass
