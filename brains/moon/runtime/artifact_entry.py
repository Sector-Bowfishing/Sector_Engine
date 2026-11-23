#!/usr/bin/env python3
"""Moon and Night Light Brain artifact mode for a runner's lease cycle (runner catalog entry `moon-central`; prepared, OFF: the catalog entry is
disabled, the Brain is PARKED and absent from the execution control).

The same steps as `run.py --write`, with the database writer replaced by the Brain's DryRunWriter (sector_brain_platform.python_artifact_entry):
every directory lake, each lake's published Weather state read from the LIVE Brain database (GET only, --read-rtdb; used only within
WEATHER_MAX_AGE_HOURS), the unchanged `publish`, then ONE sealed `moon-publication-v1` artifact stored create-only and, with --emit, handed off.

Weather edge (control manifest: OPTIONAL, maxAgeHours 3, deferIfUpstreamStarted false): this entry never waits for a Weather run. It reads
Weather's LAST COMPLETED published states, so a Weather run that is still in flight cannot hold Moon back; a lake whose Weather state is absent or
older than 3 h gets the labelled moon-only answer. When it runs is the Orchestrator's grant (after each completed Weather run), not this file's.

  python artifact_entry.py --artifact-dir DIR --emit FILE --read-rtdb

Gates (as run.py --write): an APPROVED knowledge release (else exit 2) AND MOON_WRITE_APPROVED=1 (else exit 3).
Exit codes: python_artifact_entry (0 stored, 2 refused, 3 operator intent missing, 4 no artifact)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

import run as R  # noqa: E402  (the CLI module beside this file: the Weather read and the write-intent name)
from moon_brain import contract as C, lakes as L, publish_artifact as PA  # noqa: E402
from moon_brain.publish import publish  # noqa: E402
from moon_brain.writer import DryRunWriter  # noqa: E402
from sector_brain_platform import python_artifact_entry as E  # noqa: E402

CENTRAL_MODE = "central: sealed artifact for the Publisher (runner hand-off; internal CALIBRATION only)"


def main(argv=None, *, live_factory=None, now=None) -> int:
    d = L.load()                                                       # verify first: missing/tampered -> LakeRegistryError (exit 2)

    def produce(writer, t, a):
        weather, wc = R.read_weather(writer, d, t)                     # last completed Weather states only (deferIfUpstreamStarted false)
        rep = publish(d, writer, None, weather, now=t, publish_mode=CENTRAL_MODE)
        return {**{k: rep.get(k) for k in ("ok", "evaluated", "skippedUnchanged", "readinessCounts", "basis", "errors", "writes")}, "weatherInput": wc}

    def seal(updates, ctx):
        return PA.build_artifact(updates, PA.BuildContext(ctx["generated_at"], ctx["execution_id"], ctx["code_version"], lifecycle=PA.LIFECYCLE),
                                 release_lineage=L.lineage())

    return E.main(argv, brain_id=C.BRAIN_ID, write_intent_env=R.WRITE_INTENT_ENV, require_approved=lambda: L.require_approved(d),
                  new_dry_writer=DryRunWriter, produce=produce, seal=seal, live_factory=live_factory, now=now)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except L.LakeRegistryError as e:
        print(f"REFUSED (nothing stored): {e}", file=sys.stderr)
        sys.exit(2)
