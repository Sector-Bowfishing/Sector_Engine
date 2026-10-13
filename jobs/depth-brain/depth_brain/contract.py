"""Depth Brain contract constants (Sector Brain Platform v1; docs/brains/BRAIN_PLATFORM_CONTRACT.md).

Slot `depth` is reserved by the platform contract (section 2): `/lakes/{k}/states/depth`,
`/lakeFleet/{k}/readiness/depth`, snapshot field `depth`. No new path convention is invented here.

SIGN CONVENTION (used everywhere): shiftFt = currentLevelFt - referencePoolFt.
  shiftFt < 0  -> the lake is LOWER than the reference pool; reference depths are SHALLOWER by |shiftFt|.
  shiftFt > 0  -> the lake is HIGHER; reference depths are DEEPER by shiftFt.
  effective depth of a point whose reference depth is d  =  d + shiftFt   (a depth <= 0 means dry).
This is the same number as Lake Brain's `differenceFromNormalPoolFt` when the reference is the directory full pool."""
from __future__ import annotations

from datetime import datetime, timezone

BRAIN_ID = "depth"
SLOT = "depth"
SNAPSHOT_FIELD = "depth"
DISPLAY_NAME = "Depth"
DOMAIN = "condition"
QUESTION = "How has the depth of the water we care about shifted from its reference condition?"
BRAIN_VERSION = "depth-brain-0.1.0-shadow"
SCHEMA_VERSION = 1
STATE_SCHEMA = "sector-brain-depth-state-v1"
MODEL_ID = "effective-depth-shift-v1"
JOB_ID = "depth-brain"
STALENESS_MODEL = "FINGERPRINT"          # a pure function of the Lake Brain state + the static manifest
DEPENDS_ON = ["lake-brain"]

READINESS_DEFINITIONS = {
    "DISCOVERED": "In the canonical lake directory; Depth has evaluated no reference pool or datum for it.",
    "PROFILED": "Reference pool and the datum relationship to the level source are established; a shift can be computed once Lake Brain publishes a direct level.",
    "CALIBRATION": "Shadow shift published from a live, direct Lake Brain level; shift arithmetic tested, NOT field-validated.",
    "BETA": "Not used yet.",
    "VALIDATED": "Not reached: needs field validation of effective depth on known flats (docs/brains/depth/DEPTH_FIELD_VALIDATION_PLAN.md).",
    "PRODUCTION": "Not reached: Depth is shadow/internal only; no customer surface consumes it.",
    "DEGRADED": "A profiled lake whose current Lake Brain input is stale or unavailable this run.",
    "BLOCKED": "A shift cannot be defended (datum incompatible or unknown, no usable reference pool, or no direct level source).",
}
READINESS = tuple(READINESS_DEFINITIONS)
HEALTH = ("HEALTHY", "WARNING", "DEGRADED", "FAILED", "UNKNOWN", "NOT_CONFIGURED")

# State kind (platform vocabulary). A shift from a DIRECT observed level is `observed`; anything else is `unavailable`.
KINDS = {"observed": "shift = direct observed level minus a datum-compatible reference pool",
         "unavailable": "no defensible shift this run (see limitations / reasons); values absent"}

# Evidence tiers (Phase 15). Higher quality ALWAYS overrides lower quality.
TIERS = ("A", "B", "C", "D", "UNKNOWN")
TIER_MEANING = {
    "A": "authoritative measured/surveyed depth (fine-interval contours or survey tables, whole lake)",
    "B": "trusted contour/depth dataset (coarser interval or partial coverage that still supports stated bands)",
    "C": "limited/partial authoritative evidence (binary navigation contour, partial survey, measured hypsometry)",
    "D": "proxy/model context only (never depth, never scored)",
    "UNKNOWN": "no defensible depth evidence",
}
# Research tier (docs/research/depth-brain fleet matrix) -> Depth Brain tier. Traceability is kept in the manifest.
RESEARCH_TIER_MAP = {"A": "A", "B": "B", "B-partial": "C", "B-binary": "C", "C": "C", "D": "D", "U": "UNKNOWN"}

EVIDENCE_KINDS = ("measured", "contour", "modeled", "proxy", "unknown")        # zone evidence (Phase 16)
SHIFT_EVIDENCE_KIND = "levelDelta"                                            # effectiveDepth.evidenceKind for a pure shift

MODES = ("shiftOnly", "zoned", "unknown")

# ── Level input rules ───────────────────────────────────────────────────────────────────────────
ALLOWED_LEVEL_CAPABILITIES = ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE")   # a NEARBY_GAUGE_PROXY never yields a shift
LEVEL_FRESH_HOURS = 6.0               # observation older than this -> evidenceStale (state still published, flagged)
LEVEL_MAX_AGE_HOURS = 48.0            # older than this -> no shift (unavailable)
MAX_PLAUSIBLE_SHIFT_FT = 80.0         # |shift| above this means a datum/unit/reference error, never a real drawdown
LAKE_DELTA_DISAGREE_FT = 0.15         # Depth vs Lake Brain differenceFromNormalPoolFt, same reference
REFERENCE_CONF_ALLOWED = ("high", "medium")   # `low` references (natural-lake surfaces, shorthand) never yield a shift

# ── Uncertainty (ft). Components add in quadrature. Values come from the research sigma propagation
#    (DEPTH_BRAIN_EFFECTIVE_DEPTH_RESEARCH.md); some are ASSUMED, not measured, and are flagged in the state. ─
SIGMA_POOL = {"high": 0.25, "medium": 1.0, "low": 3.0}
SIGMA_LEVEL = {"DIRECT_OPERATOR_POOL": 0.1, "DIRECT_LAKE_GAUGE": 0.15}
SIGMA_DATUM = {"SAME_SOURCE": 0.0, "SAME_OPERATOR_SYSTEM": 0.1, "SAME_DATUM": 0.1, "CONVERTED": 0.3}
SIGMA_ASSUMED = ("pool", "level", "datum")
CONF_HIGH_MAX_SIGMA = 0.5
CONF_MEDIUM_MAX_SIGMA = 1.2

# ── Contour interpolation (feet RMS), measured in the research (contour_interval_error.json) ─────────────
INTERVAL_RMS_FT = {1: 0.28, 2: 0.28, 5: 1.3, 10: 2.8}
EDGES_FT = (3.0, 6.0, 10.0)           # bowfishing bands: under 3, 3-6, 6-10, deeper
MAX_INTERVAL_FOR_ARBITRARY_EDGE_FT = 3.0

SCORE_NOTE = "Depth has NO official score. The research-only rubric (docs/research/depth-brain on docs/depth-brain-research) is separate from live Brain maturity."


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if s is None:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
