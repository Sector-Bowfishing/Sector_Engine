"""Freshwater movement sweep: validate agent output, normalise, and compute the READ-ONLY BOWFISHER KNOWLEDGE SCORE (0-10).

Not field validation, not regional validation, not human review, not production readiness: it answers "how much useful movement knowledge do we have for this fish?".
Weights: seasonal 15, spawn 20, temperature 15, depth 15, hydrology 10, vegetation/habitat 10, night+light 10, current 5.
Each component is the agent's self-score (anchored 0-10 on completeness and usefulness, never citation count) CAPPED by what the card actually contains:
  cap = min(10, 10 x filled_fraction + 1)   where filled = card sub-fields that are non-empty and not UNKNOWN
and the whole score is capped at 3.0 when no non-ANECDOTAL source supports the card. Pure functions; the official Biological rubric is untouched.
"""
from __future__ import annotations

import re

WEIGHTS = {"seasonal": 15, "spawn": 20, "temperature": 15, "depth": 15, "hydrology": 10, "vegetationHabitat": 10, "nightLight": 10, "current": 5}
SOURCE_TYPES = ("AGENCY", "FEDERAL", "EXTENSION", "REFERENCE", "PEER_REVIEWED", "PACKET", "ANECDOTAL")
CONF = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
PASS = ("DEEP", "STANDARD", "LIGHT")
SEASONS = ("winter", "preSpawn", "spawn", "postSpawn", "summer", "fall")
FIELDS = {
    "seasonal": [("seasonalMovement", s) for s in SEASONS],
    "spawn": [("spawn", "timing"), ("spawn", "temperatureF"), ("spawn", "habitat"), ("spawn", "shallowMovement")],
    "temperature": [("temperatureResponse", k) for k in ("triggers", "preSpawn", "spawn", "summer", "coldSlowdown")],
    "depth": [("depthBehavior", k) for k in ("shallowWhen", "deepWhen", "usefulDepthHabitat")],
    "hydrology": [("hydrologyResponse", k) for k in ("rising", "falling", "floodedShoreline", "current", "discharge", "backwaterConnectivity")],
    "vegetationHabitat": [("vegetationAssociation", None), ("coverAndSubstrate", None)],
    "nightLight": [("dayNightBehavior", k) for k in ("day", "dusk", "night", "dawn")] + [("clarityLightResponse", k) for k in ("brightSun", "lowLight", "turbid", "clear")],
    "current": [("currentPreference", k) for k in ("mainRiver", "reservoir", "creekTributary", "backwaterSlough", "shorelineFlat", "channelEdge")],
}
DIRECTIONS = ("MORE_LIKELY_SHALLOW", "LESS_LIKELY_SHALLOW", "MOVES_TO_HABITAT", "LEAVES_HABITAT", "ACTIVITY_UP", "ACTIVITY_DOWN", "OTHER")
KINDS = ("RESPONSE", "HABITAT", "PHENOLOGY")


def _known(v) -> bool:
    if v is None:
        return False
    if isinstance(v, dict):
        if "min" in v or "max" in v or "peak" in v:
            return any(isinstance(v.get(k), (int, float)) for k in ("min", "max", "peak")) or bool(str(v.get("note", "")).strip() and not str(v.get("note", "")).strip().upper().startswith("UNKNOWN"))
        return any(_known(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return any(_known(x) for x in v)
    s = str(v).strip()
    return bool(s) and not s.upper().startswith("UNKNOWN") and s.upper() not in ("N/A", "NONE", "-")


def filled_fraction(card: dict, component: str) -> float:
    fs = FIELDS[component]
    n = 0
    for a, b in fs:
        v = (card or {}).get(a)
        v = v.get(b) if b else v
        n += _known(v)
    return n / len(fs)


def component_scores(card: dict, agent_scores: dict) -> dict:
    out = {}
    for c in WEIGHTS:
        raw = (agent_scores.get(c) or {}).get("score")
        raw = float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else 0.0
        raw = max(0.0, min(10.0, raw))
        fr = filled_fraction(card, c)
        cap = min(10.0, 10 * fr + 1) if fr > 0 else 0.0
        out[c] = {"agent": raw, "filled": round(fr, 2), "cap": round(cap, 1), "score": round(min(raw, cap), 1)}
    return out


def knowledge_score(sp: dict) -> dict:
    cs = component_scores(sp.get("card") or {}, sp.get("componentScores") or {})
    total = sum(WEIGHTS[c] * cs[c]["score"] for c in WEIGHTS) / sum(WEIGHTS.values())
    credible = [s for s in sp.get("sources") or [] if s.get("type") in SOURCE_TYPES and s.get("type") != "ANECDOTAL"]
    capped = False
    if not credible and total > 3.0:
        total, capped = 3.0, True
    return {"score": round(total, 1), "components": cs, "sourceCapped": capped, "credibleSources": len(credible)}


def validate_species(sp: dict) -> list[str]:
    e = []
    for k in ("speciesId", "sectorLabel", "passLevel", "card", "componentScores", "ruleCandidates", "sources"):
        if k not in sp:
            e.append(f"missing {k}")
    if e:
        return e
    if sp["passLevel"] not in PASS:
        e.append("passLevel")
    card = sp["card"]
    for k in ("bowfisherTakeaway", "generalConfidence", "regionalConfidence"):
        if k not in card:
            e.append(f"card.{k}")
    if card.get("generalConfidence") not in CONF[:3] or card.get("regionalConfidence") not in CONF:
        e.append("confidence vocabulary")
    if len(str(card.get("bowfisherTakeaway", "")).strip()) < 40:           # the sentence frame may vary for protected / non-target fish, but it must say something
        e.append("takeaway sentence")
    ids = {s.get("id") for s in sp["sources"]}
    for s in sp["sources"]:
        if s.get("type") not in SOURCE_TYPES:
            e.append(f"source type {s.get('id')}")
    for r in sp["ruleCandidates"]:
        if r.get("direction") not in DIRECTIONS or r.get("kind") not in KINDS or r.get("confidence") not in CONF[:3] or not r.get("when") or not r.get("then"):
            e.append(f"rule candidate {r.get('id')}")
        for sid in r.get("sourceIds") or []:
            if sid not in ids:
                e.append(f"rule candidate {r.get('id')} cites unknown source {sid}")
    return e


def dedupe_sources(all_species: list[dict]) -> dict:
    """Canonical source list keyed by normalised URL (falls back to title); returns {key: {..., species:[...]}}."""
    out: dict = {}
    for sp in all_species:
        for s in sp.get("sources") or []:
            key = re.sub(r"^https?://(www\.)?", "", str(s.get("url") or "").lower()).rstrip("/") or str(s.get("title", "")).lower()
            d = out.setdefault(key, {"title": s.get("title"), "publisher": s.get("publisher"), "url": s.get("url"), "type": s.get("type"), "species": []})
            if sp["speciesId"] not in d["species"]:
                d["species"].append(sp["speciesId"])
    return out


def mismatch(rows: list[dict]) -> dict:
    """rows: [{bk, v2, important}] -> the rubric-mismatch counts the campaign asks for."""
    return {"bk_ge_6_but_v2_lt_3": sum(1 for r in rows if r["bk"] >= 6 and r["v2"] is not None and r["v2"] < 3),
            "bk_ge_7": sum(1 for r in rows if r["bk"] >= 7), "bk_ge_6": sum(1 for r in rows if r["bk"] >= 6),
            "important_targets": sum(1 for r in rows if r.get("important")), "important_well_understood": sum(1 for r in rows if r.get("important") and r["bk"] >= 6)}
