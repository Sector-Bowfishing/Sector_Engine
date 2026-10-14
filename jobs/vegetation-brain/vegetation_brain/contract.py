"""Vegetation Brain contract constants (Sector Brain Platform v1; docs/brains/BRAIN_PLATFORM_CONTRACT.md).

Slot `vegetation` is reserved by the platform contract (section 2): `/lakes/{k}/states/vegetation`,
`/lakeFleet/{k}/readiness/vegetation`, snapshot field `vegetation`. No new path convention is invented here.

V1 SCOPE: SURFACE-REACHING / SURFACE-VISIBLE aquatic vegetation only. Submerged vegetation is NOT observable at fleet
scale with Sentinel-2 (docs/research/vegetation-brain on branch docs/vegetation-brain-research): it can never be
published as observed. `potentialHabitat` is a different product and always carries potentialOnly=True."""
from __future__ import annotations

from datetime import datetime, timezone

BRAIN_ID = "vegetation"
SLOT = "vegetation"
SNAPSHOT_FIELD = "vegetation"
DISPLAY_NAME = "Vegetation"
DOMAIN = "condition"
QUESTION = "Where is surface-reaching aquatic vegetation, how much, what broad kind, and how old is that observation?"
BRAIN_VERSION = "vegetation-brain-0.3.0-shadow"
SCHEMA_VERSION = 1
STATE_SCHEMA = "sector-brain-vegetation-state-v1"
MODEL_ID = "surface-vegetation-observer-v1"
JOB_ID = "vegetation-brain"
STALENESS_MODEL = "TIME"                # a satellite observation ages; see OBSERVATION_FRESH_DAYS
DEPENDS_ON = ["lake-brain", "water-clarity", "wind", "water-temp", "depth"]   # all OPTIONAL context, none required in V1

# ---------------------------------------------------------------- closed vocabularies
PRESENCE = ("PRESENT", "NOT_OBSERVED", "UNKNOWN")        # NOT_OBSERVED = a valid look found none; UNKNOWN = could not look
BROAD_TYPES = ("FLOATING_LEAF", "FLOATING_MAT", "EMERGENT", "SURFACE_REACHING_MIXED", "UNKNOWN")
# V1 does NOT classify type (no validated classifier): every PRESENT lake is SURFACE_REACHING_MIXED with typeBasis=NOT_CLASSIFIED.
TYPE_BASIS = ("NOT_CLASSIFIED", "CLASSIFIED_VALIDATED")
COVERAGE_CLASSES = ("SPARSE", "MODERATE", "DENSE", "UNKNOWN", "NOT_CALIBRATED")
SEASONAL_STATES = ("EMERGING", "GROWING", "PEAK", "DECLINING", "DORMANT", "UNKNOWN")
EVIDENCE_KINDS = ("SATELLITE_SINGLE_PASS", "SATELLITE_ACCEPTED_PASS", "SATELLITE_PERSISTENCE", "SURVEY", "NONE")
PERSISTENCE = ("MEDIAN_OF_ACCEPTED", "INSUFFICIENT", "NOT_APPLICABLE")
CLOUD_STATES = ("CLEAR", "PARTLY_CLOUDY", "CLOUDY", "UNKNOWN")
VALIDATION_STATES = ("NOT_VALIDATED", "RESEARCH", "CALIBRATION", "PARTIAL", "VALIDATED")

# Reasons a cell/lake is UNKNOWN rather than "no vegetation". Never silently dropped.
REFUSALS = ("CLOUD", "SHADOW", "HAZE", "GLARE", "DARK_WATER", "SHORE_ADJACENT", "INSUFFICIENT_VALID_PIXELS",
            "SCENE_TOO_OLD", "NO_SCENE", "ICE_OR_SNOW", "NO_GEOMETRY", "GEOMETRY_LOW", "TOO_NARROW", "BLOOM_AMBIGUOUS",
            "PASS_NOT_ACCEPTED", "BOTTOM_REFLECTANCE", "CLOUD_OR_HAZE", "UNREADABLE_WATER")
REFUSAL_DOC = {
    "CLOUD": "cloud or cirrus within the cloud standoff", "SHADOW": "cloud shadow",
    "HAZE": "bright open water (SWIR > HAZE_SWIR) that is not a plant spectrum: haze / thin cloud",
    "GLARE": "sun glint or surface roughness in the pixels (SWIR above the glint limit on non-plant water, or Wind disturbance flag)",
    "DARK_WATER": "red and NIR reflectance both below the floor, so the normalized-difference ratio is unstable",
    "SHORE_ADJACENT": "cell touches the polygon edge: bank vegetation and mixed pixels cannot be separated (prereg section 1)",
    "INSUFFICIENT_VALID_PIXELS": "less than MIN_SEEN_FRACTION of the cell was seen",
    "SCENE_TOO_OLD": "only scenes older than MAX_SCENE_AGE_DAYS exist", "NO_SCENE": "no Sentinel-2 scene in the window",
    "ICE_OR_SNOW": "ice/snow class", "NO_GEOMETRY": "registry geometry is null", "GEOMETRY_LOW": "registry geometry confidence LOW",
    "TOO_NARROW": "arm narrower than the observer can resolve", "BLOOM_AMBIGUOUS": "plant spectrum cannot be separated from an algal bloom",
    "PASS_NOT_ACCEPTED": "no scene passed the pass-acceptance rule", "BOTTOM_REFLECTANCE": "shallow bright bottom can mimic a plant spectrum",
    "CLOUD_OR_HAZE": "shared Clarity pass: cloud or haze hid the water (Clarity bundles the two; code 2)",
    "UNREADABLE_WATER": "shared Clarity pass: bank band, beside bridges/docks, or narrow creek (code 1)",
}

# ---------------------------------------------------------------- claim-level maturity (Sector Brain Model v1, directive 2026-10-14)
# One experimental claim must not poison the apparent maturity of the others. Level 1 provider truth, Level 2 deterministic
# derivation, Level 3 Sector-derived intelligence. Values are claim states, not scores.
CLAIM_STATES = ("PROVIDER_VERIFIED", "VERIFIED", "SHADOW", "CALIBRATION", "NOT_VALIDATED", "NOT_ASSESSED", "NOT_OBSERVABLE", "UNAVAILABLE")
CLAIMS = {
    "geometryTier":            {"level": 2, "state": "VERIFIED", "basis": "area/confidence arithmetic over the canonical Lake Registry; unit-tested"},
    "observationAge":          {"level": 2, "state": "VERIFIED", "basis": "date arithmetic; unit-tested"},
    "agencyVegetationObservation": {"level": 1, "state": "NOT_ASSESSED", "basis": "no provider ingestion built; needs Michael's product-slice decision and source terms"},
    "surfaceVegetationPresence": {"level": 3, "state": "NOT_VALIDATED", "basis": "shadow observer; failed lake-level gates on held-out lakes (notes 11, 12)"},
    "surfaceVegetationType":   {"level": 3, "state": "NOT_ASSESSED", "basis": "no validated classifier; broadType is SURFACE_REACHING_MIXED with typeBasis NOT_CLASSIFIED"},
    "coverageDensity":         {"level": 3, "state": "NOT_ASSESSED", "basis": "density gate not passed; counts only"},
    "seasonalState":           {"level": 3, "state": "NOT_VALIDATED", "basis": "back-test did not beat the strengthened baselines (A2)"},
    "potentialHabitat":        {"level": 3, "state": "NOT_ASSESSED", "basis": "needs live Depth (tier A/B/C) and Clarity Secchi; potentialOnly"},
    "submergedVegetation":     {"level": 3, "state": "NOT_OBSERVABLE", "basis": "not observable with Sentinel-2 at fleet scale (research)"},
}

# ---------------------------------------------------------------- readiness (platform ladder + Vegetation meaning)
READINESS_DEFINITIONS = {
    "DISCOVERED": "In the canonical lake directory; no geometry or observation evaluated for Vegetation.",
    "PROFILED": "Registry geometry exists and is usable (not MISSING/LOW); the observer COULD run; nothing has been run.",
    "CALIBRATION": "Offline/shadow observer output exists for the lake; NOT validated against independent truth.",
    "BETA": "Not used yet.",
    "VALIDATED": "Not reached: needs the pre-registered PARTIAL/VALIDATED gates (docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md).",
    "PRODUCTION": "Not reached: Vegetation is shadow/internal only; no customer surface consumes it.",
    "DEGRADED": "An evaluated lake whose latest observation is stale or entirely refused this run.",
    "BLOCKED": "The observer cannot run: geometry missing/LOW or lake too small to resolve.",
}
READINESS = tuple(READINESS_DEFINITIONS)
HEALTH = ("HEALTHY", "WARNING", "DEGRADED", "FAILED", "UNKNOWN", "NOT_CONFIGURED")

# ---------------------------------------------------------------- observer constants
# Production rule constants, copied from jobs/lake-surface/derive_water_surface.py (grass logic identical on main and in the
# live image, feat/clarity-algal-warning @ 03937913).
PLANT_NDVI_MIN = 0.30
HAZE_SWIR = 0.02
SWIR_GLINT_MAX = 0.0215
S2_SCALE, S2_OFFSET_C1 = 0.0001, -0.1       # sentinel-2-c1-l2a only; sentinel-2-l2a (Earth Search) is offset-free
SCL_WATER = 6
SCL_CLOUDY = (0, 1, 3, 8, 9, 10, 11)       # no data, defective, shadow, cloud (med/high), cirrus, snow
SCL_SHADOW, SCL_SNOW = 3, 11
# Observer design (pre-registration section 1)
PX_M = 10.0
CELL_PX = 5                               # 50 m cell
PLANT_FRACTION_MIN = 0.5                  # share of SEEN pixels in a cell that must be plant pixels
MIN_SEEN_FRACTION = 0.5                   # share of the cell's pixels that must be seen at all
DARK_FLOOR = 0.01                         # red and NIR both below this: ratio unstable, pixel excluded
CLOUD_STANDOFF_PX = 6                     # 60 m
PASS_MIN_COVERAGE = 0.50                  # accepted pass: scene must read >= 50 % of the non-plant lake water
PASS_FALLBACK_COVERAGE = 0.25
PERSISTENCE_MIN_SCENES = 3                # median persistence needs >= 3 accepted scenes
PERSISTENCE_WINDOW_DAYS = 21
MAX_SCENE_AGE_DAYS = 21
OBSERVATION_FRESH_DAYS = 14
OBSERVATION_MAX_AGE_DAYS = 45
FORBIDDEN_COMPOSITES = ("max", "second_highest", "votes_ge_2")   # research: precision 0.21 - 0.40; max composites are forbidden in V1
MIN_LAKE_AREA_KM2 = 0.5

# Shared-evidence consumption (one provider ingestion path, many specialist consumers)
SHARED_SOURCE_ID = "clarity-shared-pass"
SHARED_MIN_AREA_KM2 = 0.01              # >= 1 ha of observed grass (after removing the bed-to-bank strip) before a lake is PRESENT
SHARED_BURST_FACTOR = 5.0
SHARED_BURST_MIN_PCT = 5.0

# Observability tiers recomputed from the canonical registry (docs/brains/vegetation/VEGETATION_FLEET_OBSERVABILITY.md)
AREA_HIGH_KM2 = 5.0
AREA_MEDIUM_KM2 = 0.5

# ---------------------------------------------------------------- product language (closed set)
LANGUAGE = {
    "OBSERVED": "Surface vegetation observed",
    "LIKELY": "Likely surface vegetation",
    "POTENTIAL": "Potential vegetation habitat",
    "NONE": "No reliable vegetation observation",
    "NOT_OBSERVED": "No surface vegetation seen on the latest clear look",
}
FORBIDDEN_PHRASES = ("grass is here", "grass here", "hydrilla", "milfoil", "submerged grass", "submerged vegetation here",
                     "submerged vegetation observed", "weeds here", "underwater grass")

SCORE_NOTE = ("Vegetation has NO official score. The research-only rubric (docs/research/vegetation-brain on branch "
              "docs/vegetation-brain-research) and docs/brains/vegetation/VEGETATION_SCORE_V1_PROPOSAL.md are proposals.")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
