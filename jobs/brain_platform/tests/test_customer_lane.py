"""The Publisher's CUSTOMER-lane wiring (publisher_live/customer_lane.py; Sector_Ops #51 P1). Fake database only.

Absent switch = the lane does nothing at all (no read, no write); "1" = the Brain's own copy is planned by its existing pure planner and
written in one key-guarded update; anything else = every stored copy of that kind is withdrawn once with UNKNOWN."""
import copy
import datetime as dt
import json
import os

import pytest

from sector_brain_platform.publisher_live import customer_lane as LN
from sector_brain_platform.publisher_live import customer_lake_level as LV
from sector_brain_platform.publisher_live import customer_water_temp as WT

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WT_GOLDEN = json.load(open(os.path.join(ROOT, "brains", "water-temperature", "tests", "golden", "water_temp_run_updates.json")))
LAKE_GOLDEN = json.load(open(os.path.join(ROOT, "brains", "lake", "tests", "golden", "lake_run_updates.json")))
WT_NOW = dt.datetime(2026, 7, 15, 3, 0, tzinfo=dt.timezone.utc)
LAKE_NOW = dt.datetime(2026, 6, 1, 13, 0, tzinfo=dt.timezone.utc)
RECORD = {"publishId": "7def2674", "knowledgeRelease": "release-test"}


class FakeDb:
    def __init__(self, tree=None):
        self.tree = tree or {}
        self.gets, self.updates = [], []

    def get(self, path):
        self.gets.append(path)
        node = self.tree
        for part in [p for p in path.strip("/").split("/") if p]:
            node = node.get(part) if isinstance(node, dict) else None
        return copy.deepcopy(node)

    def update(self, updates):
        self.updates.append(copy.deepcopy(updates))
        for k, v in updates.items():
            parts = k.strip("/").split("/")
            node = self.tree
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = copy.deepcopy(v)


def wt_beta():
    u = copy.deepcopy(WT_GOLDEN)
    u["brains/water-temp"]["status"] = "BETA"
    return u


def test_only_three_brains_have_a_copy_and_each_has_its_own_switch():
    assert LN.LANE == {"lake-brain": ("level", "PUBLISHER_CUSTOMER_LAKE_LEVEL"),
                       "water-clarity": ("clarity", "PUBLISHER_CUSTOMER_CLARITY"),
                       "water-temp": ("waterTemp", "PUBLISHER_CUSTOMER_WATER_TEMP")}


@pytest.mark.parametrize("env", [None, {}, {"PUBLISHER_CUSTOMER_CLARITY": "1"}, {"OTHER": "1"}])
def test_absent_switch_reads_and_writes_nothing(env):
    db = FakeDb({"customer": {"lakes": {"Wheeler_AL": {"waterTemp": {"lakeId": "Wheeler|AL", "status": "ESTIMATE"}}}}})
    assert LN.write_pass("water-temp", wt_beta(), RECORD, rtdb=db, env=env, runner="pulse", now=WT_NOW) is None
    assert db.gets == [] and db.updates == []
    assert LN.plan("water-temp", wt_beta(), {}, readiness="BETA", runner="pulse", publish_id="x", source_release="r", now=WT_NOW, env=env) == ({}, {})


def test_a_brain_without_a_copy_is_never_configured():
    env = {v: "1" for _b, (_c, v) in LN.LANE.items()}
    db = FakeDb()
    assert LN.write_pass("wind", {}, RECORD, rtdb=db, env=env, runner="cloud", now=WT_NOW) is None and db.gets == []


def test_switch_on_writes_only_the_brains_own_copies_with_readiness_from_the_write_set():
    db = FakeDb()
    rep = LN.write_pass("water-temp", wt_beta(), RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "1"}, runner="pulse", now=WT_NOW)
    assert len(db.updates) == 1
    keys = set(db.updates[0])
    assert keys == {WT.copy_path(x) for x in ("Guntersville|AL", "Lake Hartwell|SC", "Wheeler|AL")}
    assert all(k.startswith("customer/lakes/") and k.endswith("/waterTemp") for k in keys)
    assert rep["readiness"] == "BETA" and rep["written"] == 3 and rep["statuses"] == {"AVAILABLE": 1, "ESTIMATE": 2}
    assert db.gets == ["customer/lakes"]                         # readiness came from the write set: no extra status read


def wt_calibration():
    u = copy.deepcopy(WT_GOLDEN)
    u["brains/water-temp"]["status"] = "CALIBRATION"
    return u


def test_below_beta_writes_nothing_new():
    db = FakeDb()
    rep = LN.write_pass("water-temp", wt_calibration(), RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "1"}, runner="pulse", now=WT_NOW)
    assert rep["readiness"] == "CALIBRATION" and rep["written"] == 0 and db.updates == []


def test_readiness_falls_back_to_the_stored_registry_status():
    u = wt_beta()
    del u["brains/water-temp"]["status"]
    db = FakeDb({"brains": {"water-temp": {"status": "BETA"}}})
    LN.write_pass("water-temp", u, RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "1"}, runner="pulse", now=WT_NOW)
    assert "brains/water-temp/status" in db.gets


def test_switch_off_but_set_withdraws_every_stored_copy_once():
    db = FakeDb()
    on = {"PUBLISHER_CUSTOMER_WATER_TEMP": "1"}
    LN.write_pass("water-temp", wt_beta(), RECORD, rtdb=db, env=on, runner="pulse", now=WT_NOW)
    rep = LN.write_pass("water-temp", wt_beta(), RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "0"}, runner="pulse", now=WT_NOW)
    assert rep["written"] == 3 and rep["statuses"] == {"UNKNOWN": 3}
    again = LN.write_pass("water-temp", wt_beta(), RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "0"}, runner="pulse", now=WT_NOW)
    assert again["written"] == 0                                  # once: already UNKNOWN


def test_the_level_copy_uses_its_eligible_list_and_release():
    u = copy.deepcopy(LAKE_GOLDEN)
    assert LN.readiness_from(u, "lake-brain") == "CALIBRATION"           # the write set's own status wins over the stored one
    u["brains/lake-brain"]["status"] = "BETA"
    db = FakeDb()
    eligible = frozenset({"Lake Hartwell|SC", "Guntersville|AL"})
    rep = LN.write_pass("lake-brain", u, RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_LAKE_LEVEL": "1"}, runner="pulse", now=LAKE_NOW, eligible=eligible)
    assert rep["copy"] == "level"
    expected, _ = LV.plan(u, {}, readiness="BETA", eligible=eligible, source_release="release-test", now=LAKE_NOW)
    assert expected and db.updates == [expected]
    assert all(k.endswith("/level") for k in db.updates[0])


@pytest.mark.parametrize("brain,key,ok", [
    ("water-temp", "customer/lakes/Wheeler_AL/waterTemp", True),
    ("water-temp", "/customer/lakes/Wheeler_AL/waterTemp", True),
    ("water-temp", "customer/lakes/Wheeler_AL/clarity", False),           # another Brain's copy
    ("water-clarity", "customer/lakes/Wheeler_AL/clarity", True),
    ("lake-brain", "customer/lakes/Wheeler_AL/level", True),
    ("water-temp", "customer/lakes/Wheeler_AL/waterTemp/valueF", False),  # deeper than the copy node
    ("water-temp", "customer/lakes/Whee.ler/waterTemp", False),
    ("water-temp", "lakes/Wheeler_AL/states/waterTemp", False),
    ("water-temp", "customer/wind/outlookModel", False),
    ("wind", "customer/lakes/Wheeler_AL/waterTemp", False),
])
def test_the_key_guard_allows_only_the_brains_own_copy_nodes(brain, key, ok):
    assert LN.key_allowed(brain, key) is ok


def test_a_refused_key_never_reaches_the_database(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(LN, "plan", lambda *a, **k: ({"customer/lakes/X/clarity": {"status": "AVAILABLE"}}, {}))
    with pytest.raises(PermissionError):
        LN.write_pass("water-temp", wt_beta(), RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "1"}, runner="pulse", now=WT_NOW)
    assert db.updates == []


def test_water_temp_publishes_beta_so_its_own_readiness_passes_the_gate():
    """B1 (Sector_Ops #51, owner-approval-2026-11-16/sector-ops-51-b1-b5): Water Temp's registry status is BETA, so the
    lane gate passes on the readiness the Brain itself publishes. Per-lake readiness stays CALIBRATION; modeled values
    go out only as ESTIMATE."""
    assert LN.readiness_from(WT_GOLDEN, "water-temp") == "BETA"
    db = FakeDb()
    rep = LN.write_pass("water-temp", WT_GOLDEN, RECORD, rtdb=db, env={"PUBLISHER_CUSTOMER_WATER_TEMP": "1"}, runner="pulse", now=WT_NOW)
    assert rep["readiness"] == "BETA" and rep["written"] > 0
