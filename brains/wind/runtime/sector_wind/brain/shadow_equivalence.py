"""Wind shadow equivalence, per run (PREPARED 2026-10-31; OFF unless WIND_SHADOW_EQUIVALENCE=on is deployed with approval).

The Wind cutover needs at least 7 days of evidence that what the Publisher WOULD publish equals what the legacy writer actually stored
(docs/architecture/production/PRODUCTION_CUTOVER_PLANS_V1.md, Wind "dry run"). For one wind-hourly run this module:

  1. records the PATCH dictionaries the legacy writer sent (`RecordingWriter` wraps the real writer; nothing about the write changes);
  2. seals them with the existing SHADOW builder (`artifact.build_artifacts`) and renders the Publisher's plan (`render_target`, DRY_RUN, nothing persisted);
  3. reads back the STORED value of every key the legacy writer wrote (GET only) and runs the Publisher's equivalence evaluator on stored vs plan;
  4. writes ONE digest-only evidence record, create-only, to an evidence store (`exports/shadow-equivalence/wind/`). Values are never kept, only SHA-256 digests.

It never raises into the job, never changes the job's exit code and never writes the Brain database. A failure is recorded as an evidence record with
verdict ERROR (it counts against the run's coverage, never as equivalent).
"""
from __future__ import annotations

import datetime as dt
import json
import uuid

from . import artifact as A

SCHEMA = "wind-shadow-equivalence-run-v1"
PREFIX = "exports/shadow-equivalence/wind/"
FLAG = "WIND_SHADOW_EQUIVALENCE"


class RecordingWriter:
    """Delegates every call to the real writer and keeps a copy of each PATCH it actually sent (only after the write returned)."""

    def __init__(self, inner):
        self._inner, self.patches = inner, []

    def patch(self, updates: dict) -> None:
        self._inner.patch(updates)
        if updates:
            self.patches.append(dict(updates))

    def get(self, path, query=None):
        return self._inner.get(path, query)

    def delete(self, path):
        self.patch({path: None})

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _nest(flat: dict) -> dict:
    tree: dict = {}
    for key, val in flat.items():
        if val is None:
            continue
        parts = [p for p in key.strip("/").split("/") if p]
        node = tree
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = node[p] = {}
            node = nxt
        node[parts[-1]] = val
    return tree


def readback(get, keys) -> tuple[dict, list]:
    """GET the stored value of every written key. -> (nested live tree, [errors]). A key that fails to read is reported, never assumed equal."""
    stored, errors = {}, []
    for k in sorted(set(keys)):
        try:
            stored[k] = get(k)
        except Exception as e:                                                  # noqa: BLE001
            errors.append({"key": k, "error": type(e).__name__})
    return _nest(stored), errors


def evaluate_run(patches: list, get, *, run_at: str, code_version: str, execution_id: str | None = None, registry=None) -> dict:
    """The evidence record for one run (digest-only). `get(key)` reads the Brain database (GET only)."""
    from sector_brain_platform.publisher import default_registry
    from sector_brain_platform.publisher.equivalence import evaluate_equivalence, render_target
    reg = registry or default_registry()
    rec = {"schema": SCHEMA, "brainId": A.WIND, "runAt": run_at, "executionId": execution_id or str(uuid.uuid4()), "codeVersion": code_version,
           "patches": len(patches)}
    if not patches:
        return {**rec, "verdict": "NO_LEGACY_WRITE", "reason": "the legacy writer sent nothing this run"}
    built = A.build_artifacts(patches, A.BuildContext(run_at, rec["executionId"], code_version))
    if built.artifact is None:
        return {**rec, "verdict": "ERROR", "reason": "artifact build produced no artifact"}
    tgt = render_target(built.artifact, reg)
    rec.update(artifactId=built.artifact["lineage"].get("artifactId"), outputFingerprint=built.artifact["lineage"]["outputFingerprint"], targetResult=tgt["result"])
    if tgt["result"] != "SHADOW_READY":
        return {**rec, "verdict": "ERROR", "reason": f"the Publisher would not accept the artifact: {tgt['result']} {tgt.get('codes')}"}
    keys = [k for p in patches for k, v in p.items() if v is not None]
    live, errors = readback(get, keys)
    rec["readback"] = {"keys": len(set(keys)), "errors": errors}
    if errors:
        return {**rec, "verdict": "ERROR", "reason": f"{len(errors)} stored values could not be read back"}
    ev = evaluate_equivalence(live, tgt["updates"], registry=reg, derived_keys=tgt["derivedKeys"])
    return {**rec, "verdict": ev["verdict"], "blocking": ev["blocking"], "summary": ev["summary"], "openCompatibilityRules": ev["openCompatibilityRules"],
            "differences": [d for d in ev["differences"] if not d["explained"]][:50]}           # unexplained only; paths + digests, never values


def evidence_key(rec: dict) -> str:
    return f"{PREFIX}{rec['runAt'].replace(':', '')}-{rec['executionId']}.json"


def store_evidence(store, rec: dict) -> str:
    key = evidence_key(rec)
    store.put(key, json.dumps(rec, sort_keys=True, separators=(",", ":")).encode(), if_generation_match=0)
    return key


def safe_record(writer: RecordingWriter, store, *, now: dt.datetime, code_version: str) -> dict:
    """Entry point for wind-hourly: never raises. -> a short summary for the job log."""
    run_at = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rec = evaluate_run(writer.patches, lambda k: writer.get(k), run_at=run_at, code_version=code_version)
    except Exception as e:                                                      # noqa: BLE001
        rec = {"schema": SCHEMA, "brainId": A.WIND, "runAt": run_at, "executionId": str(uuid.uuid4()), "codeVersion": code_version,
               "verdict": "ERROR", "reason": f"{type(e).__name__}: {str(e)[:200]}"}
    try:
        key = store_evidence(store, rec)
    except Exception as e:                                                      # noqa: BLE001
        return {"verdict": rec["verdict"], "stored": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"verdict": rec["verdict"], "stored": True, "key": key}
