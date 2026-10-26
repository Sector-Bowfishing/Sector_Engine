"""Fish Biological Capability evaluation (Layer 3, Learning & Validation): what can Fish DEMONSTRABLY do with its biology, species by species?

This module EXECUTES the real Fish runtime (bio_state -> movement_outlook -> biological_assessment) on deterministic scenarios and records, per
species and per rubric criterion, what passed, what failed, and why. It emits an EVIDENCE artifact (`fish-biological-capability-evidence-v2`)
and deliberately computes NO points: weights, species scores and aggregates belong to the shared platform scorer
(jobs/brain_platform/sector_brain_platform/fish_capability.py, rubric docs/brains/scoring/fish-biological-capability-v2.json).

Principles (FISH_BIOLOGICAL_CAPABILITY_V2.md):
  * Credit comes only from executed runtime behaviour. Profile text, knowledge scores, evidence volume and registry bookkeeping earn nothing here.
  * Only usable (RECONCILED/APPROVED, evidence-checked) rules can execute; DRAFT rules and season-gated rules are reported as unused knowledge.
  * Scenarios are SYNTHETIC: a pass is SCENARIO_BEHAVIOR_PASSED, never FIELD_VALIDATED_ACCURACY.
  * Species are evaluated on biology, not lake presence: every rostered species is evaluated as if present (Lake Brain still owns presence).
  * Abstention credit (correct UNKNOWN) is only available to a species that has executable knowledge somewhere: universal UNKNOWN earns nothing.
  * Expectations that depend on the literature come from HUMAN-REVIEWED reference cases. Unreviewed (PROPOSED) cases are run and reported but never
    move credit; an APPROVED case that fails withdraws the credit of the criterion it checks.
  * A species whose evaluation throws is EVALUATION_FAILED (never a silent zero); NOT_ASSESSED species are never evaluated or scored.
Pure and deterministic (no clock unless `evaluated_at` is omitted, no network, no LLM). stdlib only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import traceback

import bio_state as bs
import biological_assessment as ba
import features as ft
import movement_outlook as mo
import rules as rl
import target_set as ts

EVALUATOR_VERSION = "fish-capability-evaluator-2.1.0"
EVIDENCE_SCHEMA = "fish-biological-capability-evidence-v2"
RUBRIC_ID = "FISH_BIOLOGICAL_CAPABILITY_V2"
EVALUATION_STATUS = ("ASSESSED", "NOT_ASSESSED", "INSUFFICIENT_EVIDENCE", "EVALUATION_FAILED")
RESULTS = ("PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE")
BLOCKERS = ("MISSING_KNOWLEDGE", "THIN_KNOWLEDGE", "KNOWLEDGE_NOT_IN_RUNTIME", "REVIEW_BLOCKED", "CONTRADICTORY_EVIDENCE",
            "NEEDS_FIELD_OBSERVATIONS", "RUNTIME_DEFECT", "POLICY_BLOCKED", "DEPENDS_ON_EXECUTABLE_KNOWLEDGE")
OUTCOME_KIND = "SCENARIO_BEHAVIOR_PASSED"
SPAWN_KNOWN = ("IN_WINDOW", "MONTH_ONLY", "TEMP_ONLY", "OUTSIDE")          # never FIELD_VALIDATED_ACCURACY: scenarios are synthetic

# Evaluation frame: Sector's product region (Southeast, Tennessee-River run-of-river reservoirs). OUT_REGION tests regional applicability.
FRAME = {"region": "south", "waterbodyType": "run_of_river"}
OUT_REGION = "west"
# Synthetic SCENARIO climatology (deg F, mid-month): a plausible Southeast reservoir annual cycle used ONLY to drive scenarios. Not data, not a claim.
CLIMATOLOGY_F = {1: 47.0, 2: 49.0, 3: 55.0, 4: 64.0, 5: 72.0, 6: 80.0, 7: 84.0, 8: 85.0, 9: 80.0, 10: 71.0, 11: 60.0, 12: 51.0}
BAND_PROBE_F = {"LT_10C": 45.0, "C10_15": 54.0, "C15_18": 61.0, "C18_21": 66.0, "C21_26": 74.0, "C26_30": 82.0, "GE_30C": 90.0}
CLARITY_PROBE_FT = {"TURBID": 1.0, "MODERATE": 2.0, "CLEAR": 4.0}
SEASON_OF = bs.SEASONS
# Biology is evaluated independently of lake presence: every rostered species is treated as relevant (first state of the runtime's relevance policy).
# This is an evaluation device, not a presence claim about any lake (Lake Brain owns presence).
EVALUATION_PRESENCE = bs.DEFAULT_RELEVANT_PRESENCE[0]

TEMPERATURE = frozenset({"waterTempBand", "temperatureTrend", "temperatureCrossing15C", "temperatureCrossing18C", "temperatureCrossing20C"})
HYDROLOGY = frozenset({"stageTrend", "risingStage", "fallingStage", "warmRise", "coldRise", "rapidDischargeIncrease"})
CLARITY = frozenset({"clarityBand"})
DAYPART = frozenset({"daypart"})
ENVIRONMENTAL = TEMPERATURE | HYDROLOGY | CLARITY
FAMILIES = ("TEMPERATURE", "HYDROLOGY", "CLARITY", "DAYPART", "HABITAT", "DEPTH", "PHENOLOGY")
# Behaviour dimensions every freshwater fish has (it lives through temperatures, water levels, habitats, a spawning season and day/night).
# Clarity is excluded: not every species has a documented clarity response, and forcing one would reward irrelevant biology.
CORE_BEHAVIOUR_FAMILIES = ("TEMPERATURE", "HYDROLOGY", "HABITAT", "PHENOLOGY", "DAYPART")
FAMILY_FEATURES = {"TEMPERATURE": TEMPERATURE, "HYDROLOGY": HYDROLOGY, "CLARITY": CLARITY, "DAYPART": DAYPART}

# criterion -> (rule families whose absence explains a miss, species-v2 knowledge domain used ONLY to label the blocker; never scored)
CRITERIA = {
    "BIO-1": (FAMILIES, None), "BIO-2": (FAMILIES, "aggregationMobilityLifeStage"), "BIO-3": (FAMILIES, None), "BIO-4": (FAMILIES, None),
    "BIO-5": (FAMILIES, "aggregationMobilityLifeStage"),
    "HAB-1": (("HABITAT",), "habitatDepthCover"), "HAB-2": (("HABITAT",), "habitatDepthCover"), "HAB-3": (("DEPTH",), "habitatDepthCover"),
    "HAB-4": (("DEPTH",), "habitatDepthCover"), "HAB-5": (("DEPTH",), "habitatDepthCover"),
    "ENV-1": (("TEMPERATURE",), "temperatureOxygen"), "ENV-2": (("HYDROLOGY",), "hydrologyRainInflowLevel"), "ENV-3": (("CLARITY",), "clarityLightWind"),
    "ENV-4": (("TEMPERATURE", "HYDROLOGY", "CLARITY"), None),
    "SPN-1": (("PHENOLOGY",), "seasonalLocationReproduction"), "SPN-2": (("PHENOLOGY",), "seasonalLocationReproduction"),
    "SPN-3": (FAMILIES, "seasonalLocationReproduction"), "SPN-4": (("PHENOLOGY",), "seasonalLocationReproduction"),
    "DN-1": (("DAYPART",), "dayNightMovement"), "DN-2": (("DAYPART",), "dayNightMovement"), "DN-3": (("DAYPART",), "dayNightMovement"),
    "APP-1": (FAMILIES, None),
}
ABSTENTION_CRITERIA = ("BIO-4", "HAB-5", "DN-3")          # earn credit only when the species has executable knowledge (BIO-1)
CRITERION_IDS = tuple(CRITERIA)
SUBSTANTIAL_KNOWLEDGE = 5          # species-v2 domain score at/above which knowledge is "recorded" (labels blockers only; never scored)


# ---------------------------------------------------------------- scenario construction
def inputs_for(temp_f=None, trend_f=None, stage=None, clarity_ft=None, discharge=None, status="PUBLISHED") -> dict:
    def slot(vals):
        vals = {k: v for k, v in vals.items() if v is not None}
        return {"status": status, "values": vals} if vals else {"status": "NOT_PUBLISHED"}
    wt = slot({"currentTempF": temp_f, "trend24hF": trend_f}) if temp_f is not None else {"status": "NOT_PUBLISHED"}
    return {"waterTemp": wt, "lake": slot({"trendState": stage, "tributaryDischargeTrend": discharge}),
            "waterClarity": slot({"clarityFt": clarity_ft})}


def c_to_f(c: float) -> float:
    return round(c * 9.0 / 5.0 + 32.0, 2)


def probe(feature: str, state: str) -> dict:
    """Scenario conditions that put `feature` into `state` (the inverse of features.evaluate_features). Raises KeyError for an unknown pair."""
    if feature == "waterTempBand":
        return {"temp_f": BAND_PROBE_F[state]}
    if feature == "temperatureTrend":
        return {"temp_f": 66.0, "trend_f": {"WARMING": 3.0, "COOLING": -3.0, "STEADY": 0.0}[state]}
    if feature.startswith("temperatureCrossing"):
        t = float(feature[len("temperatureCrossing"):-1])
        return {"UP_24H": {"temp_f": c_to_f(t + 0.5), "trend_f": 2.0}, "DOWN_24H": {"temp_f": c_to_f(t - 0.5), "trend_f": -2.0},
                "NONE_24H": {"temp_f": c_to_f(t + 3.0), "trend_f": 0.0}}[state]
    if feature == "stageTrend":
        return {"stage": state}
    if feature == "risingStage":
        return {"stage": "RISING" if state == "TRUE" else "STABLE"}
    if feature == "fallingStage":
        return {"stage": "FALLING" if state == "TRUE" else "STABLE"}
    if feature == "warmRise":
        return {"stage": "RISING" if state == "TRUE" else "STABLE", "temp_f": 68.0}
    if feature == "coldRise":
        return {"stage": "RISING" if state == "TRUE" else "STABLE", "temp_f": 50.0}
    if feature == "rapidDischargeIncrease":
        return {"discharge": "RISING_RAPIDLY" if state == "TRUE" else "STABLE"}
    if feature == "clarityBand":
        return {"clarity_ft": CLARITY_PROBE_FT[state]}
    if feature == "daypart":
        return {"daypart": state}
    raise KeyError(f"no probe for {feature}={state}")


def contrast_state(feature: str, states) -> str | None:
    for s in ft.REGISTRY[feature]["states"]:
        if s not in states:
            return s
    return None


def family_of(rule: dict) -> set:
    k = rule["kind"]
    if k == "PHENOLOGY":
        return {"PHENOLOGY"}
    if k == "HABITAT":
        h = rule.get("habitat") or {}
        return {"HABITAT"} | ({"DEPTH"} if h.get("depthClass") or h.get("habitatClass") in ba.DEEP_HABITATS else set())
    f = (rule.get("feature") or {}).get("featureId")
    return {fam for fam, feats in FAMILY_FEATURES.items() if f in feats}


def _cond_key(c: dict) -> tuple:
    return tuple(sorted((k, v) for k, v in c.items()))


class Harness:
    """Runs the REAL Fish runtime for a roster of species under scenario conditions (cached per condition set)."""

    def __init__(self, ruleset: rl.RuleSet, species_info: dict, species: list[str], knowledge_version: str):
        self.ruleset, self.species_info, self.species, self.kv = ruleset, species_info, list(species), knowledge_version
        self.presence = {s: {"presenceState": EVALUATION_PRESENCE, "confidence": "evaluation"} for s in self.species}
        self._cache: dict[tuple, dict] = {}
        self.scenarios_run = 0

    def state(self, month: int, daypart: str | None = None, region: str = FRAME["region"], status: str = "PUBLISHED", **cond) -> dict:
        key = (month, daypart, region, status, _cond_key(cond))
        if key not in self._cache:
            now = dt.datetime(2026, month, 15, 12, 0, tzinfo=dt.timezone.utc)
            self._cache[key] = bs.build_lake_state("CAPABILITY-EVALUATION", region=region, waterbody_type=FRAME["waterbodyType"], now=now,
                                                   inputs=inputs_for(status=status, **cond), daypart=daypart, presence=self.presence,
                                                   ruleset=self.ruleset, species_info=self.species_info)
            self.scenarios_run += 1
        return self._cache[key]

    def sp(self, sid: str, month: int, **kw) -> dict:
        return next(x for x in self.state(month, **kw)["species"] if x["speciesId"] == sid)

    def outlook(self, sid: str, month: int, **kw) -> dict:
        return mo.species_outlook(self.sp(sid, month, **kw), month)

    def assessment(self, sid: str, month: int, supplied_depth: dict | None = None, **kw) -> dict:
        st = self.state(month, **kw)
        a = ba.build_assessments(st, self.ruleset, knowledge_version=self.kv, evaluation_version=EVALUATOR_VERSION, supplied_depth=supplied_depth, species=[sid])
        return a


def scenario(month: int, **cond) -> dict:
    return {"month": month, **{k: v for k, v in cond.items() if v is not None}}


def _band(sp: dict, feature: str) -> dict | None:
    return next((r for r in sp.get("responses") or [] if r["featureId"] == feature), None)


DIRECTION = {"FAVORABLE": ("FAVORABLE_SHALLOW", "MIXED"), "WORKABLE": ("WORKABLE", "FAVORABLE_SHALLOW", "MIXED"), "LIMITING": ("LIMITING", "MIXED"),
             "BLOCKING": ("LIMITING", "MIXED")}


def _first_month(rule: dict, default: int = 7) -> int:
    months = (rule.get("applicability") or {}).get("months")
    return sorted(months)[0] if months else default


def test_response_rule(h: Harness, sid: str, rule: dict) -> dict:
    """Does an evidence-backed RESPONSE rule execute under its own condition, stop under a contrasting condition, and push the outlook its way?"""
    f, states = rule["feature"]["featureId"], rule["feature"]["states"]
    m = _first_month(rule)
    cond = probe(f, states[0])
    sp = h.sp(sid, m, **cond)
    band = _band(sp, f)
    fired = bool(band) and band["response"] == rule["response"] and rule["ruleId"] in (band.get("evidenceBasis") or {}).get("ruleIds", [])
    conflict = bool(band) and bool(band.get("conflict"))
    out = {"ruleId": rule["ruleId"], "family": sorted(family_of(rule)), "feature": f, "response": rule["response"], "behavior": rule.get("behavior"),
           "scenario": scenario(m, **cond), "observedBand": (band or {}).get("response"), "fired": fired, "conflict": conflict}
    if not fired:
        return out | {"contrastChanges": False, "directionConsistent": False, "reasonPresent": False}
    cs = contrast_state(f, states)
    if cs is not None:
        ccond = probe(f, cs)
        cb = _band(h.sp(sid, m, **ccond), f)
        out["contrastScenario"] = scenario(m, **ccond)
        out["contrastChanges"] = not (cb and cb["response"] == rule["response"] and rule["ruleId"] in (cb.get("evidenceBasis") or {}).get("ruleIds", []))
    else:
        out["contrastChanges"] = False
    o = mo.species_outlook(sp, m)
    if f in mo.ACTIVITY_FEATURES:
        want = {"FAVORABLE": ("ACTIVITY_UP", "MIXED"), "WORKABLE": ("ACTIVITY_UP", "MIXED"), "LIMITING": ("ACTIVITY_DOWN", "MIXED"), "BLOCKING": ("ACTIVITY_DOWN", "MIXED")}
        out["directionConsistent"] = o["activity"] in want[rule["response"]]
    else:
        out["directionConsistent"] = o["state"] in DIRECTION[rule["response"]]
    out["observedOutlook"] = {"state": o["state"], "movement": o["movement"], "activity": o["activity"]}
    out["reasonPresent"] = bool(o.get("why"))
    return out


def test_habitat_rule(h: Harness, sid: str, rule: dict) -> dict:
    m = _first_month(rule)
    cond: dict = {}
    for rq in rule.get("requires") or []:
        cond |= probe(rq["featureId"], rq["states"][0])
    sp = h.sp(sid, m, **cond)
    row = next((x for x in sp.get("habitat") or [] if x.get("ruleId") == rule["ruleId"]), None)
    fired = bool(row) and row.get("state") == "ACTIVE"
    out = {"ruleId": rule["ruleId"], "family": sorted(family_of(rule)), "habitatClass": rule["habitat"]["habitatClass"], "direction": rule["habitat"]["direction"],
           "depthClass": rule["habitat"].get("depthClass"), "behavior": rule.get("behavior"), "scenario": scenario(m, **cond), "fired": fired,
           "conflict": bool(row and row.get("conflict"))}
    changes = []
    if fired and rule.get("requires"):
        rq = rule["requires"][0]
        cs = contrast_state(rq["featureId"], rq["states"])
        if cs is not None:
            ccond = dict(cond) | probe(rq["featureId"], cs)
            crow = next((x for x in h.sp(sid, m, **ccond).get("habitat") or [] if x.get("ruleId") == rule["ruleId"]), None)
            changes.append({"kind": "condition", "scenario": scenario(m, **ccond), "changes": not (crow and crow.get("state") == "ACTIVE")})
    months = (rule.get("applicability") or {}).get("months")
    if fired and months:
        off = next((x for x in range(1, 13) if x not in months), None)
        if off:
            crow = next((x for x in h.sp(sid, off, **cond).get("habitat") or [] if x.get("ruleId") == rule["ruleId"]), None)
            changes.append({"kind": "season", "scenario": scenario(off, **cond), "changes": crow is None})
    out["contrasts"] = changes
    out["conditional"] = any(c["changes"] for c in changes)
    return out


def test_phenology(h: Harness, sid: str, rule: dict) -> dict:
    months = (rule.get("applicability") or {}).get("months") or []
    tr = rule["phenology"]["tempC"]
    mid_f = c_to_f((tr["min"] + tr["max"]) / 2.0)
    below_f = c_to_f(tr["min"] - 3.0)
    m_in = sorted(months)[0] if months else 6
    m_out = next((x for x in range(1, 13) if x not in months), None) if months else None
    get = lambda month, tf, region=FRAME["region"]: h.sp(sid, month, temp_f=tf, region=region).get("spawnWindow") or {}   # noqa: E731
    res = {"ruleId": rule["ruleId"], "family": ["PHENOLOGY"], "windowMonths": months, "tempC": tr, "regions": (rule.get("applicability") or {}).get("regions", ["any"])}
    inw = get(m_in, mid_f)
    res["inWindow"] = {"scenario": scenario(m_in, temp_f=mid_f), "state": inw.get("state"), "ok": inw.get("state") == "IN_WINDOW",
                       "carriesConfidence": bool(inw.get("confidence")) and bool(inw.get("transferability")), "confidence": inw.get("confidence")}
    mo_ = get(m_in, below_f)
    res["monthOnly"] = {"scenario": scenario(m_in, temp_f=below_f), "state": mo_.get("state"), "ok": mo_.get("state") == "MONTH_ONLY"}
    if m_out:
        out_ = get(m_out, below_f)
        to_ = get(m_out, mid_f)
        res["outside"] = {"scenario": scenario(m_out, temp_f=below_f), "state": out_.get("state"), "ok": out_.get("state") == "OUTSIDE"}
        res["tempOnly"] = {"scenario": scenario(m_out, temp_f=mid_f), "state": to_.get("state"), "ok": to_.get("state") == "TEMP_ONLY"}
    regions = res["regions"]
    if "any" not in regions and OUT_REGION not in regions:
        rw = get(m_in, mid_f, OUT_REGION)
        res["outOfRegion"] = {"region": OUT_REGION, "state": rw.get("state"), "ok": rw.get("state") == "UNKNOWN"}
    return res


# ---------------------------------------------------------------- grids
def standard_grid() -> list[dict]:
    g = []
    for m in range(1, 13):
        t = CLIMATOLOGY_F[m]
        g += [dict(month=m, daypart="DAY", temp_f=t, trend_f=0.0, stage="STABLE", clarity_ft=2.0),
              dict(month=m, daypart="NIGHT", temp_f=t, trend_f=0.0, stage="STABLE", clarity_ft=2.0),
              dict(month=m, daypart="DAY", temp_f=t, trend_f=1.5, stage="RISING", clarity_ft=2.0),
              dict(month=m, daypart="DAY", temp_f=t, trend_f=-1.5, stage="FALLING", clarity_ft=1.0)]
    return g


def _sig(o: dict, sp: dict) -> tuple:
    return (o["state"], o["movement"], o["activity"], tuple(o.get("where") or []), (sp.get("spawnWindow") or {}).get("state"))


def grid_signatures(h: Harness, species: list[str]) -> dict:
    out = {s: [] for s in species}
    for c in standard_grid():
        c = dict(c)
        m = c.pop("month")
        st = h.state(m, **c)
        for sp in st["species"]:
            if sp["speciesId"] in out:
                out[sp["speciesId"]].append(_sig(mo.species_outlook(sp, m), sp))
    return out


COVERAGE_FAMILIES = ("TEMPERATURE", "HYDROLOGY", "CLARITY", "DAYPART", "HABITAT")


def coverage_probes() -> list[dict]:
    """Every registered condition state of every evaluable lake-level feature, as scenario conditions (deduplicated), plus no input."""
    seen, out = set(), [{}]
    for fam in ("TEMPERATURE", "HYDROLOGY", "CLARITY", "DAYPART"):
        for f in sorted(FAMILY_FEATURES[fam]):
            for st in ft.REGISTRY[f]["states"]:
                c = probe(f, st)
                k = _cond_key(c)
                if k not in seen:
                    seen.add(k)
                    out.append(c)
    return out


def annual_coverage(h: Harness, species: list[str]) -> dict:
    """{speciesId: {family: [months]}}: the months in which the RUNTIME produced at least one known, non-conflicting output of that family under
    some supplied condition state. Measured by execution over 12 months x every registered condition state, not read from rule metadata."""
    out = {s: {f: set() for f in COVERAGE_FAMILIES} for s in species}
    for m in range(1, 13):
        for c in coverage_probes():
            c = dict(c)
            dp = c.pop("daypart", None)
            for sp in h.state(m, daypart=dp, **c)["species"]:
                sid = sp["speciesId"]
                if sid not in out:
                    continue
                for r in sp.get("responses") or []:
                    if r["response"] != "UNKNOWN" and not r.get("conflict"):
                        for fam, feats in FAMILY_FEATURES.items():
                            if r["featureId"] in feats:
                                out[sid][fam].add(m)
                if any(x.get("state") == "ACTIVE" and not x.get("conflict") for x in sp.get("habitat") or []):
                    out[sid]["HABITAT"].add(m)
    return {s: {f: sorted(v) for f, v in d.items()} for s, d in out.items()}


# ---------------------------------------------------------------- knowledge context (labels blockers; never scored)
def knowledge_context(sid: str, profile: dict | None, ruleset: rl.RuleSet, movement_card: dict | None, discrepancies: list[dict]) -> dict:
    p = profile or {}
    dom = ((p.get("knowledge") or {}).get("domains")) or {}
    active = [r for r in ruleset.by_species.get(sid, []) if ruleset.is_active(r)]
    usable = ruleset.for_species(sid)
    gated = ruleset.season_gated(sid)
    drafts = [r for r in active if r["status"] == "DRAFT"]
    fam_count = lambda rs: {f: sum(f in family_of(r) for r in rs) for f in FAMILIES}      # noqa: E731
    cand = {f: 0 for f in FAMILIES}
    for c in (movement_card or {}).get("ruleCandidates") or []:
        fams = set()
        if c.get("kind") == "PHENOLOGY":
            fams.add("PHENOLOGY")
        for hint in c.get("featureHints") or []:
            if hint == "spawnWindow":
                fams.add("PHENOLOGY")
            elif hint in ft.HABITAT_CLASSES:
                fams.add("HABITAT")
                if hint in ba.DEEP_HABITATS:
                    fams.add("DEPTH")
            else:
                fams |= {fam for fam, feats in FAMILY_FEATURES.items() if hint in feats}
        for f in fams:
            cand[f] += 1
    contr_lists = [d.get("contradictions") for d in dom.values() if isinstance(d, dict)]
    contr = None if not contr_lists or all(c is None for c in contr_lists) else sum(len(c or []) for c in contr_lists)
    disc = [d["id"] for d in discrepancies if sid in (d.get("species") or []) and d.get("status") == "OPEN"]
    spawn_disc = [d["id"] for d in discrepancies if sid in (d.get("species") or []) and d.get("status") == "OPEN" and "spawn" in (d.get("title") or "").lower()]
    return {"role": ts.role(sid), "assessment": p.get("assessment"), "taxonomyStatus": p.get("taxonomyStatus"), "researchMaturity": p.get("researchMaturity"),
            "knowledgeScoreSpeciesV2": (p.get("knowledge") or {}).get("overallRounded"),
            "knowledgeDomains": {k: v.get("score") for k, v in dom.items() if isinstance(v, dict)},
            "rules": {"usable": len(usable), "executable": len(usable) - len(gated), "seasonGated": len(gated), "draft": len(drafts),
                      "approved": sum(r["status"] == "APPROVED" for r in usable)},
            "rulesByFamily": {"executable": fam_count([r for r in usable if r not in gated]), "seasonGated": fam_count(gated), "draft": fam_count(drafts),
                              "cardCandidates": cand},
            "transfer": {t: sum((r.get("transferability") or {}).get("southeastReservoir") == t for r in usable) for t in rl.TRANSFER},
            "contradictionsRecorded": contr, "openDiscrepancies": disc, "openSpawnDiscrepancies": spawn_disc,
            "doNotResearch": ts.DO_NOT_RESEARCH.get(sid)}


def classify_blocker(cid: str, kc: dict, detail: dict) -> dict:
    fams, domain = CRITERIA[cid]
    if detail.get("conflict"):
        return {"blocker": "CONTRADICTORY_EVIDENCE", "why": "the species' own evidence-backed rules disagree here; the runtime keeps it UNKNOWN"}
    if detail.get("runtimeDefect"):
        return {"blocker": "RUNTIME_DEFECT", "why": detail["runtimeDefect"]}
    if detail.get("needsField"):
        return {"blocker": "NEEDS_FIELD_OBSERVATIONS", "why": detail["needsField"]}
    if detail.get("dependsOnExecutable"):
        return {"blocker": "DEPENDS_ON_EXECUTABLE_KNOWLEDGE", "why": "abstention credit needs executable knowledge somewhere for this species"}
    by = kc["rulesByFamily"]
    gated = sum(by["seasonGated"].get(f, 0) for f in fams)
    drafts = sum(by["draft"].get(f, 0) for f in fams)
    cands = sum(by["cardCandidates"].get(f, 0) for f in fams)
    score = None
    if domain:
        score = kc["knowledgeDomains"].get(domain)
    else:
        score = kc.get("knowledgeScoreSpeciesV2")
    base = {"knowledgeDomain": domain, "knowledgeDomainScore": score, "seasonGatedRules": gated, "draftRules": drafts, "cardRuleCandidates": cands}
    if gated:
        return base | {"blocker": "REVIEW_BLOCKED", "why": f"{gated} usable rule(s) cannot fire until a reviewer bounds their season or asserts YEAR_ROUND"}
    if drafts or cands:
        return base | {"blocker": "KNOWLEDGE_NOT_IN_RUNTIME", "why": f"existing research is not executable: {drafts} draft rule(s), {cands} movement-card rule candidate(s)"}
    if isinstance(score, (int, float)) and score >= SUBSTANTIAL_KNOWLEDGE:
        return base | {"blocker": "KNOWLEDGE_NOT_IN_RUNTIME", "why": f"knowledge recorded (species-v2 {domain or 'overall'} {score}/10) but no executable rule"}
    if isinstance(score, (int, float)) and score > 0:
        return base | {"blocker": "THIN_KNOWLEDGE", "why": f"thin knowledge (species-v2 {domain or 'overall'} {score}/10) and no executable rule"}
    return base | {"blocker": "MISSING_KNOWLEDGE", "why": "no recorded knowledge and no executable rule"}


# ---------------------------------------------------------------- criteria
def _res(fraction: float, detail: dict, kc: dict | None = None, cid: str | None = None, applicable: bool = True) -> dict:
    if not applicable:
        return {"result": "NOT_APPLICABLE", "fraction": None, "detail": detail}
    fr = round(max(0.0, min(1.0, float(fraction))), 6)
    r = {"result": "PASS" if fr >= 1.0 else ("FAIL" if fr <= 0.0 else "PARTIAL"), "fraction": fr, "detail": detail, "outcomeKind": OUTCOME_KIND}
    if fr < 1.0 and kc is not None and cid is not None:
        r["blocker"] = classify_blocker(cid, kc, detail)
    return r


def _scaled(r: dict, factor: float, why: str, kc: dict, cid: str) -> dict:
    """Abstention/safety credit is proportional to how much executable knowledge it protects (rubric 2.1 abstentionPolicy)."""
    if r.get("result") == "NOT_APPLICABLE" or r.get("fraction") is None or factor >= 1.0:
        return r
    d = dict(r.get("detail") or {})
    d |= {"unscaledFraction": r["fraction"], "breadthScale": round(factor, 6), "scaleWhy": why}
    return _res(r["fraction"] * factor, d, kc, cid)


def _ladder(t: dict) -> float:
    """A RESPONSE rule test: fired + condition-sensitive + outlook direction = 1.0; fired + sensitive = 0.75; fired = 0.5; conflict surfaced = 0.25."""
    if t["fired"]:
        return 1.0 if (t["contrastChanges"] and t["directionConsistent"] and t["reasonPresent"]) else (0.75 if t["contrastChanges"] else 0.5)
    return 0.25 if t["conflict"] else 0.0


def _cov(coverage: dict, fam: str) -> float:
    return len(coverage.get(fam) or []) / 12.0


def evaluate_species(h: Harness, sid: str, kc: dict, signatures: dict, coverage: dict | None = None) -> dict:
    coverage = coverage or {}
    rs = h.ruleset
    ev = rs.evaluable(sid)
    resp_t = [test_response_rule(h, sid, r) for r in ev if r["kind"] == "RESPONSE"]
    hab_t = [test_habitat_rule(h, sid, r) for r in ev if r["kind"] == "HABITAT"]
    phen_rule = rl.phenology_window(ev, {"month": None, **FRAME})
    phen_t = test_phenology(h, sid, next(r for r in ev if r["ruleId"] == phen_rule["ruleId"])) if phen_rule else None
    crit: dict[str, dict] = {}

    # ---- Category 1: biology & behaviour
    executed = [t for t in resp_t if t["fired"]] + [t for t in hab_t if t["fired"]]
    phen_exec = bool(phen_t and phen_t["inWindow"]["ok"])
    exec_ok = any(t.get("observedOutlook", {}).get("state", "UNKNOWN") != "UNKNOWN" for t in resp_t if t["fired"]) or any(t["fired"] for t in hab_t) or phen_exec
    crit["BIO-1"] = _res(1.0 if exec_ok else 0.0, {"executedRules": sorted({t["ruleId"] for t in executed} | ({phen_t["ruleId"]} if phen_exec else set())),
                                                    "evaluableRules": len(ev)}, kc, "BIO-1")
    my = signatures.get(sid) or []
    distinct = {s[:4] for s in my if s[0] != "UNKNOWN"}
    fams = set()
    for t in executed:
        fams |= set(t["family"]) & set(CORE_BEHAVIOUR_FAMILIES)
    if phen_exec:
        fams.add("PHENOLOGY")
    crit["BIO-2"] = _res(len(fams) / len(CORE_BEHAVIOUR_FAMILIES), {"executedBehaviourFamilies": sorted(fams), "coreFamilies": list(CORE_BEHAVIOUR_FAMILIES),
                                                                  "distinctNonUnknownGridOutputs": len(distinct)}, kc, "BIO-2")
    known = any(s[0] != "UNKNOWN" or s[4] in SPAWN_KNOWN for s in my)
    twins = sorted(o for o, sg in signatures.items() if o != sid and sg == my)
    crit["BIO-3"] = _res((1.0 if not twins else 0.5) if known else 0.0, {"identicalSignatureSpecies": twins if known else [], "anyKnownOutput": known}, kc, "BIO-3")
    if exec_ok:
        checks = _uncertainty_checks(h, sid)
        crit["BIO-4"] = _res(sum(checks.values()) / len(checks), {"checks": checks} | ({"runtimeDefect": "uncertainty check failed: " + ", ".join(k for k, v in checks.items() if not v)} if not all(checks.values()) else {}), kc, "BIO-4")
    else:
        crit["BIO-4"] = _res(0.0, {"dependsOnExecutable": True}, kc, "BIO-4")
    breadth = len(fams) / len(CORE_BEHAVIOUR_FAMILIES)
    breadth_why = f"executable knowledge in {len(fams)} of {len(CORE_BEHAVIOUR_FAMILIES)} core behaviour families"
    crit["BIO-4"] = _scaled(crit["BIO-4"], breadth, breadth_why, kc, "BIO-4")
    tagged = [t for t in executed if t.get("behavior")]
    crit["BIO-5"] = _res(len(tagged) / len(executed) if executed else 0.0, {"executedRules": len(executed), "withBehaviorDescriptor": len(tagged)}, kc, "BIO-5")

    # ---- Category 2: habitat & depth
    hab_fired = [t for t in hab_t if t["fired"]]
    hx = 1.0 if hab_fired else (0.25 if any(t["conflict"] for t in hab_t) else 0.0)
    crit["HAB-1"] = _res(0.5 * hx + 0.5 * _cov(coverage, "HABITAT"),
                         {"execution": hx, "annualCoverageMonths": coverage.get("HABITAT", []),
                          "habitatRulesFired": [t["ruleId"] for t in hab_fired], "habitatClasses": sorted({t["habitatClass"] for t in hab_fired}),
                          "conflict": any(t["conflict"] for t in hab_t) and not hab_fired}, kc, "HAB-1")
    cond_h = [t for t in hab_fired if t["conditional"]]
    crit["HAB-2"] = _res(1.0 if cond_h else 0.0, {"conditionalHabitatRules": [t["ruleId"] for t in cond_h],
                                                   "contrasts": [c for t in hab_fired for c in t["contrasts"]]}, kc, "HAB-2")
    depth_fired = [t for t in hab_fired if t.get("depthClass")]
    deep_fired = [t for t in hab_fired if t["habitatClass"] in ba.DEEP_HABITATS]
    shallow_seen = any(t.get("observedOutlook", {}).get("movement") in ("MORE_LIKELY_SHALLOW", "LESS_LIKELY_SHALLOW") for t in resp_t if t["fired"])
    if depth_fired:
        hab3 = 1.0
    elif deep_fired or shallow_seen:
        hab3 = 0.5
    else:
        hab3 = 0.0
    crit["HAB-3"] = _res(hab3, {"depthClassRulesFired": [t["ruleId"] for t in depth_fired], "deepHabitatRulesFired": [t["ruleId"] for t in deep_fired],
                                "shallowTendencyObserved": shallow_seen,
                                "depthKnowledge": "KNOWS_DEPTH_PREFERENCE" if depth_fired else ("SHALLOW_DEEP_TENDENCY_ONLY" if hab3 else "HAS_NO_DEPTH_RULE")}, kc, "HAB-3")
    crit["HAB-4"] = _supplied_depth(h, sid, depth_fired, kc)
    crit["HAB-5"] = _scaled(_depth_abstention(h, sid, depth_fired, kc), breadth, breadth_why, kc, "HAB-5") if exec_ok else _res(0.0, {"dependsOnExecutable": True}, kc, "HAB-5")

    # ---- Category 3: environmental responses
    for cid, fam, fname in (("ENV-1", TEMPERATURE, "TEMPERATURE"), ("ENV-2", HYDROLOGY, "HYDROLOGY"), ("ENV-3", CLARITY, "CLARITY")):
        ts_ = [t for t in resp_t if t["feature"] in fam]
        best = max((_ladder(t) for t in ts_), default=0.0)
        crit[cid] = _res(0.5 * best + 0.5 * _cov(coverage, fname), {"execution": best, "annualCoverageMonths": coverage.get(fname, []), "rulesTested": [{k: t.get(k) for k in ("ruleId", "feature", "response", "fired", "contrastChanges", "directionConsistent",
                                                                          "conflict", "scenario", "observedOutlook")} for t in ts_],
                                "conflict": bool(ts_) and all(t["conflict"] for t in ts_)}, kc, cid)
    env_fired = [t for t in resp_t if t["fired"] and t["feature"] in ENVIRONMENTAL]
    env_fams = {f for t in env_fired for f in t["family"]} & {"TEMPERATURE", "HYDROLOGY", "CLARITY"}
    crit["ENV-4"] = (_scaled(_env_safety(h, sid, env_fired, ev, kc), min(1.0, len(env_fams) / 2.0), f"executable rules in {len(env_fams)} environmental famil(ies); full safety credit needs 2",
                             kc, "ENV-4") if env_fired else _res(0.0, {"note": "no executable environmental rule: nothing to keep safe"}, kc, "ENV-4"))

    # ---- Category 4: spawning & seasonality
    if phen_t:
        a = [phen_t["inWindow"]["ok"]] + ([phen_t["outside"]["ok"]] if "outside" in phen_t else [])
        isc = dict(phen_t["inWindow"]["scenario"])
        spawn_out = h.outlook(sid, isc.pop("month"), **isc)
        behaviour = spawn_out["state"] != "UNKNOWN"          # Fish says what the fish DOES in its spawn window, not only when the window is
        crit["SPN-1"] = _res(0.5 * (sum(a) / len(a) if a else 0.0) + 0.5 * behaviour,
                             {"phenology": {k: phen_t.get(k) for k in ("ruleId", "inWindow", "outside")},
                              "spawnPeriodBehaviour": {"state": spawn_out["state"], "movement": spawn_out["movement"], "where": spawn_out.get("where"), "known": behaviour}}, kc, "SPN-1")
        b = [phen_t["monthOnly"]["ok"]] + ([phen_t["tempOnly"]["ok"]] if "tempOnly" in phen_t else [])
        crit["SPN-2"] = _res(sum(b) / len(b), {"phenology": {k: phen_t.get(k) for k in ("monthOnly", "tempOnly")}}, kc, "SPN-2")
        checks = {"spawnOutputCarriesConfidenceAndTransfer": phen_t["inWindow"]["carriesConfidence"]}
        if "outOfRegion" in phen_t:
            checks["regionRestrictedWindowDoesNotFireOutOfRegion"] = phen_t["outOfRegion"]["ok"]
        if kc["openSpawnDiscrepancies"]:
            checks["openSpawnDiscrepancyKeepsConfidenceBelowHigh"] = phen_t["inWindow"]["confidence"] != "HIGH"
        crit["SPN-4"] = _res(sum(checks.values()) / len(checks), {"checks": checks, "openSpawnDiscrepancies": kc["openSpawnDiscrepancies"]}, kc, "SPN-4")
    else:
        for cid in ("SPN-1", "SPN-2", "SPN-4"):
            crit[cid] = _res(0.0, {"phenologyRule": None}, kc, cid)
    seasons = {}
    grid = standard_grid()
    for i, s in enumerate(my):
        seasons.setdefault(SEASON_OF[grid[i]["month"]], set()).add(s)
    season_sigs = {k: frozenset(v) for k, v in seasons.items()}
    # Seasonal breadth = seasons in which Fish says what the fish is doing (outlook known), NOT counting the spawn-window state alone;
    # full credit needs that behaviour to differ between seasons (a year-round constant is half credit per season).
    behaviour_sigs = {k: frozenset(x[:4] for x in v) for k, v in seasons.items()}
    known_seasons = sorted(k for k, v in seasons.items() if any(x[0] != "UNKNOWN" for x in v))
    varies = len(set(behaviour_sigs.values())) >= 2
    spn3 = (len(known_seasons) / 4.0) * (1.0 if varies else 0.5)
    crit["SPN-3"] = _res(spn3, {"seasonsWithKnownBehaviour": known_seasons, "behaviourDiffersBetweenSeasons": varies,
                                "distinctSeasonalPatterns": len(set(behaviour_sigs.values())), "note": "spawn-window state alone does not count"}, kc, "SPN-3")

    # ---- Category 5: day / night
    dn_rules = [t for t in resp_t if t["feature"] == "daypart"]
    a = h.assessment(sid, dn_rules[0]["scenario"]["month"] if dn_rules else 7, daypart="NIGHT")["species"][0]
    dna = a.get("dayNightAssessment") or {}
    if any(t["fired"] for t in dn_rules) or dna.get("night") in ("ACTIVE_OR_SHALLOW", "REDUCED", "NO_DIFFERENCE_DOCUMENTED"):
        dn1, conflict = 1.0, False
    elif dna.get("night") == "CONFLICT" or any(t["conflict"] for t in dn_rules):
        dn1, conflict = 0.5, True
    else:
        dn1, conflict = 0.0, False
    night_cov = _cov(coverage, "DAYPART") if dn1 >= 1.0 else 0.0
    crit["DN-1"] = _res(0.5 * dn1 + 0.5 * night_cov, {"execution": dn1, "annualCoverageMonths": coverage.get("DAYPART", []) if dn1 >= 1.0 else [], "nightAssessment": {k: dna.get(k) for k in ("night", "evidenceKind", "reason")}, "rulesTested": [t["ruleId"] for t in dn_rules],
                              "conflict": conflict}, kc, "DN-1")
    kind = dna.get("evidenceKind")
    if dn1 >= 1.0:          # evidence kind matters only when a (non-conflicting) day/night claim is made
        frac = {"BEHAVIORAL": 1.0, "MIXED": 0.75, "CATCHABILITY": 0.5, "UNCLASSIFIED": 0.25}.get(kind, 0.0)
        det = {"evidenceKind": kind}
        if kind in ("CATCHABILITY", "UNCLASSIFIED"):
            det["needsField"] = "night evidence does not establish where the fish is (catch or unclassified study design): position data needed"
        crit["DN-2"] = _res(frac, det, kc, "DN-2")
    else:
        crit["DN-2"] = _res(0.0, {"evidenceKind": kind or "NONE", "conflict": conflict}, kc, "DN-2")
    crit["DN-3"] = _scaled(_daypart_abstention(h, sid, dn_rules, kc), breadth, breadth_why, kc, "DN-3") if exec_ok else _res(0.0, {"dependsOnExecutable": True}, kc, "DN-3")

    # ---- Category 6: knowledge application (full pipeline)
    crit["APP-1"] = _application(h, sid, ev, phen_t, kc)

    missing = sorted(set(CRITERION_IDS) - set(crit))
    if missing:
        raise RuntimeError(f"criteria not evaluated: {missing}")
    return {"criteria": crit, "tests": {"responseRules": len(resp_t), "habitatRules": len(hab_t), "phenology": bool(phen_t)}}


def _uncertainty_checks(h: Harness, sid: str) -> dict:
    """Every non-UNKNOWN output explains itself and passes the assessment contract; zero-input outputs are LOW seasonal priors."""
    reasons_ok, contract_ok = True, True
    for c in standard_grid()[::4]:
        c = dict(c)
        m = c.pop("month")
        a = h.assessment(sid, m, **c)
        if ba.validate_assessment(a):
            contract_ok = False
        s = a["species"][0]
        if s["biologicalState"]["state"] != "UNKNOWN" and not s["supportingReasons"]:
            reasons_ok = False
    prior_ok = True
    for m in range(1, 13):
        o = h.outlook(sid, m)
        if o["state"] != "UNKNOWN" and (o.get("basis") != "SEASONAL_PRIOR" or o.get("confidence") not in ("LOW", None) or not o.get("why")):
            prior_ok = False
    return {"nonUnknownOutputsExplained": reasons_ok, "assessmentContractHolds": contract_ok, "zeroInputIsLowSeasonalPrior": prior_ok}


def _supplied_depth(h: Harness, sid: str, depth_fired: list[dict], kc: dict) -> dict:
    if not depth_fired:
        return _res(0.0, {"depthKnowledge": "HAS_NO_DEPTH_RULE"}, kc, "HAB-4")
    t = depth_fired[0]
    sc = dict(t["scenario"])
    m = sc.pop("month")
    want = t["depthClass"]
    other = next(c for c in ft.DEPTH_CLASSES if c != want)
    inside = h.assessment(sid, m, supplied_depth={"depthClass": want}, **sc)["species"][0]["depthTendencies"]["suppliedDepth"]
    outside = h.assessment(sid, m, supplied_depth={"depthClass": other}, **sc)["species"][0]["depthTendencies"]["suppliedDepth"]
    ok = [inside.get("interpretation") == "WITHIN_PREFERRED_DEPTH", outside.get("interpretation") in ("OUTSIDE_PREFERRED_DEPTH", "AVOIDED_DEPTH")]
    det = {"ruleId": t["ruleId"], "preferred": want, "inside": inside, "outside": {"depthClass": other} | outside}
    if not all(ok):
        det["runtimeDefect"] = "supplied depth was not interpreted against the species' depth rule"
    return _res(sum(ok) / 2.0, det, kc, "HAB-4")


def _depth_abstention(h: Harness, sid: str, depth_fired: list[dict], kc: dict) -> dict:
    a = h.assessment(sid, 7)["species"][0]["depthTendencies"] or {}
    checks = {"noSuppliedDepthIsNotSupplied": (a.get("suppliedDepth") or {}).get("interpretation") == "NOT_SUPPLIED"}
    junk = h.assessment(sid, 7, supplied_depth={"depthM": -4})["species"][0]["depthTendencies"]["suppliedDepth"]
    checks["unrecognisedDepthIsRefused"] = junk.get("interpretation") == "UNRECOGNISED_DEPTH"
    if not depth_fired and a.get("depthKnowledge") == "HAS_NO_DEPTH_RULE":
        d = h.assessment(sid, 7, supplied_depth={"depthClass": "LT_0_5M"})["species"][0]["depthTendencies"]["suppliedDepth"]
        checks["noDepthRuleIsNotInvented"] = d.get("interpretation") in ("NO_DEPTH_RULE", "NO_APPLICABLE_DEPTH_RULE")
    det = {"checks": checks}
    if not all(checks.values()):
        det["runtimeDefect"] = "depth abstention check failed"
    return _res(sum(checks.values()) / len(checks), det, kc, "HAB-5")


def _env_safety(h: Harness, sid: str, env_fired: list[dict], ev: list[dict], kc: dict) -> dict:
    checks = {}
    miss = []
    for t in env_fired:
        m = t["scenario"]["month"]
        b = _band(h.sp(sid, m), t["feature"])
        miss.append(b is None or (b["response"] == "UNKNOWN" and "unknown" in (b.get("reason") or "").lower()))
    checks["missingInputStaysUnknown"] = all(miss)
    deg = []
    for t in env_fired:
        sc = dict(t["scenario"])
        m = sc.pop("month")
        good = _band(h.sp(sid, m, **sc), t["feature"])
        bad = _band(h.sp(sid, m, status="DEGRADED", **sc), t["feature"])
        if good and bad and good.get("confidence") and bad.get("confidence"):
            deg.append(rl.CONFIDENCE.index(bad["confidence"]) <= rl.CONFIDENCE.index(good["confidence"]) and
                       (good["confidence"] == "LOW" or rl.CONFIDENCE.index(bad["confidence"]) < rl.CONFIDENCE.index(good["confidence"])))
    if deg:
        checks["degradedInputLowersConfidence"] = all(deg)
    fav = [r for r in ev if r["kind"] == "RESPONSE" and r["feature"]["featureId"] in ENVIRONMENTAL and r["response"] == "FAVORABLE"]
    lim = [r for r in ev if r["kind"] == "RESPONSE" and r["feature"]["featureId"] in ENVIRONMENTAL and r["response"] in ("LIMITING", "BLOCKING")]
    pair = None
    for a in fav:
        for b in lim:
            ma = set((a.get("applicability") or {}).get("months") or range(1, 13))
            mb = set((b.get("applicability") or {}).get("months") or range(1, 13))
            if ma & mb and a["feature"]["featureId"] != b["feature"]["featureId"]:
                try:
                    cond = probe(a["feature"]["featureId"], a["feature"]["states"][0]) | probe(b["feature"]["featureId"], b["feature"]["states"][0])
                except KeyError:
                    continue
                pa, pb = probe(a["feature"]["featureId"], a["feature"]["states"][0]), probe(b["feature"]["featureId"], b["feature"]["states"][0])
                if any(k in pa and k in pb and pa[k] != pb[k] for k in pa):
                    continue
                pair = (a, b, sorted(ma & mb)[0], cond)
                break
        if pair:
            break
    det = {"checks": checks, "conflictConstructible": bool(pair)}
    if pair:
        a, b, m, cond = pair
        o = h.outlook(sid, m, **cond)
        checks["conflictingSignalsAreMixedNotConfident"] = o["state"] == "MIXED" and o.get("confidence") in (None, "LOW", "MEDIUM")
        det["conflictScenario"] = scenario(m, **cond)
        det["conflictOutlook"] = o["state"]
    if not all(checks.values()):
        det["runtimeDefect"] = "environmental safety check failed: " + ", ".join(k for k, v in checks.items() if not v)
    return _res(sum(checks.values()) / len(checks), det, kc, "ENV-4")


def _daypart_abstention(h: Harness, sid: str, dn_rules: list[dict], kc: dict) -> dict:
    checks = {}
    o = h.outlook(sid, 7, temp_f=CLIMATOLOGY_F[7], stage="STABLE")
    daypart_band = _band(h.sp(sid, 7, temp_f=CLIMATOLOGY_F[7], stage="STABLE"), "daypart")
    checks["missingDaypartAssertsNoDaypartBand"] = daypart_band is None or daypart_band["response"] == "UNKNOWN"
    a = h.assessment(sid, dn_rules[0]["scenario"]["month"] if dn_rules else 7, daypart="NIGHT")["species"][0]["dayNightAssessment"]
    if not dn_rules:
        checks["noDayNightRuleIsUnknown"] = a.get("night") == "UNKNOWN" and bool(a.get("reason"))
    else:
        night_only = all(set(rs["feature"]["states"]) <= {"NIGHT", "TWILIGHT"} for rs in h.ruleset.evaluable(sid) if rs["kind"] == "RESPONSE" and rs["feature"]["featureId"] == "daypart")
        if night_only:
            d = _band(h.sp(sid, dn_rules[0]["scenario"]["month"], daypart="DAY"), "daypart")
            checks["dayIsNotInferredFromNightEvidence"] = d is None or d["response"] == "UNKNOWN"
    det = {"checks": checks, "outlookActivityWithoutDaypart": o["activity"]}
    if not all(checks.values()):
        det["runtimeDefect"] = "day/night abstention check failed"
    return _res(sum(checks.values()) / len(checks), det, kc, "DN-3")


def application_scenario(h: Harness, sid: str, ev: list[dict], phen_t: dict | None) -> dict:
    """The species' best-supported scenario, built from its OWN executable knowledge (documented in the rubric): spawn window month and
    temperature when known; a favourable hydrology rule's condition in that month; night if a favourable night rule applies."""
    if phen_t and phen_t["inWindow"]["ok"]:
        m = phen_t["inWindow"]["scenario"]["month"]
        cond = {"temp_f": phen_t["inWindow"]["scenario"]["temp_f"]}
    else:
        fav = [r for r in ev if r["kind"] == "RESPONSE" and r["response"] in ("FAVORABLE", "WORKABLE") and r["feature"]["featureId"] in TEMPERATURE]
        m = _first_month(fav[0]) if fav else (_first_month(ev[0]) if ev else 5)
        cond = probe(fav[0]["feature"]["featureId"], fav[0]["feature"]["states"][0]) if fav else {"temp_f": CLIMATOLOGY_F[m]}
    for r in ev:
        if r["kind"] == "RESPONSE" and r["response"] == "FAVORABLE" and r["feature"]["featureId"] in HYDROLOGY and m in ((r.get("applicability") or {}).get("months") or range(1, 13)):
            p = probe(r["feature"]["featureId"], r["feature"]["states"][0])
            if "temp_f" in p and "temp_f" in cond:
                p = {k: v for k, v in p.items() if k != "temp_f"}
            cond |= p
            break
    night = any(r["kind"] == "RESPONSE" and r["feature"]["featureId"] == "daypart" and r["response"] in ("FAVORABLE", "WORKABLE")
                and m in ((r.get("applicability") or {}).get("months") or range(1, 13)) for r in ev)
    cond.setdefault("clarity_ft", 2.0)
    cond.setdefault("stage", "STABLE")
    return {"month": m, "daypart": "NIGHT" if night else "DAY", **cond}


def _application(h: Harness, sid: str, ev: list[dict], phen_t: dict | None, kc: dict) -> dict:
    sc = application_scenario(h, sid, ev, phen_t)
    c = dict(sc)
    m = c.pop("month")
    a = h.assessment(sid, m, **c)
    s = a["species"][0]
    checks = {"biologicalAssessment": s["biologicalState"]["state"] != "UNKNOWN" or (s.get("spawningAssessment") or {}).get("state") in SPAWN_KNOWN,
              "supportingReasons": bool(s.get("supportingReasons")),
              "uncertaintyAndClaim": bool(s.get("confidenceLimitations")) and s.get("claim", {}).get("maturity") == "NOT_VALIDATED",
              "applicableConditions": bool(a.get("conditions", {}).get("month")) and bool(a.get("conditions", {}).get("inputStatus")),
              "evidenceReferences": bool(s.get("evidenceReferences")),
              "boundaryAndContract": not ba.validate_assessment(a)}
    frac = sum(checks.values()) / len(checks) if checks["biologicalAssessment"] else 0.0
    spawn_only = s["biologicalState"]["state"] == "UNKNOWN"
    if spawn_only:
        frac *= 0.5          # only a spawn-window state: Fish cannot say what the fish is doing under these conditions
    det = {"scenario": sc, "checks": checks, "spawnStateOnly": spawn_only, "output": {"state": s["biologicalState"], "reasons": s.get("supportingReasons"), "spawn": s.get("spawningAssessment", {}).get("state"),
                                                       "habitatPreferences": [x.get("label") or x["habitatClass"] for x in s.get("habitatPreferences") or [] if x.get("state") == "ACTIVE"]}}
    if checks["biologicalAssessment"] and not all(checks.values()):
        det["runtimeDefect"] = "application output incomplete: " + ", ".join(k for k, v in checks.items() if not v)
    return _res(frac, det, kc, "APP-1")


# ---------------------------------------------------------------- reference cases (human-reviewed expectations)
REFERENCE_STATUS = ("PROPOSED", "APPROVED", "REJECTED")


def validate_reference_case(c: dict) -> list[str]:
    e = []
    for k in ("caseId", "speciesId", "criterion", "conditions", "expect", "basis", "reviewStatus"):
        if k not in c:
            e.append(f"{c.get('caseId')}: missing {k}")
    if c.get("criterion") not in CRITERIA:
        e.append(f"{c.get('caseId')}: unknown criterion {c.get('criterion')!r}")
    if c.get("reviewStatus") not in REFERENCE_STATUS:
        e.append(f"{c.get('caseId')}: reviewStatus")
    if c.get("reviewStatus") == "APPROVED" and not (c.get("review") or {}).get("reviewer"):
        e.append(f"{c.get('caseId')}: APPROVED needs review.reviewer")
    if not isinstance((c.get("conditions") or {}).get("month"), int):
        e.append(f"{c.get('caseId')}: conditions.month")
    return e


def run_reference_case(h: Harness, c: dict) -> dict:
    cond = dict(c["conditions"])
    m = cond.pop("month")
    s = h.assessment(c["speciesId"], m, **cond)["species"][0]
    obs = {"state": s["biologicalState"]["state"], "movement": s["biologicalState"]["movement"], "spawnWindow": s["seasonalState"]["spawnWindow"],
           "night": (s.get("dayNightAssessment") or {}).get("night")}
    fails = [k for k, allowed in c["expect"].items() if obs.get(k) not in allowed]
    return {"caseId": c["caseId"], "speciesId": c["speciesId"], "criterion": c["criterion"], "reviewStatus": c["reviewStatus"],
            "passed": not fails, "observed": obs, "failedExpectations": fails}


# ---------------------------------------------------------------- confidence + readiness (separate measurements; statuses only, no points)
def scientific_confidence(kc: dict, observations: int) -> dict:
    tr = kc["transfer"]
    if kc["rules"]["usable"] == 0 and not kc.get("knowledgeScoreSpeciesV2"):
        status = "NO_EVIDENCE_BASE"
    elif observations > 0:
        status = "FIELD_OBSERVATIONS_IN_PROGRESS"
    elif kc["rules"]["approved"]:
        status = "PARTLY_REVIEWED_NOT_FIELD_VALIDATED"
    else:
        status = "RESEARCH_UNREVIEWED_NOT_FIELD_VALIDATED"
    return {"status": status, "researchMaturity": kc.get("researchMaturity"), "independentReview": {"approvedRules": kc["rules"]["approved"], "usableRules": kc["rules"]["usable"]},
            "regionalTransfer": tr, "contradictionsRecorded": kc["contradictionsRecorded"] if kc["contradictionsRecorded"] is not None else "UNKNOWN",
            "openDiscrepancies": kc["openDiscrepancies"], "fieldValidation": "NOT_VALIDATED" if observations == 0 else "IN_PROGRESS",
            "note": "Scientific confidence is a status, not a score; it never adds capability points."}


def production_readiness(brain: dict | None, capability_status: str | None) -> dict:
    b = brain or {}
    gates = [
        {"gate": "lifecycle", "status": "BLOCKED" if b.get("lifecycle") in (None, "PROFILED", "CALIBRATION") else "READY", "value": b.get("lifecycle")},
        {"gate": "publisherCutover", "status": "BLOCKED" if (b.get("publisherRequired") or {}).get("cutoverStatus") != "LIVE" else "READY",
         "value": (b.get("publisherRequired") or {}).get("cutoverStatus")},
        {"gate": "customerIntegration", "status": "BLOCKED" if b.get("customerIntegrationMode") in (None, "none") else "READY", "value": b.get("customerIntegrationMode")},
        {"gate": "perLakeBiologicalState", "status": "BLOCKED", "value": capability_status or "UNKNOWN", "note": "PILOT_INTERNAL; LIVE is an owner decision (FISH-PRD-001)"},
        {"gate": "capabilityPublication", "status": "BLOCKED", "value": "INACTIVE", "note": "capability results are not published; scoring contract awaits approval"},
        {"gate": "independentEvidenceValidation", "status": "BLOCKED", "value": "NOT_VALIDATED", "note": "validation by independent historical, public-dataset or literature evidence; owner field trips are optional, never required"},
    ]
    return {"status": "NOT_READY" if any(g["status"] != "READY" for g in gates) else "READY", "gates": gates,
            "note": "Production readiness is gates only; it never adds capability points (deployment, connectivity and registry completeness earn nothing)."}


# ---------------------------------------------------------------- the evaluation
def canonical(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def evaluate(*, ruleset: rl.RuleSet, profiles: dict, cohorts: dict, knowledge: dict, movement_cards: dict | None = None,
             discrepancies: list | None = None, reference_cases: list | None = None, brain: dict | None = None, observations: int = 0,
             capability_status: str | None = None, evaluated_at: str | None = None, code_version: str | None = None) -> dict:
    """Run the full evaluation. `cohorts` = the frozen cohort definition (docs/brains/scoring/fish-capability-cohorts-v1.json).
    `knowledge` = {researchVersion, rulesVersion, manifestSha256, overlay?}. Returns the evidence artifact (no points)."""
    rosters = cohorts["cohorts"]
    evaluate_ids = sorted(set(rosters["TARGET"]["species"]) | set(rosters["ALL_ASSESSED"]["species"]))
    policy_na = sorted(cohorts.get("notAssessedByPolicy") or [])
    not_individual = dict(cohorts.get("notIndividuallyAssessable") or {})          # grouped / unresolved taxa: no species-level biology to evaluate
    species_info = {s: {"assessment": (profiles.get(s) or {}).get("assessment"), "researchMaturity": (profiles.get(s) or {}).get("researchMaturity")}
                    for s in set(evaluate_ids) | set(policy_na)}
    kv = knowledge["researchVersion"] + (f"+{knowledge['overlay']['id']}" if knowledge.get("overlay") else "")
    h = Harness(ruleset, species_info, [s for s in evaluate_ids if s in profiles], kv)
    sigs = grid_signatures(h, h.species)
    cover = annual_coverage(h, h.species)
    cases = reference_cases or []
    case_errors = [e for c in cases for e in validate_reference_case(c)]
    case_results = []
    for c in cases:
        if validate_reference_case(c):
            continue
        try:
            case_results.append(run_reference_case(h, c))
        except Exception as ex:      # a broken case is reported, never scored
            case_results.append({"caseId": c.get("caseId"), "speciesId": c.get("speciesId"), "error": str(ex), "passed": False, "reviewStatus": c.get("reviewStatus")})
    out_species = {}
    for sid, why in sorted(not_individual.items()):
        out_species[sid] = {"evaluationStatus": "INSUFFICIENT_EVIDENCE", "role": ts.role(sid),
                            "reason": f"not an individual species ({(profiles.get(sid) or {}).get('taxonomyStatus', 'unresolved')}): {why}. Explicitly unscored; outside both rosters"}
    for sid in evaluate_ids:
        if sid in not_individual:
            continue
        prof = profiles.get(sid)
        if prof is None:
            out_species[sid] = {"evaluationStatus": "EVALUATION_FAILED", "reason": "species is in the frozen roster but absent from the knowledge release",
                                "role": ts.role(sid)}
            continue
        if prof.get("assessment") == "NOT_ASSESSED":
            out_species[sid] = {"evaluationStatus": "NOT_ASSESSED", "reason": "NOT_ASSESSED by policy in the knowledge release", "role": ts.role(sid)}
            continue
        kc = knowledge_context(sid, prof, ruleset, (movement_cards or {}).get(sid), discrepancies or [])
        try:
            r = evaluate_species(h, sid, kc, sigs, cover.get(sid))
        except Exception as ex:
            out_species[sid] = {"evaluationStatus": "EVALUATION_FAILED", "reason": f"{type(ex).__name__}: {ex}", "role": kc["role"], "knowledgeContext": kc,
                                "trace": traceback.format_exc(limit=3)}
            continue
        mine = [c for c in case_results if c.get("speciesId") == sid]
        for c in mine:      # an APPROVED reference case that fails withdraws the credit of the criterion it checks
            if c.get("reviewStatus") == "APPROVED" and not c.get("passed"):
                cr = r["criteria"][c["criterion"]]
                cr.update({"result": "FAIL", "fraction": 0.0, "withdrawnBy": c["caseId"],
                           "blocker": {"blocker": "RUNTIME_DEFECT", "why": f"approved reference case {c['caseId']} failed"}})
        out_species[sid] = {"evaluationStatus": "ASSESSED", "role": kc["role"], "knowledgeContext": kc, "criteria": r["criteria"], "tests": r["tests"],
                            "annualCoverage": cover.get(sid),
                            "referenceCases": mine, "scientificConfidence": scientific_confidence(kc, observations)}
    for sid in policy_na:
        out_species.setdefault(sid, {"evaluationStatus": "NOT_ASSESSED", "reason": "NOT_ASSESSED by policy (explicitly unscored)", "role": ts.role(sid)})
    approved = sum(1 for c in cases if c.get("reviewStatus") == "APPROVED")
    body = {
        "schema": EVIDENCE_SCHEMA, "evaluatorVersion": EVALUATOR_VERSION, "rubricId": RUBRIC_ID, "criteria": list(CRITERION_IDS),
        "cohortsVersion": cohorts.get("cohortsVersion"), "knowledge": knowledge | {"knowledgeVersion": kv}, "frame": FRAME | {"outOfFrameRegion": OUT_REGION},
        "scenarioClimatologyF": CLIMATOLOGY_F, "outcomeKind": OUTCOME_KIND, "codeVersion": code_version,
        "referenceCases": {"total": len(cases), "approved": approved, "proposed": sum(1 for c in cases if c.get("reviewStatus") == "PROPOSED"),
                           "errors": case_errors, "results": case_results,
                           "status": "NO_APPROVED_REFERENCE_CASES" if approved == 0 else "APPROVED_CASES_APPLIED"},
        "species": out_species,
        "scientificConfidence": {"note": "statuses per species under species[].scientificConfidence; Brain level: no species VALIDATED, no field observations",
                                 "fieldObservations": observations},
        "productionReadiness": production_readiness(brain, capability_status),
        "scenariosRun": h.scenarios_run,
        "limitations": [
            "Synthetic scenarios: passes are SCENARIO_BEHAVIOR_PASSED, not field-validated accuracy.",
            "No APPROVED human-reviewed reference cases yet: expectations come from the species' own evidence-backed rules, so the evaluation is a CANDIDATE.",
            "Species are evaluated as if present (biology, not lake presence); Lake Brain presence policy is unchanged.",
            "Area-level habitat classes and per-lake depth layers are not evaluated (Lake/Depth/Vegetation Brains own them).",
        ],
    }
    eid = "fcap-" + hashlib.sha256(canonical(body)).hexdigest()[:20]
    return body | {"evaluationId": eid, "evaluatedAt": evaluated_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


PUBLISHABLE_KC = ("role", "assessment", "taxonomyStatus", "researchMaturity", "knowledgeScoreSpeciesV2", "rules", "openDiscrepancies", "doNotResearch")


def publishable_evidence(ev: dict) -> dict:
    """The evidence the shared scorer job ships in its image (docs/brains/scoring/evidence/fish-capability-evidence.json): same evaluation identity
    and fractions, with every private detail removed (no rule ids, behaviour tags, scenarios, habitat classes or reference-case text).
    The repository is public: this keeps only scores' inputs, blocker labels and published-equivalent counts."""
    sp = {}
    for sid, s in (ev.get("species") or {}).items():
        row = {k: s.get(k) for k in ("evaluationStatus", "role", "reason")}
        if s.get("criteria"):
            row["criteria"] = {cid: {"result": c.get("result"), "fraction": c.get("fraction"), "outcomeKind": c.get("outcomeKind"),
                                     **({"blocker": {"blocker": (c.get("blocker") or {}).get("blocker"), "why": (c.get("blocker") or {}).get("why")}} if c.get("blocker") else {})}
                               for cid, c in s["criteria"].items()}
            row["knowledgeContext"] = {k: (s.get("knowledgeContext") or {}).get(k) for k in PUBLISHABLE_KC}
            row["scientificConfidence"] = s.get("scientificConfidence")
        sp[sid] = {k: v for k, v in row.items() if v is not None}
    k = ev.get("knowledge") or {}
    rc = ev.get("referenceCases") or {}
    return {**{x: ev.get(x) for x in ("schema", "evaluatorVersion", "rubricId", "criteria", "cohortsVersion", "outcomeKind", "codeVersion", "evaluationId",
                                       "evaluatedAt", "scientificConfidence", "productionReadiness", "limitations", "frame")},
            "knowledge": {"researchVersion": k.get("researchVersion"), "rulesVersion": k.get("rulesVersion"), "manifestSha256": k.get("manifestSha256"),
                          "knowledgeVersion": k.get("knowledgeVersion"), "overlay": (k.get("overlay") or {}).get("id")},
            "referenceCases": {x: rc.get(x) for x in ("total", "approved", "proposed", "status")},
            "publishable": True, "species": sp}
