#!/usr/bin/env python3
"""Weather Brain artifact mode for a runner's lease cycle (runner catalog entry `weather-central`; prepared, OFF: the catalog entry is disabled, the Brain is
PARKED and absent from the execution control).

The same steps as `run.py --write`, with the database writer replaced by the Brain's DryRunWriter (sector_brain_platform.python_artifact_entry):
the whole lake directory, each lake's last published state read from the LIVE Brain database (GET only, --read-rtdb), the unchanged `publish.run`,
then ONE sealed `weather-publication-v1` artifact (publish_artifact.build_artifact) stored create-only in --artifact-dir and, with --emit, handed
off as a local file. No database or bucket write.

  python artifact_entry.py --artifact-dir DIR --emit FILE --read-rtdb [--point-cache FILE] [--engine URL]

Gates (as run.py --write): an APPROVED knowledge release (else exit 2) AND WEATHER_WRITE_APPROVED=1 (else exit 3). The NWS contact User-Agent
(SECTOR_WEATHER_USER_AGENT) is required (exit 2): it is runner configuration, never in the repository.
--point-cache (default $SECTOR_WEATHER_POINT_CACHE): the durable /points cache, outside the checkout (client.PointCache).
Exit codes: python_artifact_entry (0 stored, 2 refused, 3 operator intent missing, 4 no artifact)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"), HERE):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

import run as R  # noqa: E402  (the CLI module beside this file: directory, previous-state read, cache path)
from sector_brain_platform import python_artifact_entry as E  # noqa: E402
from sector_weather import contract as C, knowledge as K, publish_artifact as PA  # noqa: E402
from sector_weather.client import LiveSource, PointCache  # noqa: E402
from sector_weather.publish import run  # noqa: E402
from sector_weather.writer import DryRunWriter  # noqa: E402

CENTRAL_MODE = "CENTRAL: sealed artifact for the Publisher (runner hand-off; internal CALIBRATION only)"


def main(argv=None, *, source=None, directory=None, live_factory=None, now=None) -> int:
    """source/directory/live_factory/now: test seams (a fixture NWS source, a lake list, a fake live database, a pinned clock)."""
    def add_args(ap):
        ap.add_argument("--point-cache", default=None)
        ap.add_argument("--engine", default=R.ENGINE_URL)

    def preflight(a):
        if source is None and not os.environ.get("SECTOR_WEATHER_USER_AGENT"):
            return "SECTOR_WEATHER_USER_AGENT (the NWS contact User-Agent, see NWS_PROVIDER.md) is required"
        return None

    def produce(writer, t, a):
        lakes = directory if directory is not None else R.fetch_directory(a.engine)
        published = R.read_published(writer, lakes)
        cache = PointCache(R.point_cache_path(a.point_cache))
        src = source or LiveSource()
        out = run(lakes, src, cache, published, t, None, publish_mode=CENTRAL_MODE)
        cache.save()
        writer.patch(out["updates"])
        return {"ok": not out["errors"], "lakes": len(out["states"]), "writes": len(out["updates"]), "errors": out["errors"][:5],
                "requests": getattr(getattr(src, "http", None), "requests", None), "pointCache": R.cache_report(cache)}

    def seal(updates, ctx):
        return PA.build_artifact(updates, PA.BuildContext(ctx["generated_at"], ctx["execution_id"], ctx["code_version"], lifecycle=PA.LIFECYCLE),
                                 release_lineage=K.lineage_triple(C.RELEASE))

    return E.main(argv, brain_id=C.BRAIN_ID, write_intent_env=R.WRITE_INTENT_ENV, require_approved=lambda: K.require_approved(C.RELEASE),
                  new_dry_writer=DryRunWriter, produce=produce, seal=seal, add_args=add_args, preflight=preflight, live_factory=live_factory,
                  now=now)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except K.KnowledgeReleaseError as e:
        print(f"REFUSED (nothing stored): {e}", file=sys.stderr)
        sys.exit(2)
