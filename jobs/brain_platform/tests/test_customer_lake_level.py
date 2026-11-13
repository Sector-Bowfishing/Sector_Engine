"""The Publisher's CUSTOMER-lane Lake level copy (design note CUSTOMER_BRAIN_OUTPUT_PATH_V1 §3 gates 1-4, §6 schema; Sector_Ops #47 item 5). Pure planner; nothing writes."""
import copy
import datetime as dt
import json
import os
import re

import pytest

from sector_brain_platform.publisher_live import customer_lake_level as C

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GOLDEN = json.load(open(os.path.join(ROOT, "brains", "lake", "tests", "golden", "lake_run_updates.json")))
NOW = dt.datetime(2026, 6, 1, 13, 0, tzinfo=dt.timezone.utc)                     # inside the golden states' freshUntil
HARTWELL, GUNTERSVILLE = "Lake Hartwell|SC", "Guntersville|AL"
ELIGIBLE = frozenset({HARTWELL, GUNTERSVILLE})
FIELDS = {"schema", "lakeId", "status", "elevationFt", "datum", "observationTime", "sourceAgeHours", "trend", "change24hFt", "freshUntil", "brainId", "sourceRelease", "writtenAt"}


def plan(updates=GOLDEN, previous=None, readiness="BETA", eligible=ELIGIBLE, now=NOW):
    return C.plan(updates, previous or {}, readiness=readiness, eligible=eligible, source_release="lake-release-test", now=now)


def test_the_publisher_list_is_the_engine_validated_list():
    s = open(os.path.join(ROOT, "Sources", "SectorEngine", "API", "LakeLevelOutputAPI.swift")).read()
    block = s[s.index("validatedLakeIds"):]
    swift = set(re.findall(r'"([^"]+)"', block[block.index("[") + 1:block.index("]")]))
    assert C.eligible_lake_ids() == swift and len(swift) == 30


def test_an_eligible_observed_lake_gets_exactly_the_schema_fields():
    writes, why = plan()
    c = writes[C.copy_path(HARTWELL)]
    assert C.copy_path(HARTWELL) == "customer/lakes/Lake_Hartwell_SC/level"
    assert set(c) <= FIELDS and c["schema"] == C.SCHEMA and c["status"] == "AVAILABLE" and why[HARTWELL] == "AVAILABLE"
    assert c["lakeId"] == HARTWELL and c["elevationFt"] == 593.8 and c["datum"] == "NGVD29" and c["change24hFt"] == 0
    assert c["observationTime"] == "2026-06-01T12:00:00Z" and c["freshUntil"] == "2026-06-01T15:00:00Z" and c["trend"] == "STABLE"
    assert c["brainId"] == "lake-brain" and c["sourceRelease"] == "lake-release-test" and c["writtenAt"] == "2026-06-01T13:00:00Z"
    assert "datum" not in writes[C.copy_path(GUNTERSVILLE)]                       # absent in the state: absent in the copy, never invented


def test_only_eligible_lakes_get_a_copy():
    writes, why = plan()
    assert set(writes) == {C.copy_path(HARTWELL), C.copy_path(GUNTERSVILLE)}
    assert why["Wheeler|AL"] == "NOT_VALIDATED_HERE" and why["Pickwick Lake|TN"] == "NOT_VALIDATED_HERE"


@pytest.mark.parametrize("readiness", ["CALIBRATION", "PROFILED", "DEGRADED", "BLOCKED", None, "beta"])
def test_lake_below_beta_writes_no_copy(readiness):
    writes, why = plan(readiness=readiness)
    assert writes == {} and set(why.values()) == {"LAKE_NOT_BETA"}


def test_a_proxy_is_trend_only():
    u = copy.deepcopy(GOLDEN)
    s = u["lakes/Lake_Hartwell_SC/states/lake"]
    s.update(kind="PROXY", sourceCapability="NEARBY_GAUGE_PROXY", trendState="RISING")
    c = plan(u)[0][C.copy_path(HARTWELL)]
    assert c["status"] == "ESTIMATE" and c["trend"] == "RISING"
    assert not {"elevationFt", "datum", "change24hFt"} & set(c)                     # Cortex lake.md LC-06
    s["trendState"] = "UNKNOWN"
    assert C.copy_path(HARTWELL) not in plan(u)[0] and plan(u)[1][HARTWELL] == "NO_TREND"


@pytest.mark.parametrize("change,reason", [
    ({"lakeId": "Lake Hartwell|GA"}, "NO_PUBLICATION"),                               # key matches, stored id does not (keys are lossy)
    ({"freshness": {"stale": True, "freshUntil": "2026-06-01T15:00:00Z"}}, "STALE"),
    ({"freshness": {"stale": False, "freshUntil": "2026-06-01T12:59:00Z"}}, "STALE"),  # went stale before this publish
    ({"freshness": {"stale": False}}, "STALE"),
    ({"observationTime": None}, "STALE"),
    ({"currentElevationFt": None}, "NO_VALUE"),
    ({"currentElevationFt": float("nan")}, "NO_VALUE"),
    ({"sourceCapability": "MODELED"}, "NO_SOURCE"),
    ({"sourceCapability": "HISTORICAL_ONLY"}, "NO_SOURCE"),
    ({"kind": "UNAVAILABLE"}, "NO_SOURCE"),
    ({"kind": "PROXY"}, "NO_SOURCE"),                                                # a direct source labelled PROXY is neither
])
def test_each_failing_gate_writes_no_copy(change, reason):
    u = copy.deepcopy(GOLDEN)
    u["lakes/Lake_Hartwell_SC/states/lake"].update(change)
    writes, why = plan(u)
    assert C.copy_path(HARTWELL) not in writes and why[HARTWELL] == reason


def test_a_lake_that_stops_passing_gets_unknown_over_its_old_copy():
    before = plan()[0]
    u = copy.deepcopy(GOLDEN)
    u["lakes/Lake_Hartwell_SC/states/lake"]["freshness"]["stale"] = True
    writes, _ = plan(u, previous=before)
    c = writes[C.copy_path(HARTWELL)]
    assert c["status"] == "UNKNOWN" and set(c) == {"schema", "lakeId", "status", "brainId", "sourceRelease", "writtenAt"}
    again, _ = plan(u, previous={**before, **writes})
    assert C.copy_path(HARTWELL) not in again                                      # already UNKNOWN: not rewritten every publish


def test_a_lake_taken_off_the_list_or_a_brain_demoted_clears_its_copy():
    before = plan()[0]
    writes, _ = plan(previous=before, eligible=frozenset({GUNTERSVILLE}))
    assert writes[C.copy_path(HARTWELL)]["status"] == "UNKNOWN" and writes[C.copy_path(GUNTERSVILLE)]["status"] == "AVAILABLE"
    demoted, _ = plan(previous=before, readiness="CALIBRATION")
    assert {p: c["status"] for p, c in demoted.items()} == {C.copy_path(HARTWELL): "UNKNOWN", C.copy_path(GUNTERSVILLE): "UNKNOWN"}


def test_nothing_from_the_internal_record_leaks():
    c = plan()[0][C.copy_path(HARTWELL)]
    for internal in ("operatingZone", "provenance", "facts", "guideFt", "levelState", "historicalState", "seasonalPercentile", "sourceCapability", "kind"):
        assert internal not in c
    assert all(k.startswith("customer/lakes/") and k.endswith("/level") for k in plan()[0])


def test_the_engine_reader_accepts_what_the_publisher_writes():
    """The Engine decoder's required fields (LakeLevelOutputAPI.CustomerCopy) are present with the types it decodes."""
    c = plan()[0][C.copy_path(HARTWELL)]
    assert isinstance(c["schema"], str) and isinstance(c["lakeId"], str) and isinstance(c["status"], str)
    assert isinstance(c["elevationFt"], float) and isinstance(c["observationTime"], str) and isinstance(c["freshUntil"], str)
    assert c["schema"] == "sector-customer-lake-level-v1"
