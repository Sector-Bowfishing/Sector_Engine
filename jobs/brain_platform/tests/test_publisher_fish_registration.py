"""Fish (biological-state) is the Publisher's second concrete registration (Fish Structural Certification V1). The framework did not change for it
except one generic correction (`foreign_owner`): a root the submitter itself owns is not "foreign" to it. Wind is unchanged."""
from sector_brain_platform.publisher import default_registry
from sector_brain_platform.publisher.paths import foreign_owner
from sector_brain_platform.publisher.registry import FISH_BUNDLE, FISH_REGISTRY_CHILDREN, FISH_SCHEMAS, WIND_BUNDLE, WIND_SCHEMAS


def test_default_registry_has_exactly_wind_and_fish_schemas_and_bundles():
    r = default_registry()
    assert r.schemas_for("wind") == sorted(WIND_SCHEMAS) and r.schemas_for("biological-state") == sorted(FISH_SCHEMAS)
    assert r.bundle(WIND_BUNDLE).sections == WIND_SCHEMAS and r.bundle(FISH_BUNDLE).sections == FISH_SCHEMAS
    from sector_brain_platform.publisher.registry import CLARITY_BUNDLE, CLARITY_SCHEMAS       # Water Clarity: third registration (Water Clarity Structural Certification V1)
    assert r.schemas_for("water-clarity") == sorted(CLARITY_SCHEMAS) and r.bundle(CLARITY_BUNDLE).sections == CLARITY_SCHEMAS
    for other in ("lake-brain", "water-temp", "sector-intelligence", "depth", "vegetation"):
        assert r.schemas_for(other) == []                                      # still identity-only until their own certification


def test_fish_can_never_author_publisher_owned_children_or_other_brains_paths():
    r = default_registry()
    covered = {c for g in FISH_REGISTRY_CHILDREN.values() for c in g}
    assert not covered & {"publication", "certification"}
    for fam in [f for sid in FISH_SCHEMAS for f in r.spec(sid).families]:
        assert fam.pattern.split("/")[1] in ("species", "brains", "validation", "health", "activity")
    assert not r.spec("fish-species-v1").require_freshness and not r.spec("fish-registry-v1").require_freshness       # version-driven: no invented freshness
    assert r.spec("fish-species-v1").require_release and r.spec("fish-registry-v1").require_release


def test_foreign_owner_is_precise_for_the_root_owner_and_unchanged_for_everyone_else():
    assert foreign_owner("/species/example_fish/profile", "biological-state") is None          # Fish owns /species: not foreign to it
    assert foreign_owner("/species/example_fish", "wind") == "species"                         # a Brain that does not own it still gets the owner named
    assert foreign_owner("/speciesProfiles/x", "biological-state") == "species"                # roots Fish does not own are still foreign
    assert foreign_owner("/access/x", "biological-state") == "platform"
