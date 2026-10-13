"""Pilot evidence layer (`intelligence-evidence-v1`, carried inside evaluation `intelligence-eval-v2`).

INTERNAL, NON-CUSTOMER, PILOT. Pure functions, stdlib only, no I/O, no clock (the caller passes `now`).

Purpose: make the Intelligence evaluation honest and inspectable. For every factor a pilot evaluation uses it
records WHAT the specialist Brain published, HOW it is known (kind, support, age, staleness), HOW SURE that makes
us (weakest-link confidence with its basis), and, per species, what that factor did to the rating.

What this module does NOT do (ownership stays with the specialists):
  * It owns no science. Water temperature, clarity, wind, level, depth and vegetation values are restated from the
    published Brain state verbatim. Nothing is recomputed.
  * It owns no species knowledge. A species is rated only when the Biological Brain's species node carries an
    APPROVED, schema-valid `responseBands` object. Today none does, so every species is UNSUPPORTED and UNRANKED,
    stated explicitly, with no guessed thresholds.
  * Depth and Vegetation Brains do not exist. Their factors are always UNKNOWN until a state in a ratified shape
    is published; this module neither derives nor proxies them.
  * No numeric score, no weights, no ML, no LLM, no generated prose: explanation lines are templates over records.

Rules (mirrors the research prototype, reviewed and re-tested here):
  E1  UNKNOWN never improves a rating. Replacing ANY known state (including BLOCKING) with UNKNOWN can only keep or lower
      the rating: an unknown deciding factor yields UNRANKED (below POOR), an unknown supporting factor is treated as
      unfavourable. (tests/test_evidence.py, exhaustive over every state vector.)
  E2  A BLOCKING deciding factor => POOR; nothing offsets it. A gate hit => NOT_TONIGHT.
  E3  Top class (START_HERE) needs every deciding factor known and none LIMITING, confidence >= MEDIUM, and the
      safety gates actually evaluated (the pilot has no weather/policy source, so it cannot reach the top class).
  E4  Confidence is the weakest deciding factor. No sum, no mean, no bonus for agreement, no fixed countdown.
  E5  Stale evidence lowers a factor one level. Lake-wide support for an area decision caps at MEDIUM.
  E6  Beyond a Brain's forecast horizon a factor is UNKNOWN. A current value used later is shown as `carried`
      and never counts as forecast.
  E7  Species band tier caps confidence: RESEARCH -> LOW, REVIEWED -> MEDIUM, VALIDATED -> HIGH.
"""
from __future__ import annotations

CONTRACT_VERSION = "intelligence-evidence-v1"

ORDINALS = ("BLOCKING", "LIMITING", "WORKABLE", "FAVORABLE")           # low -> high; UNKNOWN is handled apart
RATINGS = ("NOT_TONIGHT", "UNRANKED", "POOR", "LOW_PRIORITY", "WORTH_A_LOOK", "START_HERE")   # UNRANKED sits BELOW POOR on purpose (E1)
CONF = ("INSUFFICIENT", "LOW", "MEDIUM", "HIGH")
BAND_TIER_CAP = {"RESEARCH": 1, "REVIEWED": 2, "VALIDATED": 3}
BASE_CONF_BY_KIND = {"measured": 3, "observed": 3, "analysis": 2, "modeled": 2, "forecast": 2, "proxy": 1,
                     "unavailable": 0, "not_evaluated": 0, "none": 0}
# Lake Brain presence vocabulary (docs/brains/LAKE_BRAIN_INTEGRATION.md), verbatim.
PRESENCE_ASSESSABLE = {"established": None, "reported": 1, "stocked": 2, "inRangeUnconfirmed": 1}   # value = confidence cap
PRESENCE_NOT_PRESENT = {"historical", "failed/eradicated", "failed", "eradicated"}

# Lake-level factors this layer can restate. (factorId, input slot, brain id, display name, value key, unit, categorical?)
FACTOR_SPECS = (
    ("lakeLevelTrend", "lake", "lake-brain", "Lake level trend", "trendState", "", True),
    ("waterTempF", "waterTemp", "water-temp", "Water temperature", "currentTempF", "°F", False),
    ("clarityFt", "waterClarity", "water-clarity", "Water clarity", "clarityFt", "ft", False),
    ("windSustainedMph", "wind", "wind", "Wind (sustained)", "sustainedMph", "mph", False),
)
# Factors whose Brain does not publish the needed contract. Always UNKNOWN until a ratified state exists.
FUTURE_FACTORS = (
    ("windExposure", "wind", "wind", "Bank/zone wind exposure",
     "Wind publishes bank-scale exposure only as a storage file (bankDetailRef); the RTDB lake state carries a lake-wide summary, "
     "which is not zone-specific. Dependency gap, not derived here."),
    ("effectiveDepthFt", "depth", "depth", "Effective depth", "Depth Brain is not published; Intelligence does not derive depth."),
    ("vegetation", "vegetation", "vegetation", "Vegetation", "Vegetation Brain is not published; Intelligence does not derive vegetation."),
)
KNOWN_FACTOR_IDS = tuple(s[0] for s in FACTOR_SPECS) + tuple(f[0] for f in FUTURE_FACTORS)
CATEGORICAL = {s[0] for s in FACTOR_SPECS if s[6]} | {"vegetation", "windExposure"}   # categorical by nature; depth is numeric
UNITS = {s[0]: s[5] for s in FACTOR_SPECS} | {"effectiveDepthFt": "ft", "vegetation": "", "windExposure": ""}


# ------------------------------------------------------------------------------------------------ factors
def _conf_level(name: str | None) -> int | None:
    return CONF.index(name) if name in CONF else None


def factor_confidence(*, known: bool, kind: str | None, stale: bool, evidence_stale: bool, support: str | None,
                      lead_hours: float, area_decision: bool, brain_confidence: str | None, readiness: str | None) -> tuple[str, list[str]]:
    """E4/E5: confidence of ONE factor, with its basis. Only ever lowers; nothing here can raise a level."""
    if not known:
        return "INSUFFICIENT", ["value not published or beyond the Brain's forecast horizon"]
    level = BASE_CONF_BY_KIND.get(kind or "none", 0)
    basis = [f"kind {kind or 'unknown'} -> base {CONF[level]}"]
    if stale:
        level -= 1; basis.append("input is stale: -1 level")
    if evidence_stale:
        level -= 1; basis.append("Brain reports its evidence is stale: -1 level")
    if area_decision and support in ("LAKE", "POINT"):
        if level > 2:
            level = 2
        basis.append(f"{support.lower()}-level support used for an area decision: capped at MEDIUM")
    if lead_hours > 0:
        level = min(level, 2); basis.append("forecast statement: capped at MEDIUM")
    bl = _conf_level(brain_confidence.upper() if isinstance(brain_confidence, str) else None)
    if bl is not None:
        if bl < level:
            basis.append(f"Brain's own confidence label {brain_confidence} caps it")
        level = min(level, bl)
    if readiness in ("DEGRADED", "BLOCKED"):
        level = min(level, 1); basis.append(f"Brain readiness {readiness}: capped at LOW")
    return CONF[max(level, 0)], basis


def _unknown_factor(fid: str, name: str, brain_id: str, slot: str, reason: str, detail: dict | None = None) -> dict:
    out = {"factorId": fid, "name": name, "source": {"brainId": brain_id, "slot": slot}, "status": "NOT_PUBLISHED",
           "known": False, "state": "UNKNOWN", "confidence": "INSUFFICIENT", "confidenceBasis": [reason], "stale": False, "reason": reason}
    if detail:
        out["detail"] = detail
    return out


def build_factor(spec: tuple, inp: dict | None, raw_state: dict | None, *, lead_hours: float, horizon_hours: float | None,
                 area_decision: bool) -> dict:
    fid, slot, brain_id, name, key, unit, categorical = spec
    if not inp or inp.get("status") == "NOT_PUBLISHED":
        return _unknown_factor(fid, name, brain_id, slot, f"{brain_id} state not published for this lake")
    values = inp.get("values") or {}
    value = values.get(key)
    raw = raw_state or {}
    kind = inp.get("kind")
    support = "LAKE"                                       # every pilot state is lake-level; zone support does not exist yet
    beyond = lead_hours > 0 and (horizon_hours is None or lead_hours > horizon_hours)
    known = value is not None and kind not in ("unavailable", "not_evaluated", None) and not beyond
    brain_conf = raw.get("confidence") if isinstance(raw.get("confidence"), str) else (raw.get("engine") or {}).get("confidenceLabel")
    conf, basis = factor_confidence(known=known, kind=kind, stale=bool(inp.get("stale")), evidence_stale=bool(inp.get("evidenceStale")),
                                    support=support, lead_hours=lead_hours, area_decision=area_decision,
                                    brain_confidence=brain_conf, readiness=inp.get("readiness"))
    out = {"factorId": fid, "name": name,
           "source": {"brainId": brain_id, "slot": slot, "brainVersion": inp.get("brainVersion"), "modelVersion": inp.get("modelVersion"),
                      "generatedAt": inp.get("generatedAt")},
           "status": inp.get("status"), "known": known,
           "unit": unit or None, "kind": kind, "support": support,
           "ageHours": inp.get("ageHours"), "stale": bool(inp.get("stale")), "evidenceStale": bool(inp.get("evidenceStale")),
           "leadHours": lead_hours, "confidence": conf, "confidenceBasis": basis}
    if known:
        out["value"] = value
        out["ordinal"] = "PER_SPECIES"          # FAVORABLE..BLOCKING exists only against a species band; see assess_species
    else:
        out["state"] = "UNKNOWN"
    if brain_conf:
        out["brainConfidence"] = brain_conf
    if inp.get("readiness"):
        out["readiness"] = inp["readiness"]
    if beyond and value is not None:
        out["carried"] = {"value": value, "asOf": inp.get("generatedAt"),
                          "note": "current value shown for reference only; beyond the Brain's forecast horizon so it is UNKNOWN, not forecast"}
        out["reason"] = "beyond forecast horizon"
    elif value is None:
        out["reason"] = f"{brain_id} published no {key}"
    else:
        out["reason"] = f"{name} {value}{(' ' + unit) if unit else ''} ({kind}, {support.lower()}-level)"
    if inp.get("degraded"):
        out["degradedReasons"] = list(inp["degraded"])
    return out


def build_factors(inputs: dict, snapshot: dict | None, *, lead_hours: float = 0.0, horizons: dict | None = None,
                  area_decision: bool = False) -> dict:
    """{factorId: evidence object} for the lake-level factors plus the always-UNKNOWN future/dependency-gap factors."""
    horizons = horizons or {}
    raw_by_slot = {"lake": (snapshot or {}).get("lakeState"), "waterTemp": (snapshot or {}).get("waterTemperature"),
                   "waterClarity": (snapshot or {}).get("waterClarity"), "wind": (snapshot or {}).get("wind")}
    out = {}
    for spec in FACTOR_SPECS:
        out[spec[0]] = build_factor(spec, inputs.get(spec[1]), raw_by_slot.get(spec[1]), lead_hours=lead_hours,
                                    horizon_hours=horizons.get(spec[0]), area_decision=area_decision)
    for fid, slot, brain_id, name, reason in FUTURE_FACTORS:
        detail = None
        if fid == "windExposure":
            ex = (raw_by_slot["wind"] or {}).get("exposure") if isinstance(raw_by_slot["wind"], dict) else None
            if isinstance(ex, dict) and ex:
                detail = {"lakeSummaryRestated": {k: ex.get(k) for k in ("protectedPct", "exposedPct") if ex.get(k) is not None},
                          "note": "lake-wide summary, not zone-specific; not used as a factor value"}
        out[fid] = _unknown_factor(fid, name, brain_id, slot, reason, detail)
    return out


# ------------------------------------------------------------------------------------------------ response bands (Biological-owned)
def parse_bands(species_node: dict | None) -> tuple[dict | None, list[str]]:
    """Validate a Biological `responseBands` object. Returns (profile, problems). Anything unexpected => (None, reasons)."""
    if not isinstance(species_node, dict):
        return None, ["no species node published by the Biological Brain"]
    rb = species_node.get("responseBands")
    if rb is None:
        return None, ["Biological Brain has published no responseBands for this species (knowledge score only)"]
    if not isinstance(rb, dict):
        return None, ["responseBands is not an object"]
    problems = []
    if rb.get("status") != "APPROVED":
        problems.append(f"responseBands status is {rb.get('status')!r}, not APPROVED")
    tier = rb.get("evidenceTier")
    if tier not in BAND_TIER_CAP:
        problems.append(f"evidenceTier {tier!r} is not one of {sorted(BAND_TIER_CAP)}")
    deciding = rb.get("decidingFactors")
    if not isinstance(deciding, list) or not deciding:
        problems.append("decidingFactors missing or empty")
        deciding = []
    supporting = rb.get("supportingFactors") or []
    bands = rb.get("bands") if isinstance(rb.get("bands"), dict) else {}
    for fid in list(deciding) + list(supporting):
        if fid not in KNOWN_FACTOR_IDS:
            problems.append(f"factor {fid!r} is not a known Intelligence factor")
            continue
        b = bands.get(fid)
        if not isinstance(b, dict):
            problems.append(f"no band for {fid}")
            continue
        if b.get("unit", "") != UNITS.get(fid, ""):
            problems.append(f"band unit {b.get('unit')!r} for {fid} does not match {UNITS.get(fid)!r}")
        if fid in CATEGORICAL:
            m = b.get("categorical")
            if not isinstance(m, dict) or not m or any(v not in ORDINALS for v in m.values()):
                problems.append(f"categorical band for {fid} invalid")
        else:
            cuts, top = b.get("numeric"), b.get("else")
            ok = isinstance(cuts, list) and cuts and top in ORDINALS
            ok = ok and all(isinstance(c, dict) and isinstance(c.get("lt"), (int, float)) and c.get("state") in ORDINALS for c in cuts)
            ok = ok and all(cuts[i]["lt"] < cuts[i + 1]["lt"] for i in range(len(cuts) - 1)) if ok else False
            if not ok:
                problems.append(f"numeric band for {fid} invalid (needs ascending cuts, valid states and an 'else')")
    if problems:
        return None, problems
    return {"tier": tier, "deciding": tuple(deciding), "supporting": tuple(supporting), "bands": bands,
            "version": rb.get("version") or species_node.get("researchVersion")}, []


def band_state(profile: dict, fid: str, factor: dict) -> str | None:
    """Ordinal state of a KNOWN factor under the species band; None = unknown (never guessed)."""
    if not factor.get("known"):
        return None
    b = profile["bands"].get(fid)
    if not b:
        return None
    v = factor.get("value")
    if fid in CATEGORICAL:
        return b["categorical"].get(v)
    if not isinstance(v, (int, float)):
        return None
    for c in b["numeric"]:
        if v < c["lt"]:
            return c["state"]
    return b["else"]


# ------------------------------------------------------------------------------------------------ rating (E1-E3)
def rate(deciding_states: list, supporting_states: list, *, gates: dict, confidence: str) -> tuple[str, list[str], str | None]:
    """Ordinal rating from ordinal states (None = unknown). Returns (rating, caveats, bestCaseIfUnknownResolved)."""
    caveats = []
    if gates.get("hits"):
        return "NOT_TONIGHT", ["a safety/legal gate applies"], None
    if any(s == "BLOCKING" for s in deciding_states):
        return "POOR", caveats, None                                                  # E2: a known blocker stands
    if not deciding_states or any(s is None for s in deciding_states):
        # E1: with a deciding factor unknown no rating is issued. It can never read better than the same night with that
        # factor known, because UNRANKED sits below POOR. The best case is reported separately and labelled as such.
        best, _, _ = rate([s if s is not None else "FAVORABLE" for s in deciding_states],
                          [s if s is not None else "FAVORABLE" for s in supporting_states], gates=gates, confidence=confidence) \
            if deciding_states else (None, None, None)
        return "UNRANKED", ["a deciding factor is unknown, so no rating is issued"], best
    # E1: an unknown supporting factor is treated as unfavourable, never as neutral
    sup_bad = any(s in ("BLOCKING", "LIMITING", None) for s in supporting_states)
    lim = sum(1 for s in deciding_states if s == "LIMITING")
    fav = sum(1 for s in deciding_states if s == "FAVORABLE")
    n = len(deciding_states)
    if lim >= 2:
        return "LOW_PRIORITY", caveats, None
    if lim == 1:
        return ("WORTH_A_LOOK" if (fav >= 1 and not sup_bad) else "LOW_PRIORITY"), caveats, None
    if fav == n and not sup_bad:
        if CONF.index(confidence) < CONF.index("MEDIUM"):
            return "WORTH_A_LOOK", ["would rate START_HERE but confidence is below MEDIUM"], None          # E3
        if gates.get("status") != "EVALUATED":
            return "WORTH_A_LOOK", ["would rate START_HERE but safety gates were not evaluated"], None   # E3
        return "START_HERE", caveats, None
    return "WORTH_A_LOOK", caveats, None


def _entry(fid: str, f: dict, state: str, species: str, tier: str | None) -> dict:
    unit = f.get("unit") or ""
    return {"factorId": fid, "state": state, "value": f.get("value"), "unit": f.get("unit"), "kind": f.get("kind"),
            "ageHours": f.get("ageHours"), "confidence": f.get("confidence"),
            "source": f"{f['source'].get('brainId')}@{f['source'].get('brainVersion') or '?'}",
            "reason": f"{f['name']} {f.get('value')}{(' ' + unit) if unit else ''} is {state} for {species} (band tier {tier})"}


def assess_species(sid: str, presence_row: dict | None, species_node: dict | None, factors: dict, gates: dict) -> dict:
    """One species at lake level. Nothing here invents a threshold: no approved band => UNSUPPORTED => UNRANKED."""
    prow = presence_row or {}
    pstate = prow.get("presenceState")
    out = {"speciesId": sid, "presence": {"state": pstate, "confidence": prow.get("confidence")}}
    if pstate in PRESENCE_NOT_PRESENT or pstate in (None, "unknown") or (pstate not in PRESENCE_ASSESSABLE):
        reason = (f"Lake Brain presence is {pstate!r}: not assessed" if pstate in PRESENCE_NOT_PRESENT or pstate in (None, "unknown")
                  else f"Lake Brain presence state {pstate!r} is not in the known vocabulary: not assessed")
        out |= {"bandStatus": "NOT_ASSESSED", "rating": "UNRANKED", "confidence": "INSUFFICIENT", "reason": reason,
                "weakestConfidenceFactor": {"factorId": "speciesPresence", "level": "INSUFFICIENT", "reason": reason}}
        return out
    profile, problems = parse_bands(species_node)
    if profile is None:
        reason = "no approved machine-readable Biological response band: " + "; ".join(problems[:3])
        out |= {"bandStatus": "UNSUPPORTED", "rating": "UNRANKED", "confidence": "INSUFFICIENT", "reason": reason,
                "unknownFactors": [{"factorId": "responseBands", "reason": reason}],
                "weakestConfidenceFactor": {"factorId": "responseBands", "level": "INSUFFICIENT", "reason": reason},
                "affectedRating": []}
        return out
    states, explanation = {}, {"positive": [], "limiting": [], "blocking": [], "unknown": [], "stale": []}
    levels = {}
    for fid in profile["deciding"] + profile["supporting"]:
        f = factors.get(fid) or _unknown_factor(fid, fid, "?", "?", "factor not built")
        st = band_state(profile, fid, f)
        states[fid] = st
        lvl = CONF.index(f.get("confidence", "INSUFFICIENT"))
        if fid in profile["deciding"]:
            levels[fid] = lvl
        if st is None:
            explanation["unknown"].append({"factorId": fid, "reason": f.get("reason") or "unknown", "confidence": f.get("confidence")})
        elif st == "BLOCKING":
            explanation["blocking"].append(_entry(fid, f, st, sid, profile["tier"]))
        elif st == "LIMITING":
            explanation["limiting"].append(_entry(fid, f, st, sid, profile["tier"]))
        else:
            explanation["positive"].append(_entry(fid, f, st, sid, profile["tier"]))
        if f.get("stale") or f.get("evidenceStale"):
            explanation["stale"].append({"factorId": fid, "ageHours": f.get("ageHours"), "reason": "input stale" if f.get("stale") else "Brain reports evidence stale"})
    explanation["counts"] = {k: len(v) for k, v in list(explanation.items())}     # absent list == zero, stated
    # confidence: weakest deciding factor, capped by presence evidence and band tier (E4, E7)
    pcap = PRESENCE_ASSESSABLE[pstate]
    plevel = _conf_level(str(prow.get("confidence")).upper()) if prow.get("confidence") else None
    cap = BAND_TIER_CAP[profile["tier"]]
    weakest_fid = min(levels, key=levels.get)
    level = min(levels.values())
    basis = [f"weakest deciding factor {weakest_fid}: {CONF[levels[weakest_fid]]}"]
    for lab, v in (("presence evidence", pcap), ("presence confidence label", plevel), (f"response band tier {profile['tier']}", cap)):
        if v is not None and v < level:
            level = v; basis.append(f"{lab} caps it at {CONF[v]}")
    conf = CONF[level]
    rating, caveats, best_case = rate([states[x] for x in profile["deciding"]], [states[x] for x in profile["supporting"]],
                                      gates=gates, confidence=conf)
    if gates.get("status") != "EVALUATED" and rating != "NOT_TONIGHT":
        caveats.append("safety gates not evaluated in the pilot (no weather/policy source)")
    affected = [x for x in profile["deciding"]] + [x for x in profile["supporting"] if states[x] in ("BLOCKING", "LIMITING")]
    out |= {"bandStatus": "SUPPORTED", "bandTier": profile["tier"], "bandVersion": profile.get("version"), "rating": rating,
            "confidence": conf, "confidenceBasis": basis,
            "weakestConfidenceFactor": {"factorId": weakest_fid, "level": CONF[levels[weakest_fid]],
                                        "reason": (factors.get(weakest_fid) or {}).get("reason")},
            "factorStates": {k: v if v is not None else "UNKNOWN" for k, v in states.items()},
            "explanation": explanation, "caveats": caveats, "affectedRating": affected}
    if best_case:
        out["bestCaseIfUnknownResolved"] = {"rating": best_case, "note": "the most this could rate if every unknown factor turned out favourable; NOT a recommendation"}
    return out


# ------------------------------------------------------------------------------------------------ the block
def build_evidence(*, inputs: dict, snapshot: dict | None, presence: dict | None, species: dict | None, lead_hours: float = 0.0,
                   horizons: dict | None = None, gates: dict | None = None, area_decision: bool = False) -> dict:
    """The `evidence` block of an intelligence-eval-v2 evaluation. Deterministic for identical inputs."""
    gates = gates or {"status": "NOT_EVALUATED", "hits": [],
                      "reason": "the pilot has no weather, fog, warning or legal/policy source; gates are not evaluated, "
                                "so no species can reach the top rating"}
    factors = build_factors(inputs, snapshot, lead_hours=lead_hours, horizons=horizons, area_decision=area_decision)
    assessed = {sid: assess_species(sid, row, (species or {}).get(sid), factors, gates) for sid, row in sorted((presence or {}).items())}
    for sid, a in assessed.items():                                           # which factors affected which species' rating
        for fid in a.get("affectedRating") or []:
            factors[fid].setdefault("affectedRatingFor", []).append(sid)
    for f in factors.values():
        f["affectedRating"] = bool(f.get("affectedRatingFor"))
    stale = sorted(fid for fid, f in factors.items() if f.get("stale") or f.get("evidenceStale"))
    unknown = sorted(fid for fid, f in factors.items() if not f.get("known"))
    known = [f for f in factors.values() if f.get("known")]
    weakest = min(known, key=lambda f: CONF.index(f["confidence"]), default=None)
    band_counts = {}
    for a in assessed.values():
        band_counts[a["bandStatus"]] = band_counts.get(a["bandStatus"], 0) + 1
    rating_counts = {}
    for a in assessed.values():
        rating_counts[a["rating"]] = rating_counts.get(a["rating"], 0) + 1
    return {"contractVersion": CONTRACT_VERSION, "checkpoint": "NOW" if lead_hours == 0 else f"+{lead_hours:g}h",
            "decisionLevel": "LAKE", "zones": "none: no Depth, Vegetation or bank-scale Wind state is published for zones",
            "gates": gates, "factors": factors, "species": assessed,
            "summary": {"factorCount": len(factors), "knownFactors": len(known), "unknownFactors": unknown, "staleFactors": stale,
                        "staleCount": len(stale), "unknownCount": len(unknown),
                        "weakestKnownFactor": ({"factorId": weakest["factorId"], "confidence": weakest["confidence"]} if weakest else None),
                        "speciesTotal": len(assessed), "speciesByBandStatus": band_counts, "speciesByRating": rating_counts,
                        "ratingsIssued": sum(1 for a in assessed.values() if a["bandStatus"] == "SUPPORTED" and a["rating"] != "UNRANKED"),
                        "customerScore": "none: this layer produces no score and is not read by the customer path"}}
