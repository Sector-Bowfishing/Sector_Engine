"""Tests for the rubric-proposal quantification (docs/brains/LAKE_BRAIN_RUBRIC_PROPOSALS.md).

The central guarantees:
  1. with CURRENT rules the parameterised wrapper EQUALS the production score_lake() (published pilots: displayed 3.0, uncapped 6.3; the 196 table; random fleets);
  2. nothing that scores can load the draft rubric (static scan + dynamic file-access trace + a deployed-image check);
  3. every headline number of the proposals document is recomputed here from committed inputs.
"""
import builtins
import copy
import csv
import datetime as dt
import glob as globmod
import importlib.util
import io
import json
import os
import random
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rubric_proposals as R  # noqa: E402
from sector_brain_platform.scoring import score_lake  # noqa: E402

REPO = R.REPO
NOW = R.NOW


@pytest.fixture(scope="module")
def lakes():
    return R.all_lakes()


def brk(sc):
    return {k: (v["status"], v.get("value"), v["weight"]) for k, v in sc["scoreBreakdown"].items()}


def same_as_production(a, b):
    assert a["value"] == b["value"] and a["uncapped"] == b["uncapped"]
    assert brk(a) == brk(b)
    assert [(g.get("gate"), g.get("cap"), g.get("dimension")) for g in a["scoreBlockers"]] == [(g.get("gate"), g.get("cap"), g.get("dimension")) for g in b["scoreBlockers"]]
    assert a["completenessPct"] == b["completenessPct"] and a["scoreVersion"] == b["scoreVersion"]


# ------------------------------------------------------------------------------------------------ 1. equality with production
def test_published_pilots_score_3_0_uncapped_6_3_in_production_and_in_the_wrapper(lakes):
    """Today's PUBLISHED inputs (read-only copy of the five pilot profiles/states, 2026-10-13) through the unmodified score_lake."""
    prod = score_lake(R.pilots_live_facts(), NOW)
    assert (prod["value"], prod["uncapped"]) == (3.0, 6.3)
    assert {k: v["value"] for k, v in prod["scoreBreakdown"].items()} == {
        "sourceAuthority": 10.0, "operatorPlan": 10.0, "historyQuality": 10.0, "seasonalBaseline": 10.0, "trendQuality": 10.0,
        "floodDroughtContext": 2.0, "validation": 0.0, "coverage": 1.0}
    # the same five lakes rebuilt from the committed table go through the wrapper with CURRENT rules
    wrapped = R.score_variant(R.lakes_for(5, lakes), "NOW", R.CURRENT, "NOT_VALIDATED")
    same_as_production(wrapped, prod)
    # and the table-built production facts equal the published facts field by field that the rubric reads
    published = R.pilots_live_facts()["profiles"]
    built = R.production_facts(R.lakes_for(5, lakes), "NOW", "NOT_VALIDATED")["profiles"]
    # (Hartwell's generated table row names its USGS lake gauge; the live pilot reads the CWMS pool. Both count for sourceAuthority, so the score is the same.)
    pk = lambda p: (p["sourceCapability"]["level"] in ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE"), bool(p["operatingPools"]["guideCurve"]["available"] or p["operatingPools"]["operatingZoneSource"]),
                    p["historicalCoverage"]["baselineStatus"])
    assert sorted(map(pk, published.values())) == sorted(map(pk, built.values()))


def test_pilots_have_the_five_expected_lakes_first(lakes):
    assert [l.lake_id for l in R.lakes_for(5, lakes)] == ["Guntersville|AL", "Lake Hartwell|SC", "Pickwick Lake|TN", "Wheeler|AL", "Wilson|AL"]


@pytest.mark.parametrize("n", [5, 63, 123, 196, 427])
@pytest.mark.parametrize("level", R.EVIDENCE_LEVELS)
@pytest.mark.parametrize("word", ["NOT_VALIDATED", "PARTIAL", "VALIDATED"])
def test_current_rules_equal_production_on_every_fleet(lakes, n, level, word):
    fl = R.lakes_for(n, lakes)
    same_as_production(R.score_variant(fl, level, R.CURRENT, word), score_lake(R.production_facts(fl, level, word), NOW))


def test_current_rules_equal_production_on_random_fleets(lakes):
    rnd = random.Random(20261013)
    for _ in range(120):
        k = rnd.choice([1, 2, 7, 30, 62, 63, 64, 100, 155, 156, 200, 300, 427])
        fl = rnd.sample(lakes, k)
        fl = [R.dataclasses.replace(l, history_class=rnd.choice(["SUFFICIENT", "LIMITED", "INSUFFICIENT", "NONE"]), plan_strict=rnd.random() < .4,
                                    flood_strict=rnd.random() < .5, capability=rnd.choice(["DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE", "NEARBY_GAUGE_PROXY"])) for l in fl]
        level = rnd.choice(R.EVIDENCE_LEVELS)
        word = rnd.choice(["NOT_VALIDATED", "PARTIAL", "VALIDATED"])
        health = rnd.choice(["HEALTHY", "HEALTHY", "FAILED", "UNKNOWN"])
        directory = rnd.choice([621, 621, 300, 1000])
        same_as_production(R.score_variant(fl, level, R.CURRENT, word, health=health, directory=directory),
                           score_lake(R.production_facts(fl, level, word, health, directory), NOW))


def test_empty_fleet_and_unknown_dimensions_equal_production():
    same_as_production(R.score_variant([], "NOW", R.CURRENT, "NOT_VALIDATED"), score_lake(R.production_facts([], "NOW", "NOT_VALIDATED"), NOW))


# ------------------------------------------------------------------------------------------------ facts integrity
def test_fact_table_shape_and_agreement_with_the_committed_196_table(lakes):
    assert len(lakes) == 427 and len({l.lake_id for l in lakes}) == 427
    table = {r["lakeId"]: r for r in json.load(open(R.BINDINGS))["bindings"]}
    ids196 = {l.lake_id for l in lakes if l.in196}
    assert ids196 == set(table) and len(ids196) == 196
    for l in lakes:
        if not l.in196:
            continue
        t = table[l.lake_id]
        p = t.get("plan") or {}
        assert l.plan_strict == bool(p.get("planStrict")) and l.flood_strict == bool(p.get("floodStrict")) and l.matched == bool(p.get("verifiedMatch"))
        assert l.capability == t["capability"] and l.provider == t["provider"]
        want = "SUFFICIENT" if l.lake_id in R.PILOT_HISTORY_SUFFICIENT else t["historyClass"]
        assert l.history_class == want
        assert l.nid_record == bool(t.get("dam"))
        assert l.nid_flood == ((t.get("dam") or {}).get("floodControl"))
    # rollout order: pilots first, then A..D, contiguous 0..195
    assert sorted(l.rollout_idx for l in lakes if l.in196) == list(range(196))
    assert [l.rollout_batch for l in R.lakes_for(196, lakes)][:5] == ["P"] * 5
    assert not any(l.rollout_batch for l in lakes if not l.in196)


def test_fact_file_is_small_and_has_no_species_or_private_columns():
    assert os.path.getsize(R.FACTS_CSV) < 100_000
    head = open(R.FACTS_CSV).readline().strip().split(",")
    assert head == R.FACT_COLUMNS
    assert not re.search(r"species|presence|clarity|bio", ",".join(head), re.I)


def test_wave2_lakes_carry_no_plan_or_flood_credit(lakes):
    w2 = [l for l in lakes if not l.in196 and not l.searched]
    assert len(w2) > 100 and not any(l.plan_strict or l.flood_strict or l.matched for l in w2)


# ------------------------------------------------------------------------------------------------ published / documented numbers (196)
def test_196_table_matches_the_readiness_matrix(lakes):
    fl = R.lakes_for(196, lakes)
    nv, pa, va = (R.score_variant(fl, "NOW", R.CURRENT, w) for w in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"))
    assert R.values(nv) == {"sourceAuthority": 10.0, "operatorPlan": 4.3, "historyQuality": 9.2, "seasonalBaseline": 9.5, "trendQuality": 10.0,
                            "floodDroughtContext": 5.7, "validation": 0.0, "coverage": 5.0}
    assert (nv["uncapped"], nv["value"]) == (6.5, 5.0) and (pa["uncapped"], pa["value"]) == (7.3, 7.3) and (va["uncapped"], va["value"]) == (8.0, 8.0)
    assert round(va["unroundedUncapped"], 3) == 8.045


def test_classification_counts_196(lakes):
    c = R.classification_counts(R.lakes_for(196, lakes), "NOW")
    assert c["flood"] == {"DOCUMENTED": 111, "EXISTS_UNPUBLISHED": 26, "NOT_APPLICABLE": 47, "UNDETERMINED": 12}
    assert c["plan"] == {"CAPTURED": 84, "PUBLISHED_NOT_CAPTURED": 36, "OPERATOR_READ_NO_PLAN": 5, "UNKNOWN": 71}
    assert c["floodExists"] == 137 and c["floodExistsUnpublishedTVA"] == 9
    k = R.classification_counts(R.lakes_for(196, lakes), "KNOWN")
    assert k["flood"]["DOCUMENTED"] == 115 and k["plan"]["CAPTURED"] == 93 and k["floodExists"] == 141
    ce = R.classification_counts(R.lakes_for(196, lakes), "CEILING")
    assert ce["plan"]["CAPTURED"] == 124 and ce["flood"]["DOCUMENTED"] == 141 and "EXISTS_UNPUBLISHED" not in ce["flood"]


def test_class_partition_is_exhaustive_and_disjoint(lakes):
    for l in lakes:
        for lev in R.EVIDENCE_LEVELS:
            assert R.flood_class(l, lev) in ("DOCUMENTED", "EXISTS_UNPUBLISHED", "NOT_APPLICABLE", "UNDETERMINED")
            assert R.plan_class(l, lev) in ("CAPTURED", "PUBLISHED_NOT_CAPTURED", "OPERATOR_READ_NO_PLAN", "UNKNOWN")
            # evidence only ever moves lakes toward documented, never away
            if R.flood_class(l, "NOW") == "DOCUMENTED":
                assert R.flood_class(l, lev) == "DOCUMENTED"
            if R.plan_class(l, "NOW") == "CAPTURED":
                assert R.plan_class(l, lev) == "CAPTURED"


# ------------------------------------------------------------------------------------------------ P1 flood denominator
def test_p1_numbers(lakes):
    f196 = R.lakes_for(196, lakes)
    assert R.values(R.score_variant(f196, "NOW", R.P1X, "NOT_VALIDATED"))["floodDroughtContext"] == 8.1      # 111 / 137
    assert R.values(R.score_variant(f196, "NOW", R.P1C, "NOT_VALIDATED"))["floodDroughtContext"] == 7.4      # 111 / 149
    assert round(10 * 111 / 137, 1) == 8.1 and round(10 * 111 / 149, 1) == 7.4
    pilots = R.lakes_for(5, lakes)
    assert R.values(R.score_variant(pilots, "NOW", R.P1X, "NOT_VALIDATED"))["floodDroughtContext"] == 2.5   # 1 documented / 4 pools (Wheeler NOT_APPLICABLE)
    assert R.values(R.score_variant(pilots, "NOW", R.CURRENT, "NOT_VALIDATED"))["floodDroughtContext"] == 2.0
    # TVA stays in the denominator (a pool exists, the operator publishes no bottom): excluding the 9 silent TVA lakes would be 111/128
    assert round(10 * 111 / (137 - 9), 1) == 8.7


def test_p1_changes_only_the_flood_dimension(lakes):
    for n in (5, 63, 196, 427):
        fl = R.lakes_for(n, lakes)
        base, new = R.values(R.score_variant(fl, "NOW", R.CURRENT, "VALIDATED")), R.values(R.score_variant(fl, "NOW", R.P1X, "VALIDATED"))
        assert {k: v for k, v in base.items() if k != "floodDroughtContext"} == {k: v for k, v in new.items() if k != "floodDroughtContext"}
        assert new["floodDroughtContext"] >= base["floodDroughtContext"]


def test_p1_never_credits_unknown_as_known_and_never_inflates_a_complete_denominator(lakes):
    # when every lake is DOCUMENTED the proposal equals the current rule
    fl = [R.dataclasses.replace(l, flood_strict=True) for l in R.lakes_for(63, lakes)]
    assert R.values(R.score_variant(fl, "NOW", R.P1X, "VALIDATED"))["floodDroughtContext"] == R.values(R.score_variant(fl, "NOW", R.CURRENT, "VALIDATED"))["floodDroughtContext"] == 10.0
    # a fleet with no flood pool at all: dimension UNKNOWN (contributes 0), NOT forgiven to 10
    none = [R.dataclasses.replace(l, flood_strict=False, tier2_flood=False, nid_flood=False) for l in R.lakes_for(63, lakes)]
    sc = R.score_variant(none, "NOW", R.P1X, "VALIDATED")
    assert sc["scoreBreakdown"]["floodDroughtContext"]["status"] == "UNKNOWN"
    assert sc["uncapped"] < R.score_variant(none, "NOW", R.CURRENT, "VALIDATED")["uncapped"] + 0.06


# ------------------------------------------------------------------------------------------------ P3 plan denominator
def test_p3_numbers(lakes):
    f196 = R.lakes_for(196, lakes)
    assert R.values(R.score_variant(f196, "NOW", R.P3X, "NOT_VALIDATED"))["operatorPlan"] == 7.0   # 84 / 120
    assert R.values(R.score_variant(f196, "NOW", R.P3C, "NOT_VALIDATED"))["operatorPlan"] == 4.4   # 84 / (84 + 36 + 71)
    assert round(10 * 84 / 120, 1) == 7.0 and round(10 * 84 / (84 + 36 + 71), 1) == 4.4
    ce = R.lakes_for(196, lakes)
    assert R.values(R.score_variant(ce, "CEILING", R.P3X, "NOT_VALIDATED"))["operatorPlan"] == 10.0   # degenerate by construction, flagged in the document
    assert R.values(R.score_variant(ce, "CEILING", R.P3C, "NOT_VALIDATED"))["operatorPlan"] == 6.5   # 124 / 191


def test_p3_changes_only_the_plan_dimension(lakes):
    for n in (5, 63, 196, 427):
        fl = R.lakes_for(n, lakes)
        base, new = R.values(R.score_variant(fl, "KNOWN", R.CURRENT, "VALIDATED")), R.values(R.score_variant(fl, "KNOWN", R.P3X, "VALIDATED"))
        assert {k: v for k, v in base.items() if k != "operatorPlan"} == {k: v for k, v in new.items() if k != "operatorPlan"}


def test_p3x_is_a_capture_rate_not_an_availability_rate(lakes):
    """Adding UNKNOWN lakes to the fleet cannot lower P3-X, but lowers the current rule: this is the gaming surface the document flags."""
    base = R.lakes_for(63, lakes)
    unknown = [l for l in lakes if R.plan_class(l, "NOW") == "UNKNOWN" and l.in196 and l not in base][:30]
    a = R.values(R.score_variant(base, "NOW", R.P3X, "VALIDATED"))["operatorPlan"]
    b = R.values(R.score_variant(base + unknown, "NOW", R.P3X, "VALIDATED"))["operatorPlan"]
    c0, c1 = (R.values(R.score_variant(x, "NOW", R.CURRENT, "VALIDATED"))["operatorPlan"] for x in (base, base + unknown))
    assert a == b and c1 < c0


# ------------------------------------------------------------------------------------------------ P2 claims
def test_claims_rule_min_over_counted_families_and_withholding(lakes):
    fl = R.lakes_for(196, lakes)
    N, P, V = "NOT_VALIDATED", "PARTIAL", "VALIDATED"
    fam = lambda a, b, c, d: {"providerDisplay": a, "deterministicDerivation": b, "historicalState": c, "rapidChange": d}
    d, gate = R.validation_dim(R.P2, fam(P, P, P, N))
    assert d["value"] == 0 and gate                                       # a published family that failed blocks everything (today's reality for RAPID)
    d, gate = R.validation_dim(R.P2W, fam(P, P, P, N))
    assert d["value"] == 5 and not gate                                   # RAPID withheld: not counted
    d, gate = R.validation_dim(R.P2W, fam(V, V, P, N))
    assert d["value"] == 5                                                # weakest counted family rules
    d, gate = R.validation_dim(R.P2W, fam(V, V, V, N))
    assert d["value"] == 10 and not gate
    d, gate = R.validation_dim(R.P2, "VALIDATED")
    assert d["value"] == 10                                               # a bare word applies to every family
    d, gate = R.validation_dim(R.P2WH, fam(V, V, N, N))
    assert d["value"] == 10                                               # OUT OF SCOPE variant, shown only to prove the cost of an early floor
    all_withheld = R.Rules(validation="claims", withhold_rapid=True, withhold_historical=True)
    d, gate = R.validation_dim(all_withheld, fam(N, N, N, N))
    assert d["value"] == 0                                                # Level 1/2 still counted
    d, gate = R.validation_dim(R.P2, "NOT_VALIDATED")
    assert d["value"] == 0 and gate
    assert R.score_variant(fl, "NOW", R.P2, "NOT_VALIDATED")["value"] == 5.0


def test_claims_rule_equals_the_word_rule_when_families_agree(lakes):
    for n in (5, 63, 196):
        fl = R.lakes_for(n, lakes)
        for w in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
            a, b = R.score_variant(fl, "NOW", R.CURRENT, w), R.score_variant(fl, "NOW", R.P2, w)
            assert (a["value"], a["uncapped"], R.values(a)) == (b["value"], b["uncapped"], R.values(b))


def test_claims_scenario_table_196(lakes):
    rows = {r["scenario"][:2]: r for r in R.claims_effect(lakes)}
    assert (rows["S0"]["validationDim"], rows["S0"]["displayed"], rows["S0"]["gates"]) == (0.0, 5.0, ["validation"])
    assert (rows["S2"]["validationDim"], rows["S2"]["displayed"]) == (0.0, 5.0)                 # RAPID published and failed: still capped
    assert (rows["S3"]["validationDim"], rows["S3"]["uncapped"], rows["S3"]["displayed"], rows["S3"]["gates"]) == (5.0, 7.3, 7.3, [])
    assert (rows["S4"]["validationDim"], rows["S4"]["displayed"]) == (5.0, 7.3)
    assert (rows["S5"]["validationDim"], rows["S5"]["displayed"]) == (10.0, 8.0)
    assert (rows["S4"]["meanDim"], rows["S4"]["meanDisplayed"]) == (8.3, 7.8)                    # averaging WOULD pass the 7.5 floor at PARTIAL (not proposed)
    assert rows["S6"]["validationDim"] == 10.0


def test_other_gates_are_untouched_by_the_claims_rule(lakes):
    five = R.lakes_for(5, lakes)
    assert R.score_variant(five, "NOW", R.P2W, "VALIDATED")["value"] == 3.0                    # coverage gate still caps the pilots
    assert R.score_variant(R.lakes_for(63, lakes), "NOW", R.P2W, "VALIDATED", health="FAILED")["value"] == 2.0   # health gate still fires


# ------------------------------------------------------------------------------------------------ the key honest answer
def test_validation_is_the_only_critical_dimension_that_can_fail_and_it_needs_validated(lakes):
    for n in (63, 196, 427):
        for lev in ("KNOWN", "CEILING"):
            for name in R.VARIANTS:
                pa = R.max_achievable(lakes, name, n, lev, "PARTIAL")
                assert not pa["target"] and pa["weakestCritical"] == "validation" and pa["critical"]["validation"] == 5.0
                va = R.max_achievable(lakes, name, n, lev, "VALIDATED")
                assert va["criticalOk"], (n, lev, name, va["critical"])
                assert min(v for k, v in va["critical"].items() if k != "validation") >= 8.5   # the four correctness dimensions are not the constraint


def test_target_with_the_current_rubric_on_documented_evidence(lakes):
    m = {n: R.max_achievable(lakes, "CURRENT", n, "NOW") for n in (63, 196, 427)}
    assert not m[63]["target"] and m[63]["displayed"] == 7.7                                     # 10 % rung, 3 coverage points
    assert m[196]["target"] and m[196]["unrounded"] == 8.045                                      # on the line
    assert m[427]["target"] and m[427]["displayed"] == 8.1
    # the ladder is what moves it: smallest nested fleet that reaches 8.0 is the 25 % rung (156 lakes)
    assert R.first_reaching_n(R.lakes_for(196, lakes), "CURRENT", "NOW") == 156
    assert R.score_variant(R.lakes_for(196, lakes)[:155], "NOW", R.CURRENT, "VALIDATED")["value"] < 8.0 <= R.score_variant(R.lakes_for(196, lakes)[:156], "NOW", R.CURRENT, "VALIDATED")["value"]


def test_63_lake_gap_is_not_closed_by_flood_alone(lakes):
    h = R.headroom(lakes, "NOW", "CURRENT", 63)
    assert h["gapPoints"] == 28.5 and h["room"]["floodDroughtContext"] == 25.5 and "floodDroughtContext" not in h["closedBy"]
    assert "operatorPlan" in h["closedBy"]


def test_pilots_only_can_never_display_more_than_3(lakes):
    for name in R.VARIANTS:
        for st in R.VMAP:
            for lev in R.EVIDENCE_LEVELS:
                assert R.score_variant(R.lakes_for(5, lakes), lev, R.VARIANTS[name], st)["value"] <= 3.0
    assert R.score_variant(R.lakes_for(5, lakes), "NOW", R.CURRENT, "VALIDATED")["uncapped"] == 7.8      # underlying 7.8, displayed 3.0


def test_p1_and_p3_never_lower_the_score_and_never_touch_criticals(lakes):
    for n in (63, 196, 427):
        for lev in R.EVIDENCE_LEVELS:
            cur = R.score_variant(R.lakes_for(n, lakes), lev, R.CURRENT, "VALIDATED")
            for name in ("P1-X", "P1-C", "P3-X", "P3-C", "ALL (X)", "ALL (C)"):
                new = R.score_variant(R.lakes_for(n, lakes), lev, R.VARIANTS[name], "VALIDATED")
                assert new["uncapped"] >= cur["uncapped"] and all(R.values(new)[k] == R.values(cur)[k] for k in R.CRITICAL)


def test_rounding_assist_is_detected():
    sc = {"value": 8.0, "unroundedUncapped": 7.97, **{"scoreBreakdown": {k: {"value": 10.0, "status": "SCORED", "weight": 1} for k in R.DIM_ORDER}}}
    assert R.critical_report(sc)["roundingAssist"] is True


def test_earliest_dates():
    e = R.earliest(R.LEDGER_DAY0)
    assert e["partial"] == dt.date(2027, 1, 11) and e["validated"] == dt.date(2027, 10, 13)
    later = R.earliest(dt.date(2026, 11, 15))
    assert later["validated"] == dt.date(2027, 11, 15)


def test_order_sensitivity_is_deterministic_and_nested(lakes):
    a = R.hash_order(lakes, 3)
    assert [l.lake_id for l in a] == [l.lake_id for l in R.hash_order(lakes, 3)] and [l.lake_id for l in a[:5]] == [l.lake_id for l in R.lakes_for(5, lakes)]
    assert len(a) == 196 and {l.lake_id for l in a} == {l.lake_id for l in lakes if l.in196}
    assert [l.lake_id for l in a] != [l.lake_id for l in R.hash_order(lakes, 4)]


# ------------------------------------------------------------------------------------------------ JSON patches and draft files
def test_patches_apply_to_v1_and_touch_only_intended_paths():
    base = R.v1()
    assert sum(d["weight"] for d in base["dimensions"]) == 100
    ids = [d["id"] for d in base["dimensions"]]
    assert ids == list(R.DIM_ORDER)                                   # patch indexes (/dimensions/1, 5, 6) depend on this order
    assert [g["id"] for g in base["gates"]] == ["coverage", "validation", "health"]
    touched = {"P1-X": "floodDroughtContext", "P1-C": "floodDroughtContext", "P3-X": "operatorPlan", "P3-C": "operatorPlan", "P2": "validation"}
    for name, ops in R.PATCHES.items():
        new = R.apply_patch(base, ops)
        for d_old, d_new in zip(base["dimensions"], new["dimensions"]):
            if d_old["id"] != touched[name]:
                assert d_old == d_new, (name, d_old["id"])
        assert [d["weight"] for d in new["dimensions"]] == [d["weight"] for d in base["dimensions"]]    # weights never change
        assert new["gates"][0] == base["gates"][0] and new["gates"][2] == base["gates"][2]
        if name != "P2":
            assert new["gates"] == base["gates"]
    assert R.apply_patch(base, R.PATCHES["P2"])["gates"][1]["cap"] == 5.0
    with pytest.raises(KeyError):
        R.apply_patch(base, [{"op": "replace", "path": "/dimensions/5/nonexistent", "value": 1}])
    with pytest.raises(KeyError):
        R.apply_patch(base, [{"op": "add", "path": "/dimensions/5/label", "value": 1}])


def test_apply_patch_does_not_mutate_its_input():
    base = R.v1()
    snap = copy.deepcopy(base)
    R.apply_patch(base, R.PATCHES["P2"])
    assert base == snap


def test_live_rubric_is_unchanged_and_drafts_are_current():
    v1 = R.v1()
    assert v1["scoreVersion"] == "lake-brain-score-v1" and "status" not in v1 and "proposedCriticalDimensions" not in v1
    assert [d["id"] for d in v1["dimensions"]] == list(R.DIM_ORDER)
    assert {d["id"]: d["weight"] for d in v1["dimensions"]} == R.WEIGHTS
    # v1 is byte-identical to the base branch version (the proposals branch never edits it)
    base = subprocess.run(["git", "-C", REPO, "show", "origin/feat/lake-opsvis-on-durability:docs/brains/scoring/lake-brain-score-v1.json"], capture_output=True, text=True)
    if base.returncode == 0:
        assert open(R.RUBRIC_V1).read() == base.stdout
    for name, doc in (("lake-brain-score-v2-DRAFT.json", R.draft_rubric()), ("lake-brain-score-v1-to-v2-DRAFT.patch.json", R.patch_file())):
        assert json.load(open(os.path.join(R.PROPOSED_DIR, name))) == doc, name + " is stale: run rubric_proposals.py --write-drafts"
    d = R.draft_rubric()
    assert d["scoreVersion"] == "lake-brain-score-v2-DRAFT" and d["status"].startswith("DRAFT PROPOSAL - NOT LOADED")
    assert sum(x["weight"] for x in d["dimensions"]) == 100 and d["proposedCriticalDimensions"] == list(R.CRITICAL)


# ------------------------------------------------------------------------------------------------ 2. the scorer cannot load the draft
def _load_score_brains():
    path = os.path.join(REPO, "jobs", "brain-scores", "score_brains.py")
    spec = importlib.util.spec_from_file_location("score_brains_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _python_sources(root):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".build", ".venv", "node_modules"}]
        for f in files:
            if f.endswith((".py", ".sh", ".yml", ".yaml", ".toml", ".json")) or f == "Dockerfile":
                yield os.path.join(dirpath, f)


def test_no_code_or_deploy_script_references_the_proposed_directory():
    mine = {os.path.abspath(__file__), os.path.abspath(R.__file__)}
    hits = []
    n = 0
    for root in (os.path.join(REPO, "jobs"), os.path.join(REPO, "scripts")):
        for p in _python_sources(root):
            if os.path.abspath(p) in mine or p.endswith(".json") and "readiness/data" in p:
                continue
            n += 1
            txt = open(p, errors="ignore").read()
            if re.search(r"scoring/proposed|score-v2-DRAFT|-DRAFT\.json|DRAFT\.patch", txt):
                hits.append(p)
    assert n > 100, "sanity: the scan must have looked at files"
    assert hits == []


def test_scorer_never_reads_the_rubric_json_or_any_scoring_directory_listing(monkeypatch):
    """score_lake and score_brains.compute are exercised with every file/dir access recorded: only frozen-scores.json may be opened, nothing is listed or globbed."""
    sb = _load_score_brains()
    opened, listed = [], []
    real_open, real_io_open = builtins.open, io.open
    real_listdir, real_scandir, real_glob = os.listdir, os.scandir, globmod.glob

    def rec_open(f, *a, **k):
        opened.append(os.path.abspath(str(f)))
        return real_open(f, *a, **k)

    def rec_io_open(f, *a, **k):
        opened.append(os.path.abspath(str(f)))
        return real_io_open(f, *a, **k)

    monkeypatch.setattr(builtins, "open", rec_open)
    monkeypatch.setattr(io, "open", rec_io_open)
    monkeypatch.setattr(os, "listdir", lambda p=".": (listed.append(str(p)), real_listdir(p))[1])
    monkeypatch.setattr(os, "scandir", lambda p=".": (listed.append(str(p)), real_scandir(p))[1])
    monkeypatch.setattr(globmod, "glob", lambda *a, **k: (listed.append(str(a)), real_glob(*a, **k))[1])
    score_lake(R.pilots_live_facts(), NOW)
    facts = {"lake": R.pilots_live_facts(), "biological": {}, "intelligence": {}}
    scores = sb.compute(facts, NOW)
    assert scores["lake-brain"]["scoreVersion"] == "lake-brain-score-v1" and scores["lake-brain"]["value"] == 3.0
    scoring_dir = os.path.join(REPO, "docs", "brains", "scoring")
    touched = [p for p in opened if p.startswith(scoring_dir)]
    assert {os.path.basename(p) for p in touched} <= {"frozen-scores.json"}
    assert not [p for p in opened if "proposed" in p or "lake-brain-score" in p]
    assert not [p for p in listed if "scoring" in p]


def test_draft_presence_cannot_change_any_score(tmp_path):
    """A copy of the scoring directory with and without proposed/ gives byte-identical score output (FROZEN_SCORES pointed at each copy)."""
    sb = _load_score_brains()
    src = os.path.join(REPO, "docs", "brains", "scoring")
    import shutil
    outs = []
    for with_draft in (False, True):
        d = tmp_path / ("with" if with_draft else "without")
        shutil.copytree(src, d, ignore=None if with_draft else shutil.ignore_patterns("proposed"))
        assert os.path.isdir(d / "proposed") == with_draft
        sb.FROZEN = str(d / "frozen-scores.json")
        facts = {"lake": R.pilots_live_facts(), "biological": {}, "intelligence": {}}
        outs.append(json.dumps(sb.compute(facts, NOW), sort_keys=True, default=str))
    assert outs[0] == outs[1]


def test_the_scorer_hard_codes_its_rules_so_editing_the_json_cannot_change_a_score():
    """The rubric JSON is documentation: scoring.py contains the weights and gates. (Adopting a proposal therefore needs a scorer change, not a JSON edit.)"""
    src = open(os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform", "scoring.py")).read()
    assert "json.load" not in src and "import json" not in src
    for token in ('dim("floodDroughtContext", 5', 'dim("operatorPlan", 10', 'dim("validation", 15', '"cap": 5.0'):
        assert token in src


def test_orchestrator_image_stages_only_frozen_scores_from_the_scoring_directory():
    sh = open(os.path.join(REPO, "jobs", "brain-orchestrator", "deploy-job.sh")).read()
    staged = re.findall(r'cp[^\n]*docs/brains/scoring[^\n]*', sh)
    assert staged and all("frozen-scores.json" in s for s in staged)
    assert "cp -R \"$ROOT/docs" not in sh


def test_module_is_offline_and_read_only():
    src = open(R.__file__).read()
    for banned in ("urllib", "requests", "socket", "http.client", "subprocess", "firebase", "gcloud", "shutil.rmtree", "os.remove"):
        assert banned not in src, banned

