"""Tests for the readiness projections: the what-if arithmetic must equal the real rubric code on the committed bindings table."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_flood_by_operator as P  # noqa: E402
import project_scores as S  # noqa: E402


def rows():
    return json.load(open(S.BINDINGS))["bindings"]


def test_table_is_the_196_lake_population():
    assert len(rows()) == 196


def test_projection_matches_documented_numbers():
    r = rows()
    nv, pa, va = (S.summary(S.score(r, v)) for v in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"))
    assert nv["displayed"] == 5.0 and nv["gates"] == ["validation<=5.0"]       # the validation gate caps
    assert pa["displayed"] == pa["uncapped"] and va["displayed"] == va["uncapped"]
    assert pa["uncapped"] < 8.0 <= va["uncapped"] + 0.05                      # PARTIAL alone never reaches 8.0
    assert round(va["uncapped"] - pa["uncapped"], 1) == 0.8 or round(va["uncapped"] - pa["uncapped"], 1) == 0.7


def test_counts_arithmetic_equals_rubric_code():
    r = rows()
    prof = [S.lake_facts(x) for x in r]
    counts = {
        "sourceAuthority": sum(p["sourceCapability"]["level"] in ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE") for p, _ in prof),
        "operatorPlan": sum(bool(p["operatingPools"]["guideCurve"]["available"] or p["operatingPools"]["operatingZoneSource"]) for p, _ in prof),
        "historyQuality": sum(p["historicalCoverage"]["baselineStatus"] == "SUFFICIENT" for p, _ in prof),
        "seasonalBaseline": sum(p["historicalCoverage"]["baselineStatus"] in ("SUFFICIENT", "LIMITED") for p, _ in prof),
        "trendQuality": len(prof),
        "floodDroughtContext": sum(s["floodPoolState"] != "UNKNOWN" for _, s in prof),
    }
    for v in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
        real = S.summary(S.score(r, v))
        w = S.from_counts(len(r), counts, v)
        assert w["uncapped"] == real["uncapped"] and w["displayed"] == real["displayed"]
        assert {k: w["dims"][k] for k in w["dims"]} == real["dims"]


def test_coverage_gate_and_ladder():
    c = {k: 5 for k in ("sourceAuthority", "operatorPlan", "historyQuality", "seasonalBaseline", "trendQuality", "floodDroughtContext")}
    assert S.from_counts(5, c, "NOT_VALIDATED")["displayed"] == 3.0            # < 10 % profiled: gate 3.0
    assert S.from_counts(466, {k: 466 for k in c}, "VALIDATED")["dims"]["coverage"] == 9   # 75 % of 621
    assert S.from_counts(465, {k: 465 for k in c}, "VALIDATED")["dims"]["coverage"] == 7   # one lake short of 75 %


def test_pilot_history_override_and_plan_derivation():
    p, s = S.lake_facts({"lakeId": "Guntersville|AL", "capability": "DIRECT_OPERATOR_POOL", "historyClass": "NONE",
                         "plan": {"levels": [{"role": "guideCurve"}, {"role": "zoneTop"}, {"role": "zoneBottom"}]}})
    assert p["historicalCoverage"]["baselineStatus"] == "SUFFICIENT" and s["floodPoolState"] == "UNKNOWN"
    p, s = S.lake_facts({"lakeId": "X|ZZ", "capability": "DIRECT_LAKE_GAUGE", "historyClass": "LIMITED", "plan": {"levels": [{"role": "zoneTop"}]}})
    assert not p["operatingPools"]["guideCurve"]["available"] and p["operatingPools"]["operatingZoneSource"] is None   # a top without a bottom is no zone


def test_operator_groups():
    assert P.operator_group("USACE") == "USACE" and P.operator_group("Tennessee Valley Authority") == "TVA"
    assert P.operator_group(None) == "non-federal: unknown"
    out = P.analyse([{"lakeId": "A|AA", "dam": {"operatorName": "State"}, "plan": {"planStrict": False, "floodStrict": True, "verifiedMatch": True,
                                                                               "levels": [{"role": "floodPoolBottom"}]}}],
                    {"A|AA": {"levelLabels": "Top of Conservation; Top of Inactive"}})
    assert out["byGroup"]["non-federal: State"]["flood"] == 1 and out["floodOnlyWithLowerPoolLevel"] == ["A|AA"]
