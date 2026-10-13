"""Normalized Sector Intelligence inputs and the pilot evaluation (consolidation Phase 9).

Sector Intelligence CONSUMES specialist Brain states; it never reimplements their science. This
module turns one lake's published snapshot (`/snapshots/{k}/latest`), fleet row, species presence
(Lake Brain) and species knowledge (Biological Brain) into:

  * normalized inputs — one record per specialist slot with status, exact Brain/model version,
    generatedAt, age, stale / evidenceStale, readiness, kind and the specialist's own values
    (restated verbatim, never recomputed);
  * a normalized evaluation — generatedAt, inputs used, drivers (facts), limiting factors (input
    quality and knowledge completeness), degraded inputs, synthesis, version, validation state and
    full provenance.

v2 adds the pilot EVIDENCE LAYER (`evidence.py`, contract intelligence-evidence-v1): per-factor evidence, per-species
assessment (UNSUPPORTED/UNRANKED until Biological publishes approved response bands), weakest-link confidence and a
structured explanation. All v1 fields are unchanged.

The synthesis produces NO fishing judgment and NO customer score: the customer path is still the
Engine Conditions Score, which does not read this evaluation. Pilot lakes only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import statistics

import brain_platform as bp
import evidence as evd

EVAL_VERSION = "intelligence-eval-v2"
PILOT_LAKES = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]
CONDITION_SLOTS = (("lake-brain", "lake", "lakeState"), ("water-temp", "waterTemp", "waterTemperature"),
                   ("water-clarity", "waterClarity", "waterClarity"), ("wind", "wind", "wind"))
_LEGACY_KIND = {"GAUGE_OBSERVED": "observed", "RAINFALL_MODELED": "modeled", "FALLBACK_NEUTRAL": "modeled", "UNAVAILABLE": "unavailable",
                "OBSERVED": "observed", "PROXY": "proxy", "MEASURED": "measured", "MODELED": "modeled", "NOT_EVALUATED": "not_evaluated"}


def _strip(d):
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            v = _strip(v)
            if v is None or v == {} or v == []:
                continue
            out[k] = v
        return out
    if isinstance(d, list):
        return [_strip(x) for x in d if x is not None]
    return d


def _kind(st: dict) -> str | None:
    k = st.get("kind")
    if isinstance(k, str) and k:
        return _LEGACY_KIND.get(k, k.lower())
    s = st.get("stateType")
    return _LEGACY_KIND.get(s, s.lower() if isinstance(s, str) else None)


def _values(brain_id: str, st: dict) -> dict:
    """The specialist's own values and labels, restated — never recomputed."""
    if brain_id == "lake-brain":
        return {k: st.get(k) for k in ("levelState", "trendState", "historicalState", "floodPoolState", "currentElevationFt",
                                        "differenceFromGuideFt", "differenceFromNormalPoolFt", "baselineStatus", "sourceCapability")}
    if brain_id == "water-temp":
        return {k: st.get(k) for k in ("currentTempF", "trend24hF", "lakeLocalDate", "observationType", "spatialSupport", "lastObservationAt")}
    if brain_id == "water-clarity":
        return {k: st.get(k) for k in ("clarityFt", "clarityUnit", "clarityQuantity", "stateType", "basis", "activeModel",
                                        "recentRainfallIn72h", "trend", "satelliteObservationAt")}
    if brain_id == "wind":
        an, ob = st.get("analysis") or {}, st.get("observation") or {}
        return {"sustainedMph": an.get("sustainedMph"), "gustMph": st.get("gustMph", an.get("gustMph")), "analysisProduct": an.get("product"),
                "analysisTime": an.get("analysisTime"), "observedSustainedMph": ob.get("sustainedMph"), "observationStation": ob.get("station"),
                "forecastGeneratedAt": st.get("forecastGeneratedAt")}
    return {}


def normalize_condition(brain_id: str, slot: str, field: str, snapshot: dict | None, fleet_row: dict | None,
                        dep: dict | None, now: dt.datetime) -> dict:
    st = (snapshot or {}).get(field)
    if not isinstance(st, dict) or not st:
        return {"brainId": brain_id, "slot": slot, "status": "NOT_PUBLISHED", "degraded": ["state not published for this lake"]}
    prov = st.get("provenance") or {}
    fr = st.get("freshness") or {}
    gen = prov.get("generatedAt") or fr.get("generatedAt") or st.get("generatedAt")
    age = bp.age_hours(gen, now)
    stale_after = (dep or {}).get("staleAfterHours")
    stale = bool(fr.get("stale")) or bool(st.get("stale")) or (stale_after is not None and (age is None or age > float(stale_after)))
    evidence_stale = bool(st.get("evidenceStale")) or bool(fr.get("evidenceStale"))
    kind = _kind(st)
    readiness = prov.get("readiness") or (((fleet_row or {}).get("readiness") or {}).get(slot))
    degraded = []
    if stale:
        degraded.append(f"state is {age if age is not None else '?'} h old" + (f" (> {stale_after} h)" if stale_after is not None else ""))
    if evidence_stale:
        degraded.append("brain reports its evidence is stale")
    if kind == "unavailable":
        degraded.append("value unavailable")
    if readiness in ("DEGRADED", "BLOCKED"):
        degraded.append(f"readiness {readiness}")
    status = "STALE" if stale else ("DEGRADED" if degraded else "PUBLISHED")
    return _strip({"brainId": brain_id, "slot": slot, "status": status, "kind": kind, "readiness": readiness,
                   "brainVersion": prov.get("brainVersion") or st.get("brainVersion"), "modelVersion": prov.get("modelVersion"),
                   "generatedAt": gen, "ageHours": age, "stale": stale, "evidenceStale": evidence_stale,
                   "degraded": degraded, "values": _values(brain_id, st)})


def normalize_biological(presence: dict | None, species: dict | None, dep: dict | None) -> dict:
    if not presence:
        return {"brainId": "biological-state", "slot": "biology", "status": "NOT_PUBLISHED",
                "degraded": ["no species presence published for this lake (Lake Brain)"]}
    rows, missing, scores = {}, [], []
    for sid, p in sorted(presence.items()):
        p = p or {}
        sp = (species or {}).get(sid) or {}
        if not sp:
            missing.append(sid)
        k = sp.get("knowledge") or {}
        if isinstance(k.get("overallRounded"), (int, float)):
            scores.append(float(k["overallRounded"]))
        rows[sid] = _strip({"presenceState": p.get("presenceState"), "presenceConfidence": p.get("confidence"),
                            "nativeStatus": p.get("nativeStatus"), "assessment": sp.get("assessment"),
                            "researchMaturity": sp.get("researchMaturity"), "knowledgeScore": k.get("overallRounded"),
                            "knowledgeRubric": k.get("rubric"), "speciesVersion": sp.get("researchVersion")})
    degraded = []
    if missing:
        degraded.append(f"no species knowledge for {len(missing)} present species: {', '.join(missing[:4])}")
    immature = [sid for sid, r in rows.items() if r.get("researchMaturity") in (None, "NOT_STARTED") or r.get("assessment") == "NOT_ASSESSED"]
    if immature:
        degraded.append(f"species knowledge not started for {len(immature)} present species")
    pv = next((p.get("researchVersion") for p in presence.values() if isinstance(p, dict) and p.get("researchVersion")), None)
    return _strip({"brainId": "biological-state", "slot": "biology", "status": "DEGRADED" if degraded else "PUBLISHED",
                   "speciesCount": len(rows), "species": rows, "knowledgeMedian": statistics.median(scores) if scores else None,
                   "knowledgeMissingFor": missing, "presenceVersion": pv, "brainVersion": (dep or {}).get("version"), "degraded": degraded})


def _fmt(v, unit="", signed=False):
    if v is None:
        return None
    if isinstance(v, float):
        return (f"{v:+.1f}" if signed else f"{v:.1f}") + unit
    return f"{v}{unit}"


def evaluate(lake_id: str, *, snapshot: dict | None, fleet_row: dict | None, presence: dict | None, species: dict | None,
             deps: dict, cat: dict, serving: dict, now: dt.datetime) -> dict:
    """The normalized pilot evaluation for one lake. Pure; absent stays absent; nothing is invented."""
    inputs = {slot: normalize_condition(bid, slot, field, snapshot, fleet_row, deps.get(bid), now) for bid, slot, field in CONDITION_SLOTS}
    inputs["biology"] = normalize_biological(presence, species, deps.get("biological-state"))

    used = {slot: _strip({"brainId": i["brainId"], "brainVersion": i.get("brainVersion"), "modelVersion": i.get("modelVersion"),
                          "generatedAt": i.get("generatedAt"), "status": i["status"]})
            for slot, i in inputs.items() if i["status"] != "NOT_PUBLISHED"}
    degraded_inputs = sorted(slot for slot, i in inputs.items() if i["status"] != "PUBLISHED")

    drivers, limiting = [], []
    v = inputs["lake"].get("values") or {}
    if v.get("levelState"):
        drivers.append(_strip({"slot": "lake", "fact": " · ".join(x for x in [
            f"level {v.get('levelState')}", f"trend {v.get('trendState')}" if v.get("trendState") else None,
            f"{_fmt(v.get('currentElevationFt'), ' ft')}" if v.get("currentElevationFt") is not None else None,
            f"guide {_fmt(v.get('differenceFromGuideFt'), ' ft', signed=True)}" if v.get("differenceFromGuideFt") is not None else None,
            f"history {v.get('historicalState')}" if v.get("historicalState") else None,
            f"flood pool {v.get('floodPoolState')}" if v.get("floodPoolState") not in (None, "UNKNOWN") else None] if x)}))
    v = inputs["waterTemp"].get("values") or {}
    if v.get("currentTempF") is not None:
        drivers.append({"slot": "waterTemp", "fact": f"water {_fmt(v['currentTempF'], ' °F')} ({inputs['waterTemp'].get('kind')})"
                        + (f" · 24 h {_fmt(v.get('trend24hF'), ' °F', signed=True)}" if v.get("trend24hF") is not None else "")})
    v = inputs["waterClarity"].get("values") or {}
    if v.get("clarityFt") is not None:
        drivers.append({"slot": "waterClarity", "fact": f"clarity {_fmt(v['clarityFt'], ' ft')} ({v.get('stateType')} · {v.get('activeModel')})"})
    v = inputs["wind"].get("values") or {}
    if v.get("sustainedMph") is not None:
        drivers.append({"slot": "wind", "fact": f"wind {_fmt(v['sustainedMph'], ' mph')} sustained"
                        + (f", gust {_fmt(v.get('gustMph'), ' mph')}" if v.get("gustMph") is not None else "") + f" ({v.get('analysisProduct')})"})
    b = inputs["biology"]
    if b.get("speciesCount"):
        drivers.append({"slot": "biology", "fact": f"{b['speciesCount']} present species; knowledge median {b.get('knowledgeMedian')} / 10 (species-v2)"})

    for slot in degraded_inputs:
        for r in inputs[slot].get("degraded") or [f"status {inputs[slot]['status']}"]:
            limiting.append(f"{slot}: {r}")
    limiting.append("no outcome validation exists for this evaluation (NOT_VALIDATED)")

    evidence = evd.build_evidence(inputs=inputs, snapshot=snapshot, presence=presence, species=species)
    es = evidence["summary"]
    if es["speciesTotal"] and not es["ratingsIssued"]:
        limiting.append(f"evidence: no species could be rated ({es['speciesTotal']} present; no approved Biological response bands)")
    limiting.append("evidence: depth and vegetation are UNKNOWN (no Depth or Vegetation Brain); wind exposure is lake-level only")

    published = sum(1 for i in inputs.values() if i["status"] == "PUBLISHED")
    sources = [{"sourceType": "brainState", "sourceId": f"{u['brainId']}@{u.get('brainVersion') or '?'}", "lastObservationAt": u.get("generatedAt")}
               for u in used.values()]
    flags = ["PILOT", "NO_CUSTOMER_SCORE", "EVIDENCE_LAYER_PILOT"] + (["DEGRADED_INPUTS"] if degraded_inputs else [])
    return _strip({
        "lakeId": lake_id, "kind": "evaluated", "evaluationStatus": "EVALUATED_PILOT", "evaluationVersion": EVAL_VERSION,
        "generatedAt": bp.iso(now),
        "inputsUsed": used, "inputs": inputs, "evidence": evidence, "drivers": drivers, "limitingFactors": limiting, "degradedInputs": degraded_inputs,
        "synthesis": {"inputCompleteness": f"{published} of {len(inputs)} inputs fresh", "inputsFresh": published,
                      "inputsDegraded": len(degraded_inputs),
                      "note": "Normalized specialist inputs assembled with provenance. No fishing judgment and no customer "
                              "score are produced: the customer path is the Engine Conditions Score, which does not read this."},
        "validation": {"status": "NOT_VALIDATED", "note": "pilot evaluation; no outcome validation exists"},
        "customerPath": {"implementation": cat.get("activeImplementation"), "engineRevision": serving.get("revision"),
                         "consumesThisEvaluation": False},
        "provenance": {"brainId": "sector-intelligence", "brainVersion": cat.get("brainVersion"), "processingVersion": serving.get("revision"),
                       "generatedAt": bp.iso(now), "sources": sources, "readiness": "CALIBRATION", "qualityFlags": flags,
                       "validationRef": "/validation/sector-intelligence"},
        "freshness": bp.freshness(now, now, 24, "FINGERPRINT", evidence_stale=bool(degraded_inputs),
                                  evidence_reasons=[f"{s} input {inputs[s]['status'].lower()}" for s in degraded_inputs],
                                  refresh_reason="pilot evaluation"),
    })


def inputs_fingerprint(evaluations: dict) -> str:
    """Changes when any pilot input's generatedAt or status changes (orchestration.plan input)."""
    view = {lid: {slot: [u.get("generatedAt"), u.get("status")] for slot, u in sorted((e.get("inputsUsed") or {}).items())}
            for lid, e in sorted(evaluations.items())}
    return hashlib.sha256(json.dumps([EVAL_VERSION, view], sort_keys=True).encode()).hexdigest()[:16]
