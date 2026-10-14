"""biological-species-profile-v1: a deterministic, self-describing study guide for one species, generated from canonical Biological state.

Inputs (all already in the Biological bundle): the species-v2 profile, the movement card (with source verification), the machine rules, the review ledger,
validation counts. Output is the ONLY thing Sector Ops needs to render a fish: it never reads rules, cards, packets or ledgers itself.

Principles enforced here (and tested):
  * UNKNOWN stays UNKNOWN: an unanswered question is listed as open, never scored 0 or filled for presentation.
  * No month is invented from a season: every month states its `precision` (MONTH | SEASONAL | INFERRED | UNKNOWN).
  * Base seasonal pattern and condition modifiers are separate: a rule with no season bound is a modifier flagged UNBOUNDED, never a calendar fact.
  * General behaviour and regional (Southeast) confidence are separate fields.
  * Knowledge, human review and field validation are independent axes.
  * Presence on a lake is Lake-Brain truth and is never part of a profile; current conditions are a different payload (movement_outlook).
  * No private paths, bucket names or research text leave through this contract.
Pure functions; no I/O.
"""
from __future__ import annotations

import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import movement_cards as mc      # noqa: E402
import movement_outlook as mo      # noqa: E402
import review_plain as rp      # noqa: E402
import species_audit as sa      # noqa: E402
import target_set as ts      # noqa: E402

CONTRACT = "biological-species-profile-v1"
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
SEASON_OF = {12: "WINTER", 1: "WINTER", 2: "WINTER", 3: "SPRING", 4: "SPRING", 5: "SPRING", 6: "SUMMER", 7: "SUMMER", 8: "SUMMER", 9: "FALL", 10: "FALL", 11: "FALL"}
COVERAGE = ("STRONG", "MODERATE", "WEAK", "UNKNOWN")
MOVEMENT_STATES = ("WINTER_HOLDING", "PRE_SPAWN", "SPAWN", "POST_SPAWN", "SUMMER_PATTERN", "FALL_TRANSITION", "SHALLOW_ACTIVE", "DEEPER_HOLDING", "TRIBUTARY_MOVEMENT", "BACKWATER_USE", "UNKNOWN")
SHALLOW = ("HIGH", "MODERATE", "CONDITIONAL", "LOW", "UNKNOWN")
PRECISION = ("MONTH", "SEASONAL", "INFERRED", "UNKNOWN")
SPAWN_STATE = ("ACTIVE_WINDOW", "OUTSIDE_WINDOW", "UNKNOWN")
CONF = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
REVIEW = ("UNREVIEWED", "ACCEPTED", "REJECTED", "NEEDS_MORE_EVIDENCE")
FIELD = ("NOT_VALIDATED", "FIELD_PLANNED", "OBSERVATIONS_IN_PROGRESS", "VALIDATED", "FAILED")
PRIORITY = ("HIGH", "MEDIUM", "LOW", "DO_NOT_RESEARCH")
CATEGORIES = ("seasonal", "spawn", "temperature", "depth", "hydrology", "vegetation", "night", "clarity", "current", "regional")
SECTIONS = ("spawn", "temperature", "depth", "hydrology", "habitat", "dayNight", "clarityLight", "currentWaterbody")
IMPORTANCE = {"night": 1.0, "depth": 1.0, "regional": 0.9, "hydrology": 0.8, "spawn": 0.8, "seasonal": 0.8, "temperature": 0.7, "vegetation": 0.6, "current": 0.6, "clarity": 0.4}
CHANGES_RECOMMENDATION = {"seasonal": True, "spawn": True, "temperature": True, "depth": True, "hydrology": True, "vegetation": True, "night": True, "clarity": False, "current": True, "regional": True}
TIER_FACTOR = {"TARGET": 1.0, "SECONDARY": 0.6, "KNOWLEDGE_ONLY": 0.15}
IF_LEARNED = {
    "seasonal": "Would show when this fish is in the shallows through the year, changing which months to fish it.",
    "spawn": "Would pin down the spawn window and habitat, the best shallow period for this fish.",
    "temperature": "Would show which water temperatures put the fish shallow or push it deep, changing day-to-day calls.",
    "depth": "Would change whether Sector points a bowfisher at shallow flats or deeper edges.",
    "hydrology": "Would show what rising, falling and flooded water do to where the fish sits.",
    "vegetation": "Would change which cover and habitat to prioritise on the water.",
    "night": "Would change whether Sector recommends shallow flats or deeper edges after dark, when most bowfishing happens.",
    "clarity": "Would only refine how clear or muddy water changes the fish's response; unlikely to change where to look.",
    "current": "Would change where in a lake or river system (creek, tailwater, backwater, channel edge) to look.",
    "regional": "Would show whether the general behaviour holds on Southeast reservoirs, changing how much to trust advice there.",
}
CATEGORY_LABEL = {"seasonal": "Seasonal movement", "spawn": "Spawn", "temperature": "Temperature", "depth": "Depth / shallow behavior", "hydrology": "Water level / hydrology", "vegetation": "Vegetation / habitat",
                  "night": "Day / night", "clarity": "Clarity / light", "current": "Current / waterbody use", "regional": "Southeast / regional"}
CAT_FIELDS = {"seasonal": mc.FIELDS["seasonal"], "spawn": mc.FIELDS["spawn"], "temperature": mc.FIELDS["temperature"], "depth": mc.FIELDS["depth"], "hydrology": mc.FIELDS["hydrology"],
              "vegetation": mc.FIELDS["vegetationHabitat"], "night": [("dayNightBehavior", k) for k in ("day", "dusk", "night", "dawn")],
              "clarity": [("clarityLightResponse", k) for k in ("brightSun", "lowLight", "turbid", "clear")], "current": mc.FIELDS["current"]}
CAT_COMPONENT = {"seasonal": "seasonal", "spawn": "spawn", "temperature": "temperature", "depth": "depth", "hydrology": "hydrology", "vegetation": "vegetationHabitat", "night": "nightLight",
                 "clarity": "nightLight", "current": "current"}
CAT_TAGS = {"seasonal": ("seasonal", "summer"), "spawn": ("spawn", "spawn temperature"), "temperature": ("temperature",), "depth": ("depth", "habitat"), "hydrology": ("hydrology",),
            "vegetation": ("vegetation", "vegetationHabitat", "habitat"), "night": ("night", "nightLight", "dayNight"), "clarity": ("clarity", "nightLight"), "current": ("current", "backwater")}
FIELD_LABEL = {"timing": "Timing", "habitat": "Habitat", "shallowMovement": "Shallow movement", "temperatureF": "Temperature", "triggers": "What triggers movement", "preSpawn": "Pre-spawn", "spawn": "Spawn",
               "summer": "Summer", "coldSlowdown": "Cold-water slowdown", "shallowWhen": "Shallow when", "deepWhen": "Deeper when", "usefulDepthHabitat": "Useful depth and habitat", "rising": "Rising water",
               "falling": "Falling water", "floodedShoreline": "Flooded shoreline", "current": "Current", "discharge": "River discharge", "backwaterConnectivity": "Backwater connection", "day": "Day", "dusk": "Dusk",
               "night": "Night", "dawn": "Dawn", "brightSun": "Bright sun", "lowLight": "Low light", "turbid": "Turbid water", "clear": "Clear water", "mainRiver": "Main river", "reservoir": "Reservoir",
               "creekTributary": "Creek / tributary", "backwaterSlough": "Backwater / slough", "shorelineFlat": "Shoreline / flat", "channelEdge": "Channel edge", "winter": "Winter", "postSpawn": "Post-spawn", "fall": "Fall"}
MONTH_TOKENS = {m.lower(): i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_RANGE_RE = re.compile(_MONTH_RE + r"\s*(?:-|–|to|through|and)\s*(?:early |mid |late )?" + _MONTH_RE, re.I)
HAB_RULE_CAT = {"shallowVegetatedHabitat": "vegetation", "floodedVegetation": "vegetation", "woodyCover": "vegetation", "backwaterHabitat": "current", "tributaryMouth": "current", "tributaryAccess": "current",
                "tailwaterHabitat": "current", "channelBorder": "current", "deepChannelPool": "depth", "openWaterBasin": "depth"}
RESP_CAT = {"waterTempBand": "temperature", "temperatureTrend": "temperature", "temperatureCrossing15C": "temperature", "temperatureCrossing18C": "temperature", "temperatureCrossing20C": "temperature",
            "stageTrend": "hydrology", "risingStage": "hydrology", "fallingStage": "hydrology", "warmRise": "hydrology", "coldRise": "hydrology", "rapidDischargeIncrease": "hydrology", "clarityBand": "clarity", "daypart": "night"}
TRANSFER_CONF = {"TRANSFERS": "HIGH", "PARTIAL": "MEDIUM", "UNTESTED": "LOW"}


def parse_months(text: str) -> list[int] | None:
    """Month range named in a sentence ('April-June', 'late Feb to Apr'); wraps the year. None when no explicit range is named. Never guesses from a season word."""
    m = _RANGE_RE.search(str(text or ""))
    if not m:
        return None
    a, b = MONTH_TOKENS[m.group(1).lower()[:3]], MONTH_TOKENS[m.group(2).lower()[:3]]
    out, i = [a], a
    while i != b:
        i = i % 12 + 1
        out.append(i)
        if len(out) > 12:
            return None
    return out


def short(text, n=240):
    s = " ".join(str(text or "").split())
    if len(s) <= n:
        return s
    cut = max(s.rfind(". ", 0, n), s.rfind("; ", 0, n))
    return (s[: cut + 1] if cut > 80 else s[: n - 1].rstrip() + "…")


def _known(v) -> bool:
    return mc._known(v)


def _get(card, group, field):
    v = ((card or {}).get("card") or {}).get(group)
    return v.get(field) if field and isinstance(v, dict) else v


def _fmt_temp(v) -> str:
    if isinstance(v, dict):
        lo, hi, pk = v.get("min"), v.get("max"), v.get("peak")
        parts = []
        if isinstance(lo, (int, float)) or isinstance(hi, (int, float)):
            parts.append(f"{lo if lo is not None else '?'}-{hi if hi is not None else '?'} F")
        if isinstance(pk, (int, float)):
            parts.append(f"peak about {pk:g} F")
        if _known(v.get("note")):
            parts.append(short(v["note"], 160))
        return "; ".join(parts)
    return str(v or "")


def _min_conf(cs):
    cs = [c for c in cs if c in ("LOW", "MEDIUM", "HIGH")]
    return min(cs, key=("LOW", "MEDIUM", "HIGH").index) if cs else "UNKNOWN"


def rule_category(r: dict) -> str:
    if r["kind"] == "PHENOLOGY":
        return "spawn"
    if r["kind"] == "RESPONSE":
        return RESP_CAT.get(r["feature"]["featureId"], "hydrology")
    h = r["habitat"]
    return "depth" if h.get("depthClass") and h["habitatClass"] not in ("backwaterHabitat", "tributaryMouth", "tributaryAccess", "tailwaterHabitat") else HAB_RULE_CAT.get(h["habitatClass"], "vegetation")


def seasonality(r: dict) -> str:
    return "BOUNDED" if (r.get("applicability") or {}).get("months") else "UNBOUNDED"


def review_state(r: dict, ledger: dict) -> str:
    if r["status"] == "APPROVED":
        return "ACCEPTED"
    d = (ledger or {}).get(r["ruleId"])
    return {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "NEEDS_MORE_EVIDENCE": "NEEDS_MORE_EVIDENCE", "CHANGES": "NEEDS_MORE_EVIDENCE"}.get(d, "UNREVIEWED")


def _streams(card, tags) -> tuple[int, int, list[str]]:
    """(independent inspected credible streams, unverified credible sources, source ids) supporting any tag; partial support counts only for the topics the verifier affirmed."""
    import adopt_cards as ac
    good, unread, ids = set(), 0, []
    for s in (card or {}).get("sources") or []:
        sup = set(s.get("supports") or [])
        v = s.get("verification")
        if v == "NOT_SUPPORTED":
            sup &= set(s.get("supportedTags") or [])
        if not sup & set(tags) or s.get("type") == "ANECDOTAL":
            continue
        if v in ("READ-FULL", "READ-ABSTRACT") or (v == "NOT_SUPPORTED" and s.get("supportedTags")) or (s.get("type") == "PACKET" and v != "NOT_SUPPORTED"):
            good.add(ac.stream_key(s))
            ids.append(s["id"])
        else:
            unread += 1
    return len(good), unread, ids


def category_coverage(card, rules, category: str, tally: dict) -> dict:
    """STRONG / MODERATE / WEAK / UNKNOWN plus an internal 0-10 completeness that is None (never 0) when nothing is known."""
    if category == "regional":
        n = sum(tally.values())
        if not n:
            return {"status": "UNKNOWN", "completeness": None, "evidence": "NONE", "note": "no usable rules to judge Southeast applicability"}
        share = (tally.get("TRANSFERS", 0) + 0.5 * tally.get("PARTIAL", 0)) / n
        st = "STRONG" if share >= 0.6 else "MODERATE" if share >= 0.3 else "WEAK"
        return {"status": st, "completeness": round(10 * share, 1), "evidence": "RULE_TRANSFER", "note": f"{tally.get('TRANSFERS', 0)} Southeast-supported, {tally.get('PARTIAL', 0)} partly, {tally.get('UNTESTED', 0)} untested of {n} usable rules"}
    fields = CAT_FIELDS[category]
    n_known = sum(_known(_get(card, a, b)) for a, b in fields)
    rule_cat = [r for r in rules if r["status"] in ("RECONCILED", "APPROVED") and rule_category(r) == category]
    if not card or (not n_known and not rule_cat):
        return {"status": "UNKNOWN", "completeness": None, "evidence": "NONE", "note": "nothing recorded"}
    fill = n_known / len(fields)
    comp = ((card or {}).get("componentScores") or {}).get(CAT_COMPONENT[category]) or {}
    raw = float(comp.get("score", 0)) if isinstance(comp.get("score"), (int, float)) else 0.0
    raw = min(raw, 10 * fill + 1) if fill else min(raw, 3.0)
    streams, unread, _ = _streams(card, CAT_TAGS[category])
    cap = 3.0 if not streams else (6.0 if streams == 1 else 8.0)
    score = round(min(max(raw, 1.0 if rule_cat else 0.0), cap), 1)
    if rule_cat and not n_known:
        score = min(score, 3.0)
    ev = "UNVERIFIED" if not streams else ("SINGLE_SOURCE" if streams == 1 else "MULTI_SOURCE")
    st = "STRONG" if score >= 7 else "MODERATE" if score >= 4 else "WEAK"
    return {"status": st, "completeness": score, "evidence": ev, "note": f"{n_known} of {len(fields)} sub-questions answered; {streams} inspected independent source(s)" + (f", {unread} unverified" if unread else "")}


def research_priority(species_id: str, role: str, category: str, cov: dict) -> tuple[str, float]:
    if species_id in ts.DO_NOT_RESEARCH:
        return "DO_NOT_RESEARCH", 0.0
    gap = 1.0 if cov["completeness"] is None else max(0.0, (10 - cov["completeness"]) / 10)
    if cov["status"] == "STRONG":
        return "LOW", round(IMPORTANCE[category] * TIER_FACTOR[role] * gap, 3)
    score = IMPORTANCE[category] * TIER_FACTOR[role] * gap * (1.0 if CHANGES_RECOMMENDATION[category] else 0.5)
    return ("HIGH" if score >= 0.5 else "MEDIUM" if score >= 0.25 else "LOW"), round(score, 3)


def _statements(card, category_fields, claim_prefix, claims, card_conf, card_reg):
    out, open_q = [], []
    for g, f in category_fields:
        v = _get(card, g, f)
        label = FIELD_LABEL.get(f or g, (f or g))
        if f == "temperatureF":
            v = _fmt_temp(v)
        if _known(v):
            cid = f"card:{g}:{f}" if f else f"card:{g}"
            claims.setdefault(cid, {"type": "CARD", "summary": f"{label}: {short(v, 120)}"})
            out.append({"label": label, "text": short(v), "confidence": card_conf, "regionalConfidence": card_reg, "claimIds": [cid]})
        else:
            open_q.append(label)
    return out, open_q


def season_review(r: dict, assertions: dict) -> str:
    """BOUNDED (months or spawn window) | YEAR_ROUND (reviewer-asserted) | NEEDS_REVIEW / NOT_ESTABLISHED (does not fire)."""
    if r["kind"] == "PHENOLOGY" or (r.get("applicability") or {}).get("months"):
        return "BOUNDED"
    return assertions.get(r["ruleId"], "NOT_ESTABLISHED")


def _rule_row(r, ledger, preds, claims, assertions=None):
    plain = {"when": rp.condition(r), "expects": rp.conclusion(r), "bowfisherMeaning": rp.meaning(r)}
    n = len({e["streamId"] for e in r["evidence"] if e.get("counts")})
    claims[r["ruleId"]] = {"type": "RULE", "summary": f"{plain['when']} -> {plain['expects']}", "maturity": r["status"], "evidenceStrength": "NONE" if not n else "SINGLE_SOURCE" if n == 1 else "MULTI_SOURCE",
                           "inspected": any(e.get("counts") for e in r["evidence"]), "sourceCount": n}
    return {"ruleId": r["ruleId"], "ruleVersion": r["ruleVersion"], "kind": r["kind"], "category": rule_category(r), **plain, "status": r["status"], "review": review_state(r, ledger),
            "field": "NOT_VALIDATED", "seasonality": seasonality(r), "seasonReview": season_review(r, assertions or {}), "fires": season_review(r, assertions or {}) in ("BOUNDED", "YEAR_ROUND") and r["status"] in ("RECONCILED", "APPROVED"),
            "months": (r.get("applicability") or {}).get("months") or None, "confidence": r["confidence"],
            "regionalConfidence": TRANSFER_CONF[r["transferability"]["southeastReservoir"]], "predictionsLogged": preds, "claimIds": [r["ruleId"]]}


def build_profile(species_id: str, *, profile: dict | None, card: dict | None, rules: list[dict], ledger: dict | None = None, validation: dict | None = None,
                  generated_from: dict | None = None, canonical: bool = True, season_assertions: dict | None = None) -> dict:
    """Pure builder. `profile` = species-v2 profile; `card` = movement card with per-source verification; `rules` = this species' non-retired rules."""
    profile = profile or {}
    assertions = season_assertions or {}
    ledger = ledger or {}
    validation = validation or {}
    role = ts.role(species_id)
    hab = sa.habitat_for(species_id)
    assessed = profile.get("assessment") == "ASSESSED"
    claims: dict = {}
    usable = sorted([r for r in rules if r["status"] in ("RECONCILED", "APPROVED")], key=lambda r: r["ruleId"])
    drafts = sorted([r for r in rules if r["status"] == "DRAFT"], key=lambda r: r["ruleId"])
    pcount = validation.get("predictions", {}).get(species_id, 0)
    rule_rows = [_rule_row(r, ledger, pcount, claims, assertions) for r in usable + drafts]
    cconf = ((card or {}).get("card") or {}).get("generalConfidence", "UNKNOWN") if card else "UNKNOWN"
    rconf = ((card or {}).get("card") or {}).get("regionalConfidence", "UNKNOWN") if card else "UNKNOWN"
    tally = {"TRANSFERS": 0, "PARTIAL": 0, "UNTESTED": 0}
    for r in usable:
        tally[r["transferability"]["southeastReservoir"]] += 1
    cov = {c: category_coverage(card, rules, c, tally) for c in CATEGORIES}
    # ---- sections
    secs = {}
    def build_section(name, cat, fields, extra_rules=()):
        stm, open_q = _statements(card, fields, name, claims, cconf, rconf) if card else ([], [FIELD_LABEL.get(f or g, f or g) for g, f in fields])
        rr = [x for x in rule_rows if x["category"] in extra_rules and x["status"] != "DRAFT"]
        return {"coverage": cov[cat]["status"], "completeness": cov[cat]["completeness"], "statements": stm, "openQuestions": open_q, "rules": [x["ruleId"] for x in rr]}
    secs["spawn"] = build_section("spawn", "spawn", [("spawn", "timing"), ("spawn", "temperatureF"), ("spawn", "habitat"), ("spawn", "shallowMovement"), ("seasonalMovement", "preSpawn"), ("seasonalMovement", "postSpawn")], ("spawn",))
    secs["temperature"] = build_section("temperature", "temperature", mc.FIELDS["temperature"], ("temperature",))
    secs["depth"] = build_section("depth", "depth", mc.FIELDS["depth"], ("depth",))
    secs["hydrology"] = build_section("hydrology", "hydrology", mc.FIELDS["hydrology"], ("hydrology",))
    secs["habitat"] = build_section("habitat", "vegetation", mc.FIELDS["vegetationHabitat"], ("vegetation",))
    secs["dayNight"] = build_section("dayNight", "night", CAT_FIELDS["night"], ("night",))
    secs["clarityLight"] = build_section("clarityLight", "clarity", CAT_FIELDS["clarity"], ("clarity",))
    secs["currentWaterbody"] = build_section("currentWaterbody", "current", mc.FIELDS["current"], ("current",))
    # ---- yearly movement
    def _fires(r):
        return season_review(r, assertions) in ("BOUNDED", "YEAR_ROUND")
    conflict_ids = set()
    resp = [r for r in usable if r["kind"] == "RESPONSE" and _fires(r)]
    for i, a in enumerate(resp):
        for b2 in resp[i + 1:]:
            if a["feature"]["featureId"] == b2["feature"]["featureId"] and set(a["feature"]["states"]) & set(b2["feature"]["states"]) and a["response"] != b2["response"]:
                ma, mb = (a.get("applicability") or {}).get("months"), (b2.get("applicability") or {}).get("months")
                if not ma or not mb or set(ma) & set(mb):
                    conflict_ids |= {a["ruleId"], b2["ruleId"]}
    spawn_rules = [r for r in usable if r["kind"] == "PHENOLOGY" and (r.get("applicability") or {}).get("months")]
    spawn_months = sorted({m for r in spawn_rules for m in r["applicability"]["months"]})
    spawn_basis = "RULE" if spawn_months else None
    if not spawn_months:
        pm = parse_months(_get(card, "spawn", "timing"))
        if pm:
            spawn_months, spawn_basis = sorted(pm), "CARD_TEXT"
    season_known = {s: _known(_get(card, "seasonalMovement", k)) for s, k in (("WINTER", "winter"), ("SUMMER", "summer"), ("FALL", "fall"))}
    pre_known, post_known = _known(_get(card, "seasonalMovement", "preSpawn")), _known(_get(card, "seasonalMovement", "postSpawn"))
    shallow_spawn = any(r["kind"] == "HABITAT" and r["habitat"]["direction"] == "FAVOR" and r["habitat"]["habitatClass"] in ("shallowVegetatedHabitat", "floodedVegetation") for r in usable) or _known(_get(card, "spawn", "shallowMovement"))
    def card_claim(key, label):
        cid = "card:" + key.replace(".", ":")        # RTDB keys may not contain a dot
        group, field = key.split(".", 1)
        v = _get(card, group, field)
        if _known(v):
            claims.setdefault(cid, {"type": "CARD", "summary": f"{label}: {short(v, 120)}"})
        return cid
    months_out = []
    for m in range(1, 13):
        bounded = [r for r in usable if (r.get("applicability") or {}).get("months") and m in r["applicability"]["months"]]
        unbounded_h = [r for r in usable if r["kind"] == "HABITAT" and not (r.get("applicability") or {}).get("months") and not r.get("requires") and _fires(r)]
        states, prec, ids = [], [], []
        in_spawn = m in spawn_months
        if in_spawn:
            states.append("SPAWN"); prec.append("MONTH"); ids += [r["ruleId"] for r in spawn_rules if m in r["applicability"]["months"]] or [card_claim("spawn.timing", "Spawn timing")]
        elif spawn_months and pre_known and m == (min(spawn_months) - 2) % 12 + 1:
            states.append("PRE_SPAWN"); prec.append("INFERRED"); ids.append(card_claim("seasonalMovement.preSpawn", "Pre-spawn"))
        elif spawn_months and post_known and m == max(spawn_months) % 12 + 1:
            states.append("POST_SPAWN"); prec.append("INFERRED"); ids.append(card_claim("seasonalMovement.postSpawn", "Post-spawn"))
        season = SEASON_OF[m]
        cold = [r for r in bounded if r["kind"] == "RESPONSE" and r["feature"]["featureId"] == "waterTempBand" and r["response"] in ("LIMITING", "BLOCKING")]
        if cold and season == "WINTER":                      # a cold-water limit is a temperature MODIFIER; it defines a base state only in winter months
            states.append("DEEPER_HOLDING"); prec.append("MONTH"); ids += [r["ruleId"] for r in cold]
        if not in_spawn:
            if season == "WINTER" and season_known["WINTER"]:
                states.append("WINTER_HOLDING"); prec.append("SEASONAL"); ids.append(card_claim("seasonalMovement.winter", "Winter"))
            elif season == "SUMMER" and season_known["SUMMER"]:
                states.append("SUMMER_PATTERN"); prec.append("SEASONAL"); ids.append(card_claim("seasonalMovement.summer", "Summer"))
            elif season == "FALL" and season_known["FALL"]:
                states.append("FALL_TRANSITION"); prec.append("SEASONAL"); ids.append(card_claim("seasonalMovement.fall", "Fall"))
        base_h = [r for r in bounded if r["kind"] == "HABITAT" and not r.get("requires")] + unbounded_h
        for r in base_h:
            if r["habitat"]["direction"] != "FAVOR":
                continue
            tag = {"shallowVegetatedHabitat": "SHALLOW_ACTIVE", "floodedVegetation": "SHALLOW_ACTIVE", "backwaterHabitat": "BACKWATER_USE", "tributaryMouth": "TRIBUTARY_MOVEMENT", "tributaryAccess": "TRIBUTARY_MOVEMENT"}.get(r["habitat"]["habitatClass"])
            if tag and tag not in states:
                states.append(tag); prec.append("MONTH" if (r.get("applicability") or {}).get("months") else "SEASONAL"); ids.append(r["ruleId"])
        habitats = sorted({r["habitat"]["habitatClass"] for r in base_h if r["habitat"]["direction"] == "FAVOR"})
        depth_cls = sorted({r["habitat"]["depthClass"] for r in base_h if r["habitat"].get("depthClass")})
        sh = "UNKNOWN"
        if in_spawn and shallow_spawn:
            sh = "HIGH"
        elif season == "WINTER" and cold:
            sh = "LOW"
        elif any(x in ("SHALLOW_ACTIVE", "BACKWATER_USE", "TRIBUTARY_MOVEMENT") for x in states):
            sh = "MODERATE"
        elif any(r["kind"] in ("RESPONSE", "HABITAT") and (r["kind"] == "HABITAT" or r["response"] in ("FAVORABLE", "WORKABLE")) for r in bounded):
            sh = "CONDITIONAL"
        temp_ctx = ["if " + rp.condition(r).split("; ", 1)[-1] + ": " + rp.conclusion(r) for r in bounded if rule_category(r) == "temperature" and r["ruleId"] not in conflict_ids]
        if in_spawn and spawn_rules:
            t = spawn_rules[0]["phenology"]["tempC"]
            temp_ctx.insert(0, f"spawns when water is about {t['min'] * 9 / 5 + 32:.0f}-{t['max'] * 9 / 5 + 32:.0f} F")
        hyd = [rp.conclusion(r) + ": " + rp.condition(r).split("; ", 1)[-1] for r in bounded if rule_category(r) == "hydrology" and r["ruleId"] not in conflict_ids]
        dn = [rp.conclusion(r) + ": " + rp.condition(r).split("; ", 1)[-1] for r in bounded if rule_category(r) == "night" and r["ruleId"] not in conflict_ids]
        if any(r["ruleId"] in conflict_ids and rule_category(r) == "night" for r in bounded):
            dn.append("CONFLICTING EVIDENCE: night effect unresolved (see conditionModifiers)")
        meaning = [rp.meaning(r) for r in bounded if r["kind"] != "PHENOLOGY" and r["ruleId"] not in conflict_ids][:2]
        if in_spawn and spawn_rules:
            meaning.insert(0, rp.meaning(spawn_rules[0]))
        defining = [r for r in usable if r["ruleId"] in set(ids)]
        card_def = any(i.startswith("card:") for i in ids)
        conf = _min_conf([r["confidence"] for r in defining] + ([cconf] if card_def else [])) if ids else "UNKNOWN"
        reg = _min_conf([TRANSFER_CONF[r["transferability"]["southeastReservoir"]] for r in defining] + ([rconf] if card_def else [])) if ids else "UNKNOWN"
        if not states:
            states, prec = ["UNKNOWN"], ["UNKNOWN"]
        precision = "MONTH" if "MONTH" in prec else "SEASONAL" if "SEASONAL" in prec else "INFERRED" if "INFERRED" in prec else "UNKNOWN"
        months_out.append({"month": MONTHS[m - 1], "season": season, "movementStates": states, "shallowLikelihood": sh, "typicalDepthBehavior": ", ".join(depth_cls) or "UNKNOWN",
                           "favoredHabitat": habitats, "spawnState": ("ACTIVE_WINDOW" if in_spawn else "OUTSIDE_WINDOW") if spawn_months else "UNKNOWN",
                           "temperatureContext": "; ".join(temp_ctx) or "UNKNOWN", "hydrologyContext": "; ".join(hyd) or "UNKNOWN", "dayNightContext": "; ".join(dn) or "UNKNOWN",
                           "bowfisherMeaning": " ".join(meaning) or "UNKNOWN", "confidence": conf, "regionalConfidence": reg, "precision": precision, "claimIds": sorted(set(ids))})
    modifiers = []
    for x in rule_rows:
        if x["status"] == "DRAFT" or x["kind"] == "PHENOLOGY":
            continue
        modifiers.append({"id": x["ruleId"], "category": x["category"], "when": x["when"], "effect": x["expects"], "bowfisherMeaning": x["bowfisherMeaning"], "seasonality": x["seasonality"], "seasonReview": x["seasonReview"],
                          "firesNow": x["fires"], "conflict": x["ruleId"] in conflict_ids, "months": x["months"],
                          "confidence": x["confidence"], "regionalConfidence": x["regionalConfidence"], "claimIds": [x["ruleId"]]})
    unbounded = [x["id"] for x in modifiers if x["seasonality"] == "UNBOUNDED" and x["seasonReview"] != "YEAR_ROUND"]
    yearly = {"precisionNote": "A month is only as precise as its evidence: MONTH = a month-bounded rule or named months; SEASONAL = a season-level statement shown across its months; INFERRED = adjacent to a known window; UNKNOWN stays unknown.",
              "spawnWindowMonths": [MONTHS[m - 1] for m in spawn_months] or None, "spawnWindowBasis": spawn_basis, "months": months_out, "conditionModifiers": modifiers,
              "unboundedSeasonalModifiers": unbounded, "evidenceConflicts": sorted(conflict_ids) or None}
    # ---- seasonal guide + bowfisher guide
    def season_text(*keys):
        parts = [(FIELD_LABEL.get(k, k), _get(card, "seasonalMovement", k)) for k in keys if _known(_get(card, "seasonalMovement", k))]
        return parts
    def season_rules(season):
        ms = {m for m in range(1, 13) if SEASON_OF[m] == season}
        return [x for x in rule_rows if x["status"] != "DRAFT" and x["months"] and ms & set(x["months"]) and x["kind"] != "PHENOLOGY"]
    guide = {}
    for season, keys in (("winter", ("winter",)), ("spring", ("preSpawn", "spawn", "postSpawn")), ("summer", ("summer",)), ("fall", ("fall",))):
        parts = season_text(*keys)
        why = [f"{x['when']}: {x['bowfisherMeaning']}" for x in season_rules(season.upper())][:3]
        guide[season] = {"look": [{"phase": p, "text": short(t)} for p, t in parts] or None, "why": why or None, "precision": "SEASONAL" if parts else "UNKNOWN",
                         "claimIds": [card_claim(f"seasonalMovement.{k}", FIELD_LABEL.get(k, k)) for k in keys if _known(_get(card, "seasonalMovement", k))] + [x["ruleId"] for x in season_rules(season.upper())][:3]}
    night_rules = [x for x in rule_rows if x["category"] == "night" and x["status"] != "DRAFT"]
    night_text = _get(card, "dayNightBehavior", "night")
    best = None
    if spawn_months:
        wr = spawn_rules[0] if spawn_rules else None
        habs = [x["bowfisherMeaning"] for x in rule_rows if x["kind"] == "HABITAT" and x["status"] != "DRAFT" and "shallow" in x["bowfisherMeaning"].lower()][:1]
        t = f" when water is about {wr['phenology']['tempC']['min'] * 9 / 5 + 32:.0f}-{wr['phenology']['tempC']['max'] * 9 / 5 + 32:.0f} F" if wr else ""
        rise = [x for x in rule_rows if x["ruleId"] and x["category"] == "hydrology" and "rising" in x["when"] and x["status"] != "DRAFT"][:1]
        best = {"text": f"{rp.months_phrase(spawn_months)}{t}" + (f"; {habs[0]}" if habs else "") + (f"; stronger when {rise[0]['when'].split('; ')[-1]}" if rise else ""),
                "precision": "MONTH", "claimIds": [r["ruleId"] for r in spawn_rules] or [card_claim("spawn.timing", "Spawn timing")]}
    elif _known(_get(card, "spawn", "shallowMovement")):
        best = {"text": short(_get(card, "spawn", "shallowMovement")), "precision": "SEASONAL", "claimIds": [card_claim("spawn.shallowMovement", "Shallow movement")]}
    take = _get(card, "bowfisherTakeaway", None)
    bowfisher = {"takeaway": short(take, 420) if _known(take) else None, "seasons": {k: guide[k] for k in ("spring", "summer", "fall", "winter")},
                 "night": {"look": short(night_text) if _known(night_text) else None, "rules": [x["ruleId"] for x in night_rules], "coverage": cov["night"]["status"]},
                 "bestShallowWindow": best}
    # ---- gaps
    gaps, priorities = [], []
    open_by = {"seasonal": [], "spawn": secs["spawn"]["openQuestions"], "temperature": secs["temperature"]["openQuestions"], "depth": secs["depth"]["openQuestions"], "hydrology": secs["hydrology"]["openQuestions"],
               "vegetation": secs["habitat"]["openQuestions"], "night": secs["dayNight"]["openQuestions"], "clarity": secs["clarityLight"]["openQuestions"], "current": secs["currentWaterbody"]["openQuestions"], "regional": []}
    open_by["seasonal"] = [FIELD_LABEL.get(k, k) for k in ("winter", "preSpawn", "spawn", "postSpawn", "summer", "fall") if not _known(_get(card, "seasonalMovement", k))] if card else [FIELD_LABEL.get(k, k) for k in ("winter", "preSpawn", "spawn", "postSpawn", "summer", "fall")]
    for c in CATEGORIES:
        pr, sc = research_priority(species_id, role, c, cov[c])
        row = {"category": c, "label": CATEGORY_LABEL[c], "coverage": cov[c]["status"], "completeness": cov[c]["completeness"], "confidence": cconf if c != "regional" else rconf,
               "reviewed": any(x["review"] == "ACCEPTED" for x in rule_rows if x["category"] == c), "validated": False, "bowfisherImportance": IMPORTANCE[c], "researchPriority": pr,
               "priorityScore": sc, "changesRecommendation": CHANGES_RECOMMENDATION[c], "evidence": cov[c]["evidence"], "gapExplanation": cov[c]["note"], "openQuestions": open_by[c],
               "ifWeLearnThis": IF_LEARNED[c], "researchStatus": "RESEARCH_NOT_AUTHORIZED"}
        if cov[c]["status"] != "STRONG":
            gaps.append(row)
        priorities.append(row)
    matrix = {r["category"]: {k: r[k] for k in ("coverage", "completeness", "confidence", "reviewed", "validated", "bowfisherImportance", "researchPriority", "gapExplanation")} for r in priorities}
    top = sorted([g for g in gaps if g["researchPriority"] in ("HIGH", "MEDIUM")], key=lambda g: (-g["priorityScore"], g["category"]))[:5]
    pg = (card or {}).get("biggestPracticalGap")
    # ---- evidence / provenance
    srcs = [{"id": s["id"], "title": short(re.sub(r"packets?/\S+", "internal compilation", str(s.get("title"))), 140), "publisher": short(s.get("publisher"), 80), "url": None if s.get("type") == "PACKET" else s.get("url"), "type": s.get("type"), "verification": s.get("verification") or "NOT_CHECKED",
             "supports": s.get("supports") or []} for s in (card or {}).get("sources") or [] if s.get("type") != "ANECDOTAL"]
    anec = sum(1 for s in (card or {}).get("sources") or [] if s.get("type") == "ANECDOTAL")
    by_type: dict = {}
    for s in srcs:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1
    rank = {"PEER_REVIEWED": 4, "FEDERAL": 4, "AGENCY": 4, "EXTENSION": 3, "REFERENCE": 2, "PACKET": 2}
    insp = [s for s in srcs if s["verification"] in ("READ-FULL", "READ-ABSTRACT")]
    best_src = sorted(insp, key=lambda s: (-rank.get(s["type"], 1), 0 if s["verification"] == "READ-FULL" else 1, s["id"]))[:1]
    evidence = {"sourceCount": len(srcs), "byType": by_type, "inspected": len(insp), "unreachableOrUnsupported": sum(1 for s in srcs if s["verification"] in ("UNREACHABLE", "NOT_SUPPORTED")), "anecdotalIgnored": anec,
                "strongestSource": ({k: best_src[0][k] for k in ("id", "title", "publisher", "type", "verification")} if best_src else None),
                "claimMaturity": {"RECONCILED": len([r for r in usable if r["status"] == "RECONCILED"]), "APPROVED": len([r for r in usable if r["status"] == "APPROVED"]), "DRAFT": len(drafts)},
                "sources": srcs, "claims": {k: claims[k] for k in sorted(claims)}}
    n_rev = {k: sum(1 for x in rule_rows if x["review"] == k and x["status"] != "DRAFT") for k in REVIEW}
    review = {"status": "ACCEPTED" if usable and n_rev["ACCEPTED"] == len(usable) else "UNREVIEWED" if not (n_rev["ACCEPTED"] + n_rev["REJECTED"] + n_rev["NEEDS_MORE_EVIDENCE"]) else "IN_PROGRESS", "rules": n_rev, "usableRules": len(usable),
              "awaitingReview": [x["ruleId"] for x in rule_rows if x["status"] != "DRAFT" and x["review"] == "UNREVIEWED"]}
    obs = validation.get("observations", {}).get(species_id, 0)
    trips = validation.get("trips", {}).get(species_id, 0)
    fstat = "VALIDATED" if validation.get("validated", {}).get(species_id) else "OBSERVATIONS_IN_PROGRESS" if obs else "NOT_VALIDATED"
    val = {"status": fstat, "observations": obs, "trips": trips, "lastObservation": validation.get("lastObservation", {}).get(species_id), "predictionsLogged": pcount, "fieldCandidate": species_id in validation.get("fieldCandidates", ()), "note": "Field validation never alters the knowledge shown above."}
    k = (profile or {}).get("knowledge") or {}
    mv = (profile or {}).get("movement") or {}
    status = "PROPOSED" if (not canonical and card) else "NOT_ASSESSED" if not assessed else ("PROFILED" if card else "THIN")
    out = {"contract": CONTRACT,
           "generatedFrom": {**(generated_from or {}), "cardVersion": mv.get("cardVersion")},
           "identity": {"speciesId": species_id, "sectorLabel": (profile or {}).get("displayName") or species_id.replace("_", " ").title(), "scientificName": (profile or {}).get("scientificName"), "role": role,
                        "targetTier": {"TARGET": "TARGET", "SECONDARY": "SECONDARY"}.get(role, "KNOWLEDGE_ONLY"), "habitatClass": hab["primaryGroup"], "habitatFlag": hab["habitatFlag"], "canonical": canonical,
                        **({"doNotResearch": ts.DO_NOT_RESEARCH[species_id]} if species_id in ts.DO_NOT_RESEARCH else {})},
           "summary": {"knowledgeStatus": status, "bowfisherKnowledge": mv.get("bowfisherKnowledge"), "speciesV2Score": k.get("overallExact"), "generalConfidence": cconf, "regionalConfidence": rconf,
                       "reviewStatus": review["status"], "fieldValidationStatus": fstat, "ruleCount": {"usable": len(usable), "draft": len(drafts)}, "lastUpdated": (generated_from or {}).get("researchVersion"),
                       "profileFreshness": "CURRENT_WITH_BUNDLE", "passLevel": mv.get("passLevel"), "strongest": [c for c in CATEGORIES if cov[c]["status"] == "STRONG"], "weakest": [c for c in CATEGORIES if cov[c]["status"] in ("WEAK", "UNKNOWN")]},
           "yearlyMovement": yearly,
           "seasonalGuide": guide, "spawn": secs["spawn"], "temperature": secs["temperature"], "depth": secs["depth"], "hydrology": secs["hydrology"], "habitat": secs["habitat"], "dayNight": secs["dayNight"],
           "clarityLight": secs["clarityLight"], "currentWaterbody": secs["currentWaterbody"], "bowfisherGuide": bowfisher,
           "knowledgeCoverage": {c: {"label": CATEGORY_LABEL[c], "status": cov[c]["status"], "completeness": cov[c]["completeness"], "evidence": cov[c]["evidence"], "note": cov[c]["note"]} for c in CATEGORIES},
           "knowledgeGapMatrix": matrix, "knowledgeGaps": gaps, "researchPriorities": {"top": [{"category": g["category"], "label": g["label"], "priority": g["researchPriority"], "ifWeLearnThis": g["ifWeLearnThis"]} for g in top],
                                                                                          "speciesNote": short(pg, 300) if _known(pg) else None, "policy": "RESEARCH_NOT_AUTHORIZED: a gap is exposed, never researched automatically"},
           "rulesSummary": rule_rows, "evidenceSummary": evidence, "reviewSummary": review, "validationSummary": val}
    return out


def validate_profile(p: dict) -> list[str]:
    """Contract problems (empty = valid): vocabulary, 12 unique months, UNKNOWN not scored 0, every claim id resolvable, nothing private, compact."""
    import json
    e = []
    if p.get("contract") != CONTRACT:
        e.append("contract")
    for k in ("generatedFrom", "identity", "summary", "yearlyMovement", "seasonalGuide", "bowfisherGuide", "knowledgeCoverage", "knowledgeGapMatrix", "knowledgeGaps", "researchPriorities", "rulesSummary", "evidenceSummary", "reviewSummary", "validationSummary") + SECTIONS:
        if k not in p:
            e.append(f"missing {k}")
    if e:
        return e
    ms = p["yearlyMovement"]["months"]
    if [m["month"] for m in ms] != list(MONTHS):
        e.append("yearlyMovement must hold the 12 months JAN..DEC in order")
    claims = p["evidenceSummary"]["claims"]
    for m in ms:
        if m["precision"] not in PRECISION or m["shallowLikelihood"] not in SHALLOW or m["spawnState"] not in SPAWN_STATE or any(s not in MOVEMENT_STATES for s in m["movementStates"]):
            e.append(f"{m['month']}: vocabulary")
        if m["movementStates"] == ["UNKNOWN"] and (m["precision"] != "UNKNOWN" or m["confidence"] != "UNKNOWN"):
            e.append(f"{m['month']}: an UNKNOWN month carries precision/confidence")
        for c in m["claimIds"]:
            if c not in claims:
                e.append(f"{m['month']}: claim {c} has no provenance")
    for c, v in p["knowledgeCoverage"].items():
        if v["status"] not in COVERAGE:
            e.append(f"coverage {c}")
        if v["status"] == "UNKNOWN" and v["completeness"] is not None:
            e.append(f"coverage {c}: UNKNOWN must not carry a number")
    for g in p["knowledgeGaps"]:
        if g["researchPriority"] not in PRIORITY or g["researchStatus"] != "RESEARCH_NOT_AUTHORIZED":
            e.append(f"gap {g['category']}")
    for r in p["rulesSummary"]:
        if r["review"] not in REVIEW or r["field"] not in FIELD:
            e.append(f"rule {r['ruleId']}")
    if p["validationSummary"]["status"] not in FIELD or p["reviewSummary"]["status"] not in ("UNREVIEWED", "ACCEPTED", "IN_PROGRESS"):
        e.append("review/validation vocabulary")
    blob = json.dumps(p)
    for bad in ("gs:" + "//", "sector-biology" + "-private", "Sector_" + "Research_Data", "/Us" + "ers/", "packets" + "/", "biology" + "/v1"):
        if bad in blob:
            e.append(f"private data leaked: {bad}")
    if len(blob) > 90_000:
        e.append("profile too large for a compact payload")
    if any(k in blob for k in ("lakeId", "speciesPresence", "presenceState")):
        e.append("per-lake presence must not appear in a species profile")
    return e


def outlook_contradictions(outlook: dict, profile: dict, month: int) -> list[str]:
    """Current outlook vs the yearly profile built from the SAME rules: empty = consistent. A favourable shallow call must be allowed by the profile for that month,
    and every rule behind it must be one the profile says can fire."""
    e = []
    m = profile["yearlyMovement"]["months"][month - 1]
    fires = {r["ruleId"]: r["fires"] for r in profile["rulesSummary"]}
    if outlook.get("state") in ("FAVORABLE_SHALLOW",) and m["shallowLikelihood"] == "LOW":
        e.append(f"outlook FAVORABLE_SHALLOW but the {m['month']} profile says shallow likelihood LOW")
    for r in (outlook.get("trace") or {}).get("matchedKnowledge", []):
        if r["ruleId"] in fires and not fires[r["ruleId"]]:
            e.append(f"{r['ruleId']} contributed but the profile says it cannot fire")
        rr = next((x for x in profile["rulesSummary"] if x["ruleId"] == r["ruleId"]), None)
        if rr and rr["months"] and month not in rr["months"]:
            e.append(f"{r['ruleId']} contributed outside its months")
    if "inside the spawning window" in " ".join(outlook.get("why") or []) and m["spawnState"] != "ACTIVE_WINDOW":
        e.append(f"outlook cites the spawning window but the {m['month']} profile is {m['spawnState']}")
    return e
