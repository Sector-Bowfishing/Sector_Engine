"""WindBrain publisher: Candidate archive -> Sector Brain RTDB (additive adapter; research/shadow data only).

Write order (BRAIN_INTEGRATION_REQUIREMENTS §0.9): per lake `states/wind` + `snapshots/{k}/latest` (one atomic update)
-> `lakeFleet` -> registry `brains/wind` (+ validation, sources) -> `health` -> `activity`.
WindBrain writes ONLY wind-owned paths. Shared nodes are touched field-by-field (`lakeFleet/{k}/readiness/wind`,
`snapshots/{k}/latest/wind`), never overwritten whole. It never writes /schemaVersion, /health/engine, /access or
another brain's slot. `publish()` never raises: a Brain RTDB failure cannot affect the hourly archive job."""
from __future__ import annotations

import json
import os
import subprocess
import time
import traceback
from datetime import datetime, timedelta, timezone

from .. import DECODER_VERSION
from ..sample import parse_iso
from . import contract as C
from .lakes import ENGINE_URL, WIND_LAKE_IDS, check_keys, fetch_directory, national_profiled, verify_wind_lakes
from .writer import PLATFORM
from sector_brain_platform import event_id as _event_id, is_promotion as _is_promotion, prune_activity as _prune_own
from .profile import build_profile, geometry_facts
from .state import build_state

EVIDENCE = os.path.join(os.path.dirname(__file__), "validation_evidence.json")
ACTIVITY_MAX, ACTIVITY_DAYS = 500, 30


def deployment_version() -> str | None:
    v = os.environ.get("SECTOR_WIND_BUILD")          # set at deploy time (git SHA / image tag)
    if v:
        return v
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5, cwd=os.path.dirname(__file__))
        return f"local-{r.stdout.strip()}" if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def _newest_run(store, now):
    keys = []
    for d in (now, now - timedelta(days=1)):
        keys += store.list(f"runs/{d:%Y%m%d}/")
    keys.sort()
    runs = [(k, store.get_json(k)) for k in keys[-30:]]
    runs = [(k, r) for k, r in runs if r]
    last = runs[-1][1] if runs else None
    ok = [r for _, r in runs if not r.get("errors")]
    return last, (ok[-1] if ok else None)


def _read_ledger_lines(store, now):
    """Ledger runs are JSONL objects; read only the last 24 h of files."""
    cutoff = now - timedelta(hours=24); rows = []
    days = {f"{d:%Y%m%d}" for d in (now, now - timedelta(days=1))}
    keys = [k for k in store.list("ledger/runs/") if k.rsplit("/", 1)[-1][:8] in days]   # LocalStore.list walks dirs only
    for k in sorted(set(keys)):
        try:
            if datetime.strptime(k.rsplit("/", 1)[-1][:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc) < cutoff:
                continue
        except ValueError:
            continue
        try:
            if hasattr(store, "bucket"):
                txt = store.bucket.blob(store._k(k)).download_as_text()
            else:
                txt = open(os.path.join(store.root, k)).read()
            rows += [json.loads(l) for l in txt.splitlines() if l.strip()]
        except Exception:
            continue
    return rows


def _health_status(errors: list, stale_lakes: int, live_lakes: int) -> str:
    if errors and live_lakes == 0:
        return "FAILED"
    if errors or stale_lakes:
        return "DEGRADED" if stale_lakes == live_lakes and live_lakes else "WARNING"
    return "HEALTHY"


FLEET_FULL_REFRESH_H = 24


def canonical_scores_ref(ev: dict) -> dict:
    """Registry/validation `scores` block WITHOUT the baked certification number.

    The canonical Wind score is owned by the scorer and published by the shared brain-orchestrator at /scores/wind. This job image bakes
    validation_evidence.json at build time, so republishing its certification number hourly kept re-writing a stale value (3.1) next to the
    canonical 3.3. Publish a reference instead; keep BWIS (not published elsewhere) clearly dated."""
    sc = ev.get("scores") or {}
    out = {"canonicalRef": "/scores/wind", "canonicalField": "value",
           "note": "certification score is NOT published here: read /scores/wind (shared orchestrator) or /control/overview/brains/wind/score"}
    for k in ("windCertificationRubric", "bowfishingWindIntelligenceScore", "bwisDefinitionSha256"):
        if k in sc:
            out[k] = sc[k]
    out["bwisAsOf"] = ev.get("frozenAt")
    return out


def _validation_payloads(ev: dict, now_iso: str) -> tuple[dict, dict]:
    units = {"speedMaeMph": "mph", "speedBiasMph": "mph", "nightSpeedMaeMph": "mph", "nightSpeedBiasMph": "mph", "windyHourSpeedMaeMph": "mph",
             "directionMaeDeg": "deg", "directionWithin22_5Pct": "%", "gustMaeMph": "mph", "gustConditionalBiasMph": "mph",
             "event15mphPod": "ratio", "event15mphFar": "ratio"}
    shell = {"brainId": C.BRAIN_ID, "modelVersion": ev["candidateModel"], "validationVersion": f"wind-validation-evidence (frozen {ev['frozenAt']})",
             "status": "PARTIAL", "lastRunAt": ev["frozenAt"], "holdoutType": ev["holdoutType"], "failedGates": ev["failedGates"],
             "metricUnits": units, "artifactRef": ev["artifactRefs"][0], "window": ev["window"], "truth": ev["truth"]}
    fleet = {**shell, "sampleCount": ev["sampleCount"], "lakeCount": ev["lakeCount"], "metrics": ev["metrics"], "byClass": ev["byClass"],
             "problemLakes": sorted([{"lakeId": lid, "metric": "speedMaeMph", "value": v["metrics"]["speedMaeMph"]} for lid, v in ev["perLake"].items()
                                     if v["metrics"]["speedMaeMph"] > ev["metrics"]["speedMaeMph"]], key=lambda x: -x["value"]),
             "modelHistory": [{"version": C.PRODUCTION_MODEL["modelId"], "date": None, "status": "ACTIVE_PRODUCTION"},
                              {"version": ev["candidateModel"], "date": "2026-10-06", "status": "RESEARCH_CANDIDATE (not promoted)"}],
             "productionProxy": ev["productionProxy"], "surfacePhysics": ev["surfacePhysics"], "scores": canonical_scores_ref(ev),
             "liveValidation": ev["liveValidation"], "artifactRefs": ev["artifactRefs"], "publishedAt": now_iso,
             "separation": "MODEL/SCIENCE validation only. Lake readiness lives in /lakeFleet and profiles; runtime health in /health."}
    per_lake = {lid: {**shell, "lakeId": lid, "sampleCount": v["sampleCount"], "lakeCount": 1, "metrics": v["metrics"],
                      "stations": v["stations"], "publishedAt": now_iso} for lid, v in ev["perLake"].items()}
    return fleet, per_lake


def prune_activity(writer, now):
    """Delete only THIS brain's old activity, decided by `at` (Brain Platform contract §7). Best effort."""
    dels = _prune_own(writer.get("activity") or {}, C.BRAIN_ID, now)
    if dels:
        writer.patch(dels)


def publish(store, cfg, writer, now: datetime | None = None, run_summary: dict | None = None,
            directory: list[dict] | None = None, engine_url: str = ENGINE_URL, mode: str = "scheduled") -> dict:
    """mode: 'scheduled' (inside the wind-hourly Cloud Run Job) or 'manual' (an operator run; data will not refresh on its own)."""
    t0 = time.time(); now = (now or datetime.now(timezone.utc)).replace(microsecond=0); now_iso = C.iso(now)
    rep = {"ok": False, "errors": [], "lakes": {}, "writes": 0}
    dep = deployment_version(); proc = f"{DECODER_VERSION} + {C.BRAIN_VERSION} @ {dep}"
    try:
        directory = directory or fetch_directory(engine_url)
        keys = check_keys(directory)
        wind_dir = verify_wind_lakes(directory, cfg)
    except Exception as e:
        rep["errors"].append(f"directory: {e!r}")
        try:
            writer.patch({f"health/brains/{C.BRAIN_ID}/status": "FAILED", f"health/brains/{C.BRAIN_ID}/lastRun": now_iso,
                          f"health/brains/{C.BRAIN_ID}/latestError": f"canonical lake directory unavailable or invalid: {e!r}"[:300]})
        except Exception as e2:
            rep["errors"].append(f"health write: {e2!r}")
        return rep

    last = store.get_json("brain/wind/last_publish.json") or {}
    manifest = store.get_json("fetch/national/MANIFEST.json")
    national = national_profiled(manifest, directory)

    # ── 1. per-lake state + snapshot (one atomic update each) ─────────────────────────────────
    new_fps: dict[str, str | None] = {}
    readiness: dict[str, str] = {}; kinds = {"analysis": 0, "forecast": 0, "unavailable": 0}; stale_lakes = 0
    ev = json.load(open(EVIDENCE))
    val_fleet, val_lakes = _validation_payloads(ev, now_iso)
    for wl, lid in WIND_LAKE_IDS.items():
        k = keys[lid]
        try:
            fetch_obj = store.get_json(f"fetch/dev/{wl}.windfetch.json.gz")
            state, rows, meta = build_state(store, cfg, wl, lid, wind_dir[wl], now, fetch_obj, proc)
            geom = None; gflags = []
            if fetch_obj:
                geom = geometry_facts(fetch_obj)
            else:
                gflags.append("fetchTablesNotInStorage")
            stations = [{"station": s, "network": v.get("network")} for s, v in cfg["stations"].items() if v.get("lake") == wl]
            forcing = {"forecast": "NOAA NBM v5.0 hourly cycles (direct NODD, Candidate decoder)", "analysis": "NOAA RTMA-RU 2.5 km, 15 min",
                       "observations": stations, "cutoutBox": cfg["lakes"][wl]["bbox"], "archive": "gs://sector-wind-candidate/wind/v1"}
            profile = build_profile(lid, now_iso, meta["readiness"], geom,
                                    {"source": "USGS NHD-HR (frozen app asset)", "researchKey": wl}, forcing, {"status": "PASS", "basis": "Stage 1/2 six-case + exact Shapely check"}, gflags)
            writer.patch({f"lakes/{k}/states/{C.SLOT}": state, f"lakes/{k}/profiles/{C.SLOT}": profile,
                          f"lakes/{k}/validation/{C.BRAIN_ID}": val_lakes.get(lid),
                          f"snapshots/{k}/latest/{C.SNAPSHOT_FIELD}": state, f"snapshots/{k}/latest/lakeId": lid,
                          f"snapshots/{k}/latest/brainVersions/{C.BRAIN_ID}": C.BRAIN_VERSION})
            rep["writes"] += 1
            fp = meta.get("inputFingerprint"); new_fps[lid] = fp
            if fp and (last.get("fingerprints") or {}).get(lid) == fp:
                rep["fingerprintSkips"] = rep.get("fingerprintSkips", 0) + 1     # inputs unchanged: bank detail would be byte-identical
            elif rows:
                try:
                    store.put_json(f"brain/wind/latest/{k}.json.gz", {"lakeId": lid, "generatedAt": now_iso, "model": C.CANDIDATE_MODEL,
                                                                       "wind": {kk: state[kk] for kk in ("kind", "sustainedMph", "directionDeg")},
                                                                       "note": "physical per-bank surface for the current wind; not a recommendation", "banks": rows})
                except Exception as e:
                    rep["errors"].append(f"bank detail {lid}: {e!r}")
            readiness[lid] = meta["readiness"]; kinds[meta["kind"]] += 1; stale_lakes += meta["stale"] or meta["kind"] == "unavailable"
            rep["lakes"][lid] = meta
        except Exception as e:
            readiness[lid] = "DEGRADED"; kinds["unavailable"] += 1; stale_lakes += 1
            rep["errors"].append(f"lake {lid}: {e!r} {traceback.format_exc()[-300:]}")

    # National fetch-only lakes: profile (no state — no forcing is archived for them).
    prof_updates = {}
    for lid, m in national.items():
        k = keys[lid]
        try:
            sha = m["tableSha256"]
            geom = store.get_json(f"brain/wind/profile_cache/{sha}.json")
            if geom is None:
                obj = store.get_json(f"fetch/national/{m['slug']}.windfetch.json.gz")
                if obj is None:
                    continue
                geom = geometry_facts(obj); store.put_json(f"brain/wind/profile_cache/{sha}.json", geom)
            flags = [] if m["status"] == "PASS" else [f"fetchQaFlagged:{m.get('reason')}"]
            if last.get("profileShas", {}).get(lid) != sha:
                prof_updates[f"lakes/{k}/profiles/{C.SLOT}"] = build_profile(
                    lid, now_iso, "PROFILED", geom, {"source": (m.get("geometry") or {}).get("source"), "gnis": (m.get("geometry") or {}).get("gnis"),
                                                     "reachcodes": (m.get("geometry") or {}).get("reachcodes")},
                    None, {"status": m["status"], "reason": m.get("reason"), "spotCheck": (m.get("qa") or {}).get("spotCheck")}, flags)
            readiness[lid] = "PROFILED"
        except Exception as e:
            rep["errors"].append(f"profile {lid}: {e!r}")
    if prof_updates:
        writer.patch(prof_updates); rep["writes"] += 1

    # ── 2. fleet: wind readiness for every canonical lake (field-level, never the whole row) ──
    for l in directory:
        readiness.setdefault(l["id"], "DISCOVERED")
    fleet = {}
    # Only the live lakes (heartbeat fields) and lakes whose readiness CHANGED are rewritten; the other ~600 rows are unchanged hour to hour.
    # A full refresh every FLEET_FULL_REFRESH_H hours repairs any drift (a deleted node, a first run) without a per-run fleet-wide write.
    prev_fleet = last.get("fleetReadiness") or {}
    full_due = (not prev_fleet) or (not last.get("fleetFullAt")) or \
        (now - datetime.strptime(last["fleetFullAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() >= FLEET_FULL_REFRESH_H * 3600
    for lid, r in readiness.items():
        k = keys[lid]
        if not (full_due or lid in WIND_LAKE_IDS.values() or prev_fleet.get(lid) != r):
            continue
        fleet[f"lakeFleet/{k}/lakeId"] = lid
        fleet[f"lakeFleet/{k}/readiness/{C.SLOT}"] = r
        if lid in WIND_LAKE_IDS.values():
            fleet[f"lakeFleet/{k}/modelVersions/{C.SLOT}"] = C.CANDIDATE_MODEL
            m = rep["lakes"].get(lid) or {}
            # Per-brain fleet record (same shape the Water Clarity brain writes): wind staleness without touching lake aggregates.
            fleet[f"lakeFleet/{k}/slots/{C.SLOT}"] = {"readiness": r, "stale": bool(m.get("stale", True)), "stateType": m.get("kind", "unavailable"), "kind": m.get("kind", "unavailable"),
                                                       "issueCount": 0 if r == "CALIBRATION" else 1, "lastUpdatedAt": now_iso}
    if fleet:
        writer.patch(fleet); rep["writes"] += 1
    rep["fleetPathsWritten"] = len(fleet)

    # ── 3. registry + validation + sources ────────────────────────────────────────────────────
    counts: dict[str, int] = {}
    for r in readiness.values():
        counts[r] = counts.get(r, 0) + 1
    live = len(WIND_LAKE_IDS)
    run_last, run_ok = (run_summary, run_summary if run_summary and not run_summary.get("errors") else None) if run_summary else _newest_run(store, now)
    ledger = _read_ledger_lines(store, now)
    done = {(e.get("product"), e.get("cycle"), e.get("lake")) for e in ledger if e.get("status") == "complete"}
    def _miss(prod, recovered):
        if not any(e.get("product") == prod for e in ledger):
            return None                                  # no ledger evidence: never a fake 0
        return sum(1 for e in ledger if e.get("product") == prod and e.get("status") != "complete"
                   and ((e.get("product"), e.get("cycle"), e.get("lake")) in done) == recovered)
    fails = lambda prod: _miss(prod, False)              # never completed within the window
    recovered = lambda prod: _miss(prod, True)           # partial / failed first attempt, completed by catch-up
    newest = lambda prod: max((e.get("cycle") for e in ledger if e.get("product") == prod and e.get("status") == "complete"), default=None)
    errors_now = list(rep["errors"]) + list((run_last or {}).get("errors") or [])
    health = _health_status(errors_now, stale_lakes, live)
    registry = {
        "brainId": C.BRAIN_ID, "displayName": C.DISPLAY_NAME, "domain": C.DOMAIN, "question": C.QUESTION,
        "platform": PLATFORM,
        "stalenessModel": "TIME", "dependsOn": [],
        "schedule": {"cadence": C.JOB_SCHEDULE, "jobId": C.JOB_ID, "running": False},
        "descriptor": {"components": {"windState": {"status": "ACTIVE (candidate; production wind is Open-Meteo in /conditions)",
                                                   "inputs": ["NOAA NBM (hourly cycles)", "RTMA-RU (15 min)", "METAR (8 frozen stations)", "gs://sector-wind-candidate/wind/v1"],
                                                   "staleness": f"time-based: newest NBM cycle > {C.STALE_FORECAST_CYCLE_H} h or state > {C.STALE_AFTER_HOURS} h",
                                                   "recomputeWhen": ["every hour (wind-hourly)", "a newer NBM cycle is available"]}}},
        "version": C.BRAIN_VERSION, "schemaVersion": C.SCHEMA_VERSION, "enabled": True, "health": health,
        "status": "CALIBRATION", "supportedLakeCount": live, "profiledLakeCount": live + len(national),
        "readinessCounts": counts, "staleLakeCount": stale_lakes, "staleAfterHours": C.STALE_AFTER_HOURS,
        "staleRule": f"stale when the newest NBM cycle is > {C.STALE_FORECAST_CYCLE_H:g} h old, no current value exists, or generatedAt is > {C.STALE_GENERATED_MIN} min old",
        "lastSuccessfulRun": now_iso if not rep["errors"] else last.get("lastSuccessfulRun"),
        "lastError": {"at": now_iso, "message": errors_now[0][:300]} if errors_now else None,
        "deploymentVersion": dep,
        "breakdowns": {"readiness": counts, "stateKind": kinds,
                       "fetchQa": {"PASS (dev lakes)": live, **{s: sum(1 for m in national.values() if m["status"] == s) for s in ("PASS", "FLAGGED")}}},
        "versions": [{"version": C.PRODUCTION_MODEL["modelId"], "date": None, "note": "Active production wind in Engine /conditions (Open-Meteo Best Match = HRRR then GFS)", "status": "CURRENT"},
                     {"version": C.CANDIDATE_MODEL, "date": "2026-10-06", "note": "Research candidate: NBM v5.0 + RTMA-RU + frozen CEM. Shadow only; NOT promoted", "status": "SHADOW"}],
        "activeProductionModel": C.PRODUCTION_MODEL, "researchCandidate": C.RESEARCH_CANDIDATE,
        "scores": canonical_scores_ref(ev), "readinessDefinitions": C.READINESS_DEFINITIONS, "stateKinds": C.STATE_KINDS,
        "runsPerMinute": round(1 / 60, 4), "updatedAt": now_iso,
        "publishMode": mode if mode == "scheduled" else "manual operator run: no scheduled publisher is deployed yet, so this data does not refresh on its own",
    }
    srcs = {
        "noaa-nbm-v5": {"provider": "NOAA/NWS (NODD s3://noaa-nbm-grib2-pds)", "type": "forecast", "provides": "10 m wind speed, direction, gust; qmd percentiles",
                        "staleThresholdHours": C.STALE_FORECAST_CYCLE_H, "latestObservationAt": None, "latestIssuedAt": newest("NBM"), "failures24h": fails("NBM"), "recoveredRetries24h": recovered("NBM")},
        "noaa-rtma-ru": {"provider": "NOAA/NWS (NODD s3://noaa-rtma-pds)", "type": "analysis", "provides": "15-min 2.5 km 10 m wind analysis",
                         "staleThresholdHours": C.ANALYSIS_MAX_AGE_H, "latestObservationAt": newest("RTMA-RU"), "failures24h": fails("RTMA-RU"), "recoveredRetries24h": recovered("RTMA-RU")},
        "iem-metar-wind": {"provider": "Iowa Environmental Mesonet ASOS/AWOS archive", "type": "observation", "provides": "airport 10 m wind (8 frozen stations)",
                           "staleThresholdHours": C.OBSERVATION_MAX_AGE_H, "latestObservationAt": max((m.get("observationAt") or "" for m in rep["lakes"].values()), default=None) or None,
                           "failures24h": fails("METAR"), "recoveredRetries24h": recovered("METAR")},
    }
    src_updates = {}
    for sid, s in srcs.items():
        f24 = s["failures24h"]
        st = "UNKNOWN" if f24 is None else ("HEALTHY" if f24 == 0 else ("WARNING" if f24 < 6 else "DEGRADED"))
        src_updates[f"sources/{sid}"] = {"sourceId": sid, **s, "ownerBrainId": C.BRAIN_ID, "brains": {C.BRAIN_ID: True}, "lakeCount": live, "health": st,
                                         "lastFetchAt": (run_last or {}).get("runAt"), "latencyMs": None,
                                         "notes": "wind-hourly ledger, last 24 h: failures24h = never completed; recoveredRetries24h = completed by catch-up"}
        src_updates[f"health/sources/{sid}"] = {"status": st, "lastFetchAt": (run_last or {}).get("runAt"), "failures24h": s["failures24h"],
                                                "recoveredRetries24h": s["recoveredRetries24h"]}
    writer.patch({f"brains/{C.BRAIN_ID}": registry, f"validation/{C.BRAIN_ID}": val_fleet, **src_updates}); rep["writes"] += 1

    # ── 4. health ─────────────────────────────────────────────────────────────────────────────
    dur = int((time.time() - t0) * 1000)
    job_err = ((run_last or {}).get("errors") or [None])[0]
    writer.patch({
        f"health/brains/{C.BRAIN_ID}": {"status": health, "lastRun": now_iso, "lastSuccess": registry["lastSuccessfulRun"], "durationMs": dur,
                                        "staleLakeCount": stale_lakes, "errorCount": len(errors_now), "latestError": errors_now[0][:300] if errors_now else None,
                                        "deployedVersion": dep, "publishMode": registry["publishMode"]},
        f"health/jobs/{C.JOB_ID}": {"displayName": "Wind hourly (NBM / RTMA-RU / METAR archive)" + (" + WindBrain publish" if mode == "scheduled" else ""),
                                    "kind": "Cloud Run Job", "brainPublishInJob": mode == "scheduled",
                                    "schedule": C.JOB_SCHEDULE, "status": "FAILED" if job_err else ("HEALTHY" if run_last else "UNKNOWN"),
                                    "lastRun": (run_last or {}).get("runAt"), "lastSuccess": (run_ok or {}).get("runAt"),
                                    "durationMs": int(1000 * run_last["seconds"]) if run_last and run_last.get("seconds") is not None else None,
                                    "latestError": job_err[:300] if job_err else None, "running": False},
    }); rep["writes"] += 1

    # ── 5. activity (only on change) ──────────────────────────────────────────────────────────
    events = []
    if last.get("version") != C.BRAIN_VERSION:
        events.append(("brain.version" if last.get("version") else "brain.registered", "success",
                       f"WindBrain {C.BRAIN_VERSION} publishing ({live} lakes live, {len(national)} profiled)", None))
    for lid in WIND_LAKE_IDS.values():
        before = (last.get("readiness") or {}).get(lid)
        if before and before != readiness.get(lid):
            sev = "warning" if readiness.get(lid) == "DEGRADED" else "success"
            events.append(("readiness.promoted" if _is_promotion(before, readiness.get(lid)) else "readiness.changed", sev,
                           f"Wind readiness {before} -> {readiness.get(lid)}", lid))
    if errors_now and not last.get("errors"):
        events.append(("run.failed", "critical", f"WindBrain run error: {errors_now[0][:120]}", None))
    if events:
        writer.patch({f"activity/{_event_id(now, C.BRAIN_ID, i)}": {"id": _event_id(now, C.BRAIN_ID, i), "at": now_iso, "kind": kind, "title": title,
                                                       "brainId": C.BRAIN_ID, **({"lakeId": lid} if lid else {}), "severity": sev}
                      for i, (kind, sev, title, lid) in enumerate(events)})
        try:
            prune_activity(writer, now)
        except Exception as e:
            rep["errors"].append(f"activity prune: {e!r}")
    rep["events"] = len(events)

    try:
        store.put_json("brain/wind/last_publish.json", {"at": now_iso, "version": C.BRAIN_VERSION,
                                                        "readiness": {l: readiness[l] for l in WIND_LAKE_IDS.values()},
                                                        "fleetReadiness": dict(readiness), "fleetFullAt": now_iso if full_due else last.get("fleetFullAt"),
                                                        "fingerprints": {**(last.get("fingerprints") or {}), **{l: f for l, f in new_fps.items() if f}},
                                                        "profileShas": {**last.get("profileShas", {}), **{lid: m["tableSha256"] for lid, m in national.items()}},
                                                        "lastSuccessfulRun": registry["lastSuccessfulRun"], "errors": errors_now[:3]})
    except Exception as e:
        rep["errors"].append(f"last_publish: {e!r}")
    rep.update({"ok": not rep["errors"], "health": health, "readinessCounts": counts, "durationMs": dur, "national": len(national)})
    return rep


def safe_publish(*args, **kwargs) -> dict:
    """Entry point for the hourly job: absolutely never raises."""
    try:
        return publish(*args, **kwargs)
    except Exception as e:
        return {"ok": False, "errors": [f"publish crashed: {e!r}", traceback.format_exc()[-500:]]}
