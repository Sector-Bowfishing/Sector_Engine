"""SYNTHETIC species, rules and profiles for the Fish Biological Capability V2 tests (this repository is public: no real biology here).

  alpha_fish   rich: temperature, hydrology, clarity, night (telemetry), habitat with a depth class, spawn window
  beta_fish    thin: one habitat rule only
  twin_fish    identical rules to beta_fish (species-specific-difference test)
  gamma_fish   assessed, no rules at all (missing capability -> 0)
  gated_fish   one usable rule that cannot fire until a reviewer asserts its season (REVIEW_BLOCKED)
  draft_fish   only a DRAFT rule (knowledge not in runtime)
  conflict_fish  night evidence that disagrees (FAVORABLE vs LIMITING)
  spawn_fish   a spawn window and nothing else (narrow knowledge must not earn broad credit)
  na_fish      NOT_ASSESSED by policy
"""
import copy
import json
import os

import rules as rl

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
RUBRIC_PATH = os.path.join(REPO, "docs", "brains", "scoring", "fish-biological-capability-v2.json")
COHORTS_PATH = os.path.join(REPO, "docs", "brains", "scoring", "fish-capability-cohorts-v1.json")


def ev(i, stream, study="field study", read="READ-FULL"):
    return {"evidenceId": f"E{i}", "packet": "synthetic", "sourceNo": f"S{i}", "readStatus": read, "streamId": stream, "directness": "DIRECT",
            "counts": True, "southeast": False, "studyType": study}


def rule(rid, sid, kind="RESPONSE", **kw):
    r = {"schemaVersion": 1, "ruleId": rid, "ruleVersion": 1, "speciesId": sid, "kind": kind, "status": "RECONCILED", "confidence": "LOW",
         "transferability": {"southeastReservoir": "PARTIAL"}, "applicability": {"regions": ["any"]}, "behavior": "SYNTHETIC_BEHAVIOUR",
         "evidence": [ev(1, f"{rid}-a")]}
    r.update(kw)
    return r


def resp(rid, sid, feature, states, response, months=None, **kw):
    app = {"regions": ["any"], **({"months": months} if months else {})}
    return rule(rid, sid, feature={"featureId": feature, "states": states}, response=response, applicability=app, **kw)


def habitat(rid, sid, cls, months=None, depth=None, requires=None, direction="FAVOR", **kw):
    h = {"habitatClass": cls, "direction": direction, **({"depthClass": depth} if depth else {})}
    app = {"regions": ["any"], **({"months": months} if months else {})}
    return rule(rid, sid, kind="HABITAT", habitat=h, applicability=app, **({"requires": requires} if requires else {}), **kw)


def phenology(rid, sid, months, lo, hi, regions=("south",)):
    return rule(rid, sid, kind="PHENOLOGY", phenology={"event": "spawn", "tempC": {"min": lo, "max": hi}},
                applicability={"months": list(months), "regions": list(regions)})


def base_rules():
    a = "alpha_fish"
    rs = [
        resp("AL-TMP-01", a, "waterTempBand", ["C15_18", "C18_21"], "FAVORABLE", months=[3, 4, 5, 6]),
        resp("AL-TMP-02", a, "waterTempBand", ["LT_10C", "C10_15"], "LIMITING", months=[11, 12, 1, 2]),
        resp("AL-HYD-01", a, "risingStage", ["TRUE"], "FAVORABLE", months=[3, 4, 5, 6, 7]),
        resp("AL-CLR-01", a, "clarityBand", ["TURBID"], "WORKABLE"),
        resp("AL-NGT-01", a, "daypart", ["NIGHT"], "FAVORABLE", months=[5, 6, 7, 8, 9], evidence=[ev(1, "tele", study="radio telemetry")]),
        habitat("AL-HAB-01", a, "shallowVegetatedHabitat", months=[3, 4, 5, 6, 7, 8], depth="LT_0_5M"),
        habitat("AL-HAB-02", a, "floodedVegetation", requires=[{"featureId": "risingStage", "states": ["TRUE"]}], months=[4, 5, 6]),
        phenology("AL-SPN-01", a, [4, 5, 6], 17.0, 24.0),
        habitat("BE-HAB-01", "beta_fish", "backwaterHabitat"),
        habitat("TW-HAB-01", "twin_fish", "backwaterHabitat"),
        resp("GA-HYD-01", "gated_fish", "risingStage", ["TRUE"], "FAVORABLE"),          # unbounded, no YEAR_ROUND assertion -> gated
        resp("DR-HYD-01", "draft_fish", "risingStage", ["TRUE"], "FAVORABLE", months=[4, 5], status="DRAFT"),
        resp("CF-NGT-01", "conflict_fish", "daypart", ["NIGHT"], "FAVORABLE", months=[6, 7, 8]),
        resp("CF-NGT-02", "conflict_fish", "daypart", ["NIGHT"], "LIMITING", months=[6, 7, 8]),
        habitat("CF-HAB-01", "conflict_fish", "woodyCover", months=[6, 7, 8]),
        phenology("SP-SPN-01", "spawn_fish", [4, 5, 6], 15.0, 20.0),          # spawn window only (narrow knowledge)
    ]
    return rs


def ruleset(rules_=None, assertions=None, version="syn.1"):
    rs = rules_ if rules_ is not None else base_rules()
    sa = {"AL-CLR-01": "YEAR_ROUND", "BE-HAB-01": "YEAR_ROUND", "TW-HAB-01": "YEAR_ROUND"} | (assertions or {})
    return rl.RuleSet(copy.deepcopy(rs), version, season_assertions=sa)


def profile(sid, assessment="ASSESSED", domains=None):
    d = domains or {}
    return {"speciesId": sid, "assessment": assessment, "researchMaturity": "RESEARCH" if assessment == "ASSESSED" else "NOT_STARTED", "taxonomyStatus": "RESOLVED",
            "knowledge": {"overallRounded": d.get("_overall", 3.0),
                          "domains": {k: {"score": v, "contradictions": []} for k, v in d.items() if not k.startswith("_")}} if assessment == "ASSESSED" else {}}


ASSESSED = ["alpha_fish", "beta_fish", "twin_fish", "gamma_fish", "gated_fish", "draft_fish", "conflict_fish", "spawn_fish"]


def profiles():
    p = {s: profile(s) for s in ASSESSED}
    p["gamma_fish"] = profile("gamma_fish", domains={"_overall": 0.0, "habitatDepthCover": 0, "temperatureOxygen": 6})
    p["na_fish"] = profile("na_fish", assessment="NOT_ASSESSED")
    return p


def cohorts(target=("alpha_fish", "beta_fish", "gamma_fish"), all_=None, version="fish-capability-cohorts-v1"):
    return {"cohortsVersion": version, "status": "CANDIDATE_PENDING_OWNER_APPROVAL",
            "cohorts": {"TARGET": {"label": "t", "species": sorted(target)}, "ALL_ASSESSED": {"label": "a", "species": sorted(all_ or ASSESSED)}},
            "notAssessedByPolicy": ["na_fish"], "overall": {"definition": "ALL_ASSESSED"}}


def rubric():
    return json.load(open(RUBRIC_PATH))


KNOWLEDGE = {"researchVersion": "0000-00-00.1", "rulesVersion": "syn.1", "manifestSha256": "0" * 64, "overlay": None}
