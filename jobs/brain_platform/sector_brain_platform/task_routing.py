"""Task dispatch ownership (Cortex 3.1 BA-07, migration M08): the Orchestrator dispatches each research or development task ONLY to the Brain that owns it.

It consumes `cortex.py mission-audit --tasks ... --json` (Cortex owns the detection; the Orchestrator acts on the findings):
  WRONG_OWNER          -> the task is RE-ROUTED to the finding's `correctOwner` and the original owner is told why
  UNKNOWN_BRAIN / UNREGISTERED_BRAIN / UNAUTHORIZED_INPUT -> the task is BLOCKED until the owner changes the task or the architecture
  Cortex unavailable   -> nothing is dispatched (fail closed): an unaudited task is never assumed to be in mission.
Brain ids are checked against the nine Cortex target Brains and the deployed identities (data_ownership.recognize) before the audit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

from . import data_ownership as DO

BLOCKING = ("UNKNOWN_BRAIN", "UNREGISTERED_BRAIN", "UNAUTHORIZED_INPUT")


def cortex_tool(env=None) -> str | None:
    home = (env or os.environ).get("CORTEX_HOME")          # no machine-specific default: runtime code never assumes a developer checkout (KM standing check)
    p = os.path.join(home, "tools", "cortex.py") if home else ""
    return p if p and os.path.exists(p) else None


def run_audit(tasks: list, pack: str = "sector/engine", runner=subprocess.run, tool: str | None = None) -> dict | None:
    """-> the mission-audit JSON report for `tasks` ([{id, brain, title}]), or None when Cortex cannot be run."""
    tool = tool or cortex_tool()
    if not tool:
        return None
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "tasks.json")
        json.dump({"tasks": tasks}, open(path, "w"))
        p = runner([sys.executable, tool, "mission-audit", pack, "--tasks", path, "--json"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(p.stdout)
    except (ValueError, TypeError, AttributeError):
        return None


def dispatch_gate(tasks: list, audit=None, **kw) -> dict:
    """-> {dispatch, rerouted, blocked, unverified}. `audit` is an injectable report (tests); otherwise Cortex is run."""
    out = {"dispatch": [], "rerouted": [], "blocked": [], "unverified": False}
    known, pending = [], []
    for t in tasks:
        r = DO.recognize(t.get("brain", ""))
        if r["kind"] in ("UNREGISTERED", "ALIAS"):
            out["blocked"].append({"id": t["id"], "kind": "UNREGISTERED_BRAIN", "brain": t.get("brain"), "why": f"{t.get('brain')!r} is neither a Cortex target Brain nor a deployed package"})
        else:
            known.append(t)
    if not known:
        return out
    report = audit if audit is not None else run_audit(known, **kw)
    if report is None:
        out["unverified"] = True
        out["blocked"] += [{"id": t["id"], "kind": "UNVERIFIED", "brain": t.get("brain"), "why": "mission-audit could not be run (Cortex unavailable): nothing is dispatched unaudited"} for t in known]
        return out
    by_task = {}
    for f in report.get("findings") or []:
        subj = str(f.get("subject", ""))
        by_task.setdefault(subj.replace("task ", "", 1), []).append(f)
    for t in known:
        fs = by_task.get(t["id"], [])
        block = [f for f in fs if f["kind"] in BLOCKING]
        wrong = [f for f in fs if f["kind"] == "WRONG_OWNER" and f.get("correctOwner")]
        if block:
            out["blocked"].append({"id": t["id"], "kind": block[0]["kind"], "brain": t.get("brain"), "why": block[0].get("correction", ""), "findingId": block[0].get("id")})
        elif wrong:
            out["rerouted"].append({"id": t["id"], "from": t["brain"], "to": wrong[0]["correctOwner"], "why": wrong[0].get("correction", ""), "findingId": wrong[0].get("id"), "task": {**t, "brain": wrong[0]["correctOwner"]}})
        else:
            out["dispatch"].append(t)
    return out
