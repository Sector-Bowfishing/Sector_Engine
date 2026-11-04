"""Sector_Ops #50 WT-P2 A3: Water Temp's /health paths become Orchestrator-derived (as Water Clarity's and Lake's). The mirror derives them only
from published Water Temp data."""
from sector_brain_platform import health_mirror as HM
from sector_brain_platform.publisher.registry import WATER_TEMP, WATER_TEMP_HEALTH_DOMAIN_CHILDREN, _owned_sources


def test_water_temp_health_is_derived_from_published_registry_and_sources_only():
    src = sorted(_owned_sources(WATER_TEMP))[0]
    out = HM.derive(WATER_TEMP, {"status": "CALIBRATION", "health": "WARNING", "staleLakeCount": 1, "lastSuccessfulRun": "2026-11-03T06:00:00Z"},
                    {src: {"health": "HEALTHY", "lastFetchAt": "2026-11-03T06:00:00Z", "failuresLastRun": 0}, "not-its-source": {"health": "HEALTHY"}})
    assert out == {f"health/brains/{WATER_TEMP}/status": "WARNING", f"health/brains/{WATER_TEMP}/staleLakeCount": 1,
                   f"health/brains/{WATER_TEMP}/lastSuccess": "2026-11-03T06:00:00Z",
                   f"health/brains/{WATER_TEMP}/lastRun": None, f"health/brains/{WATER_TEMP}/errorCount": None, f"health/brains/{WATER_TEMP}/durationMs": None,
                   f"health/sources/{src}": {"status": "HEALTHY", "lastFetchAt": "2026-11-03T06:00:00Z", "failuresLastRun": 0}}
    assert set(WATER_TEMP_HEALTH_DOMAIN_CHILDREN) <= set(HM.SPECS[WATER_TEMP]["registryChildren"])


def test_lifecycle_status_is_never_published_as_health():
    """The registry `status` is the lifecycle (CALIBRATION); health comes from `health` (2026-11-04 review)."""
    out = HM.derive(WATER_TEMP, {"status": "CALIBRATION"}, {})
    assert f"health/brains/{WATER_TEMP}/status" not in out


def test_every_child_the_legacy_job_writes_is_either_derived_or_retired():
    import json, os
    golden = os.path.join(os.path.dirname(__file__), "..", "..", "..", "brains", "water-temperature", "tests", "golden", "water_temp_run_updates.json")
    u = json.load(open(golden))
    legacy = set((u.get("updates", u))[f"health/brains/{WATER_TEMP}"])
    spec = HM.SPECS[WATER_TEMP]
    assert legacy == set(spec["registryChildren"]) | set(spec["retireChildren"]), legacy


def test_stage_removes_retired_children_and_keeps_derived_ones_fresh():
    class DB:
        def __init__(self, tree): self.tree, self.updates = tree, []
        def get(self, path): return self.tree.get(path)
        def update(self, d): self.updates.append(d); self.tree.update({k: v for k, v in d.items()})
    src = sorted(_owned_sources(WATER_TEMP))[0]
    db = DB({f"brains/{WATER_TEMP}/health": "HEALTHY", f"brains/{WATER_TEMP}/staleLakeCount": 0, f"brains/{WATER_TEMP}/lastSuccessfulRun": "2026-11-04T00:00:00Z",
             f"health/brains/{WATER_TEMP}/lastRun": "2026-10-22T00:00:00Z", f"health/brains/{WATER_TEMP}/lastSuccess": "2026-10-22T00:00:00Z",
             "sources": {src: {"health": "HEALTHY", "failuresLastRun": 0}}})
    HM.stage(db, [WATER_TEMP], write=True)
    (u,) = db.updates
    assert u[f"health/brains/{WATER_TEMP}/lastRun"] is None and u[f"health/brains/{WATER_TEMP}/lastSuccess"] == "2026-11-04T00:00:00Z"
    assert u[f"health/brains/{WATER_TEMP}/status"] == "HEALTHY" and f"health/brains/{WATER_TEMP}/errorCount" not in u   # already absent: nothing to remove


def test_unknown_stays_absent():
    out = HM.derive(WATER_TEMP, {}, {})
    assert all(v is None for v in out.values()) and set(out) == {f"health/brains/{WATER_TEMP}/{c}" for c in HM.SPECS[WATER_TEMP]["retireChildren"]}


def test_the_publisher_registry_no_longer_authorises_water_temp_health_paths():
    from sector_brain_platform.publisher import default_registry
    reg = default_registry()
    for path in (f"/health/brains/{WATER_TEMP}/status", f"/health/sources/{sorted(_owned_sources(WATER_TEMP))[0]}"):
        assert not any(reg.authorizing_family(sp, path, delete=False) is not None for sp in (reg.spec(s) for s in reg.schemas_for(WATER_TEMP))), path
