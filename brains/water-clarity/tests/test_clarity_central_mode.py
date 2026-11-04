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


FLEET_TOTAL_PATHS = ("brains/water-clarity/readinessCounts", "brains/water-clarity/staleLakeCount", "brains/water-clarity/breakdowns",
                     "health/brains/water-clarity/staleLakeCount")


def test_a_full_run_still_publishes_the_fleet_totals():
    flat, _, _ = S.real_run_updates()
    assert all(p in flat for p in FLEET_TOTAL_PATHS)


@pytest.mark.parametrize("narrow", [("--lakes", "Guntersville|AL,Kentucky Lake|KY"), ("--limit", "1")])
def test_a_partial_run_updates_only_its_own_lakes_and_never_rewrites_the_fleet_totals(narrow):
    flat, t, _ = S.real_run_updates(argv=("--artifact-bucket", "test-artifacts", "--batch", "2", *narrow))
    assert not any(p in flat for p in FLEET_TOTAL_PATHS)                        # absent, so the published totals stay as the last full run left them
    assert not any(k.startswith("lakeFleet/Aleknagik") for k in flat)           # a lake outside the run is not touched
    assert "brains/water-clarity/supportedLakeCount" in flat                   # the directory size is still the whole directory
    art = json.loads(t.store.get(next(iter(t.store.list("artifacts/water-clarity/")))))
    named = {m["path"] for sec in art["sections"] for m in sec["mutations"]}
    assert not any("/" + p in named for p in FLEET_TOTAL_PATHS)                # no SET and no DELETE of a fleet total


# --read-rtdb (Sector_Ops #51: Sector Pulse runs the dry run and hands the artifact off itself, so the dry run must read the previous state)
def test_dry_run_with_read_rtdb_reads_the_previous_state_and_writes_nothing(tmp_path):
    flat, t, rc = S.real_run_updates(argv=("--dry-run", "--read-rtdb", "--out", str(tmp_path), "--batch", "2"))
    gets = [u.split(".firebaseio.com/", 1)[-1].split(".json", 1)[0] for m, u, _ in t.calls if m == "GET"]
    assert {"brains/water-clarity/version", "brains/water-clarity/lastSuccessfulRun"} <= set(gets)
    assert [m for m, _, _ in t.calls if m in WRITE_VERBS] == []
    assert list(t.store.list("artifacts/")) == []                                                            # nothing stored anywhere: the artifact is in --out
    art = json.loads((tmp_path / "artifact.json").read_text())
    assert art["lineage"]["brainId"] == "water-clarity" and rc == 0
    assert json.loads((tmp_path / "run_report.json").read_text())["rtdbWrites"] == 0


def test_dry_run_with_read_rtdb_seals_the_same_payload_as_central_mode(tmp_path):
    central, _, _ = S.real_run_updates()
    dry, _, _ = S.real_run_updates(argv=("--dry-run", "--read-rtdb", "--out", str(tmp_path), "--batch", "2"))
    time_free = lambda d: {k for k in d if "/activity/" not in "/" + k}                                       # activity ids are uuid-like per run
    assert time_free(central) == time_free(dry)


def test_plain_dry_run_still_makes_no_database_call(tmp_path):
    _, t, rc = S.real_run_updates(argv=("--dry-run", "--out", str(tmp_path), "--batch", "2"))
    assert t.calls == [] and rc == 0


@pytest.mark.parametrize("argv", [("--read-rtdb", "--artifact-bucket", "b"), ("--dry-run", "--read-rtdb")])
def test_read_rtdb_outside_a_dry_run_into_a_folder_is_refused(argv, capsys):
    flat, t, rc = S.real_run_updates(argv=(*argv, "--batch", "2"))
    assert rc == 2 and flat == {} and t.calls == []
    assert "REFUSED" in capsys.readouterr().err


def test_the_read_only_view_has_no_write_method():
    import run
    view = run.ReadOnlyRtdb(object())
    assert not any(hasattr(view, m) for m in ("patch", "put", "post", "delete", "update", "set", "write"))
