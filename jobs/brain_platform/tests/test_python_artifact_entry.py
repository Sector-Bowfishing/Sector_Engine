"""python_artifact_entry: the shared artifact mode of the Weather, Moon and Generation Brains (Sector Pulse `<brain>-central`, prepared, off).
Fake Brain hooks and a fake live database only: no network, no credential, no database write."""
import json
import os
import types

import pytest

from sector_brain_platform import python_artifact_entry as E
from sector_brain_platform.knowledge_release import KnowledgeReleaseError
from sector_brain_platform.ownership import OwnershipError  # noqa: F401  (the DryRunStore below enforces ownership)
from sector_brain_platform import DryRunStore


class FakeLive:
    def __init__(self, tree):
        self.tree, self.calls = tree, []

    def get(self, path, shallow=False):
        self.calls.append(path)
        node = self.tree
        for p in [p for p in path.split("/") if p]:
            node = node.get(p) if isinstance(node, dict) else None
        return node


class Dry:
    def __init__(self):
        self._s = DryRunStore({}, brain_id="weather")

    @property
    def patches(self):
        return self._s.patches

    def patch(self, u):
        self._s.update(u)

    def get(self, p):
        return self._s.get(p)


class Built:
    def __init__(self, updates):
        self.artifact = ({"lineage": {"brainId": "weather", "executionId": "e", "artifactSchema": "test"}, "updates": updates}
                         if updates else None)
        self.dropped, self.deletes = [], []


def test_overlay_applies_this_runs_writes_over_the_live_value_in_order():
    live = {"a": 1, "b": {"c": 2}}
    patches = [{"x/b/c": 3, "x/b/d": 4}, {"x/a": None}, {"y": 5}]
    assert E.overlay(live, "x", patches) == {"b": {"c": 3, "d": 4}}
    assert E.overlay(live, "x/b", [{"x": {"b": {"z": 1}}}]) == {"z": 1}
    assert E.overlay(None, "x/b", [{"x/b/c": None}]) is None
    assert E.overlay({"keep": 1}, "x", []) == {"keep": 1}


def test_the_live_view_has_no_write_method_and_reads_come_from_live_with_own_writes_overlaid():
    view = E.LiveReadOnly(FakeLive({"lakes": {"A": {"states": {"weather": {"v": 1}}}}}))
    assert not any(hasattr(view, m) for m in ("patch", "update", "set", "put", "delete"))
    w = E.ReadThroughWriter(Dry(), view)
    assert w.get("lakes/A/states/weather") == {"v": 1}
    w.patch({"lakes/A/states/weather": {"v": 2}})
    assert w.get("lakes/A/states/weather") == {"v": 2} and view.reads == 2
    assert w.flat() == {"lakes/A/states/weather": {"v": 2}}


def _main(tmp_path, argv, *, approved=True, intent="1", produce=None, monkeypatch=None, live=None):
    if intent is None:
        monkeypatch.delenv("TEST_WRITE_APPROVED", raising=False)
    else:
        monkeypatch.setenv("TEST_WRITE_APPROVED", intent)

    def require():
        if not approved:
            raise KnowledgeReleaseError("BLOCKED_AWAITING_APPROVED_RELEASE: release r approval is NOT_RECORDED")

    def default_produce(writer, now, a):
        prev = writer.get("lakes/A/states/weather")
        writer.patch({"lakes/A/states/weather": {"prev": prev, "at": now.isoformat()}})
        return {"ok": True}
    fake = live or FakeLive({"lakes": {"A": {"states": {"weather": {"v": 1}}}}})
    return E.main(argv, brain_id="weather", write_intent_env="TEST_WRITE_APPROVED", require_approved=require, new_dry_writer=Dry,
                  produce=produce or default_produce, seal=lambda u, ctx: Built(u), live_factory=lambda url, b: E.LiveReadOnly(fake))


def _args(tmp_path, *extra):
    return ["--artifact-dir", str(tmp_path / "store"), *extra]


def test_a_hand_off_seals_one_artifact_from_the_live_previous_state(tmp_path, monkeypatch, capsys):
    emit = tmp_path / "artifact.json"
    assert _main(tmp_path, _args(tmp_path, "--emit", str(emit), "--read-rtdb"), monkeypatch=monkeypatch) == 0
    art = json.load(open(emit))
    assert art["updates"]["lakes/A/states/weather"]["prev"] == {"v": 1}
    assert os.listdir(tmp_path / "store")
    assert _main(tmp_path, _args(tmp_path, "--emit", str(emit), "--read-rtdb"), monkeypatch=monkeypatch) == 2   # never overwritten


@pytest.mark.parametrize("argv,why", [
    (["--emit", "{t}/a.json"], "needs --read-rtdb"),
    (["--rtdb-url", "https://x.firebaseio.com"], "--rtdb-url needs --read-rtdb"),
    (["--execution-id", "nope"], "not a UUID"),
    (["--emit", "gs://b/a.json", "--read-rtdb"], "new local file"),
])
def test_refusals_store_nothing(tmp_path, monkeypatch, capsys, argv, why):
    argv = [a.replace("{t}", str(tmp_path)) for a in argv]
    assert _main(tmp_path, _args(tmp_path, *argv), monkeypatch=monkeypatch) == 2
    assert why in capsys.readouterr().err and not (tmp_path / "store").exists()


def test_the_write_gates_of_run_py_write_hold(tmp_path, monkeypatch, capsys):
    a = _args(tmp_path, "--emit", str(tmp_path / "a.json"), "--read-rtdb")
    assert _main(tmp_path, a, approved=False, monkeypatch=monkeypatch) == 2
    assert "BLOCKED_AWAITING_APPROVED_RELEASE" in capsys.readouterr().err
    assert _main(tmp_path, a, intent=None, monkeypatch=monkeypatch) == 3
    assert _main(tmp_path, a, intent="yes", monkeypatch=monkeypatch) == 3
    assert "TEST_WRITE_APPROVED=1" in capsys.readouterr().err
    assert not (tmp_path / "store").exists() and not (tmp_path / "a.json").exists()


def test_a_run_with_no_write_set_stores_nothing(tmp_path, monkeypatch):
    a = _args(tmp_path, "--emit", str(tmp_path / "a.json"), "--read-rtdb")
    assert _main(tmp_path, a, produce=lambda w, n, x: {"ok": False}, monkeypatch=monkeypatch) == 4
    assert not (tmp_path / "a.json").exists()
