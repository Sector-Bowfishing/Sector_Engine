"""Option (a), owner decision 2026-11-04 (Sector_Ops #50, CG-3.1-15): Water Clarity's health family moves to the Orchestrator by a registry row, and the platform
write guard follows the registry. FAKE clients only: no production database, credential or service is touched."""
from __future__ import annotations

from sector_brain_platform import data_ownership as DO, health_mirror as HM
from sector_brain_platform.ownership import PLATFORM_WRITER, OwnershipError, assert_owned, path_allowed

CLARITY_SOURCES = ("sentinel-2-l2a", "usgs-nwis-turbidity", "noaa-mrms")
WATER_TEMP_SOURCES = ("open-meteo-forecast", "usace-cwms-water-temp", "usgs-nwis-00010")      # Water Temp G3 (DRAFT, Sector_Ops #52)


def test_the_registry_gives_the_orchestrator_clarity_health_and_only_clarity_health():
    assert DO.registered_writer("/health/brains/water-clarity/status")["current"] == DO.ORCHESTRATOR
    for s in CLARITY_SOURCES:
        assert DO.registered_writer(f"/health/sources/{s}")["current"] == DO.ORCHESTRATOR
    assert DO.registered_writer("/health/brains/water-temp/status")["current"] == DO.ORCHESTRATOR
    for s in WATER_TEMP_SOURCES:
        assert DO.registered_writer(f"/health/sources/{s}")["current"] == DO.ORCHESTRATOR
    for other in ("wind", "lake-brain", "sector-intelligence", "water-clarity-x", "water-temp-x"):
        assert DO.registered_writer(f"/health/brains/{other}/status")["current"] == f"brain:{other}"
    assert DO.registered_writer("/health/sources/tva-restapi")["current"] == "@owning-brain"


def test_the_platform_guard_follows_the_registry():
    assert path_allowed(PLATFORM_WRITER, "health/brains/water-clarity/status")
    assert path_allowed(PLATFORM_WRITER, "health/brains/water-clarity/staleLakeCount")
    assert not path_allowed(PLATFORM_WRITER, "health/brains/water-clarity")                # child level, never the whole node
    for s in CLARITY_SOURCES:
        assert path_allowed(PLATFORM_WRITER, f"health/sources/{s}")
    assert path_allowed(PLATFORM_WRITER, "health/brains/water-temp/status") and not path_allowed(PLATFORM_WRITER, "health/brains/water-temp")
    for s in WATER_TEMP_SOURCES:
        assert path_allowed(PLATFORM_WRITER, f"health/sources/{s}")
    for other in ("wind", "lake-brain", "sector-intelligence", "biological-state"):
        assert not path_allowed(PLATFORM_WRITER, f"health/brains/{other}/status")           # no registry row: not moved
    for s in ("tva-restapi", "noaa-nbm-v5", "unknown-source"):
        assert not path_allowed(PLATFORM_WRITER, f"health/sources/{s}")
    assert not path_allowed(PLATFORM_WRITER, "health/jobs/water-clarity")
    assert not path_allowed(PLATFORM_WRITER, "health/brains")


def test_no_brain_writes_a_moved_health_family():
    assert not path_allowed("water-clarity", "health/brains/water-clarity/status")
    assert not path_allowed("water-clarity", "health/brains/water-clarity")
    for s in CLARITY_SOURCES:
        assert not path_allowed("water-clarity", f"health/sources/{s}")
    assert path_allowed("lake-brain", "health/brains/lake-brain/status")                   # unchanged for every Brain not moved
    assert not path_allowed("water-temp", "health/brains/water-temp/status") and not path_allowed("water-temp", "health/brains/water-temp")
    for s in WATER_TEMP_SOURCES:
        assert not path_allowed("water-temp", f"health/sources/{s}")
    assert path_allowed("lake-brain", "health/sources/tva-restapi")


def test_the_ownership_audit_stays_clean():
    assert DO.audit() == []


def test_health_mirror_stage_now_writes_clarity_through_the_platform_guard():
    class FakeDb:
        def __init__(self, data):
            self.data, self.writes = data, []

        def get(self, path):
            node = self.data
            for seg in path.strip("/").split("/"):
                if not isinstance(node, dict):
                    return None
                node = node.get(seg)
            return node

        def update(self, updates):
            assert_owned(updates, PLATFORM_WRITER)                                            # what the real BrainRtdb(brain_id="brain-platform") client enforces
            self.writes.append(dict(updates))

    db = FakeDb({"brains": {"water-clarity": {"health": "WARNING", "staleLakeCount": 2}},
                 "sources": {"noaa-mrms": {"health": "OK", "lastFetchAt": "2026-11-04T10:00:00Z"}, "usgs-nwis-00010": {"health": "OK"}},
                 "health": {"brains": {"water-clarity": {"status": "HEALTHY"}}}})
    done = HM.stage(db, ["water-clarity"], write=True)
    assert done["water-clarity"]["written"] is True
    assert db.writes == [{"health/brains/water-clarity/status": "WARNING", "health/brains/water-clarity/staleLakeCount": 2,
                          "health/sources/noaa-mrms": {"status": "OK", "lastFetchAt": "2026-11-04T10:00:00Z"}}]


def test_a_brain_without_a_registry_row_is_still_refused_whole():
    try:
        assert_owned({"health/brains/lake-brain/status": "HEALTHY"}, PLATFORM_WRITER)
    except OwnershipError:
        return
    raise AssertionError("Lake health moved without a registry row")


def test_the_swift_guard_lists_exactly_the_registry_rows():
    import os
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Sources", "SectorEngine", "Brain", "BrainContract.swift"), encoding="utf-8").read()
    def swift_set(name):
        return set(re.findall(r'"([^"]+)"', re.search(rf"static let {name}: Set<String> = \[([^\]]*)\]", src).group(1)))
    rows = [f["pattern"] for f in DO.mirror()["families"] if f["writer"] == DO.ORCHESTRATOR and "{" not in f["pattern"]]
    assert swift_set("orchestratorHealthBrains") == {p.split("/")[3] for p in rows if p.startswith("/health/brains/")}
    assert swift_set("orchestratorHealthSources") == {p.split("/")[3] for p in rows if p.startswith("/health/sources/")}
