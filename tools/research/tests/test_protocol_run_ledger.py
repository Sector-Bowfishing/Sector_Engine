"""Protocol run ledger: a pre-registered step runs once, pinned by public comments on Sector_Ops #51 (mocked here; no network).

Covers: re-runs refused (new --out, new process, new folder, deleted ledger), rollback to a snapshot detected as REPEAT, edited comments
refused, copied root refused, the abort path and terminal dangling starts, non-result attempts, chain and tail tampering, protocol hash
mismatch, concurrent begin under the lock, root under --out, input changes, for_brain with a fake Cortex, and audit()."""
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import protocol_run_ledger as PRL  # noqa: E402
from protocol_run_ledger import ChainBroken, Ledger, LedgerRefusal, RepeatDetected  # noqa: E402

PID = "wind-strong-wind-v1"
PSHA = hashlib.sha256(b"protocol v1").hexdigest()
OTHER = hashlib.sha256(b"protocol v2").hexdigest()
REAL_GH = PRL._gh_api
RS = frozenset({"fit", "score", "select"})  # the runner's declared result steps
ISSUE_PATH = "repos/Sector-Bowfishing/Sector_Ops/issues/51/comments?per_page=100"


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv(PRL.ENV_ROOT, raising=False)

    def no_network(path):
        raise AssertionError(f"a test reached the real gh: {path}")
    monkeypatch.setattr(PRL, "_gh_api", no_network)


class Issue:
    """A fake Sector_Ops #51 behind `gh api --paginate`: comments in pages of 3, printed as concatenated arrays like gh does."""

    def __init__(self):
        self.comments, self.fail, self.calls, self.next_id = [], None, 0, 1000
        self.clock = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)

    def post(self, body, created=None, updated=None, user="runner-bot"):
        if created is None:
            self.clock += dt.timedelta(minutes=1)
            created = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        cid, self.next_id = self.next_id, self.next_id + 1
        c = {"id": cid, "created_at": created, "updated_at": updated or created, "body": body, "user": {"login": user},
             "html_url": f"https://example.invalid/issues/51#issuecomment-{cid}"}
        self.comments.append(c)
        return c

    def __call__(self, path):
        assert path == ISSUE_PATH, path
        self.calls += 1
        if self.fail:
            raise LedgerRefusal(self.fail)
        pages = [self.comments[i:i + 3] for i in range(0, len(self.comments), 3)] or [[]]
        return "".join(json.dumps(p) for p in pages)


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "Sector Research" / "wind-brain"
    r.mkdir(parents=True)
    return r


def ledger(root, issue=None, anchored=True, **kw):
    issue = issue if issue is not None else Issue()
    kw.setdefault("result_steps", RS)
    L = Ledger(root, PID, PSHA, gh=issue, **kw)
    L.issue = issue
    if anchored and not any(c["body"].startswith(f"Run anchor: {PID} {L.anchor()}") for c in issue.comments):
        issue.post(L.post_anchor_text())
    return L


def go(L, step="fit", key="all", args=None, inputs=None):
    """begin + post start_text on #51 + confirm_started: what a well-behaved runner does before computing."""
    run = L.begin(step, key, args or {}, inputs or {})
    L.issue.post(L.start_text(step, key))
    L.confirm_started(step, key)
    return run


def run_step(L, step="fit", key="all", result=None, post_result=True):
    run = go(L, step, key)
    L.complete(step, key, {}, result or {"metric": 0.5})
    if post_result:
        L.issue.post(L.result_text(step, key))
        L.confirm_result(step, key)
    return run


def lines(root):
    return (root / "_ledgers" / f"{PID}.jsonl").read_bytes().splitlines()


def last(root):
    return json.loads(lines(root)[-1])


# ---------- the core rule ----------
def test_first_run_counts_and_rerun_is_refused(root):
    L = ledger(root)
    assert run_step(L) == 1
    assert L.counts("fit", "all") and L.counts("fit", "all", 1)
    with pytest.raises(LedgerRefusal, match="already ran"):
        L.begin("fit", "all", {}, {})
    e = L.require("fit", "all")
    assert e["result"] == {"metric": 0.5} and e["counted"] is True
    assert e["external"]["anchor"]["id"] == 1000 and e["external"]["start"]["id"] == 1001 and e["external"]["startCommentsAtComplete"] == 1


def test_new_out_folder_and_new_process_still_refused(root, tmp_path):
    L1 = ledger(root, forbid_under=[tmp_path / "out1"])
    run_step(L1)
    L2 = ledger(root, issue=L1.issue, forbid_under=[tmp_path / "out2"])
    with pytest.raises(LedgerRefusal, match="already ran"):
        L2.begin("fit", "all", {"out": str(tmp_path / "out2")}, {})


def test_other_keys_and_steps_are_independent(root):
    L = ledger(root)
    run_step(L, key="lake-a")
    assert run_step(L, key="lake-b") == 1
    assert run_step(L, step="score", key="lake-a") == 1


def test_step_and_key_without_whitespace(root):
    with pytest.raises(LedgerRefusal, match="whitespace"):
        ledger(root).begin("fit", "Lake Guntersville", {}, {})


# ---------- the anchor ----------
def test_post_anchor_text_shape_and_genesis(root):
    L = ledger(root, anchored=False)
    text = L.post_anchor_text()
    assert text.splitlines()[0] == f"Run anchor: {PID} {L.anchor()} fit,score,select"
    assert "owner approval" not in text.lower() and PSHA in text and str(root.resolve()) in text
    g = json.loads(lines(root)[0])["result"]
    assert len(g["nonce"]) == 32 and g["protocol_id"] == PID and g["protocol_sha256"] == PSHA and g["root"] and g["host"]


def test_nonce_makes_every_genesis_unique(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    assert ledger(a).anchor() != ledger(b).anchor()


def test_earliest_anchor_match_over_pages(root):
    issue = Issue()
    issue.post("unrelated")
    issue.post(f"Run anchor: other-protocol {'c' * 64}")
    issue.post("also unrelated")
    L = ledger(root, issue=issue)  # the anchor lands on page 2
    m = L.require_external_anchor()
    assert m["comment_id"] == 1003 and m["anchor"] == L.anchor()
    assert go(L) == 1 and last(root)["status"] == "START_CONFIRMED"


def test_later_duplicate_anchor_refused(root):
    issue = Issue()
    issue.post(f"Run anchor: {PID} {'d' * 64}")  # an earlier ledger's anchor
    L = ledger(root, issue=issue)  # this ledger posts later: it never counts
    with pytest.raises(LedgerRefusal, match="earliest anchor"):
        L.begin("fit", "all", {}, {})
    assert len(lines(root)) == 1


def test_anchor_posted_after_start_refused(root):
    issue = Issue()
    L = ledger(root, issue=issue, anchored=False)
    issue.post(L.post_anchor_text(), created="2099-01-01T00:00:00Z")
    with pytest.raises(LedgerRefusal, match="not before the ledger's first start"):
        L.begin("fit", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="not before the ledger's first start"):
        L.begin("fetch", "all", {}, {})


def test_no_step_of_any_kind_before_the_anchor(root):
    L = ledger(root, anchored=False)
    with pytest.raises(LedgerRefusal, match="no `Run anchor:"):
        L.begin("fetch", "all", {}, {})  # not a declared result step, still refused
    with pytest.raises(LedgerRefusal, match="no `Run anchor:"):
        L.begin("fit", "all", {}, {})
    L.issue.post(L.post_anchor_text())
    assert L.begin("fetch", "all", {}, {}) == 1
    e = L.complete("fetch", "all", {"raw": "e" * 64}, None)
    assert e["counted"] is True and not L.counts("fetch", "all") and L.first("fetch", "all") is None  # only result steps count


def test_gh_failure_refused(root):
    L = ledger(root)
    L.issue.fail = "gh: HTTP 502"
    with pytest.raises(LedgerRefusal, match="502"):
        L.begin("fit", "all", {}, {})
    L2 = Ledger(root, PID, PSHA, result_steps=RS, gh=lambda path: "<html>not json</html>")
    with pytest.raises(LedgerRefusal, match="not JSON"):
        L2.begin("fit", "all", {}, {})
    assert len(lines(root)) == 1


def test_gh_failure_at_complete_refuses_then_retry_by_same_object(root):
    L = ledger(root)
    go(L)
    L.issue.fail = "gh: timeout"
    with pytest.raises(LedgerRefusal, match="timeout"):
        L.complete("fit", "all", {}, {"m": 1})
    L.issue.fail = None
    assert L.complete("fit", "all", {}, {"m": 1})["counted"] is True


def test_real_gh_missing_or_failing_refused(monkeypatch):
    def missing(*a, **k):
        raise FileNotFoundError("gh")
    monkeypatch.setattr(PRL.subprocess, "run", missing)
    with pytest.raises(LedgerRefusal, match="gh api unavailable"):
        REAL_GH("repos/x/y/issues/1/comments")

    class Done:
        returncode, stdout, stderr = 1, "", "HTTP 401"
    monkeypatch.setattr(PRL.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(LedgerRefusal, match="401"):
        REAL_GH("repos/x/y/issues/1/comments")


def test_new_folder_refused(tmp_path):
    first, second = tmp_path / "r1" / "wind-brain", tmp_path / "r2" / "wind-brain"
    first.mkdir(parents=True), second.mkdir(parents=True)
    L1 = ledger(first)
    run_step(L1)
    L2 = ledger(second, issue=L1.issue)  # a fresh folder gives a fresh ledger, and it even posts its own (later) anchor
    with pytest.raises(LedgerRefusal, match="earliest anchor"):
        L2.begin("fit", "all", {}, {})


def test_deleted_ledger_refused(root):
    L = ledger(root)
    run_step(L)
    shutil.rmtree(root / "_ledgers")
    L2 = ledger(root, issue=L.issue)
    with pytest.raises(LedgerRefusal, match="earliest anchor"):
        L2.begin("fit", "all", {}, {})


# ---------- Run start: rollback, repeats, edits ----------
def test_start_text_shape(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    first = L.start_text("fit", "all").splitlines()[0]
    assert first == f"Run start: {PID} fit all {hashlib.sha256(lines(root)[-1]).hexdigest()}"
    assert "owner approval" not in L.start_text("fit", "all").lower()


def test_complete_needs_a_confirmed_start(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="no confirmed"):
        L.complete("fit", "all", {}, {"m": 1})
    with pytest.raises(LedgerRefusal, match="no `Run start:"):
        L.confirm_started("fit", "all")
    with pytest.raises(LedgerRefusal, match="no confirmed"):
        L.record_outputs("fit", "all", {"r": "a" * 64})


def test_rollback_to_snapshot_then_second_run_start_is_repeat(root, tmp_path):
    L = ledger(root)
    snap = tmp_path / "snapshot"
    shutil.copytree(root / "_ledgers", snap)  # snapshot after the anchor, before the run
    run_step(L, result={"metric": 0.41})
    shutil.rmtree(root / "_ledgers")
    shutil.copytree(snap, root / "_ledgers")  # roll back: locally the step never ran
    R = ledger(root, issue=L.issue)  # same root, same anchor: the anchor check passes
    assert R.begin("fit", "all", {}, {}) == 1
    L.issue.post(R.start_text("fit", "all"))  # the second Run start for (protocol, fit, all)
    with pytest.raises(RepeatDetected, match="REPEAT"):
        R.confirm_started("fit", "all")
    assert last(root)["status"] == "REPEAT_DETECTED"
    with pytest.raises(LedgerRefusal, match="no confirmed"):
        R.complete("fit", "all", {}, {"metric": 0.55})
    assert not R.counts("fit", "all")


def test_rollback_without_posting_cannot_complete(root, tmp_path):
    L = ledger(root)
    snap = tmp_path / "snapshot"
    shutil.copytree(root / "_ledgers", snap)
    run_step(L)
    shutil.rmtree(root / "_ledgers")
    shutil.copytree(snap, root / "_ledgers")
    R = ledger(root, issue=L.issue)
    R.begin("fit", "all", {}, {})
    with pytest.raises(RepeatDetected):  # the original's Run start is the earliest and carries another hash
        R.confirm_started("fit", "all")


def test_second_run_start_appearing_before_complete_marks_result_not_counting(root, tmp_path):
    L = ledger(root)
    go(L)
    L.issue.post(f"Run start: {PID} fit all {'f' * 64}")  # e.g. a restored copy started the same step meanwhile
    e = L.complete("fit", "all", {}, {"metric": 0.5})
    assert e["counted"] is False and "REPEAT" in e["reason"] and e["external"]["startCommentsAtComplete"] == 2
    assert not L.counts("fit", "all")
    with pytest.raises(LedgerRefusal, match="REPEAT"):
        L.require("fit", "all")
    with pytest.raises(LedgerRefusal, match="already ran"):
        L.begin("fit", "all", {}, {})


def test_edited_anchor_comment_refused(root):
    L = ledger(root, anchored=False)
    L.issue.post(L.post_anchor_text(), created="2000-01-01T00:00:00Z", updated="2000-01-02T00:00:00Z")
    with pytest.raises(LedgerRefusal, match="edited"):
        L.begin("fit", "all", {}, {})


def test_edited_run_start_comment_refused(root):
    L = ledger(root)
    L.begin("fit", "all", {}, {})
    c = L.issue.post(L.start_text("fit", "all"))
    c["updated_at"] = "2001-01-01T00:00:00Z"
    with pytest.raises(LedgerRefusal, match="edited"):
        L.confirm_started("fit", "all")


def test_edited_comment_that_mentions_the_protocol_refused(root):
    L = ledger(root)
    L.issue.post(f"note about {PID}", created="2000-02-01T00:00:00Z", updated="2000-02-02T00:00:00Z")  # e.g. an anchor edited away
    with pytest.raises(LedgerRefusal, match="edited"):
        L.begin("fit", "all", {}, {})


def test_audit_reports_comment_ids_and_detects_deletion(root):
    L = ledger(root)
    run_step(L)
    a = L.audit()
    assert a["anchor"] == L.anchor() and a["steps"][0]["external"]["start"]["id"] == 1001 and "findings" not in a
    assert a["result_steps"] == sorted(RS)
    assert L.audit(check_external=True)["findings"] == []
    L.issue.comments = [c for c in L.issue.comments if c["id"] != 1001]  # someone deletes the Run start comment
    f = L.audit(check_external=True)["findings"]
    assert any("MISSING_COMMENT" in x and "1001" in x for x in f) and any("START_COUNT" in x for x in f)
    L.issue.fail = "gh down"
    assert L.audit(check_external=True)["findings"][0].startswith("EXTERNAL_UNCHECKED")


# ---------- abort and terminal starts ----------
def test_abort_before_result_allows_attempt_two(root):
    L = ledger(root)
    assert L.begin("fit", "all", {}, {}) == 1
    e = L.abort_before_result("fit", "all", "source download failed")  # before any Run start was posted
    assert e["status"] == PRL.ABORTED and e["reason"] == "source download failed"
    assert L.first("fit", "all") is None and not L.counts("fit", "all")
    assert go(L) == 2
    L.complete("fit", "all", {}, {"metric": 1})
    assert L.counts("fit", "all", 2) and not L.counts("fit", "all", 1)


def test_retry_after_a_posted_start_is_a_repeat(root):
    L = ledger(root)
    go(L)
    L.abort_before_result("fit", "all", "network down")
    assert L.begin("fit", "all", {}, {}) == 2
    L.issue.post(L.start_text("fit", "all"))
    with pytest.raises(RepeatDetected):
        L.confirm_started("fit", "all")


def test_abort_refused_once_an_output_was_recorded(root, tmp_path):
    L = ledger(root)
    res = tmp_path / "results.csv"
    res.write_text("a,b\n1,2\n")
    go(L)
    L.record_outputs("fit", "all", {"results": res})
    with pytest.raises(LedgerRefusal, match="cannot be aborted"):
        L.abort_before_result("fit", "all", "did not like it")
    with pytest.raises(LedgerRefusal, match="terminal"):
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


def test_dangling_start_is_terminal_even_for_abort(root):
    ledger(root).begin("fit", "all", {}, {})  # the process is killed here: no end
    L = ledger(root)
    with pytest.raises(LedgerRefusal, match="terminal"):
        L.abort_before_result("fit", "all", "rebooted")
    with pytest.raises(LedgerRefusal, match="terminal"):
        L.complete("fit", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="new protocol id"):
        L.begin("fit", "all", {}, {})


def test_complete_refuses_an_output_that_changed_since_recorded(root, tmp_path):
    L = ledger(root)
    f = tmp_path / "r.json"
    f.write_text("1")
    go(L)
    L.record_outputs("fit", "all", {"r": f})
    f.write_text("2")
    with pytest.raises(LedgerRefusal, match="was recorded as"):
        L.complete("fit", "all", {"r": f}, {})


# ---------- non-result attempts ----------
def test_non_result_complete_with_result_refused(root):
    L = ledger(root)
    L.begin("fetch", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="not result-producing"):
        L.complete("fetch", "all", {}, {"metric": 0.3})
    with pytest.raises(LedgerRefusal, match="not result-producing"):
        L.record_outputs("fetch", "all", {"raw": "a" * 64})
    e = L.complete("fetch", "all", {"raw": "a" * 64})
    assert e["counted"] is True and e["result"] == {} and e["external"] is None


# ---------- require / bind ----------
def test_require_binds_a_later_step_to_the_first_result(root):
    L = ledger(root)
    with pytest.raises(LedgerRefusal, match="no COMPLETED run"):
        L.require("fit", "all")
    go(L)
    L.complete("fit", "all", {"fit": "a" * 64}, {})
    assert L.require("fit", "all")["outputs"]["fit"] == "a" * 64


# ---------- local tampering ----------
def rewrite(root, idx, **changes):
    p = root / "_ledgers" / f"{PID}.jsonl"
    ls = p.read_bytes().splitlines()
    e = json.loads(ls[idx])
    e.update(changes)
    ls[idx] = PRL._canon(e).encode()
    p.write_bytes(b"\n".join(ls) + b"\n")


def test_editing_an_earlier_entry_is_detected(root):
    L = ledger(root)
    run_step(L, key="a")
    run_step(L, key="b")
    rewrite(root, 3, result={"metric": 0.99})
    with pytest.raises(ChainBroken):
        L.verify_chain()
    with pytest.raises(ChainBroken):
        ledger(root, issue=L.issue)


def test_editing_the_last_entry_is_detected_by_the_head(root):
    L = ledger(root)
    run_step(L)
    rewrite(root, -1, result={"metric": 0.99})
    with pytest.raises(ChainBroken, match="tail"):
        L.verify_chain()


def test_truncating_the_tail_is_detected(root):
    L = ledger(root)
    run_step(L)
    p = root / "_ledgers" / f"{PID}.jsonl"
    p.write_bytes(b"\n".join(p.read_bytes().splitlines()[:-1]) + b"\n")
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
    ls = good.splitlines()
    p.write_bytes(json.dumps(json.loads(ls[0]), indent=1).replace("\n", " ").encode() + b"\n" + b"\n".join(ls[1:]) + b"\n")
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
    p.write_bytes(b"\n".join([ls[0], ls[2], ls[1]] + ls[3:]) + b"\n")
    with pytest.raises(ChainBroken):
        L.verify_chain()


def test_ledger_opened_only_first(root):
    L = ledger(root)
    first = json.loads(lines(root)[0])
    run_step(L)
    p = root / "_ledgers" / f"{PID}.jsonl"
    ls = p.read_bytes().splitlines()
    fake = dict(first, seq=len(ls) + 1, prev_entry_sha256=hashlib.sha256(ls[-1]).hexdigest())
    line = PRL._canon(fake).encode()
    p.write_bytes(p.read_bytes() + line + b"\n")
    (root / "_ledgers" / f"{PID}.head.json").write_text(
        PRL._canon({"protocol_id": PID, "seq": len(ls) + 1, "entry_sha256": hashlib.sha256(line).hexdigest()}))
    with pytest.raises(ChainBroken, match="LEDGER_OPENED"):
        L.verify_chain()


def test_interrupted_head_update_is_repaired_not_refused(root):
    L = ledger(root)
    go(L)
    head = (root / "_ledgers" / f"{PID}.head.json").read_bytes()
    L.complete("fit", "all", {}, {})
    (root / "_ledgers" / f"{PID}.head.json").write_bytes(head)  # stopped after the append, before the head write
    n = len(lines(root))
    assert ledger(root, issue=L.issue).head()["seq"] == n
    assert L.verify_chain() == n


def test_short_os_write_is_completed(root, monkeypatch):
    real = os.write
    monkeypatch.setattr(PRL.os, "write", lambda fd, data: real(fd, bytes(data[:7])))
    L = ledger(root)
    run_step(L)
    monkeypatch.undo()
    assert L.verify_chain() == len(lines(root))


def test_chain_fields_and_entry_contents(root, tmp_path):
    L = ledger(root)
    inp = tmp_path / "in.csv"
    inp.write_text("x\n")
    go(L, args={"alpha": 0.05}, inputs={"data": inp})
    L.complete("fit", "all", {"fit": "b" * 64}, {"n": 3})
    ls = lines(root)
    es = [json.loads(x) for x in ls]
    assert [e["status"] for e in es] == ["LEDGER_OPENED", "STARTED", "START_CONFIRMED", "COMPLETED"]
    assert all(set(e) == set(PRL.FIELDS) for e in es)
    assert es[0]["seq"] == 1 and es[0]["prev_entry_sha256"] == PRL.GENESIS
    assert all(es[i]["prev_entry_sha256"] == hashlib.sha256(ls[i - 1]).hexdigest() for i in range(1, len(es)))
    assert es[0]["result"]["root"] == str(root.resolve()) and es[0]["result"]["resolvedBy"] == "explicit-root"
    assert es[1]["inputs"] == {"data": PRL.sha256_file(inp)} and es[1]["args"] == {"alpha": 0.05} and es[1]["result_producing"] is True
    assert es[3]["run"] == 1 and es[3]["counted"] is True and es[1]["host"] and es[1]["utc"].endswith("Z")
    assert L.head() == {"protocol_id": PID, "protocol_sha256": PSHA, "seq": 4, "entry_sha256": hashlib.sha256(ls[3]).hexdigest()}


# ---------- protocol binding ----------
def test_protocol_hash_mismatch_refused(root):
    run_step(ledger(root))
    with pytest.raises(LedgerRefusal, match="new protocol id"):
        Ledger(root, PID, OTHER, result_steps=RS, gh=Issue())
    Ledger(root, PID + "-v2", OTHER, result_steps=RS, gh=Issue())


def test_invalid_protocol_id_and_hash_refused(root):
    with pytest.raises(LedgerRefusal, match="protocol_id"):
        Ledger(root, "../escape", PSHA, result_steps=RS)
    with pytest.raises(LedgerRefusal, match="protocol_sha256"):
        Ledger(root, PID, "ABC", result_steps=RS)


# ---------- root ----------
def test_copied_root_refused(root, tmp_path):
    L = ledger(root)
    run_step(L)
    copy = tmp_path / "copy" / "wind-brain"
    copy.mkdir(parents=True)
    shutil.copytree(root / "_ledgers", copy / "_ledgers")
    with pytest.raises(ChainBroken, match="copied or moved"):
        ledger(copy, issue=L.issue)


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
        Ledger(None, PID, PSHA, result_steps=RS)
    with pytest.raises(LedgerRefusal, match="does not exist"):
        Ledger(tmp_path / "nope", PID, PSHA, result_steps=RS)
    monkeypatch.setenv(PRL.ENV_ROOT, str(root))
    assert Ledger(None, PID, PSHA, result_steps=RS, gh=Issue()).path == root.resolve() / "_ledgers" / f"{PID}.jsonl"
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(LedgerRefusal, match="differs from"):
        Ledger(other, PID, PSHA, result_steps=RS)


# ---------- for_brain ----------
def fake_cortex(tmp_path, printed, rc=0):
    home = tmp_path / "cortex"
    (home / "tools").mkdir(parents=True, exist_ok=True)
    (home / "tools" / "cortex.py").write_text(
        "import sys\n"
        "assert sys.argv[1:3] == ['research-path', 'sector/engine'], sys.argv\n"
        f"print({str(printed)!r} if sys.argv[3] == 'wind' else '/nowhere')\n"
        "print('# brain=wind folder=wind-brain exists=True manifest=True')\n"
        f"sys.exit({rc})\n")
    return home


def test_for_brain_resolves_root_with_research_path_and_records_it(root, tmp_path):
    issue = Issue()
    L = Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, cortex_home=fake_cortex(tmp_path, root), gh=issue, result_steps=RS)
    assert L.root == root.resolve()
    g = json.loads(lines(root)[0])["result"]
    assert g["resolvedBy"] == "cortex-research-path" and g["brain"] == "wind" and g["root"] == str(root.resolve()) and g["host"]
    assert L.anchor() == hashlib.sha256(lines(root)[0]).hexdigest()


def test_for_brain_refuses_env_root_that_differs_and_accepts_equal(root, tmp_path, monkeypatch):
    home = fake_cortex(tmp_path, root)
    other = tmp_path / "chosen"
    other.mkdir()
    monkeypatch.setenv(PRL.ENV_ROOT, str(other))
    with pytest.raises(LedgerRefusal, match="not the research-path folder"):
        Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, cortex_home=home, result_steps=RS)
    assert not (other / "_ledgers").exists()
    monkeypatch.setenv(PRL.ENV_ROOT, str(root))
    assert Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, cortex_home=home, gh=Issue(), result_steps=RS).root == root.resolve()


def test_for_brain_refuses_without_cortex_or_on_failure(root, tmp_path, monkeypatch):
    monkeypatch.delenv(PRL.ENV_CORTEX, raising=False)
    with pytest.raises(LedgerRefusal, match="Cortex location unknown"):
        Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, result_steps=RS)
    with pytest.raises(LedgerRefusal, match="failed"):
        Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, cortex_home=fake_cortex(tmp_path, root, rc=2), result_steps=RS)
    home2 = tmp_path / "c2"
    home2.mkdir()
    with pytest.raises(LedgerRefusal, match="no Cortex tool"):
        Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, cortex_home=home2, result_steps=RS)
    with pytest.raises(LedgerRefusal, match="invalid brain"):
        Ledger.for_brain("../x", PID, PSHA, repo=tmp_path, cortex_home=home2, result_steps=RS)


def test_for_brain_refuses_a_research_path_that_does_not_exist(tmp_path):
    with pytest.raises(LedgerRefusal, match="does not exist"):
        Ledger.for_brain("wind", PID, PSHA, repo=tmp_path, cortex_home=fake_cortex(tmp_path, tmp_path / "absent"), result_steps=RS)


# ---------- inputs ----------
def test_input_change_detected(root, tmp_path):
    L = ledger(root)
    f = tmp_path / "gauges.csv"
    f.write_text("lake,level\na,1\n")
    hashes = L.bind_inputs("score", "all", {"gauges": f})
    assert L.check_inputs("score", "all", {"gauges": f}) == hashes
    n = len(lines(root))
    L.bind_inputs("score", "all", {"gauges": f})
    assert len(lines(root)) == n
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
    go(L, "score", "all", inputs={"a": f})
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
    go(L)
    with pytest.raises(LedgerRefusal, match="larger than"):
        L.complete("fit", "all", {}, {"blob": "x" * (PRL.RESULT_MAX_BYTES + 1)})
    with pytest.raises(LedgerRefusal, match="JSON"):
        L.complete("fit", "all", {}, {"bad": float("nan")})
    L.complete("fit", "all", {}, {"ok": True})


# ---------- concurrency ----------
def _race(root, issue, barrier, q):
    L = Ledger(Path(root), PID, PSHA, result_steps=RS, gh=issue)
    barrier.wait()
    try:
        q.put(("ok", L.begin("fit", "all", {"pid": os.getpid()}, {})))
    except LedgerRefusal as e:
        q.put(("refused", str(e)))


def test_concurrent_begin_only_one_wins(root):
    L = ledger(root)
    ctx = mp.get_context("fork")
    n = 8
    barrier, q = ctx.Barrier(n), ctx.Queue()
    procs = [ctx.Process(target=_race, args=(str(root), L.issue, barrier, q)) for _ in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    results = [q.get(timeout=5) for _ in range(n)]
    assert [r for r in results if r[0] == "ok"] == [("ok", 1)]
    assert sum(r[0] == "refused" for r in results) == n - 1
    assert L.verify_chain() == 2  # LEDGER_OPENED + one STARTED


def test_sha256_helpers(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"abc")
    assert PRL.sha256_file(f) == hashlib.sha256(b"abc").hexdigest()
    with pytest.raises(LedgerRefusal):
        PRL.sha256_tree(f)


# ---------- round 2: declared result steps, sha binding, Run result, edit screening ----------
def test_result_steps_recorded_and_fixed(root):
    L = ledger(root)
    assert json.loads(lines(root)[0])["result"]["resultSteps"] == sorted(RS)
    with pytest.raises(LedgerRefusal, match="result steps are fixed"):
        ledger(root, issue=L.issue, result_steps=frozenset({"score", "select"}))  # e.g. to make "fit" a non-result step
    with pytest.raises(LedgerRefusal, match="frozenset"):
        Ledger(root, PID, PSHA, result_steps="fit")
    with pytest.raises(TypeError):
        Ledger(root, PID, PSHA)  # result_steps is required
    with pytest.raises(TypeError):
        L.begin("fit", "all", {}, {}, result_producing=False)  # no per-call flag


def test_poc_rollback_that_posts_nothing_is_refused(root, tmp_path):
    """Round-1 PoC: restore a snapshot, then run the result step as a non-result step to skip #51. Now the step's kind is declared."""
    L = ledger(root)
    snap = tmp_path / "snapshot"
    shutil.copytree(root / "_ledgers", snap)
    run_step(L)
    shutil.rmtree(root / "_ledgers")
    shutil.copytree(snap, root / "_ledgers")
    with pytest.raises(LedgerRefusal, match="result steps are fixed"):
        ledger(root, issue=L.issue, result_steps=frozenset())
    R = ledger(root, issue=L.issue)
    R.begin("fit", "all", {}, {})  # it is a result step whatever the caller wants
    with pytest.raises(LedgerRefusal, match="no confirmed"):
        R.complete("fit", "all", {}, {"metric": 0.9})
    with pytest.raises(RepeatDetected):
        R.confirm_started("fit", "all")


def test_poc_abort_then_nonresult_is_refused(root):
    L = ledger(root)
    go(L)
    L.abort_before_result("fit", "all", "pretend nothing was seen")
    L.begin("fit", "all", {}, {})  # the retry is still a result step ...
    with pytest.raises(LedgerRefusal, match="no confirmed"):
        L.complete("fit", "all", {}, {})  # ... and cannot complete without a (second, hence REPEAT) Run start
    M = ledger(root, issue=L.issue)
    L.issue.post(f"Run start: {PID} fetch all {'a' * 64}")
    with pytest.raises(LedgerRefusal, match="not a result step"):
        M.begin("fetch", "all", {}, {})


def test_single_run_start_with_another_sha_does_not_count(root):
    L = ledger(root)
    go(L)
    mine = [c for c in L.issue.comments if c["body"].startswith("Run start:")][0]
    L.issue.comments.remove(mine)  # the same identity deletes its start comment ...
    L.issue.post(f"Run start: {PID} fit all {'9' * 64}")  # ... and one with another hash is the only one left
    e = L.complete("fit", "all", {}, {"metric": 0.5})
    assert e["counted"] is False and e["external"]["startCommentsAtComplete"] == 1
    L.issue.post(L.result_text("fit", "all"))
    f = L.audit(check_external=True)["findings"]
    assert any(x.startswith("START_MISMATCH") for x in f) and any(x.startswith("MISSING_COMMENT") for x in f)


def test_run_result_audit_detects_a_forged_tail(root):
    L = ledger(root)
    run_step(L, post_result=False)
    assert any(x.startswith("RESULT_MISSING") for x in L.audit(check_external=True)["findings"])
    text = L.result_text("fit", "all")
    assert text.splitlines()[0].startswith(f"Run result: {PID} fit all ") and "owner approval" not in text.lower()
    L.issue.post(text)
    assert L.audit(check_external=True)["findings"] == []
    # a forger with filesystem access rewrites the COMPLETED line and recomputes the head: the chain still verifies ...
    p = root / "_ledgers" / f"{PID}.jsonl"
    ls = p.read_bytes().splitlines()
    e = json.loads(ls[-1])
    e["result"] = {"metric": 0.99}
    ls[-1] = PRL._canon(e).encode()
    p.write_bytes(b"\n".join(ls) + b"\n")
    (root / "_ledgers" / f"{PID}.head.json").write_text(
        PRL._canon({"protocol_id": PID, "seq": len(ls), "entry_sha256": hashlib.sha256(ls[-1]).hexdigest()}))
    assert L.verify_chain() == len(ls)
    # ... but the posted Run result no longer matches
    assert any(x.startswith("RESULT_MISMATCH") for x in L.audit(check_external=True)["findings"])
    L.issue.post(L.result_text("fit", "all"))
    assert any(x.startswith("RESULT_COUNT") for x in L.audit(check_external=True)["findings"])


def test_result_text_only_for_completed_result_steps(root):
    L = ledger(root)
    with pytest.raises(LedgerRefusal, match="no COMPLETED"):
        L.result_text("fit", "all")
    L.begin("fetch", "all", {}, {})
    L.complete("fetch", "all", {"raw": "e" * 64})
    with pytest.raises(LedgerRefusal, match="no COMPLETED"):
        L.result_text("fetch", "all")


def test_edited_check_uses_exact_tokens(root):
    L = ledger(root)
    L.issue.post(f"see {PID}0 and x{PID}", created="2000-03-01T00:00:00Z", updated="2000-03-02T00:00:00Z", user="someone-else")
    assert go(L) == 1  # a superstring is not the protocol id
    (root.parent / "b").mkdir()
    L2 = ledger(root.parent / "b")
    L2.issue.post(f"pinned: `{PID}`,", created="2000-03-01T00:00:00Z", updated="2000-03-02T00:00:00Z", user="someone-else")
    with pytest.raises(LedgerRefusal, match="names"):
        L2.begin("fit", "all", {}, {})


def test_edited_away_recorded_comment_refused_and_audited(root):
    L = ledger(root)
    go(L)
    start = [c for c in L.issue.comments if c["body"].startswith("Run start:")][0]
    start["body"], start["updated_at"] = "never mind", "2001-01-01T00:00:00Z"  # edited away: no longer a Run comment
    with pytest.raises(LedgerRefusal, match="recorded in this ledger"):
        L.complete("fit", "all", {}, {"metric": 0.5})
    f = L.audit(check_external=True)["findings"]
    assert any(x.startswith("EDITED:") for x in f) and any(x.startswith("EDITED_AWAY") for x in f)


def test_edit_blast_radius_is_one_protocol(root):
    L = ledger(root)
    L.issue.post("Run anchor: some-other-protocol " + "1" * 64 + " -", updated="2030-01-01T00:00:00Z")  # same author, other protocol
    assert go(L) == 1  # an edit elsewhere does not lock this protocol
    L.issue.post(f"Run note: {PID} typo", updated="2030-01-01T00:00:00Z")
    with pytest.raises(LedgerRefusal, match=f"refused for {PID}"):
        L.complete("fit", "all", {}, {"m": 1})


# ---------- round 3: anchor before any step, result steps in the anchor, edit grace, recorded body sha ----------
def test_reviewer_poc_wrong_result_steps_then_replaced_ledger_refused(tmp_path):
    """Ledger A declares no result steps and runs `score` as a non-result step (values produced); A is deleted; ledger B, now declaring
    `score` a result step, anchors afterwards. B must be refused: A's anchor is the protocol's earliest."""
    r = tmp_path / "wind-brain"
    r.mkdir()
    issue = Issue()
    A = ledger(r, issue=issue, result_steps=frozenset())
    assert issue.comments[0]["body"].splitlines()[0].endswith(" -")
    A.begin("score", "all", {}, {})
    A.complete("score", "all", {"values": "c" * 64})
    shutil.rmtree(r / "_ledgers")
    B = ledger(r, issue=issue, result_steps=frozenset({"score"}))
    with pytest.raises(LedgerRefusal, match="earliest anchor"):
        B.begin("score", "all", {}, {})
    with pytest.raises(LedgerRefusal, match="earliest anchor"):
        B.begin("fetch", "all", {}, {})


def test_poc_without_any_anchor_cannot_produce_values(tmp_path):
    r = tmp_path / "wind-brain"
    r.mkdir()
    A = ledger(r, anchored=False, result_steps=frozenset())
    with pytest.raises(LedgerRefusal, match="no `Run anchor:"):
        A.begin("score", "all", {}, {})


def test_anchor_must_carry_the_genesis_result_steps(root):
    L = ledger(root, anchored=False)
    L.issue.post(f"Run anchor: {PID} {L.anchor()} fit")  # this ledger's hash, but a different step list
    with pytest.raises(LedgerRefusal, match="declares result steps 'fit'"):
        L.begin("fit", "all", {}, {})
    (root.parent / "m").mkdir()
    M = ledger(root.parent / "m", anchored=False)
    M.issue.post(f"Run anchor: {PID} {M.anchor()}")  # old one-hash form
    with pytest.raises(LedgerRefusal, match="declares result steps None"):
        M.begin("fit", "all", {}, {})


def test_updated_at_within_grace_is_not_an_edit(root):
    L = ledger(root)
    L.issue.post(f"note {PID}", created="2000-05-01T00:00:00Z", updated="2000-05-01T00:00:02Z")  # exactly 2 s: not an edit
    assert go(L) == 1
    L.issue.post(f"note {PID}", created="2000-05-01T00:00:00Z", updated="2000-05-01T00:00:03Z")  # > 2 s: an edit
    with pytest.raises(LedgerRefusal, match="edited"):
        L.complete("fit", "all", {}, {})


def test_recorded_comments_compare_body_sha_not_updated_at(root):
    L = ledger(root)
    run_step(L)
    for c in L.issue.comments:
        c["updated_at"] = "2040-01-01T00:00:00Z"  # GitHub bumps updated_at (e.g. a reaction); bodies unchanged
    assert L.audit(check_external=True)["findings"] == []
    res = next(c for c in L.issue.comments if c["body"].startswith("Run result:"))
    assert L.entries()[-1]["external"]["result"]["body_sha256"] == hashlib.sha256(res["body"].encode()).hexdigest()
    res["body"] = res["body"].replace("Do not edit", "Edited")
    f = L.audit(check_external=True)["findings"]
    assert any(x.startswith("BODY_CHANGED") for x in f) and any(x.startswith("EDITED:") for x in f)
    with pytest.raises(LedgerRefusal, match="differs from the body recorded"):
        L.begin("score", "all", {}, {})


def test_confirm_result_checks_the_comment(root):
    L = ledger(root)
    go(L)
    L.complete("fit", "all", {}, {"m": 1})
    with pytest.raises(LedgerRefusal, match="exactly one"):
        L.confirm_result("fit", "all")
    L.issue.post(f"Run result: {PID} fit all {'a' * 64} {'b' * 64}")
    with pytest.raises(LedgerRefusal, match="exactly one"):
        L.confirm_result("fit", "all")
