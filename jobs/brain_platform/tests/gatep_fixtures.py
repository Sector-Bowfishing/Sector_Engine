"""Gate P fixtures: a synthetic multi-section Wind artifact (envelope v2). Lake keys, ids and values are invented; nothing here comes from a live system."""
import copy
import datetime as dt

from publisher_fixtures import LAKE_A, LAKE_B, SHA, T0, iso, uuid4
from sector_brain_platform.publisher import seal_bundle

FRESH = {"freshnessStatus": "FRESH"}


def lake_section(speed=4.2, lakes=(LAKE_A, LAKE_B), scope="lake-live", extra=()):
    muts = []
    for k in lakes:
        muts += [{"op": "SET", "path": f"/lakes/{k}/states/wind", "value": {"kind": "modeled", "windMS": speed, "inputAgeHours": 1.5, "generatedAt": "2026-10-15T03:00:00Z"}},
                 {"op": "SET", "path": f"/lakeFleet/{k}/slots/wind", "value": {"readiness": "CALIBRATION", "stale": False}}]
    return {"artifactSchema": "wind-lake-state-v1", "scope": scope, "freshness": dict(FRESH), "mutations": muts + list(extra)}


def registry_section(status="CALIBRATION", health="HEALTHY", version="wind-test-1", updated="2026-10-15T03:00:00Z", last_ok="2026-10-15T03:00:00Z", extra=()):
    return {"artifactSchema": "wind-registry-v1", "mutations": [
        {"op": "SET", "path": "/brains/wind/version", "value": version},
        {"op": "SET", "path": "/brains/wind/status", "value": status},
        {"op": "SET", "path": "/brains/wind/updatedAt", "value": updated},
        {"op": "SET", "path": "/brains/wind/lastSuccessfulRun", "value": last_ok},
        {"op": "SET", "path": "/health/brains/wind/status", "value": health},
        {"op": "SET", "path": "/health/brains/wind/staleLakeCount", "value": 0},
        {"op": "SET", "path": "/validation/wind", "value": {"status": "NOT_VALIDATED"}}] + list(extra)}


def source_section(last_fetch="2026-10-15T03:00:00Z", observed="2026-10-15T02:45:00Z", extra=()):
    return {"artifactSchema": "wind-source-registry-v1", "mutations": [
        {"op": "SET", "path": "/sources/noaa-nbm-v5", "value": {"provider": "synthetic", "latestObservationAt": observed}},
        {"op": "SET", "path": "/health/sources/noaa-nbm-v5", "value": {"status": "HEALTHY", "lastFetchAt": last_fetch, "latencyMs": 120, "failures24h": 0}}] + list(extra)}


def bundle(n=1, minutes=0, sections=None, **over):
    secs = copy.deepcopy(sections) if sections is not None else [lake_section(), registry_section(), source_section()]
    kw = dict(brain_id="wind", bundle_id="wind-publication-v1", sections=secs, lifecycle="CALIBRATION", review_status="UNREVIEWED", validation_status="NOT_VALIDATED",
              generated_at=iso(T0 + dt.timedelta(minutes=minutes)), execution_id=uuid4(1000 + n), code_version="deadbeef", input_fingerprint=SHA, artifact_id=uuid4(2000 + n))
    kw.update(over)
    return seal_bundle(**kw)
