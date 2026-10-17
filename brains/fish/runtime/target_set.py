"""CURRENT_FRESHWATER_BOWFISHING_TARGET_SET: where Sector is actually trying to give targeting intelligence.

A product-scoping layer, NOT a registry change: no species row is removed, hidden or renamed. Every registry species is either a TARGET (drives
target-readiness), a SECONDARY candidate (decided by geography / policy later), or KNOWLEDGE_ONLY (kept and scored as knowledge, never a readiness driver).
Membership is a product decision (Michael ratifies); the reasons are recorded so the decision is inspectable. Pure data + helpers.
"""
from __future__ import annotations

TARGET_SET_VERSION = "freshwater-bowfishing-targets-v1"

TARGET = {
    "common_carp": "reference species; widely targeted; strongest evidence",
    "grass_carp": "legally targetable in most waters; vegetation and rise response",
    "silver_carp": "targeted where present; strong discharge response",
    "spotted_gar": "core Southeast gar target",
    "longnose_gar": "core Southeast gar target",
    "smallmouth_buffalo": "core buffalo target in TVA/Southeast rivers and reservoirs",
    "bigmouth_buffalo": "buffalo target; policy SUPPRESS in some states, kept as a target for readiness",
    "bowfin": "engine tier-1 target; backwater and night shallow fish",
}
SECONDARY = {
    "bighead_carp": "targeted where present; evidence pooled with silver carp; rare upstream",
    "northern_snakehead": "presence-gated invasive; target only where confirmed present",
    "blue_tilapia": "tier-1 in AZ/CA/FL/NV/NC/TX only; not yet a separate registry row",
    "quillback": "proposed registry split; value depends on geography",
    "river_carpsucker": "proposed registry split; value depends on geography",
}
KNOWLEDGE_ONLY = {
    "alligator_gar": "policy REFUSE; regional (Gulf slope, Texas): strong knowledge, not a Tennessee River readiness driver",
    "black_buffalo": "policy REFUSE; field identification unreliable",
    "black_carp": "injurious; product-suppressed, reporting only",
    "shortnose_gar": "policy SUPPRESS (extirpated in Alabama); look-alike with spotted gar",
    "paddlefish": "protected; not a target",
    "channel_catfish": "not sight-shootable; policy not assessed",
    "american_shad": "managed gamefish; not legal by default",
    "freshwater_drum": "tier 3; policy not assessed",
    "gizzard_shad": "forage; policy not assessed",
    "goldfish": "low value; legality unverified",
    "striped_mullet": "saltwater-primary (future phase)",
    "blue_sucker": "protected/concern in many states; not a realistic bow target",
    "shorthead_redhorse": "not a Sector target", "golden_redhorse": "not a Sector target", "river_redhorse": "not a Sector target", "silver_redhorse": "not a Sector target",
    "highfin_carpsucker": "conservation concern; not a Sector target", "spotted_sucker": "future candidate only",
    "carpsuckers_group": "grouped registry row; superseded by species proposals", "tilapia_unresolved": "unresolved taxon row; see blue_tilapia",
    "suckers_redhorse_carpsuckers_group": "registry artifact (NOT_ASSESSED)",
}


def role(species_id: str) -> str:
    if species_id in TARGET:
        return "TARGET"
    if species_id in SECONDARY:
        return "SECONDARY"
    return "KNOWLEDGE_ONLY"


def partition(species_ids) -> dict:
    out = {"TARGET": [], "SECONDARY": [], "KNOWLEDGE_ONLY": []}
    for s in sorted(species_ids):
        out[role(s)].append(s)
    return out


def check_disjoint() -> list[str]:
    e = []
    for a, b, n in ((TARGET, SECONDARY, "TARGET/SECONDARY"), (TARGET, KNOWLEDGE_ONLY, "TARGET/KNOWLEDGE_ONLY"), (SECONDARY, KNOWLEDGE_ONLY, "SECONDARY/KNOWLEDGE_ONLY")):
        both = set(a) & set(b)
        if both:
            e.append(f"{n}: {sorted(both)}")
    return e

# Species where new research is not worth commissioning (protected, policy-held, not a Sector target). Used only to label research priority DO_NOT_RESEARCH; knowledge stays displayed.
DO_NOT_RESEARCH = {
    "paddlefish": "protected; not a target", "american_shad": "managed gamefish; not legal by default", "channel_catfish": "not sight-shootable by Sector policy",
    "black_buffalo": "policy REFUSE; field identification unreliable", "black_carp": "injurious; reporting only", "blue_sucker": "protected/concern; not a realistic bow target",
    "striped_mullet": "saltwater-primary: future phase", "highfin_carpsucker": "conservation concern; not a target",
}
