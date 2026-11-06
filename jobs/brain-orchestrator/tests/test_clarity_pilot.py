"""The pilot's rollback never overwrites newer data (owner condition 5/7); the pilot tool refuses live writes without the explicit flag."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import clarity_pilot as CP                                                         # noqa: E402
from sector_brain_platform.publisher.canonical import canonical_bytes, sha256_ref   # noqa: E402
from sector_brain_platform.publisher_live.fakes import FakeRtdb                                      # noqa: E402


def sha(v):
    return sha256_ref(canonical_bytes(v))


def world(live):
    base = {"values": {"lakes/a/states/waterClarity": {"v": 1}, "validation/water-clarity": {"ok": True}}}
    written = {"lakes/a/states/waterClarity": sha({"v": 1}), "validation/water-clarity": sha({"ok": True})}
    return base, written, FakeRtdb(live)


def test_restore_leaves_newer_values_alone_and_removes_only_the_pilots_own_publication_record():
    base, written, db = world({"lakes": {"a": {"states": {"waterClarity": {"v": 2}}}}, "validation": {"water-clarity": {"ok": True}},
                               "brains": {"water-clarity": {"publication": {"publishId": "P1"}}}})
    out = CP.restore(db, base, written, "P1")
    assert [s["path"] for s in out["skipped"]] == ["lakes/a/states/waterClarity"]          # newer intelligence is never overwritten
    assert out["removed"] == ["brains/water-clarity/publication"] and out["alreadyEqualToPrePilot"] == 1
    assert db.get("lakes/a/states/waterClarity") == {"v": 2} and db.get("brains/water-clarity/publication") is None


def test_restore_does_not_remove_a_later_publication_record():
    base, written, db = world({"lakes": {"a": {"states": {"waterClarity": {"v": 1}}}}, "validation": {"water-clarity": {"ok": True}},
                               "brains": {"water-clarity": {"publication": {"publishId": "P2"}}}})
    out = CP.restore(db, base, written, "P1")
    assert out["removed"] == [] and any("later publication" in s["why"] for s in out["skipped"])
    assert db.get("brains/water-clarity/publication") == {"publishId": "P2"}




# ------------------------------------------------------------------------------------------- Sector_Ops #51 O6: rollback of a real publish, verify by publish id
class _Res:
    def __init__(self, value, pid="R1"):
        self.result, self.codes, self.detail, self.publish_id = type("V", (), {"value": value})(), [], "", pid
        self.record = {"rollback": {"fromPublishId": "P2", "restoredPublishId": "P1"}}


class _Live:
    def __init__(self, value="ROLLED_BACK"):
        self.value, self.calls = value, []

    def rollback(self, brain, pid, *, approval_ref, reason):
        self.calls.append((brain, pid, approval_ref, reason))
        return _Res(self.value)


def _wire(monkeypatch, live):
    monkeypatch.setattr(CP, "_tokens", lambda imp: object())
    monkeypatch.setattr(CP, "_gcs_store", lambda bucket, tokens: object())
    monkeypatch.setattr(CP, "_publisher", lambda *a, **k: live)


def test_rollback_needs_yes_live_and_every_reference(tmp_path, monkeypatch):
    live = _Live()
    _wire(monkeypatch, live)
    with pytest.raises(SystemExit, match="--yes-live"):
        CP.main(["rollback", "--out", str(tmp_path), "--bucket", "b", "--publish-id", "P2", "--approval-ref", "r", "--reason", "x"])
    with pytest.raises(SystemExit, match="needs --publish-id"):
        CP.main(["rollback", "--out", str(tmp_path), "--bucket", "b", "--yes-live", "--publish-id", "P2", "--reason", "x"])
    assert live.calls == []                                                          # nothing was rolled back


def test_rollback_calls_the_publisher_and_records_the_result_without_a_ref_file(tmp_path, monkeypatch):
    live = _Live()
    _wire(monkeypatch, live)                                                         # no ref.json in the folder: rollback does not need one
    assert CP.main(["rollback", "--out", str(tmp_path), "--bucket", "b", "--yes-live", "--publish-id", "P2", "--approval-ref", "owner/o6", "--reason", "bad data"]) == 0
    assert live.calls == [("water-clarity", "P2", "owner/o6", "bad data")]
    import json
    assert json.load(open(tmp_path / "rollback-result.json"))["result"] == "ROLLED_BACK"


def test_rollback_that_does_not_roll_back_exits_non_zero(tmp_path, monkeypatch):
    _wire(monkeypatch, _Live("NOT_AUTHORIZED"))
    assert CP.main(["rollback", "--out", str(tmp_path), "--bucket", "b", "--yes-live", "--publish-id", "P2", "--approval-ref", "r", "--reason", "x"]) == 9
