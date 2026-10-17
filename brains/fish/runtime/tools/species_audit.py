"""READ-ONLY species inventory + SPECIES MATURITY AUDIT SCORE (an audit view, NOT an official Sector score; nothing here is wired or published).

Pure functions over data passed in (live species rows, a RuleSet, counts). Reads nothing, writes nothing, never touches the Biological rubric.

Species Maturity Audit Score (0-10) = weighted mean over the components that are KNOWN (UNKNOWN components are excluded and the weights re-normalised;
`completeness` reports the weight that was known):
  knowledgeDepth   55  species-v2 overallExact (the canonical per-species number; already contains the habitat/season/night/hydrology/clarity/temperature domains)
  evidenceQuality  15  mean over usable rules of min(counting independent streams, 3)/3 x 10   (UNKNOWN when the species has no usable rule)
  responseCoverage 20  condition families (temperature, trend/crossing, stage/hydrology, clarity, daypart) covered by >=1 usable RESPONSE rule / 5 x 10 (0 when no rule: measured)
  regionalTransfer 10  (TRANSFERS + 0.5 x PARTIAL) / usable rules x 10                             (UNKNOWN when the species has no usable rule)
Review and field validation are NOT in the score: they are reported beside it, so good desk knowledge never reads as 0.
"""
from __future__ import annotations

import statistics

WEIGHTS = {"knowledgeDepth": 55, "evidenceQuality": 15, "responseCoverage": 20, "regionalTransfer": 10}
FAMILIES = {"temperature": ("waterTempBand",), "trendCrossing": ("temperatureTrend", "temperatureCrossing15C", "temperatureCrossing18C", "temperatureCrossing20C"),
            "stageHydrology": ("stageTrend", "risingStage", "fallingStage", "warmRise", "coldRise", "rapidDischargeIncrease"),
            "clarity": ("clarityBand",), "daypart": ("daypart",)}
GROUPS = ("FRESHWATER", "SALTWATER")
FLAGS = ("FRESHWATER_ONLY", "SALTWATER_ONLY", "BRACKISH_ESTUARINE", "ANADROMOUS", "CATADROMOUS", "CROSS_HABITAT")
DOMAINS = ("temperatureOxygen", "seasonalLocationReproduction", "habitatDepthCover", "dayNightMovement", "hydrologyRainInflowLevel", "clarityLightWind",
           "foodFeedingLocation", "aggregationMobilityLifeStage")

# Primary product group + biology flag. Source = the private evidence packet (or the Sector row) that states the habitat; no habitat is guessed.
# `review` marks a genuinely ambiguous grouping (never forced).
HABITAT = {
    "striped_mullet": ("SALTWATER", "CATADROMOUS", True, "packet striped_mullet: marine/estuarine fish that ascends coastal rivers, no obligate freshwater phase; one source calls it mostly freshwater and was discounted; Sector treats it as an unassessed freshwater-policy fish"),
    "american_shad": ("FRESHWATER", "ANADROMOUS", False, "packet american_shad: anadromous clupeid; Sector relevance is freshwater runs only (packet title)"),
    "tilapia_unresolved": ("FRESHWATER", "CROSS_HABITAT", False, "packet tilapia: introduced warm freshwater fish, tolerant of brackish water"),
    "alligator_gar": ("FRESHWATER", "BRACKISH_ESTUARINE", False, "packet alligator_gar: Gulf-slope rivers, floodplain lakes and estuaries"),
    "longnose_gar": ("FRESHWATER", "BRACKISH_ESTUARINE", False, "packet longnose_gar: fresh to brackish"),
}
DEFAULT_HABITAT = ("FRESHWATER", "FRESHWATER_ONLY", False, "no brackish/marine finding recorded in the Sector packet; freshwater by registry")


def habitat_for(species_id: str) -> dict:
    g, f, review, why = HABITAT.get(species_id, DEFAULT_HABITAT)
    return {"primaryGroup": g, "habitatFlag": f, "groupingReviewRequired": review, "rationale": why}


def rule_stats(ruleset, frozen: dict | None = None, predictions: dict | None = None) -> dict:
    """Per species from a rules.RuleSet: counts, condition-family coverage, transfer tally, evidence streams."""
    out = {}
    for sid in ruleset.by_species:
        use = ruleset.for_species(sid)
        draft = [r for r in ruleset.by_species[sid] if r["status"] == "DRAFT" and ruleset.is_active(r)]
        fams = {f for f, feats in FAMILIES.items() for r in use if r["kind"] == "RESPONSE" and r["feature"]["featureId"] in feats}
        tally = {"TRANSFERS": 0, "PARTIAL": 0, "UNTESTED": 0}
        for r in use:
            tally[r["transferability"]["southeastReservoir"]] += 1
        streams = [min(len({e["streamId"] for e in r["evidence"] if e.get("counts")}), 3) for r in use]
        out[sid] = {"usable": len(use), "draft": len(draft), "families": sorted(fams), "transfer": tally,
                    "meanStreams": round(statistics.fmean(streams), 2) if streams else None,
                    "hasSpawnRule": any(r["kind"] == "PHENOLOGY" for r in use), "hasHabitatRule": any(r["kind"] == "HABITAT" for r in use),
                    "frozenRules": (frozen or {}).get(sid, 0), "predictions": (predictions or {}).get(sid, 0)}
    return out


def components(row: dict, st: dict | None) -> dict:
    """Component values 0-10, or None for UNKNOWN. `row` = live /species/{id}; `st` = rule_stats()[id] or None."""
    k = (row or {}).get("knowledge") or {}
    depth = k.get("overallExact") if row and row.get("assessment") == "ASSESSED" else None
    usable = (st or {}).get("usable", 0)
    ev = None if not usable else round(st["meanStreams"] / 3 * 10, 2)
    cov = round(len(st["families"]) / len(FAMILIES) * 10, 2) if usable else (0.0 if row and row.get("assessment") == "ASSESSED" else None)
    tr = None if not usable else round((st["transfer"]["TRANSFERS"] + 0.5 * st["transfer"]["PARTIAL"]) / usable * 10, 2)
    return {"knowledgeDepth": depth, "evidenceQuality": ev, "responseCoverage": cov, "regionalTransfer": tr}


def audit_score(comp: dict) -> dict:
    known = {k: v for k, v in comp.items() if v is not None}
    w = sum(WEIGHTS[k] for k in known)
    if not known or comp.get("knowledgeDepth") is None:
        return {"score": None, "completeness": 0.0, "scoreType": "NOT_SCORED"}
    return {"score": round(sum(WEIGHTS[k] * v for k, v in known.items()) / w, 2), "completeness": round(w / sum(WEIGHTS.values()), 2), "scoreType": "DERIVED_AUDIT"}


def domain_view(row: dict) -> dict:
    """Per-domain scores with UNKNOWN preserved (species-v2 counts an UNKNOWN domain as 0 inside overallExact; the audit shows it as UNKNOWN)."""
    doms = ((row or {}).get("knowledge") or {}).get("domains") or {}
    return {d: (doms[d]["score"] if doms.get(d, {}).get("status") == "SCORED" else "UNKNOWN") for d in DOMAINS if d in doms}


def species_record(sid: str, row: dict, st: dict | None, extra: dict | None = None) -> dict:
    comp = components(row, st)
    sc = audit_score(comp)
    h = habitat_for(sid)
    rb = (row or {}).get("responseBands") or {}
    maturity = (row or {}).get("researchMaturity")
    rec = {"speciesId": sid, "sectorLabel": (row or {}).get("displayName"), "scientificName": (row or {}).get("scientificName"), **h,
           "inBiologicalScore": (row or {}).get("assessment") == "ASSESSED", "biologicalStatus": (row or {}).get("assessment"), "researchMaturity": maturity,
           "ruleCount": (st or {}).get("usable", 0), "draftRules": (st or {}).get("draft", 0), "responseBands": bool(rb.get("bands")), "responseBandStatus": rb.get("status"),
           "evidenceTier": "T1 desk literature" if (st or {}).get("usable") else ("desk research only" if maturity == "RESEARCH" else "none"),
           "review": "NONE (0 reviewed)", "validation": "NOT_VALIDATED",
           "regionalTransferStatus": "UNKNOWN" if comp["regionalTransfer"] is None else f"{comp['regionalTransfer']}/10 ({st['transfer']['TRANSFERS']} transfer, {st['transfer']['PARTIAL']} partial, {st['transfer']['UNTESTED']} untested)",
           "components": comp, "domains": domain_view(row), "auditScore": sc["score"], "auditCompleteness": sc["completeness"], "scoreType": sc["scoreType"],
           "canonicalSpeciesScore": (row or {}).get("knowledge", {}).get("overallRounded"), "frozenRules": (st or {}).get("frozenRules", 0),
           "predictions": (st or {}).get("predictions", 0)}
    rec["missingCapabilities"] = missing(rec, st)
    if extra:
        rec.update(extra)
    return rec


def missing(rec: dict, st: dict | None) -> list[str]:
    m = []
    if not rec["inBiologicalScore"]:
        return ["species not assessed (NOT_ASSESSED row)"]
    unk = [d for d, v in rec["domains"].items() if v == "UNKNOWN"]
    if unk:
        m.append(f"{len(unk)} knowledge domain(s) UNKNOWN ({', '.join(unk[:3])}{'...' if len(unk) > 3 else ''})")
    if not rec["ruleCount"]:
        m.append("no usable machine rules")
    elif not rec["responseBands"]:
        m.append("no response bands")
    if rec["ruleCount"] and st and len(st["families"]) < 4:
        m.append(f"response rules cover {len(st['families'])} of 5 condition families")
    m += ["no human review", "no field validation"]
    return m


def group_view(records: list[dict], group: str) -> dict:
    rows = [r for r in records if r["primaryGroup"] == group]
    scored = sorted([r for r in rows if r["auditScore"] is not None], key=lambda r: r["auditScore"])
    vals = [r["auditScore"] for r in scored]
    return {"total": len(rows), "assessed": sum(r["inBiologicalScore"] for r in rows), "notAssessed": sum(not r["inBiologicalScore"] for r in rows),
            "withUsableRules": sum(r["ruleCount"] > 0 for r in rows), "withResponseBands": sum(r["responseBands"] for r in rows),
            "reviewed": 0, "validated": 0, "averageAuditScore": round(statistics.fmean(vals), 2) if vals else None,
            "medianAuditScore": round(statistics.median(vals), 2) if vals else None,
            "lowestFive": [(r["speciesId"], r["auditScore"]) for r in scored[:5]], "highestFive": [(r["speciesId"], r["auditScore"]) for r in scored[-5:][::-1]],
            "coverageCompleteness": round(statistics.fmean([r["auditCompleteness"] for r in scored]), 2) if scored else None}


def check_accounting(records: list[dict], registry_ids: list[str]) -> list[str]:
    """Every registry species appears exactly once, with exactly one primary group. Empty list = OK."""
    e = []
    ids = [r["speciesId"] for r in records]
    for s in registry_ids:
        if ids.count(s) != 1:
            e.append(f"{s}: appears {ids.count(s)} times")
    for r in records:
        if r["primaryGroup"] not in GROUPS:
            e.append(f"{r['speciesId']}: primary group {r['primaryGroup']}")
        if r["habitatFlag"] not in FLAGS:
            e.append(f"{r['speciesId']}: flag {r['habitatFlag']}")
    return e


def subset_facts(facts: dict, keep) -> dict:
    """Read-only simulation helper: the scorer's facts restricted to species ids where keep(id) is true, with registry counts recomputed."""
    import copy
    f = copy.deepcopy(facts)
    f["species"] = {k: v for k, v in f["species"].items() if keep(k)}
    sp = f["species"]
    sk = f["registry"]["responsibilities"]["speciesKnowledge"]
    sk["speciesCount"] = len(sp)
    sk["assessedCount"] = sum(1 for v in sp.values() if v.get("assessment") == "ASSESSED")
    sk["notAssessedCount"] = sum(1 for v in sp.values() if v.get("assessment") != "ASSESSED")
    return f
