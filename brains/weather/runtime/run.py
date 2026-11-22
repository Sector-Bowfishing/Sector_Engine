#!/usr/bin/env python3
"""Weather Brain entry point.

  PYTHONPATH=../../../jobs/brain_platform python3 run.py --dry-run OUT.json [--lakes 'Guntersville|AL,...'] [--limit N]
        [--directory lakes.json | --engine URL] [--point-cache FILE] [--published FILE] [--now ISO]

--dry-run reads the public lake directory and the public NWS API (read-only) and writes the Brain's write set to OUT.json through the
platform's in-memory store (ownership checks included). Nothing is written to any database.
--write is REFUSED (exit 2): this version has no live writer. Enabling it is a separate owner step (WEATHER_BRAIN_PLAN.md section 6).
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone

from sector_weather import contract as C
from sector_weather.client import LiveSource, PointCache
from sector_weather.publish import run

ENGINE_URL = "https://sector-engine-e43utajroa-uc.a.run.app"


def fetch_directory(url: str) -> list[dict]:
    req = urllib.request.Request(f"{url}/lakes", headers={"User-Agent": "sector-weather-brain/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.loads(r.read())
    lakes = body.get("lakes") or []
    if not lakes or body.get("count") != len(lakes):
        raise SystemExit(f"lake directory malformed: count={body.get('count')} lakes={len(lakes)}")
    return lakes


def dry_run_store():
    from sector_brain_platform import DryRunStore
    return DryRunStore({}, brain_id=C.BRAIN_ID)


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
        print("REFUSED: the Weather Brain has no live writer in this version; live publication is a separate owner step "
              "(WEATHER_BRAIN_PLAN.md section 6). Nothing was written.", file=sys.stderr)
        return 2
    directory = json.load(open(a.directory))["lakes"] if a.directory else fetch_directory(a.engine)
    ids = [x for x in a.lakes.split(",") if x] or None
    if a.limit and not ids:
        ids = [l["id"] for l in directory[: a.limit]]
    now = datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else datetime.now(timezone.utc)
    published = json.load(open(a.published)) if a.published else {}
    cache = PointCache(a.point_cache)
    src = LiveSource()
    out = run(directory, src, cache, published, now, ids)
    cache.save()
    store = dry_run_store()
    store.update(out["updates"])
    store.dump(a.dry_run)
    print(json.dumps({"ok": not out["errors"], "lakes": len(out["states"]), "readiness": {r: list(out["readiness"].values()).count(r) for r in set(out["readiness"].values())},
                      "errors": out["errors"][:5], "requests": src.http.requests, "dryRunFile": a.dry_run}, indent=1))
    return 0 if not out["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
