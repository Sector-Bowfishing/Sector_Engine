"""The Orchestrator's publication stage (Cortex 3.1 PL-19), run inside the real cycle (jobs/brain-orchestrator/orchestrate.py, step 4b).

  collect  -> every terminal execution of this cycle and of Cloud Run (orchestration.execution_record dicts) is reconciled with the sealed artifacts in the private store
  shadow   -> the SHADOW Publisher records its verdict separately (never counted as published)
  request  -> the live Publisher is asked ONLY for a Brain whose cutover is approved AND only when a live Publisher was supplied AND the global execution control permits work
  record   -> a run record per (Brain, run, artifact) with PUBLISHED / SKIPPED / REJECTED / FAILED, reason and readback; Brains still on their direct writer say so

OFF unless the cycle is started with --coordinate-publication. This module never builds a database client, a bucket client or a live Publisher: those are injected by the caller, and the
cycle supplies none (the Publisher stays unarmed until an approved arming). A cutover document may mark a Brain CENTRAL only with an approval reference; DIRECT_WRITE is always available
and is the rollback (the Publisher's heads are never rewritten by a rollback of the Brain's mode).
"""
from __future__ import annotations

import json
import os

from .publication_coordination import PublicationCoordinator, PublicationLedger

CUTOVER_SCHEMA = "sector-publication-cutover-v1"
STATES = ("DIRECT_WRITE", "CENTRAL")


def load_cutover(path: str | None) -> tuple[dict, list]:
    """-> ({brainId: {state, approvalRef}}, problems). A CENTRAL entry without an approval reference, an unknown Brain, an alias or an unrecognised state is IGNORED (the Brain stays on its
    direct writer) and reported. Unreadable or absent = every Brain on its direct writer."""
    from . import data_ownership as DO
    if not path or not os.path.exists(path):
        return {}, []
    problems, out = [], {}
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, [{"kind": "CUTOVER_UNREADABLE", "why": type(e).__name__}]
    if doc.get("schema") != CUTOVER_SCHEMA:
        return {}, [{"kind": "CUTOVER_SCHEMA", "why": f"expected {CUTOVER_SCHEMA}"}]
    for bid, e in sorted((doc.get("brains") or {}).items()):
        kind = DO.recognize(bid)["kind"]
        if kind in ("UNREGISTERED", "ALIAS"):
            problems.append({"kind": "CUTOVER_UNKNOWN_BRAIN", "brainId": bid})
        elif kind == "LEGACY_COMBINED" and e.get("state") == "CENTRAL":
            problems.append({"kind": "CUTOVER_LEGACY_COMBINED_FROZEN", "brainId": bid, "why": "biological-state stays on its direct writer until the approved Fish/Biological split (BA-04)"})
        elif e.get("state") not in STATES:
            problems.append({"kind": "CUTOVER_STATE", "brainId": bid})
        elif e["state"] == "CENTRAL" and not e.get("approvalRef"):
            problems.append({"kind": "CUTOVER_NOT_APPROVED", "brainId": bid, "why": "CENTRAL needs an approvalRef"})
        else:
            out[bid] = {"state": e["state"], "approvalRef": e.get("approvalRef")}
    return out, problems


def run_stage(*, store, ledger_path: str | None, executions: list, shadow=None, live=None, cutover_path: str | None = None, paused_reason: str | None = None, clock=None) -> dict:
    """One publication pass. Returns {summary, reconcile, resume, cutover, outputChanged, armed} for the cycle record. Raises nothing the cycle needs to handle for a single bad artifact:
    those become ledger records."""
    cut, problems = load_cutover(cutover_path)
    central = sorted(b for b, e in cut.items() if e["state"] == "CENTRAL")
    kw = {"clock": clock} if clock else {}
    co = PublicationCoordinator(PublicationLedger(ledger_path), store, shadow=shadow, live=live, cutover=central, hold_reason=paused_reason, **kw)
    rec = co.reconcile(executions)
    changes = {}
    for key in rec["collected"]:
        co.evaluate_shadow(key)
        r = co.request_publication(key)
        changes[r["runId"] if r["brainId"] else key] = {"brainId": r["brainId"], "outputChanged": co.output_change(r)}
    resumed = co.resume()                                                       # records left unfinished by an earlier cycle (retries after backoff, shadow not yet run)
    return {"armed": live is not None, "cutover": {"central": central, "directWrite": "every other Brain", "problems": problems}, "reconcile": rec, "resume": resumed,
            "outputChanged": changes, "summary": co.summary()}
