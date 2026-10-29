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


