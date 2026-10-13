"""Tests for the prediction-ledger scorer: synthetic ledgers with known answers. Run:  python -m pytest jobs/lake-brain/ledger -q"""
import datetime as dt
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_predictions as S  # noqa: E402

LAKE = "Test Lake|TN"
KEY = "Test_Lake_TN"
AS_OF = dt.date(2026, 10, 12)


def day(n):  # n = day of October 2026
    return dt.date(2026, 10, 1) + dt.timedelta(days=n - 1)


BAND = {"p02": 9.0, "p10": 10.0, "p50": 15.0, "p90": 20.0, "p98": 21.0}


def record(base, *, lake=LAKE, run="r1", gen=None, label="STABLE", floor=0.1, rapid=0.5, kind="OBSERVED", tier="FULL",
           provider="tva", pool="fullPool", band=BAND, rate_p95=0.3, horizons=(1, 7, 30), version="lake-prediction-ledger-v1",
           obs_at=None, rules="lake-level-rules-v2", binding="bindings-test.1", tz="America/Chicago", targets=None):
    b = dt.date.fromisoformat(base)
    return {
        "ledgerVersion": version, "rulesVersion": rules, "runId": run, "generatedAt": gen or f"{base}T12:30:00Z", "lakeId": lake, "baseDate": base,
        "bindingVersion": binding, "baselineMethod": "doy15-percentile-v2", "timeZone": tz,
        "observation": {"at": obs_at or f"{base}T12:00:00Z", "ft": 15.0},
        "kind": kind, "provider": provider, "poolBasis": pool, "historicalTier": tier,
        "labels": {"levelState": "IN_ZONE", "historicalState": "NORMAL", "trendState": label, "floodPoolState": "UNKNOWN"},
        "rapidThresholdFt": rapid, "stableFloorFt": floor,
        "horizons": [{"days": h, "targetDate": (targets or {}).get(h) or (b + dt.timedelta(days=h)).isoformat(), "doy": 1,
                      **({"band": dict(band), "bandN": 100} if band else {}), **({"rateP95": rate_p95} if rate_p95 is not None else {})}
                     for h in horizons],
    }


def write_ledger(root, records_by_object):
    for name, recs in records_by_object.items():
        p = os.path.join(root, "predictions", "2026", "10", name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            for r in recs:
                fh.write((r if isinstance(r, str) else json.dumps(r, sort_keys=True)) + "\n")


def write_history(root, series, lake=LAKE):
    p = os.path.join(root, "history", S.lake_key(lake), "daily.csv")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("date,elevationFt,sourceId\n")
        for d in sorted(series):
            fh.write(f"{d},{series[d]:.2f},t\n")


def score(root, **kw):
    return S.score_month(S.LocalSource(root), S.LocalSource(root), "2026-10", kw.pop("as_of", AS_OF), kw.pop("grace", 3))


def h(group, days):
    return group["horizons"][str(days)]


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


def known_coverage_ledger(root):
    """10 base dates Oct 1..10, horizon +1 only. Realised on the target day: 8 inside [10,20]; 1 in [9,10) (inside p02..p98, outside p10..p90); 1 above p98."""
    vals = [12, 15, 18, 10.0, 20.0, 14, 16, 9.5, 25.0, 11]       # for targets Oct 2..11
    recs = [record(day(i + 1).isoformat(), horizons=(1,)) for i in range(10)]
    series = {day(i + 2).isoformat(): v for i, v in enumerate(vals)}
    write_ledger(root, {"01/120000Z-r1.jsonl": recs})
    write_history(root, series)


def test_coverage_and_tail_rates_match_the_known_answer(root):
    known_coverage_ledger(root)
    g = score(root)["primary"]["overall"]
    x = h(g, 1)
    assert (x["predictions"], x["scored"], x["pending"], x["missingRealised"]) == (10, 10, 0, 0)
    assert x["coverageP10P90"] == {"n": 10, "inside": 8, "rate": 0.8}
    assert x["coverageP02P98"] == {"n": 10, "inside": 9, "rate": 0.9}
    assert x["tailOutsideP02P98"] == {"n": 10, "outside": 1, "below": 0, "above": 1, "rate": 0.1}


def test_band_edges_are_inclusive_and_come_from_the_record_not_the_history(root):
    # Realised exactly on p10 and p90 counts as inside; the history file carries no band at all.
    recs = [record("2026-10-01", horizons=(1,)), record("2026-10-02", horizons=(1,))]
    write_ledger(root, {"01/120000Z-r1.jsonl": recs})
    write_history(root, {"2026-10-02": 10.0, "2026-10-03": 20.0})
    x = h(score(root)["primary"]["overall"], 1)
    assert x["coverageP10P90"]["inside"] == 2 and x["tailOutsideP02P98"]["outside"] == 0


def test_pending_is_counted_and_never_scored_even_when_a_row_exists(root):
    recs = [record(day(i).isoformat()) for i in range(1, 11)]     # bases Oct 1..10; targets +1 Oct 2..11, +7 Oct 8..17, +30 Nov 1..10
    write_ledger(root, {"01/120000Z-r1.jsonl": recs})
    # Rows exist for EVERY date through Nov 10, including the future relative to as-of Oct 12 (a leak the scorer must ignore).
    series = {(dt.date(2026, 10, 1) + dt.timedelta(days=i)).isoformat(): 15.0 for i in range(0, 45)}
    write_history(root, series)
    g = score(root)["primary"]["overall"]
    assert h(g, 1)["scored"] == 10 and h(g, 1)["pending"] == 0                      # targets Oct 2..11 < Oct 12
    assert h(g, 7)["scored"] == 4 and h(g, 7)["pending"] == 6                       # Oct 8..11 scored; Oct 12..17 pending
    assert h(g, 30)["scored"] == 0 and h(g, 30)["pending"] == 10
    assert h(g, 30)["coverageP10P90"] == {"n": 0, "inside": 0, "rate": None}        # no rate from nothing
    assert h(g, 7)["coverageP10P90"]["n"] == 4


def test_missing_realised_after_grace_and_pending_inside_grace(root):
    recs = [record("2026-10-01", horizons=(1,)), record("2026-10-07", horizons=(1,)), record("2026-10-09", horizons=(1,)), record("2026-10-10", horizons=(1,))]
    write_ledger(root, {"01/120000Z-r1.jsonl": recs})
    write_history(root, {"2026-10-10": 15.0})      # targets: Oct 2 (no row, old), Oct 8 (no row, old), Oct 10 (row), Oct 11 (no row, in grace of Oct 12)
    x = h(score(root, grace=3)["primary"]["overall"], 1)
    assert (x["scored"], x["missingRealised"], x["pending"]) == (1, 2, 1)
    x0 = h(score(root, grace=0)["primary"]["overall"], 1)
    assert (x0["scored"], x0["missingRealised"], x0["pending"]) == (1, 3, 0)


def test_rapid_exceedance_exact(root):
    recs = [record(day(i).isoformat(), rapid=0.5, rate_p95=0.3, horizons=(1,)) for i in range(1, 5)]
    write_ledger(root, {"01/120000Z-r1.jsonl": recs})
    write_history(root, {"2026-10-01": 15.0, "2026-10-02": 15.2, "2026-10-03": 15.8, "2026-10-04": 16.15, "2026-10-05": 16.41})
    x = h(score(root)["primary"]["overall"], 1)
    assert x["rapidExceedanceVsStoredThreshold"] == {"n": 4, "exceeded": 1, "rate": 0.25}
    assert x["rapidExceedanceVsTargetDayThreshold"] == {"n": 4, "exceeded": 2, "rate": 0.5}
    # With no rate climatology the floor 0.25 ft alone applies (the Brain's own rule): 0.26 and 0.35 and 0.6 exceed.
    write_ledger(root, {"01/120000Z-r1.jsonl": [record(day(i).isoformat(), rapid=0.5, rate_p95=None, horizons=(1,)) for i in range(1, 5)]})
    y = h(score(root)["primary"]["overall"], 1)
    assert y["rapidExceedanceVsTargetDayThreshold"] == {"n": 4, "exceeded": 3, "rate": 0.75}


def test_label_persistence_table_and_24h_change_vs_stable_floor(root):
    recs = [
        record("2026-10-01", label="STABLE", floor=0.1, rapid=0.5, horizons=(1,)),
        record("2026-10-02", label="STABLE", floor=0.1, rapid=0.5, horizons=(1,)),
        record("2026-10-03", label="RISING", floor=0.1, rapid=0.5, horizons=(1,)),
        record("2026-10-04", label="FALLING_RAPIDLY", floor=0.1, rapid=0.5, horizons=(1,)),
    ]
    write_ledger(root, {"01/120000Z-r1.jsonl": recs})
    series = {
        "2026-10-01": 100.0, "2026-10-02": 100.05, "2026-10-03": 100.1, "2026-10-04": 100.2,   # STABLE@Oct1: d1 +0.05 (<= floor), d3 mean 0.0667 -> STABLE
        "2026-10-05": 100.3, "2026-10-06": 100.4, "2026-10-07": 100.9,                       # STABLE@Oct2: d1 +0.05, d3 (100.3-100.05)/3=.083 -> STABLE
        "2026-10-08": 99.0,                                                                  # RISING@Oct3 (b0 100.1): d1 +0.1<=? 100.2-100.1 = .1 (<= floor), d3 (100.4-100.1)/3=.1 -> STABLE
    }
    write_history(root, series)
    g = score(root, as_of=dt.date(2026, 10, 20))["primary"]["overall"]
    st = g["labelPersistence"]["STABLE"]
    assert st["predictions"] == 2
    assert st["next24h"]["scored"] == 2 and st["next24h"]["withinStableFloor"] == {"n": 2, "count": 2, "rate": 1.0}
    assert st["next24h"]["meanAbsChangeFt"] == 0.05
    assert st["next72h"]["realisedMeanRateClass"] == {"RISING": 0, "STABLE": 2, "FALLING": 0}
    assert st["next72h"]["sameDirectionAsLabel"] == {"n": 2, "count": 2, "rate": 1.0}
    rs = g["labelPersistence"]["RISING"]
    assert rs["next72h"]["realisedMeanRateClass"]["STABLE"] == 1 and rs["next72h"]["sameDirectionAsLabel"]["count"] == 0
    # FALLING_RAPIDLY@Oct4 (b0 100.2): d1 100.3-100.2 = .1 -> not > rapid .5; d3 = (100.9... Oct7 100.9 - 100.2)/3 = +0.233 -> RISING, opposite of FALLING.
    fr = g["labelPersistence"]["FALLING_RAPIDLY"]
    assert fr["next72h"]["realisedMeanRateClass"]["RISING"] == 1 and fr["next72h"]["sameDirectionAsLabel"]["rate"] == 0.0
    assert fr["next24h"]["exceededStoredRapidThreshold"] == {"n": 1, "count": 0, "rate": 0.0}
    assert set(g["labelPersistence"]) == {"STABLE", "RISING", "FALLING_RAPIDLY"}


def test_label_windows_that_have_not_arrived_are_pending(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-10", horizons=(1,))]})
    write_history(root, {"2026-10-10": 15.0, "2026-10-11": 15.0, "2026-10-12": 15.0, "2026-10-13": 15.0})   # D+3 = Oct 13 >= as-of Oct 12
    st = score(root)["primary"]["overall"]["labelPersistence"]["STABLE"]
    assert st["next24h"]["scored"] == 1 and st["next72h"]["scored"] == 0 and st["next72h"]["pending"] == 1


def test_unknown_trend_is_counted_not_tabulated(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", label="UNKNOWN", horizons=(1,))]})
    write_history(root, {"2026-10-01": 15.0, "2026-10-02": 15.0})
    g = score(root)["primary"]["overall"]
    assert g["unknownTrendRecords"] == 1 and g["labelPersistence"] == {}


def test_primary_dedupes_to_one_record_per_lake_day_and_all_records_pools(root):
    recs = [record("2026-10-01", run=f"r{i}", gen=f"2026-10-01T{12 + i:02d}:00:00Z", horizons=(1,)) for i in range(3)]
    write_ledger(root, {"01/120000Z-r0.jsonl": recs[:1], "01/130000Z-r1.jsonl": recs[1:2], "01/140000Z-r2.jsonl": recs[2:]})
    write_history(root, {"2026-10-02": 15.0})
    d = score(root)
    assert d["inputs"]["records"] == 3 and d["inputs"]["primaryRecords"] == 1 and d["inputs"]["objects"] == 3
    assert h(d["primary"]["overall"], 1)["predictions"] == 1
    assert h(d["allRecords"]["overall"], 1)["predictions"] == 3
    # Earliest generatedAt is the primary: change the realised band so only a r0-specific band would differ.
    other = record("2026-10-01", run="r0", gen="2026-10-01T06:00:01Z", obs_at="2026-10-01T06:00:00Z", band={"p02": 0, "p10": 1, "p50": 2, "p90": 3, "p98": 4}, horizons=(1,))
    write_ledger(root, {"01/000001Z-r00.jsonl": [other]})
    assert h(score(root)["primary"]["overall"], 1)["coverageP10P90"]["inside"] == 0


def test_groups_by_lake_and_class(root):
    a = [record("2026-10-01", lake=LAKE, provider="tva", tier="PROVISIONAL", horizons=(1,))]
    b = [record("2026-10-01", lake="Other Lake|SC", provider="cwms", tier="FULL", pool="naturalSurface", horizons=(1,))]
    write_ledger(root, {"01/120000Z-r1.jsonl": a + b})
    write_history(root, {"2026-10-02": 15.0})                     # inside the band
    write_history(root, {"2026-10-02": 30.0}, lake="Other Lake|SC")  # far above
    d = score(root)["primary"]
    assert set(d["byLake"]) == {LAKE, "Other Lake|SC"}
    assert h(d["byLake"][LAKE], 1)["coverageP10P90"]["rate"] == 1.0
    assert h(d["byLake"]["Other Lake|SC"], 1)["coverageP10P90"]["rate"] == 0.0
    assert h(d["byClass"]["provider"]["tva"], 1)["coverageP10P90"]["rate"] == 1.0
    assert h(d["byClass"]["provider"]["cwms"], 1)["tailOutsideP02P98"]["above"] == 1
    assert set(d["byClass"]["historicalTier"]) == {"PROVISIONAL", "FULL"}
    assert set(d["byClass"]["poolBasis"]) == {"fullPool", "naturalSurface"}
    assert set(d["byClass"]["rulesVersion"]) == {"lake-level-rules-v2"}
    assert h(d["overall"], 1)["coverageP10P90"] == {"n": 2, "inside": 1, "rate": 0.5}


def test_records_without_a_band_have_no_coverage_but_still_count(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", band=None, tier="NONE", horizons=(1,))]})
    write_history(root, {"2026-10-02": 15.0, "2026-10-01": 15.0})
    x = h(score(root)["primary"]["overall"], 1)
    assert x["scored"] == 1 and x["bandPredictionsScored"] == 0 and x["coverageP10P90"]["rate"] is None


def test_lake_without_history_is_listed_and_nothing_is_imputed(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", horizons=(1,))]})
    d = score(root)
    assert d["inputs"]["lakesWithoutHistory"] == [LAKE]
    assert h(d["primary"]["overall"], 1)["scored"] == 0 and h(d["primary"]["overall"], 1)["missingRealised"] == 1


def test_malformed_lines_and_other_versions_are_counted_and_skipped(root):
    good = record("2026-10-01", horizons=(1,))
    write_ledger(root, {"01/120000Z-r1.jsonl": [good, "{not json", json.dumps({"lakeId": "x"}), record("2026-10-01", version="lake-prediction-ledger-v2")]})
    write_history(root, {"2026-10-02": 15.0})
    d = score(root)
    assert d["inputs"]["lines"] == 4 and d["inputs"]["malformedLines"] == 2 and d["inputs"]["otherLedgerVersion"] == 1 and d["inputs"]["records"] == 1


def test_other_months_are_not_read(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", horizons=(1,))]})
    other = os.path.join(root, "predictions", "2026", "09", "30")
    os.makedirs(other)
    with open(os.path.join(other, "120000Z-x.jsonl"), "w") as fh:
        fh.write(json.dumps(record("2026-09-30", horizons=(1,))) + "\n")
    assert score(root)["inputs"]["records"] == 1


def test_header_repeats_not_validated_and_has_no_verdict_keys(root):
    known_coverage_ledger(root)
    d = score(root)
    assert d["validationStatus"] == "NOT_VALIDATED" and "NOT_VALIDATED" in d["notice"] and "PARTIAL" in d["notice"]

    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)
    banned = {"pass", "passed", "fail", "failed", "verdict", "status", "result"}
    assert not (banned & {k.lower() for k in keys({k: v for k, v in d.items() if k not in ("rules",)})} - {"validationstatus"})
    assert "pass" not in json.dumps(d["primary"]).lower()


def test_idempotent_byte_identical_and_independent_of_where_it_runs(root, tmp_path):
    known_coverage_ledger(root)
    a = S.to_json(score(root))
    b = S.to_json(score(root))
    assert a == b
    copy = str(tmp_path / "copy")
    shutil.copytree(root, copy)
    assert S.to_json(score(copy)) == a
    # Writing twice gives the same file.
    out = str(tmp_path / "out")
    p1 = S.write_out(out, "2026-10", a)
    first = open(p1).read()
    S.write_out(out, "2026-10", S.to_json(score(root)))
    assert open(p1).read() == first and p1.endswith("predictions_scores/2026-10.json")


def test_as_of_changes_only_pending_counts_not_scored_results(root):
    known_coverage_ledger(root)
    early = h(score(root, as_of=dt.date(2026, 10, 6))["primary"]["overall"], 1)       # targets Oct 2..11; < Oct 6 -> 4 scored
    late = h(score(root, as_of=dt.date(2026, 10, 30))["primary"]["overall"], 1)
    # Records generated after the as-of date are not yet "known" and are excluded (a replay as of Oct 6 sees bases Oct 1..6 only).
    assert early["predictions"] == 6 and early["scored"] == 4 and early["pending"] + early["missingRealised"] == 2
    assert late["scored"] == 10
    assert early["coverageP10P90"]["inside"] <= late["coverageP10P90"]["inside"]


def test_cli_writes_the_month_file_and_defaults_to_previous_month(root, tmp_path, capsys):
    known_coverage_ledger(root)
    out = str(tmp_path / "scores")
    assert S.main(["--month", "2026-10", "--predictions", root, "--out", out, "--as-of", "2026-10-12"]) == 0
    doc = json.load(open(os.path.join(out, "predictions_scores", "2026-10.json")))
    assert doc["month"] == "2026-10" and doc["asOf"] == "2026-10-12" and doc["validationStatus"] == "NOT_VALIDATED"
    assert "NOT_VALIDATED" in capsys.readouterr().out
    assert S.previous_month(dt.date(2026, 11, 3)) == "2026-10"
    assert S.previous_month(dt.date(2027, 1, 15)) == "2026-12"
    S.main(["--predictions", root, "--out", out, "--as-of", "2026-11-03"])
    assert os.path.exists(os.path.join(out, "predictions_scores", "2026-10.json"))


def test_lake_key_matches_the_swift_slug():
    assert S.lake_key("Lake Hartwell|SC") == "Lake_Hartwell_SC"
    assert S.lake_key("Guntersville|AL") == "Guntersville_AL"
    assert S.lake_key("St. Mary's  Lake|MN") == "St_Mary_s_Lake_MN"


def test_history_csv_parse_matches_the_swift_encoder_format():
    data = b"date,elevationFt,sourceId\n2026-10-01,599.97,tva:GVDA1\n2026-10-02,600.00,cwms:SAS:Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS\nbad,1,2\n2026-10-03,x,y\n"
    assert S.parse_daily_csv(data) == {"2026-10-01": 599.97, "2026-10-02": 600.0}


def test_gcs_source_uses_gcloud_cat_and_ls_and_never_writes(root):
    calls = []

    def run(args):
        calls.append(args)
        if args[:3] == ["gcloud", "storage", "ls"]:
            return 0, b"gs://b/predictions/2026/10/01/120000Z-r1.jsonl\ngs://b/predictions/2026/10/01/readme.txt\n", ""
        if args[-1].endswith("daily.csv"):
            return 1, b"", "ERROR: One or more URLs matched no objects"
        return 0, (json.dumps(record("2026-10-01", horizons=(1,))) + "\n").encode(), ""
    src = S.GcsSource("gs://b", run=run)
    assert src.list("predictions/2026/10/") == ["predictions/2026/10/01/120000Z-r1.jsonl"]
    assert src.read("history/x/daily.csv") is None
    recs, info = S.load_records(src, "2026-10")
    assert len(recs) == 1 and info["objects"] == 1
    assert all(c[:3] in (["gcloud", "storage", "ls"], ["gcloud", "storage", "cat"]) for c in calls)
    bad = S.GcsSource("gs://b", run=lambda a: (1, b"", "ERROR: permission denied"))
    with pytest.raises(RuntimeError):
        bad.read("history/x/daily.csv")


def test_gcs_output_goes_through_gcloud_cp(tmp_path):
    seen = {}

    def run(args):
        seen["args"] = args
        seen["body"] = open(args[3]).read()
        return 0, b"", ""
    dest = S.write_out("gs://b/scores", "2026-10", "{}\n", run=run)
    assert dest == "gs://b/scores/predictions_scores/2026-10.json" and seen["args"][:3] == ["gcloud", "storage", "cp"] and seen["body"] == "{}\n"


def test_swift_golden_fixture_parses_and_scores():
    """The fixture is produced by the Swift encoder (LakePredictionLedgerTests.testGoldenLedgerMatchesCheckedInFixture)."""
    src = os.path.join(HERE, "fixtures", "sample_ledger.jsonl")
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        dst = os.path.join(root, "predictions", "2026", "06", "01")
        os.makedirs(dst)
        shutil.copy(src, os.path.join(dst, "123000Z-golden.jsonl"))
        recs, info = S.load_records(S.LocalSource(root), "2026-06")
        assert info["malformedLines"] == 0 and info["otherLedgerVersion"] == 0 and len(recs) == 2
        by = {r["lakeId"]: r for r in recs}
        for r in by.values():
            assert r["ledgerVersion"] == "lake-prediction-ledger-v1" and [x["days"] for x in r["horizons"]] == [1, 7, 30]
            assert r["horizons"][0]["targetDate"] == "2026-06-02" and r["horizons"][2]["targetDate"] == "2026-07-01"
        # Realised on 2026-06-02 inside the stored band for both lakes -> 100 % coverage; nothing recomputed from a baseline.
        for lake, r in by.items():
            b = r["horizons"][0]["band"]
            write_history(root, {"2026-06-01": r["observation"]["ft"], "2026-06-02": b["p50"]}, lake=lake)
        d = S.score_month(S.LocalSource(root), S.LocalSource(root), "2026-06", dt.date(2026, 6, 5))
        x = d["primary"]["overall"]["horizons"]["1"]
        assert x["coverageP10P90"] == {"n": 2, "inside": 2, "rate": 1.0}
        assert d["primary"]["overall"]["horizons"]["30"]["pending"] == 2


# ----------------------------------------------------------------------------- hardening (2026-10-13)

def test_each_horizon_joins_to_its_own_target_day(root):
    # Base Oct 1: +1 -> Oct 2 (inside p10..p90), +7 -> Oct 8 (p02..p10: inside p02..p98 only), +30 -> Oct 31 (above p98).
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01")]})
    write_history(root, {"2026-10-02": 15.0, "2026-10-08": 9.5, "2026-10-31": 25.0})
    g = score(root, as_of=dt.date(2026, 11, 5))["primary"]["overall"]
    assert h(g, 1)["coverageP10P90"]["inside"] == 1
    assert h(g, 7)["coverageP10P90"] == {"n": 1, "inside": 0, "rate": 0.0} and h(g, 7)["coverageP02P98"]["inside"] == 1
    assert h(g, 30)["tailOutsideP02P98"] == {"n": 1, "outside": 1, "below": 0, "above": 1, "rate": 1.0}
    assert [h(g, d)["scored"] for d in (1, 7, 30)] == [1, 1, 1]


def test_a_month_with_only_future_targets_is_a_pending_report(root):
    # What the live ledger looks like on its first day: nothing has arrived, nothing is scored, no rate exists.
    write_ledger(root, {"13/185314Z-x.jsonl": [record("2026-10-13", gen="2026-10-13T18:53:14Z", obs_at="2026-10-13T18:00:00Z")]})
    write_history(root, {"2026-10-13": 15.0})
    d = score(root, as_of=dt.date(2026, 10, 13))
    g = d["primary"]["overall"]
    for days in (1, 7, 30):
        x = h(g, days)
        assert (x["predictions"], x["pending"], x["scored"], x["missingRealised"]) == (1, 1, 0, 0)
        assert x["coverageP10P90"]["rate"] is None and x["rapidExceedanceVsStoredThreshold"]["rate"] is None
    assert g["labelPersistence"]["STABLE"]["next24h"]["pending"] == 1


def test_realisation_must_be_the_exact_target_day_never_a_neighbour(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", horizons=(1,))]})
    write_history(root, {"2026-10-01": 15.0, "2026-10-03": 15.0, "2026-10-04": 15.0})      # rows the day before and after Oct 2, none on it
    x = h(score(root)["primary"]["overall"], 1)
    assert (x["scored"], x["missingRealised"]) == (0, 1)


def test_rows_dated_on_or_after_as_of_are_never_realisations(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", horizons=(1,))]})
    write_history(root, {"2026-10-02": 15.0})
    assert h(score(root, as_of=dt.date(2026, 10, 2))["primary"]["overall"], 1)["pending"] == 1      # the day is not over yet
    assert h(score(root, as_of=dt.date(2026, 10, 3))["primary"]["overall"], 1)["scored"] == 1


def test_default_as_of_waits_for_the_last_us_day_to_end():
    assert S.default_as_of(dt.datetime(2026, 11, 1, 3, 0, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 31)
    assert S.default_as_of(dt.datetime(2026, 11, 1, 11, 59, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 31)
    assert S.default_as_of(dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.timezone.utc)) == dt.date(2026, 11, 1)


def test_stale_history_is_flagged_and_its_targets_are_missing_not_imputed(root):
    write_ledger(root, {"01/120000Z-r1.jsonl": [record("2026-10-01", horizons=(1, 7))]})
    write_history(root, {"2026-10-02": 15.0})                                    # history stopped on Oct 2; as-of Oct 12
    d = score(root)
    assert any(w.startswith("STALE_HISTORY") for w in d["warnings"])
    assert d["inputs"]["historyLatestDate"] == {LAKE: "2026-10-02"}
    g = d["primary"]["overall"]
    assert (h(g, 1)["scored"], h(g, 7)["missingRealised"]) == (1, 1)


def test_rules_binding_and_baseline_changes_are_grouped_never_pooled_silently(root):
    recs = [record("2026-10-01", horizons=(1,), rules="lake-level-rules-v2", binding="bindings-A"),
            record("2026-10-02", horizons=(1,), rules="lake-level-rules-v3", binding="bindings-B", band={"p02": 0, "p10": 1, "p50": 2, "p90": 3, "p98": 4})]
    write_ledger(root, {"01/120000Z-r1.jsonl": recs[:1], "02/120000Z-r2.jsonl": recs[1:]})
    write_history(root, {"2026-10-02": 15.0, "2026-10-03": 15.0})
    d = score(root)
    by = d["primary"]["byClass"]
    assert set(by["rulesVersion"]) == {"lake-level-rules-v2", "lake-level-rules-v3"}
    assert h(by["rulesVersion"]["lake-level-rules-v2"], 1)["coverageP10P90"]["rate"] == 1.0
    assert h(by["rulesVersion"]["lake-level-rules-v3"], 1)["coverageP10P90"]["rate"] == 0.0       # v3's own stored band, not v2's
    assert set(by["bindingVersion"]) == {"bindings-A", "bindings-B"}
    assert d["inputs"]["versions"]["rulesVersion"] == {"lake-level-rules-v2": 1, "lake-level-rules-v3": 1}
    w = " ".join(d["warnings"])
    assert "MIXED_RULES_VERSIONS" in w and "MIXED_BINDING_VERSIONS" in w
    # One version only: no warning.
    write_ledger(root, {"02/120000Z-r2.jsonl": [record("2026-10-02", horizons=(1,), binding="bindings-A")]})
    assert not any(x.startswith("MIXED_") for x in score(root)["warnings"])


def test_duplicate_objects_and_lines_are_counted_once_and_scoring_twice_is_identical(root):
    r = record("2026-10-01", horizons=(1,))
    write_ledger(root, {"01/120000Z-r1.jsonl": [r, r], "01/120000Z-copy.jsonl": [r]})       # the same claim in two objects and twice in one
    write_history(root, {"2026-10-02": 15.0})
    d = score(root)
    assert d["inputs"]["lines"] == 3 and d["inputs"]["records"] == 1 and d["inputs"]["duplicateRecords"] == 2
    assert h(d["allRecords"]["overall"], 1)["predictions"] == 1
    assert S.to_json(score(root)) == S.to_json(d)


def test_scoring_uses_only_the_stored_thresholds_never_a_baseline(root):
    # Same realised path; two records that differ ONLY in their stored thresholds/bands give different, predictable answers.
    tight = record("2026-10-01", lake="Tight Lake|TN", rapid=0.1, rate_p95=0.1, band={"p02": 14, "p10": 14.5, "p50": 15, "p90": 15.2, "p98": 15.4}, horizons=(1,))
    loose = record("2026-10-01", lake="Loose Lake|TN", rapid=2.0, rate_p95=2.0, band={"p02": 0, "p10": 5, "p50": 15, "p90": 25, "p98": 30}, horizons=(1,))
    write_ledger(root, {"01/120000Z-r1.jsonl": [tight, loose]})
    for lake in ("Tight Lake|TN", "Loose Lake|TN"):
        write_history(root, {"2026-10-01": 15.0, "2026-10-02": 15.5}, lake=lake)
    # A baseline artifact that would give a different answer sits right there; the scorer must not look at it.
    os.makedirs(os.path.join(root, "baselines", "Tight_Lake_TN"))
    open(os.path.join(root, "baselines", "Tight_Lake_TN", "b.json"), "w").write("{}")
    reads = []

    class Spy(S.LocalSource):
        def read(self, path):
            reads.append(path)
            return super().read(path)
    d = S.score_month(Spy(root), Spy(root), "2026-10", AS_OF, 3)
    lakes = d["primary"]["byLake"]
    t, l = h(lakes["Tight Lake|TN"], 1), h(lakes["Loose Lake|TN"], 1)
    assert t["coverageP10P90"]["inside"] == 0 and l["coverageP10P90"]["inside"] == 1
    assert t["rapidExceedanceVsStoredThreshold"]["exceeded"] == 1 and l["rapidExceedanceVsStoredThreshold"]["exceeded"] == 0
    assert reads and all(p.startswith(("predictions/", "history/")) for p in reads)


@pytest.mark.parametrize("kw,reason", [
    (dict(obs_at="2026-10-01T13:00:00Z", gen="2026-10-01T12:30:00Z"), "observationAfterPrediction"),
    (dict(targets={1: "2026-10-01"}), "targetNotBasePlusDays"),                       # the base day's own row would be the "realisation"
    (dict(targets={1: "2026-09-30"}), "targetNotBasePlusDays"),                       # a value from before the prediction
    (dict(targets={1: "2026-10-03"}), "targetNotBasePlusDays"),                       # date does not match days
    (dict(obs_at="2026-10-01T04:30:00Z", gen="2026-10-02T04:30:00Z"), "baseDateNotObservationDate"),   # 23:30 Chicago on Sep 30 is not base Oct 1
    (dict(obs_at="2026-10-02T03:30:00Z", gen="2026-10-02T04:30:00Z", targets={}), None),               # 22:30 Oct 1 local, made 23:30 Oct 1 local: fine
])
def test_no_hindsight_records_that_need_it_are_rejected_not_scored(root, kw, reason):
    r = record("2026-10-01", horizons=(1,), **kw)
    write_ledger(root, {"01/120000Z-r1.jsonl": [r]})
    write_history(root, {"2026-09-30": 15.0, "2026-10-01": 15.0, "2026-10-02": 15.0, "2026-10-03": 15.0})
    d = score(root)
    if reason is None:
        assert d["inputs"]["invalidRecords"] == 0 and d["inputs"]["records"] == 1
        return
    assert d["inputs"]["invalidReasons"] == {reason: 1}
    assert d["inputs"]["records"] == 0 and d["primary"]["overall"]["records"] == 0
    assert any(w.startswith("INVALID_RECORDS") for w in d["warnings"])


def test_target_on_the_day_the_prediction_was_made_is_not_a_realisation(root):
    # Observation 23:00 Oct 1 local (Chicago = 04:00Z Oct 2), made 01:00 Oct 2 local: base Oct 1, +1 d target Oct 2 is the day it was made.
    r = record("2026-10-01", horizons=(1,), obs_at="2026-10-02T04:00:00Z", gen="2026-10-02T06:00:00Z")
    write_ledger(root, {"02/060000Z-r1.jsonl": [r]})
    write_history(root, {"2026-10-02": 15.0})
    d = score(root)
    assert d["inputs"]["invalidReasons"] == {"targetNotAfterPredictionDay": 1}


def test_records_generated_after_the_as_of_date_are_excluded(root):
    write_ledger(root, {"05/120000Z-r1.jsonl": [record("2026-10-05", horizons=(1,))]})
    write_history(root, {"2026-10-06": 15.0})
    d = score(root, as_of=dt.date(2026, 10, 4))
    assert d["inputs"]["futureDatedRecords"] == 1 and d["inputs"]["records"] == 0
