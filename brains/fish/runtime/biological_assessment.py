"""Fish biological assessment (`fish-biological-assessment-v1`): what Fish knows about each species UNDER SUPPLIED CONDITIONS, shaped for Intelligence.

Fish knows fish; Intelligence makes bowfishing decisions (BRAIN_OPERATING_CONTRACT.md "Specialist boundary"). This contract therefore carries
biological interpretation only: state, seasonal state, habitat PREFERENCES (classes, not places), depth TENDENCIES, environmental responses, spawning,
day/night, reasons, unknowns and confidence limits. It never carries a location, an area, a ranking, an opportunity score or a recommendation;
`validate_assessment` rejects any of those keys anywhere in the payload.

Derived only from an already-built Biological State (bio_state.build_lake_state) plus the same validated RuleSet the state used. Unsupported fields
stay UNKNOWN (never guessed). Evidence references are opaque rule identities (id + version); rule text and evidence stay private.
Pure, deterministic, stdlib only.
"""
from __future__ import annotations

import features as ft
import movement_outlook as mo
import rules as rl
import target_set as ts

CONTRACT = "fish-biological-assessment-v1"
ASSESSMENT_STATUS = ("EVALUATED", "NOT_EVALUATED")
DEPTH_KNOWLEDGE = ("KNOWS_DEPTH_PREFERENCE", "HAS_NO_DEPTH_RULE")
SUPPLIED_DEPTH = ("WITHIN_PREFERRED_DEPTH", "OUTSIDE_PREFERRED_DEPTH", "AVOIDED_DEPTH", "NO_DEPTH_RULE", "NO_APPLICABLE_DEPTH_RULE", "NOT_SUPPLIED", "UNRECOGNISED_DEPTH")
NIGHT_STATES = ("ACTIVE_OR_SHALLOW", "REDUCED", "NO_DIFFERENCE_DOCUMENTED", "CONFLICT", "UNKNOWN")
EVIDENCE_KIND = ("BEHAVIORAL", "CATCHABILITY", "MIXED", "UNCLASSIFIED", "NONE")
SHALLOW_TENDENCY = ("MORE_LIKELY_SHALLOW", "LESS_LIKELY_SHALLOW", "MIXED", "UNKNOWN")
DEPTH_CLASS_BOUNDS_M = (("LT_0_5M", 0.0, 0.5), ("M0_5_1_5", 0.5, 1.5), ("M1_5_3", 1.5, 3.0), ("GT_3M", 3.0, float("inf")))
DEEP_HABITATS = ("deepChannelPool", "openWaterBasin")
# Keys that would turn a biological assessment into a bowfishing decision (Intelligence's job). Rejected anywhere in the payload.
FORBIDDEN_KEYS = frozenset({"rank", "ranking", "rankedAreas", "score", "opportunity", "opportunityScore", "recommendation", "recommendations",
                            "recommendedLocation", "location", "locations", "lat", "lon", "latitude", "longitude", "geometry", "areaId", "bankId",
                            "spot", "spots", "bestPlaces"})
# Study designs that observe WHERE a fish is (behaviour) versus how often it is CAUGHT (catchability). Keyword match on the structured studyType.
_BEHAVIORAL_WORDS = ("telemetry", "tracking", "tagged", "acoustic", "radio", "movement-state", "positional")
_CATCH_WORDS = ("electrofish", "catch", "capture", "angl", "creel", "gill net", "gillnet", "netting", "encounter", "harvest", "survey")
NO_DIFFERENCE_BEHAVIORS = ("NO_DAY_NIGHT_DIFFERENCE",)


def depth_class_for_m(depth_m) -> str | None:
    if not isinstance(depth_m, (int, float)) or isinstance(depth_m, bool) or depth_m < 0:
        return None
    for cid, lo, hi in DEPTH_CLASS_BOUNDS_M:
        if lo <= depth_m < hi:
            return cid
    return None


def evidence_kind(rules_: list[dict]) -> str:
    """BEHAVIORAL / CATCHABILITY / MIXED / UNCLASSIFIED from the counting evidence of the rules behind a day/night band."""
    kinds = set()
    for r in rules_:
        for e in r.get("evidence") or []:
            if not e.get("counts"):
                continue
            st = str(e.get("studyType") or "").lower()
            b = any(w in st for w in _BEHAVIORAL_WORDS)
            c = any(w in st for w in _CATCH_WORDS)
            kinds.add("MIXED" if (b and c) else "BEHAVIORAL" if b else "CATCHABILITY" if c else "UNCLASSIFIED")
    if not kinds:
        return "NONE"
    known = kinds - {"UNCLASSIFIED"}
    if not known:
        return "UNCLASSIFIED"
    if "MIXED" in known or len(known) > 1:
        return "MIXED"
    return known.pop()


def day_night(use: list[dict], ctx: dict, current_daypart: str | None) -> dict:
    """Documented night behaviour, evaluated from the species' own daypart rules (independent of the current clock) plus the current daypart band."""
    by_id = {r["ruleId"]: r for r in use}
    rows = [r for r in rl.evaluate_responses(use, {"daypart": {"state": "NIGHT", "reason": "probe"}}, ctx) if r["featureId"] == "daypart"]
    night = rows[0] if rows else None
    if night is None:
        has_rule = any(r["kind"] == "RESPONSE" and r["feature"]["featureId"] == "daypart" for r in use)
        why = ("the species' day/night rule does not apply in this month/region: night behaviour is UNKNOWN here" if has_rule
               else "no evidence-backed day/night rule for this species: night behaviour is UNKNOWN, not assumed")
        return {"night": "UNKNOWN", "evidenceKind": "NONE", "reason": why,
                "currentDaypart": current_daypart or "UNKNOWN", "evidenceReferences": []}
    ids = (night.get("evidenceBasis") or {}).get("ruleIds", [])
    matched = [by_id[i] for i in ids if i in by_id]
    refs = [{"ruleId": r["ruleId"], "ruleVersion": r["ruleVersion"]} for r in matched]
    if night.get("conflict"):
        return {"night": "CONFLICT", "evidenceKind": evidence_kind(matched), "reason": "day/night evidence disagrees for this species: kept UNKNOWN rather than guessed",
                "currentDaypart": current_daypart or "UNKNOWN", "evidenceReferences": refs}
    if night["response"] == "UNKNOWN":
        return {"night": "UNKNOWN", "evidenceKind": "NONE", "reason": night.get("reason", "no rule covers night"), "currentDaypart": current_daypart or "UNKNOWN",
                "evidenceReferences": refs}
    behaviors = set(night.get("behavior") or [])
    if behaviors & set(NO_DIFFERENCE_BEHAVIORS):
        state = "NO_DIFFERENCE_DOCUMENTED"
    else:
        state = "ACTIVE_OR_SHALLOW" if night["response"] in ("FAVORABLE", "WORKABLE") else "REDUCED"
    kind = evidence_kind(matched)
    note = {"BEHAVIORAL": "from studies that observed where the fish was", "CATCHABILITY": "from catch/encounter studies: says when fish are caught, not where they sit",
            "MIXED": "from both position and catch studies", "UNCLASSIFIED": "study design not classified as position or catch evidence"}.get(kind, "")
    return {"night": state, "evidenceKind": kind, "reason": f"night band {night['response']} ({note})", "confidence": night.get("confidence"),
            "transferability": night.get("transferability"), "currentDaypart": current_daypart or "UNKNOWN", "evidenceReferences": refs}


def depth_tendencies(sp: dict, outlook: dict, all_habitat_rules: list[dict], supplied_depth: dict | None) -> dict:
    active = [h for h in sp.get("habitat") or [] if h.get("state") == "ACTIVE" and not h.get("conflict")]
    pref = sorted({h["depthClass"] for h in active if h.get("depthClass") and h["direction"] == "FAVOR"})
    avoid = sorted({h["depthClass"] for h in active if h.get("depthClass") and h["direction"] == "AVOID"})
    deep = sorted({h["habitatClass"] for h in active if h["habitatClass"] in DEEP_HABITATS and h["direction"] == "FAVOR"})
    any_depth_rule = any((r.get("habitat") or {}).get("depthClass") for r in all_habitat_rules)
    mv = outlook.get("movement")
    shallow = mv if mv in ("MORE_LIKELY_SHALLOW", "LESS_LIKELY_SHALLOW", "MIXED") else "UNKNOWN"
    out = {"shallowTendency": shallow, "preferredDepthClasses": pref, "avoidedDepthClasses": avoid, "deepHabitatPreference": deep,
           "depthKnowledge": "KNOWS_DEPTH_PREFERENCE" if any_depth_rule else "HAS_NO_DEPTH_RULE"}
    if not supplied_depth:
        out["suppliedDepth"] = {"interpretation": "NOT_SUPPLIED"}
        return out
    dc = supplied_depth.get("depthClass") or depth_class_for_m(supplied_depth.get("depthM"))
    if dc not in ft.DEPTH_CLASSES:
        out["suppliedDepth"] = {"interpretation": "UNRECOGNISED_DEPTH", "supplied": supplied_depth}
    elif not any_depth_rule:
        out["suppliedDepth"] = {"depthClass": dc, "interpretation": "NO_DEPTH_RULE", "reason": "no evidence-backed depth preference for this species"}
    elif not pref and not avoid:
        out["suppliedDepth"] = {"depthClass": dc, "interpretation": "NO_APPLICABLE_DEPTH_RULE", "reason": "the species' depth rules do not apply in this season/region"}
    elif dc in avoid:
        out["suppliedDepth"] = {"depthClass": dc, "interpretation": "AVOIDED_DEPTH"}
    else:
        out["suppliedDepth"] = {"depthClass": dc, "interpretation": "WITHIN_PREFERRED_DEPTH" if dc in pref else "OUTSIDE_PREFERRED_DEPTH"}
    return out


def species_assessment(sp: dict, ruleset: rl.RuleSet, ctx: dict, *, knowledge_version: str, evaluation_version: str | None = None,
                       supplied_depth: dict | None = None, daypart: str | None = None) -> dict:
    sid = sp["speciesId"]
    o = mo.species_outlook(sp, ctx.get("month"))
    base = {"speciesId": sid, "role": ts.role(sid), "knowledgeVersion": knowledge_version, "evaluationVersion": evaluation_version,
            "claim": {"level": 3, "maturity": "NOT_VALIDATED"}}
    if not sp.get("evaluated"):
        reason = sp.get("notEvaluatedReason") or "not evaluated"
        return base | {"assessmentStatus": "NOT_EVALUATED", "notEvaluatedReason": reason,
                       "biologicalState": {"state": "UNKNOWN", "movement": "UNKNOWN", "activity": "UNKNOWN", "basis": None, "confidence": None},
                       "seasonalState": {"calendarSeason": None, "spawnWindow": "UNKNOWN"}, "habitatPreferences": [], "depthTendencies": None,
                       "environmentalResponses": [], "spawningAssessment": {"state": "UNKNOWN", "reason": reason}, "dayNightAssessment": {"night": "UNKNOWN", "evidenceKind": "NONE", "reason": reason},
                       "supportingReasons": [], "unknowns": [reason], "confidenceLimitations": ["species not evaluated: nothing is asserted"], "evidenceReferences": []}
    use = ruleset.evaluable(sid)
    by_id = {r["ruleId"]: r for r in use}
    habitat_rules = [r for r in use if r["kind"] == "HABITAT"]
    sw = sp.get("spawnWindow") or {}
    win = rl.phenology_window(use, ctx) if use else None
    env = [{k: v for k, v in {"featureId": r["featureId"], "featureState": r["featureState"], "response": r["response"], "confidence": r.get("confidence"),
                              "transferability": r.get("transferability"), "conflict": r.get("conflict"),
                              "reason": r.get("reason") if r["response"] == "UNKNOWN" else mo._why(r)}.items() if v is not None}
           for r in sp.get("responses") or []]
    habitats = [{k: v for k, v in {"habitatClass": h["habitatClass"], "label": mo.WHERE.get(h["habitatClass"]), "direction": h["direction"], "state": h["state"],
                                   "depthClass": h.get("depthClass"), "confidence": h.get("confidence"), "transferability": h.get("transferability"),
                                   "conflict": h.get("conflict")}.items() if v is not None}
                for h in sp.get("habitat") or []]
    spawn = {"state": sw.get("state", "UNKNOWN"), "reason": sw.get("reason")}
    if win:
        spawn |= {"windowMonths": win["months"], "temperatureRangeC": win["tempC"], "confidence": win["confidence"], "transferability": win["transferability"]}
    dn = day_night(use, ctx, daypart)
    limits = list(o.get("confidenceLimitations") or [])
    limits.append("NOT_VALIDATED: research-derived; no prediction has been compared with field outcomes")
    trans = sorted({r.get("transferability") for r in sp.get("responses") or [] if r.get("transferability")} | {h.get("transferability") for h in sp.get("habitat") or [] if h.get("transferability")})
    if trans and "TRANSFERS" not in trans:
        limits.append("Southeast-reservoir transfer is " + "/".join(trans) + " for the rules used")
    if dn["evidenceKind"] == "CATCHABILITY":
        limits.append("night signal comes from catch studies, not position studies")
    ref_ids = set()
    for r in sp.get("responses") or []:
        ref_ids |= set((r.get("evidenceBasis") or {}).get("ruleIds") or [])
    ref_ids |= {h["ruleId"] for h in sp.get("habitat") or [] if h.get("ruleId")}
    if sw.get("ruleId"):
        ref_ids.add(sw["ruleId"])
    refs = [{"ruleId": i, "ruleVersion": by_id[i]["ruleVersion"]} for i in sorted(ref_ids) if i in by_id]
    unknowns = list(sp.get("unknowns") or []) + [f"{f}: input or rule state unknown" for f in o.get("unknownFeatures") or []]
    return base | {
        "assessmentStatus": "EVALUATED",
        "biologicalState": {"state": o["state"], "movement": o["movement"], "activity": o["activity"], "basis": o.get("basis"), "confidence": o["confidence"]},
        "seasonalState": {"calendarSeason": (sp.get("seasonState") or {}).get("calendarSeason"), "spawnWindow": sw.get("state", "UNKNOWN"),
                          "basis": o.get("basis")},
        "habitatPreferences": habitats,
        "depthTendencies": depth_tendencies(sp, o, habitat_rules, supplied_depth),
        "environmentalResponses": env,
        "spawningAssessment": spawn,
        "dayNightAssessment": dn,
        "supportingReasons": list(o.get("why") or []),
        "cautions": list(o.get("cautions") or []),
        "unknowns": unknowns,
        "confidenceLimitations": limits,
        "evidenceReferences": refs,
    }


def build_assessments(state: dict, ruleset: rl.RuleSet, *, knowledge_version: str, evaluation_version: str | None = None,
                      supplied_depth: dict | None = None, species: list[str] | None = None) -> dict:
    c = state.get("context") or {}
    ctx = {"month": c.get("month"), "region": c.get("region"), "waterbodyType": c.get("waterbodyType")}
    rows = [species_assessment(sp, ruleset, ctx, knowledge_version=knowledge_version, evaluation_version=evaluation_version,
                               supplied_depth=supplied_depth, daypart=c.get("daypart"))
            for sp in state.get("species") or [] if species is None or sp["speciesId"] in species]
    return {"contract": CONTRACT, "lakeId": state.get("lakeId"), "generatedAt": state.get("generatedAt"),
            "conditions": {"month": c.get("month"), "daypart": c.get("daypart"), "region": c.get("region"), "waterbodyType": c.get("waterbodyType"),
                           "inputStatus": {k: v.get("status") for k, v in (state.get("inputs") or {}).items()},
                           "features": {k: v.get("state") for k, v in (state.get("features") or {}).items()},
                           "suppliedDepth": supplied_depth},
            "knowledgeVersion": knowledge_version, "evaluationVersion": evaluation_version, "stateVersion": state.get("stateVersion"),
            "status": state.get("status"), "consumable": state.get("status") != "PILOT_INTERNAL",
            "claim": {"level": 3, "maturity": (state.get("validation") or {}).get("status", "NOT_VALIDATED")},
            "boundary": "biological interpretation only: no locations, areas, rankings or bowfishing recommendations (Intelligence owns those)",
            "species": rows}


def _walk_keys(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, f"{path}.{k}"
            yield from _walk_keys(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_keys(v, f"{path}[{i}]")


def validate_assessment(a: dict) -> list[str]:
    """Problems (empty = valid): contract id, the Fish/Intelligence boundary, vocabularies, reasons for every non-UNKNOWN state, honest seasonal priors."""
    e = []
    if a.get("contract") != CONTRACT:
        e.append("contract")
    for k, p in _walk_keys(a):
        if k in FORBIDDEN_KEYS:
            e.append(f"boundary: {p} is a bowfishing-decision field (Intelligence owns it)")
    if a.get("status") == "PILOT_INTERNAL" and a.get("consumable") is not False:
        e.append("a PILOT_INTERNAL assessment is not consumable")
    for s in a.get("species") or []:
        sid = s.get("speciesId")
        bsx = s.get("biologicalState") or {}
        if s.get("assessmentStatus") not in ASSESSMENT_STATUS:
            e.append(f"{sid}: assessmentStatus")
        if bsx.get("state") not in mo.STATES:
            e.append(f"{sid}: biologicalState.state")
        if s.get("assessmentStatus") == "NOT_EVALUATED":
            if bsx.get("state") != "UNKNOWN" or not s.get("notEvaluatedReason"):
                e.append(f"{sid}: a not-evaluated species is UNKNOWN and says why")
            continue
        if bsx.get("state") != "UNKNOWN" and not s.get("supportingReasons"):
            e.append(f"{sid}: a non-UNKNOWN assessment needs supporting reasons")
        if bsx.get("state") == "UNKNOWN" and bsx.get("confidence") is not None:
            e.append(f"{sid}: UNKNOWN carries no confidence")
        if bsx.get("basis") == "SEASONAL_PRIOR" and bsx.get("confidence") not in (None, "LOW"):
            e.append(f"{sid}: a seasonal prior is LOW confidence at most")
        if not s.get("confidenceLimitations"):
            e.append(f"{sid}: confidenceLimitations are required")
        dn = s.get("dayNightAssessment") or {}
        if dn.get("night") not in NIGHT_STATES or dn.get("evidenceKind") not in EVIDENCE_KIND:
            e.append(f"{sid}: dayNightAssessment vocabulary")
        dt_ = s.get("depthTendencies") or {}
        if dt_.get("depthKnowledge") not in DEPTH_KNOWLEDGE or (dt_.get("suppliedDepth") or {}).get("interpretation") not in SUPPLIED_DEPTH:
            e.append(f"{sid}: depthTendencies vocabulary")
        if dt_.get("shallowTendency") not in SHALLOW_TENDENCY:
            e.append(f"{sid}: depthTendencies.shallowTendency")
    return e
