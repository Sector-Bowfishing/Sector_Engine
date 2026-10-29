"""CENTRAL mode (Cortex 3.1 FD-15): the Water Clarity run stores ONE sealed artifact and performs NO database write; the direct writer needs an explicit flag."""
import json
import sys
from unittest import mock

import pytest

import clarity_support as S
from sector_brain_platform.publisher import MemoryObjectStore, default_registry


def central_run(monkeypatch, argv):
    store = MemoryObjectStore()
    import sector_brain_platform.object_bucket as ob
    monkeypatch.setattr(ob, "GcsRestObjectStore", lambda bucket, tokens: store)
    return store, S.real_run_updates(argv=argv)


def test_central_mode_writes_no_database_path_and_stores_one_valid_artifact(monkeypatch):
    store, (flat, t, rc) = central_run(monkeypatch, ("--artifact-bucket", "b", "--batch", "2"))
    assert flat == {} and [m for m, _, _ in t.calls if m in ("PATCH", "PUT", "POST", "DELETE")] == []        # zero database writes of any kind
    keys = [k for k in store.list("artifacts/water-clarity/")]
    assert len(keys) == 1 and keys[0].endswith("/artifact.json")
    art = json.loads(store.get(keys[0]))
    assert art["lineage"]["brainId"] == "water-clarity" and art["lineage"]["lifecycle"] == "CALIBRATION"
    assert not any(k.startswith("/health/") for sec in art.get("sections", []) for k in (sec.get("mutations") or [{}]) if isinstance(k, str))
    assert rc in (0, 2)


def test_without_a_mode_the_run_refuses_and_the_direct_writer_needs_its_flag(monkeypatch, capsys):
    store, (flat, t, rc) = central_run(monkeypatch, ("--batch", "2"))
    assert rc == 2 and flat == {} and t.calls == [] and store.list("artifacts/") == []
    assert "REFUSED" in capsys.readouterr().err
    flat, t, rc = S.real_run_updates(argv=("--legacy-direct-write", "--batch", "2"))
    assert flat                                                                                              # the legacy writer still works, but only when named
