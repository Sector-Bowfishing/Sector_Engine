"""Water Clarity Brain run: production Clarity -> Brain RTDB (sector-brain).

Reads only what production already publishes (Engine /lakes, Engine
/conditions, the public gs://sector-lake-surface bucket, Cloud Run job status)
and writes only Water Clarity's Brain RTDB paths. It is a separate process
from every production Clarity path, so a Brain RTDB outage, a bad payload or
a crash here cannot change what customers see.

usage:
  python run.py --dry-run --out /tmp/wcb                 # build everything, write JSON files, no RTDB
  python run.py --lakes "Guntersville|AL,Wheeler|AL"     # publish a few lakes
  python run.py                                          # publish the whole directory
env:
  ENGINE_URL (default prod Cloud Run URL), BRAIN_RTDB_URL (default sector-brain),
  ENGINE_REVISION (else read from Cloud Run), POLYGONS (lake-surface outlines),
  BRAIN_TOKEN_MODE metadata|gcloud, GCP_PROJECT (sector-9393c), GCP_REGION (us-central1)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brain_platform as bp            # noqa: E402
import clarity_brain as cb             # noqa: E402

ENGINE_URL = os.environ.get("ENGINE_URL", "https://sector-engine-e43utajroa-uc.a.run.app")
PROJECT = os.environ.get("GCP_PROJECT", "sector-9393c")
REGION = os.environ.get("GCP_REGION", "us-central1")
_HERE = os.path.dirname(os.path.abspath(__file__))
POLYGONS = os.environ.get("POLYGONS") or next(       # in the image: copied beside run.py; in the repo: the lake-surface job's copy
    (p for p in (os.path.join(_HERE, "polygons.geojson.gz"), os.path.join(_HERE, "..", "lake-surface", "polygons.geojson.gz")) if os.path.exists(p)),
    os.path.join(_HERE, "polygons.geojson.gz"))
STORAGE_API = "https://storage.googleapis.com/storage/v1/b/sector-lake-surface/o"


def http_json(url: str, timeout: float = 30, retries: int = 1, headers: dict | None = None):
    """GET JSON; None on 404; raises on anything else after retries."""
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
            if 400 <= e.code < 500 and e.code != 429:
                break
        except Exception as e:      # timeouts, resets
            last = e
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    raise last


# ---------------------------------------------------------------- inputs
def load_directory() -> list[dict]:
    d = http_json(f"{ENGINE_URL}/lakes", timeout=60, retries=2)
    lakes = d["lakes"]
    if len(lakes) < 100:
        raise RuntimeError(f"lake directory has only {len(lakes)} lakes; refusing to publish a partial fleet")
    return lakes


def polygon_ids() -> set[str]:
    with (gzip.open if POLYGONS.endswith(".gz") else open)(POLYGONS, "rt") as fh:
        return {f["properties"]["id"] for f in json.load(fh)["features"] if f.get("geometry")}


def bucket_lake(lake_id: str) -> dict:
    """latest.json, the pass metadata and the pass count for one lake (public reads)."""
    key = f"{cb.BUCKET_URL}/lakes/{bp.lake_key(lake_id)}/clarity"
    latest = http_json(f"{key}/latest.json", timeout=20)
    meta = hist = None
    if latest and (latest.get("files") or {}).get("meta"):
        meta = http_json(f"{cb.BUCKET_URL}/{latest['files']['meta']}", timeout=30)
        hist = http_json(f"{key}/history.json", timeout=20)
    return {"latest": latest, "meta": meta, "passCount": len(hist["passes"]) if hist and "passes" in hist else None}


def engine_conditions(lake: dict) -> dict:
    q = urllib.parse.urlencode({"lat": lake["lat"], "lon": lake["lon"]})
    return http_json(f"{ENGINE_URL}/conditions?{q}", timeout=60, retries=1)


def lake_surface_run(now: dt.datetime) -> dict | None:
    """The newest lake-surface-daily run, from the job's own run records in the bucket."""
    for back in range(0, 3):
        day = (now - dt.timedelta(days=back)).date().isoformat()
        listing = http_json(f"{STORAGE_API}?prefix=runs/{day}-task&fields=items(name,updated)", timeout=20) or {}
        items = listing.get("items") or []
        if not items:
            continue
        outcome = {"published": 0, "upToDate": 0, "noUsablePass": 0, "noPassInWindow": 0, "error": 0}
        for it in items:
            rec = http_json(f"{cb.BUCKET_URL}/{it['name']}", timeout=30) or {}
            for v in (rec.get("results") or {}).values():
                outcome[cb.lake_surface_outcome(v.get("status"))] += 1
        return {"day": day, "tasks": len(items), "lakes": sum(outcome.values()), "errors": outcome["error"],
                "outcomes": outcome, "finishedAt": max(it["updated"] for it in items)}
    return None


def google_api(url: str, tokens: bp.TokenProvider):
    try:
        return http_json(url, timeout=20, headers={"Authorization": f"Bearer {tokens.token()}"})
    except Exception as e:
        return {"_error": str(e)[:200]}


def engine_revision(tokens: bp.TokenProvider) -> str | None:
    if os.environ.get("ENGINE_REVISION"):
        return os.environ["ENGINE_REVISION"]
    s = google_api(f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/services/sector-engine", tokens) or {}
    live = [t.get("revision") for t in s.get("trafficStatuses") or [] if t.get("percent") == 100]
    return live[0] if live else None


def job_health(job_id: str, meta: dict, tokens: bp.TokenProvider) -> dict:
    base = {"displayName": meta["displayName"], "kind": meta["kind"], "schedule": meta.get("schedule"),
            "processingPathId": meta.get("processingPathId"), "brainId": cb.BRAIN_ID, "status": "UNKNOWN", "lastRun": None, "lastSuccess": None, "durationMs": None, "latestError": None, "running": False}
    ex = google_api(f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/jobs/{job_id}/executions?pageSize=10", tokens)
    sch = google_api(f"https://cloudscheduler.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/jobs/{job_id}", tokens)
    if "_error" in (ex or {}):
        base["latestError"] = "status unreadable: " + ex["_error"]
        return base
    runs = sorted((ex or {}).get("executions") or [], key=lambda e: e.get("createTime", ""), reverse=True)
    if runs:
        r0 = runs[0]
        base["lastRun"] = r0.get("startTime") or r0.get("createTime")
        base["running"] = not r0.get("completionTime")
        ok = [r for r in runs if r.get("completionTime") and r.get("succeededCount") and not r.get("failedCount")]
        if ok:
            base["lastSuccess"] = ok[0]["completionTime"]
            s, c = bp.parse_time(ok[0].get("startTime")), bp.parse_time(ok[0].get("completionTime"))
            base["durationMs"] = int((c - s).total_seconds() * 1000) if s and c else None
        failed = r0.get("completionTime") and r0.get("failedCount")
        base["status"] = "FAILED" if failed else "HEALTHY" if ok else "WARNING"
        if failed:
            base["latestError"] = f"execution {r0.get('name', '').rsplit('/', 1)[-1]} had {r0.get('failedCount')} failed task(s)"
    if (sch or {}).get("state") == "PAUSED":
        base["status"] = "PAUSED"
    return base


# ---------------------------------------------------------------- run
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lakes", default=None, help="comma-separated canonical lake IDs")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="write the payloads to --out instead of the Brain RTDB")
    ap.add_argument("--out", default=None, help="folder for the run report (and the payloads in --dry-run)")
    ap.add_argument("--force", action="store_true", help="rewrite every lake even when its input fingerprint is unchanged")
    ap.add_argument("--engine-concurrency", type=int, default=2)
    ap.add_argument("--batch", type=int, default=25, help="lakes per atomic RTDB update")
    ap.add_argument("--rtdb-url", default=os.environ.get("BRAIN_RTDB_URL", bp.BRAIN_RTDB_URL))
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    t0 = time.time()
    report = {"startedAt": bp.iso(now), "dryRun": a.dry_run, "published": 0, "engineFailures": [], "publishFailures": [], "errors": []}
    tokens = bp.TokenProvider()
    rtdb = None if a.dry_run else bp.BrainRtdb(a.rtdb_url, tokens, brain_id=cb.BRAIN_ID)
    payload = {}                     # dry-run: everything that would be written

    def write(updates: dict, what: str) -> bool:
        if a.dry_run:
            payload.update(updates)
            return True
        try:
            rtdb.update(updates)
            return True
        except Exception as e:
            report["publishFailures"].append({"what": what, "error": str(e)[:300]})
            return False

    # 1. canonical lakes, outlines, previous Brain state
    try:
        lakes = load_directory()
        keys = bp.lake_keys([l["id"] for l in lakes])
        polys = polygon_ids()
        unknown = sorted(p for p in polys if p not in keys)
        if unknown:
            report["errors"].append(f"{len(unknown)} lake-surface outlines are not canonical lake IDs: {unknown[:5]}")
        prev_registry = prev_fleet = prev_activity = None
        if rtdb:
            bp.check_schema(rtdb)
            prev_registry = rtdb.get(f"brains/{cb.BRAIN_ID}")
            prev_fleet = rtdb.get("lakeFleet") or {}
            prev_activity = rtdb.get("activity") or {}
        prev_fleet = prev_fleet or {}
    except Exception as e:
        report["errors"].append("aborted before any lake: " + str(e)[:300])
        report["status"] = "FAILED"
        if rtdb:
            try:
                rtdb.update({f"/health/brains/{cb.BRAIN_ID}/status": "FAILED", f"/health/brains/{cb.BRAIN_ID}/lastRun": bp.iso(now),
                             f"/health/brains/{cb.BRAIN_ID}/latestError": str(e)[:300]})
            except Exception:
                pass
        print(json.dumps(report, indent=1))
        return 1

    all_ids = [l["id"] for l in lakes]
    if a.lakes:
        want = set(a.lakes.split(","))
        lakes = [l for l in lakes if l["id"] in want]
    if a.limit:
        lakes = lakes[: a.limit]
    rev = engine_revision(tokens)
    report["engineRevision"] = rev
    print(f"water-clarity-brain: {len(lakes)} lakes, engine {rev}, {'DRY RUN' if a.dry_run else a.rtdb_url}", flush=True)

    # 2. bucket evidence (cheap public reads)
    bucket = {}
    with cf.ThreadPoolExecutor(16) as ex:
        futs = {ex.submit(bucket_lake, l["id"]): l["id"] for l in lakes if l["id"] in polys}
        for f in cf.as_completed(futs):
            try:
                bucket[futs[f]] = f.result()
            except Exception as e:
                bucket[futs[f]] = {"latest": None, "meta": None, "passCount": None, "error": str(e)[:200]}
                report["errors"].append(f"bucket read {futs[f]}: {str(e)[:120]}")

    # 3. engine conditions per lake, published in atomic batches as they arrive
    results, pending, done = {}, {}, 0
    with cf.ThreadPoolExecutor(a.engine_concurrency) as ex:
        futs = {ex.submit(engine_conditions, l): l for l in lakes}
        for f in cf.as_completed(futs):
            lake = futs[f]
            lid = lake["id"]
            err = None
            try:
                cond = f.result()
            except Exception as e:
                cond, err = None, f"{type(e).__name__}: {str(e)[:160]}"
            try:
                t_lake = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
                b = bucket.get(lid) or {}
                est = cb.engine_estimate(cond, lid)
                sat = cb.satellite_evidence(b.get("latest"), b.get("meta"), lid in polys, b.get("passCount"), t_lake)
                sat = cb.apply_rain_invalidation(sat, est.get("rainDaily"))
                layers, geo = cb.map_layers(b.get("latest"), b.get("meta"))
                prev_slot = ((prev_fleet.get(keys[lid]) or {}).get("slots") or {}).get(cb.SLOT)
                if est["stateType"] == "UNAVAILABLE":
                    report["engineFailures"].append({"lakeId": lid, "error": err or "no clarityVisibility"})
                if est["stateType"] == "UNAVAILABLE" and prev_slot:
                    # keep the last good state; record the miss and age it
                    pending[lid] = {**cb.lake_writes(lid, None, None, t_lake, err or "no clarityVisibility"), **cb.stale_carry(lid, prev_slot, t_lake)}
                    results[lid] = {"state": None, "error": err}
                else:
                    state = cb.build_state(lid, est, sat, layers, geo, t_lake, rev)
                    if (prev_slot or {}).get("inputFingerprint") == state["inputFingerprint"] and not a.force:
                        # nothing material changed: stamp verification + freshness only (state stays as published)
                        pending[lid] = cb.noop_writes(lid, state["inputFingerprint"], t_lake)
                        results[lid] = {"state": state, "profile": None, "error": err, "noop": True}
                        report["noop"] = report.get("noop", 0) + 1
                    else:
                        profile = cb.build_profile(lake, est, sat, lid in polys, t_lake)
                        pending[lid] = cb.lake_writes(lid, profile, state, t_lake)
                        results[lid] = {"state": state, "profile": profile, "error": err}
            except Exception as e:              # one lake's bad data never stops the others
                report["errors"].append(f"build {lid}: {type(e).__name__}: {str(e)[:160]}")
                traceback.print_exc()
                results[lid] = {"state": None, "error": str(e)}
            done += 1
            if len(pending) >= a.batch or done == len(lakes):
                batch = {k: v for w in pending.values() for k, v in w.items()}
                if write(batch, f"{len(pending)} lakes"):
                    report["published"] += sum(1 for l in pending if results[l].get("state"))
                pending = {}
                print(f"  {done}/{len(lakes)} lakes", flush=True)

    # 4. fleet-level records
    run_rec = None
    try:
        run_rec = lake_surface_run(now)
    except Exception as e:
        report["errors"].append(f"lake-surface run record: {str(e)[:160]}")
    n_ok = sum(1 for r in results.values() if r.get("state") and r["state"]["stateType"] != "UNAVAILABLE")
    sat_job_ok = None if run_rec is None else (now - bp.parse_time(run_rec["finishedAt"])).total_seconds() < 36 * 3600
    status = cb.run_health(len(lakes), n_ok, len(lakes) - n_ok, sat_job_ok, aborted=False)
    if report["publishFailures"]:
        status = "DEGRADED" if status == "HEALTHY" else status
    last_success = bp.iso(now) if status in ("HEALTHY", "WARNING") else (prev_registry or {}).get("lastSuccessfulRun")
    last_error = None
    if report["engineFailures"] or report["publishFailures"]:
        msg = (report["publishFailures"] or report["engineFailures"])[0]
        last_error = {"at": bp.iso(now), "message": f"{len(report['engineFailures'])} engine misses, {len(report['publishFailures'])} publish failures; first: {msg.get('error')}"[:300]}
    # counts span the whole directory: lakes not in this run keep their last published slot
    registry = cb.registry_entry(results, prev_fleet, now, status, last_error, rev, all_ids, last_success)
    sources = cb.source_records(results, now, run_rec)
    jobs = {}
    if not a.dry_run or os.environ.get("BRAIN_DRY_RUN_JOBS"):
        jobs = {j: job_health(j, m, tokens) for j, m in cb.CATALOG["jobs"].items()}
    duration_ms = int((time.time() - t0) * 1000)
    jobs["water-clarity-brain"] = {"displayName": "water-clarity-brain", "brainId": cb.BRAIN_ID,
                                   "deploymentStatus": "SCHEDULED_JOB" if os.environ.get("CLOUD_RUN_JOB") else "MANUAL_RUN_NOT_DEPLOYED",
                                   "kind": "Cloud Run job" if os.environ.get("CLOUD_RUN_JOB") else "manual run",
                                   "schedule": None, "status": status, "lastRun": bp.iso(now), "lastSuccess": last_success,
                                   "durationMs": duration_ms, "latestError": (last_error or {}).get("message"), "running": False}
    health = {"status": status, "lastRun": bp.iso(now), "lastSuccess": last_success, "durationMs": duration_ms,
              "staleLakeCount": registry["staleLakeCount"], "errorCount": len(report["engineFailures"]) + len(report["publishFailures"]),
              "latestError": (last_error or {}).get("message"), "deployedVersion": cb.BRAIN_VERSION, "brainVersion": cb.BRAIN_VERSION,
              "engineRevision": rev, "publisherDeployment": jobs["water-clarity-brain"]["deploymentStatus"],
              "lakesAttempted": len(lakes), "lakesPublished": report["published"], "lakeSurfaceRun": run_rec}
    validation = dict(cb.CATALOG["validation"]["production"])
    validation["candidates"] = cb.CATALOG["validation"]["candidates"]
    glob = {f"/brains/{cb.BRAIN_ID}": registry, f"/health/brains/{cb.BRAIN_ID}": health, f"/validation/{cb.BRAIN_ID}": validation}
    for sid, rec in sources.items():
        glob[f"/sources/{sid}"] = rec
        glob[f"/health/sources/{sid}"] = {"status": rec["health"], "lastFetchAt": rec["lastFetchAt"]}
        if rec.get("failures24h") is not None:            # unknown stays absent, never 0 (contract §6)
            glob[f"/health/sources/{sid}"]["failures24h"] = rec["failures24h"]
    for jid, rec in jobs.items():
        glob[f"/health/jobs/{jid}"] = rec
    events = cb.activity_events(prev_registry, prev_fleet, results, now, status)
    glob.update({f"/activity/{k}": v for k, v in events.items()})
    glob.update(cb.prune_activity(prev_activity, now))
    write(glob, "fleet records")
    report.update({"status": status, "durationMs": duration_ms, "lakes": len(lakes), "engineOk": n_ok,
                   "readinessCounts": registry["readinessCounts"], "breakdowns": registry["breakdowns"],
                   "rtdbWrites": rtdb.writes if rtdb else 0, "rtdbBytes": rtdb.bytes_written if rtdb else 0})
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(report, open(os.path.join(a.out, "run_report.json"), "w"), indent=1)
        if a.dry_run:
            json.dump(payload, open(os.path.join(a.out, "payload.json"), "w"), indent=1)
    print(json.dumps({k: report[k] for k in ("status", "lakes", "engineOk", "published", "durationMs", "readinessCounts")}, indent=1))
    return 0 if status in ("HEALTHY", "WARNING") else 2


if __name__ == "__main__":
    sys.exit(main())
