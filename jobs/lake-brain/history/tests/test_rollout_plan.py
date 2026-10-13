"""Tests for rollout_plan.py: batch selection, cost model and the score projection (which calls the real score_lake)."""
import datetime as dt
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preseed_fleet as P
import rollout_plan as R

NOW = P.parse_iso("2026-10-13T20:00:00Z")
HAVE_TABLE = os.path.exists(P.DEFAULT_BINDINGS)


def synth_row(i, host="cwms", years=20, plan=True, flood=True, age=1.0, cap="DIRECT_OPERATOR_POOL", live="cwms"):
    hist = {"cwms": dict(kind="cwmsDaily", office="XX", series=f"L{i}.Elev.Inst.~1Day.0.MRS"), "usgs": dict(kind="usgsDaily", site=str(i), param="62615", stat="dv", offsetFt=0.0),
            "hads": dict(kind="hadsDaily", lid=f"L{i}", pe="HP", offsetFt=0.0), "rise": dict(kind="riseDaily", item=str(i))}[host]
    levels = ([dict(role="zoneTop"), dict(role="zoneBottom")] if plan else []) + ([dict(role="floodPoolBottom")] if flood else [])
    return dict(lakeId=f"S{i:03d} Lake|ZZ", status="MACHINE_VERIFIED", capability=cap, provider=live, live=[dict(provider=live, station="X", series="s")],
                history=[hist], historyCompleteYears=years, historyClass="SUFFICIENT" if years >= 5 else "LIMITED" if years >= 2 else "NONE", historyFirstYear=2026 - years,
                plan=dict(levels=levels, planStrict=True, floodStrict=True) if levels else None, verification=dict(probe=dict(ageHours=age)), historyNotes=[])


def rows_of(n, **kw):
    return {r["lakeId"]: r for r in (synth_row(i, **kw) for i in range(n))}


def test_projection_matches_the_real_scorer_gate_logic_with_synthetic_lakes():
    rows = rows_of(70)
    ids = sorted(rows)
    pilots = set(ids[:5])
    # 5 profiled of 621: coverage gate (cap 3.0) and validation gate
    s = R.score(rows, set(ids[:5]), pilots, NOW)
    assert s["value"] == 3.0 and {g["gate"] for g in s["scoreBlockers"] if "gate" in g} == {"coverage", "validation"}
    # 62 lakes = 9.98 % -> still gated; 63 = 10.14 % -> coverage gate lifts, validation still caps at 5.0
    assert R.score(rows, set(ids[:62]), pilots, NOW)["value"] == 3.0
    s63 = R.score(rows, set(ids[:63]), pilots, NOW)
    assert s63["value"] == min(5.0, s63["uncapped"]) and {g["gate"] for g in s63["scoreBlockers"] if "gate" in g} == {"validation"}
    # validation never lifts by itself here; PARTIAL would add 5 points of weight 15 (a different, unassumed scenario)
    assert R.score(rows, set(ids[:63]), pilots, NOW, validation="PARTIAL")["uncapped"] > s63["uncapped"]


def test_observed_share_marks_the_stalest_probe_lakes_unobserved():
    rows = {f"S{i:03d} Lake|ZZ": synth_row(i, age=float(i)) for i in range(20)}
    pilots = set()
    profiles, states = R.build_facts(rows, set(rows), pilots, observed_share=0.9)
    unobs = sorted(k for k, v in states.items() if v["kind"] != "observed")
    assert unobs == ["S018 Lake|ZZ", "S019 Lake|ZZ"] and all(states[k]["floodPoolState"] == "UNKNOWN" for k in unobs)


def test_plan_facts_and_baseline_status():
    assert R.plan_facts(synth_row(1, plan=False, flood=True)) == dict(plan=False, flood=True)
    assert R.plan_facts(synth_row(1, plan=True, flood=False)) == dict(plan=True, flood=False)
    assert R.plan_facts(dict(plan=dict(tvaOperatingGuide="X", levels=[dict(role="guideCurve")]))) == dict(plan=True, flood=False)
    assert R.plan_facts({}) == dict(plan=False, flood=False)
    assert R.baseline_status(synth_row(1, years=7)) == "SUFFICIENT" and R.baseline_status(synth_row(1, years=3)) == "LIMITED"
    assert R.baseline_status(synth_row(1, years=0)) == "INSUFFICIENT"
    tva = dict(synth_row(1), history=[dict(kind="tvaOperatingGuide", locationId="X")], historyClass="NONE")
    assert R.baseline_status(tva) == "INSUFFICIENT"


def test_throughput_aggregation(tmp_path):
    st = {"lakes": {"A": {"metrics": {"byHost": {"cwms": {"calls": 10, "bytes": 1000, "netSeconds": 12.0}}}},
                    "B": {"metrics": {"byHost": {"cwms": {"calls": 10, "bytes": 3000, "netSeconds": 8.0}, "hads": {"calls": 2, "bytes": 10, "netSeconds": 44.0}}}},
                    "C": {}}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(st))
    t = R.throughput_from_states([str(p)])
    assert t["perHost"]["cwms"]["secondsPerCall"] == 1.0 and t["perHost"]["hads"]["secondsPerCall"] == 22.0 and t["lakes"] == ["A", "B"]
    q = tmp_path / "t.json"
    q.write_text(json.dumps(t))
    assert R.load_throughput(str(q)) == {"cwms": 1.0, "hads": 22.0}


def test_batches_partition_and_follow_the_declared_rules():
    rows = {}
    for i in range(30):
        rows.update({f"S{i:03d} Lake|ZZ": synth_row(i, host=["cwms", "usgs", "rise", "hads"][i % 4], years=20 if i % 5 else 8)})
    rows["P1 Lake|ZZ"] = synth_row(900)
    rows["P1 Lake|ZZ"]["lakeId"] = "P1 Lake|ZZ"
    batches, info = R.select_batches(rows, {"P1 Lake|ZZ"}, NOW, None, dict(R.DEFAULT_SECONDS_PER_CALL))
    flat = [l for v in batches.values() for l in v]
    assert len(flat) == len(set(flat)) == 30 and "P1 Lake|ZZ" not in flat
    for l in batches["B"]:
        assert info[l]["years"] >= R.B_MIN_COMPLETE_YEARS and info[l]["host"] in ("cwms", "usgs", "rise") and info[l]["probeAgeH"] <= rows[l]["live"][0].get("lagMin", 0) / 60.0 + R.B_PROBE_AGE_SLACK_H
    for l in batches["C"]:
        assert info[l]["host"] == "hads" or info[l]["estSeconds"] > R.B_MAX_EST_SECONDS or info[l]["historyStat"] == "iv"
    for l in batches["D"]:
        assert info[l]["years"] < R.B_MIN_COMPLETE_YEARS and info[l]["host"] != "hads"          # fast, fresh, but not well seeded (8 years)
    keys = {(info[l]["liveProvider"], info[l]["historyKind"], info[l]["historyStat"]) for l in batches["A"] if info[l]["host"] != "hads"}
    assert len(keys) == len([l for l in batches["A"] if info[l]["host"] != "hads"])        # one canary per provider/kind combination
    assert sum(1 for l in batches["A"] if info[l]["host"] == "hads") <= 1
    again, _ = R.select_batches(rows, {"P1 Lake|ZZ"}, NOW, None, dict(R.DEFAULT_SECONDS_PER_CALL))
    assert again == batches


@pytest.mark.skipif(not HAVE_TABLE, reason="bindings table missing")
def test_real_table_projection_reproduces_the_published_pilot_score():
    doc, rows = P.load_bindings(P.DEFAULT_BINDINGS)
    pilots = {p["lakeId"] for p in doc["pilotReproduction"]}
    assert len(pilots) == 5
    s = R.score(rows, set(pilots), pilots, NOW)
    # published /scores/lake-brain at 2026-10-13T18:58:18Z: value 3.0, uncapped 6.3, coverage 1.0, floodDroughtContext 2.0
    assert s["value"] == 3.0 and s["uncapped"] == 6.3
    assert s["scoreBreakdown"]["coverage"]["value"] == 1.0 and s["scoreBreakdown"]["floodDroughtContext"]["value"] == 2.0
    assert s["scoreBreakdown"]["operatorPlan"]["value"] == 10.0 and s["scoreBreakdown"]["historyQuality"]["value"] == 10.0


@pytest.mark.skipif(not HAVE_TABLE, reason="bindings table missing")
def test_real_table_batches_cover_every_non_pilot_once_and_projection_is_capped_at_5():
    doc, rows = P.load_bindings(P.DEFAULT_BINDINGS)
    pilots = {p["lakeId"] for p in doc["pilotReproduction"]}
    batches, info = R.select_batches(rows, pilots, NOW, None, dict(R.DEFAULT_SECONDS_PER_CALL))
    flat = [l for v in batches.values() for l in v]
    assert len(flat) == len(set(flat)) == 191 and set(flat) == set(rows) - pilots
    proj = R.project(rows, pilots, batches, NOW)
    assert [p["profiled"] for p in proj] == [5, 5 + len(batches["A"]), 5 + len(batches["A"]) + len(batches["B"]),
                                             5 + len(batches["A"]) + len(batches["B"]) + len(batches["C"]), 196]
    assert all(p["displayed"] <= 5.0 for p in proj) and proj[0]["displayed"] == 3.0
    for p in proj:                                                  # the coverage gate is on exactly while fewer than 63 lakes are profiled
        assert ("coverage" in p["gates"]) == (p["profiled"] < 63)
        assert p["displayed"] == min(p["uncapped"], 3.0 if p["profiled"] < 63 else 5.0)


@pytest.mark.skipif(not HAVE_TABLE, reason="bindings table missing")
def test_cli_writes_json(tmp_path):
    out = tmp_path / "plan.json"
    assert R.main(["--out", str(out)]) == 0
    d = json.load(open(out))
    assert set(d["batches"]) == {"A", "B", "C", "D"} and len(d["projection"]) == 5


@pytest.mark.skipif(not HAVE_TABLE, reason="bindings table missing")
def test_accepted_restricts_the_batches(tmp_path):
    doc, rows = P.load_bindings(P.DEFAULT_BINDINGS)
    pilots = sorted(p["lakeId"] for p in doc["pilotReproduction"])
    keep = sorted(set(rows) - set(pilots))[:30]
    acc = tmp_path / "accepted_batch.json"
    acc.write_text(json.dumps(sorted(keep + pilots)))
    out = tmp_path / "p.json"
    assert R.main(["--accepted", str(acc), "--out", str(out)]) == 0
    d = json.load(open(out))
    flat = [l for v in d["batches"].values() for l in v["lakes"]]
    assert sorted(flat) == keep and d["projection"][-1]["profiled"] == 35


@pytest.mark.skipif(not HAVE_TABLE, reason="bindings table missing")
def test_emit_stage_is_a_cumulative_subset_of_the_accepted_batch(tmp_path):
    doc, rows = P.load_bindings(P.DEFAULT_BINDINGS)
    pilots = sorted(p["lakeId"] for p in doc["pilotReproduction"])
    keep = sorted(set(rows) - set(pilots))[:80]
    acc = tmp_path / "accepted_batch.json"
    acc.write_text(json.dumps(sorted(keep)))
    seen = []
    for st in "ABCD":
        out = tmp_path / f"stage_{st}.json"
        assert R.main(["--accepted", str(acc), "--emit-stage", st, "--out", str(out)]) == 0
        d = json.load(open(out))
        assert d["stage"] == st and set(d["lakeIds"]) <= set(keep) and not set(d["lakeIds"]) & set(pilots)
        assert d["stagedFromAcceptedBatchSha256"] == P.sha256_file(str(acc))
        assert set(seen) <= set(d["lakeIds"]) and len(d["lakeIds"]) >= len(seen)
        seen = d["lakeIds"]
    assert seen == keep
    with pytest.raises(SystemExit):
        R.main(["--emit-stage", "A"])
