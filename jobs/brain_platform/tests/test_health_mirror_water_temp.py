"""Sector_Ops #50 WT-P2 A3: Water Temp's /health paths become Orchestrator-derived (as Water Clarity's and Lake's). The mirror derives them only
from published Water Temp data."""
from sector_brain_platform import health_mirror as HM
from sector_brain_platform.publisher.registry import WATER_TEMP, WATER_TEMP_HEALTH_DOMAIN_CHILDREN, _owned_sources


def test_water_temp_health_is_derived_from_published_registry_and_sources_only():
    src = sorted(_owned_sources(WATER_TEMP))[0]
    out = HM.derive(WATER_TEMP, {"status": "WARNING", "staleLakeCount": 1, "lastSuccessfulRun": "x"},
                    {src: {"health": "HEALTHY", "lastFetchAt": "2026-11-03T06:00:00Z"}, "not-its-source": {"health": "HEALTHY"}})
    assert out == {f"health/brains/{WATER_TEMP}/status": "WARNING", f"health/brains/{WATER_TEMP}/staleLakeCount": 1,
                   f"health/sources/{src}": {"status": "HEALTHY", "lastFetchAt": "2026-11-03T06:00:00Z"}}
    assert set(HM.SPECS[WATER_TEMP]["registryChildren"]) == set(WATER_TEMP_HEALTH_DOMAIN_CHILDREN)


def test_unknown_stays_absent():
    assert HM.derive(WATER_TEMP, {}, {}) == {}


def test_the_publisher_registry_no_longer_authorises_water_temp_health_paths():
    from sector_brain_platform.publisher import default_registry
    reg = default_registry()
    for path in (f"/health/brains/{WATER_TEMP}/status", f"/health/sources/{sorted(_owned_sources(WATER_TEMP))[0]}"):
        assert not any(reg.authorizing_family(sp, path, delete=False) is not None for sp in (reg.spec(s) for s in reg.schemas_for(WATER_TEMP))), path
