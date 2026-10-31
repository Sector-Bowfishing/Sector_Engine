"""CENTRAL mode (Cortex 3.1 FD-15): the Water Clarity run stores ONE sealed artifact and performs NO database write; the direct writer is retired (X14)."""
import json

import pytest

import clarity_support as S

WRITE_VERBS = ("PATCH", "PUT", "POST", "DELETE")


def test_central_mode_writes_no_database_path_and_stores_one_valid_artifact():
    flat, t, rc = S.real_run_updates()
    assert flat and [m for m, _, _ in t.calls if m in WRITE_VERBS] == []                                     # a full payload was sealed; zero database writes of any kind
    keys = list(t.store.list("artifacts/water-clarity/"))
    assert len(keys) == 1 and keys[0].endswith("/artifact.json")
    art = json.loads(t.store.get(keys[0]))
    assert art["lineage"]["brainId"] == "water-clarity" and art["lineage"]["lifecycle"] == "CALIBRATION"
    assert not any(m["path"].startswith("/health/") for sec in art["sections"] for m in sec["mutations"])
    assert rc == 0


def test_the_run_reads_only_child_paths_of_its_own_brain_node():
    _, t, _ = S.real_run_updates()
    gets = [u.split(".firebaseio.com/", 1)[-1].split(".json", 1)[0] for m, u, _ in t.calls if m == "GET"]
    assert "brains/water-clarity" not in gets and {"brains/water-clarity/version", "brains/water-clarity/lastSuccessfulRun"} <= set(gets)


def test_the_payload_never_names_a_whole_brain_node():
    flat, _, _ = S.real_run_updates()
    assert "brains/water-clarity" not in flat and "health/brains/water-clarity" not in flat
    assert flat["brains/water-clarity/brainId"] == "water-clarity"


def test_without_a_mode_the_run_refuses_and_stores_nothing(capsys):
    flat, t, rc = S.real_run_updates(argv=("--batch", "2"))
    assert rc == 2 and flat == {} and t.calls == [] and list(t.store.list("artifacts/")) == []
    assert "REFUSED" in capsys.readouterr().err


def test_the_retired_direct_writer_flag_is_rejected():
    with pytest.raises(SystemExit) as e:
        S.real_run_updates(argv=("--legacy-direct-write", "--batch", "2"))
    assert e.value.code == 2                                                                                 # argparse: unknown option; nothing ran
