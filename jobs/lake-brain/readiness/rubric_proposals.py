#!/usr/bin/env python3
"""Lake Brain rubric-mismatch PROPOSALS, quantified (docs/brains/LAKE_BRAIN_RUBRIC_PROPOSALS.md).  READ-ONLY, OFFLINE, NOTHING PUBLISHED.

What this is
------------
Three mismatches between `lake-brain-score-v1` and what the Lake Brain actually claims are analysed with the REAL production scorer
(`jobs/brain_platform/sector_brain_platform/scoring.py`).  Production is not forked: `score_variant()` calls the unmodified `score_lake()` for
every dimension the proposals do not touch and re-derives only the three that a proposal changes (operatorPlan, floodDroughtContext, validation),
then combines them with production's own `finish()`.  With `CURRENT` rules the wrapper must equal `score_lake()` (tests prove it on the published
pilots, on the 196-lake table, and on randomised fleets).

What this is NOT
----------------
It does not change the live rubric (`docs/brains/scoring/lake-brain-score-v1.json`), the scorer, any profile, validation node, lifecycle or
status.  The scorer does not even read the rubric JSON (weights and rules are hard-coded in scoring.py), and nothing reads
`docs/brains/scoring/proposed/`; tests prove both.  Every figure under a PARTIAL / VALIDATED column is HYPOTHETICAL.

Inputs (all committed): the 196-lake table `jobs/lake-brain/data/bindings.proposed.v1.json` and the per-lake fact table
`jobs/lake-brain/readiness/data/rubric_proposals_lake_facts.csv` (427 research-bound lakes; rebuild with `--build-facts`, see that function).

  python3 jobs/lake-brain/readiness/rubric_proposals.py --summary            # headline numbers as JSON
  python3 jobs/lake-brain/readiness/rubric_proposals.py --tables             # the markdown tables used in the proposals document
  python3 jobs/lake-brain/readiness/rubric_proposals.py --write-drafts       # (re)generate docs/brains/scoring/proposed/*.json
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "jobs", "brain_platform"))
from sector_brain_platform.scoring import dim, finish, ladder, score_lake  # noqa: E402  (production code, unmodified)

BINDINGS = os.path.join(REPO, "jobs", "lake-brain", "data", "bindings.proposed.v1.json")
FACTS_CSV = os.path.join(HERE, "data", "rubric_proposals_lake_facts.csv")
PILOTS_LIVE = os.path.join(HERE, "data", "pilots_live_2026-10-13.json")
RUBRIC_V1 = os.path.join(REPO, "docs", "brains", "scoring", "lake-brain-score-v1.json")
PROPOSED_DIR = os.path.join(REPO, "docs", "brains", "scoring", "proposed")

DIRECTORY = 621
NOW = dt.datetime(2026, 10, 13, tzinfo=dt.timezone.utc)
DIM_ORDER = ("sourceAuthority", "operatorPlan", "historyQuality", "seasonalBaseline", "trendQuality", "floodDroughtContext", "validation", "coverage")
WEIGHTS = {"sourceAuthority": 15, "operatorPlan": 10, "historyQuality": 15, "seasonalBaseline": 10, "trendQuality": 10,
           "floodDroughtContext": 5, "validation": 15, "coverage": 20}
CRITICAL = ("sourceAuthority", "historyQuality", "seasonalBaseline", "trendQuality", "validation")   # PROPOSED designation (readiness matrix option A)
TARGET_OVERALL, TARGET_CRITICAL = 8.0, 7.5
PILOT_HISTORY_SUFFICIENT = {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}   # live profiles say SUFFICIENT (deep TVA history)
LOWER_POOL_LABELS = ("Top of Inactive", "Bottom of Power", "Minimum", "Bottom of Operating", "Top of Power")   # as plan_flood_by_operator.py
VMAP = {"NOT_VALIDATED": 0, "PARTIAL": 5, "VALIDATED": 10}
FAMILIES = ("providerDisplay", "deterministicDerivation", "historicalState", "rapidChange")
FAMILY_LEVEL = {"providerDisplay": 1, "deterministicDerivation": 2, "historicalState": 3, "rapidChange": 3}
EVIDENCE_LEVELS = ("NOW", "KNOWN", "CEILING")
FLEETS = (5, 63, 123, 196)
# Validation calendar (docs/brains/LAKE_BRAIN_VALIDATION_READINESS.md section 6): ledger day 0 is 2026-10-13 with 5 pilots only.
LEDGER_DAY0 = dt.date(2026, 10, 13)
PARTIAL_EARLIEST = LEDGER_DAY0 + dt.timedelta(days=90)     # 2027-01-11
VALIDATED_EARLIEST = LEDGER_DAY0 + dt.timedelta(days=365)  # 2027-10-13


# ============================================================================================================== rules
@dataclasses.dataclass(frozen=True)
class Rules:
    """Which proposals are applied.  CURRENT = lake-brain-score-v1 exactly."""
    flood: str = "all"          # all (current) | exists_x (UNDETERMINED excluded) | exists_c (UNDETERMINED counted)
    plan: str = "all"           # all (current) | published_x (UNKNOWN excluded) | published_c (UNKNOWN counted)
    validation: str = "word"    # word (current) | claims (weakest counted family)
    withhold_rapid: bool = False
    withhold_historical: bool = False   # OUT OF SCOPE variant, shown only to prove what it would take to meet the validation floor early
    claims_agg: str = "min"     # min (proposed) | mean (NOT proposed: sensitivity only)

    def label(self) -> str:
        parts = []
        if self.flood != "all":
            parts.append("P1-" + self.flood[-1].upper())
        if self.validation != "word":
            parts.append("P2" + ("+withhold-RAPID" if self.withhold_rapid else "") + ("+withhold-HISTORICAL" if self.withhold_historical else ""))
        if self.plan != "all":
            parts.append("P3-" + self.plan[-1].upper())
        return " + ".join(parts) or "CURRENT"


CURRENT = Rules()
P1X, P1C = Rules(flood="exists_x"), Rules(flood="exists_c")
P2 = Rules(validation="claims")
P2W = Rules(validation="claims", withhold_rapid=True)
P3X, P3C = Rules(plan="published_x"), Rules(plan="published_c")
COMBINED_X = Rules(flood="exists_x", plan="published_x", validation="claims", withhold_rapid=True)
COMBINED_C = Rules(flood="exists_c", plan="published_c", validation="claims", withhold_rapid=True)
VARIANTS = {"CURRENT": CURRENT, "P1-X": P1X, "P1-C": P1C, "P2": P2, "P2+withhold-RAPID": P2W, "P3-X": P3X, "P3-C": P3C,
            "ALL (X)": COMBINED_X, "ALL (C)": COMBINED_C}


# ============================================================================================================== facts
@dataclasses.dataclass(frozen=True)
class Lake:
    lake_id: str
    in196: bool
    wave: str
    rollout_batch: str          # P pilot, A..D rollout batch of the 2026-10-13 plan, '' = not in the 196
    rollout_idx: int            # position in the declared rollout order (pilots first); -1 = not in the 196
    provider: str
    capability: str
    history_class: str          # SUFFICIENT | LIMITED | INSUFFICIENT | NONE (pilot override applied)
    plan_strict: bool           # guide curve, or zone with top AND bottom (research strict definition)
    plan_partial: bool          # S-B: documented flood-pool bottom + operator-published lower-pool level, no strict zone (a definition decision)
    tier2_plan: bool            # TWDB conservation + dead pool, not strict
    matched: bool               # lake joined to an operator project by a verified match
    searched: bool              # a plan/flood evidence search was run for this lake
    flood_strict: bool          # operator flood-pool bottom documented
    tier2_flood: bool           # TWDB flood level
    nid_record: bool            # an NID dam record is linked
    nid_flood: bool | None      # NID purposes contain 'Flood Risk Reduction'; None = no record / no purposes

    @property
    def pilot(self) -> bool:
        return self.rollout_batch == "P"


def _b(x: str) -> bool:
    return str(x).strip() in ("1", "True", "true")


def load_facts(path: str = FACTS_CSV) -> list[Lake]:
    out = []
    for r in csv.DictReader(open(path)):
        out.append(Lake(r["lake_id"], _b(r["in196"]), r["wave"], r["rollout_batch"], int(r["rollout_idx"]), r["provider"], r["capability"],
                        r["history_class"], _b(r["plan_strict"]), _b(r["plan_partial"]), _b(r["tier2_plan"]), _b(r["matched"]), _b(r["searched"]),
                        _b(r["flood_strict"]), _b(r["tier2_flood"]), _b(r["nid_record"]),
                        None if r["nid_flood"] == "" else _b(r["nid_flood"])))
    return out


FACT_COLUMNS = ["lake_id", "in196", "wave", "rollout_batch", "rollout_idx", "provider", "capability", "history_class", "plan_strict", "plan_partial",
                "tier2_plan", "matched", "searched", "flood_strict", "tier2_flood", "nid_record", "nid_flood"]


def build_facts(bindings_path: str, ev_csv: str, v2_csv: str, nid_links_csv: str, rollout_plan_json: str, out_path: str = FACTS_CSV) -> int:
    """Rebuild the committed fact table from its sources (none of this runs in tests):
         bindings_path   jobs/lake-brain/data/bindings.proposed.v1.json                     (196 accepted-eligible lakes, authoritative for them)
         ev_csv          research branch  docs/research/lake-brain/data/plan_flood_evidence.csv     (315 wave-1 lakes: plan/flood/tier-2 evidence)
         v2_csv          research branch  docs/research/lake-brain/data/verified_bindings_v2.csv     (427 research-bound lakes under ANY rule)
         nid_links_csv   Sector_Research_Data/lake-brain/binding/nid_links.csv                (NID dam link and purposes; same input as the table builder)
         rollout_plan_json  jobs/lake-brain/history/rollout_plan.v1.json (branch feat/lake-fleet-opsvis; declared batch order A..D)
       Lakes in the 196 take every field from the committed table; the other 231 take plan/flood from the evidence CSV (wave-2 lakes: no search was run,
       so they carry NO plan/flood credit and `searched` = 0).  History for the 231 is the research `history_class`."""
    table = {r["lakeId"]: r for r in json.load(open(bindings_path))["bindings"]}
    ev = {r["lakeId"]: r for r in csv.DictReader(open(ev_csv))}
    v2 = {r["lake_id"]: r for r in csv.DictReader(open(v2_csv))}
    nid = {r["lakeId"]: r for r in csv.DictReader(open(nid_links_csv))}
    plan = json.load(open(rollout_plan_json))
    order = {}
    for lk in plan["pilots"]:
        order[lk] = ("P", len(order))
    for b in ("A", "B", "C", "D"):
        for lk in plan["batches"][b]["lakes"]:
            order[lk] = (b, len(order))

    def tf(x: str) -> bool:
        return str(x).strip().lower() == "true"

    rows = []
    for lake_id, v in sorted(v2.items()):
        t = table.get(lake_id)
        e = ev.get(lake_id)
        if t:
            p = t.get("plan") or {}
            d = t.get("dam")
            flood_strict, plan_strict, matched = bool(p.get("floodStrict")), bool(p.get("planStrict")), bool(p.get("verifiedMatch"))
            hist, cap, prov = t["historyClass"], t["capability"], t["provider"]
            nid_record, nid_flood = bool(d), (d.get("floodControl") if d else None)
            searched = True
        else:
            hist, cap, prov = v["history_class"], v["capability_class"], v["provider"]
            n = nid.get(lake_id)
            purposes = (n or {}).get("purposes") or ""
            nid_record, nid_flood = n is not None, (("Flood Risk Reduction" in purposes) if purposes else None)
            searched = e is not None
            plan_strict, flood_strict, matched = (tf(e["planStrict"]), tf(e["floodStrict"]), tf(e["verifiedMatch"])) if e else (False, False, False)
        if lake_id in PILOT_HISTORY_SUFFICIENT or lake_id == "Lake Hartwell|SC":
            hist = "SUFFICIENT"
        labels = (e or {}).get("levelLabels") or ""
        partial = bool(flood_strict and not plan_strict and any(lbl in labels for lbl in LOWER_POOL_LABELS))
        t2p = bool(e and tf(e["tier2Zone"]) and not plan_strict)
        t2f = bool(e and tf(e["tier2Flood"]) and not flood_strict)
        batch, idx = order.get(lake_id, ("", -1))
        rows.append({"lake_id": lake_id, "in196": int(t is not None), "wave": v["wave"], "rollout_batch": batch, "rollout_idx": idx, "provider": prov,
                     "capability": cap, "history_class": hist, "plan_strict": int(plan_strict), "plan_partial": int(partial), "tier2_plan": int(t2p),
                     "matched": int(matched), "searched": int(searched), "flood_strict": int(flood_strict), "tier2_flood": int(t2f),
                     "nid_record": int(nid_record), "nid_flood": "" if nid_flood is None else int(bool(nid_flood))})
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, FACT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ============================================================================================================== classification
def effective(l: Lake, level: str) -> tuple[bool, bool]:
    """(plan captured, flood known) for a lake at an evidence level.
       NOW      what the committed table documents today (strict research definitions).
       KNOWN    plus TWDB tier-2 evidence already in hand (conservation/dead-pool zone pair, flood level).  No definition change.
       CEILING  every lake whose operator-published evidence could exist is documented: plan = strict + S-B partial (a DEFINITION decision, not
                evidence) + tier-2; flood = every lake where a flood pool exists (generous: includes TVA, whose API publishes no flood bottom)."""
    if level == "NOW":
        return l.plan_strict, l.flood_strict
    if level == "KNOWN":
        return l.plan_strict or l.tier2_plan, l.flood_strict or l.tier2_flood
    if level == "CEILING":
        return l.plan_strict or l.tier2_plan or l.plan_partial, flood_exists(l, "CEILING")
    raise ValueError(level)


def flood_exists(l: Lake, level: str = "NOW") -> bool:
    """A flood pool exists when the operator documents a flood-pool bottom, TWDB documents a flood level (only once that evidence is in hand: KNOWN, CEILING),
    or the linked NID dam record lists 'Flood Risk Reduction' among its purposes."""
    return l.flood_strict or (level != "NOW" and l.tier2_flood) or l.nid_flood is True


def flood_class(l: Lake, level: str = "NOW") -> str:
    """DOCUMENTED            a flood-pool level is documented at this evidence level
       EXISTS_UNPUBLISHED    a flood pool exists (NID flood control, or a TWDB level) and no level is documented: UNKNOWN because unpublished or not found
       NOT_APPLICABLE        an NID dam record with purposes is linked, none is flood control, and nothing is documented
       UNDETERMINED          no NID dam record or no purposes, nothing documented: whether a pool exists is not known"""
    if effective(l, level)[1]:
        return "DOCUMENTED"
    if flood_exists(l, level):
        return "EXISTS_UNPUBLISHED"
    if l.nid_flood is False:
        return "NOT_APPLICABLE"
    return "UNDETERMINED"


def plan_published(l: Lake, level: str = "NOW") -> bool:
    """The operator publishes plan-type levels: strict plan, an S-B lower-pool level beside Top of Conservation, or (once in hand) a TWDB zone pair."""
    return l.plan_strict or l.plan_partial or (level != "NOW" and l.tier2_plan)


def plan_class(l: Lake, level: str = "NOW") -> str:
    """CAPTURED                strict guide curve / two-sided zone documented (at this evidence level)
       PUBLISHED_NOT_CAPTURED  the operator publishes plan-type levels that do not meet the strict rule (S-B lower-pool level, TWDB zone pair)
       OPERATOR_READ_NO_PLAN   a verified operator project was read and publishes no plan-type level (not applicable)
       UNKNOWN                 no verified operator record (not matched, or no search was run): cannot say whether a plan is published"""
    if effective(l, level)[0]:
        return "CAPTURED"
    if plan_published(l, level):
        return "PUBLISHED_NOT_CAPTURED"
    if l.matched:
        return "OPERATOR_READ_NO_PLAN"
    return "UNKNOWN"


# ============================================================================================================== scoring
def production_facts(lakes: list[Lake], level: str, validation_word: str, health: str = "HEALTHY", directory: int = DIRECTORY) -> dict:
    """Facts in the shape score_lake() reads (published profile and state fields only)."""
    profiles, states = {}, {}
    for l in lakes:
        plan, flood = effective(l, level)
        profiles[l.lake_id] = {"sourceCapability": {"level": l.capability},
                               "operatingPools": {"guideCurve": {"available": plan}, "operatingZoneSource": None},
                               "historicalCoverage": {"baselineStatus": l.history_class}}
        states[l.lake_id] = {"kind": "OBSERVED", "floodPoolState": "NORMAL" if flood else "UNKNOWN"}
    return {"registry": {"health": health, "directoryLakeCount": directory}, "validation": {"status": validation_word}, "health": {"status": health},
            "profiles": profiles, "states": states, "directoryLakeCount": directory}


def _pct(num: int, den: int) -> str:
    return "n/a" if den <= 0 else f"{round(100 * num / den)} %"


def operator_plan_dim(lakes: list[Lake], level: str, rule: str) -> dict:
    cap = {l.lake_id: effective(l, level)[0] for l in lakes}
    if rule == "all":
        den = list(lakes)
    elif rule == "published_x":
        den = [l for l in lakes if plan_class(l, level) in ("CAPTURED", "PUBLISHED_NOT_CAPTURED")]
    elif rule == "published_c":
        den = [l for l in lakes if plan_class(l, level) in ("CAPTURED", "PUBLISHED_NOT_CAPTURED", "UNKNOWN")]
    else:
        raise ValueError(rule)
    num = sum(cap[l.lake_id] for l in den)
    return dim("operatorPlan", 10, None if not den else (num / len(den)) * 10, f"{num} of {len(den)} lakes in the plan denominator ({rule}): {_pct(num, len(den))}")


def flood_dim(lakes: list[Lake], level: str, rule: str) -> dict:
    kn = {l.lake_id: effective(l, level)[1] for l in lakes}
    if rule == "all":
        den = list(lakes)
    elif rule == "exists_x":
        den = [l for l in lakes if flood_class(l, level) in ("DOCUMENTED", "EXISTS_UNPUBLISHED")]
    elif rule == "exists_c":
        den = [l for l in lakes if flood_class(l, level) in ("DOCUMENTED", "EXISTS_UNPUBLISHED", "UNDETERMINED")]
    else:
        raise ValueError(rule)
    num = sum(kn[l.lake_id] for l in den)
    return dim("floodDroughtContext", 5, None if not den else (num / len(den)) * 10, f"{num} of {len(den)} states in the flood denominator ({rule}): {_pct(num, len(den))}")


def claims_state(validation, rules: Rules) -> dict:
    """Normalise a validation input to {family: status}.  A bare word means every family has that status."""
    if isinstance(validation, str):
        validation = {f: validation for f in FAMILIES}
    out = {f: validation.get(f, "NOT_VALIDATED") for f in FAMILIES}
    if rules.withhold_rapid:
        out["rapidChange"] = "WITHHELD"
    if rules.withhold_historical:
        out["historicalState"] = "WITHHELD"
    return out


def validation_dim(rules: Rules, validation) -> tuple[dict, bool]:
    """(dimension, gate fires).  word: production's rule.  claims: min (or mean) of the COUNTED families; a WITHHELD family is not counted."""
    if rules.validation == "word":
        status = validation if isinstance(validation, str) else None
        v = VMAP.get(status) if status in VMAP else None
        return dim("validation", 15, v, f"/validation/lake-brain: {status or 'absent'}"), (status == "NOT_VALIDATED" or status is None)
    st = claims_state(validation, rules)
    counted = {f: s for f, s in st.items() if s != "WITHHELD"}
    vals = [VMAP[s] for s in counted.values()]
    if not vals:
        return dim("validation", 15, None, "no published claim family to validate"), False
    v = min(vals) if rules.claims_agg == "min" else statistics.fmean(vals)
    return dim("validation", 15, v, f"claims {rules.claims_agg} over counted {sorted(counted)}: {counted}"), min(vals) == 0


def score_variant(lakes: list[Lake], level: str, rules: Rules, validation, now: dt.datetime = NOW, health: str = "HEALTHY", directory: int = DIRECTORY) -> dict:
    """Production score_lake() for the unchanged dimensions and gates; the three proposal-affected dimensions re-derived; combined by production finish().
       `validation` is a status word, or {family: status} for the claims rule."""
    # Production runs with the status word for CURRENT rules; for the claims rule its validation dimension and gate are replaced below, so any word will do.
    base = score_lake(production_facts(lakes, level, validation if rules.validation == "word" else "VALIDATED", health, directory), now)
    by_id = {k: {"id": k, "weight": v["weight"], "status": v["status"], **({"value": v["value"]} if "value" in v else {}), "evidence": v["evidence"]}
             for k, v in base["scoreBreakdown"].items()}
    by_id["operatorPlan"] = operator_plan_dim(lakes, level, rules.plan)
    by_id["floodDroughtContext"] = flood_dim(lakes, level, rules.flood)
    vdim, vgate = validation_dim(rules, validation)
    by_id["validation"] = vdim
    dims = [by_id[k] for k in DIM_ORDER]
    n = len(lakes)
    cov = n / directory if directory else None
    gates = []
    if cov is not None and cov < 0.10:
        gates.append({"gate": "coverage", "cap": 3.0, "why": f"{n} of {directory} lakes profiled ({round(100 * cov)} % < 10 %)"})
    if vgate:
        gates.append({"gate": "validation", "cap": 5.0, "why": "validation not yet at PARTIAL for every counted claim family" if rules.validation == "claims" else "validation NOT_VALIDATED"})
    if health in ("FAILED", "UNKNOWN", None):
        gates.append({"gate": "health", "cap": 2.0, "why": f"brain health {health or 'absent'}"})
    out = finish("lake-brain-score-v1", "docs/brains/scoring/lake-brain-score-v1.json", dims, gates, now, "n/a")
    out["unroundedUncapped"] = sum(d["value"] * d["weight"] for d in dims if d["status"] == "SCORED") / 100.0
    return out


def values(sc: dict) -> dict:
    return {k: sc["scoreBreakdown"][k].get("value") for k in DIM_ORDER}


def fleet(lakes: list[Lake], n: int, order: list[Lake] | None = None) -> list[Lake]:
    """Nested fleets of the 196: the pilots, then lakes in the declared rollout order, truncated to n.  n=427 returns every research-bound lake."""
    if n == 427:
        return list(lakes)
    pool = order if order is not None else sorted((l for l in lakes if l.in196), key=lambda l: l.rollout_idx)
    return pool[:n]


def hash_order(lakes: list[Lake], seed: int) -> list[Lake]:
    pilots = sorted((l for l in lakes if l.pilot), key=lambda l: l.rollout_idx)
    rest = sorted((l for l in lakes if l.in196 and not l.pilot), key=lambda l: hashlib.sha256(f"{seed}|{l.lake_id}".encode()).hexdigest())
    return pilots + rest


def critical_report(sc: dict) -> dict:
    v = values(sc)
    crit = {k: v[k] for k in CRITICAL}
    worst = min(crit, key=lambda k: (crit[k] if crit[k] is not None else -1))
    ok_crit = all((x is not None and x >= TARGET_CRITICAL) for x in crit.values())
    ok_overall = sc["value"] >= TARGET_OVERALL
    unrounded = sc["unroundedUncapped"]
    return {"critical": crit, "weakestCritical": worst, "criticalOk": ok_crit, "overallOk": ok_overall, "target": ok_crit and ok_overall,
            "unrounded": round(unrounded, 3), "roundingAssist": ok_overall and unrounded < TARGET_OVERALL}


# ============================================================================================================== pilots (live) equality input
def pilots_live_facts(path: str = PILOTS_LIVE, validation: str = "NOT_VALIDATED") -> dict:
    """The five pilot profiles and states as PUBLISHED (read-only copy of lakes/{k}/brain and lakes/{k}/states/lake, 2026-10-13)."""
    raw = json.load(open(path))
    return {"registry": {"health": "HEALTHY", "directoryLakeCount": DIRECTORY}, "validation": {"status": validation}, "health": {"status": "HEALTHY"},
            "profiles": {k: v["profile"] for k, v in raw.items()}, "states": {k: v["state"] for k, v in raw.items()}, "directoryLakeCount": DIRECTORY}


# ============================================================================================================== JSON patches against v1
def v1() -> dict:
    return json.load(open(RUBRIC_V1))


PATCHES = {
    "P1-X": [
        {"op": "replace", "path": "/dimensions/5/label", "value": "Flood-pool state known, where a flood pool exists"},
        {"op": "replace", "path": "/dimensions/5/fact", "value": "states[*].floodPoolState != UNKNOWN, over lakes with profiles[*].operatingPools.floodPoolApplicability == EXISTS"},
        {"op": "add", "path": "/dimensions/5/applicability", "value": {
            "field": "profiles[*].operatingPools.floodPoolApplicability",
            "EXISTS": "an operator or TWDB flood-pool level is documented, OR the linked NID dam record lists 'Flood Risk Reduction' among its purposes",
            "NOT_APPLICABLE": "an NID dam record with purposes is linked, none of them is flood control, and no flood-pool level is documented",
            "UNDETERMINED": "no NID dam record or no purposes, and no flood-pool level is documented",
            "denominator": "EXISTS only (UNDETERMINED excluded)",
            "EXISTS_but_unpublished": "stays in the denominator as UNKNOWN: a pool that exists but whose level is not published is a real gap, not a non-applicability"}},
    ],
    "P1-C": [
        {"op": "replace", "path": "/dimensions/5/label", "value": "Flood-pool state known, where a flood pool exists or cannot be ruled out"},
        {"op": "replace", "path": "/dimensions/5/fact", "value": "states[*].floodPoolState != UNKNOWN, over lakes with profiles[*].operatingPools.floodPoolApplicability in {EXISTS, UNDETERMINED}"},
        {"op": "add", "path": "/dimensions/5/applicability", "value": {
            "field": "profiles[*].operatingPools.floodPoolApplicability",
            "EXISTS": "an operator or TWDB flood-pool level is documented, OR the linked NID dam record lists 'Flood Risk Reduction' among its purposes",
            "NOT_APPLICABLE": "an NID dam record with purposes is linked, none of them is flood control, and no flood-pool level is documented",
            "UNDETERMINED": "no NID dam record or no purposes, and no flood-pool level is documented",
            "denominator": "EXISTS and UNDETERMINED (only a positive NOT_APPLICABLE finding is excluded)"}},
    ],
    "P2": [
        {"op": "replace", "path": "/dimensions/6/label", "value": "Claim validation (weakest published claim family)"},
        {"op": "replace", "path": "/dimensions/6/fact", "value": "min over COUNTED claim families of /validation/lake-brain/claims/{family}.status"},
        {"op": "add", "path": "/dimensions/6/families", "value": [
            {"id": "providerDisplay", "level": 1, "claims": "current pool elevation, operator guide / normal pool / flood-pool bottom as published, source id, freshness"},
            {"id": "deterministicDerivation", "level": 2, "claims": "difference from guide or normal pool, operator zone, 72 h mean rate, trend direction arithmetic"},
            {"id": "historicalState", "level": 3, "claims": "NORMAL / UNUSUAL / VERY_UNUSUAL against the lake's own history; trend label stability"},
            {"id": "rapidChange", "level": 3, "claims": "RISING_RAPIDLY / FALLING_RAPIDLY flag"}]},
        {"op": "add", "path": "/dimensions/6/counted", "value": "a family counts while at least one of its claims is published; a family withheld from publication (status WITHHELD) is not counted and its claims are not shown"},
        {"op": "add", "path": "/dimensions/6/aggregate", "value": "min"},
        {"op": "add", "path": "/dimensions/6/familyMaturity", "value": {
            "NOT_VALIDATED": "no family-specific acceptance evidence recorded",
            "PARTIAL": "binding acceptance recorded (n >= 60, <= 1 error, flagged tier in full); plus per family: derivation = conformance fixtures and level-meaning review; historicalState = pre-registered hold-out PASS and ledger >= 90 days; rapidChange = a pre-registered criterion PASS on ledger data dated after its commit",
            "VALIDATED": "PARTIAL plus per family: provider display and derivation = continuous freshness record >= 90 days; historicalState and rapidChange = >= 12 months of logged predictions scored once under the pre-registered criteria"}},
        {"op": "replace", "path": "/gates/1/when", "value": "any COUNTED claim family is NOT_VALIDATED"},
    ],
    "P3-X": [
        {"op": "replace", "path": "/dimensions/1/label", "value": "Operating guide or zone captured, where the operator publishes one"},
        {"op": "replace", "path": "/dimensions/1/fact", "value": "profiles[*].operatingPools.guideCurve.available or operatingZoneSource, over lakes with profiles[*].operatingPools.planPublication in {CAPTURED, PUBLISHED_NOT_CAPTURED}"},
        {"op": "add", "path": "/dimensions/1/publication", "value": {
            "field": "profiles[*].operatingPools.planPublication",
            "CAPTURED": "strict guide curve, or a zone with BOTH a top and a bottom, documented",
            "PUBLISHED_NOT_CAPTURED": "the operator publishes plan-type levels (a lower-pool level beside Top of Conservation; a TWDB conservation + dead pool pair) that do not meet the strict rule",
            "OPERATOR_READ_NO_PLAN": "a verified operator project was read and publishes no plan-type level (not applicable)",
            "UNKNOWN": "no verified operator record",
            "denominator": "CAPTURED and PUBLISHED_NOT_CAPTURED (UNKNOWN excluded)"}},
    ],
    "P3-C": [
        {"op": "replace", "path": "/dimensions/1/label", "value": "Operating guide or zone captured, where the operator publishes one or is unknown"},
        {"op": "replace", "path": "/dimensions/1/fact", "value": "profiles[*].operatingPools.guideCurve.available or operatingZoneSource, over lakes with profiles[*].operatingPools.planPublication in {CAPTURED, PUBLISHED_NOT_CAPTURED, UNKNOWN}"},
        {"op": "add", "path": "/dimensions/1/publication", "value": {
            "field": "profiles[*].operatingPools.planPublication",
            "CAPTURED": "strict guide curve, or a zone with BOTH a top and a bottom, documented",
            "PUBLISHED_NOT_CAPTURED": "the operator publishes plan-type levels that do not meet the strict rule",
            "OPERATOR_READ_NO_PLAN": "a verified operator project was read and publishes no plan-type level (not applicable)",
            "UNKNOWN": "no verified operator record",
            "denominator": "CAPTURED, PUBLISHED_NOT_CAPTURED and UNKNOWN (only OPERATOR_READ_NO_PLAN excluded)"}},
    ],
}
DRAFT_COMBINATION = ("P1-X", "P2", "P3-X")        # the draft file carries the X variants; the C variants are alternatives (patch file)
DRAFT_VERSION = "lake-brain-score-v2-DRAFT"


def apply_patch(doc: dict, ops: list[dict]) -> dict:
    """Minimal RFC 6902 (add / replace on object keys and array indexes), enough for PATCHES."""
    doc = copy.deepcopy(doc)
    for op in ops:
        parts = [p for p in op["path"].split("/") if p != ""]
        cur = doc
        for p in parts[:-1]:
            cur = cur[int(p)] if isinstance(cur, list) else cur[p]
        last = parts[-1]
        if isinstance(cur, list):
            raise ValueError("array add/replace by index at the leaf is not used here")
        if op["op"] == "replace" and last not in cur:
            raise KeyError(op["path"])
        if op["op"] == "add" and last in cur:
            raise KeyError("add over existing " + op["path"])
        cur[last] = op["value"]
    return doc


def draft_rubric() -> dict:
    doc = v1()
    for k in DRAFT_COMBINATION:
        doc = apply_patch(doc, PATCHES[k])
    doc["scoreVersion"] = DRAFT_VERSION
    doc["status"] = "DRAFT PROPOSAL - NOT LOADED BY ANY SCORER - NOT ADOPTED (docs/brains/LAKE_BRAIN_RUBRIC_PROPOSALS.md)"
    doc["derivedFrom"] = "lake-brain-score-v1 + JSON patches P1-X, P2, P3-X (docs/brains/scoring/proposed/lake-brain-score-v1-to-v2-DRAFT.patch.json)"
    doc["proposedCriticalDimensions"] = list(CRITICAL)
    return doc


def patch_file() -> dict:
    return {"status": "DRAFT PROPOSAL - NOT LOADED BY ANY SCORER - NOT ADOPTED", "base": "docs/brains/scoring/lake-brain-score-v1.json", "format": "RFC 6902 subset (add, replace)",
            "note": "P1-X/P1-C and P3-X/P3-C are alternatives (UNKNOWN excluded / counted). P2 changes only the validation dimension and its gate; withholding RAPID is a publishing decision, not a rubric edit.",
            "patches": PATCHES}


def write_drafts() -> list[str]:
    os.makedirs(PROPOSED_DIR, exist_ok=True)
    outs = []
    for name, doc in (("lake-brain-score-v2-DRAFT.json", draft_rubric()), ("lake-brain-score-v1-to-v2-DRAFT.patch.json", patch_file())):
        p = os.path.join(PROPOSED_DIR, name)
        with open(p, "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        outs.append(p)
    return outs


# ============================================================================================================== analysis / tables
def all_lakes() -> list[Lake]:
    return load_facts()


def lakes_for(fleet_size: int, lakes: list[Lake] | None = None) -> list[Lake]:
    lakes = lakes if lakes is not None else all_lakes()
    return fleet(lakes, fleet_size)


def classification_counts(lakes: list[Lake], level: str = "NOW") -> dict:
    return {"flood": dict(collections.Counter(flood_class(l, level) for l in lakes)), "plan": dict(collections.Counter(plan_class(l, level) for l in lakes)),
            "floodExists": sum(flood_exists(l, level) for l in lakes),
            "floodExistsUnpublishedTVA": sum(1 for l in lakes if flood_class(l, level) == "EXISTS_UNPUBLISHED" and l.provider == "tva")}


def today_pilot_lakes(lakes: list[Lake]) -> list[Lake]:
    return fleet(lakes, 5)


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.1f}"


def proposal_effect_rows(lakes: list[Lake], rules_list: list[str], level: str = "NOW") -> list[dict]:
    """For each fleet size: dimension (current -> proposed), uncapped and displayed, under NOT_VALIDATED / PARTIAL / VALIDATED (hypothetical)."""
    rows = []
    for n in (5, 63, 123, 196):
        fl = lakes_for(n, lakes)
        for name in rules_list:
            rules = VARIANTS[name]
            row = {"fleet": n, "variant": name}
            for st, label in (("NOT_VALIDATED", "NV"), ("PARTIAL", "PA"), ("VALIDATED", "VA")):
                sc = score_variant(fl, level, rules, st)
                row[label] = {"uncapped": sc["uncapped"], "displayed": sc["value"], "dims": values(sc)}
            rows.append(row)
    return rows


def max_achievable(lakes: list[Lake], variant: str, n: int, level: str, validation_word: str = "VALIDATED") -> dict:
    fl = lakes_for(n, lakes)
    sc = score_variant(fl, level, VARIANTS[variant], validation_word)
    rep = critical_report(sc)
    return {"fleet": n, "variant": variant, "level": level, "validation": validation_word, "dims": values(sc), "uncapped": sc["uncapped"], "displayed": sc["value"],
            "unrounded": rep["unrounded"], "critical": rep["critical"], "weakestCritical": rep["weakestCritical"], "criticalOk": rep["criticalOk"],
            "overallOk": rep["overallOk"], "target": rep["target"], "gates": [g["gate"] for g in sc["scoreBlockers"] if "cap" in g]}


def history_margin(lakes: list[Lake], variant: str, level: str = "NOW", n: int = 196, to: str = "NONE") -> int:
    """How many SUFFICIENT-history lakes (non-pilot, lowest rollout order first) could drop to `to` (NONE hits historyQuality and seasonalBaseline;
    LIMITED hits historyQuality only) before the VALIDATED displayed score falls below 8.0.  -1 if it is already below 8.0."""
    fl = list(lakes_for(n, lakes))
    base = score_variant(fl, level, VARIANTS[variant], "VALIDATED")
    if base["value"] < TARGET_OVERALL:
        return -1
    k = 0
    for i, l in enumerate(fl):
        if l.history_class == "SUFFICIENT" and not l.pilot:
            fl[i] = dataclasses.replace(l, history_class=to)
            k += 1
            if score_variant(fl, level, VARIANTS[variant], "VALIDATED")["value"] < TARGET_OVERALL:
                return k - 1
    return k


def first_reaching_n(pool: list[Lake], variant: str, level: str = "NOW", validation: str = "VALIDATED", lo: int = 5) -> int | None:
    """Smallest nested fleet size (first n lakes of `pool`) whose displayed score reaches 8.0."""
    for n in range(lo, len(pool) + 1):
        if score_variant(pool[:n], level, VARIANTS[variant], validation)["value"] >= TARGET_OVERALL:
            return n
    return None


def headroom(lakes: list[Lake], level: str, variant: str, n: int) -> dict:
    """Weighted points (of 100) each non-critical dimension could still add if it were 10.0, against the gap to 8.0, at VALIDATED."""
    fl = lakes_for(n, lakes)
    sc = score_variant(fl, level, VARIANTS[variant], "VALIDATED")
    v = values(sc)
    gap = round(TARGET_OVERALL * 100 - sc["unroundedUncapped"] * 100, 2)
    room = {k: round((10.0 - (v[k] or 0)) * WEIGHTS[k], 2) for k in ("operatorPlan", "floodDroughtContext", "coverage")}
    return {"gapPoints": gap, "room": room, "closedBy": [k for k, r in room.items() if r >= gap]}


def order_sensitivity(lakes: list[Lake], variant_names: list[str], sizes=(63, 123), seeds: int = 200, level: str = "NOW") -> dict:
    out = {}
    for n in sizes:
        for name in variant_names:
            vals = collections.defaultdict(list)
            for seed in range(seeds):
                fl = fleet(lakes, n, hash_order(lakes, seed))
                sc = score_variant(fl, level, VARIANTS[name], "VALIDATED")
                v = values(sc)
                vals["operatorPlan"].append(v["operatorPlan"])
                vals["floodDroughtContext"].append(v["floodDroughtContext"])
                vals["uncapped"].append(sc["uncapped"])
            out[f"{n}|{name}"] = {k: (min(x), round(statistics.median(x), 2), max(x)) for k, x in vals.items()}
    return out


P2WH = dataclasses.replace(P2W, withhold_historical=True)


def families_scenarios() -> list[dict]:
    """Claim-family states (hypothetical after S0) and the rule that applies.  Family states are inputs, not predictions of dates."""
    N, P, V = "NOT_VALIDATED", "PARTIAL", "VALIDATED"
    return [
        {"name": "S0 today: nothing recorded", "families": {"providerDisplay": N, "deterministicDerivation": N, "historicalState": N, "rapidChange": N}, "rules": P2},
        {"name": "S1 binding accepted; Level 1/2 PARTIAL; historicalState and RAPID not yet", "families": {"providerDisplay": P, "deterministicDerivation": P, "historicalState": N, "rapidChange": N}, "rules": P2},
        {"name": "S2 + ledger 90 d: historicalState PARTIAL; RAPID (H-C failed) still published", "families": {"providerDisplay": P, "deterministicDerivation": P, "historicalState": P, "rapidChange": N}, "rules": P2},
        {"name": "S3 as S2 with RAPID withheld", "families": {"providerDisplay": P, "deterministicDerivation": P, "historicalState": P, "rapidChange": N}, "rules": P2W},
        {"name": "S4 Level 1/2 VALIDATED, historicalState PARTIAL, RAPID withheld", "families": {"providerDisplay": V, "deterministicDerivation": V, "historicalState": P, "rapidChange": N}, "rules": P2W},
        {"name": "S5 all counted families VALIDATED, RAPID withheld", "families": {"providerDisplay": V, "deterministicDerivation": V, "historicalState": V, "rapidChange": N}, "rules": P2W},
        {"name": "S6 OUT OF SCOPE: Level 1/2 VALIDATED, historicalState AND RAPID withheld", "families": {"providerDisplay": V, "deterministicDerivation": V, "historicalState": N, "rapidChange": N}, "rules": P2WH},
    ]


def claims_effect(lakes: list[Lake], n: int = 196, level: str = "NOW") -> list[dict]:
    fl = lakes_for(n, lakes)
    out = []
    for s in families_scenarios():
        rules = s["rules"]
        sc = score_variant(fl, level, rules, s["families"])
        mean_sc = score_variant(fl, level, dataclasses.replace(rules, claims_agg="mean"), s["families"])
        out.append({"scenario": s["name"], "families": claims_state(s["families"], rules), "validationDim": values(sc)["validation"],
                    "uncapped": sc["uncapped"], "displayed": sc["value"], "gates": [g["gate"] for g in sc["scoreBlockers"] if "cap" in g],
                    "meanDim": values(mean_sc)["validation"], "meanDisplayed": mean_sc["value"]})
    return out


def md(rows: list[list], head: list[str]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _cell(a, b):
    return f"{fmt(a)} -> {fmt(b)}"


def table_classification(lakes: list[Lake]) -> str:
    rows = []
    for n in (5, 63, 123, 196, 427):
        c = classification_counts(lakes_for(n, lakes), "NOW")
        f, p = c["flood"], c["plan"]
        rows.append([n, f.get("DOCUMENTED", 0), f.get("EXISTS_UNPUBLISHED", 0), f.get("NOT_APPLICABLE", 0), f.get("UNDETERMINED", 0),
                     p.get("CAPTURED", 0), p.get("PUBLISHED_NOT_CAPTURED", 0), p.get("OPERATOR_READ_NO_PLAN", 0), p.get("UNKNOWN", 0)])
    return md(rows, ["fleet", "flood DOCUMENTED", "EXISTS_UNPUBLISHED", "NOT_APPLICABLE", "UNDETERMINED", "plan CAPTURED", "PUBLISHED_NOT_CAPTURED", "OPERATOR_READ_NO_PLAN", "UNKNOWN"])


def table_effect(lakes: list[Lake], proposed: list[str], dim_keys: list[str], level: str = "NOW") -> str:
    rows = []
    for n in FLEETS:
        fl = lakes_for(n, lakes)
        for name in proposed:
            cells = [n, name]
            cur = {st: score_variant(fl, level, CURRENT, st) for st in VMAP}
            new = {st: score_variant(fl, level, VARIANTS[name], st) for st in VMAP}
            cells.append("; ".join(f"{k}: {_cell(values(cur['NOT_VALIDATED'])[k], values(new['NOT_VALIDATED'])[k])}" for k in dim_keys))
            for st in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
                cells.append(f"{fmt(cur[st]['uncapped'])} -> {fmt(new[st]['uncapped'])} / {fmt(cur[st]['value'])} -> {fmt(new[st]['value'])}")
            rows.append(cells)
    return md(rows, ["fleet", "proposal", "dimension (current -> proposed)", "NOT_VALIDATED: uncapped / displayed", "PARTIAL (hypothetical): uncapped / displayed",
                     "VALIDATED (hypothetical): uncapped / displayed"])


def earliest(fleet_first_ledger_day: dt.date) -> dict:
    """Earliest dates for the ledger-based evidence of a fleet whose first ledger day is given (docs/brains/LAKE_BRAIN_VALIDATION_READINESS.md section 6):
    pooled PARTIAL evidence at +90 d, VALIDATED at +365 d.  With the pilots only (day 0 = 2026-10-13) that is 2027-01-11 and 2027-10-13."""
    return {"partial": fleet_first_ledger_day + dt.timedelta(days=90), "validated": fleet_first_ledger_day + dt.timedelta(days=365)}


def table_claims(lakes: list[Lake], n: int = 196, level: str = "NOW") -> str:
    rows = []
    for r in claims_effect(lakes, n, level):
        f = r["families"]
        rows.append([r["scenario"], "/".join({"NOT_VALIDATED": "0", "PARTIAL": "5", "VALIDATED": "10", "WITHHELD": "W"}[f[k]] for k in FAMILIES),
                     fmt(r["validationDim"]), fmt(r["uncapped"]), fmt(r["displayed"]), ", ".join(r["gates"]) or "none", fmt(r["meanDim"]), fmt(r["meanDisplayed"])])
    return md(rows, ["claim-family state (hypothetical)", "families (display/derivation/historical/RAPID; W = withheld)", "validation dim (min)", "uncapped", "displayed", "gate fired",
                     "NOT PROPOSED: dim if averaged", "NOT PROPOSED: displayed if averaged"])


def table_claims_fleets(lakes: list[Lake], level: str = "NOW") -> str:
    scen = {s["name"][:2]: s for s in families_scenarios()}
    rows = []
    for n in FLEETS:
        fl = lakes_for(n, lakes)
        cells = [n]
        for k in ("S0", "S2", "S3", "S5"):
            s = scen[k]
            sc = score_variant(fl, level, s["rules"], s["families"])
            cells.append(f"{fmt(sc['uncapped'])} / {fmt(sc['value'])}")
        rows.append(cells)
    return md(rows, ["fleet", "S0 today", "S2 RAPID published, H-C failed", "S3 RAPID withheld, all PARTIAL", "S5 RAPID withheld, all VALIDATED"])


def table_max(lakes: list[Lake], n: int, level: str, validation: str = "VALIDATED") -> str:
    rows = []
    for name in ("CURRENT", "P1-X", "P1-C", "P2+withhold-RAPID", "P3-X", "P3-C", "ALL (X)", "ALL (C)"):
        m = max_achievable(lakes, name, n, level, validation)
        d = m["dims"]
        rows.append([name, fmt(d["sourceAuthority"]), fmt(d["historyQuality"]), fmt(d["seasonalBaseline"]), fmt(d["trendQuality"]), fmt(d["validation"]), fmt(d["operatorPlan"]),
                     fmt(d["floodDroughtContext"]), fmt(d["coverage"]), f"{m['uncapped']:.1f} ({m['unrounded']:.3f})", fmt(m["displayed"]),
                     ("YES" if m["target"] else "no") + (" (rounding)" if (m["overallOk"] and m["unrounded"] < TARGET_OVERALL) else "")])
    return md(rows, ["rubric", "sourceAuth", "history", "baseline", "trend", "validation", "plan", "flood", "coverage", "uncapped (unrounded)", "displayed", "overall>=8.0 and critical>=7.5"])


def table_first_n(lakes: list[Lake]) -> str:
    pool = lakes_for(196, lakes)
    rows = []
    for name in ("CURRENT", "P1-X", "P1-C", "P3-X", "P3-C", "ALL (X)", "ALL (C)"):
        res = {}
        for lev in ("NOW", "KNOWN"):
            res[lev] = first_reaching_n(pool, name, lev)
        hs = []
        for seed in range(60):
            hs.append(first_reaching_n(hash_order(lakes, seed), name, "NOW"))
        hs_ok = [h for h in hs if h is not None]
        rows.append([name, res["NOW"], res["KNOWN"], f"{min(hs_ok)} / {int(statistics.median(hs_ok))} / {max(hs_ok)}" if hs_ok else "never", f"{len(hs_ok)}/60"])
    return md(rows, ["rubric", "first fleet size >= 8.0, rollout order, documented evidence", "same, with TWDB tier-2 adopted", "random orders (60): min / median / max", "orders that ever reach 8.0"])


def table_order_sensitivity(lakes: list[Lake]) -> str:
    sens = order_sensitivity(lakes, ["CURRENT", "P1-X", "P3-X", "P3-C", "ALL (X)", "ALL (C)"], seeds=100)
    rows = []
    for key, v in sens.items():
        n, name = key.split("|")
        rows.append([n, name, "{} / {} / {}".format(*v["operatorPlan"]), "{} / {} / {}".format(*v["floodDroughtContext"]), "{} / {} / {}".format(*v["uncapped"])])
    return md(rows, ["fleet", "rubric", "operatorPlan min/med/max", "floodDroughtContext min/med/max", "uncapped at VALIDATED min/med/max"])


def table_margin(lakes: list[Lake]) -> str:
    rows = []
    for name in ("CURRENT", "P1-X", "P3-X", "ALL (X)", "ALL (C)"):
        rows.append([name, history_margin(lakes, name, "NOW", 196, "NONE"), history_margin(lakes, name, "NOW", 196, "LIMITED"), history_margin(lakes, name, "KNOWN", 196, "NONE"),
                     f"{score_variant(lakes_for(196, lakes), 'NOW', VARIANTS[name], 'VALIDATED')['unroundedUncapped']:.3f}"])
    return md(rows, ["rubric (196 lakes, VALIDATED)", "SUFFICIENT lakes that may drop to NONE before displayed < 8.0 (documented evidence)", "... drop to LIMITED", "... drop to NONE (TWDB adopted)", "unrounded uncapped (documented)"])


def table_headroom(lakes: list[Lake]) -> str:
    rows = []
    for n, lev in ((63, "NOW"), (63, "KNOWN"), (123, "NOW"), (196, "NOW")):
        h = headroom(lakes, lev, "CURRENT", n)
        rows.append([n, lev, h["gapPoints"], h["room"]["operatorPlan"], h["room"]["floodDroughtContext"], h["room"]["coverage"], ", ".join(h["closedBy"]) or "none alone"])
    return md(rows, ["fleet", "evidence", "gap to 8.0 (weighted points of 100)", "room in operatorPlan", "room in floodDroughtContext", "room in coverage", "dimension that closes the gap alone"])


def table_dims(lakes: list[Lake]) -> str:
    rows = []
    for n in FLEETS:
        fl = lakes_for(n, lakes)
        sc = {st: score_variant(fl, "NOW", CURRENT, st) for st in VMAP}
        v = values(sc["VALIDATED"])
        rows.append([n, f"{n / DIRECTORY:.1%}", fmt(v["sourceAuthority"]), fmt(v["operatorPlan"]), fmt(v["historyQuality"]), fmt(v["seasonalBaseline"]), fmt(v["trendQuality"]),
                     fmt(v["floodDroughtContext"]), fmt(v["coverage"]),
                     *[f"{fmt(sc[st]['uncapped'])} / {fmt(sc[st]['value'])}" for st in VMAP]])
    return md(rows, ["fleet", "profiled", "sourceAuth", "plan", "history", "baseline", "trend", "flood", "coverage", "NOT_VALIDATED unc / disp", "PARTIAL (hyp.) unc / disp", "VALIDATED (hyp.) unc / disp"])


def table_mean_stack(lakes: list[Lake]) -> str:
    """NOT PROPOSED. Shows what stacking an averaged validation dimension on the denominator proposals would do at claim state S4 (Level 1/2 VALIDATED, historicalState only PARTIAL)."""
    s4 = [s for s in families_scenarios() if s["name"].startswith("S4")][0]
    rows = []
    for label, rules in (("P2 (min), proposed", P2W), ("P2 averaged", dataclasses.replace(P2W, claims_agg="mean")),
                         ("ALL (X) averaged", dataclasses.replace(COMBINED_X, claims_agg="mean")), ("ALL (C) averaged", dataclasses.replace(COMBINED_C, claims_agg="mean"))):
        for n in (196, 427):
            sc = score_variant(lakes_for(n, lakes), "NOW", rules, s4["families"])
            rep = critical_report(sc)
            rows.append([label, n, fmt(values(sc)["validation"]), fmt(sc["uncapped"]), fmt(sc["value"]), "yes" if rep["criticalOk"] else "no", "YES" if rep["target"] else "no"])
    return md(rows, ["validation rule", "fleet", "validation dim", "uncapped", "displayed", "all critical >= 7.5", "target met on documented evidence"])


def render_tables() -> dict:
    lakes = all_lakes()
    return {
        "dims": table_dims(lakes),
        "mean_stack": table_mean_stack(lakes),
        "classification": table_classification(lakes),
        "p1": table_effect(lakes, ["P1-X", "P1-C"], ["floodDroughtContext"]),
        "p3": table_effect(lakes, ["P3-X", "P3-C"], ["operatorPlan"]),
        "combined": table_effect(lakes, ["ALL (X)", "ALL (C)"], ["operatorPlan", "floodDroughtContext"]),
        "claims196": table_claims(lakes, 196),
        "claims_fleets": table_claims_fleets(lakes),
        **{f"max_{n}_{lev}": table_max(lakes, n, lev) for n in (63, 196, 427) for lev in ("KNOWN", "CEILING")},
        **{f"maxPA_{n}_{lev}": table_max(lakes, n, lev, "PARTIAL") for n in (63, 196, 427) for lev in ("KNOWN", "CEILING")},
        "first_n": table_first_n(lakes),
        "order": table_order_sensitivity(lakes),
        "margin": table_margin(lakes),
        "headroom": table_headroom(lakes),
    }


def summary() -> dict:
    lakes = all_lakes()
    out = {"lakes": len(lakes), "in196": sum(l.in196 for l in lakes),
           "classification": {n: classification_counts(lakes_for(n, lakes)) for n in (5, 63, 123, 196, 427)},
           "today": {st: {"displayed": s["value"], "uncapped": s["uncapped"]} for st in VMAP for s in [score_variant(lakes_for(5, lakes), "NOW", CURRENT, st)]},
           "effect": {name: {n: {st: {"uncapped": s["uncapped"], "displayed": s["value"], "dims": values(s)} for st in VMAP for s in [score_variant(lakes_for(n, lakes), "NOW", rules, st)]}
                             for n in FLEETS} for name, rules in VARIANTS.items()},
           "claims": claims_effect(lakes)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--tables", action="store_true", help="print the markdown tables used in the proposals document")
    ap.add_argument("--write-drafts", action="store_true")
    ap.add_argument("--build-facts", nargs=5, metavar=("BINDINGS", "EV_CSV", "V2_CSV", "NID_LINKS_CSV", "ROLLOUT_PLAN"))
    a = ap.parse_args()
    if a.build_facts:
        print(build_facts(*a.build_facts), "rows written to", FACTS_CSV)
    if a.write_drafts:
        print("\n".join(write_drafts()))
    if a.tables:
        for k, v in render_tables().items():
            print(f"\n### {k}\n\n{v}")
    if a.summary or not (a.write_drafts or a.build_facts or a.tables):
        print(json.dumps(summary(), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
