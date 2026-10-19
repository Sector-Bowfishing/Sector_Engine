"""Build the canonical Wind Exposure Assessment (`sector-wind-exposure-assessment-v1`) for one lake and one wind.

Inputs are existing Wind contracts only: a wind input (from a published/derived `sector-brain-wind-state-v1` via
`wind_from_state`, or an explicit, honestly-labelled synthetic scenario via `synthetic_wind`) and a runtime fetch object
(`ranking.geometry`). The output is bounded (top-N banks + requested banks); the full per-bank ranking is a separate artifact.

Rules that protect users:
  * never fabricate: no fresh wind / no direction / no geometry / unsupported lake -> a non-READY status with NO shoreline results;
  * unknown banks are never sheltered; the strong-wind limitation is always attached;
  * confidence is LOW or MODERATE only (HIGH needs field validation that does not exist), and never above what inputs allow;
  * `validated: false`, lifecycle SHADOW, customer exposure NOT_AUTHORIZED (no customer path reads this).
"""
from __future__ import annotations

from datetime import datetime

from .. import bowfishing as BF
from ..brain import contract as C
from . import limitations as LIM
from . import ranking as R
from . import schema as SC
from . import semantics as S
from . import timeline as T

SYNTHETIC_TAG = "SYNTHETIC"


def synthetic_wind(speed_mph: float, dir_from_deg: float | None, duration_h: float = BF.STEADY_H, gust_mph: float | None = None,
                   at: str | None = None, label: str = "") -> dict:
    """A scenario wind. Always kind 'synthetic'; never presented as a forecast or an observation."""
    return {"kind": "synthetic", "speedMS": None if speed_mph is None else speed_mph * BF.MPH, "dirFromDeg": dir_from_deg,
            "gustMS": None if gust_mph is None else gust_mph * BF.MPH, "durationH": duration_h, "validAt": at, "leadHours": None,
            "stale": False, "staleReasons": [], "source": f"{SYNTHETIC_TAG} scenario input{': ' + label if label else ''}", "hourly": None}


def wind_from_state(state: dict) -> dict:
    """Wind input from a `sector-brain-wind-state-v1` (built by brain.state.build_state). Units back to SI; labels kept.
    The published state carries mph to 0.1, so modeled waves can differ from the state's own bank rows by a few hundredths of an inch."""
    kind = state.get("kind") or "unavailable"
    ms = lambda v: None if v is None else v * BF.MPH
    lead = None
    if kind == "forecast" and state.get("hourly"):
        lead = state["hourly"][0].get("leadHours")
    hourly = [{"at": h["at"], "speedMS": ms(h.get("mph")), "dirFromDeg": h.get("dirDeg"), "gustMS": ms(h.get("gustMph")),
               "kind": "forecast", "leadHours": h.get("leadHours")} for h in (state.get("hourly") or [])]
    dur = (state.get("surfaceState") or {}).get("durationH")
    prov = state.get("provenance") or {}
    return {"kind": kind, "speedMS": ms(state.get("sustainedMph")), "dirFromDeg": state.get("directionDeg"), "gustMS": ms(state.get("gustMph")),
            "durationH": dur if dur is not None else BF.STEADY_H, "durationBasis": "frozen duration rule (analysis history)" if dur is not None else
            f"no analysis history: steady {BF.STEADY_H:g} h assumed (the frozen ranking default)",
            "validAt": (state.get("analysis") or {}).get("analysisTime") or (hourly[0]["at"] if hourly else None), "leadHours": lead,
            "stale": bool(state.get("stale")), "staleReasons": list(state.get("staleReasons") or []),
            "source": ", ".join(s.get("sourceId", "?") for s in prov.get("sources", [])) or None, "hourly": hourly,
            "forecastInit": state.get("forecastGeneratedAt"), "stateGeneratedAt": prov.get("generatedAt")}


def _status(wind, L, supported):
    if not supported:
        return "UNSUPPORTED_LAKE"
    if L is None:
        return "GEOMETRY_UNAVAILABLE"
    if wind["kind"] == "unavailable" or wind.get("speedMS") is None:
        return "WIND_UNAVAILABLE"
    if wind.get("stale"):
        return "INPUT_STALE"
    if wind.get("dirFromDeg") is None and wind["speedMS"] >= 0.5:
        return "DIRECTION_UNKNOWN"
    return "READY"


def _confidence(wind, sh, mph_now, gust_mph):
    reasons = []
    if wind["kind"] == "synthetic":
        reasons.append("synthetic input")
    if wind["kind"] == "forecast":
        if mph_now is not None and mph_now >= LIM.WINDY_MPH:
            reasons.append(f"forecast wind >= {LIM.WINDY_MPH:g} mph (forecast speed error is largest here)")
        if wind.get("leadHours") is not None and wind["leadHours"] > LIM.LONG_LEAD_H:
            reasons.append(f"forecast lead > {LIM.LONG_LEAD_H} h")
    if mph_now is not None and mph_now >= LIM.STRONG_WIND_MPH or (gust_mph or 0) >= LIM.STRONG_WIND_MPH + 5:
        reasons.append("strong-wind regime (not detected reliably by the forecast; surface classes least certain)")
    shown = sh["sheltered"] + sh["exposed"] + [b for b in sh["requested"] if b["windExposure"]["code"] != "UNKNOWN"]
    if shown and sum(1 for b in shown if b["confidence"] == "boundary") / len(shown) > 0.5:
        reasons.append("most shown banks sit at a class boundary")
    level = "LOW" if reasons else "MODERATE"
    return {"level": level, "reasons": reasons or ["fresh input, wind below the known-weak regime, firm classes on most shown banks"],
            "ceiling": "MODERATE", "ceilingReason": "HIGH requires bank-scale field validation; 0 field observations exist",
            "definition": SC.CONFIDENCE[level]}


def build(lake_id: str, wind: dict, L: dict | None, now: datetime, *, supported: bool = True, top: int = R.DEFAULT_TOP,
          bank_ids: tuple = (), window_hours: list[dict] | None = None, prior_hours: list[dict] | None = None,
          processing_version: str | None = None, include_full_ranking: bool = False) -> dict:
    """One assessment. `window_hours` (hourly wind dicts) adds the hourly wind timeline for the shown + requested banks."""
    status = _status(wind, L, supported)
    mph_now, gust_mph = C.mph(wind.get("speedMS")), C.mph(wind.get("gustMS"))
    d_from = wind.get("dirFromDeg")
    calm = status == "READY" and d_from is None
    out = {
        "assessmentSchema": SC.ASSESSMENT_SCHEMA, "knowledgeVersion": SC.KNOWLEDGE_VERSION, "lakeId": lake_id, "lakeKey": C.lake_key(lake_id),
        "status": status, "statusMeaning": SC.STATUS[status], "evaluatedAt": C.iso(now),
        "reference": {"validAt": wind.get("validAt"), "forecastInit": wind.get("forecastInit"), "leadHours": wind.get("leadHours"),
                      "stateGeneratedAt": wind.get("stateGeneratedAt")},
        "wind": {"kind": wind["kind"], "sustainedMph": mph_now, "gustMph": gust_mph,
                 "directionDeg": None if d_from is None else round(d_from), "directionCardinal": C.cardinal(d_from),
                 "durationH": wind.get("durationH"), "durationBasis": wind.get("durationBasis", "scenario duration"),
                 "source": wind.get("source"), "stale": wind.get("stale"), "staleReasons": wind.get("staleReasons"),
                 "units": {"speed": "mph", "direction": "degrees FROM, true north", "waves": "inches (significant wave height Hm0)"}},
        "scope": {"supportedLake": supported, "geometryAvailable": L is not None,
                  "geometry": None if L is None else {"tableSha256": L.get("tableSha256"), "sourceTableSha256": L.get("sourceTableSha256"),
                                                      "subset": L.get("subset"), "banks": len(L["banks"])},
                  "answers": "wind exposure and wind-driven surface disturbance per bank (specialist wind assessment)",
                  "doesNotAnswer": ["where to bowfish", "fish presence or behaviour", "water clarity", "overall fishing opportunity", "access, launch or legality", "private property", "safety", "whether to go"], "synthesisOwner": "sector-intelligence"},
        "shorelines": None, "lakeSummary": None, "timeline": None,
        "confidence": {"level": "UNKNOWN", "reasons": [SC.STATUS[status]], "ceiling": "MODERATE", "definition": SC.CONFIDENCE["UNKNOWN"]},
        "limitations": [], "explanation": None,
        "provenance": {"brainId": C.BRAIN_ID, "brainVersion": C.BRAIN_VERSION, "modelVersion": C.CANDIDATE_MODEL,
                       "physics": "frozen CEM EM 1110-2-1100 II-2-36..39 + frozen duration rule (M0) + frozen SPM84/CEM 9-ray fetch tables",
                       "rankingRules": "BWIS v1 frozen ranking + nearby-alternative rules (definition sha256 21e2a326...)",
                       "processingVersion": processing_version, "deterministic": True, "aiUsed": False},
        "validation": dict(SC.VALIDATION_STATUS),
    }
    if status != "READY":
        out["explanation"] = f"No shoreline assessment: {SC.STATUS[status]}"
        if wind.get("staleReasons"):
            out["explanation"] += f" ({', '.join(wind['staleReasons'])})"
        _assert(out)
        return out
    dur = wind.get("durationH") or BF.STEADY_H
    dir_eval = 0.0 if calm else d_from
    sh = R.rank(L, wind["speedMS"], dir_eval, dur, top=top, bank_ids=tuple(bank_ids))
    allr = sh.pop("_all")
    out["shorelines"] = sh
    out["lakeSummary"] = R.lake_summary(allr, L)
    if calm:
        out["lakeSummary"]["note"] = "calm: direction undefined; below 0.5 m/s modeled waves stay under 1 in at any fetch"
    if include_full_ranking:
        out["fullRanking"] = R.full_ranking(allr, lake_id)
    if window_hours:
        ids = list(dict.fromkeys([b["bankId"] for b in sh["requested"] + sh["sheltered"][:3] + sh["exposed"][:3]]))
        out["timeline"] = T.timeline(L, window_hours, ids, prior_hours)
    out["confidence"] = _confidence(wind, sh, mph_now, gust_mph)
    out["limitations"] = LIM.applicable(wind["kind"], mph_now, gust_mph, wind.get("leadHours"), bool(L.get("subset")))
    out["explanation"] = _headline(out, sh)
    _assert(out)
    return out


def _headline(d, sh):
    w = d["wind"]
    if w["directionCardinal"] is None:
        return (f"Calm wind ({w['sustainedMph']:g} mph): the surface is modeled flat to rippled everywhere; exposure differences do not matter "
                f"at this speed. {d['lakeSummary']['unknownBanks']} banks have unknown fetch.")
    s = f"For a {w['sustainedMph']:g} mph {w['directionCardinal']} wind ({w['kind']}), "
    s += f"{d['lakeSummary']['shelteredPct']:g}% of evaluated banks are sheltered or low-exposure and {d['lakeSummary']['exposedPct']:g}% highly exposed."
    if sh["sheltered"]:
        b = sh["sheltered"][0]
        s += f" Most sheltered: {b['bankId']} ({b['fetch']['effectiveM']:g} m effective fetch, {b['predictedSurface']['label'].lower()})."
    if sh["exposed"]:
        b = sh["exposed"][0]
        s += f" Most exposed: {b['bankId']} ({b['fetch']['effectiveM'] / 1000:.1f} km fetch, {b['predictedSurface']['label'].lower()})"
        near = b.get("nearestSheltered") or []
        s += (f"; the nearest sheltered bank is {near[0]['bankId']}, {near[0]['distanceM']} m away ({near[0]['effectiveFetchM']:g} m fetch, "
              f"{near[0]['predictedSurfaceLabel'].lower()})." if near else "; no sheltered bank within 10 km in the evaluated geometry.")
    s += f" {d['lakeSummary']['unknownBanks']} banks have unknown fetch and are not ranked. Model output, not field-validated."
    return s


def _assert(d):
    p = SC.check(d)
    if p:
        raise AssertionError(f"assessment invariant failed: {p[:5]}")
