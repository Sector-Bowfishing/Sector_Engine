"""End to end: the REAL orchestrate.main() cycle drives publication coordination (Cortex 3.1 PL-19, FD-15, M08).

Everything outside the process is a fake: the RTDB is FakeDb, the Cloud Run results are injected, the artifact store and the Publisher's RTDB are the shared rig's in-memory fakes. The
only thing replaced in the production code path is the factory seam that would build the artifact-bucket store and the LIVE Publisher (the cycle never builds a live Publisher itself).
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "brain_platform", "tests"))
import orchestrate as OR                                          # noqa: E402
from test_central_scheduling import world                         # noqa: E402,F401  (fixture)
from test_control_plane import tree, ago, enabled_control          # noqa: E402
from live_rig import Rig                                          # noqa: E402
from publisher_fixtures import wind_artifact, uuid4               # noqa: E402
from sector_brain_platform import data_ownership as DO, publication_stage as PS    # noqa: E402
from sector_brain_platform.publisher.storage import MemoryObjectStore               # noqa: E402

pytestmark = pytest.mark.live_manifest


def quiet(control="enabled"):
    """Nothing is due: no Brain starts, so every effect in these tests comes from publication coordination."""
    t = tree()
    for b in ("water-temp", "lake-brain", "wind"):
        t["brains"][b]["lastSuccessfulRun"] = ago(0.2)
    t["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(1), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    t["control"] = {"executionControlV1": enabled_control()} if control == "enabled" else {}
    return t


def cloud(n=1, ok=True, brain_job="wind-hourly"):
    return {brain_job: [{"metadata": {"name": uuid4(1000 + n)},
                         "status": {"startTime": ago(0.3).replace("T", "T"), "completionTime": ago(0.2), **({"succeededCount": 1} if ok else {"failedCount": 1})}}]}


@pytest.fixture
def stack(world, monkeypatch, tmp_path):
    setup, calls = world
    rig = Rig(brains=("wind",))
    arm = {"live": None, "stores": 0}
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: rig.store if (d or b) else None)
    monkeypatch.setattr(OR, "build_live_publisher", lambda store: arm["live"])
    paths = {"ledger": str(tmp_path / "ledger.json"), "cut": str(tmp_path / "cutover.json"), "out": str(tmp_path / "pub.json")}
    argv = ["--coordinate-publication", "--artifact-store-dir", "x", "--publication-ledger", paths["ledger"], "--publication-cutover", paths["cut"], "--emit-publication-state", paths["out"]]

    def cutover(**brains):
        json.dump({"schema": PS.CUTOVER_SCHEMA, "brains": brains}, open(paths["cut"], "w"))

    def pub(db):
        return db.tree["control"]["orchestrator"].get("publication")
    return type("S", (), dict(setup=staticmethod(setup), calls=calls, rig=rig, arm=arm, paths=paths, argv=argv, cutover=staticmethod(cutover), pub=staticmethod(pub)))


def rec_of(path, n=1):
    led = json.load(open(path))["records"]
    return next(r for k, r in led.items() if r["artifact"].get("artifactId") == uuid4(2000 + n))


# 1. off by default: the deployed cycle is unchanged -------------------------------------------------------------------------------------------------------------------
def test_default_cycle_has_no_publication_stage(stack, monkeypatch):
    db = stack.setup(quiet(), cloud())
    monkeypatch.setattr(PS, "run_stage", lambda **k: pytest.fail("publication stage ran without --coordinate-publication"))
    assert OR.main([]) == 0
    assert "publication" not in db.tree["control"]["orchestrator"]


# 2. pre-cutover: collected, shadow-checked, NOT published; direct writer stays the writer ---------------------------------------------------------------------------
def test_pre_cutover_cloud_run_artifact_is_collected_shadowed_and_not_reported_published(stack):
    stack.rig.ref(wind_artifact(n=1))
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0
    p = stack.pub(db)
    assert p["state"] == "COORDINATED" and p["armed"] is False
    r = rec_of(stack.paths["ledger"])
    assert r["runId"] == uuid4(1001) and r["artifact"]["state"] == "COLLECTED" and r["artifact"]["schema"] == "wind-lake-state-v1"
    assert r["shadow"]["result"] == "SHADOW_READY" and r["shadow"]["live"] is False                  # shadow passed ...
    assert r["publication"]["outcome"] == "NOT_REQUESTED" and r["publication"]["reason"] == "DIRECT_WRITER_ACTIVE"      # ... and is not a publication
    assert r["writePath"] == "DIRECT_WRITE_PRE_CUTOVER"
    assert p["summary"]["brains"]["wind"]["published"] == 0 and p["summary"]["brains"]["wind"]["directWriter"] is True
    assert stack.rig.rtdb.updates == []


# 3. approved cutover + live Publisher supplied: the cycle gets the artifact PUBLISHED with readback; a second cycle never duplicates ------------------------------
def test_approved_central_brain_is_published_once_through_the_publisher_in_the_real_cycle(stack):
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.arm["live"] = stack.rig.live
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0
    r = rec_of(stack.paths["ledger"])
    assert r["publication"]["outcome"] == "PUBLISHED" and r["publication"]["readback"]["verified"] is True and r["writePath"] == "PUBLISHER" and r["publication"]["attempts"] == 1
    assert stack.pub(db)["summary"]["brains"]["wind"]["published"] == 1
    assert any("/states/wind" in k or k.startswith("lakes/") for u in stack.rig.rtdb.updates for k in u)      # the Publisher (not the Orchestrator) wrote the Brain keys
    calls = stack.rig.rtdb.calls
    assert OR.main(stack.argv) == 0 and stack.rig.rtdb.calls == calls                                  # same run, next cycle: nothing is submitted twice
    assert rec_of(stack.paths["ledger"])["publication"]["attempts"] == 1


# 4. a cutover without an approval reference, for a legacy/alias identity, or while the Publisher is unarmed changes nothing -------------------------------------
@pytest.mark.parametrize("entry,problem", [({"wind": {"state": "CENTRAL"}}, "CUTOVER_NOT_APPROVED"),
                                           ({"biological-state": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_LEGACY_COMBINED_FROZEN"),
                                           ({"biological-state": {"state": "CENTRAL", "approvalRef": "x", "legacyCombinedAck": True}}, "CUTOVER_LEGACY_COMBINED_FROZEN"),
                                           ({"fish-knowledge": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_DEFERRED"),
                                           ({"fish-behavior": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_DEFERRED"),
                                           ({"depth": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_BLOCKED"),
                                           ({"vegetation": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_BLOCKED"),
                                           ({"wind": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_ORDER"),
                                           ({"fish": {"state": "CENTRAL", "approvalRef": "x"}}, "CUTOVER_UNKNOWN_BRAIN")])
def test_unapproved_or_frozen_cutover_is_ignored_and_reported(stack, entry, problem):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    stack.arm["live"] = stack.rig.live
    stack.cutover(**entry)
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0
    assert problem in [x["kind"] for x in stack.pub(db)["cutover"]["problems"]]
    assert rec_of(stack.paths["ledger"])["publication"]["outcome"] == "NOT_REQUESTED" and stack.rig.rtdb.updates == []


def test_cutover_declared_but_publisher_unarmed_holds_with_a_reason(stack):
    stack.rig.ref(wind_artifact(n=1))
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0 and stack.pub(db)["armed"] is False
    p = rec_of(stack.paths["ledger"])["publication"]
    assert p["outcome"] == "NOT_REQUESTED" and p["reason"] == "PUBLISHER_UNARMED" and stack.rig.rtdb.updates == []


# 5. scheduler paused: artifacts are still recorded, nothing is published, nothing starts ---------------------------------------------------------------------------
def test_paused_execution_control_records_but_never_publishes_or_starts(stack):
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.arm["live"] = stack.rig.live
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    db = stack.setup(quiet(control=None), cloud())
    assert OR.main(stack.argv) == 0
    p = rec_of(stack.paths["ledger"])
    assert p["artifact"]["state"] == "COLLECTED" and p["publication"]["outcome"] == "NOT_REQUESTED" and p["publication"]["reason"] == "EXECUTION_PAUSED"
    assert stack.rig.rtdb.updates == [] and stack.calls["start"] == [] and stack.calls["inproc"] == []


# 6. invalid / missing / failed ------------------------------------------------------------------------------------------------------------------------------------------
def test_a_succeeded_run_without_an_artifact_and_a_failed_run_are_recorded_not_published(stack):
    db = stack.setup(quiet(), {**cloud(1), **{"lake-brain": cloud(2, ok=False)["wind-hourly"]}})
    assert OR.main(stack.argv) == 0
    s = stack.pub(db)["summary"]["brains"]
    assert s["wind"]["missingArtifacts"] == 1 and s["wind"]["published"] == 0 and s["lake-brain"]["runs"] == 1
    assert {x["reason"] for x in s["wind"]["problems"]} == {"ARTIFACT_MISSING"}


def test_an_artifact_changed_after_collection_is_rejected_and_never_reaches_the_publisher(stack):
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0                                         # unarmed: collected and pinned, held
    assert rec_of(stack.paths["ledger"])["publication"]["reason"] == "PUBLISHER_UNARMED"
    other = wind_artifact(n=1, speed=99.0)
    stack.rig.store.put(ref.location, json.dumps(other).encode())          # someone rewrites the stored bytes
    stack.arm["live"] = stack.rig.live                                      # Publisher armed later
    assert OR.main(stack.argv) == 0
    r = rec_of(stack.paths["ledger"])
    assert r["artifact"]["state"] == "INVALID" and r["artifact"]["problems"] == ["DIGEST_CHANGED_AFTER_COLLECTION"]
    assert r["publication"]["outcome"] == "REJECTED" and r["publication"]["reason"] == "ARTIFACT_CHANGED_AFTER_COLLECTION" and stack.rig.rtdb.updates == []


def test_a_non_canonical_artifact_in_the_store_is_invalid(stack):
    art = wind_artifact(n=1)
    stack.rig.store.put("artifacts/wind/" + art["lineage"]["artifactId"] + "/artifact.json", json.dumps(art, indent=2).encode(), if_generation_match=0)
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0
    r = rec_of(stack.paths["ledger"])
    assert r["artifact"]["problems"] == ["NOT_CANONICAL"] and r["publication"]["outcome"] == "NOT_REQUESTED"


# 7. interruption, retry and recovery -----------------------------------------------------------------------------------------------------------------------------------
def test_publisher_outage_is_retried_in_a_later_cycle_and_publishes_exactly_once(stack):
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    real = stack.rig.live
    boom = {"on": True}

    class Flaky:
        def publish(self, r):
            if boom["on"]:
                raise ConnectionError("publisher unreachable")
            return real.publish(r)
    stack.arm["live"] = Flaky()
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0
    p = rec_of(stack.paths["ledger"])["publication"]
    assert p["outcome"] == "FAILED" and p["retryable"] is True and p["reason"].startswith("PUBLISHER_ERROR") and p["attempts"] == 1
    assert OR.main(stack.argv) == 0 and rec_of(stack.paths["ledger"])["publication"]["attempts"] == 1       # backoff not elapsed: not hammered
    led = json.load(open(stack.paths["ledger"]))
    for r in led["records"].values():                                       # time passes
        r["publication"]["nextAttemptAfter"] = "2000-01-01T00:00:00Z"
    json.dump(led, open(stack.paths["ledger"], "w"))
    boom["on"] = False
    assert OR.main(stack.argv) == 0
    p = rec_of(stack.paths["ledger"])["publication"]
    assert p["outcome"] == "PUBLISHED" and p["attempts"] == 2
    n = len(stack.rig.rtdb.updates)
    assert OR.main(stack.argv) == 0 and len(stack.rig.rtdb.updates) == n


def test_a_failure_inside_the_stage_never_breaks_the_cycle_or_the_scores(stack, monkeypatch):
    db = stack.setup(quiet(), cloud())
    monkeypatch.setattr(PS, "run_stage", lambda **k: (_ for _ in ()).throw(RuntimeError("ledger disk full")))
    assert OR.main(stack.argv) == 0
    assert db.tree["control"]["orchestrator"]["publication"]["state"] == "FAILED"
    assert "scores" in db.tree["control"]["orchestrator"]


def test_no_artifact_store_configured_is_reported_unavailable(stack, monkeypatch):
    db = stack.setup(quiet(), cloud())
    assert OR.main(["--coordinate-publication"]) == 0
    assert db.tree["control"]["orchestrator"]["publication"]["state"] == "UNAVAILABLE"


# 8. output-change evidence replaces UNKNOWN; scoring triggers are not altered -----------------------------------------------------------------------------------------
def test_second_artifact_with_different_output_marks_the_execution_output_changed(stack):
    stack.rig.ref(wind_artifact(n=1))
    stack.rig.ref(wind_artifact(n=2, speed=9.0, minutes=60, executionId=uuid4(1002)))
    ex = {"wind-hourly": cloud(1)["wind-hourly"] + cloud(2)["wind-hourly"]}
    db = stack.setup(quiet(), ex)
    assert OR.main(stack.argv) == 0
    changes = json.load(open(stack.paths["out"]))["outputChanged"]
    assert changes[uuid4(1001)]["outputChanged"] == "UNKNOWN" and changes[uuid4(1002)]["outputChanged"] == "YES"       # first artifact: no baseline; second differs
    stack.rig.ref(wind_artifact(n=3, speed=9.0, minutes=120, executionId=uuid4(1003)))                                # same content again, later
    stack.setup(quiet(), {"wind-hourly": cloud(1)["wind-hourly"] + cloud(2)["wind-hourly"] + cloud(3)["wind-hourly"]})
    assert OR.main(stack.argv) == 0
    assert json.load(open(stack.paths["out"]))["outputChanged"][uuid4(1003)]["outputChanged"] == "NO"


# 9. M08 in the execution path -------------------------------------------------------------------------------------------------------------------------------------------
def test_dispatch_gate_blocks_aliases_unknowns_and_double_dispatch_of_the_legacy_package():
    d = []
    ok = OR.gate_dispatch({"wind", "fish", "no-such-brain", "biological-state", "fish-knowledge", "fish-behavior"}, d)
    assert ok == {"wind", "biological-state"}
    why = {x["brainId"]: x["why"] for x in d}
    assert why["fish"].startswith("NONCANONICAL_BRAIN_KEY") and why["no-such-brain"].startswith("UNREGISTERED_BRAIN")
    assert why["fish-knowledge"].startswith("DOUBLE_DISPATCH_PREVENTED") and why["fish-behavior"].startswith("DOUBLE_DISPATCH_PREVENTED")


def test_real_cycle_dispatches_only_recognised_owners_when_enabled(stack):
    t = quiet()
    t["brains"]["wind"]["lastSuccessfulRun"] = ago(9)
    stack.setup(t)
    assert OR.main([]) == 0
    assert set(stack.calls["start"]) <= {"wind", "lake-brain", "water-temp", "water-clarity"} and "wind" in stack.calls["start"]


# 10. ownership boundaries in what the cycle actually writes ----------------------------------------------------------------------------------------------------------
def test_everything_the_cycle_writes_is_orchestrator_owned_and_no_brain_or_score_path_is_touched(stack):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    t = quiet()
    t["brains"]["wind"]["lastSuccessfulRun"] = ago(9)
    db = stack.setup(t, cloud())
    assert OR.main(stack.argv) == 0
    keys = [k for w in db.writes for k in w]
    assert keys
    for k in keys:
        assert DO.platform_path_role(k) == DO.ORCHESTRATOR, f"{k} is not an Orchestrator-owned path"
        assert not k.startswith(("brains/", "scores", "access", "species"))


# 11. reversible cutover: rolling a Brain back to its direct writer stops requests and never rewrites what the Publisher already published ---------------------------------
def test_rollback_to_direct_write_stops_publication_without_touching_published_data(stack):
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.arm["live"] = stack.rig.live
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    db = stack.setup(quiet(), cloud(1))
    assert OR.main(stack.argv) == 0 and rec_of(stack.paths["ledger"])["publication"]["outcome"] == "PUBLISHED"
    before = [dict(u) for u in stack.rig.rtdb.updates]
    stack.cutover(wind={"state": "DIRECT_WRITE"})                           # owner rolls the Brain back
    stack.rig.ref(wind_artifact(n=2, speed=7.0, minutes=60, executionId=uuid4(1002)))
    stack.setup(quiet(), {"wind-hourly": cloud(1)["wind-hourly"] + cloud(2)["wind-hourly"]})
    assert OR.main(stack.argv) == 0
    led = json.load(open(stack.paths["ledger"]))["records"]
    new = next(r for r in led.values() if r["runId"] == uuid4(1002))
    assert new["publication"]["outcome"] == "NOT_REQUESTED" and new["publication"]["reason"] == "DIRECT_WRITER_ACTIVE" and new["writePath"] == "DIRECT_WRITE_PRE_CUTOVER"
    assert stack.rig.rtdb.updates == before                                  # the rollback is a mode change: nothing was rewritten
    assert rec_of(stack.paths["ledger"])["publication"]["outcome"] == "PUBLISHED"       # the earlier publication stays recorded as published


# 12. durable ledger: no ledger file, the cycle persists its records in the private store and a restarted worker resumes from them ------------------------------------------
def test_without_a_ledger_file_the_records_live_in_the_store_and_survive_a_restart(stack):
    from sector_brain_platform.publication_coordination import StoreLedger
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    argv = [x for x in stack.argv if x not in ("--publication-ledger", stack.paths["ledger"])]
    stack.arm["live"] = None                                                 # first worker: Publisher unarmed
    db = stack.setup(quiet(), cloud())
    assert OR.main(argv) == 0
    wind = [r for r in StoreLedger(stack.rig.store).records("wind")]
    assert [r["publication"]["reason"] for r in wind] == ["PUBLISHER_UNARMED"] and not os.path.exists(stack.paths["ledger"])
    stack.arm["live"] = stack.rig.live                                       # a later worker (new process, nothing in memory) with the Publisher armed
    stack.setup(quiet(), cloud())
    assert OR.main(argv) == 0
    r = StoreLedger(stack.rig.store).records("wind")[0]
    assert r["publication"]["outcome"] == "PUBLISHED" and r["publication"]["attempts"] == 1


# 13. one authoritative cutover order (Cortex PL-10) ------------------------------------------------------------------------------------------------------------------------
def test_cutover_document_enforces_the_recorded_order(tmp_path):
    def load(brains):
        p = tmp_path / "c.json"
        json.dump({"schema": PS.CUTOVER_SCHEMA, "brains": brains}, open(p, "w"))
        return PS.load_cutover(str(p))
    ok = {"state": "CENTRAL", "approvalRef": "a"}
    cut, problems = load({"water-clarity": ok, "wind": ok, "water-temp": ok})
    assert sorted(cut) == ["water-clarity", "water-temp", "wind"] and problems == []                         # the recorded order, in full
    cut, problems = load({"water-clarity": ok, "water-temp": ok})                                            # skips wind
    assert sorted(cut) == ["water-clarity"] and problems[0]["kind"] == "CUTOVER_ORDER"
    cut, problems = load({"wind": {**ok, "orderReviewRef": "review/1"}})                                    # an explicit order review is the only way to change it
    assert sorted(cut) == ["wind"] and problems == []
    cut, problems = load({"wind": {"state": "DIRECT_WRITE"}, "depth": {"state": "DIRECT_WRITE"}})            # DIRECT_WRITE is always allowed (rollback)
    assert problems == [] and all(e["state"] == "DIRECT_WRITE" for e in cut.values())


# 14. operational health stays with the Orchestrator and is derived from what the Publisher published ---------------------------------------------------------------------
def test_health_mirror_derives_only_from_published_data_and_writes_only_orchestrator_paths(stack, monkeypatch):
    from sector_brain_platform import health_mirror as HM
    src = HM._clarity_source_ids()[0]
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.arm["live"] = stack.rig.live
    stack.cutover(wind={"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"})
    monkeypatch.setitem(HM.SPECS, "wind", {"registryChildren": ("status", "staleLakeCount"), "sources": lambda: (src,)})
    t = quiet()
    t["brains"]["wind"].update({"status": "HEALTHY", "staleLakeCount": 2})
    t["sources"] = {src: {"health": "OK", "lastFetchAt": "2026-10-29T00:00:00Z", "failures24h": 0}}
    db = stack.setup(t, cloud())
    assert OR.main(stack.argv) == 0
    assert db.tree["health"]["brains"]["wind"]["status"] == "HEALTHY" and db.tree["health"]["brains"]["wind"]["staleLakeCount"] == 2
    assert db.tree["health"]["sources"][src] == {"status": "OK", "lastFetchAt": "2026-10-29T00:00:00Z", "failures24h": 0}
    assert db.pub if False else stack.pub(db)["healthMirror"]["wind"]["written"] is True
    for w in db.writes:
        for k in w:
            assert DO.platform_path_role(k) == DO.ORCHESTRATOR, k
    n = len(db.writes)
    assert OR.main(stack.argv) == 0
    assert stack.pub(db)["healthMirror"]["wind"]["changed"] == 0                  # nothing to change the second time: no rewrite


def test_health_mirror_never_runs_for_a_brain_that_was_not_published(stack, monkeypatch):
    from sector_brain_platform import health_mirror as HM
    monkeypatch.setitem(HM.SPECS, "wind", {"registryChildren": ("status",), "sources": None})
    stack.rig.ref(wind_artifact(n=1))
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0                                                    # pre-cutover: the legacy writer still owns what it writes today
    assert stack.pub(db)["healthMirror"] == {} and "wind" not in (db.tree.get("health") or {}).get("sources", {})


# 15. the bucket store and the dry run -----------------------------------------------------------------------------------------------------------------------------------
def test_bucket_store_is_built_only_from_the_configured_bucket_and_never_without_it(monkeypatch):
    from sector_brain_platform.object_bucket import GcsRestObjectStore
    assert OR.build_publication_store(None, None) is None
    monkeypatch.setattr(OR, "TokenProvider", lambda *a, **k: object())
    s = OR.build_publication_store(None, "some-bucket")
    assert isinstance(s, GcsRestObjectStore) and s.bucket == "some-bucket"


def test_a_dry_run_cycle_writes_nothing_to_the_artifact_store(stack):
    stack.rig.ref(wind_artifact(n=1))
    before = sorted(stack.rig.store.list(""))  if hasattr(stack.rig.store, "list") else None
    db = stack.setup(quiet(), cloud())
    assert OR.main(["--dry-run"] + stack.argv) == 0
    assert sorted(stack.rig.store.list("exports/")) == [] and sorted(stack.rig.store.list("publishes/")) == []
    assert db.writes == []                                                              # and no database write either


def test_the_shipped_cutover_document_is_valid_and_lists_only_water_clarity():
    cut, problems = PS.load_cutover(os.path.join(HERE, "..", "publication-cutover.json"))
    assert problems == [] and {b: e["state"] for b, e in cut.items()} == {"water-clarity": "CENTRAL"}
