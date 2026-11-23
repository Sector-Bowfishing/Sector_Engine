"""Artifact mode for the Python Brains that publish through a writer (Weather, Moon, Generation): one implementation of "run the Brain's
UNCHANGED publish step into its DryRunWriter, reading the previous state from the live Brain database (GET only), seal the write set with the
Brain's `publish_artifact.build_artifact`, store ONE artifact create-only and hand it off as a local file" for a runner that holds the Brain's
lease (a runner's `<brain>-central` catalog entries). The Python sibling of swift_artifact_entry.py; the wind entry is its own (ingest + archive).

It performs NO database write and no bucket write. The central Publisher is the only writer once a Brain is CENTRAL, and it refuses the artifact
until the Brain's knowledge release is approved, the Brain is CENTRAL in publication-cutover.json and the execution control enables it.

The Brain's live write gates hold here too, because a hand-off is the path to a write: the entry refuses unless the verified knowledge release is
APPROVED (exit 2, BLOCKED_AWAITING_APPROVED_RELEASE) AND `<BRAIN>_WRITE_APPROVED=1` is set (operator intent; exit 3), exactly as `run.py --write`.

  <brain>/runtime/artifact_entry.py --artifact-dir DIR [--emit FILE --read-rtdb [--rtdb-url URL]] [--execution-id UUID] [brain flags]
env: SECTOR_ENGINE_COMMIT (code version in the lineage); with --read-rtdb, BRAIN_ACCESS_TOKEN (the runner's READ token; GET only)

  * --emit (the hand-off) REQUIRES --read-rtdb: the previous state must be what is live, never an empty or local tree (wind W-H2 rule).
  * the live database is reached only through LiveReadOnly, which has no write method.
  * a publish step that reads a path it already wrote in this run sees its own write (ReadThroughWriter overlays the run's patches on the live
    value), so the sealed write set is the one `run.py --write` would have written.

Exit 0 = artifact stored (its reference is printed as JSON; the run's own outcome, e.g. PARTIAL, is inside the artifact as the Brain writes it);
2 = refused (nothing stored); 3 = operator intent missing (nothing stored); 4 = the run produced no artifact (nothing stored)."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import sys
import uuid
from typing import Callable

BLOCKED = "BLOCKED_AWAITING_APPROVED_RELEASE"


class LiveReadOnly:
    """GET-only view of the Brain RTDB. It exposes no write method, so no code path of the run can write through it, whatever the token allows."""

    def __init__(self, inner):
        self._inner = inner
        self.reads = 0

    def get(self, path: str):
        self.reads += 1
        return self._inner.get(path)


def _parts(path: str) -> list[str]:
    return [p for p in path.split("/") if p]


def overlay(value, path: str, patches: list) -> object:
    """`value` (what is live at `path`) with every patch of this run that touches `path` applied in order (null deletes)."""
    want = _parts(path)
    v = copy.deepcopy(value)
    for upd in patches:
        for key, new in upd.items():
            kp = _parts(key)
            if kp == want:
                v = copy.deepcopy(new)
            elif kp[: len(want)] == want:                        # a write below `path`
                if not isinstance(v, dict):
                    v = {}
                node = v
                for p in kp[len(want):-1]:
                    if not isinstance(node.get(p), dict):
                        node[p] = {}
                    node = node[p]
                if new is None:
                    node.pop(kp[-1], None)
                else:
                    node[kp[-1]] = copy.deepcopy(new)
            elif want[: len(kp)] == kp:                          # a write of an ancestor of `path`
                node = new
                for p in want[len(kp):]:
                    node = node.get(p) if isinstance(node, dict) else None
                v = copy.deepcopy(node)
    return None if v == {} else v


class ReadThroughWriter:
    """The Brain's DryRunWriter (ownership and key checks unchanged) whose reads come from the live database (GET only) with this run's own
    writes overlaid. Without `live` it is the DryRunWriter itself (an empty previous state: a local seal, never a hand-off)."""

    def __init__(self, dry, live: LiveReadOnly | None = None):
        self.dry, self.live = dry, live

    @property
    def patches(self) -> list:
        return self.dry.patches

    def patch(self, updates: dict) -> None:
        self.dry.patch(updates)

    def get(self, path: str):
        if self.live is None:
            return self.dry.get(path)
        return overlay(self.live.get(path), path, self.dry.patches)

    def flat(self) -> dict:
        out = {}
        for p in self.dry.patches:
            out.update(p)
        return out


def _live(url: str, brain_id: str) -> LiveReadOnly:
    from .rtdb import BrainRtdb, TokenProvider
    return LiveReadOnly(BrainRtdb(url, TokenProvider(), brain_id=brain_id))


def main(argv, *, brain_id: str, write_intent_env: str, require_approved: Callable[[], object], new_dry_writer: Callable[[], object],
         produce: Callable[[ReadThroughWriter, dt.datetime, argparse.Namespace], dict], seal: Callable[[dict, dict], object],
         add_args: Callable[[argparse.ArgumentParser], None] | None = None,
         preflight: Callable[[argparse.Namespace], str | None] | None = None, live_factory: Callable[[str, str], LiveReadOnly] | None = None,
         now: dt.datetime | None = None) -> int:
    """`require_approved()` raises (a KnowledgeReleaseError) unless the verified release is APPROVED; `produce(writer, now, a)` runs the Brain's
    unchanged publish step into `writer` and returns its report; `seal(updates, ctx)` returns the Brain's BuildResult for ctx
    {generated_at, execution_id, code_version}. `preflight(a)` returns a refusal reason or None. `live_factory`/`now` are for tests."""
    from .knowledge_release import KnowledgeReleaseError
    from .rtdb import BRAIN_RTDB_URL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artifact-dir", required=True, help="a LOCAL artifact store (create-only)")
    ap.add_argument("--emit", default=None, help="also write the sealed artifact JSON to this new LOCAL file (the runner's hand-off)")
    ap.add_argument("--read-rtdb", action="store_true", help="read the previous state from the LIVE Brain database (GET only, BRAIN_ACCESS_TOKEN)")
    ap.add_argument("--rtdb-url", default=None, help=f"with --read-rtdb: the Brain database (default {BRAIN_RTDB_URL})")
    ap.add_argument("--execution-id", default=None, help="UUIDv4 of this run (default: a new one)")
    if add_args:
        add_args(ap)
    a = ap.parse_args(argv)

    def refuse(why: str, code: int = 2) -> int:
        print(f"REFUSED (nothing stored): {why}", file=sys.stderr)
        return code

    if not (a.artifact_dir or "").strip() or a.artifact_dir.startswith("gs://"):
        return refuse("--artifact-dir is a local folder")
    emit = (a.emit or "").strip()
    if emit and (emit.startswith("gs://") or os.path.exists(emit)):
        return refuse("--emit is a new local file (an earlier hand-off is never overwritten)")
    if emit and not a.read_rtdb:
        return refuse("a hand-off (--emit) needs --read-rtdb: the previous state must come from what is live")
    if a.rtdb_url and not a.read_rtdb:
        return refuse("--rtdb-url needs --read-rtdb")
    try:
        execution_id = str(uuid.UUID(a.execution_id, version=4)) if a.execution_id else str(uuid.uuid4())
    except ValueError:
        return refuse("--execution-id is not a UUID")
    try:
        require_approved()                                       # gate (a): the verified knowledge release is APPROVED
    except KnowledgeReleaseError as e:
        return refuse(f"{e}" if BLOCKED in str(e) else f"{BLOCKED}: {e}")
    if os.environ.get(write_intent_env) != "1":                 # gate (b): operator intent, as for run.py --write
        return refuse(f"needs {write_intent_env}=1 (operator intent; owner approval of the first {brain_id} write)", 3)
    why = preflight(a) if preflight else None
    if why:
        return refuse(why)

    now = (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0)
    live = (live_factory or _live)(a.rtdb_url or BRAIN_RTDB_URL, brain_id) if a.read_rtdb else None
    writer = ReadThroughWriter(new_dry_writer(), live)
    report = produce(writer, now, a)
    built = seal(writer.flat(), {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "execution_id": execution_id,
                                 "code_version": f"{brain_id}@{os.environ.get('SECTOR_ENGINE_COMMIT', 'unknown')}"[:40]})
    print(json.dumps({"report": report, "liveReads": live.reads if live else 0}, default=str)[:4000])
    if not getattr(built, "artifact", None):
        print("FAILED (nothing stored): the run produced no artifact", file=sys.stderr)
        return 4
    from .publisher.handoff import ArtifactWriter
    from .publisher.storage import LocalDirObjectStore
    ref = ArtifactWriter(LocalDirObjectStore(a.artifact_dir), brain_id).write(built.artifact)
    if emit:
        with open(emit, "x") as fh:                              # never overwrites an earlier hand-off
            json.dump(built.artifact, fh, sort_keys=True)
    print(json.dumps({"artifactId": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "executionId": ref.execution_id,
                      "artifactSchema": ref.expected_schema, "dropped": len(getattr(built, "dropped", []) or []),
                      "deletes": len(getattr(built, "deletes", []) or [])}, sort_keys=True))
    return 0
