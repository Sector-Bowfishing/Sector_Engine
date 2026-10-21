"""WaterClarityBrain: production Water Clarity as a Sector Brain.

An additive adapter. It reads what production Clarity already produces and
restates it in the Brain Platform contract. It changes no science:

  Sector Engine /conditions.clarityVisibility   the customer clarity estimate
      (secchi-power-v1 from a USGS turbidity gauge, else rain-decay-v0)
  gs://sector-lake-surface (lake-surface-daily)  the nightly Sentinel-2 pass:
      turbidity field, map rasters, pass metadata (evidence; no client reads it yet)

and builds, per canonical lake:

  WaterClarityProfile  how Sector understands clarity on this lake
  WaterClarityState    what the Brain believes is happening now (BrainResult payload)

plus the fleet-level registry, health, validation and source records.

R3.1 is represented as a certified candidate in the model catalog. It never
produces a published state here: it is not running in production.

Every function in this module is pure (no network); run.py does the I/O.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

from brain_platform import SCHEMA_VERSION, age_hours, event_id, freshness, iso, lake_key, parse_time

HERE = os.path.dirname(os.path.abspath(__file__))


def merge_catalog(base: dict, overlay: dict) -> dict:
    """Deep merge: dicts recurse, model lists merge by modelId, anything else is replaced."""
    out = dict(base)
    for k, v in overlay.items():
        if k.startswith("_"):
            continue
        b = out.get(k)
        if isinstance(b, dict) and isinstance(v, dict):
            out[k] = merge_catalog(b, v)
        elif isinstance(b, list) and isinstance(v, list) and all(isinstance(x, dict) and "modelId" in x for x in b + v):
            by = {x["modelId"]: x for x in v}
            out[k] = [merge_catalog(x, by[x["modelId"]]) if x["modelId"] in by else x for x in b]
        else:
            out[k] = v
    return out


def _read_overlay(uri: str) -> dict:
    if uri.startswith("gs://"):                       # private bucket, read with the job's own credential
        import urllib.parse, urllib.request
        from brain_platform import TokenProvider
        bucket, _, obj = uri[5:].partition("/")
        url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{urllib.parse.quote(obj, safe='')}?alt=media"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TokenProvider().token()}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    return json.load(open(uri))


def verified_release() -> dict:
    """Approved memory (Cortex BR-11): the packaged knowledge release (knowledge-release.json: catalog.json with its digest). Raises
    KnowledgeReleaseError when it is missing, unreadable or tampered: the run stops, nothing falls back to an unversioned catalog."""
    import brain_platform  # noqa: F401  (resolves the shared platform package: repo layout or staged image)
    from sector_brain_platform.knowledge_release import load_release
    return load_release(HERE, "water-clarity")


def load_catalog() -> tuple[dict, str]:
    """Public catalog (in git) plus the optional private overlay that carries the detailed
    research results kept out of the public repo: $CLARITY_PRIVATE_CATALOG (path or gs:// URI),
    else catalog.private.json beside this file (gitignored). Without it the Brain publishes
    status-level candidate facts only. The public catalog is read only after its release verifies; the private overlay is optional detail
    and degrades explicitly (PRIVATE_OVERLAY_UNAVAILABLE)."""
    verified_release()
    cat = json.load(open(os.path.join(HERE, "catalog.json")))
    uri = os.environ.get("CLARITY_PRIVATE_CATALOG") or (
        os.path.join(HERE, "catalog.private.json") if os.path.exists(os.path.join(HERE, "catalog.private.json")) else None)
    if not uri:
        return cat, "PUBLIC_ONLY"
    try:
        return merge_catalog(cat, _read_overlay(uri)), "PRIVATE_OVERLAY_LOADED"
    except Exception:
        return cat, "PRIVATE_OVERLAY_UNAVAILABLE"


CATALOG, CATALOG_DETAIL = load_catalog()
RELEASE = verified_release()

BRAIN_ID = CATALOG["brainId"]
SLOT = CATALOG["slot"]
BRAIN_VERSION = CATALOG["brainVersion"]
STALE_AFTER_H = CATALOG["staleAfterHours"]
SAT_FRESH_DAYS = CATALOG["satelliteFreshDays"]
BUCKET_URL = "https://storage.googleapis.com/sector-lake-surface"

# secchi-power-v1 (Sources/SectorEngine/Hydrology/VisibilityModel.swift): compiled
# defaults; Remote Config conditions_config carried no clarity override on 2026-10-12.
SECCHI_A, SECCHI_B = 11.123, -0.637
SAT_RANGE_LOG10 = (-0.356, 0.520)          # satelliteObserved 80% range, n = 905

STATE_TYPE_BY_SOURCE = {"inSituGauge": "GAUGE_OBSERVED", "rainDecayModel": "RAINFALL_MODELED", "noRainData": "FALLBACK_NEUTRAL"}
READINESS_BY_STATE = {"GAUGE_OBSERVED": "PRODUCTION", "RAINFALL_MODELED": "BETA", "FALLBACK_NEUTRAL": "DEGRADED", "UNAVAILABLE": "DEGRADED"}
TREND_BY_TURBIDITY = {"rising": "WORSENING", "falling": "IMPROVING", "steady": "STABLE"}
LAYER_LABELS = {"clarity": ("clarity", "Clarity"), "measured": ("satellite-footprint", "Satellite footprint"),
                "distance": ("distance-to-reading", "Distance to reading"), "ndci": ("algal-ndci", "Algal (NDCI)")}
LAYER_FIELDS = {  # published once, in the registry's layerCatalog: what each raster encodes
    "clarity": {"field": "TURBIDITY", "unit": "FNU", "encoding": "LOG10_UINT8", "coverage": "READ_AND_FILLED"},
    "measured": {"field": "READ_MASK", "unit": None, "encoding": "UINT8_MASK", "coverage": "READ_ONLY"},
    "distance": {"field": "DISTANCE_TO_READ_CELL", "unit": "m", "encoding": "UINT8", "coverage": "READ_AND_FILLED"},
    "ndci": {"field": "NDCI", "unit": None, "encoding": "UINT8", "coverage": "CURRENT_CLARITY_REGIONS"},
}
SAT_PATH = "lake-surface-l2a-red"
SAT_AUTHORITY = CATALOG["sensorAuthority"]["byProcessingPath"][SAT_PATH]["sensors"]
PLATFORM_SENSOR = {"sentinel-2a": "S2A", "sentinel-2b": "S2B", "sentinel-2c": "S2C"}
CANDIDATE = next(m for m in CATALOG["models"] if m["modelId"] == CATALOG["candidateModel"]["modelId"])


def lake_surface_outcome(status: str | None) -> str:
    """Bucket run-record status -> outcome. 'no usable pass' is a cloudy window, not a failure."""
    s = str(status or "")
    if s.startswith("error"):
        return "error"
    if s.startswith("no usable pass"):
        return "noUsablePass"
    if s.startswith("no pass in the window"):
        return "noPassInWindow"
    if s.startswith("published"):
        return "published"
    return "upToDate"          # "up to date", "newest usable pass ... already published"


def _r(x, n=2):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), n)


# ---------------------------------------------------------------- adapters
def engine_estimate(cond: dict | None, lake_id: str) -> dict:
    """Restate /conditions clarity fields; no value is recomputed."""
    if not cond or not cond.get("clarityVisibility"):
        return {"stateType": "UNAVAILABLE"}
    v = cond["clarityVisibility"]
    try:
        central = float(v.get("centralFt"))
    except (TypeError, ValueError):
        central = float("nan")
    if not isinstance(v, dict) or v.get("source") not in STATE_TYPE_BY_SOURCE or not math.isfinite(central):
        return {"stateType": "UNAVAILABLE", "malformed": f"clarityVisibility source={v.get('source')!r} centralFt={v.get('centralFt')!r}"}
    rain = cond.get("clarityRain") or {}
    gauges = cond.get("clarityGauges") or []
    driving_turb = next((g for g in gauges if g.get("role") == "turbidity" and g.get("driving")), None)
    st = STATE_TYPE_BY_SOURCE.get(v.get("source"), "UNAVAILABLE")
    if rain.get("source") == "mrms":
        rain72, rain_src, window = rain.get("watershed72hIn"), "MRMS_WATERSHED_72H", 72
    elif st == "RAINFALL_MODELED":
        rain72, rain_src, window = None, "OPEN_METEO_POINT_48H", 48   # the 48 h value is only inside engine provenance text
    else:
        rain72, rain_src, window = None, None, None
    trend, trend_basis = "UNKNOWN", None
    if st == "GAUGE_OBSERVED" and driving_turb and driving_turb.get("trend") in TREND_BY_TURBIDITY:
        trend = TREND_BY_TURBIDITY[driving_turb["trend"]]
        trend_basis = {"sourceType": "usgsTurbidityGauge", "sourceId": f"USGS:{driving_turb.get('siteCode')}",
                       "gaugeTrend": driving_turb["trend"], "relation": "INVERSE"}
    resolved = (cond.get("resolvedLake") or {}).get("id")
    return {
        "stateType": st,
        "clarityFt": _r(v.get("centralFt")), "lowFt": _r(v.get("lowFt")), "highFt": _r(v.get("highFt")),
        "trend": trend, "trendBasis": trend_basis,
        "recentRainfallIn72h": _r(rain72), "rainfallSource": rain_src, "rainfallWindowHours": window,
        "rainfallLatestDay": ((rain.get("daily") or [{}])[-1] or {}).get("date"),
        "engine": {"model": v.get("model"), "source": v.get("source"), "confidenceLabel": v.get("confidence"),
                   "provenance": v.get("provenance"), "limitations": list(v.get("limitations") or []),
                   "evaluatedAt": cond.get("generatedAt"), "resolvedLakeId": resolved},
        "gauges": [{"siteCode": g.get("siteCode"), "role": g.get("role"), "parameterCode": g.get("parameterCode"),
                    "trend": g.get("trend"), "driving": bool(g.get("driving"))} for g in gauges],
        "resolvedLakeMismatch": resolved is not None and resolved != lake_id,
        "resolvedLakeMissing": resolved is None,
    }


def satellite_evidence(latest: dict | None, meta: dict | None, has_polygon: bool, pass_count: int | None,
                       now: dt.datetime) -> dict:
    """Restate the newest published lake-surface pass; FNU -> ft only via secchi-power-v1."""
    if not has_polygon:
        return {"status": "UNSUPPORTED", "inCustomerEstimate": False, "reasonCode": "NO_LAKE_OUTLINE", "processingPathId": SAT_PATH}
    s = (latest or {}).get("summary")
    if not s:
        return {"status": "NONE", "inCustomerEstimate": False, "reasonCode": "NO_PUBLISHED_PASS", "processingPathId": SAT_PATH}
    obs_at = s.get("time") or (s.get("date") + "T00:00:00Z" if s.get("date") else None)
    age = age_hours(obs_at, now)
    status = "FRESH" if age is not None and age <= SAT_FRESH_DAYS * 24 else "STALE"
    p50 = s.get("fnuP50")
    vis = None
    if p50 is not None:
        c = SECCHI_A * max(float(p50), 0.1) ** SECCHI_B
        vis = {"centralFt": _r(c), "lowFt": _r(c * 10 ** SAT_RANGE_LOG10[0]), "highFt": _r(c * 10 ** SAT_RANGE_LOG10[1]),
               "model": "secchi-power-v1", "source": "satelliteObserved",
               "basisCode": "LAKE_MEDIAN_FNU_OF_READ_CELLS", "rangeQuantiles": [0.1, 0.9], "rangeValidationPairs": 905}
    pas = (meta or {}).get("pass") or {}
    return {
        "status": status, "freshWithinDays": SAT_FRESH_DAYS, "inCustomerEstimate": False,
        "observedAt": obs_at, "ageHours": age, "date": s.get("date"), "platform": s.get("platform"),
        "sceneIds": pas.get("sceneIds"), "coveragePct": s.get("measuredPct"), "openWaterReadPct": s.get("openWaterReadPct"),
        "grassPct": s.get("grassPct"), "fnu": {"p25": s.get("fnuP25"), "p50": p50, "p75": s.get("fnuP75")},
        "visibilityAtMedianFnu": vis, "passCount": pass_count, "publishedAt": (latest or {}).get("publishedAt"),
        "productId": "lake-surface-daily", "modelId": "lake-surface-s2-fnu", "processingPathId": SAT_PATH,
        "authority": SAT_AUTHORITY.get(PLATFORM_SENSOR.get(s.get("platform"))),
    }


def map_layers(latest: dict | None, meta: dict | None) -> tuple[list, dict | None]:
    files = (latest or {}).get("files") or {}
    s = (latest or {}).get("summary") or {}
    out = []
    for name in ("clarity", "measured", "distance", "ndci"):
        if name in files:
            lid, label = LAYER_LABELS[name]
            out.append({"id": lid, "label": label, "url": f"{BUCKET_URL}/{files[name]}", "observedAt": s.get("time"),
                        "kind": "encoded-data", "field": LAYER_FIELDS[name]["field"]})
    geo = None
    if meta and out:
        geo = {"projection": meta.get("projection"), "corners": meta.get("coordinates"), "pixelWidth": meta.get("pixelWidth"),
               "pixelHeight": meta.get("pixelHeight"), "cellMetres": meta.get("cellMetresMercator"), "encoding": meta.get("encoding"),
               "field": meta.get("field"), "unit": meta.get("unit"), "metaUrl": f"{BUCKET_URL}/{files['meta']}" if files.get("meta") else None}
    return out, geo


# ---------------------------------------------------------------- per-lake results
def quality_flags(est: dict, sat: dict) -> list[str]:
    f = []
    st = est.get("stateType")
    if st == "UNAVAILABLE":
        f.append("engineUnavailable")
    if st == "FALLBACK_NEUTRAL":
        f.append("noMeasurement")
    if st == "RAINFALL_MODELED":
        f.append("uncalibratedModel:rain-decay-v0")
        if est.get("rainfallSource") == "OPEN_METEO_POINT_48H":
            f.append("rainfallFallback:open-meteo-48h")
    if st == "GAUGE_OBSERVED" and est.get("lowFt") is None:
        f.append("noValidatedRange:algal")
    if est.get("resolvedLakeMismatch"):
        f.append(f"resolvedLakeMismatch:{est['engine']['resolvedLakeId']}")
    if sat["status"] == "STALE":
        f.append(f"satelliteStale:{(sat.get('ageHours') or 0) / 24:.0f}d>{SAT_FRESH_DAYS}d")
    elif sat["status"] in ("NONE", "UNSUPPORTED"):
        f.append(f"satellite{sat['status'].title()}")
    return f


STRONG_NOT_EVALUATED = {
    "state": "NOT_EVALUATED", "evaluated": False, "strong": None, "evidenceCount": None, "fullAuthorityEvidenceCount": None,
    "consensusWindowDays": None, "authority": None,
    "policyId": CATALOG["strongPolicy"]["policyId"], "policyVersion": CATALOG["strongPolicy"]["policyVersion"],
    "reasonCode": "ACTIVE_MODEL_HAS_NO_MULTI_SCENE_CONSENSUS",
}
CANDIDATE_REF = {"modelId": CANDIDATE["modelId"], "lifecycle": CANDIDATE["lifecycle"], "certificationStatus": CANDIDATE["certificationStatus"],
                 "deploymentStatus": CANDIDATE["deploymentStatus"], "publishesLakeState": False,
                 "researchScore": CANDIDATE.get("researchScore"), "certificationRef": CANDIDATE.get("certificationRef")}


# Contract §3 state kind beside the brain-specific stateType (Ops still reads stateType).
KIND_OF = {"GAUGE_OBSERVED": "observed", "RAINFALL_MODELED": "modeled", "FALLBACK_NEUTRAL": "modeled", "UNAVAILABLE": "unavailable"}
# The shared Brain Platform this brain publishes through (contract §13; Engine Score reads it).
PLATFORM = {"implementation": "sector_brain_platform", "contract": "docs/brains/BRAIN_PLATFORM_CONTRACT.md v1.0", "conformant": True}


def build_state(lake_id: str, est: dict, sat: dict, layers: list, layer_geo: dict | None, now: dt.datetime,
                engine_revision: str | None) -> dict:
    st = est["stateType"]
    readiness = READINESS_BY_STATE[st]
    flags = quality_flags(est, sat)
    eng = est.get("engine") or {}
    sources = []
    if eng.get("evaluatedAt"):
        sources.append({"sourceType": "sectorEngineConditions", "sourceId": "sector-engine:/conditions", "lastObservationAt": eng["evaluatedAt"]})
    for g in est.get("gauges") or []:
        if g["driving"]:
            sources.append({"sourceType": "usgsTurbidityGauge" if g["role"] == "turbidity" else "usgsDischargeGauge",
                            "sourceId": f"USGS:{g['siteCode']}", "lastObservationAt": None})
    if est.get("rainfallSource"):
        mrms = est["rainfallSource"] == "MRMS_WATERSHED_72H"
        sources.append({"sourceType": "mrmsRain" if mrms else "openMeteoRain", "sourceId": "NOAA-MRMS" if mrms else "Open-Meteo",
                        "lastObservationAt": est.get("rainfallLatestDay")})
    if sat.get("observedAt"):
        sources.append({"sourceType": "sentinel2L2A", "sourceId": (sat.get("sceneIds") or [f"S2:{sat.get('platform')}:{sat.get('date')}"])[0],
                        "lastObservationAt": sat["observedAt"]})
    provenance = {
        "brainId": BRAIN_ID, "brainVersion": BRAIN_VERSION, "modelVersion": eng.get("model"),
        "processingVersion": engine_revision, "generatedAt": iso(now), "sources": sources,
        "inputAgeHours": age_hours(eng.get("evaluatedAt"), now), "readiness": readiness,
        "qualityFlags": flags, "validationRef": f"/validation/{BRAIN_ID}",
    }
    return {
        "lakeId": lake_id, "schemaVersion": SCHEMA_VERSION, "brainId": BRAIN_ID, "brainVersion": BRAIN_VERSION,
        "generatedAt": iso(now), "evaluationTime": eng.get("evaluatedAt"),
        "stateType": st, "kind": KIND_OF[st], "basis": CATALOG["stateTypes"][st]["basis"], "readiness": readiness,
        "freshness": freshness(now, now, STALE_AFTER_H, "TIME", evidence_stale=(st == "UNAVAILABLE"),
                               evidence_reasons=["no usable clarity input this run"]),
        "processingPathId": "engine-conditions",
        "clarityFt": est.get("clarityFt"), "lowFt": est.get("lowFt"), "highFt": est.get("highFt"),
        "clarityUnit": "ft", "clarityQuantity": "SECCHI_EQUIVALENT_VISIBILITY",
        "clarityClass": None,                       # production has no clarity class taxonomy
        "trend": est.get("trend", "UNKNOWN"), "trendBasis": est.get("trendBasis"),
        "recentRainfallIn72h": est.get("recentRainfallIn72h"), "rainfallSource": est.get("rainfallSource"),
        "rainfallWindowHours": est.get("rainfallWindowHours"),
        "engine": {k: eng.get(k) for k in ("model", "source", "confidenceLabel", "provenance", "limitations", "resolvedLakeId")} if eng else None,
        "gauges": est.get("gauges") or None,
        "satelliteObservationAt": sat.get("observedAt"), "satelliteAgeHours": sat.get("ageHours"),
        "spatialCoveragePct": sat.get("coveragePct"), "satellite": sat,
        "mapLayerAvailable": bool(layers), "mapLayerVersion": sat.get("date") if layers else None,
        "layers": layers or None, "layerGeometry": layer_geo,
        "strong": STRONG_NOT_EVALUATED,
        "activeModel": eng.get("model"),
        "candidateModel": CANDIDATE_REF,
        "authority": {"customerEstimate": "NOT_APPLICABLE", "satelliteEvidence": sat.get("authority"),
                      "satelliteProcessingPathId": SAT_PATH},
        "sensorAuthorityRef": f"/brains/{BRAIN_ID}/sensorAuthority",
        "stale": False,
        "provenance": provenance,
    }


def build_profile(lake: dict, est: dict, sat: dict, has_polygon: bool, now: dt.datetime) -> dict:
    st = est["stateType"]
    eng = est.get("engine") or {}
    turb = [g for g in est.get("gauges") or [] if g["role"] == "turbidity"]
    disch = [g for g in est.get("gauges") or [] if g["role"] == "discharge" and g["driving"]]
    rain_in = [est["rainfallSource"]] if est.get("rainfallSource") else []
    if disch:
        rain_in.append("USGS_ARM_DISCHARGE_12H")
    model = eng.get("model")
    validation = {"secchi-power-v1": "VALIDATED_NATIONALLY", "rain-decay-v0": "NOT_VALIDATED"}.get(model) if model else None
    codes = []
    if model == "rain-decay-v0":
        codes.append("UNCALIBRATED_MODEL")
    if st != "UNAVAILABLE":
        codes.append("SINGLE_POINT_ESTIMATE")
    if sat["status"] in ("FRESH", "STALE"):
        codes.append("SATELLITE_NOT_IN_CUSTOMER_ESTIMATE")
    return {
        "lakeId": lake["id"], "brainId": BRAIN_ID, "schemaVersion": SCHEMA_VERSION, "profileVersion": 1, "updatedAt": iso(now),
        "activeModels": CATALOG["activeModel"]["modelIds"],
        "modelVersion": model,
        "lakeClarityClass": None, "hydrologicClass": None,
        "geometryReady": has_polygon,
        "satelliteSupported": has_polygon, "sentinel2Supported": has_polygon, "landsatSupported": False,
        "satelliteAvailable": sat["status"] in ("FRESH", "STALE"),
        "weatherRunoffInputs": rain_in or None,
        "precipitationInputsAvailable": bool(est.get("rainfallSource")),
        "runoffInputsAvailable": bool(disch),
        "observationSources": [{"sourceKind": "usgsTurbidityGauge", "sourceId": f"USGS:{g['siteCode']}", "driving": g["driving"]} for g in turb] or None,
        "observationSourceIds": [f"USGS:{g['siteCode']}" for g in turb] or None,
        "historicalObservationCount": {"satellitePasses": sat.get("passCount"), "inSituSecchi": None},
        "sourceCoverage": {"inSituTurbidity": any(g["driving"] for g in turb), "rainfall": est.get("rainfallSource"),
                           "satellite": sat["status"]},
        "spatialModelSupported": sat["status"] in ("FRESH", "STALE"),
        "mapLayerSupported": sat["status"] in ("FRESH", "STALE"),
        "validationStatus": validation,
        "readiness": READINESS_BY_STATE[st],
        "candidateModel": {**CANDIDATE_REF, "perLakeOutput": None},
        "limitationCodes": codes or None,
        "engineLimitations": list(eng.get("limitations") or []) or None,
        "validation": {"ref": f"/validation/{BRAIN_ID}"},
    }


def lake_writes(lake_id: str, profile: dict | None, state: dict | None, now: dt.datetime, error: str | None = None) -> dict:
    """Leaf-path updates for one lake. Nodes other brains share are written leaf by leaf."""
    k = lake_key(lake_id)
    # Fleet-level lastUpdatedAt / snapshot generatedAt + snapshotVersion are Orchestrator rollups
    # (Brain Platform contract §5): this brain writes only its own slot and snapshot field.
    w = {f"/lakeFleet/{k}/lakeId": lake_id}
    if state is not None:
        w[f"/lakes/{k}/states/{SLOT}"] = state
        w[f"/snapshots/{k}/latest/lakeId"] = lake_id
        w[f"/snapshots/{k}/latest/{CATALOG['snapshotField']}"] = state
        w[f"/snapshots/{k}/latest/brainVersions/{BRAIN_ID}"] = BRAIN_VERSION
        w[f"/lakeFleet/{k}/readiness/{SLOT}"] = state["provenance"]["readiness"]
        w[f"/lakeFleet/{k}/modelVersions/{SLOT}"] = state["provenance"]["modelVersion"]
        w[f"/lakeFleet/{k}/slots/{SLOT}"] = {
            "readiness": state["provenance"]["readiness"], "stateType": state["stateType"], "kind": state["kind"], "stale": False,
            "issueCount": sum(1 for f in state["provenance"]["qualityFlags"] if not f.startswith("uncalibratedModel")),
            "lastUpdatedAt": iso(now), "lastErrorAt": None, "satellite": state["satellite"]["status"]}
    if profile is not None:
        w[f"/lakes/{k}/profiles/{SLOT}"] = profile
    if error is not None and state is None:
        w[f"/lakeFleet/{k}/slots/{SLOT}/lastErrorAt"] = iso(now)
        w[f"/lakeFleet/{k}/slots/{SLOT}/lastError"] = error[:200]
    return w


def stale_carry(lake_id: str, prev_slot: dict | None, now: dt.datetime) -> dict:
    """A lake the engine missed this run keeps its last state; mark it stale when old."""
    k = lake_key(lake_id)
    last = parse_time((prev_slot or {}).get("lastUpdatedAt"))
    stale = last is None or (now - last).total_seconds() / 3600 > STALE_AFTER_H
    return {f"/lakeFleet/{k}/slots/{SLOT}/stale": stale}


# ---------------------------------------------------------------- fleet records
def registry_entry(results: dict, prev_fleet: dict, now: dt.datetime, health: str, last_error: dict | None,
                   engine_revision: str | None, lake_ids: list, last_success: str | None) -> dict:
    states = {lid: r["state"] for lid, r in results.items() if r.get("state")}
    readiness_counts, breakdowns = {}, {"stateType": {}, "engineModel": {}, "satellite": {}, "satellitePlatform": {}, "rainfall": {}}

    def bump(d, k):
        if k is not None:
            d[k] = d.get(k, 0) + 1
    stale = 0
    for lid in lake_ids:
        s = states.get(lid)
        if s is None:
            slot = ((prev_fleet.get(lake_key(lid)) or {}).get("slots") or {}).get(SLOT)
            if slot:
                bump(readiness_counts, slot.get("readiness"))
                last = parse_time(slot.get("lastUpdatedAt"))
                if last is None or (now - last).total_seconds() / 3600 > STALE_AFTER_H:
                    stale += 1
            continue
        bump(readiness_counts, s["provenance"]["readiness"])
        bump(breakdowns["stateType"], s["stateType"])
        bump(breakdowns["engineModel"], (s.get("engine") or {}).get("model"))
        bump(breakdowns["satellite"], s["satellite"]["status"])
        bump(breakdowns["satellitePlatform"], s["satellite"].get("platform"))
        rs = s.get("rainfallSource")
        bump(breakdowns["rainfall"], rs or "NONE")
    c = CATALOG
    # contract `versions[]` (Model versions tab): status CURRENT | SHADOW | CANDIDATE, from lifecycle
    vstatus = {"PRODUCTION": "CURRENT", "PRODUCTION_EVIDENCE": "CURRENT", "CANDIDATE": "CANDIDATE", "SHADOW": "SHADOW", "REVIEW": "SHADOW", "RETIRED": "RETIRED"}
    cert_dates = {v["modelId"]: v.get("certifiedAt") for v in c["certifications"].values()}
    versions = [{"version": m["modelId"], "date": m.get("since") or cert_dates.get(m["modelId"]) or "", "note": None,
                 "status": vstatus[m["lifecycle"]], "lifecycle": m["lifecycle"]} for m in c["models"]]
    return {
        "brainId": BRAIN_ID, "displayName": c["displayName"], "domain": c["domain"], "question": c["question"],
        "platform": PLATFORM,
        "stalenessModel": "TIME", "dependsOn": [],
        "schedule": {"cadence": "manual (deploy-job.sh not run; Orchestrator will own cadence)", "jobId": "water-clarity-brain", "running": False},
        "descriptor": {"components": {"clarityState": {"status": "ACTIVE (mirror of production /conditions clarity)",
                                                      "inputs": ["sector-engine /conditions (621 lakes)", "gs://sector-lake-surface lakes/<slug>/clarity/latest.json + meta"],
                                                      "staleness": f"time-based: staleAfterHours {STALE_AFTER_H}",
                                                      "recomputeWhen": ["published state older than staleAfterHours", "lake-surface-daily published a new pass", "brain or catalog version changed"]}}},
        "version": BRAIN_VERSION, "schemaVersion": SCHEMA_VERSION, "enabled": True, "health": health,
        "status": c["brainStatus"], "statusReasons": c["brainStatusReasons"],
        "supportedLakeCount": len(lake_ids), "readinessCounts": readiness_counts, "staleLakeCount": stale,
        "staleAfterHours": STALE_AFTER_H, "lastSuccessfulRun": last_success, "lastError": last_error,
        "deploymentVersion": engine_revision, "breakdowns": breakdowns, "versions": versions, "runsPerMinute": None,
        "activeModel": {**c["activeModel"], "engineRevision": engine_revision},
        "candidateModel": CANDIDATE_REF,
        "modelRoster": c["models"], "certifications": c["certifications"], "processingPaths": c["processingPaths"],
        "sensorAuthority": c["sensorAuthority"], "strongPolicy": c["strongPolicy"],
        "readinessRule": c["readinessRule"], "stateTypes": c["stateTypes"], "vocabularies": c["vocabularies"],
        "satelliteFreshDays": SAT_FRESH_DAYS, "updatedAt": iso(now), "catalogDetail": CATALOG_DETAIL,
        "layerCatalog": {LAYER_LABELS[k][0]: {"kind": "encoded-data", **v} for k, v in LAYER_FIELDS.items()},
    }


def run_health(n_lakes: int, n_ok: int, n_fail: int, sat_job_ok: bool | None, aborted: bool) -> str:
    """Operational status of one Brain run (ops thresholds, not science)."""
    if aborted:
        return "FAILED"
    if n_lakes == 0:
        return "UNKNOWN"
    ok = n_ok / n_lakes
    if ok < 0.80:
        return "DEGRADED"
    if ok < 0.95 or sat_job_ok is False:
        return "WARNING"
    return "HEALTHY"


def source_records(results: dict, now: dt.datetime, lake_surface_run: dict | None) -> dict:
    states = [r["state"] for r in results.values() if r.get("state")]
    out = {}
    s2 = [s["satellite"] for s in states if s["satellite"]["status"] in ("FRESH", "STALE")]
    newest = max((x["observedAt"] for x in s2 if x.get("observedAt")), default=None)
    fresh = sum(1 for x in s2 if x["status"] == "FRESH")
    run_errors = (lake_surface_run or {}).get("errors")
    s2_health = "UNKNOWN" if not s2 else "HEALTHY" if fresh >= 0.8 * len(s2) else "WARNING" if fresh >= 0.5 * len(s2) else "DEGRADED"
    out["sentinel-2-l2a"] = {"lakeCount": len(s2), "health": s2_health, "lastFetchAt": (lake_surface_run or {}).get("finishedAt"),
                             "latestObservationAt": newest, "failures24h": run_errors, "notes": None,
                             "coverage": {"lakesWithPass": len(s2), "lakesFresh": fresh, "freshWithinDays": SAT_FRESH_DAYS},
                             "lastRunOutcomes": (lake_surface_run or {}).get("outcomes")}
    turb = sum(1 for s in states if s["stateType"] == "GAUGE_OBSERVED")
    out["usgs-nwis-turbidity"] = {"lakeCount": turb, "health": "HEALTHY" if turb else "UNKNOWN", "lastFetchAt": iso(now),
                                  "latestObservationAt": None, "failures24h": None, "notes": None,
                                  "coverage": {"lakesDrivingCustomerEstimate": turb}, "observationTimesAvailable": False}
    rained = [s for s in states if s["stateType"] == "RAINFALL_MODELED"]
    mrms = sum(1 for s in rained if s.get("rainfallSource") == "MRMS_WATERSHED_72H")
    out["noaa-mrms"] = {"lakeCount": mrms, "health": "UNKNOWN" if not rained else "HEALTHY" if mrms >= 0.8 * len(rained) else "WARNING",
                        "lastFetchAt": iso(now), "latestObservationAt": None, "failures24h": None, "notes": None,
                        "coverage": {"lakesRainModeled": len(rained), "lakesMrms": mrms, "lakesOpenMeteoFallback": len(rained) - mrms}}
    recs = {}
    for sid, rec in out.items():
        meta = CATALOG["sources"][sid]
        recs[sid] = {"sourceId": sid, "provider": meta["provider"], "type": meta["type"], "ownerBrainId": BRAIN_ID, "brains": {BRAIN_ID: True},
                     "provides": meta["provides"], "processingPathId": meta["processingPathId"],
                     "staleThresholdHours": meta["staleThresholdHours"], "latencyMs": None, **rec}
    return recs


def activity_events(prev_registry: dict | None, prev_fleet: dict, results: dict, now: dt.datetime,
                    run_status: str, max_lake_events: int = 15) -> dict:
    ev, n = {}, 0

    def add(kind, title, severity, lake_id=None):
        nonlocal n
        n += 1
        e = {"id": event_id(now, BRAIN_ID, n), "at": iso(now), "kind": kind, "title": title, "brainId": BRAIN_ID, "severity": severity}
        if lake_id:
            e["lakeId"] = lake_id
        ev[e["id"]] = e
    if not prev_registry:
        add("brain.registered", f"Water Clarity Brain registered (v{BRAIN_VERSION})", "info")
    elif prev_registry.get("version") != BRAIN_VERSION:
        add("brain.version", f"Water Clarity Brain v{prev_registry.get('version')} -> v{BRAIN_VERSION}", "info")
    if run_status in ("FAILED", "DEGRADED"):
        add("run.failed" if run_status == "FAILED" else "run.degraded", f"Water Clarity run {run_status.lower()}", "critical" if run_status == "FAILED" else "warning")
    changes = []
    for lid, r in results.items():
        s = r.get("state")
        if not s:
            continue
        prev = (((prev_fleet.get(lake_key(lid)) or {}).get("slots") or {}).get(SLOT) or {}).get("readiness")
        cur = s["provenance"]["readiness"]
        if prev and prev != cur:
            changes.append((lid, prev, cur))
    for lid, a, b in sorted(changes)[:max_lake_events]:
        promo = ["DISCOVERED", "PROFILED", "CALIBRATION", "BETA", "VALIDATED", "PRODUCTION"]
        up = b in promo and a in promo and promo.index(b) > promo.index(a)
        add("readiness.promoted" if up else "readiness.changed", f"{lid}: clarity readiness {a} -> {b}", "success" if up else "warning", lid)
    if len(changes) > max_lake_events:
        add("readiness.changed", f"{len(changes) - max_lake_events} more lakes changed clarity readiness", "info")
    return ev


def prune_activity(activity: dict | None, now: dt.datetime, keep: int = 200, max_age_days: int = 30) -> dict:
    """Deletes for this brain's own old events only (other brains prune their own)."""
    mine = sorted(((k, e) for k, e in (activity or {}).items() if (e or {}).get("brainId") == BRAIN_ID),
                  key=lambda kv: kv[1].get("at") or "")
    cutoff = now - dt.timedelta(days=max_age_days)
    drop = {k for k, e in mine if (parse_time(e.get("at")) or now) < cutoff}
    drop |= {k for k, _ in mine[:-keep]} if len(mine) > keep else set()
    return {f"/activity/{k}": None for k in drop}
