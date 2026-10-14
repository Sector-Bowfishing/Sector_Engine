"""Movement-card adoption: deterministic tooling (no publication, no network, no writes outside the paths the caller passes).

  * `temp_states` / `parse_temp_range`: Fahrenheit/Celsius condition ranges -> waterTempBand states (never a single decimal threshold)
  * `build_rule`: a reviewed disposition spec + the card's sources -> a `biological-rule-v1` rule (validated by rules.validate_rule)
  * `domain_scores`: movement card + source verification -> species-v2 knowledge domains (whole points; provenance kept; general vs regional separate)
  * `validate_dispositions`: every candidate has exactly one disposition; ACCEPT needs a spec; malformed cards are refused

Species-v2 practical standard applied here (Michael's direction, 2026-10-14): one credible, inspected source supports a basic behaviour up to 6;
two independent credible sources up to 8; anecdotal and unverified (snippet-only) sources count for nothing; regional confidence never lowers a general behaviour.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as ft      # noqa: E402
import movement_cards as mc      # noqa: E402
import rules as rl      # noqa: E402

DISPOSITIONS = ("ACCEPT_AS_DRAFT_RULE", "MERGE_WITH_EXISTING_RULE", "REJECT_WEAK_EVIDENCE", "REJECT_NO_PRODUCT_VALUE", "REVIEW_REQUIRED")
BANDS = [("LT_10C", -99.0, 10.0), ("C10_15", 10.0, 15.0), ("C15_18", 15.0, 18.0), ("C18_21", 18.0, 21.0), ("C21_26", 21.0, 26.0), ("C26_30", 26.0, 30.0), ("GE_30C", 30.0, 99.0)]
SEASON_MONTHS = {"winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11], "spawn": None}
DOMAIN_TAGS = {"seasonalLocationReproduction": ("seasonal", "spawn", "spawn temperature", "summer"), "temperatureOxygen": ("temperature",),
               "habitatDepthCover": ("habitat", "depth", "vegetation", "vegetationHabitat", "backwater"), "hydrologyRainInflowLevel": ("hydrology", "current"),
               "dayNightMovement": ("night", "nightLight", "dayNight"), "clarityLightWind": ("clarity", "nightLight"), "aggregationMobilityLifeStage": ("aggregation", "current", "seasonal"),
               "foodFeedingLocation": ("food", "feeding")}
CARD_COMPONENT = {"seasonalLocationReproduction": ("seasonal", "spawn"), "temperatureOxygen": ("temperature",), "habitatDepthCover": ("depth", "vegetationHabitat"),
                  "hydrologyRainInflowLevel": ("hydrology",), "dayNightMovement": ("nightLight",), "clarityLightWind": ("nightLight",), "aggregationMobilityLifeStage": ("current",)}
SUBFIELDS = {"dayNightMovement": [("dayNightBehavior", k) for k in ("day", "dusk", "night", "dawn")], "clarityLightWind": [("clarityLightResponse", k) for k in ("brightSun", "lowLight", "turbid", "clear")]}
CREDIBLE = ("AGENCY", "FEDERAL", "EXTENSION", "REFERENCE", "PEER_REVIEWED", "PACKET")
READ_OK = ("READ-FULL", "READ-ABSTRACT", "PROFILE-REVIEWED")


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def temp_states(min_c: float | None, max_c: float | None) -> list[str]:
    """waterTempBand states a Celsius range touches. A band is included when the range covers at least 1.5 C of it (or the whole band): ranges stay ranges."""
    lo = -99.0 if min_c is None else float(min_c)
    hi = 99.0 if max_c is None else float(max_c)
    if lo > hi:
        raise ValueError("min > max")
    out = []
    for name, a, b in BANDS:
        ov = min(hi, b) - max(lo, a)
        if ov >= min(1.5, (b - a) if b - a < 90 else 1.5) and ov > 0:
            out.append(name)
    return out


_RANGE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:-|–|to)\s*(\d{1,3}(?:\.\d+)?)\s*(?:°\s*)?(F|C)\b", re.I)
_BELOW = re.compile(r"(?:below|under|<|at or below)\s*(?:about|~)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:°\s*)?(F|C)\b", re.I)
_ABOVE = re.compile(r"(?:above|over|>=|>|at least)\s*(?:about|~)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:°\s*)?(F|C)\b", re.I)


def parse_temp_range(text: str) -> tuple[float | None, float | None] | None:
    """'water temp roughly 60-72 F' -> (15.6, 22.2) C; 'below about 50 F' -> (None, 10.0); unparsable -> None. Rounded to 0.1 C, a range never a point."""
    t = str(text)
    m = _RANGE.search(t)
    if m:
        a, b, u = float(m.group(1)), float(m.group(2)), m.group(3).upper()
        if u == "F":
            a, b = f_to_c(a), f_to_c(b)
        return (round(min(a, b), 1), round(max(a, b), 1))
    m = _BELOW.search(t)
    if m:
        v = float(m.group(1))
        return (None, round(f_to_c(v) if m.group(2).upper() == "F" else v, 1))
    m = _ABOVE.search(t)
    if m:
        v = float(m.group(1))
        return (round(f_to_c(v) if m.group(2).upper() == "F" else v, 1), None)
    return None


def stream_key(src: dict) -> str:
    """Independence key: one cohort / one publisher domain is one stream however many pages report it (conservative)."""
    url = str(src.get("url") or "").lower()
    if src.get("type") == "PEER_REVIEWED":
        return "paper:" + re.sub(r"[^a-z0-9]+", "-", str(src.get("title", "")).lower())[:48]
    m = re.match(r"https?://(?:www\.)?([^/]+)", url)
    return "site:" + (m.group(1) if m else re.sub(r"[^a-z0-9]+", "-", str(src.get("title", "")).lower())[:48])


def build_rule(spec: dict, cand: dict, card: dict, verification: dict, rule_id: str, rules_version_note: str = "movement-sweep-2026-10-14") -> dict:
    """spec = reviewed mapping for ONE accepted candidate:
       R: {"kind":"R","f":featureId,"st":[states],"resp":"FAVORABLE|WORKABLE|LIMITING|BLOCKING","months":[..]|None,"beh":str,"stmt":str}
       H: {"kind":"H","cls":habitatClass,"dir":"FAVOR|AVOID","depth":None|class,"req":[(featureId,[states])],"months":..,"stmt":str}
       P: {"kind":"P","c":(minC,maxC),"months":[..],"regions":[..],"stmt":str}
    `verification` = {"<speciesId>:<sourceId>": "READ-FULL|READ-ABSTRACT|SNIPPET-ONLY|UNREACHABLE|NOT_SUPPORTED"}; anything not read does not count."""
    src = {s["id"]: s for s in card["sources"]}
    ev = []
    for sid in cand["sourceIds"]:
        s = src.get(sid)
        if s is None:
            raise ValueError(f"{cand['id']}: unknown source {sid}")
        v = verification.get(f"{card['speciesId']}:{sid}")
        rs = v if v in ("READ-FULL", "READ-ABSTRACT") else ("SNIPPET-ONLY" if v in ("SNIPPET-ONLY", "UNREACHABLE", "NOT_SUPPORTED") else "PROFILE-CARRIED")
        counts = rs in rl.COUNTING_READ and s["type"] in CREDIBLE and v != "NOT_SUPPORTED"
        ev.append({"evidenceId": f"{card['speciesId']}:{sid}", "packet": "movement-sweep", "sourceNo": sid, "streamId": stream_key(s), "readStatus": rs,
                   "directness": "INFERRED" if "inferred" in cand["then"].lower() else "DIRECT", "counts": counts, "studyType": s["type"].lower(),
                   "region": "", "sample": "", **({"note": f"verification: {v}"} if v else {})})
    streams = {e["streamId"] for e in ev if e["counts"]}
    conf = cand["confidence"] if cand["confidence"] in rl.CONFIDENCE else "LOW"
    cap = "HIGH" if len(streams) >= 3 else ("MEDIUM" if len(streams) >= 2 else "LOW")
    conf = conf if rl.CONFIDENCE.index(conf) <= rl.CONFIDENCE.index(cap) else cap
    tr = "PARTIAL" if cand.get("regionalConfidence") in ("HIGH", "MEDIUM") else "UNTESTED"      # TRANSFERS needs a counting Southeast stream; never assumed here
    k = spec["kind"]
    r = {"schemaVersion": 1, "ruleId": rule_id, "ruleVersion": 1, "speciesId": card["speciesId"], "lifeStage": "ADULT", "status": "RECONCILED" if streams else "DRAFT",
         "confidence": conf, "conflicts": spec.get("conflicts", []), "transferability": {"southeastReservoir": tr}, "evidence": ev, "statement": spec["stmt"],
         "applicability": {"months": spec.get("months"), "regions": spec.get("regions", ["any"]), "waterbodyTypes": spec.get("wb", ["any"])},
         "provenance": {"origin": rules_version_note, "candidateId": cand["id"], "generalConfidence": cand["confidence"], "regionalConfidence": cand.get("regionalConfidence", "UNKNOWN")}}
    if r["applicability"]["months"] is None:
        del r["applicability"]["months"]
    if k == "R":
        r |= {"kind": "RESPONSE", "feature": {"featureId": spec["f"], "states": spec["st"]}, "response": spec["resp"], "behavior": spec["beh"]}
    elif k == "H":
        r |= {"kind": "HABITAT", "habitat": {"habitatClass": spec["cls"], "direction": spec["dir"], **({"depthClass": spec["depth"]} if spec.get("depth") else {})}}
        if spec.get("req"):
            r["requires"] = [{"featureId": f, "states": list(s)} for f, s in spec["req"]]
    elif k == "P":
        lo, hi = spec["c"]
        r |= {"kind": "PHENOLOGY", "phenology": {"event": "spawn", "tempC": {"min": float(lo), "max": float(hi)}}}
    else:
        raise ValueError(f"{cand['id']}: unknown spec kind {k!r}")
    errs = rl.validate_rule(r)
    if errs:
        raise ValueError(f"{cand['id']} -> {rule_id}: " + "; ".join(errs))
    return r


def validate_dispositions(candidates: list[dict], disp: dict) -> list[str]:
    e = []
    ids = [c["id"] for c in candidates]
    for i in ids:
        d = disp.get(i)
        if d is None:
            e.append(f"{i}: no disposition")
            continue
        if d["disposition"] not in DISPOSITIONS:
            e.append(f"{i}: disposition {d['disposition']!r}")
        if not d.get("why"):
            e.append(f"{i}: a disposition needs a reason")
        if d["disposition"] == "ACCEPT_AS_DRAFT_RULE" and not d.get("spec"):
            e.append(f"{i}: ACCEPT needs a spec")
        if d["disposition"] == "MERGE_WITH_EXISTING_RULE" and not d.get("into"):
            e.append(f"{i}: MERGE needs the existing rule id")
    e += [f"{i}: disposition for an unknown candidate" for i in disp if i not in ids]
    return e


def domain_scores(card: dict, verification: dict, existing: dict | None = None) -> dict:
    """Species-v2 domains from a movement card. Whole points 0-10; score 0 is the bundle's UNKNOWN. Never lowers an existing evidence-based score.
    score = min(card component score, source cap); source cap = 0 with no inspected credible source supporting the domain, 6 with one, 8 with two or more
    (distinct streams). A domain the card does not research (food/feeding) keeps its existing score."""
    sp = card["speciesId"]
    ks = mc.knowledge_score(card)["components"]
    out = {}
    for dom, comps in CARD_COMPONENT.items():
        raw = sum(ks[c]["score"] for c in comps) / len(comps)
        if dom in SUBFIELDS:           # day/night and clarity share one card component: cap each by its own sub-fields
            n = sum(_known(((card.get("card") or {}).get(a) or {}).get(b)) for a, b in SUBFIELDS[dom])
            raw = min(raw, 10 * n / len(SUBFIELDS[dom]) + 1) if n else 0.0
        tags = DOMAIN_TAGS[dom]
        good, anecdotal, unread = set(), 0, 0
        for s in card["sources"]:
            if not set(s.get("supports") or []) & set(tags):
                continue
            if s["type"] == "ANECDOTAL":
                anecdotal += 1
                continue
            v = verification.get(f"{sp}:{s['id']}")
            if (s["type"] == "PACKET" and v != "NOT_SUPPORTED") or v in ("READ-FULL", "READ-ABSTRACT"):      # packet sources were inspected by the original campaign
                good.add(stream_key(s))
            else:
                unread += 1
        cap = 0 if not good else (6 if len(good) == 1 else 8)
        score = int(min(round(raw), cap))
        old = (existing or {}).get(dom, {}).get("score", 0)
        out[dom] = {"score": max(score, old), "fromCard": score, "existing": old, "cardComponent": round(raw, 1), "independentInspectedStreams": len(good), "unverifiedSources": unread,
                    "anecdotalIgnored": anecdotal, "keptExisting": old > score}
    food = (existing or {}).get("foodFeedingLocation", {}).get("score", 0)
    out["foodFeedingLocation"] = {"score": food, "fromCard": None, "existing": food, "cardComponent": None, "independentInspectedStreams": 0, "unverifiedSources": 0, "anecdotalIgnored": 0, "keptExisting": True}
    return out


def dedupe_key(rule: dict) -> tuple:
    """Two rules say the same thing when species, kind, what they key on and what they conclude match (months/regions are compared separately)."""
    k = rule["kind"]
    if k == "RESPONSE":
        return (rule["speciesId"], k, rule["feature"]["featureId"], tuple(sorted(rule["feature"]["states"])), rule["response"])
    if k == "HABITAT":
        h = rule["habitat"]
        return (rule["speciesId"], k, h["habitatClass"], h["direction"], tuple(sorted((q["featureId"], tuple(sorted(q["states"]))) for q in rule.get("requires") or [])))
    return (rule["speciesId"], k, "spawn")


def find_duplicate(rule: dict, existing: list[dict]) -> dict | None:
    key = dedupe_key(rule)
    for e in existing:
        if e.get("status") in ("RETIRED",):
            continue
        if dedupe_key(e) == key:
            return e
    return None


DOMAIN_ORDER = ["seasonalLocationReproduction", "habitatDepthCover", "temperatureOxygen", "hydrologyRainInflowLevel", "foodFeedingLocation", "dayNightMovement", "clarityLightWind",
                "aggregationMobilityLifeStage"]
DOMAIN_WEIGHT = {"seasonalLocationReproduction": 20, "habitatDepthCover": 20, "temperatureOxygen": 15, "hydrologyRainInflowLevel": 15, "foodFeedingLocation": 10, "dayNightMovement": 10,
                 "clarityLightWind": 5, "aggregationMobilityLifeStage": 5}
CARD_TEXT = {"seasonalLocationReproduction": [("seasonalMovement", None), ("spawn", None)], "temperatureOxygen": [("temperatureResponse", None)],
             "habitatDepthCover": [("depthBehavior", None), ("vegetationAssociation", None), ("coverAndSubstrate", None)], "hydrologyRainInflowLevel": [("hydrologyResponse", None)],
             "dayNightMovement": [("dayNightBehavior", None)], "clarityLightWind": [("clarityLightResponse", None)], "aggregationMobilityLifeStage": [("currentPreference", None)]}


def _round_half(x: float) -> float:
    return float(int(x * 2 + 0.5)) / 2


def _texts(card: dict, dom: str) -> list[str]:
    out = []
    for key, _ in CARD_TEXT.get(dom, []):
        v = (card.get("card") or {}).get(key)
        if isinstance(v, dict):
            for k, x in v.items():
                if isinstance(x, (str, int, float)) and _known(x):
                    out.append(f"{key}.{k}: {str(x)[:180]}")
                elif isinstance(x, dict) and _known(x):
                    out.append(f"{key}.{k}: " + ", ".join(f"{a}={b}" for a, b in x.items() if b not in (None, "")))
        elif isinstance(v, str) and _known(v):
            out.append(f"{key}: {v[:180]}")
    return out[:6]


def _known(v) -> bool:
    return mc._known(v)


def encode_profile(profile: dict, card: dict, verification: dict, today: str) -> tuple[dict, dict]:
    """Return (updated species-v2 profile, per-domain diff). Pure: the input profile is not mutated. Domain scores are whole points; score 0 is UNKNOWN."""
    import copy
    p = copy.deepcopy(profile)
    k = p["knowledge"]
    old = {d: dict(v) for d, v in k["domains"].items()}
    new = domain_scores(card, verification, old)
    diff, total = {}, 0
    for dom in DOMAIN_ORDER:
        d = k["domains"][dom]
        n = new[dom]
        s = int(n["score"])
        if n["fromCard"] is not None and s > old[dom]["score"]:
            d["basis"] = list(d.get("basis") or []) + [f"movement-sweep 2026-10-14: {t}" for t in _texts(card, dom)]
            d["limits"] = list(d.get("limits") or []) + [f"movement-sweep: {n['independentInspectedStreams']} inspected independent stream(s); {n['unverifiedSources']} unverified; anecdotal ignored {n['anecdotalIgnored']}; general confidence {card['card']['generalConfidence']}, regional {card['card']['regionalConfidence']}"]
            d["calibrationNote"] = "practical standard: one inspected credible source <=6, two independent <=8; regional confidence is separate and does not lower general behaviour"
        d["score"], d["status"] = s, "SCORED" if s else "UNKNOWN"
        d["potentialGainPerPoint"] = DOMAIN_WEIGHT[dom] / 100
        total += s * DOMAIN_WEIGHT[dom]
        diff[dom] = {"before": old[dom]["score"], "after": s, "why": ("kept existing (higher or card does not research this domain)" if n["keptExisting"] else f"card {n['cardComponent']}, {n['independentInspectedStreams']} inspected stream(s)")}
    exact = total / 100
    k["overallExact"], k["overallRounded"] = round(exact, 2), _round_half(exact)
    scored = {d: v["score"] for d, v in k["domains"].items() if v["score"]}
    k["strongest"] = [d for d, v in scored.items() if v == max(scored.values())] if scored else []
    k["weakest"] = [d for d, v in scored.items() if v == min(scored.values())] if scored else []
    k["unknownDomains"] = [d for d, v in k["domains"].items() if not v["score"]]
    if p.get("researchMaturity") == "NOT_STARTED" and exact > 0:
        p["researchMaturity"] = "RESEARCH"
    c = card["card"]
    p["movement"] = {"passLevel": card["passLevel"], "generalConfidence": c["generalConfidence"], "regionalConfidence": c["regionalConfidence"], "bowfisherTakeaway": c["bowfisherTakeaway"],
                     "bowfisherKnowledge": card.get("bk", {}).get("score"), "sourcesInspected": sum(1 for s in card["sources"] if verification.get(f"{card['speciesId']}:{s['id']}") in ("READ-FULL", "READ-ABSTRACT")),
                     "sourcesTotal": len(card["sources"]), "cardVersion": "movement-sweep-2026-10-14"}
    p.setdefault("history", []).append({"date": today, "rubric": "species-v2", "label": "movement-sweep adoption", "overallExact": k["overallExact"], "overallRounded": k["overallRounded"],
                                         "reason": "practical movement knowledge from the 2026-10-14 sweep encoded into the existing domains; no rubric change"})
    return p, diff
