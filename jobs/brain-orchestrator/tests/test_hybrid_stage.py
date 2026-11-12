"""Staged hybrid moves for Lake, Water Temp and Wind (tools/ops/hybrid_stage.py; Roadmap Sector_Ops #23 section 2, Sector_Ops #51).

The staged fragments are read by no runtime. Lake is APPLIED (owner, Sector_Ops #51, 2026-11-12): the live policies name Water Clarity and Lake, and
`check` verifies Lake's live entries against its fragment. Water Temp and Wind stay staged. Applied in memory (to the policies as they were before the
Lake flip, for Lake), each fragment gives policies the REAL loaders accept, and the cycle watchdog then allows exactly that Brain's lease, grants,
artifacts and lake-bounded publications."""
import datetime as dt
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))

import hybrid_stage as HS                                                     # noqa: E402
from sector_brain_platform import cycle_watchdog as WD                       # noqa: E402
from sector_brain_platform import runner_lease as RL                         # noqa: E402
from sector_brain_platform.publisher.storage import MemoryObjectStore        # noqa: E402

pytestmark = [pytest.mark.watchdog]

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)
STAGED = ("water-temp", "wind")
APPLIED = ("lake-brain",)
LAKE_REF = "owner-approval-2026-11-12/sector-ops-51-lake-on-pulse"


def live():
    """The live policies with every APPLIED Brain taken out again: the world each fragment is merged into (Lake: the policies before its flip)."""
    r, w, c = HS._read(HS.RUNNER_POLICY), HS._read(HS.WATCHDOG_POLICY), HS._read(HS.CUTOVER)
    for b in APPLIED:
        r["primary"].pop(b, None)
        r.get("approvals", {}).pop(b, None)
        w["brains"].pop(b, None)
        c["brains"].pop(b, None)
    return r, w, c


def committed():
    return HS._read(HS.RUNNER_POLICY), HS._read(HS.WATCHDOG_POLICY), HS._read(HS.CUTOVER)


def _pre_flip_files(tmp_path, monkeypatch):
    for name, doc in zip(("runner.json", "watchdog.json", "cutover.json"), live()):
        (tmp_path / name).write_text(json.dumps(doc, indent=2) + "\n")
    monkeypatch.setattr(HS, "RUNNER_POLICY", str(tmp_path / "runner.json"))
    monkeypatch.setattr(HS, "WATCHDOG_POLICY", str(tmp_path / "watchdog.json"))
    monkeypatch.setattr(HS, "CUTOVER", str(tmp_path / "cutover.json"))


def put(store, key, doc):
    store.put(key, json.dumps(doc).encode())


def test_flags_off_the_live_policies_name_none_of_the_staged_brains():
    r, w, c = committed()
    for b in STAGED:
        assert b not in r["primary"] and b not in w["brains"] and b not in c["brains"]
        assert RL.primary(RL.load_policy(), b) == "cloud"


def test_lake_is_applied_and_its_live_entries_match_its_fragment():
    r, w, c = committed()
    assert RL.primary(RL.load_policy(), "lake-brain") == "pulse" and r["approvals"]["lake-brain"] == LAKE_REF
    assert w["brains"]["lake-brain"]["approvalRef"] == LAKE_REF and c["brains"]["lake-brain"]["approvalRef"] == LAKE_REF
    assert HS.is_live("lake-brain", r, w, c) and HS.live_problems(HS.fragments()["lake-brain"], r, w, c) == []


def test_live_check_catches_drift_between_the_live_policies_and_the_fragment():
    f = HS.fragments()["lake-brain"]
    r, w, c = committed()
    w["brains"]["lake-brain"]["lakes"] = w["brains"]["lake-brain"]["lakes"] + ["Lake_Lanier_GA"]
    assert any("holder/lakes differ" in p for p in HS.live_problems(f, r, w, c))
    r, w, c = committed()
    del c["brains"]["lake-brain"]["orderReviewRef"]
    assert any("order review" in p for p in HS.live_problems(f, r, w, c))
    r, w, c = committed()
    assert any("still lists" in p for p in HS.live_problems(dict(f, blockers=["x"]), r, w, c))


def test_no_runtime_reads_the_stage_folder():
    out = subprocess.run(["git", "grep", "-l", "hybrid-stage", "--", "jobs", "brains"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert [p for p in out if not p.startswith("jobs/brain-orchestrator/tests/")] == []


def test_three_fragments_ordered_by_readiness_each_with_its_blockers():
    frags = HS.fragments()
    assert sorted(frags) == sorted(STAGED + APPLIED)
    assert [b for b, _ in sorted(frags.items(), key=lambda kv: kv[1]["readiness"])] == ["lake-brain", "water-temp", "wind"]
    for f in frags.values():
        if f["brainId"] in APPLIED:
            assert f["blockers"] == [], f"{f['brainId']} is live: applying it confirmed its blockers were done"
        else:
            assert f["blockers"], f"{f['brainId']} is not ready: its blockers must be listed"
        assert f["watchdog"]["holder"] == "pulse" == f["runnerPolicy"]["primary"]


def test_public_fragments_carry_no_iam_detail():
    for f in HS.fragments().values():
        text = json.dumps(f)
        for word in ("roles/", "serviceAccount", "iam.gserviceaccount.com", "objectCreator", "objectViewer", "objectUser"):
            assert word not in text, f"{f['brainId']}: {word} (IAM details live on Sector_Ops #51 only)"


@pytest.mark.parametrize("brain", ["lake-brain", "wind"])
def test_applied_in_memory_the_real_loaders_make_it_central_with_pulse_primary(brain):
    merged = HS.merged(HS.fragments()[brain], "owner-approval-test", *live())
    assert HS.verify(*merged, brain) == []
    pol = merged[0]
    assert RL.primary(pol, brain) == "pulse"
    ok, why = RL.cloud_may_start(MemoryObjectStore(), pol, brain, NOW)               # the legacy cloud job can no longer start
    assert (ok, why) == (False, "PRIMARY_PULSE_FAILOVER_OFF")
    assert RL.primary(pol, "water-clarity") == "pulse"                               # Water Clarity is untouched


def test_water_temp_needs_an_order_review_before_it_can_be_central():
    merged = HS.merged(HS.fragments()["water-temp"], "owner-approval-test", *live())
    probs = HS.verify(*merged, "water-temp")
    assert len(probs) == 1 and "CUTOVER_ORDER" in probs[0] and "wind" in probs[0]
    _, _, c = merged
    c["brains"]["water-temp"]["orderReviewRef"] = "owner-approval-test/wt-ord"      # what the owner's WT-ORD decision adds
    assert HS.verify(merged[0], merged[1], c, "water-temp") == []


def test_lake_carries_the_recorded_l2_order_review():
    _, _, c = HS.merged(HS.fragments()["lake-brain"], "owner-approval-test", *live())
    assert c["brains"]["lake-brain"]["orderReviewRef"] == "owner-approval-2026-11-02/sector-ops-50#L-2"


def _lake_world(lakes_written):
    s = MemoryObjectStore()
    put(s, "exports/runners/leases/water-clarity.json", {"holder": "pulse", "cycleId": "c1"})
    put(s, "exports/runners/leases/lake-brain.json", {"holder": "pulse", "cycleId": "l1"})
    put(s, "exports/runners/grants/lake-brain/l1.json", {"grantedAt": "2026-11-20T11:00:00Z"})
    put(s, "artifacts/lake-brain/sha256-l/artifact.json", {"lineage": {"generatedAt": "2026-11-20T11:20:00Z"}})
    put(s, "publishes/lake-brain/q1/record.json", {"mode": "LIVE", "result": "PUBLISHED", "status": "COMPLETE", "live": True, "publishedAt": "2026-11-20T11:50:00Z",
                                                   "pathSha256": {f"/lakes/{k}/states/lake": "x" for k in lakes_written}})
    return s


def test_the_watchdog_allows_the_staged_brain_once_applied_and_halts_outside_its_lakes():
    _, w, _ = HS.merged(HS.fragments()["lake-brain"], "owner-approval-test", *live())
    ctl = {"state": "ENABLED", "brains": {"water-clarity": {"enabled": True}, "lake-brain": {"enabled": True}}}
    execs = {"brain-orchestrator": [], "brain-publisher": []}
    res = WD.evaluate(w, store=_lake_world(["Guntersville_AL", "Lake_Hartwell_SC"]), executions=execs, control=ctl, now=NOW)
    assert [t.kind for t in res.trips] == []
    res = WD.evaluate(w, store=_lake_world(["Guntersville_AL", "Lake_Lanier_GA"]), executions=execs, control=ctl, now=NOW)
    assert [t.kind for t in res.trips] == ["PUBLISH_OUTSIDE_LAKES"]
    live_w = live()[1]                                                                # before the flip: the same world halts
    res = WD.evaluate(live_w, store=_lake_world(["Guntersville_AL"]), executions=execs, control=ctl, now=NOW)
    assert "LEASE_OUTSIDE_POLICY" in {t.kind for t in res.trips}


def test_a_cloud_start_of_the_legacy_job_still_halts_after_the_move():
    _, w, _ = HS.merged(HS.fragments()["lake-brain"], "owner-approval-test", *live())
    execs = {"lake-brain": [{"metadata": {"name": "lake-brain-x", "creationTimestamp": "2026-11-20T11:55:00Z"}}]}
    res = WD.evaluate(w, store=MemoryObjectStore(), executions=execs, control=None, now=NOW)
    assert "EXECUTION_OUTSIDE_POLICY" in {t.kind for t in res.trips}


def test_water_temp_apply_takes_the_owners_order_review(tmp_path, monkeypatch):
    for name, src in (("runner.json", HS.RUNNER_POLICY), ("watchdog.json", HS.WATCHDOG_POLICY), ("cutover.json", HS.CUTOVER)):
        (tmp_path / name).write_text(open(src).read())                             # the committed policies, Lake live
    monkeypatch.setattr(HS, "RUNNER_POLICY", str(tmp_path / "runner.json"))
    monkeypatch.setattr(HS, "WATCHDOG_POLICY", str(tmp_path / "watchdog.json"))
    monkeypatch.setattr(HS, "CUTOVER", str(tmp_path / "cutover.json"))
    base = ["apply", "--brain", "water-temp", "--approval-ref", "owner-approval-test", "--blockers-cleared", "--write"]
    assert HS.main(base) == 2                                                          # CUTOVER_ORDER: Wind first, or an order review
    assert HS.main(base + ["--order-review-ref", "owner-approval-test/wt-ord"]) == 0
    assert json.loads((tmp_path / "cutover.json").read_text())["brains"]["water-temp"]["orderReviewRef"] == "owner-approval-test/wt-ord"


def test_lake_names_must_be_rtdb_keys(tmp_path):
    f = json.load(open(os.path.join(HS.STAGE_DIR, "lake-brain.json")))
    f["watchdog"]["lakes"] = ["Guntersville|AL"]
    (tmp_path / "lake-brain.json").write_text(json.dumps(f))
    with pytest.raises(HS.StageError):
        HS.load_fragment(str(tmp_path / "lake-brain.json"))


def test_merge_refuses_no_approval_and_a_brain_already_live():
    f = HS.fragments()["lake-brain"]
    with pytest.raises(HS.StageError):
        HS.merged(f, " ", *live())
    r, w, c = HS.merged(f, "owner-approval-test", *live())
    with pytest.raises(HS.StageError):
        HS.merged(f, "again", r, w, c)


def test_apply_refuses_open_blockers_and_writes_only_with_write(tmp_path, monkeypatch, capsys):
    _pre_flip_files(tmp_path, monkeypatch)
    real = HS.fragments
    monkeypatch.setattr(HS, "fragments", lambda *a: {b: (dict(f, blockers=["an open blocker"]) if b in APPLIED else f) for b, f in real(*a).items()})
    before = {p.name: p.read_text() for p in tmp_path.iterdir()}
    assert HS.main(["apply", "--brain", "lake-brain", "--approval-ref", "owner-approval-test"]) == 2          # blockers open
    assert HS.main(["apply", "--brain", "nope", "--approval-ref", "x"]) == 2
    assert HS.main(["apply", "--brain", "water-temp", "--approval-ref", "x", "--blockers-cleared"]) == 2     # the order review is still missing
    assert HS.main(["apply", "--brain", "lake-brain", "--approval-ref", "owner-approval-test", "--blockers-cleared"]) == 2   # L-2 not restated
    assert HS.main(["apply", "--brain", "lake-brain", "--approval-ref", "owner-approval-test", "--blockers-cleared", "--order-review-ref", "other"]) == 2
    L2 = ["--order-review-ref", "owner-approval-2026-11-02/sector-ops-50#L-2"]
    assert HS.main(["apply", "--brain", "lake-brain", "--approval-ref", "owner-approval-test", "--blockers-cleared"] + L2) == 0
    assert {p.name: p.read_text() for p in tmp_path.iterdir()} == before                                     # diff only
    assert HS.main(["apply", "--brain", "lake-brain", "--approval-ref", "owner-approval-test", "--blockers-cleared", "--write"] + L2) == 0
    assert json.loads((tmp_path / "cutover.json").read_text())["brains"]["lake-brain"]["orderReviewRef"] == L2[1]
    assert RL.primary(RL.load_policy(str(tmp_path / "runner.json")), "lake-brain") == "pulse"
    assert "lake-brain" in WD.load_policy(str(tmp_path / "watchdog.json"))["brains"]
    assert HS.main(["apply", "--brain", "lake-brain", "--approval-ref", "again", "--blockers-cleared"] + L2) == 2   # already live


def test_check_and_show_run_against_the_committed_files(capsys):
    assert HS.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "lake-brain: LIVE (applied), OK" in out and "wind: OK" in out and "water-temp: OK, but needs an order review" in out
    assert HS.main(["show"]) == 0
