import json
import os

import pytest

from vegetation_brain import holdout as H


def test_consumed_truth_is_refused_as_a_fresh_holdout(tmp_path):
    for t in ("snohomish-wa-2021-2023", "epa-nla-2017", "umn-mn-plants-1999-2018", "fwc-ltm-lake-pac-pvi-2015-2023"):
        with pytest.raises(H.HoldoutError, match="not a fresh holdout"):
            H.run_once(t, "x", str(tmp_path), lambda p: {}, {})


def test_one_evaluation_per_fresh_truth_set_and_the_seal_is_written_first(tmp_path):
    seen = {}

    def ev(params):
        seen["seal_existed"] = os.path.exists(tmp_path / "new-truth.seal.json")      # sealed BEFORE the evaluator runs
        return {"gates": "NOT_RUN_IN_TEST"}
    rec = H.run_once("new-truth", "abc", str(tmp_path), ev, {"haze": 0.1})
    assert seen["seal_existed"] and rec["status"] == "COMPLETED" and rec["params"] == {"haze": 0.1}
    with pytest.raises(H.HoldoutError, match="already"):
        H.run_once("new-truth", "abc", str(tmp_path), ev, {"haze": 0.2})               # no retry with different parameters


def test_a_crash_leaves_a_started_seal_so_it_cannot_be_retried_quietly(tmp_path):
    def boom(params):
        raise RuntimeError("evaluator crashed")
    with pytest.raises(RuntimeError):
        H.run_once("t2", "abc", str(tmp_path), boom, {})
    assert json.load(open(tmp_path / "t2.seal.json"))["status"] == "STARTED"
    with pytest.raises(H.HoldoutError):
        H.run_once("t2", "abc", str(tmp_path), lambda p: {}, {})


def test_observer_fingerprint_is_stable_and_covers_the_observer_files():
    assert H.observer_fingerprint() == H.observer_fingerprint() and len(H.observer_fingerprint()) == 64
    assert {"observer.py", "shared.py", "contract.py", "validation.py"} == set(H.OBSERVER_FILES)
