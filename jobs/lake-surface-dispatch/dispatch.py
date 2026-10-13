#!/usr/bin/env python3
"""lake-surface-dispatch — the cheap daily satellite discovery job (cost work 2026-10-13, Phase 8).

For every lake outline, ask the STAC catalog (metadata only, no imagery) for the newest Sentinel-2 pass in
the lookback window and compare it with the date already published in the bucket's latest.json. Lakes with a
newer usable pass form the WORK SET; only then is the heavy `lake-surface-daily` job started — for those lakes
only (`--lakes a,b,c` container-arg override) and with as many tasks as the work needs, never 8 × 4 vCPU × 16 Gi
for 621 lakes that have nothing new.

  python3 dispatch.py --dry-run                 discover, print the work set, start nothing
  python3 dispatch.py --dry-run --lakes "Guntersville|AL,Wheeler|AL"
  python3 dispatch.py                           discover and start lake-surface-daily when there is work

env: BUCKET (default sector-lake-surface), POLYGONS (default polygons.geojson.gz next to this file), HEAVY_JOB
     (default lake-surface-daily), MAX_TASKS (default 8), LAKES_PER_TASK (default 12), WORKERS (default 8),
     LOOKBACK_DAYS (default 14), MAX_CLOUD (default 40)

The same decision rules as daily.process(): a pass counts when its cloud cover ≤ MAX_CLOUD and it is within
LOOKBACK_DAYS; a lake is work when that pass date is newer than latest.json.summary.date (or nothing is published).
daily.py keeps its own "up to date" check, so dispatching a lake twice is safe, only wasteful.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                   # vendored sector_brain_platform (deploy) …
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))   # … or the repo copy
from sector_brain_platform import TokenProvider            # noqa: E402
from sector_brain_platform.gcp import run_job              # noqa: E402

ES_SEARCH = "https://earth-search.aws.element84.com/v1/search"
S2_COLLECTION = "sentinel-2-c1-l2a"
BUCKET = os.environ.get("BUCKET", "sector-lake-surface")
POLYGONS = os.environ.get("POLYGONS", os.path.join(HERE, "polygons.geojson.gz"))
HEAVY_JOB = os.environ.get("HEAVY_JOB", "lake-surface-daily")
MAX_TASKS = int(os.environ.get("MAX_TASKS", "8"))
LAKES_PER_TASK = int(os.environ.get("LAKES_PER_TASK", "12"))
WORKERS = int(os.environ.get("WORKERS", "8"))
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "14"))
MAX_CLOUD = float(os.environ.get("MAX_CLOUD", "40"))
PUBLIC = f"https://storage.googleapis.com/{BUCKET}"


def slug(lake_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id).strip("_")


def bbox_of(geometry: dict) -> list[float]:
    rings = geometry["coordinates"] if geometry["type"] == "Polygon" else [r for poly in geometry["coordinates"] for r in poly]
    xs = [c[0] for r in rings for c in r]
    ys = [c[1] for r in rings for c in r]
    return [min(xs), min(ys), max(xs), max(ys)]


def load_polygons(path: str = POLYGONS) -> dict[str, dict]:
    with (gzip.open if path.endswith(".gz") else open)(path, "rt") as fh:
        return {f["properties"]["id"]: f["geometry"] for f in json.load(fh)["features"] if f.get("geometry")}


def _post(url: str, body: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get_json(url: str, timeout: float = 20) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def newest_pass_date(bbox: list[float], until: dt.datetime, post=None) -> str | None:
    """Newest Sentinel-2 pass day over `bbox` within LOOKBACK_DAYS whose least-cloudy tile is ≤ MAX_CLOUD. Metadata only."""
    post = post or _post                                  # resolved at call time so tests can stub the module function
    since = (until - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    body = {"collections": [S2_COLLECTION], "bbox": bbox, "datetime": f"{since}/{until.strftime('%Y-%m-%dT23:59:59Z')}", "limit": 200,
            "fields": {"include": ["properties.datetime", "properties.platform", "properties.eo:cloud_cover"], "exclude": ["assets", "links", "geometry"]},
            "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
    by: dict[tuple[str, str], list[float]] = {}
    for f in post(ES_SEARCH, body).get("features") or []:
        p = f.get("properties") or {}
        key = (p.get("datetime", "")[:10], p.get("platform", ""))
        by.setdefault(key, []).append(float(p.get("eo:cloud_cover", 0)))
    fresh = [d for (d, _), cc in by.items() if min(cc) <= MAX_CLOUD and (until.date() - dt.date.fromisoformat(d)).days <= LOOKBACK_DAYS]
    return max(fresh) if fresh else None


def published_date(lake_id: str, get=None) -> str | None:
    get = get or _get_json
    latest = get(f"{PUBLIC}/lakes/{slug(lake_id)}/clarity/latest.json") or {}
    return (latest.get("summary") or {}).get("date")


def decide(lake_id: str, geometry: dict, until: dt.datetime, post=None, get=None) -> dict:
    newest = newest_pass_date(bbox_of(geometry), until, post)
    held = published_date(lake_id, get)
    if newest is None:
        return {"lakeId": lake_id, "work": False, "why": "no usable pass in the window", "published": held}
    if held and held >= newest:
        return {"lakeId": lake_id, "work": False, "why": "up to date", "published": held, "newestPass": newest}
    return {"lakeId": lake_id, "work": True, "why": "newer pass" if held else "nothing published yet", "published": held, "newestPass": newest}


def discover(polys: dict[str, dict], until: dt.datetime, workers: int = WORKERS, post=None, get=None) -> dict:
    out, errors = {}, {}
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(decide, lid, g, until, post, get): lid for lid, g in polys.items()}
        for f in cf.as_completed(futs):
            lid = futs[f]
            try:
                out[lid] = f.result()
            except Exception as e:                           # one lake's STAC/HTTP error never hides the others
                errors[lid] = repr(e)[:200]
    return {"decisions": out, "errors": errors}


def task_count(n_lakes: int, lakes_per_task: int = LAKES_PER_TASK, max_tasks: int = MAX_TASKS) -> int:
    return max(1, min(max_tasks, math.ceil(n_lakes / max(1, lakes_per_task))))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="discover only; never start the heavy job")
    ap.add_argument("--lakes", default=None, help="comma-separated lake ids to consider (default: every outline)")
    ap.add_argument("--until", default=None, help="ISO date/time (default: now, UTC)")
    ap.add_argument("--no-summary", action="store_true", help="do not write dispatch/<date>.json to the bucket")
    a = ap.parse_args(argv)
    until = dt.datetime.fromisoformat(a.until).replace(tzinfo=None) if a.until else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    polys = load_polygons()
    if a.lakes:
        want = set(a.lakes.split(","))
        polys = {k: v for k, v in polys.items() if k in want}
    t0 = time.time()
    res = discover(polys, until)
    work = sorted(l for l, d in res["decisions"].items() if d["work"])
    why = {}
    for d in res["decisions"].values():
        why[d["why"]] = why.get(d["why"], 0) + 1
    summary = {"until": until.isoformat() + "Z", "lakes": len(polys), "work": work, "workCount": len(work), "outcomes": why,
               "errors": res["errors"], "discoverySeconds": round(time.time() - t0, 1), "dryRun": a.dry_run, "heavyJob": HEAVY_JOB}
    print(json.dumps({k: v for k, v in summary.items() if k != "work"}, indent=1), flush=True)
    print("work set:", ", ".join(work) if work else "(none)", flush=True)
    started = None
    if work and not a.dry_run:
        tasks = task_count(len(work))
        op = run_job(TokenProvider(), HEAVY_JOB, args=["--lakes", ",".join(work)], task_count=tasks)
        started = {"execution": (op.get("metadata") or {}).get("name"), "tasks": tasks, "lakes": len(work)}
        print(f"started {HEAVY_JOB}: {started}", flush=True)
    summary["started"] = started
    if not a.no_summary and (os.environ.get("CLOUD_RUN_JOB") or os.environ.get("DISPATCH_WRITE_SUMMARY")):
        _write_summary(summary, until)
    return 0


def _write_summary(summary: dict, until: dt.datetime) -> None:
    """dispatch/<date>.json in the bucket (public bucket; the summary holds lake ids and counts only)."""
    tokens = TokenProvider()
    name = f"dispatch/{until.date().isoformat()}.json"
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o?uploadType=media&name={urllib.parse.quote(name, safe='')}"
    req = urllib.request.Request(url, data=json.dumps(summary, separators=(",", ":")).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tokens.token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()


if __name__ == "__main__":
    sys.exit(main())
