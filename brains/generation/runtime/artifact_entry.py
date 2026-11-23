#!/usr/bin/env python3
"""Generation Brain artifact mode for a runner's lease cycle (runner catalog entry `generation-central`; prepared, OFF: the catalog entry is disabled, the
Brain is PARKED and absent from the execution control, and enablement is also blocked on D-G and D-I in GENERATION_BRAIN_PLAN.md section 7).

The same steps as `run.py --write`, with the database writer replaced by the Brain's DryRunWriter (sector_brain_platform.python_artifact_entry):
the bound dams of the verified release, each lake's last published state read from the LIVE Brain database (GET only, --read-rtdb) so only dams
whose nextCheckAt is reached are read, the unchanged `publish`, then ONE sealed `generation-publication-v1` artifact stored create-only and, with
--emit, handed off. Official sources only, through generation_brain.http (access-gated, at most one read per URL per run).

  python artifact_entry.py --artifact-dir DIR --emit FILE --read-rtdb

Gates (as run.py --write): an APPROVED knowledge release (else exit 2) AND GENERATION_WRITE_APPROVED=1 (else exit 3).
Exit codes: python_artifact_entry (0 stored, 2 refused, 3 operator intent missing, 4 no artifact)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

import generation_brain  # noqa: E402,F401  (bootstraps the platform path)
from generation_brain import contract as C, knowledge as K, publish_artifact as PA  # noqa: E402
from generation_brain.http import Fetcher  # noqa: E402
from generation_brain.publish import publish  # noqa: E402
from generation_brain.writer import DryRunWriter  # noqa: E402
from sector_brain_platform import python_artifact_entry as E  # noqa: E402

WRITE_INTENT_ENV = "GENERATION_WRITE_APPROVED"                           # == run.py --write (tested)
CENTRAL_MODE = "central: sealed artifact for the Publisher (runner hand-off; internal CALIBRATION only)"


def main(argv=None, *, transport=None, sleep=None, live_factory=None, now=None) -> int:
    """transport/sleep/live_factory/now: test seams (a fixture transport, no retry wait, a fake live database, a pinned clock)."""
    k = K.load()                                                       # verify first: missing/tampered -> KnowledgeReleaseError (exit 2)

    def produce(writer, t, a):
        seams = {**({"transport": transport} if transport else {}), **({"sleep": sleep} if sleep else {})}
        fetcher = Fetcher(k.access(), **seams, log=lambda s: print(s, file=sys.stderr))
        rep = publish(k.catalog(), k.access(), fetcher, writer, t, scope="bound", release=k.summary(), mode=CENTRAL_MODE)
        return {k_: rep.get(k_) for k_ in ("ok", "evaluated", "notDue", "changed", "unavailable", "readinessCounts", "requests", "errors", "writes")}

    def seal(updates, ctx):
        return PA.build_artifact(updates, PA.BuildContext(ctx["generated_at"], ctx["execution_id"], ctx["code_version"], lifecycle=PA.LIFECYCLE),
                                 knowledge=k)

    return E.main(argv, brain_id=C.BRAIN_ID, write_intent_env=WRITE_INTENT_ENV, require_approved=lambda: K.require_approved(k),
                  new_dry_writer=DryRunWriter, produce=produce, seal=seal, live_factory=live_factory, now=now)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except K.KnowledgeReleaseError as e:
        print(f"REFUSED (nothing stored): {e}", file=sys.stderr)
        sys.exit(2)
