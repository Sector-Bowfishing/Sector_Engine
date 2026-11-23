"""_wsw_run_ledger: append-only, hash-chained run binding for pre-registered research protocols (offline, stdlib)."""
import datetime as dt
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _wsw_run_ledger as L  # noqa: E402

UTC = dt.timezone.utc


class Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 11, 23, 12, tzinfo=UTC)

    def __call__(self):
        self.t += dt.timedelta(seconds=1)
        return self.t


def _led(tmp_path, clock=None, pid="P-1", sha="a" * 64):
    return L.RunLedger(str(tmp_path / "runs" / pid), pid, sha, clock=clock or Clock())


def test_first_run_counts_and_a_second_is_refused(tmp_path):
    clock = Clock()
    led = _led(tmp_path, clock=clock)
    with led.step("rows", "pw", {"x": 1}) as run:
        run.writing()
        run.outputs = {"rows": "h"}
    assert run.run_number == 1 and led.completed("rows", "pw")["outputs"] == {"rows": "h"}
    with pytest.raises(L.LedgerRefused):
        with led.step("rows", "pw", {"x": 2}):
            pass
    other = L.RunLedger(led.folder, "P-1", "a" * 64, clock=clock)     # a second handle (another --out) sees the same binding
    with pytest.raises(L.LedgerRefused):
        with other.step("rows", "pw", {}):
            pass
    assert [e["kind"] for e in led.entries()] == ["START", "END", "REFUSED", "REFUSED"]
    with led.step("rows", "h2", {}):                                    # another window is its own step
        pass


def test_an_abort_before_output_allows_a_retry_with_its_run_number(tmp_path):
    led = _led(tmp_path)
    with pytest.raises(RuntimeError):
        with led.step("fit", "cal_h1", {}):
            raise RuntimeError("network down")
    assert led.attempts("fit", "cal_h1")[0]["status"] == "ABORTED_NO_RESULT"
    with led.step("fit", "cal_h1", {}) as run:
        run.outputs = {"fitSha256": "f"}
    assert run.run_number == 2


def test_a_failure_after_writing_or_a_crash_blocks_the_step(tmp_path):
    led = _led(tmp_path)
    with pytest.raises(OSError):
        with led.step("score", "pw", {}) as run:
            run.writing()
            raise OSError("disk")
    assert led.attempts("score", "pw")[0]["status"] == "FAILED"
    with pytest.raises(L.LedgerRefused):
        with led.step("score", "pw", {}):
            pass
    gen = led.step("rows", "pw", {})
    gen.__enter__()                                                      # a SIGKILL: START with no END
    assert led.attempts("rows", "pw")[0]["status"] == "STARTED"
    with pytest.raises(L.LedgerRefused):
        with led.step("rows", "pw", {}):
            pass


def test_the_chain_detects_edits_and_foreign_ledgers(tmp_path):
    led = _led(tmp_path)
    with led.step("fit", "cal_h1", {}) as run:
        run.outputs = {"fitSha256": "f"}
    good = open(led.path).read()
    open(led.path, "w").write(good.replace('"f"', '"g"'))               # last line edited: the head catches it
    with pytest.raises(L.LedgerRefused):
        led.entries()
    lines = good.splitlines(True)
    open(led.path, "w").write(lines[0].replace('"cal_h1"', '"pw"') + "".join(lines[1:]))   # earlier line edited: the chain
    with pytest.raises(L.LedgerRefused):
        led.entries()
    open(led.path, "w").write(lines[0])                                  # truncated
    with pytest.raises(L.LedgerRefused):
        led.entries()
    led2 = _led(tmp_path, pid="P-2")
    with led2.step("fit", "cal_h1", {}):
        pass
    with pytest.raises(L.LedgerRefused):
        L.RunLedger(led2.folder, "P-2", "b" * 64).entries()             # same id, other protocol sha


def test_a_clock_earlier_than_the_newest_line_is_refused(tmp_path):
    c = Clock()
    led = _led(tmp_path, clock=c)
    led.log("fetch", "pw", "COMPLETED")
    c.t -= dt.timedelta(hours=1)
    with pytest.raises(L.LedgerRefused):
        led.log("fetch", "pw", "COMPLETED")


def test_tree_hash_and_write_once(tmp_path):
    d = tmp_path / "store"
    (d / "a").mkdir(parents=True)
    (d / "a" / "x.json").write_text("1")
    (d / "y.json").write_text("2")
    (d / "y.json.tmp").write_text("ignored")
    h1 = L.tree_hash(str(d))
    assert h1["files"] == 2 and h1["hashMethod"] == "sha256-tree-v1" and h1["exists"]
    (d / "a" / "x.json").unlink()
    assert L.tree_hash(str(d))["collectionSha256"] != h1["collectionSha256"]
    assert not L.tree_hash(str(tmp_path / "none"))["exists"]
    p = str(tmp_path / "m.json")
    s = L.write_once_json(p, {"a": 1})
    assert L.write_once_json(p, {"a": 1}) == s
    with pytest.raises(L.LedgerRefused):
        L.write_once_json(p, {"a": 2})
    L.atomic_write_json(str(tmp_path / "b.json"), {"n": 1})
    assert json.load(open(tmp_path / "b.json")) == {"n": 1} and not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
