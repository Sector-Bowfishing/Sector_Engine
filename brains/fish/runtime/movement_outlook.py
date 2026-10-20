"""Bowfisher-facing movement outlook for one species on one lake, derived ONLY from the already-evaluated Biological State (no rules, no evidence, no inputs of its own).

Answers: is the fish more or less likely to be shallow and shootable right now, why, where, and how sure. Deterministic and pure.
Unknown stays unknown: an unevaluated species, or one with no evaluable band, is UNKNOWN, never FAVORABLE. Claim level is 3 (Sector-derived predictive) at the
validation maturity of the state (NOT_VALIDATED until the validation record says otherwise); regional and field confidence are separate and not implied.
"""
from __future__ import annotations

OUTLOOK_VERSION = "biological-movement-outlook-v1"
STATES = ("FAVORABLE_SHALLOW", "WORKABLE", "MIXED", "LIMITING", "UNKNOWN")
SHALLOW_FEATURES = {"waterTempBand", "temperatureTrend", "temperatureCrossing15C", "temperatureCrossing18C", "temperatureCrossing20C", "stageTrend", "risingStage", "fallingStage",
                    "warmRise", "coldRise", "rapidDischargeIncrease"}
ACTIVITY_FEATURES = {"daypart", "clarityBand"}
# Features that carry CURRENT water conditions (temperature, level, clarity). Month and daypart are calendar facts, not water conditions.
ENVIRONMENTAL_FEATURES = SHALLOW_FEATURES | {"clarityBand"}
BASIS = ("CURRENT_CONDITIONS", "SEASONAL_PRIOR")
SEASONAL_PRIOR_WHY = "seasonal prior: the month (and time of day) fit this fish's researched habits; no current water reading confirms it"
HABITAT_WHY = "its researched habitat use applies in this month and season"
SEASONAL_PRIOR_LIMIT = "seasonal prior only: no water temperature, level or clarity input contributed, so confidence is capped at LOW"
CONF_ORDER = ("LOW", "MEDIUM", "HIGH")
GOOD, BAD = ("FAVORABLE",), ("LIMITING", "BLOCKING")

PHRASE = {
    ("risingStage", "TRUE"): "the lake level is rising", ("risingStage", "FALSE"): "the lake level is not rising", ("fallingStage", "TRUE"): "the lake level is falling",
    ("warmRise", "TRUE"): "the level is rising in warm water", ("coldRise", "TRUE"): "the level is rising in cold water",
    ("daypart", "NIGHT"): "it is night", ("daypart", "TWILIGHT"): "it is dusk or dawn", ("daypart", "DAY"): "it is daytime",
    ("clarityBand", "TURBID"): "the water is turbid", ("clarityBand", "CLEAR"): "the water is clear", ("clarityBand", "MODERATE"): "the water clarity is moderate",
    ("temperatureTrend", "WARMING"): "the water is warming", ("temperatureTrend", "COOLING"): "the water is cooling",
    ("stageTrend", "FALLING_RAPIDLY"): "the level is falling fast",
}
TEMP_PHRASE = {"LT_10C": "water is under 50 F", "C10_15": "water is about 50-59 F", "C15_18": "water is about 59-64 F", "C18_21": "water is about 64-70 F",
               "C21_26": "water is about 70-79 F", "C26_30": "water is about 79-86 F", "GE_30C": "water is over 86 F"}
WHERE = {"shallowVegetatedHabitat": "shallow vegetated coves and weedy shallows", "floodedVegetation": "newly flooded vegetation and margins", "backwaterHabitat": "backwaters, sloughs and oxbows",
         "tributaryMouth": "creek and tributary mouths", "tributaryAccess": "tributary runs", "tailwaterHabitat": "tailwaters below dams", "channelBorder": "channel borders",
         "deepChannelPool": "deep channel pools (not shootable)", "woodyCover": "woody cover and brush", "openWaterBasin": "open-water basins"}
SPAWN_PHRASE = {"IN_WINDOW": "it is inside the spawning window"}
SPAWN_CAUTION = {"TEMP_ONLY": "water is in spawning range but the month is outside the spawning window", "MONTH_ONLY": "the month fits spawning but the water is outside the spawning temperature range"}


def _why(r: dict) -> str:
    f, s = r["featureId"], r["featureState"]
    p = TEMP_PHRASE.get(s) if f == "waterTempBand" else PHRASE.get((f, s))
    return p or f"{f} is {s}"


def _min_conf(confs):
    cs = [c for c in confs if c in CONF_ORDER]
    return min(cs, key=CONF_ORDER.index) if cs else None


def _net(rows) -> str | None:
    g = sum(r["response"] in GOOD for r in rows)
    b = sum(r["response"] in BAD for r in rows)
    w = sum(r["response"] == "WORKABLE" for r in rows)
    if not (g or b or w):
        return None
    if g and b:
        return "MIXED"
    return "FAVORABLE" if g else ("LIMITING" if b else "WORKABLE")


def basis_of(sp: dict) -> str:
    """CURRENT_CONDITIONS when a supplied water condition (temperature, level, clarity) produced a known band or a temperature-based spawn state;
    otherwise the result rests on month/daypart knowledge alone and is a SEASONAL_PRIOR (audit 2026-10-19 defect A)."""
    if any(r["response"] != "UNKNOWN" and r["featureId"] in ENVIRONMENTAL_FEATURES for r in sp.get("responses") or []):
        return "CURRENT_CONDITIONS"
    if (sp.get("spawnWindow") or {}).get("state") in ("IN_WINDOW", "MONTH_ONLY", "TEMP_ONLY"):
        return "CURRENT_CONDITIONS"
    return "SEASONAL_PRIOR"


def species_outlook(sp: dict, month: int | None = None, rule_text: dict | None = None) -> dict:
    base = {"speciesId": sp["speciesId"], "claim": {"level": 3}}
    if not sp.get("evaluated"):
        reason = sp.get("notEvaluatedReason") or "not evaluated for this lake"
        return base | {"state": "UNKNOWN", "movement": "UNKNOWN", "activity": "UNKNOWN", "why": [], "cautions": [], "where": [], "confidence": None,
                       "note": reason, "notEvaluatedReason": reason, "basis": None, "confidenceLimitations": []}
    known = [r for r in sp.get("responses") or [] if r["response"] != "UNKNOWN"]
    shallow = [r for r in known if r["featureId"] in SHALLOW_FEATURES]
    act = [r for r in known if r["featureId"] in ACTIVITY_FEATURES]
    ns, na = _net(shallow), _net(act)
    habitats = [h for h in sp.get("habitat") or [] if h.get("state") == "ACTIVE" and h["direction"] == "FAVOR" and not h.get("conflict")]
    sw = (sp.get("spawnWindow") or {}).get("state")
    movement = {"FAVORABLE": "MORE_LIKELY_SHALLOW", "LIMITING": "LESS_LIKELY_SHALLOW"}.get(ns, "UNKNOWN" if ns is None else "MIXED")
    if movement in ("UNKNOWN", "MIXED") and habitats and ns != "LIMITING":
        movement = "MOVES_TO_HABITAT"
    activity = {"FAVORABLE": "ACTIVITY_UP", "WORKABLE": "ACTIVITY_UP", "LIMITING": "ACTIVITY_DOWN"}.get(na, "UNKNOWN" if na is None else "MIXED")
    nets = [x for x in (ns, na) if x]
    if not nets and not habitats and sw not in ("IN_WINDOW",):
        state = "UNKNOWN"
    elif "MIXED" in nets or (any(x in ("FAVORABLE", "WORKABLE") for x in nets) and "LIMITING" in nets):
        state = "MIXED"
    elif "LIMITING" in nets:
        state = "LIMITING"
    elif "FAVORABLE" in nets or (habitats and sw == "IN_WINDOW"):
        state = "FAVORABLE_SHALLOW"
    elif "WORKABLE" in nets or habitats:
        state = "WORKABLE"
    else:
        state = "UNKNOWN"
    why = [_why(r) for r in shallow + act][:6]
    if sw in SPAWN_PHRASE:
        why.append(SPAWN_PHRASE[sw])
    cautions = [SPAWN_CAUTION[sw]] if sw in SPAWN_CAUTION else []
    where = []
    for h in habitats:
        w = WHERE.get(h["habitatClass"])
        if w and w not in where:
            where.append(w)
    conf = _min_conf([r.get("confidence") for r in shallow + act] + [h.get("confidence") for h in habitats])
    basis = basis_of(sp) if state != "UNKNOWN" else None
    limits = []
    if basis == "SEASONAL_PRIOR":
        why.insert(0, SEASONAL_PRIOR_WHY)
        limits.append(SEASONAL_PRIOR_LIMIT)
        conf = "LOW" if conf else conf
    elif state != "UNKNOWN" and not why and habitats:
        why.append(HABITAT_WHY)          # never a silent non-UNKNOWN result (audit 2026-10-19: always explain)
    if state == "UNKNOWN":
        conf = None
    rule_ids = sorted({i for r in shallow + act for i in (r.get("evidenceBasis") or {}).get("ruleIds", [])} | {h["ruleId"] for h in habitats if h.get("ruleId")})
    return base | {"state": state, "movement": movement, "activity": activity, "why": why, "cautions": cautions, "where": where, "confidence": conf,
                   "basis": basis, "confidenceLimitations": limits,
                   "unknownFeatures": sorted({r["featureId"] for r in sp.get("responses") or [] if r["response"] == "UNKNOWN"}),
                   "trace": explain(sp, month, rule_ids, rule_text)}


def explain(sp: dict, month: int | None, rule_ids: list, rule_text: dict | None = None) -> dict:
    """The WHY? panel: current inputs -> matched knowledge -> season check -> result. Internal/Ops debugging only (carries rule ids); the Intelligence view never includes it."""
    inputs = [{"feature": r["featureId"], "state": r["featureState"], "band": r["response"]} for r in sp.get("responses") or []]
    sw = (sp.get("spawnWindow") or {})
    gated = (sp.get("knowledge") or {}).get("rules", {}).get("seasonGated", 0)
    return {"inputs": inputs, "matchedKnowledge": [{"ruleId": i, "plain": (rule_text or {}).get(i)} for i in rule_ids],
            "seasonCheck": {"month": month, "spawnWindow": sw.get("state") or "UNKNOWN", "spawnRuleApplies": sw.get("state") == "IN_WINDOW", "rulesNotEvaluatedForSeason": gated},
            "result": "no rule applies" if not rule_ids else f"{len(rule_ids)} rule(s) applied"}


def lake_outlook(state: dict, roles: dict | None = None, rule_text: dict | None = None) -> dict:
    """roles = {speciesId: TARGET|SECONDARY|KNOWLEDGE_ONLY}; targets first, knowledge-only species are returned but flagged."""
    out = []
    for sp in state.get("species") or []:
        o = species_outlook(sp, state.get("context", {}).get("month"), rule_text)
        o["role"] = (roles or {}).get(sp["speciesId"], "KNOWLEDGE_ONLY" if roles else None)
        out.append(o)
    order = {"TARGET": 0, "SECONDARY": 1, "KNOWLEDGE_ONLY": 2, None: 3}
    out.sort(key=lambda o: (order[o["role"]], o["speciesId"]))
    return {"outlookVersion": OUTLOOK_VERSION, "lakeId": state["lakeId"], "generatedAt": state["generatedAt"],
            "claim": {"level": 3, "maturity": (state.get("validation") or {}).get("status", "NOT_VALIDATED")},
            "freshness": {k: {"status": v.get("status"), "ageHours": v.get("ageHours")} for k, v in (state.get("inputs") or {}).items()},
            "status": state["status"], "consumable": state["status"] != "PILOT_INTERNAL", "species": out}
