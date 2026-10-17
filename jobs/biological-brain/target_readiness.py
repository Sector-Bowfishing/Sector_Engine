"""Raw, auditable per-target-species facts the registry publishes so a scorer can judge TARGET readiness without recomputing rules.

Counts only: usable rules, condition families covered by usable RESPONSE rules, mean counting independent streams (capped at 3), Southeast-transfer tally, APPROVED (human-reviewed)
rules. Nothing here is a score; `species_audit.rule_stats` shares the same definitions. A target with no usable rule reports zeros (a measured absence), never UNKNOWN-as-zero.
"""
from __future__ import annotations

import statistics

import target_set as ts

FAMILIES = {"temperature": ("waterTempBand",), "trendCrossing": ("temperatureTrend", "temperatureCrossing15C", "temperatureCrossing18C", "temperatureCrossing20C"),
            "stageHydrology": ("stageTrend", "risingStage", "fallingStage", "warmRise", "coldRise", "rapidDischargeIncrease"), "clarity": ("clarityBand",), "daypart": ("daypart",)}


def species_facts(ruleset, species_id: str) -> dict:
    use = ruleset.for_species(species_id)
    fams = {f for f, feats in FAMILIES.items() for r in use if r["kind"] == "RESPONSE" and r["feature"]["featureId"] in feats}
    tally = {"TRANSFERS": 0, "PARTIAL": 0, "UNTESTED": 0}
    for r in use:
        tally[r["transferability"]["southeastReservoir"]] += 1
    streams = [min(len({e["streamId"] for e in r["evidence"] if e.get("counts")}), 3) for r in use]
    return {"usableRules": len(use), "conditionFamilies": len(fams), "meanCountingStreams": round(statistics.fmean(streams), 2) if streams else 0.0,
            "transfer": tally, "approvedRules": sum(r["status"] == "APPROVED" for r in use), "spawnRule": any(r["kind"] == "PHENOLOGY" for r in use),
            "habitatRule": any(r["kind"] == "HABITAT" for r in use)}


def build(ruleset, target_ids=None) -> dict:
    ids = sorted(target_ids if target_ids is not None else ts.TARGET)
    return {"version": ts.TARGET_SET_VERSION, "targets": ids, "perSpecies": {s: species_facts(ruleset, s) for s in ids}}
