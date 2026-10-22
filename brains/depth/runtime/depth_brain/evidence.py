"""Evidence tiers, precedence, and the GLOBathy restriction (research decision, codified).

Precedence: A > B > C > D > UNKNOWN. A lower tier NEVER overrides or fills a gap in a higher tier for the same quantity.
GLOBathy is Tier D at best and is forbidden for every depth product. The only thing it may ever emit is a
coarse class prior, and that is DISABLED by default because the research found it adds almost nothing
(max-depth Spearman 0.42/0.18, broad-shallow AUC 0.53; it recognised 1 of 6 truly shallow lakes)."""
from __future__ import annotations

from dataclasses import dataclass

from . import contract as C

ENABLE_GLOBATHY_COARSE_PRIOR = False         # product decision: off. Changing it needs an explicit, reviewed edit.

# Every use below is FORBIDDEN for modeled bathymetry (GLOBathy / HydroLAKES depth / any model), enforced by assert_allowed_use.
FORBIDDEN_MODEL_USES = (
    "absolute_depth", "point_depth", "flats", "dropoffs", "channels", "depth_zones", "zone_shares",
    "lake_depth_ranking", "customer_contour_layer", "effective_depth", "scored_factor", "override_measured",
)
ALLOWED_PRIOR_CLASSES = ("likelyShallow", "unknown", "likelyDeep")


class ForbiddenEvidenceUse(ValueError):
    pass


def assert_allowed_use(source_kind: str, use: str) -> None:
    """Raise ForbiddenEvidenceUse when modeled/proxy evidence is asked to do a measured-evidence job."""
    if source_kind in ("modeled", "proxy", "globathy") and use in FORBIDDEN_MODEL_USES:
        raise ForbiddenEvidenceUse(f"{source_kind} evidence may not be used for {use!r} (Depth Brain evidence policy)")


@dataclass(frozen=True)
class Evidence:
    tier: str                         # A B C D UNKNOWN
    kind: str                         # measured | contour | modeled | proxy | unknown
    source: str
    detail: dict | None = None


def tier_rank(tier: str) -> int:
    return C.TIERS.index(tier)


def best_evidence(items) -> Evidence:
    """Highest tier wins; ties keep the first (callers order by recency/quality). Empty -> UNKNOWN."""
    items = [e for e in items if e is not None]
    if not items:
        return Evidence("UNKNOWN", "unknown", "none")
    return min(items, key=lambda e: tier_rank(e.tier))


def depth_tier_from_research(research_tier: str | None) -> str:
    return C.RESEARCH_TIER_MAP.get(research_tier or "U", "UNKNOWN")


def globathy_coarse_prior(dmax_m: float | None, match_tier: str | None, *, best_existing: Evidence | None = None) -> dict | None:
    """The ONLY thing GLOBathy may produce: a labelled class prior, tier D, never numeric, never scored.

    Returns None (the default) because ENABLE_GLOBATHY_COARSE_PRIOR is False. Even when enabled:
      - suspect/unmatched HydroLAKES matches get nothing;
      - any existing A/B/C evidence suppresses it (a measured source always wins);
      - cutoffs (12 m / 40 m on Dmax) were suggested by the research but never tested;
      - the output has no depth value, no zone, no polygon, no share."""
    if not ENABLE_GLOBATHY_COARSE_PRIOR:
        return None
    if dmax_m is None or match_tier not in ("verified", "weak"):
        return None
    if best_existing is not None and best_existing.tier in ("A", "B", "C"):
        return None
    cls = "likelyShallow" if dmax_m < 12 else ("likelyDeep" if dmax_m > 40 else "unknown")
    return {"class": cls, "tier": "D", "evidenceKind": "modeled", "source": "globathy", "scored": False,
            "confidence": "very_low", "note": "coarse class prior from modeled maximum depth; not a depth, not for scoring"}
