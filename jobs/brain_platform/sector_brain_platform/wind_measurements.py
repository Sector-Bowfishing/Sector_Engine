"""Wind's three measurements, evaluated by the PLATFORM scorer (the only scoring authority; Wind never publishes a score).

  WIND CAPABILITY           wind-specialist-capability-v2 (PROPOSED): what Wind, as the wind SPECIALIST, can demonstrably
                            calculate, interpret and assess. A number, with its MEASURED_SKILL and MODEL_CAPABILITY points always
                            reported separately. It scores no cross-Brain bowfishing recommendation (Sector Intelligence owns those).
  SCIENTIFIC CONFIDENCE     wind-scientific-confidence-v1: how thoroughly the outputs are validated. Evidence STATUSES, no number
                            (no defensible single confidence metric exists; a number would hide the 0 field observations).
  PRODUCTION READINESS      wind-production-readiness-v1: operational maturity, from facts that already exist (brain.json,
                            certification dims 8-10, health, publisher cutover). Gates and statuses, no new readiness number.

The certification score (`wind-certification-rubric-v1`, frozen block in frozen-scores.json) and BWIS v1 are carried VERBATIM and
never recomputed here. Inputs: the frozen Wind block, docs/brains/scoring/evidence/wind-measurements-evidence.json, the rubric JSON,
brains/wind/brain.json and (optionally) RTDB health facts. Pure functions; no I/O except the explicit loaders.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

from .timeutil import iso

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUBRIC_PATH = os.path.join(ROOT, "docs", "brains", "scoring", "wind-specialist-capability-v2.json")
EVIDENCE_PATH = os.path.join(ROOT, "docs", "brains", "scoring", "evidence", "wind-measurements-evidence.json")
BRAIN_JSON = os.path.join(ROOT, "brains", "wind", "brain.json")
GAPS_PATH = os.path.join(ROOT, "brains", "wind", "research", "GAPS.json")

ENVELOPE = "wind-score-measurements-v1"
CAP_VERSION = "wind-specialist-capability-v2"
SC_VERSION = "wind-scientific-confidence-v1"
PR_VERSION = "wind-production-readiness-v1"
CERT_VERSION = "wind-certification-rubric-v1"
EVIDENCE_SCHEMA = "wind-measurements-evidence-v1"
TARGET = 7.0
CUTOVER_SEQUENCE = ("water-clarity", "biological-state", "wind")      # approved Publisher cutover order; Wind is last
_LOCAL = re.compile(r"/Users/|~/Desktop|Desktop/Development|Library/Caches|Sector Research")

# rubric item -> research gap that improves it (brains/wind/research/GAPS.json)
ITEM_GAP = {"WI1": "WIND-CNF-001", "WI2": "WIND-CNF-003", "WI3": "WIND-CNF-001", "WI4": "WIND-CNF-001", "EA1": "WIND-CNF-001",
            "SI1": "WIND-CNF-002", "SI2": "WIND-CNF-002", "TI3": "WIND-CNF-002"}


def load(path):
    return json.load(open(path))


def lin(x, zero, full):
    if x is None:
        return 0.0
    if full > zero:
        return max(0.0, min(1.0, (x - zero) / (full - zero)))
    return max(0.0, min(1.0, (zero - x) / (zero - full)))


# ---------------------------------------------------------------- evidence admission
def evidence_problems(ev: dict | None, rubric: dict) -> list[str]:
    """Reasons the evidence cannot be scored (empty = admissible). Inadmissible evidence is HELD, never partially used."""
    if not ev:
        return ["no evidence file"]
    p = []
    if ev.get("schema") != EVIDENCE_SCHEMA:
        p.append(f"evidence schema {ev.get('schema')!r} != {EVIDENCE_SCHEMA}")
    if ev.get("brainId") != "wind":
        p.append("evidence is not Wind's")
    if not str(ev.get("knowledgeVersion", "")).startswith("wind-exposure-assessment-"):
        p.append("evidence has no exposure-assessment knowledgeVersion")
    if (ev.get("atmospheric") or {}).get("h2Read") is not False:
        p.append("atmospheric evidence does not attest H2 unread")
    sc = ev.get("scenarios") or {}
    if sc.get("suite") != rubric.get("scenarioSuite"):
        p.append(f"scenario suite {sc.get('suite')!r} != rubric {rubric.get('scenarioSuite')!r}")
    if sc.get("evidenceClass") != "MODEL_CAPABILITY":
        p.append("scenario evidence not classed MODEL_CAPABILITY")
    if _LOCAL.search(json.dumps(ev)):
        p.append("evidence contains a local path")
    return p


# ---------------------------------------------------------------- Wind Specialist Capability V2
def _windy(m):
    if m is None:
        return 0.0
    if m <= 0.9:
        return 1.0
    if m <= 1.35:
        return (5 - 2.5 * (m - 0.9) / 0.45) / 5
    return max(0.0, 2.5 * (2.25 - m) / 0.9) / 5


def _strong(sw):
    pod, far = (sw or {}).get("pod15mphByLead") or {}, (sw or {}).get("far15mphByLead") or {}
    if not pod or not (sw or {}).get("observedNight15mphEvents"):
        return 0.0, "no observed >= 15 mph night events: unmeasured -> 0"
    pc = min(lin(v, 0.0, 0.5) for v in pod.values())
    fc = min(1.0 if v is None else lin(v, 0.8, 0.5) for v in far.values())
    flag = (sw.get("probabilisticFlag") or {})
    note = f"; probabilistic flag {flag.get('status')} (POD {flag.get('pod')}, FAR {flag.get('far')}) not credited" if flag else ""
    return pc * fc, f"{sw['observedNight15mphEvents']} observed events, POD by lead {list(pod.values())}{note}"


def _scenario_share(ev, ids, lakes):
    res = (ev.get("scenarios") or {}).get("lakes") or {}
    n = len(ids) * len(lakes)
    ok = sum(1 for lk in lakes for s in ids if (res.get(lk) or {}).get("results", {}).get(s) is True)
    missing = [lk for lk in lakes if lk not in res]
    return (ok / n if n else 0.0), f"{ok}/{n} lake x scenario passes ({', '.join(ids)})" + (f"; missing lakes {missing}" if missing else "")


def _measured(item, ev):
    a, s, g, sw = ev.get("atmospheric") or {}, ev.get("surface") or {}, ev.get("geometry") or {}, ev.get("strongWind") or {}
    i = item["id"]
    if i == "WI1":
        v = a.get("nightSpeedMaeMS"); return lin(v, item["zero"], item["full"]), f"night MAE {v} m/s ({a.get('nNight')} rows)"
    if i == "WI2":
        v = a.get("directionWithin22_5"); return lin(v, item["zero"], item["full"]), f"within 22.5 deg {v}, circular MAE {a.get('directionCircMaeDeg')} deg"
    if i == "WI3":
        v = a.get("windyHourMaeMS"); return _windy(v), f"MAE on observed >= 10 mph hours {v} m/s ({a.get('nWindy')} rows)"
    if i == "WI4":
        return _strong(sw)
    if i == "GI1":
        c = g.get("qaChecks") or {}; return (sum(bool(v) for v in c.values()) / 4 if c else 0.0), f"{sum(bool(v) for v in c.values())}/4 QA checks pass"
    if i == "GI2":
        n, t = g.get("canonicalCasesPassed"), g.get("canonicalCasesTotal"); return (n / t if t else 0.0), f"{n}/{t} canonical cases"
    if i == "SI1":
        v = s.get("hm0MaeM"); return lin(v, item["zero"], item["full"]), f"Hm0 MAE {v} m on {s.get('buoyRows')} buoy-hours"
    if i == "SI2":
        c = min(lin(s.get("exact"), 0.20, 0.60), lin(s.get("within1"), 0.50, 0.90), lin(s.get("severe"), 0.25, 0.05)) if s else 0.0
        return c, f"exact {s.get('exact')}, within 1 {s.get('within1')}, severe {s.get('severe')}"
    if i == "EA1":
        d = a.get("surfaceClassAgreement") or {}; v = d.get("symmetricNight5mph")
        return lin(v, item["zero"], item["full"]), f"symmetric night surface-class agreement {v} (n {d.get('nSymmetric')}); observed >= 10 mph {d.get('observedNight10mph')} (reported)"
    if i == "TI3":
        t = s.get("transient") or {}; return (1.0 if t.get("m4Promoted") else 0.0), t.get("why") or "no transient evidence"
    raise KeyError(i)


def wind_capability(ev: dict, rubric: dict, now: dt.datetime) -> dict:
    problems = evidence_problems(ev, rubric)
    base = {"scoreVersion": rubric["scoreVersion"], "rubricStatus": rubric["status"], "scale": 10, "notComparableWith": rubric["notComparableWith"],
            "scoreUpdatedAt": iso(now)}
    if problems:
        return {**base, "value": None, "basis": "HELD", "heldBecause": problems}
    lakes = rubric["developmentLakes"]
    items, cats = {}, {}
    for c in rubric["categories"]:
        earned = 0.0
        for it in c["items"]:
            if it["class"] == "MODEL_CAPABILITY":
                credit, why = _scenario_share(ev, it["scenarios"], lakes)
            else:
                credit, why = _measured(it, ev)
            pts = round(it["points"] * credit, 2)
            earned += pts
            items[it["id"]] = {"label": it["label"], "category": c["id"], "class": it["class"], "credit": round(credit, 4), "points": pts,
                               "max": it["points"], "evidence": why}
        cats[c["id"]] = {"label": c["label"], "points": round(earned, 2), "max": c["weight"]}
    total = round(sum(v["points"] for v in items.values()), 2)
    cap_pts = round(sum(v["points"] for v in items.values() if v["class"] == "MODEL_CAPABILITY"), 2)
    cap_max = sum(v["max"] for v in items.values() if v["class"] == "MODEL_CAPABILITY")
    ms_pts = round(total - cap_pts, 2); ms_max = 100 - cap_max
    value = round(total / 10, 1)
    return {**base, "value": value, "basis": "COMPUTED", "rawPoints": total, "categories": cats, "items": items,
            "split": {"measuredSkill": {"points": ms_pts, "max": ms_max, "meaning": "against real observations / exact geometry"},
                      "modelCapability": {"points": cap_pts, "max": cap_max, "meaning": "deterministic scenarios, SYNTHETIC wind on real geometry"},
                      "measuredSkillOnlyView": round(10 * ms_pts / ms_max, 1) if ms_max else None},
            "evidence": {"generatedAt": ev.get("generatedAt"), "codeCommit": ev.get("codeCommit"), "knowledgeVersion": ev.get("knowledgeVersion"),
                         "atmosphericRowsSha": (ev.get("inputs") or {}).get("atmosphericRowsSha"), "h2": (ev.get("inputs") or {}).get("h2")},
            "explanation": _bi_explain(items, value)}


def _bi_explain(items, value):
    missing = sorted(((k, v) for k, v in items.items() if v["max"] - v["points"] > 0.005), key=lambda kv: -(kv[1]["max"] - kv[1]["points"]))
    why = [f"{k} {v['label']}: {v['points']:g} of {v['max']} ({v['evidence']})" for k, v in missing[:5]]
    improve = [{"item": k, "headroom": round(v["max"] - v["points"], 2), "gap": ITEM_GAP.get(k), "class": v["class"]} for k, v in missing]
    need = round(max(0.0, TARGET * 10 - sum(v["points"] for v in items.values())), 2)
    head = round(sum(x["headroom"] for x in improve), 2)
    return {"whyThisScore": why or ["every item at full credit"],
            "howToImprove": improve,
            "pathTo7": {"target": TARGET, "pointsNeeded": need, "reached": value >= TARGET, "headroomAvailable": head,
                        "note": "rubric arithmetic only; every remaining point is MEASURED_SKILL and needs new validated evidence"
                                if all(x["class"] == "MEASURED_SKILL" for x in improve) else "rubric arithmetic only"}}


# ---------------------------------------------------------------- Scientific Confidence
def scientific_confidence(ev: dict | None, cert: dict, now: dt.datetime) -> dict:
    ev = ev or {}
    a, sw, s, f = ev.get("atmospheric") or {}, ev.get("strongWind") or {}, ev.get("surface") or {}, ev.get("field") or {}
    flag = sw.get("probabilisticFlag") or {}
    items = [
        {"id": "fetchGeometry", "claim": "Fetch per bank is computed correctly", "status": "VALIDATED",
         "evidence": f"{sum(bool(v) for v in ((ev.get('geometry') or {}).get('qaChecks') or {}).values())}/4 QA checks; "
                     f"{(ev.get('geometry') or {}).get('canonicalCasesPassed')}/{(ev.get('geometry') or {}).get('canonicalCasesTotal')} canonical cases"},
        {"id": "lightWindForecast", "claim": "Night wind speed below the strong-wind regime", "status": "VALIDATED_LAND_STATIONS",
         "evidence": f"night MAE {a.get('nightSpeedMaeMS')} m/s, bias {a.get('nightSpeedBiasMS')} m/s, CAL+H1, 8 land stations"},
        {"id": "directionForecast", "claim": "Wind direction", "status": "PARTIAL", "evidence": f"within 22.5 deg {a.get('directionWithin22_5')} (certification full credit at 0.85)"},
        {"id": "strongWindForecast", "claim": "Strong-wind nights are forecast", "status": "FAILS",
         "evidence": f"{sw.get('observedNight15mphEvents')} observed >= 15 mph night events, deterministic POD {list((sw.get('pod15mphByLead') or {}).values())}; "
                     f"gust >= 20 kt POD {list((sw.get('gust20ktPodByLead') or {}).values())[:1]} at +1 h"},
        {"id": "strongWindProbabilisticFlag", "claim": "A probabilistic flag warns of windy nights", "status": "EXPLORATORY",
         "evidence": f"POD {flag.get('pod')}, FAR {flag.get('far')} on consumed CAL+H1; validation test sealed until 2027-01-01 (H2)" if flag else "no flag evidence"},
        {"id": "surfacePhysics", "claim": "Modeled wave height and class", "status": "PARTIAL_BUOYS_ONLY",
         "evidence": f"Hm0 MAE {s.get('hm0MaeM')} m, exact class {s.get('exact')}, within 1 {s.get('within1')} on {s.get('buoyRows')} buoy-hours (buoys are not banks)"},
        {"id": "surfaceClassAgreement", "claim": "Forecast wind gives the same surface class as observed wind", "status": "PARTIAL",
         "evidence": f"symmetric night {((a.get('surfaceClassAgreement') or {}).get('symmetricNight5mph'))}; observed >= 10 mph {((a.get('surfaceClassAgreement') or {}).get('observedNight10mph'))}"},
        {"id": "bankExposureField", "claim": "Real banks rank the way the model ranks them", "status": "NOT_VALIDATED",
         "evidence": f"{f.get('observations', 0)} field observations; {f.get('requirement', 'Evidence Addendum v1')}"},
        {"id": "surfaceField", "claim": "A bank's surface looks like the modeled class", "status": "NOT_VALIDATED", "evidence": f"{f.get('observations', 0)} field observations"},
        {"id": "transientRealism", "claim": "Chop builds and lays down at the right pace", "status": "NOT_VALIDATED",
         "evidence": (s.get("transient") or {}).get("why") or "no evidence"},
        {"id": "overWaterReference", "claim": "Over-water wind matches the land-station wind", "status": "NOT_AVAILABLE",
         "evidence": f"{(ev.get('overwater') or {}).get('measuredStationComparisons', 0)} over-water station comparisons"},
        {"id": "geographicApplicability", "claim": "Results transfer to other lakes", "status": "PARTIAL",
         "evidence": f"{(ev.get('coverage') or {}).get('developmentLakesComplete')} development lakes with atmospheric validation; "
                     f"{(ev.get('coverage') or {}).get('directoryLakesPassed')} directory lakes with geometry QA only; no field validation anywhere"},
    ]
    core = {"bankExposureField", "surfaceField", "strongWindForecast"}
    overall = "LIMITED" if any(i["status"] in ("NOT_VALIDATED", "FAILS") for i in items if i["id"] in core) else "PARTIAL"
    return {"version": SC_VERSION, "basis": "EVIDENCE_STATUS", "value": None, "overall": overall, "evaluatedAt": iso(now),
            "overallRule": "LIMITED while bank exposure, bank surface or strong-wind forecasting is NOT_VALIDATED or FAILS",
            "modelCapabilityIsNotValidation": "Capability scenarios (synthetic wind) are never counted here.",
            "items": items,
            "certificationScore": {"value": cert.get("value"), "scoreVersion": cert.get("scoreVersion"),
                                   "fieldValidationPoints": _cert_points(cert, ("Exposure (field)", "Surface (field)")),
                                   "note": "the certification score is the existing confidence-weighted measure; carried verbatim"},
            "h2": "SEALED until 2027-01-01; gates validation of NEW strong-wind/gust methods only",
            "noNumberBecause": "no defensible single confidence metric exists; a number would average a VALIDATED geometry with 0 field observations"}


def _cert_points(cert, names):
    b = cert.get("scoreBreakdown") or {}
    got = [b.get(n) or b.get(n.replace("/", "-")) for n in names]
    return {"earned": round(sum((g or {}).get("points", 0) for g in got), 2), "possible": sum((g or {}).get("weight", 0) for g in got)}


# ---------------------------------------------------------------- Production Readiness
def production_readiness(cert: dict, brain: dict, health: dict | None, now: dt.datetime) -> dict:
    b = cert.get("scoreBreakdown") or {}
    rel = b.get("Freshness/reliability") or b.get("Freshness-reliability") or {}
    m = re.search(r"(\d+)/30 complete days", rel.get("evidence", ""))
    days = int(m.group(1)) if m else None
    pub = (brain.get("publisherRequired") or {})
    h = (health or {}).get("status") or (health or {}).get("health")
    gates = [
        {"gate": "lifecycle", "status": "OPEN" if brain.get("lifecycle") in ("VALIDATED", "PRODUCTION") else "BLOCKED", "detail": f"lifecycle {brain.get('lifecycle')}"},
        {"gate": "publisherCutover", "status": "OPEN" if pub.get("cutoverStatus") == "CUTOVER" else "BLOCKED",
         "detail": f"publisher {pub.get('cutoverStatus')}; approved sequence {' -> '.join(CUTOVER_SEQUENCE)} (Wind is last)"},
        {"gate": "customerIntegration", "status": "OPEN" if brain.get("customerIntegrationMode") not in (None, "none") else "BLOCKED",
         "detail": f"customerIntegrationMode {brain.get('customerIntegrationMode')}: customers get Open-Meteo Best Match"},
        {"gate": "windAssessmentActivation", "status": "BLOCKED", "detail": "wind exposure assessment contract built and tested in nonproduction; not wired into wind-hourly, not published"},
        {"gate": "liveReliability", "status": "OPEN" if days is not None and days >= 30 else "BLOCKED",
         "detail": f"{days}/30 valid live days at the certification snapshot ({cert.get('scoreUpdatedAt')})" if days is not None else "unknown"},
        {"gate": "runtimeHealth", "status": "UNKNOWN" if h is None else ("OPEN" if h == "HEALTHY" else "BLOCKED"), "detail": f"health {h or 'not read'}"},
    ]
    caps = {n: (b.get(n) or {}).get("value") for n in ("Freshness/reliability", "Coverage", "Provenance/Unknown")}
    return {"version": PR_VERSION, "basis": "GATE_STATUS", "value": None, "evaluatedAt": iso(now),
            "overall": "NOT_READY" if any(g["status"] == "BLOCKED" for g in gates) else ("UNKNOWN" if any(g["status"] == "UNKNOWN" for g in gates) else "READY"),
            "gates": gates, "fromCertification": {"dimensionValues": caps, "source": f"{cert.get('scoreVersion')} dims 8-10 (carried verbatim)"},
            "notCapability": "uptime, freshness and publication state say nothing about whether a wind-exposure ranking is right",
            "noNumberBecause": "existing facts already express readiness as gates; a second readiness scorer would compete with the certification dims"}


# ---------------------------------------------------------------- envelope
def measurements(cert: dict, ev: dict | None, rubric: dict, brain: dict, now: dt.datetime, health: dict | None = None) -> dict:
    bi = wind_capability(ev, rubric, now)
    sec = (cert.get("secondary") or {})
    out = {"schema": ENVELOPE, "brainId": "wind", "evaluatedAt": iso(now), "authority": "platform scorer (sector_brain_platform.wind_measurements)",
           "certification": {"value": cert.get("value"), "scoreVersion": cert.get("scoreVersion"), "basis": cert.get("basis"),
                             "scoreUpdatedAt": cert.get("scoreUpdatedAt"), "carried": "verbatim from frozen-scores.json; not recomputed here"},
           "bwisV1": {"value": sec.get("bowfishingWindIntelligenceScore"), "definition": sec.get("definition"), "carried": "verbatim; frozen"},
           "windCapability": bi,
           "scientificConfidence": scientific_confidence(ev, cert, now),
           "productionReadiness": production_readiness(cert, brain, health, now),
           "presentation": "Show the three measurements side by side with the certification score; never average them; label Wind Capability v2 PROPOSED until adopted. None of them is a bowfishing recommendation."}
    out["consistency"] = consistency(out)
    return out


def consistency(m: dict) -> list[str]:
    """Problems with the envelope (empty = consistent). Checked by tests and before any write."""
    p = []
    versions = [m["certification"]["scoreVersion"], CAP_VERSION, SC_VERSION, PR_VERSION]
    if len(set(versions)) != 4:
        p.append("measurement versions collide")
    if m["certification"]["scoreVersion"] != CERT_VERSION:
        p.append("certification block is not wind-certification-rubric-v1")
    bi = m["windCapability"]
    if bi.get("value") is not None:
        if abs(bi["rawPoints"] - sum(i["points"] for i in bi["items"].values())) > 0.02:
            p.append("Capability raw points do not reproduce from items")
        if round(bi["rawPoints"] / 10, 1) != bi["value"]:
            p.append("Capability value does not reproduce from raw points")
        if bi["scoreVersion"] == m["certification"]["scoreVersion"]:
            p.append("Capability score reuses the certification version")
    for k in ("scientificConfidence", "productionReadiness"):
        if m[k].get("value") is not None:
            p.append(f"{k} carries a number")
    return p


def load_all():
    """Loaders for the default repository files (the scorer job image stages docs/ and brains/*/brain.json)."""
    return load(RUBRIC_PATH), (load(EVIDENCE_PATH) if os.path.exists(EVIDENCE_PATH) else None), load(BRAIN_JSON)
