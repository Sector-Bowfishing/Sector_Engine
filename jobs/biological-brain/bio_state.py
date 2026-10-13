"""Biological State (internal pilot): "What is this fish likely doing on this lake right now?"

Pure and deterministic. Inputs are already-published specialist Brain states plus species presence (Lake Brain) and the
researched Biological rules; the output is an INTERNAL state record. Nothing here reads live services, writes the Brain
RTDB, or touches a customer path. A missing/stale upstream input makes the dependent features UNKNOWN (never a placeholder).

State status is always PILOT_INTERNAL here. LIVE / VALIDATED are lifecycle decisions made elsewhere, not by this module.
"""
from __future__ import annotations

import datetime as dt

import contracts_in as ci
import features as ft
import rules as rl

STATE_VERSION = "biological-state-v0.1-pilot"
DEFAULT_STALE_AFTER_H = 36
# Which Lake Brain presence states make a species "relevant" is an OPEN decision (integration contract section 10). This is the
# conservative default; species outside it are reported as evaluated=false, never silently dropped.
DEFAULT_RELEVANT_PRESENCE = ("established", "reported", "stocked", "inRangeUnconfirmed")
SEASONS = {12: "WINTER", 1: "WINTER", 2: "WINTER", 3: "SPRING", 4: "SPRING", 5: "SPRING", 6: "SUMMER", 7: "SUMMER", 8: "SUMMER",
           9: "FALL", 10: "FALL", 11: "FALL"}


def daypart_for(lat: float, lon: float, now: dt.datetime) -> str:
    """DAY / TWILIGHT / NIGHT from solar elevation (NOAA low-precision formulae; about +/-1 degree, ample for a three-way class)."""
    import math
    n = now.astimezone(dt.timezone.utc)
    doy = n.timetuple().tm_yday
    g = 2 * math.pi / 365 * (doy - 1 + (n.hour - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
    tst = (n.hour * 60 + n.minute + eqt + 4 * lon) % 1440
    ha = math.radians(tst / 4 - 180)
    la = math.radians(lat)
    elev = math.degrees(math.asin(math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)))
    return "DAY" if elev > 0 else ("TWILIGHT" if elev > -6 else "NIGHT")


def _parse(ts):
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def _slot(st: dict | None, values: dict, now: dt.datetime, stale_after_h: float, brain: str) -> dict:
    if not isinstance(st, dict) or not st:
        return {"brainId": brain, "status": "NOT_PUBLISHED"}
    prov = st.get("provenance") or {}
    gen = prov.get("generatedAt") or st.get("generatedAt")
    g = _parse(gen)
    age = None if g is None else round((now - g).total_seconds() / 3600.0, 1)
    stale = bool(st.get("stale")) or bool((st.get("freshness") or {}).get("stale")) or age is None or age > stale_after_h
    degraded = st.get("observationType") == "UNAVAILABLE" or prov.get("readiness") in ("DEGRADED", "BLOCKED") or bool(st.get("evidenceStale"))
    status = "STALE" if stale else ("DEGRADED" if degraded else "PUBLISHED")
    return {k: v for k, v in {"brainId": brain, "status": status, "generatedAt": gen, "ageHours": age,
                              "brainVersion": prov.get("brainVersion"), "values": values}.items() if v is not None}


def normalize_inputs(snapshot: dict | None, now: dt.datetime, stale_after_h: float = DEFAULT_STALE_AFTER_H) -> dict:
    """The published lake snapshot (`/snapshots/{k}/latest`) -> the slots Biological features read. Implausible values and unrecognised vocabulary
    are dropped here (they become UNKNOWN features), never repaired."""
    s = snapshot or {}
    lk, wt, wc = s.get("lakeState"), s.get("waterTemperature"), s.get("waterClarity")
    pick = lambda d, ks: {k: (d or {}).get(k) for k in ks if (d or {}).get(k) is not None}      # noqa: E731
    cur, tr = ci.sane_temperature((wt or {}).get("currentTempF"), (wt or {}).get("trend24hF"))
    wt_vals = {k: v for k, v in (("currentTempF", cur), ("trend24hF", tr)) if v is not None}
    lk_vals = pick(lk, ("levelState", "floodPoolState", "tributaryDischargeTrend"))
    if ci.lake_trend((lk or {}).get("trendState")) != ci.UNKNOWN:
        lk_vals["trendState"] = lk["trendState"]
    if ci.lake_trend(lk_vals.get("tributaryDischargeTrend")) == ci.UNKNOWN:
        lk_vals.pop("tributaryDischargeTrend", None)
    return {
        "lake": _slot(lk, lk_vals, now, stale_after_h, "lake-brain"),
        "waterTemp": _slot(wt, wt_vals, now, stale_after_h, "water-temp"),
        "waterClarity": _slot(wc, pick(wc, ("clarityFt",)), now, stale_after_h, "water-clarity"),
    }


def build_lake_state(lake_id: str, *, region: str, waterbody_type: str, now: dt.datetime, inputs: dict, daypart: str | None,
                     presence: dict, ruleset: rl.RuleSet, species_info: dict | None = None,
                     relevant_presence=DEFAULT_RELEVANT_PRESENCE) -> dict:
    """One lake's internal Biological State. `presence` = {speciesId: {presenceState, confidence, ...}} from the Lake Brain."""
    month = now.month
    ctx = {"month": month, "region": region, "waterbodyType": waterbody_type}
    feats = ft.evaluate_features(inputs, {"month": month, "daypart": daypart})
    cur_f = ((inputs.get("waterTemp") or {}).get("values") or {}).get("currentTempF") if (inputs.get("waterTemp") or {}).get("status") in ft.USABLE_INPUT_STATUS else None
    temp_c = ft.f_to_c(cur_f) if isinstance(cur_f, (int, float)) else None

    species_out, lake_unknowns = [], []
    for sid in sorted(presence):
        p = presence[sid] or {}
        info = (species_info or {}).get(sid) or {}
        rec = {"speciesId": sid, "presence": {k: p.get(k) for k in ("presenceState", "confidence", "latestRecord") if p.get(k) is not None},
               "knowledge": {k: info.get(k) for k in ("researchMaturity", "knowledgeScore", "assessment") if info.get(k) is not None}}
        # Presence (Lake Brain) and knowledge (Biological) are separate: a present species may be unassessed or have no knowledge row at all.
        if info.get("assessment") == "NOT_ASSESSED":
            rec["knowledge"]["state"] = "NOT_ASSESSED"
        elif not info:
            rec["knowledge"]["state"] = "NO_KNOWLEDGE_ROW"
        elif ruleset.counts(sid)["usable"]:
            rec["knowledge"]["state"] = "ASSESSED_WITH_RULES"
        else:
            rec["knowledge"]["state"] = "ASSESSED_NO_RULES"
        if rec["knowledge"]["state"] in ("NOT_ASSESSED", "NO_KNOWLEDGE_ROW"):
            rec |= {"evaluated": False, "notEvaluatedReason": f"presence {p.get('presenceState')!r} is known but Biological knowledge is {rec['knowledge']['state']}: UNKNOWN, not rated"}
            species_out.append(rec)
            continue
        if p.get("presenceState") not in relevant_presence:
            rec |= {"evaluated": False, "notEvaluatedReason": f"presence state {p.get('presenceState')!r} is outside the relevance policy (Lake Brain owns presence)"}
            species_out.append(rec)
            continue
        all_rules = [r for r in ruleset.by_species.get(sid, []) if ruleset.is_active(r)]
        use = ruleset.for_species(sid)
        rec["knowledge"]["rules"] = ruleset.counts(sid)
        rec["seasonState"] = {"calendarSeason": SEASONS[month]}
        unknowns = []
        if not use:
            rec |= {"evaluated": True, "responses": [], "habitat": [], "spawnWindow": {"state": ft.UNKNOWN, "reason": "no usable rules"},
                    "nightMovementSupported": ft.UNKNOWN}
            unknowns.append("no usable (RECONCILED/APPROVED) rules for this species" + (f"; {len(all_rules)} draft rule(s) excluded" if all_rules else ""))
        else:
            win = rl.phenology_window(use, ctx)
            sw = ft.spawn_window(month, temp_c, win)
            if win:
                sw |= {"ruleId": win["ruleId"], "confidence": win["confidence"], "transferability": win["transferability"]}
            responses = rl.evaluate_responses(use, feats, ctx)
            habitat = rl.evaluate_habitat(use, feats, ctx)
            night = next((r for r in responses if r["featureId"] == "daypart" and r["featureState"] == "NIGHT"), None)
            nms = ft.UNKNOWN if not night or night["response"] == "UNKNOWN" else ("TRUE" if night["response"] in ("FAVORABLE", "WORKABLE") else "FALSE")
            rec |= {"evaluated": True, "spawnWindow": sw, "responses": responses, "habitat": habitat, "nightMovementSupported": nms}
            rec["seasonState"]["spawnWindow"] = sw["state"]
            for r in responses:
                if r["response"] == "UNKNOWN":
                    unknowns.append(f"{r['featureId']}: {r['reason']}")
            if not [r for r in responses if r["response"] != "UNKNOWN"]:
                unknowns.append("no response band could be evaluated from current inputs")
        rec["unknowns"] = unknowns
        species_out.append(rec)

    for slot in ("lake", "waterTemp", "waterClarity"):
        if (inputs.get(slot) or {}).get("status") not in ft.USABLE_INPUT_STATUS:
            lake_unknowns.append(f"{slot} input {(inputs.get(slot) or {}).get('status', 'NOT_PUBLISHED')}: dependent features are UNKNOWN")
    lake_unknowns.append("tributary discharge change is not published by any Brain: rapidDischargeIncrease is UNKNOWN")
    lake_unknowns.append("area-level habitat classes are not evaluable at lake level")
    evaluated = [s for s in species_out if s.get("evaluated")]
    return {
        "lakeId": lake_id, "kind": "biological-state", "stateVersion": STATE_VERSION, "status": "PILOT_INTERNAL",
        "generatedAt": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "context": {"region": region, "waterbodyType": waterbody_type, "month": month, "daypart": daypart},
        "inputs": {k: {kk: vv for kk, vv in v.items() if kk != "values"} for k, v in inputs.items()},
        "features": {k: v for k, v in feats.items() if ft.REGISTRY[k]["availability"] != "AREA"},
        "species": species_out, "unknowns": lake_unknowns,
        "summary": {"speciesPresent": len(species_out), "speciesEvaluated": len(evaluated),
                    "speciesWithAnyResponseBand": sum(1 for s in evaluated if any(r["response"] != "UNKNOWN" for r in s.get("responses", [])))},
        "provenance": {"brainId": "biological-state", "featuresVersion": ft.FEATURES_VERSION, "rulesVersion": ruleset.rules_version,
                       "stateVersion": STATE_VERSION},
        "validation": {"status": "NOT_VALIDATED", "note": "Rules are research-derived; no prediction has been compared with outcomes."},
        "customerPath": {"consumed": False},
    }


VOLATILE_KEYS = ("generatedAt", "ageHours")


def state_fingerprint(state: dict) -> str:
    """Stable hash of everything material in a Biological State (volatile timestamps/ages removed). A run whose fingerprint equals the last one
    needs no new artifact, prediction or write: compute because INPUT TRUTH CHANGED, not because a page was opened or the clock ticked."""
    import hashlib
    import json

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in VOLATILE_KEYS}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o
    return hashlib.sha256(json.dumps(strip(state), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
