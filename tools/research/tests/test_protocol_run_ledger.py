"""Protocol run ledger: a pre-registered step runs once wherever its outputs go. Re-runs refused (also with a new --out folder), the abort
path, chain and tail tampering detected, protocol hash mismatch refused, concurrent begin under the lock, root under --out refused, input
changes detected. Disposable folders only; no network."""
import hashlib
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import protocol_run_ledger as PRL  # noqa: E402
from protocol_run_ledger import ChainBroken, Ledger, LedgerRefusal  # noqa: E402

PID = "wind-strong-wind-v1"
PSHA = hashlib.sha256(b"protocol v1").hexdigest()
OTHER = hashlib.sha256(b"protocol v2").hexdigest()


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv(PRL.ENV_ROOT, raising=False)


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "Sector Research" / "wind-brain"
    r.mkdir(parents=True)
    return r


def ledger(root, **kw):
    return Ledger(root, PID, PSHA, **kw)


def lines(root):
    return (root / "_ledgers" / f"{PID}.jsonl").read_bytes().splitlines()


def run_step(L, step="fit", key="all", out=None):
    run = L.begin(step, key, {"out": str(out) if out else None}, {})
    L.complete(step, key, {}, {"metric": 0.5})
    return run


# ---------- the core rule ----------
def test_first_run_counts_and_rerun_is_refused(root):
    L = ledger(root)
    assert run_step(L) == 1
    assert L.counts("fit", "all") and L.counts("fit", "all", 1)
    with pytest.raises(LedgerRefusal, match="already ran"):
        L.begin("fit", "all", {}, {})
    assert L.first("fit", "all")["result"] == {"metric": 0.5}


def test_new_out_folder_and_new_process_still_refused(root, tmp_path):
    out1, out2 = tmp_path / "out1", tmp_path / "out2"
    run_step(ledger(root, forbid_under=[out1]), out=out1)
    L2 = ledger(root, forbid_under=[out2])  # a fresh object, as a new process with another --out would build
    with pytest.raises(LedgerRefusal, match="already ran"):
        L2.begin("fit", "all", {"out": str(out2)}, {})


def test_other_keys_and_steps_are_independent(root):
    L = ledger(root)
    run_step(L, key="lake-a")
    assert run_step(L, key="lake-b") == 1
    assert run_step(L, step="score", key="lake-a") == 1


def test_started_without_close_blocks_a_second_begin(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="never completed or aborted"):
        ledger(root).begin("fit", "all", {}, {})


# ---------- abort path ----------
def test_abort_before_result_allows_attempt_two(root):
    L = ledger(root)
    assert L.begin("fit", "all", {}, {}) == 1
    e = L.abort_before_result("fit", "all", "source download failed")
    assert e["status"] == PRL.ABORTED and e["reason"] == "source download failed"
    assert L.first("fit", "all") is None and not L.counts("fit", "all")
    assert L.begin("fit", "all", {}, {}) == 2
    L.complete("fit", "all", {}, {"metric": 1})
    assert L.counts("fit", "all", 2) and not L.counts("fit", "all", 1)
    with pytest.raises(LedgerRefusal, match="already ran"):
        L.begin("fit", "all", {}, {})


def test_abort_refused_once_an_output_was_recorded(root, tmp_path):
    L = ledger(root)
    res = tmp_path / "results.csv"
    res.write_text("a,b\n1,2\n")
    L.begin("fit", "all", {}, {})
    L.record_outputs("fit", "all", {"results": res})
    with pytest.raises(LedgerRefusal, match="cannot be aborted"):
        L.abort_before_result("fit", "all", "did not like it")
    with pytest.raises(LedgerRefusal, match="never completed"):
        L.begin("fit", "all", {}, {})
    e = L.complete("fit", "all", {}, {"n": 1})
    assert e["outputs"] == {"results": PRL.sha256_file(res)}


def test_abort_after_complete_and_without_begin_refused(root):
    L = ledger(root)
    with pytest.raises(LedgerRefusal, match="no open attempt"):
        L.abort_before_result("fit", "all", "x")
    run_step(L)
    with pytest.raises(LedgerRefusal, match="no open attempt"):
        L.abort_before_result("fit", "all", "x")
    with pytest.raises(LedgerRefusal, match="no open attempt"):
        L.complete("fit", "all", {}, {})


def test_abort_needs_a_reason(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="reason"):
        L.abort_before_result("fit", "all", "  ")


def test_complete_refuses_an_output_that_changed_since_recorded(root, tmp_path):
    L = ledger(root)
    f = tmp_path / "r.json"
    f.write_text("1")
    L.begin("fit", "all", {}, {})
    L.record_outputs("fit", "all", {"r": f})
    f.write_text("2")
    with pytest.raises(LedgerRefusal, match="was recorded as"):
        L.complete("fit", "all", {"r": f}, {})


# ---------- require / bind ----------
def test_require_binds_a_later_step_to_the_first_result(root):
    L = ledger(root)
    with pytest.raises(LedgerRefusal, match="no COMPLETED run"):
        L.require("fit", "all")
    fit_sha = "a" * 64
    L.begin("fit", "all", {}, {})
    L.complete("fit", "all", {"fit": fit_sha}, {})
    assert L.require("fit", "all")["outputs"]["fit"] == fit_sha


# ---------- tampering ----------
def test_editing_an_earlier_entry_is_detected(root):
    L = ledger(root)
    run_step(L, key="a")
    run_step(L, key="b")
    p = root / "_ledgers" / f"{PID}.jsonl"
    ls = p.read_bytes().splitlines()
    e = json.loads(ls[1])
    e["result"] = {"metric": 0.99}
    ls[1] = PRL._canon(e).encode()
    p.write_bytes(b"\n".join(ls) + b"\n")
    with pytest.raises(ChainBroken):
        L.verify_chain()
    with pytest.raises(ChainBroken):
        ledger(root)


def test_editing_the_last_entry_is_detected_by_the_head(root):
    L = ledger(root)
    run_step(L)
    p = root / "_ledgers" / f"{PID}.jsonl"
    ls = p.read_bytes().splitlines()
    e = json.loads(ls[-1])
    e["result"] = {"metric": 0.99}
    ls[-1] = PRL._canon(e).encode()
    p.write_bytes(b"\n".join(ls) + b"\n")
    with pytest.raises(ChainBroken, match="tail"):
        L.verify_chain()


def test_truncating_the_tail_to_allow_a_rerun_is_detected(root):
    L = ledger(root)
    run_step(L)
    p = root / "_ledgers" / f"{PID}.jsonl"
    p.write_bytes(b"\n".join(p.read_bytes().splitlines()[:-1]) + b"\n")  # drop the COMPLETED line
    with pytest.raises(ChainBroken):
        L.begin("fit", "all", {}, {})


def test_deleting_the_ledger_but_not_the_head_is_detected(root):
    run_step(ledger(root))
    (root / "_ledgers" / f"{PID}.jsonl").unlink()
    with pytest.raises(ChainBroken, match="missing or empty"):
        ledger(root)


def test_reformatted_line_and_partial_line_are_detected(root):
    L = ledger(root)
    run_step(L)
    p = root / "_ledgers" / f"{PID}.jsonl"
    good = p.read_bytes()
    first = good.splitlines()[0]
    p.write_bytes(json.dumps(json.loads(first), indent=1).replace("\n", " ").encode() + b"\n" + b"\n".join(good.splitlines()[1:]) + b"\n")
    with pytest.raises(ChainBroken, match="canonical"):
        L.verify_chain()
    p.write_bytes(good[:-5])
    with pytest.raises(ChainBroken, match="incomplete"):
        L.verify_chain()


def test_reordered_entries_detected(root):
    L = ledger(root)
    run_step(L)
    p = root / "_ledgers" / f"{PID}.jsonl"
    ls = p.read_bytes().splitlines()
    p.write_bytes(b"\n".join([ls[1], ls[0]]) + b"\n")
    with pytest.raises(ChainBroken):
        L.verify_chain()


def test_interrupted_head_update_is_repaired_not_refused(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    head = (root / "_ledgers" / f"{PID}.head.json").read_bytes()
    L.complete("fit", "all", {}, {})
    (root / "_ledgers" / f"{PID}.head.json").write_bytes(head)  # the process stopped after the append, before the head write
    assert ledger(root).head()["seq"] == 2
    assert L.verify_chain() == 2


def test_chain_fields_and_entry_contents(root, tmp_path):
    L = ledger(root)
    inp = tmp_path / "in.csv"
    inp.write_text("x\n")
    L.begin("fit", "all", {"alpha": 0.05}, {"data": inp})
    L.complete("fit", "all", {"fit": "b" * 64}, {"n": 3})
    ls = lines(root)
    a, b = json.loads(ls[0]), json.loads(ls[1])
    assert set(a) == set(PRL.FIELDS)
    assert a["seq"] == 1 and a["prev_entry_sha256"] == PRL.GENESIS
    assert b["prev_entry_sha256"] == hashlib.sha256(ls[0]).hexdigest()
    assert a["inputs"] == {"data": PRL.sha256_file(inp)} and a["args"] == {"alpha": 0.05}
    assert a["status"] == "STARTED" and b["status"] == "COMPLETED" and b["run"] == 1
    assert a["host"] and a["utc"].endswith("Z") and a["protocol_sha256"] == PSHA
    assert L.head() == {"protocol_id": PID, "protocol_sha256": PSHA, "seq": 2, "entry_sha256": hashlib.sha256(ls[1]).hexdigest()}


# ---------- protocol binding ----------
def test_protocol_hash_mismatch_refused(root):
    run_step(ledger(root))
    with pytest.raises(LedgerRefusal, match="new protocol id"):
        Ledger(root, PID, OTHER)
    Ledger(root, PID + "-v2", OTHER)  # a changed protocol is a new protocol id


def test_invalid_protocol_id_and_hash_refused(root):
    with pytest.raises(LedgerRefusal, match="protocol_id"):
        Ledger(root, "../escape", PSHA)
    with pytest.raises(LedgerRefusal, match="protocol_sha256"):
        Ledger(root, PID, "ABC")


# ---------- root ----------
def test_root_inside_out_refused(root, tmp_path):
    with pytest.raises(LedgerRefusal, match="inside the --out folder"):
        ledger(root, forbid_under=[root.parent])
    with pytest.raises(LedgerRefusal, match="inside the --out folder"):
        ledger(root, forbid_under=[root])
    ledger(root, forbid_under=[tmp_path / "elsewhere", None])


def test_root_inside_out_via_symlink_refused(root, tmp_path):
    link = tmp_path / "out-link"
    link.symlink_to(root.parent)
    with pytest.raises(LedgerRefusal, match="inside the --out folder"):
        ledger(root, forbid_under=[link])


def test_root_from_env_and_missing_root(root, tmp_path, monkeypatch):
    with pytest.raises(LedgerRefusal, match="no research root"):
        Ledger(None, PID, PSHA)
    with pytest.raises(LedgerRefusal, match="does not exist"):
        Ledger(tmp_path / "nope", PID, PSHA)
    monkeypatch.setenv(PRL.ENV_ROOT, str(root))
    assert Ledger(None, PID, PSHA).path == root.resolve() / "_ledgers" / f"{PID}.jsonl"
    assert Ledger(root, PID, PSHA).root == root.resolve()
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(LedgerRefusal, match="differs from"):
        Ledger(other, PID, PSHA)


# ---------- inputs ----------
def test_input_change_detected(root, tmp_path):
    L = ledger(root)
    f = tmp_path / "gauges.csv"
    f.write_text("lake,level\na,1\n")
    hashes = L.bind_inputs("score", "all", {"gauges": f})
    assert L.check_inputs("score", "all", {"gauges": f}) == hashes
    L.bind_inputs("score", "all", {"gauges": f})  # identical re-bind is a no-op
    assert len(lines(root)) == 1
    f.write_text("lake,level\na,2\n")
    with pytest.raises(LedgerRefusal, match="changed since it was bound"):
        L.check_inputs("score", "all", {"gauges": f})
    with pytest.raises(LedgerRefusal, match="was bound as"):
        L.bind_inputs("score", "all", {"gauges": f})
    with pytest.raises(LedgerRefusal, match="differs from the bound input"):
        L.begin("score", "all", {}, {"gauges": f})


def test_inputs_cannot_be_bound_after_a_result_and_unknown_names_refused(root, tmp_path):
    L = ledger(root)
    f = tmp_path / "a.csv"
    f.write_text("1")
    with pytest.raises(LedgerRefusal, match="no inputs were bound"):
        L.check_inputs("score", "all", {"a": f})
    L.bind_inputs("score", "all", {"a": f})
    with pytest.raises(LedgerRefusal, match="never bound"):
        L.check_inputs("score", "all", {"b": f})
    L.begin("score", "all", {}, {"a": f})
    L.complete("score", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="before results"):
        L.bind_inputs("score", "all", {"b": f})


def test_tree_inputs_and_missing_files(root, tmp_path):
    d = tmp_path / "corpus"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "x.txt").write_text("x")
    (d / ".DS_Store").write_text("junk")
    L = ledger(root)
    h = L.bind_inputs("select", "all", {"corpus": d})["corpus"]
    assert h == hashlib.sha256(f"{hashlib.sha256(b'x').hexdigest()}  sub/x.txt\n".encode()).hexdigest()
    (d / "sub" / "y.txt").write_text("y")
    with pytest.raises(LedgerRefusal, match="changed"):
        L.check_inputs("select", "all", {"corpus": d})
    with pytest.raises(LedgerRefusal, match="no such file"):
        L.bind_inputs("select", "other", {"x": tmp_path / "missing"})
    with pytest.raises(LedgerRefusal, match="sha256 hex"):
        L.begin("select", "other", {}, {"x": "not-a-hash"})


def test_result_must_be_small_json(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="larger than"):
        L.complete("fit", "all", {}, {"blob": "x" * (PRL.RESULT_MAX_BYTES + 1)})
    with pytest.raises(LedgerRefusal, match="JSON"):
        L.complete("fit", "all", {}, {"bad": float("nan")})
    L.complete("fit", "all", {}, {"ok": True})


# ---------- concurrency ----------
def _race(root, barrier, q):
    L = Ledger(Path(root), PID, PSHA)
    barrier.wait()
    try:
        q.put(("ok", L.begin("fit", "all", {"pid": os.getpid()}, {})))
    except LedgerRefusal as e:
        q.put(("refused", str(e)))


def test_concurrent_begin_only_one_wins(root):
    ctx = mp.get_context("fork")
    n = 8
    barrier, q = ctx.Barrier(n), ctx.Queue()
    procs = [ctx.Process(target=_race, args=(str(root), barrier, q)) for _ in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    results = [q.get(timeout=5) for _ in range(n)]
    assert [r for r in results if r[0] == "ok"] == [("ok", 1)]
    assert sum(r[0] == "refused" for r in results) == n - 1
    assert ledger(root).verify_chain() == 1


def test_sha256_helpers(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"abc")
    assert PRL.sha256_file(f) == hashlib.sha256(b"abc").hexdigest()
    with pytest.raises(LedgerRefusal):
        PRL.sha256_tree(f)
