#!/usr/bin/env python3
"""Read-only production status for Sector Ops, and the Engine deploy's cycle preflight (Sector_Engine#160, Sector_Ops #51).

Run by .github/workflows/ops-status.yml as the read-only status account (WIF, `GCP_SA_OPS_STATUS`). It READS only: it never writes, deploys,
pauses, resumes, clears a latch or changes IAM. Every call is a GET (or the Logging entries:list query).

  python3 tools/deploy/ops_status.py report [--executions N] [--remote-config-log] [--rtdb]
  python3 tools/deploy/ops_status.py gate   [--max-cycle-age-hours H]

`gate` exits 0 only when
  1. the newest REAL (not --dry-run) completed brain-orchestrator execution succeeded (succeeded >= 1, failed 0) and was created within H
     hours, and
  2. the cycle watchdog latch (exports/orchestrator/watchdog/halt.json in the private artifact bucket) is absent or not HALTED.
Anything it cannot read or cannot classify REFUSES (exit 1). It never guesses that a cycle was real.

The token comes from OPS_STATUS_ACCESS_TOKEN (the auth step's short-lived access token). Output is safe for a public Actions log: names,
times, counts and states only; no account emails, no response bodies, no secret values. HTTP errors print the status code only."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT = os.environ.get("OPS_STATUS_PROJECT", "sector-9393c")
REGION = os.environ.get("OPS_STATUS_REGION", "us-central1")
JOB = "brain-orchestrator"
SERVICE = "sector-engine"
BUCKET = os.environ.get("PUBLICATION_ARTIFACT_BUCKET", "sector-9393c-brain-artifacts")
LATCH_KEY = "exports/orchestrator/watchdog/halt.json"          # sector_brain_platform.cycle_watchdog.LATCH_KEY (pinned by a test)
RTDB = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
CONTROL_NODE = "control/executionControlV1"                    # sector_brain_platform.execution_control.NODE (pinned by a test)
DRY_RUN_ARG = "--dry-run"
# exactly RemoteConfigStore.refreshLogLine: outcome, status, then optional parameters and the tile flag; nothing else is printed
RC_LINE = re.compile(r"\[remote-config\] refresh outcome=[a-z-]{1,20} status=(?:\d{3}|none)(?: parameters=\d{1,4})?"
                     r"(?: conditions_tiles_v1=(?:present|absent))?(?=\s|$)")
SCHEDULE_MINUTE = int(os.environ.get("OPS_STATUS_SCHEDULE_MINUTE", "50"))   # brain-orchestrator runs `50 * * * *` UTC


class Unreadable(Exception):
    """A read failed. The message carries the HTTP status or error class only."""


# ---- transport (injected in tests) ---------------------------------------------------------------------------------------------------

def http_fetch(token: str):
    def fetch(url: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""
        except (urllib.error.URLError, TimeoutError) as e:
            raise Unreadable(type(e).__name__) from None
    return fetch


def _get_json(fetch, url, body=None, missing_ok=False):
    status, raw = fetch(url, body)
    if status == 404 and missing_ok:
        return None
    if status != 200:
        raise Unreadable(f"HTTP {status}")
    try:
        return json.loads(raw or b"null")
    except ValueError:
        raise Unreadable("not JSON") from None


# ---- pure logic ----------------------------------------------------------------------------------------------------------------------

def _ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def classify(ex: dict) -> dict:
    """One Cloud Run v2 Execution -> a leak-free row. kind is real | dry-run | unknown (args not visible: never treated as real)."""
    containers = ((ex.get("template") or {}).get("containers")) if isinstance(ex.get("template"), dict) else None
    created = _ts(ex.get("createTime"))
    if isinstance(containers, list) and containers and all(isinstance(c, dict) and "args" in c for c in containers):
        if any(DRY_RUN_ARG in (c.get("args") or []) for c in containers):
            kind = "dry-run"
        elif created is not None and created.minute in (SCHEDULE_MINUTE, (SCHEDULE_MINUTE + 1) % 60):
            kind = "real"         # no --dry-run AND started by the :50 schedule: two independent signals, so a dry run cannot pass alone
        else:
            kind = "manual"       # no --dry-run visible but not at the schedule minute: never counted as the real cycle
    else:
        kind = "unknown"
    running = int(ex.get("runningCount") or 0)
    done = bool(ex.get("completionTime"))
    return {"name": str(ex.get("name", "")).rsplit("/", 1)[-1], "created": ex.get("createTime"), "completed": ex.get("completionTime"),
            "succeeded": int(ex.get("succeededCount") or 0), "failed": int(ex.get("failedCount") or 0),
            "cancelled": int(ex.get("cancelledCount") or 0), "running": running, "done": done, "kind": kind}


def latch_state(doc) -> str:
    if doc is None:
        return "none"
    if isinstance(doc, dict) and doc.get("state") in ("HALTED", "CLEARED"):
        return doc["state"]
    return "unrecognised"


def gate(rows: list[dict], latch: str, now: dt.datetime, max_age_hours: float) -> tuple[bool, list[str]]:
    """(ok, reasons). rows newest first is NOT assumed; they are sorted here."""
    reasons: list[str] = []
    if latch == "HALTED":
        reasons.append("watchdog latch is HALTED")
    elif latch not in ("none", "CLEARED"):
        reasons.append(f"watchdog latch is {latch}")
    rows = sorted(rows, key=lambda r: _ts(r["created"]) or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
    candidate = next((r for r in rows if r["done"] and r["kind"] not in ("dry-run", "manual")), None)   # newest completed scheduled run
    if candidate is not None and candidate["kind"] == "unknown":
        reasons.append(f"cannot tell whether {candidate['name']} was a real or a dry-run cycle (no args visible)")
        return False, reasons
    real = candidate
    if real is None:
        reasons.append("no completed real (non --dry-run) cycle in the listed executions")
        return False, reasons
    created = _ts(real["created"])
    if created is None:
        reasons.append(f"{real['name']} has no readable createTime")
    elif now - created > dt.timedelta(hours=max_age_hours):
        reasons.append(f"newest real cycle {real['name']} was created {created:%Y-%m-%dT%H:%MZ}, older than {max_age_hours:g} h")
    if not (real["succeeded"] >= 1 and real["failed"] == 0 and real["cancelled"] == 0):
        reasons.append(f"newest real cycle {real['name']} did not succeed (succeeded {real['succeeded']}, failed {real['failed']},"
                       f" cancelled {real['cancelled']})")
    return (not reasons), reasons


def remote_config_lines(entries: list[dict]) -> list[str]:
    out = []
    for e in entries or []:
        m = RC_LINE.search(str(e.get("textPayload") or ""))
        if m:
            out.append(f"{str(e.get('timestamp', ''))[:19]}Z {m.group(0)}")
    return out


# ---- reads ---------------------------------------------------------------------------------------------------------------------------

def read_executions(fetch, n: int) -> list[dict]:
    url = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/jobs/{JOB}/executions?pageSize={int(n)}"
    doc = _get_json(fetch, url) or {}
    return [classify(e) for e in doc.get("executions") or []]


def read_latch(fetch) -> str:
    url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{urllib.parse.quote(LATCH_KEY, safe='')}?alt=media"
    return latch_state(_get_json(fetch, url, missing_ok=True))


def read_scheduler(fetch) -> str:
    d = _get_json(fetch, f"https://cloudscheduler.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/jobs/{JOB}") or {}
    return f"{d.get('state', '?')} {d.get('schedule', '?')} (last attempt {d.get('lastAttemptTime', '?')})"


def read_engine(fetch) -> str:
    base = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/services/{SERVICE}"
    s = _get_json(fetch, base) or {}
    traffic = [t for t in s.get("trafficStatuses") or [] if t.get("percent")]
    if not traffic:
        return "no serving revision found"
    rev = max(traffic, key=lambda t: t.get("percent", 0)).get("revision", "")
    r = _get_json(fetch, f"{base}/revisions/{rev}") or {}
    return f"{rev} ({max(t.get('percent', 0) for t in traffic)}% traffic, commit label {(r.get('labels') or {}).get('commit', '?')})"


def read_remote_config_log(fetch) -> list[str]:
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"resourceNames": [f"projects/{PROJECT}"], "orderBy": "timestamp desc", "pageSize": 5,
            "filter": f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" '
                      f'AND textPayload:"[remote-config]" AND timestamp>="{since}"'}
    return remote_config_lines((_get_json(fetch, "https://logging.googleapis.com/v2/entries:list", body) or {}).get("entries"))


def read_control(fetch) -> str:
    d = _get_json(fetch, f"{RTDB}/{CONTROL_NODE}.json")
    if not isinstance(d, dict):
        return "absent (reads as PAUSED)"
    on = sorted(b for b, v in (d.get("brains") or {}).items() if isinstance(v, dict) and v.get("enabled") is True)
    return f"{d.get('state', '?')} approvalRef {str(d.get('approvalRef') or '-')[:80]}; enabled Brains {', '.join(on) or 'none'}"


def _try(label, fn):
    try:
        return fn()
    except Unreadable as e:
        return f"not readable ({e})"


# ---- CLI -----------------------------------------------------------------------------------------------------------------------------

def main(argv=None, fetch=None, now=None, out=print) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("report", "gate"))
    ap.add_argument("--executions", type=int, default=5)
    ap.add_argument("--max-cycle-age-hours", type=float, default=3.0)
    ap.add_argument("--remote-config-log", action="store_true")
    ap.add_argument("--rtdb", action="store_true", help="also read the execution control (needs the optional RTDB read grant)")
    a = ap.parse_args(argv)
    if fetch is None:
        token = os.environ.get("OPS_STATUS_ACCESS_TOKEN", "")
        if not token:
            out("refused: OPS_STATUS_ACCESS_TOKEN is not set (GCP_SA_OPS_STATUS / WIF not configured?)")
            return 1
        fetch = http_fetch(token)
    now = now or dt.datetime.now(dt.timezone.utc)

    try:
        rows = read_executions(fetch, max(a.executions, 10) if a.cmd == "gate" else a.executions)
        exec_err = None
    except Unreadable as e:
        rows, exec_err = [], str(e)
    try:
        latch, latch_err = read_latch(fetch), None
    except Unreadable as e:
        latch, latch_err = "unreadable", str(e)

    out(f"## brain-orchestrator executions (newest first){'' if exec_err is None else f': not readable ({exec_err})'}")
    out("| execution | kind | created | completed | succeeded | failed | running |")
    out("|---|---|---|---|---|---|---|")
    for r in rows[: a.executions]:
        out(f"| {r['name']} | {r['kind']} | {r['created'] or '-'} | {r['completed'] or '-'} | {r['succeeded']} | {r['failed']} | {r['running']} |")
    out(f"watchdog latch: {latch}{'' if latch_err is None else f' ({latch_err})'}")

    if a.cmd == "gate":
        if exec_err is not None:
            out(f"GATE REFUSED: executions not readable ({exec_err})")
            return 1
        ok, reasons = gate(rows, latch, now, a.max_cycle_age_hours)
        if ok:
            out(f"GATE PASSED: the newest real cycle succeeded within {a.max_cycle_age_hours:g} h and the watchdog shows no halt")
            return 0
        for why in reasons:
            out(f"GATE REFUSED: {why}")
        return 1

    out(f"scheduler {JOB}: {_try('scheduler', lambda: read_scheduler(fetch))}")
    out(f"Engine serving revision: {_try('engine', lambda: read_engine(fetch))}")
    if a.rtdb:
        out(f"execution control: {_try('control', lambda: read_control(fetch))}")
    else:
        out("execution control: not read (run with rtdb=true; needs the optional RTDB read grant)")
    if a.remote_config_log:
        lines = _try("logs", lambda: read_remote_config_log(fetch))
        if isinstance(lines, str):
            out(f"[remote-config] log: {lines}")
        else:
            out("[remote-config] log, newest first (last 3 days):" if lines else "[remote-config] log: no line in the last 3 days")
            for line in lines:
                out(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
