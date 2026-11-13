"""ops_status: execution classification, the deploy-engine cycle gate, leak-free output, read-only transport. Offline (fake fetch)."""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ops_status as S  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NOW = dt.datetime(2026, 11, 10, 7, 0, tzinfo=dt.timezone.utc)


def ex(name, created, ok=True, dry=False, done=True, args=True, failed=0):
    c = {"image": "x"}
    if args:
        c["args"] = ["--publish-health"] + (["--dry-run"] if dry else [])
    return {"name": f"projects/p/locations/r/jobs/brain-orchestrator/executions/{name}", "createTime": created,
            "completionTime": created if done else None, "succeededCount": 1 if (ok and done) else 0,
            "failedCount": failed if failed else (0 if ok else 1), "runningCount": 0 if done else 1, "template": {"containers": [c]}}


def rows(*e):
    return [S.classify(x) for x in e]


def test_pinned_constants_match_the_platform():
    sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
    from sector_brain_platform import cycle_watchdog as WD, execution_control as EC
    assert S.LATCH_KEY == WD.LATCH_KEY
    assert S.CONTROL_NODE == EC.NODE


def test_classify_kinds():
    assert S.classify(ex("a", "2026-11-10T05:50:00Z"))["kind"] == "real"
    assert S.classify(ex("b", "2026-11-10T05:50:00Z", dry=True))["kind"] == "dry-run"
    assert S.classify(ex("c", "2026-11-10T05:50:00Z", args=False))["kind"] == "unknown"
    assert S.classify({"name": "d"})["kind"] == "unknown"
    # no --dry-run visible but not started at the :50 schedule minute: never the real cycle (fails closed if overrides are hidden)
    assert S.classify(ex("m", "2026-11-10T05:37:00Z"))["kind"] == "manual"
    assert S.classify(ex("a", "2026-11-10T05:50:00Z"))["name"] == "a"


def test_gate_passes_on_a_recent_successful_real_cycle_with_no_latch():
    ok, why = S.gate(rows(ex("real1", "2026-11-10T05:50:00Z")), "none", NOW, 3)
    assert ok and why == []
    assert S.gate(rows(ex("real1", "2026-11-10T05:50:00Z")), "CLEARED", NOW, 3)[0]


def test_gate_skips_newer_dry_runs_and_a_running_cycle():
    r = rows(ex("dry", "2026-11-10T06:30:00Z", dry=True), ex("running", "2026-11-10T06:50:00Z", done=False),
             ex("real1", "2026-11-10T05:50:00Z"))
    assert S.gate(r, "none", NOW, 3)[0]


def test_gate_ignores_manual_runs_and_refuses_when_only_manual_runs_exist():
    assert S.gate(rows(ex("man", "2026-11-10T06:37:00Z"), ex("real1", "2026-11-10T05:50:00Z")), "none", NOW, 3)[0]
    ok, why = S.gate(rows(ex("man", "2026-11-10T06:37:00Z")), "none", NOW, 3)
    assert not ok and "no completed real" in why[0]


def test_gate_refuses_a_cancelled_cycle():
    e = ex("c1", "2026-11-10T05:50:00Z")
    e["cancelledCount"] = 1
    assert not S.gate(rows(e), "none", NOW, 3)[0]


def test_gate_refuses_halted_or_unreadable_latch():
    r = rows(ex("real1", "2026-11-10T05:50:00Z"))
    for latch in ("HALTED", "unreadable", "unrecognised"):
        ok, why = S.gate(r, latch, NOW, 3)
        assert not ok and any("latch" in w for w in why)


def test_gate_refuses_failed_stale_missing_or_unknown():
    assert not S.gate(rows(ex("bad", "2026-11-10T05:50:00Z", ok=False)), "none", NOW, 3)[0]
    assert not S.gate(rows(ex("old", "2026-11-10T02:50:00Z")), "none", NOW, 3)[0]
    assert not S.gate(rows(ex("dry", "2026-11-10T05:50:00Z", dry=True)), "none", NOW, 3)[0]
    assert not S.gate([], "none", NOW, 3)[0]
    # an execution whose args are not visible is never assumed real, even if an older real one succeeded
    ok, why = S.gate(rows(ex("unk", "2026-11-10T06:50:00Z", args=False), ex("real1", "2026-11-10T05:50:00Z")), "none", NOW, 3)
    assert not ok and "cannot tell" in why[0]
    # a newer FAILED real cycle wins over an older success
    assert not S.gate(rows(ex("bad", "2026-11-10T06:50:00Z", ok=False), ex("real1", "2026-11-10T05:50:00Z")), "none", NOW, 3)[0]


def test_remote_config_lines_are_filtered_to_the_known_shape():
    entries = [{"timestamp": "2026-11-10T06:00:00.123Z", "textPayload": "x [remote-config] refresh outcome=ok status=200 parameters=2 conditions_tiles_v1=present"},
               {"timestamp": "2026-11-10T05:00:00Z", "textPayload": "unrelated user@example.com line"},
               {"timestamp": "2026-11-10T04:00:00Z", "textPayload": "[remote-config] refresh outcome=http-error status=403 secret=ya29.AAAA/BBB"}]
    out = S.remote_config_lines(entries)
    assert out[0] == "2026-11-10T06:00:00Z [remote-config] refresh outcome=ok status=200 parameters=2 conditions_tiles_v1=present"
    assert len(out) == 2 and out[1].endswith("outcome=http-error status=403")
    assert "ya29" not in " ".join(out) and "example.com" not in " ".join(out)


class Fake:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, body=None):
        self.calls.append((url, body))
        for frag, (status, doc) in self.routes.items():
            if frag in url:
                return status, (json.dumps(doc).encode() if doc is not None else b"")
        return 404, b""


def routes(execs, latch=(404, None)):
    return {"/jobs/brain-orchestrator/executions": (200, {"executions": execs}), "/o/exports%2Forchestrator%2Fwatchdog%2Fhalt.json": latch,
            "cloudscheduler": (200, {"state": "ENABLED", "schedule": "50 * * * *", "lastAttemptTime": "2026-11-10T06:50:00Z"}),
            "/services/sector-engine/revisions/": (200, {"labels": {"commit": "9bb11233abcd"}}),
            "/services/sector-engine": (200, {"trafficStatuses": [{"revision": "sector-engine-00056-9s2", "percent": 100}]}),
            "entries:list": (200, {"entries": [{"timestamp": "2026-11-10T06:00:00Z", "textPayload": "[remote-config] refresh outcome=ok status=200"}]}),
            "firebaseio.com": (200, {"state": "ENABLED", "approvalRef": "ref-1", "brains": {"wind": {"enabled": True}, "lake": {"enabled": False}}})}


def run(argv, fake):
    lines = []
    code = S.main(argv, fetch=fake, now=NOW, out=lines.append)
    return code, "\n".join(lines)


def test_gate_cli_pass_and_refuse():
    code, text = run(["gate"], Fake(routes([ex("real1", "2026-11-10T05:50:00Z")])))
    assert code == 0 and "GATE PASSED" in text and "watchdog latch: none" in text
    code, text = run(["gate"], Fake(routes([ex("real1", "2026-11-10T05:50:00Z")], latch=(200, {"state": "HALTED", "at": "x"}))))
    assert code == 1 and "GATE REFUSED: watchdog latch is HALTED" in text
    code, text = run(["gate"], Fake(routes([ex("real1", "2026-11-10T05:50:00Z")], latch=(403, None))))
    assert code == 1 and "HTTP 403" in text


def test_gate_cli_refuses_when_executions_are_unreadable():
    r = routes([])
    r["/jobs/brain-orchestrator/executions"] = (403, None)
    code, text = run(["gate"], Fake(r))
    assert code == 1 and "executions not readable (HTTP 403)" in text


def test_report_reads_only_and_prints_no_identity():
    fake = Fake(routes([ex("real1", "2026-11-10T05:50:00Z"), ex("dry1", "2026-11-10T05:40:00Z", dry=True)]))
    code, text = run(["report", "--remote-config-log", "--rtdb"], fake)
    assert code == 0
    assert "| real1 | real |" in text and "| dry1 | dry-run |" in text
    assert "ENABLED 50 * * * *" in text and "sector-engine-00056-9s2 (100% traffic, commit label 9bb11233abcd)" in text
    assert "enabled Brains wind" in text and "[remote-config] refresh outcome=ok status=200" in text
    assert "gserviceaccount" not in text and "@" not in text
    # read-only: every call is a GET except the Logging entries:list query
    assert all(body is None or url.endswith("entries:list") for url, body in fake.calls)


def test_report_without_rtdb_does_not_touch_the_database():
    fake = Fake(routes([ex("real1", "2026-11-10T05:50:00Z")]))
    code, text = run(["report"], fake)
    assert code == 0 and "execution control: not read" in text
    assert not any("firebaseio.com" in url or "entries:list" in url for url, _ in fake.calls)


def test_missing_token_refuses(monkeypatch):
    monkeypatch.delenv("OPS_STATUS_ACCESS_TOKEN", raising=False)
    lines = []
    assert S.main(["gate"], out=lines.append) == 1 and "refused" in lines[0]
