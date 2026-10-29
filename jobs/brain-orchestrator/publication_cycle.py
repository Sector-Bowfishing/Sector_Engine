#!/usr/bin/env python3
"""Local publication-coordination cycle for the Orchestrator (Cortex 3.1 PL-19). LOCAL ONLY: it reads a private artifact store directory and an execution-records file, keeps a
JSON ledger, and prints the summary. It writes NO database, creates no bucket, holds no credential and never arms the Publisher: the live Publisher is not constructed here, so every
Brain's run record says its existing direct writer is the writer and `publication.outcome` stays NOT_REQUESTED. Shadow checks are recorded separately and are never counted as published.

  python3 publication_cycle.py --store-dir DIR --ledger LEDGER.json [--executions EXEC.json] [--shadow] [--dispatch-tasks TASKS.json]

DIR holds artifacts/{brainId}/{artifactId}/artifact.json (what the Brains' ArtifactWriter creates). EXEC.json is a list of orchestration.execution_record dicts (Cloud Run results already
retrieved by the control plane). TASKS.json is [{id, brain, title}]: each is routed only to its owning Brain (mission-audit) before dispatch.
Wiring this into the scheduled cycle needs the private artifact bucket and the Publisher's live dependencies; both are gated (see docs/cortex/sessions/2026-10-28-orchestrator-cortex-3-1.md).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform import data_ownership as DO                                             # noqa: E402
from sector_brain_platform import task_routing as TR                                               # noqa: E402
from sector_brain_platform.publication_coordination import PublicationCoordinator, PublicationLedger          # noqa: E402
from sector_brain_platform.publisher import ShadowPublisher, ShadowSink, PublishHistory, PublisherMode, default_registry, publisher_view      # noqa: E402
from sector_brain_platform.publisher.storage import LocalDirObjectStore                           # noqa: E402


def run(store_dir: str, ledger_path: str, executions: list | None = None, shadow: bool = False, tasks: list | None = None) -> dict:
    store = LocalDirObjectStore(store_dir)
    sh = ShadowPublisher(default_registry(), PublishHistory(publisher_view(store)), ShadowSink(), mode=PublisherMode.SHADOW) if shadow else None
    co = PublicationCoordinator(PublicationLedger(ledger_path), store, shadow=sh, live=None, cutover=())
    out = {"reconcile": co.reconcile(executions or [])}
    for key in out["reconcile"]["collected"]:
        co.evaluate_shadow(key)
        co.request_publication(key)
    out["resume"] = co.resume()
    out["summary"] = co.summary()
    out["targetBrains"] = DO.target_ids()
    if tasks is not None:
        out["dispatch"] = TR.dispatch_gate(tasks)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store-dir", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--executions")
    ap.add_argument("--shadow", action="store_true")
    ap.add_argument("--dispatch-tasks")
    a = ap.parse_args(argv)
    ex = json.load(open(a.executions, encoding="utf-8")) if a.executions else []
    tasks = json.load(open(a.dispatch_tasks, encoding="utf-8")) if a.dispatch_tasks else None
    print(json.dumps(run(a.store_dir, a.ledger, ex, a.shadow, tasks), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
