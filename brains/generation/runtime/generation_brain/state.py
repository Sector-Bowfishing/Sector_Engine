"""One lake's Generation state (generation-dam-state-v1) from its bound sources. The only module that calls the source readers."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from . import contract as C
from .assess import assess
from .freshness import decide, schedule_fingerprint
from .sources import cwms, rise, swpa, tva, usgs

READERS = {"tva": tva.read, "cwms": cwms.read, "swpa": swpa.read, "rise": rise.read, "usgs": usgs.read}


def bound_sources(rec: dict, access: dict) -> list[dict]:
    """Sources this lake can be read from now: BOUND in the catalog AND the provider's access status is ALLOWED."""
    return [s for s in rec.get("sources") or [] if s.get("status") == "BOUND" and (access.get(s["provider"]) or {}).get("status") == "ALLOWED"]


def readiness_of(rec: dict, access: dict) -> str:
    if bound_sources(rec, access):
        return "CALIBRATION"
    if any(s.get("status") == "BOUND" for s in rec.get("sources") or []):
        return "ACCESS_BLOCKED"
    return "NOT_BOUND"


def _sha(obj) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def read_sources(rec: dict, access: dict, fetcher, now: datetime) -> list:
    return [READERS[s["provider"]](s, fetcher, now) for s in bound_sources(rec, access)]


def build_state(rec: dict, readings: list, prev: dict | None, now: datetime, catalog_version: str, release: dict | None) -> tuple[dict, dict]:
    a = assess(readings, now)
    fresh = decide(a, prev, now)
    access = {r.provider: r.agency for r in readings}
    sources = [r.summary(now) for r in readings]
    rel = a["release"]
    basis = ("NONE" if a["kind"] == C.UNAVAILABLE else "SCHEDULE_ONLY" if a["kind"] == C.SCHEDULE_ONLY
             else "MEASURED_DOWNSTREAM" if rel["downstreamGauge"] else "OPERATOR_PUBLISHED")
    fp_core = {"release": {k: v for k, v in rel.items()}, "schedule": schedule_fingerprint(a["schedule"]), "tailwater": a["tailwater"],
               "sources": [(s["provider"], s["ok"], s["error"]) for s in sources], "catalog": catalog_version, "brain": C.BRAIN_VERSION}
    state = {
        "schema": C.STATE_SCHEMA, "lakeId": rec["lakeId"], "kind": a["kind"], "lane": "INTERNAL",
        "dam": {"name": (rec.get("dam") or {}).get("name"), "nidId": (rec.get("dam") or {}).get("nidId"), "operatorName": rec.get("operatorName"),
                "group": rec.get("group")},
        "release": rel, "schedule": a["schedule"], "tailwater": a["tailwater"], "history": a["history"],
        "sources": sources, "agencies": sorted(set(access.values())),
        "freshness": fresh,
        "confidence": {"basis": basis, "unitsStated": bool(a["schedule"] and a["schedule"]["unitsStated"]),
                       "validation": "NOT_VALIDATED", "note": "operator-published and measured values only; nothing estimated or derived"},
        "gaps": a["gaps"],
        "provenance": {"brainVersion": C.BRAIN_VERSION, "modelId": C.MODEL_ID, "catalogVersion": catalog_version,
                       "knowledgeRelease": (release or {}).get("releaseId"), "scheduleFingerprint": schedule_fingerprint(a["schedule"]),
                       "inputFingerprint": _sha(fp_core), "generatedAt": C.iso(now)},
    }
    meta = {"kind": a["kind"], "status": rel["status"], "tier": fresh["tier"], "stale": fresh["stale"],
            "readiness": "CALIBRATION" if a["kind"] != C.UNAVAILABLE else "DEGRADED",
            "errors": [s["error"] for s in sources if s["error"]], "inputFingerprint": state["provenance"]["inputFingerprint"]}
    return state, meta


def plan(published: dict | None, new_fp: str) -> dict:
    """A dam that was due is always re-published (its freshness window is renewed); `changed` says whether the release picture moved."""
    if not published:
        return {"action": "PUBLISH", "reason": "first publication", "changed": True}
    changed = (published.get("provenance") or {}).get("inputFingerprint") != new_fp
    return {"action": "PUBLISH", "reason": "input fingerprint changed" if changed else "freshness renewed (same answer)", "changed": changed}
