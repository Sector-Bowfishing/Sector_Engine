"""Sector Intelligence Brain run: upstream brain registries + Engine serving revision -> Brain RTDB (sector-brain).

Reads: /brains, /health/brains, /validation/*/status and /lakeFleet in the Brain RTDB; GET /lakes from the Engine;
the Cloud Run service document for sector-engine. Writes only the Sector Intelligence paths (see
sector_intelligence_brain.py). It never calls /conditions, never evaluates a lake and touches no production path.

usage:
  python run.py --plan                       # orchestrator question: is a publish warranted?
  python run.py --dry-run --out out/         # build everything from live reads (GET only), write JSON files, no writes
  python run.py --write                      # publish (one atomic multi-path update)
env:
  BRAIN_RTDB_URL (sector-brain), ENGINE_URL, BRAIN_TOKEN_MODE metadata|gcloud,
  DEPLOYMENT_VERSION (else brain/sector-intelligence@<git sha>)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brain_platform as bp                  # noqa: E402
import orchestration as orch                 # noqa: E402
import sector_intelligence_brain as sib      # noqa: E402
import evaluation as ev                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RTDB_URL = os.environ.get("BRAIN_RTDB_URL", bp.BRAIN_RTDB_URL)
ENGINE_URL = os.environ.get("ENGINE_URL", "https://sector-engine-e43utajroa-uc.a.run.app")


def http_json(url: str, headers: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def cloud_run_service(tokens: bp.TokenProvider, lineage: dict) -> dict | None:
    url = (f"https://run.googleapis.com/v2/projects/{lineage['project']}/locations/{lineage['region']}"
           f"/services/{lineage['service']}")
    try:
        return http_json(url, {"Authorization": f"Bearer {tokens.token()}"}, timeout=30)
    except (urllib.error.URLError, RuntimeError, ValueError) as e:
        print(f"warning: Cloud Run service not readable ({e}); serving revision reported UNKNOWN", file=sys.stderr)
        return None


def deployment_version() -> str:
    if os.environ.get("DEPLOYMENT_VERSION"):
        return os.environ["DEPLOYMENT_VERSION"]
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True,
                             timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, capture_output=True, text=True,
                               timeout=10).stdout.strip()
        return f"brain/sector-intelligence@{sha or 'unknown'}{'+local' if dirty else ''}"
    except Exception:
        return "brain/sector-intelligence@unknown"


def read_upstream(rtdb: bp.BrainRtdb) -> dict:
    out = {}
    for bid in sib.DEPENDENCY_ORDER:
        out[bid] = {"registry": rtdb.get(f"brains/{bid}"), "health": rtdb.get(f"health/brains/{bid}"),
                    "validationStatus": rtdb.get(f"validation/{bid}/status")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--out", default="out")
    ap.add_argument("--no-pilot", action="store_true", help="skip the pilot evaluations (inventory-only publish)")
    ap.add_argument("--force", action="store_true", help="publish even when --plan says SKIP")
    a = ap.parse_args(argv)

    t0 = time.time()
    now = dt.datetime.now(dt.timezone.utc)
    tokens = bp.TokenProvider()
    with open(os.path.join(HERE, "catalog.json"), "rb") as fh:
        raw = fh.read()
    cat, cat_sha = sib.load_catalog(raw), sib.catalog_sha(raw)

    rtdb = bp.BrainRtdb(RTDB_URL, tokens, brain_id=sib.BRAIN_ID)   # ownership-checked; --plan/--dry-run only GET
    published = rtdb.get(f"brains/{sib.BRAIN_ID}")
    upstream = read_upstream(rtdb)
    serving = sib.engine_serving(cloud_run_service(tokens, cat["codeLineage"]), cat["codeLineage"], now)
    deps = {bid: sib.dependency_status(bid, cat["dependencies"][bid], upstream[bid]["registry"], upstream[bid]["health"],
                                       upstream[bid]["validationStatus"], cat, now) for bid in sib.DEPENDENCY_ORDER}
    # Pilot evaluations (Phase 9): real specialist states for the pilot lakes; a lake that cannot be
    # evaluated is recorded as an error and stays NOT_EVALUATED — never invented.
    evaluations, eval_errors = {}, {}
    if not a.no_pilot:
        species = rtdb.get("species") or {}
        fleet_rows = {}
        for lid in ev.PILOT_LAKES:
            k = bp.lake_key(lid)
            try:
                fleet_rows[k] = rtdb.get(f"lakeFleet/{k}")
                evaluations[lid] = ev.evaluate(lid, snapshot=rtdb.get(f"snapshots/{k}/latest"), fleet_row=fleet_rows[k],
                                               presence=rtdb.get(f"lakes/{k}/speciesPresence"), species=species,
                                               deps=deps, cat=cat, serving=serving, now=now)
            except Exception as e:                                 # degrade safely
                eval_errors[lid] = repr(e)[:200]
    inputs_fp = ev.inputs_fingerprint(evaluations) if evaluations else None
    fp = sib.fingerprint(cat_sha, serving, deps, inputs_fp)
    decision = orch.plan(published, fp, sib.BRAIN_VERSION,
                         published_age_hours=bp.age_hours((published or {}).get("lastSuccessfulRun"), now))
    if a.plan:
        print(json.dumps(decision | {"fingerprint": fp, "engineRevision": serving.get("revision")}, indent=1))
        return 0

    lakes = [l["id"] for l in http_json(f"{ENGINE_URL}/lakes")["lakes"]]
    fleet = rtdb.get("lakeFleet") or {}
    updates = sib.build_updates(cat=cat, cat_sha=cat_sha, lakes=lakes, fleet=fleet, upstream=upstream, serving=serving,
                                now=now, deployment=deployment_version(), descriptor=orch.DESCRIPTOR,
                                duration_ms=int((time.time() - t0) * 1000), published=published,
                                event_id=bp.event_id(now, sib.BRAIN_ID, 0),
                                evaluations=evaluations, evaluation_errors=eval_errors, inputs_fp=inputs_fp, fingerprint_value=fp)
    sib.check_keys(updates)
    body = json.dumps({k.lstrip("/"): v for k, v in updates.items()}, separators=(",", ":"), allow_nan=False)
    reg = updates[f"/brains/{sib.BRAIN_ID}"]
    summary = dict(decision=decision, fingerprint=fp, lakes=len(lakes), paths=len(updates), bytes=len(body),
                   evaluated=sorted(evaluations), evaluationErrors=eval_errors,
                   pilot={lid: {"inputsFresh": e["synthesis"]["inputsFresh"], "degraded": e.get("degradedInputs"), "drivers": [d["fact"] for d in e.get("drivers", [])]}
                          for lid, e in evaluations.items()},
                   engineServing=serving, dependencySummary=reg["dependencySummary"],
                   connection={b: d["connectionStatus"] for b, d in reg["dependencies"].items()})

    if a.dry_run:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "updates.json"), "w") as fh:
            json.dump(updates, fh, indent=1, ensure_ascii=False)
        print(json.dumps(summary, indent=1))
        return 0

    if decision["action"] == "SKIP" and not a.force:
        print(json.dumps(summary | {"published": False}, indent=1))
        return 0
    bp.check_schema(rtdb)
    rtdb.update(updates)
    print(json.dumps(summary | {"published": True, "rtdbWrites": rtdb.writes, "rtdbBytes": rtdb.bytes_written}, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except sib.CatalogError as e:
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
