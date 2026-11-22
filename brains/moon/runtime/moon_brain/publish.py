"""Moon and Night Light DRY-RUN publisher: lake directory (+ optional Weather Brain cloud input) -> Brain RTDB shape, in memory only.

Write order mirrors the platform contract: per lake `states/moon` + snapshot -> `lakeFleet` rows -> registry/validation -> health.
The Brain writes ONLY moon-owned paths (ownership enforced by the writer). `publish()` never raises. There is no live writer: adopting one is a
Michael decision (customer publication off; execution control disabled)."""
from __future__ import annotations

import datetime as dt
import traceback
from collections import Counter

from . import contract as C
from .night import evening_date
from .state import build_state, plan
from .writer import PLATFORM  # noqa: E402  (also puts the shared platform package on sys.path)

from sector_brain_platform import lake_key, key_collisions  # noqa: E402

NOT_VALIDATED = {
    "brainId": C.BRAIN_ID, "status": "NOT_VALIDATED", "modelVersion": C.MODEL_ID,
    "validationVersion": "moon-validation-usno-crosscheck-v1 (astronomy only)",
    "note": "Sun, twilight and moon events are cross-checked against USNO published values in tests (brains/moon/tests/fixtures/usno_reference.json, "
            "tolerance 2 min). The darkness class is a stated rule (DARKNESS_RULE_V1), NOT validated against measured on-water light. "
            "No customer surface consumes it.",
    "separation": "MODEL/SCIENCE validation only. Lake readiness lives in /lakeFleet; runtime health in /health.",
}


def _health(errors: list, evaluated: int) -> str:
    if errors and evaluated == len(errors):
        return "FAILED"
    if errors:
        return "DEGRADED"
    return "HEALTHY" if evaluated else "UNKNOWN"


def publish(directory: dict, writer, date: dt.date | None, weather: dict | None = None, now: dt.datetime | None = None) -> dict:
    """directory: lakes.load(). date: the evening date for every lake, or None for each lake's own current night
    (night.evening_date(lon, now)). weather: {lakeId: Weather Brain state document} (optional, per lake; sector-brain-weather-state-v1)."""
    now = (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0)
    now_iso = C.iso(now)
    weather = weather or {}
    rep: dict = {"ok": False, "errors": [], "writes": 0, "lakes": {}}
    try:
        lakes = directory["lakes"]
        coll = key_collisions([r["lakeId"] for r in lakes])
        if coll:
            raise ValueError(f"lake key collision: {coll}")
        readiness, classes, bases = {}, Counter(), Counter()
        evaluated = skipped = 0
        for lake in lakes:
            lid = lake["lakeId"]
            k = lake_key(lid)
            w = weather.get(lid)
            night_of = date or evening_date(lake["lat"], lake["lon"], now)
            try:
                pl = plan(writer.get(f"lakes/{k}/states/{C.SLOT}"), lake, night_of, w)
                state = build_state(lake, night_of, w)
                evaluated += 1
                readiness[lid] = state["readiness"]
                classes[state["darkness"]["class"]] += 1
                bases[state["darkness"]["basis"]] += 1
                rep["lakes"][lid] = {"class": state["darkness"]["class"], "basis": state["darkness"]["basis"], "plan": pl["action"], "date": state["date"]}
                if pl["action"] == "SKIP":
                    skipped += 1
                    continue
                writer.patch({f"lakes/{k}/states/{C.SLOT}": state, f"snapshots/{k}/latest/{C.SNAPSHOT_FIELD}": state,
                              f"snapshots/{k}/latest/lakeId": lid, f"snapshots/{k}/latest/brainVersions/{C.BRAIN_ID}": C.BRAIN_VERSION})
                rep["writes"] += 1
            except Exception as e:
                readiness[lid] = "DEGRADED"
                evaluated += 1
                rep["errors"].append(f"lake {lid}: {e!r} {traceback.format_exc()[-300:]}")

        fleet = {}
        for lid, r in readiness.items():
            k = lake_key(lid)
            fleet[f"lakeFleet/{k}/lakeId"] = lid
            fleet[f"lakeFleet/{k}/readiness/{C.SLOT}"] = r
            fleet[f"lakeFleet/{k}/modelVersions/{C.SLOT}"] = C.MODEL_ID
            m = rep["lakes"].get(lid)
            if m:
                fleet[f"lakeFleet/{k}/slots/{C.SLOT}"] = {"readiness": r, "date": m["date"], "darknessClass": m["class"], "basis": m["basis"]}
        writer.patch(fleet)
        rep["writes"] += 1

        counts = dict(Counter(readiness.values()))
        health = _health(rep["errors"], evaluated)
        reg = {
            "brainId": C.BRAIN_ID, "displayName": C.DISPLAY_NAME, "domain": C.DOMAIN, "question": C.QUESTION, "platform": PLATFORM,
            "version": C.BRAIN_VERSION, "schemaVersion": C.SCHEMA_VERSION, "enabled": False, "health": health, "status": "CALIBRATION",
            "supportedLakeCount": len(lakes), "directoryLakeCount": directory["count"], "readinessCounts": counts,
            "staleLakeCount": counts.get("DEGRADED", 0), "staleAfterHours": C.STALE_AFTER_HOURS, "stalenessModel": C.STALENESS_MODEL,
            "dependsOn": list(C.DEPENDS_ON), "lastSuccessfulRun": now_iso if not rep["errors"] else None,
            "lastError": {"at": now_iso, "message": rep["errors"][0][:300]} if rep["errors"] else None,
            "schedule": {"cadence": "not scheduled: execution control disabled", "jobId": C.JOB_ID, "running": False},
            "models": {"active": None, "candidates": [{"modelId": C.MODEL_ID, "status": "CALIBRATION", "version": C.BRAIN_VERSION}]},
            "versions": [{"version": C.BRAIN_VERSION, "date": now_iso[:10], "note": "Moon, sun, twilight and on-water darkness; internal only",
                          "status": "CALIBRATION"}],
            "validation": {"ref": f"/validation/{C.BRAIN_ID}", "status": "NOT_VALIDATED"}, "sourceIds": [],
            "readinessDefinitions": C.READINESS_DEFINITIONS, "updatedAt": now_iso, "publishMode": "dry run only: no live writer",
            "scoreNote": C.SCORE_NOTE, "knowledgeRelease": directory.get("release"), "breakdowns": {"darknessClass": dict(classes), "basis": dict(bases), "night": date.isoformat() if date else "per lake: the night containing the run (local solar noon to noon)"},
        }
        writer.patch({f"brains/{C.BRAIN_ID}": reg, f"validation/{C.BRAIN_ID}": {**NOT_VALIDATED, "publishedAt": now_iso}})
        rep["writes"] += 1
        writer.patch({f"health/brains/{C.BRAIN_ID}/status": health, f"health/brains/{C.BRAIN_ID}/staleLakeCount": reg["staleLakeCount"]})
        rep["writes"] += 1
        rep.update({"ok": not rep["errors"], "health": health, "readinessCounts": counts, "evaluated": evaluated, "skippedUnchanged": skipped,
                    "darknessClass": dict(classes), "basis": dict(bases)})
    except Exception as e:
        rep["errors"].append(f"publish crashed: {e!r} {traceback.format_exc()[-400:]}")
    return rep
