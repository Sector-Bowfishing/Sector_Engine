"""Sector_Ops #48 A3: Lake's /health paths become Orchestrator-derived (as Water Clarity's). The mirror derives them only from published Lake data."""
from sector_brain_platform import health_mirror as HM
from sector_brain_platform.publisher.registry import LAKE, LAKE_HEALTH_DOMAIN_CHILDREN, _owned_sources


def test_lake_health_is_derived_from_published_registry_and_sources_only():
    src = sorted(_owned_sources(LAKE))[0]
    out = HM.derive(LAKE, {"status": "CALIBRATION", "health": "WARNING", "staleLakeCount": 1, "healthReasons": ["cwms fallback"], "lastSuccessfulRun": "x"},
                    {src: {"health": "HEALTHY", "lastFetchAt": "2026-11-02T12:00:00Z"}, "not-lakes-source": {"health": "HEALTHY"}})
    assert out == {f"health/brains/{LAKE}/status": "WARNING", f"health/brains/{LAKE}/staleLakeCount": 1, f"health/brains/{LAKE}/reasons": ["cwms fallback"],
                   f"health/sources/{src}": {"status": "HEALTHY", "lastFetchAt": "2026-11-02T12:00:00Z"}}
    assert set(HM.SPECS[LAKE]["registryChildren"]) == set(LAKE_HEALTH_DOMAIN_CHILDREN)


def test_unknown_stays_absent():
    assert HM.derive(LAKE, {}, {}) == {}


def test_the_publisher_registry_no_longer_authorises_lake_health_paths():
    from sector_brain_platform.publisher import default_registry
    reg = default_registry()
    for path in (f"/health/brains/{LAKE}/status", f"/health/sources/{sorted(_owned_sources(LAKE))[0]}"):
        assert not any(reg.authorizing_family(sp, path, delete=False) is not None for sp in (reg.spec(s) for s in reg.schemas_for(LAKE))), path


def test_clarity_health_status_comes_from_health_not_the_lifecycle_status():
    """2026-11-04 review: the live Clarity registry has status BETA and health HEALTHY; the mirror must publish HEALTHY."""
    out = HM.derive("water-clarity", {"status": "BETA", "health": "HEALTHY", "staleLakeCount": 619}, {})
    assert out == {"health/brains/water-clarity/status": "HEALTHY", "health/brains/water-clarity/staleLakeCount": 619}
