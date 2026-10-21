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
    from sector_brain_platform.publisher.registry import INTELLIGENCE_BUNDLE, INTELLIGENCE_SCHEMAS   # Sector Intelligence: fourth (Cortex architecture completion)
    assert r.schemas_for("sector-intelligence") == sorted(INTELLIGENCE_SCHEMAS) and r.bundle(INTELLIGENCE_BUNDLE).sections == INTELLIGENCE_SCHEMAS
    from sector_brain_platform.publisher.registry import LAKE_BUNDLE, LAKE_SCHEMAS, WATER_TEMP_BUNDLE, WATER_TEMP_SCHEMAS   # Lake, Water Temperature: SHADOW
    assert r.schemas_for("lake-brain") == sorted(LAKE_SCHEMAS) and r.bundle(LAKE_BUNDLE).sections == LAKE_SCHEMAS
    assert r.schemas_for("water-temp") == sorted(WATER_TEMP_SCHEMAS) and r.bundle(WATER_TEMP_BUNDLE).sections == WATER_TEMP_SCHEMAS
    from sector_brain_platform.publisher.registry import DEPTH_BUNDLE, DEPTH_SCHEMAS   # Depth: SHADOW (Cortex 2.1 structural completion)
    assert r.schemas_for("depth") == sorted(DEPTH_SCHEMAS) and r.bundle(DEPTH_BUNDLE).sections == DEPTH_SCHEMAS
    from sector_brain_platform.publisher.registry import VEGETATION_BUNDLE, VEGETATION_SCHEMAS   # Vegetation: SHADOW (no live writer)
    assert r.schemas_for("vegetation") == sorted(VEGETATION_SCHEMAS) and r.bundle(VEGETATION_BUNDLE).sections == VEGETATION_SCHEMAS


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
