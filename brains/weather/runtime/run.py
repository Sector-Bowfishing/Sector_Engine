#!/usr/bin/env python3
"""Weather Brain entry point.

  PYTHONPATH=../../../jobs/brain_platform python3 run.py --dry-run OUT.json [--lakes 'Guntersville|AL,...'] [--limit N]
        [--directory lakes.json | --engine URL] [--point-cache FILE] [--published FILE] [--now ISO]

--dry-run reads the public lake directory and the public NWS API (read-only) and writes the Brain's write set to OUT.json through the
platform's in-memory store (ownership checks included). Nothing is written to any database.
  python3 run.py --write [--point-cache FILE]
--write applies the SAME write set to the Brain RTDB ($BRAIN_RTDB_URL, sector-brain only) through sector_weather.writer.RtdbWriter, over the
whole directory, reading each lake's last published state for the planner (GET). It REFUSES unless BOTH hold:
  (a) the verified knowledge release is APPROVED (else exit 2, BLOCKED_AWAITING_APPROVED_RELEASE), and
  (b) WEATHER_WRITE_APPROVED=1 is set (operator intent; else exit 3).
Dry-run inputs (--directory, --published, --now, --lakes, --limit) are refused with --write (exit 3): files never feed a real write.
--point-cache FILE (default $SECTOR_WEATHER_POINT_CACHE) keeps the /points -> gridpoint/stations resolution between runs (client.PointCache,
30 days, revalidated on 404/redirect). It must be outside the repository checkout (exit 2 otherwise): it is runtime data, never committed.
The Brain is registered DISABLED (control manifest PARKED, executionTarget none, absent from the execution control): nothing starts it.
Turning it on is the owner checklist in WEATHER_BRAIN_PLAN.md section 6.1.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))       # the job image runs run.py beside its packages (deploy/deploy-job.sh)
from sector_weather import contract as C, knowledge as K  # noqa: E402
from sector_weather.client import LiveSource, PointCache, default_point_cache_path  # noqa: E402
from sector_weather.publish import LIVE_MODE, run  # noqa: E402

ENGINE_URL = "https://sector-engine-e43utajroa-uc.a.run.app"
RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
WRITE_INTENT_ENV = "WEATHER_WRITE_APPROVED"
DRY_RUN_ONLY = ("directory", "published", "now", "lakes", "limit")


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def point_cache_path(given: str | None) -> str | None:
    """The cache file to use (--point-cache, else $SECTOR_WEATHER_POINT_CACHE), refused (SystemExit 2) inside the repository checkout."""
    path = default_point_cache_path(given)
    if path and os.path.exists(os.path.join(REPO_ROOT, ".git")):            # a checkout (a job image has no .git: nothing to protect there)
        root = os.path.realpath(REPO_ROOT)
        if os.path.commonpath([os.path.realpath(path), root]) == root:
            print("REFUSED (nothing read or written): the point cache must be outside the repository checkout (runtime data, never committed)",
                  file=sys.stderr)
            raise SystemExit(2)
    return path


def cache_report(cache: PointCache) -> dict:
    return {**cache.stats, "file": "configured" if cache.path else "none", **({"loadError": cache.load_error} if cache.load_error else {})}


def fetch_directory(url: str) -> list[dict]:
    req = urllib.request.Request(f"{url}/lakes", headers={"User-Agent": "sector-weather-brain/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.loads(r.read())
    lakes = body.get("lakes") or []
    if not lakes or body.get("count") != len(lakes):
        raise SystemExit(f"lake directory malformed: count={body.get('count')} lakes={len(lakes)}")
    return lakes


def dry_run_store():
    from sector_weather.writer import DryRunWriter
    return DryRunWriter()


def read_published(writer, directory: list[dict]) -> dict:
    """lakeId -> the last published Weather state (GET /lakes/{k}/states/weather), for the per-lake planner. Absent stays absent."""
    out = {}
    for lake in directory:
        st = writer.get(f"lakes/{C.lake_key(lake['id'])}/states/{C.SLOT}")
        if isinstance(st, dict):
            out[lake["id"]] = st
    return out


def write_gate(a) -> int:
    """0 when a live write may proceed; else the refusal exit code (message on stderr). Order: release approval, then operator intent."""
    K.require_approved(C.RELEASE)                                       # unapproved -> KnowledgeNotApproved (exit 2, BLOCKED)
    if os.environ.get(WRITE_INTENT_ENV) != "1":
        print(f"refusing: --write needs {WRITE_INTENT_ENV}=1 (operator intent; owner approval of the first Weather write)", file=sys.stderr)
        return 3
    given = [o for o in DRY_RUN_ONLY if getattr(a, o)]
    if given:
        print(f"refusing: {', '.join('--' + o for o in given)} are dry-run options; a live write runs over the whole directory", file=sys.stderr)
        return 3
    return 0


def live_write(a) -> int:
    from sector_weather.writer import RtdbWriter
    writer = RtdbWriter(RTDB_URL)
    directory = fetch_directory(a.engine)
    now = datetime.now(timezone.utc)
    published = read_published(writer, directory)
    cache = PointCache(point_cache_path(a.point_cache))
    src = LiveSource()
    out = run(directory, src, cache, published, now, None, publish_mode=LIVE_MODE)
    cache.save()
    writer.patch(out["updates"])
    print(json.dumps({"ok": not out["errors"], "lakes": len(out["states"]), "writes": len(out["updates"]),
                      "readiness": {r: list(out["readiness"].values()).count(r) for r in set(out["readiness"].values())},
                      "errors": out["errors"][:5], "requests": src.http.requests, "pointCache": cache_report(cache),
                      "knowledgeRelease": C.RELEASE["releaseId"], "published": True}, indent=1))
    return 0 if not out["errors"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", metavar="OUT.json")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--lakes", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--directory")
    ap.add_argument("--engine", default=ENGINE_URL)
    ap.add_argument("--point-cache")
    ap.add_argument("--published")
    ap.add_argument("--now")
    a = ap.parse_args(argv)
    if a.write:
        rc = write_gate(a)
        return rc or live_write(a)
    directory = json.load(open(a.directory))["lakes"] if a.directory else fetch_directory(a.engine)
    ids = [x for x in a.lakes.split(",") if x] or None
    if a.limit and not ids:
        ids = [l["id"] for l in directory[: a.limit]]
    now = datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else datetime.now(timezone.utc)
    published = json.load(open(a.published)) if a.published else {}
    cache = PointCache(point_cache_path(a.point_cache))
    src = LiveSource()
    out = run(directory, src, cache, published, now, ids)
    cache.save()
    store = dry_run_store()
    store.patch(out["updates"])
    store.dump(a.dry_run)
    print(json.dumps({"ok": not out["errors"], "lakes": len(out["states"]), "readiness": {r: list(out["readiness"].values()).count(r) for r in set(out["readiness"].values())},
                      "errors": out["errors"][:5], "requests": src.http.requests, "pointCache": cache_report(cache), "dryRunFile": a.dry_run}, indent=1))
    return 0 if not out["errors"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except K.KnowledgeReleaseError as e:                                # includes KnowledgeNotApproved
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
