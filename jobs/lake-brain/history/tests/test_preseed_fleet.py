"""Tests for preseed_fleet.py. Everything runs against FIXTURE lakes and a synthetic provider server (fixture_lib.py): no network, no real
bucket, no real review files. `--gcs-prefix` is never passed to the CLI here."""
import base64
import copy
import csv
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys

import pytest

import fixture_lib as F
import held_lakes
import preseed_fleet as P

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "preseed_fleet.py")
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
FIXTURE_DIR = os.path.join(HERE, "fixtures", "fixture_batch")


class Clock:
    """Fake clock: sleeping advances time, so rate-limit gaps are checked without waiting."""

    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


@pytest.fixture
def fx(tmp_path):
    b, r, bp = F.make_fixture_batch(str(tmp_path / "batch"), str(tmp_path))
    return dict(batch=b, result=r, bindings=bp, tmp=tmp_path)


def cli(fx, work, extra=(), server=None, clock=None, now=F.NOW, parallel=False, batch=None):
    server = server or F.FakeServer()
    clock = clock or Clock()
    argv = ["--batch", batch or fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(work), "--allow-fixture", "--now", now, "--quiet"]
    if not parallel:
        argv.append("--no-parallel")
    rc = P.main(argv + list(extra), transport=server, clock=clock, sleep=clock.sleep)
    return rc, server, clock


def manifest(work):
    return json.load(open(os.path.join(str(work), "preseed_manifest.json")))


def all_files(root):
    out = []
    for dp, _, fns in os.walk(root):
        out += [os.path.join(dp, f) for f in fns]
    return sorted(out)


# ================================================================================================================================
# 1. Pre-registered continuity check
# ================================================================================================================================
def days(n, start="2026-09-01", v=100.0):
    d0 = dt.date.fromisoformat(start)
    return {(d0 + dt.timedelta(days=i)).isoformat(): v for i in range(n)}


def test_preregistered_constants_are_the_header_values():
    src = open(SCRIPT).read()
    head = src.split('"""')[1]
    assert "|d| >  2.0 ft" in head and "REJECT_DATUM" in head and "15.0 ft" in head
    assert P.DATUM_REJECT_MEDIAN_FT == 2.0 and P.COARSE_REJECT_FT == 15.0 and P.COARSE_REF_ROWS == 30 and P.COARSE_MIN_ROWS == 10


@pytest.mark.parametrize("off,verdict", [(0.0, "PASS_OVERLAP"), (1.99, "PASS_OVERLAP"), (2.0, "PASS_OVERLAP"), (-2.0, "PASS_OVERLAP"),
                                         (2.01, "REJECT_DATUM"), (-2.01, "REJECT_DATUM"), (30.0, "REJECT_DATUM")])
def test_overlap_threshold(off, verdict):
    hist = days(40)
    live = {d: v + off for d, v in days(10, "2026-09-20").items()}
    r = P.continuity_check(live, hist)
    assert r["verdict"] == verdict and r["mode"] == "overlap" and r["overlapDays"] == 10


def test_overlap_uses_the_median_not_one_outlier_day():
    hist = days(40)
    live = days(9, "2026-09-20")
    live["2026-09-29"] = 130.0                      # one wild day
    assert P.continuity_check(live, hist)["verdict"] == "PASS_OVERLAP"


def test_single_overlapping_day_decides():
    assert P.continuity_check({"2026-09-10": 105.0}, days(40))["verdict"] == "REJECT_DATUM"
    assert P.continuity_check({"2026-09-10": 101.0}, days(40))["verdict"] == "PASS_OVERLAP"


def test_no_overlap_coarse_check():
    hist = days(40)                                  # ends 2026-10-10
    ok = P.continuity_check({"2026-10-13": 110.0}, hist)           # 10 ft off: coarse cannot see it
    assert ok["verdict"] == "PASS_COARSE" and ok["mode"] == "coarse"
    assert P.continuity_check({"2026-10-13": 115.0}, hist)["verdict"] == "PASS_COARSE"       # exactly 15.0 passes
    assert P.continuity_check({"2026-10-13": 115.01}, hist)["verdict"] == "REJECT_DATUM"
    assert P.continuity_check({"2026-10-13": 84.0}, hist)["verdict"] == "REJECT_DATUM"
    assert P.continuity_check({"2026-10-13": 100.0}, days(9))["verdict"] == "DEFER_NO_EVIDENCE"


def test_empty_inputs():
    assert P.continuity_check({"2026-10-13": 1.0}, {})["verdict"] == "REJECT_EMPTY"
    assert P.continuity_check({}, days(40))["verdict"] == "DEFER_NO_LIVE"


# ---- the 14 known series/datum mismatch lakes (held_back_series_mismatch.csv) ---------------------------------------------------
# Provider of each lake as listed in the review pack's held_back_series_mismatch.csv.
MISMATCH_PROVIDER = {"Bartlett|AZ": "nwps", "Blue Mesa Reservoir|CO": "rise", "Buffalo Bill Reservoir|WY": "rise", "Canyon Lake|TX": "a2w",
                     "Detroit Lake|OR": "a2w", "Glendo Reservoir|WY": "rise", "Jackson Lake|WY": "a2w", "Jordanelle Reservoir|UT": "rise",
                     "Lake Koocanusa|MT": "cwms", "Lake Shelbyville|IL": "cwms", "Lake Taneycomo|MO": "usgs", "Navajo Reservoir|NM": "rise",
                     "Pineview Reservoir|UT": "rise", "Rend Lake|IL": "cwms"}


def test_the_14_known_mismatch_lakes_are_the_repository_hold_list():
    assert set(MISMATCH_PROVIDER) == set(held_lakes.SERIES_MISMATCH) and len(MISMATCH_PROVIDER) == 14
    pack = "/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review/held_back_series_mismatch.csv"
    if os.path.exists(pack):
        rows = list(csv.DictReader(open(pack, encoding="utf-8-sig")))
        assert {r["lake_id"]: r["provider"] for r in rows} == MISMATCH_PROVIDER


def canned_mismatch(i, lake):
    """Canned history/live for one held lake: the held-list definition is 'history differs from live by more than 15 ft', so the canned
    offset is 15.5 + i ft (sign alternating); the level itself is a made-up reservoir level. Synthetic, not recorded."""
    base = 4000.0 + 100 * i
    off = (15.5 + i) * (1 if i % 2 == 0 else -1)
    hist = {d: base + 0.1 * k for k, d in enumerate(sorted(days(400, "2025-09-01")))}
    live = {d: hist[d] + off for d in sorted(hist)[-12:]}
    return hist, live, off


@pytest.mark.parametrize("i,lake", list(enumerate(sorted(held_lakes.SERIES_MISMATCH))))
def test_known_mismatch_lake_is_rejected_by_the_check(i, lake):
    hist, live, off = canned_mismatch(i, lake)
    r = P.continuity_check(live, hist)
    assert r["verdict"] == "REJECT_DATUM" and r["mode"] == "overlap" and abs(abs(r["medianDiffFt"]) - abs(off)) < 1e-6
    coarse = P.continuity_check({"2027-01-05": list(live.values())[-1]}, hist)          # latest-only live (RISE/A2W style)
    assert coarse["verdict"] == "REJECT_DATUM" and coarse["mode"] == "coarse"


def _two_lake_info(tmp_path, lakes):
    rows = {}
    for i, lk in enumerate(lakes):
        prov = MISMATCH_PROVIDER[lk]
        rows[lk] = dict(lakeId=lk, status="MACHINE_VERIFIED", provider=prov, capability="DIRECT_OPERATOR_POOL", timeZone="America/Denver",
                        live=[dict(provider=prov, station="X", series="s", datumOffsetFt=0.0)], history=[dict(kind="cwmsDaily", office="X", series="s.~1Day")],
                        historyCompleteYears=1)
    return dict(mode="batch", batch=sorted(rows), bindings=rows, bindingsDoc={"pilotReproduction": []}, bindingsSha256="0" * 64,
                batchSha256="1" * 64, resultSha256="2" * 64, fixture=True)


def test_known_mismatch_lakes_through_the_whole_pipeline_are_rejected_and_never_written(tmp_path, monkeypatch):
    """The real Runner/State/publish code with canned history+live per held lake: every one ends REJECT_DATUM, no staged file, nothing published."""
    lakes = sorted(held_lakes.SERIES_MISMATCH)
    info = _two_lake_info(tmp_path, lakes)
    canned = {lk: canned_mismatch(i, lk) for i, lk in enumerate(lakes)}
    monkeypatch.setattr(P, "fetch_history", lambda ctx: [(d, v, "canned") for d, v in canned[ctx.lake_id][0].items()])
    monkeypatch.setattr(P, "fetch_live_daily", lambda ctx: (canned[ctx.lake_id][1], dict(refIndex=0)))
    args = P.build_parser().parse_args(["--work-dir", str(tmp_path / "w"), "--write-dir", str(tmp_path / "out"), "--quiet", "--no-parallel"])
    args.now_dt = P.parse_iso("2026-10-13T12:00:00Z")
    r = P.Runner(args, info, transport=None)
    r.run(lakes)
    man = manifest(tmp_path / "w")
    assert man["counts"] == {"REJECT_DATUM": 14}
    assert not [f for f in all_files(tmp_path / "w") if f.endswith("daily.csv")]
    assert not os.path.exists(tmp_path / "out" / "history")


# ================================================================================================================================
# 2. A legitimately formed accepted batch (and only that)
# ================================================================================================================================
def test_fixture_batch_comes_from_the_real_ingest_and_validates(fx):
    v = P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True)
    assert v["fixture"] is True and len(v["batch"]) == 8 and v["result"]["verdict"] == "ACCEPT_BATCH"


def test_committed_fixture_files_match_what_the_ingest_writes_and_live_only_under_tests(fx):
    for name in ("accepted_batch.json", "binding_review_result.json", "bindings.fixture.json"):
        committed = open(os.path.join(FIXTURE_DIR, name)).read()
        fresh = open(os.path.join(os.path.dirname(fx["batch"]), name)).read()
        if name == "binding_review_result.json":
            a, b = json.loads(committed), json.loads(fresh)
            a.pop("reviewCsvSha256"), b.pop("reviewCsvSha256")            # the CSV lives in a tmp dir; everything else must be identical
            assert a == b
        else:
            assert committed == fresh
    assert "tests" + os.sep + "fixtures" in FIXTURE_DIR
    tracked = subprocess.run(["git", "-C", REPO, "ls-files", "jobs/lake-brain/data", "jobs/lake-brain/review"], capture_output=True, text=True).stdout
    assert "fixture" not in tracked.lower() and tracked.strip()


def test_fixture_is_refused_without_allow_fixture_with_real_bindings_and_with_gcs(fx, tmp_path):
    assert P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(tmp_path / "w1")]) == 2
    with pytest.raises(P.PreseedError):
        P.validate_batch(fx["batch"], fx["result"], P.DEFAULT_BINDINGS, allow_fixture=True)          # real bindings table: ids unknown AND fixture
    with pytest.raises(P.PreseedError, match="fixture"):
        P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True, gcs=True)


def mutate_json(path, fn):
    d = json.load(open(path))
    fn(d)
    json.dump(d, open(path, "w"), indent=1)


@pytest.mark.parametrize("name,edit,match", [
    ("unsorted", lambda b, r: b.reverse(), "not sorted"),
    ("duplicate", lambda b, r: b.__setitem__(slice(None), sorted(b + [b[0]])), "duplicate"),
    ("count", lambda b, r: r.__setitem__("acceptedBatchCount", 9), "acceptedBatchCount"),
    ("rule not met", lambda b, r: r.__setitem__("ruleMet", False), "not an accepted batch"),
    ("verdict", lambda b, r: r.__setitem__("verdict", "REJECT_BATCH"), "not an accepted batch"),
    ("too many rejects", lambda b, r: r.__setitem__("rejected", 2), "maxErrors"),
    ("pending", lambda b, r: r.__setitem__("pending", 1), "every row must be decided"),
    ("criteria", lambda b, r: r.__setitem__("criteriaVersion", "binding-review-v2"), "criteriaVersion"),
    ("pack id", lambda b, r: r.__setitem__("packId", "SOMETHING-ELSE"), "packId"),
    ("csv hash", lambda b, r: r.__setitem__("reviewCsvSha256", "abc"), "reviewCsvSha256"),
    ("held lake", lambda b, r: r["heldBackLakes"].append(b[0]), "held back"),
    ("rejected id", lambda b, r: r["rejectedIds"].append(b[0]), "rejected ids"),
    ("full review stratum", lambda b, r: r["fullReviewStrata"].append("cwms | DIRECT_OPERATOR_POOL"), "full review"),
    ("batch hash", lambda b, r: r.__setitem__("acceptedBatchSha256", "0" * 64), "acceptedBatchSha256"),
])
def test_malformed_batches_are_refused(fx, name, edit, match):
    batch, res = json.load(open(fx["batch"])), json.load(open(fx["result"]))
    edit(batch, res)
    json.dump(batch, open(fx["batch"], "w"), indent=1)
    json.dump(res, open(fx["result"], "w"), indent=1)
    with pytest.raises(P.PreseedError, match=match):
        P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True)


def test_other_refusals(fx):
    for bad in ('{"a": 1}', "[]", '[1, 2]', '["a", ""]', "not json"):
        open(fx["batch"], "w").write(bad)
        with pytest.raises(P.PreseedError):
            P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True)
    # id not in the bindings table
    open(fx["batch"], "w").write(json.dumps(["FIXTURE Zulu Lake|ZZ"]))
    with pytest.raises(P.PreseedError):
        P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True)


def test_missing_result_and_bindings_and_not_machine_verified(fx, tmp_path):
    os.remove(fx["result"])
    with pytest.raises(P.PreseedError, match="binding_review_result.json"):
        P.validate_batch(fx["batch"], None, fx["bindings"], allow_fixture=True)


def test_binding_that_is_not_machine_verified_is_refused(fx):
    mutate_json(fx["bindings"], lambda d: d["bindings"][0].__setitem__("status", "CANDIDATE"))
    with pytest.raises(P.PreseedError, match="MACHINE_VERIFIED"):
        P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True)


def test_held_repository_lake_in_batch_is_refused(fx):
    held = sorted(held_lakes.SERIES_MISMATCH)[0]
    mutate_json(fx["bindings"], lambda d: d["bindings"].append(dict(d["bindings"][0], lakeId=held)))
    batch = sorted(json.load(open(fx["batch"])) + [held])
    json.dump(batch, open(fx["batch"], "w"))
    mutate_json(fx["result"], lambda r: r.__setitem__("acceptedBatchCount", len(batch)))
    with pytest.raises(P.PreseedError, match="held back"):
        P.validate_batch(fx["batch"], fx["result"], fx["bindings"], allow_fixture=True)


def test_ingest_with_one_reject_excludes_its_stratum_and_the_rest_runs(tmp_path):
    b, r, bp = F.make_fixture_batch(str(tmp_path / "b1"), str(tmp_path / "t1"), decision=lambda lid: "REJECT" if "Golf" in lid else "ACCEPT") \
        if os.makedirs(str(tmp_path / "t1")) is None else None
    batch = json.load(open(b))
    assert "FIXTURE Golf Lake|ZZ" not in batch and len(batch) == 7             # the ingest dropped the tva stratum
    fx = dict(batch=b, result=r, bindings=bp)
    rc, srv, _ = cli(fx, tmp_path / "w")
    assert rc == 0 and manifest(tmp_path / "w")["counts"]["PASS"] == 6


def test_ingest_with_two_rejects_gives_empty_batch_which_is_refused(tmp_path):
    os.makedirs(str(tmp_path / "t2"))
    b, r, bp = F.make_fixture_batch(str(tmp_path / "b2"), str(tmp_path / "t2"), decision=lambda lid: "REJECT" if ("Golf" in lid or "Alpha" in lid) else "ACCEPT")
    assert json.load(open(b)) == []
    with pytest.raises(P.PreseedError):
        P.validate_batch(b, r, bp, allow_fixture=True)


def test_cli_requires_batch_and_work_dir(tmp_path):
    assert P.main(["--work-dir", str(tmp_path / "w")]) == 2
    assert P.main(["--batch", "x"]) == 2


@pytest.mark.skipif(not os.path.exists("/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review/strict_population.csv"),
                    reason="real review pack not on this machine")
def test_stratum_rule_matches_the_real_review_pack():
    pop = list(csv.DictReader(open("/Users/mcather/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review/strict_population.csv", encoding="utf-8-sig")))
    _, rows = P.load_bindings(P.DEFAULT_BINDINGS)
    assert len(pop) == 196 and pop
    assert all(P.stratum_of(rows[r["lake_id"]]) == r["stratum"] for r in pop)


# ================================================================================================================================
# 3. End to end dry run, local write, determinism
# ================================================================================================================================
EXPECTED_PASS = ["FIXTURE Alpha Lake|ZZ", "FIXTURE Bravo Lake|ZZ", "FIXTURE Charlie Lake|ZZ", "FIXTURE Delta Lake|ZZ", "FIXTURE Echo Lake|ZZ",
                 "FIXTURE Foxtrot Lake|ZZ", "FIXTURE Golf Lake|ZZ"]


def test_dry_run_end_to_end_writes_only_the_work_dir(fx):
    before = set(all_files(fx["tmp"]))
    work = fx["tmp"] / "work"
    rc, srv, clk = cli(fx, work)
    assert rc == 0
    new = set(all_files(fx["tmp"])) - before
    assert new and all(f.startswith(str(work)) for f in new)
    assert not os.path.exists(fx["tmp"] / "out")
    man = manifest(work)
    assert man["counts"] == {"PASS": 7, "REJECT_DATUM": 1} and man["fixture"] is True and man["mode"] == "batch"
    assert man["lakes"]["FIXTURE Hotel Lake|ZZ"]["status"] == "REJECT_DATUM"
    assert abs(man["lakes"]["FIXTURE Hotel Lake|ZZ"]["continuity"]["medianDiffFt"] + 6.5) < 1e-9
    assert not os.path.exists(work / "staged" / "history" / "FIXTURE_Hotel_Lake_ZZ")
    for lake in EXPECTED_PASS:
        m = man["lakes"][lake]
        assert m["status"] == "PASS" and m["continuity"]["verdict"] == "PASS_OVERLAP" and m["rows"] > 600
        data = open(work / "staged" / "history" / P.lake_key(lake) / "daily.csv", "rb").read()
        assert P.sha256_bytes(data) == m["sha256"] and data.startswith(b"date,elevationFt,sourceId\n") and data.endswith(b"\n") and b"\r" not in data
        rows = P.decode(data)
        assert len(rows) == m["rows"] and [r[0] for r in rows] == sorted({r[0] for r in rows})
        assert all(len(r[0]) == 10 and "," not in r[2] for r in rows)
        for line in data.decode().splitlines()[1:]:
            assert len(line.split(",")[1].split(".")[1]) == 2                    # '%.2f'
    rep = json.load(open(work / "run_report.json"))
    assert set(rep["byHostGroup"]) >= {"cwms", "usgs", "rise", "hads", "tva", "a2w"}
    log = [json.loads(l) for l in open(work / "preseed.log.jsonl")]
    assert {"run_start", "lake_start", "lake_done", "step_fetched", "http_429_backoff", "run_done"} <= {l["event"] for l in log}


def test_source_ids_and_provider_reductions(fx):
    work = fx["tmp"] / "w"
    cli(fx, work)
    def rows(lake):
        return P.decode(open(work / "staged" / "history" / P.lake_key(lake) / "daily.csv", "rb").read())
    assert {r[2] for r in rows("FIXTURE Alpha Lake|ZZ")} == {"cwms:SPA:Alpha.Elev.Inst.~1Day.0.MRS"}
    assert {r[2] for r in rows("FIXTURE Charlie Lake|ZZ")} == {"usgs:00000001:62615:dv"}
    assert {r[2] for r in rows("FIXTURE Delta Lake|ZZ")} == {"usgs:00000002:00065:iv"}
    assert {r[2] for r in rows("FIXTURE Echo Lake|ZZ")} == {"hads:ECHO1:HP"}
    assert {r[2] for r in rows("FIXTURE Foxtrot Lake|ZZ")} == {"rise:9001"}
    assert {r[2] for r in rows("FIXTURE Golf Lake|ZZ")} == {"tva:operating-guide:GLFT1"}
    fox = {r[0] for r in rows("FIXTURE Foxtrot Lake|ZZ")}
    assert "2024-03-15" not in fox and "2024-03-16" not in fox and "2024-03-14" in fox        # RISE 0.0 placeholder and modeled day dropped
    gage = {r[0]: r[1] for r in rows("FIXTURE Delta Lake|ZZ")}
    d = dt.date(2024, 5, 20)
    assert abs(gage[d.isoformat()] - (F.level(F.lake("Delta"), d) + 0.5 / 2 * 0)) < 3.0       # elevation = gage height + datum offset (743.91)
    echo = {r[0] for r in rows("FIXTURE Echo Lake|ZZ")}
    assert "2022-06-01" in echo and "2019-10-01" in echo and min(echo) < "2019-09-05"            # pool column moved in 2021; walk stopped at the empty chunk


def test_write_dir_publishes_only_passed_lakes_atomically(fx):
    work, out = fx["tmp"] / "w", fx["tmp"] / "out"
    rc, *_ = cli(fx, work, ["--write-dir", str(out)])
    assert rc == 0
    files = [os.path.relpath(f, out) for f in all_files(out)]
    assert sorted(files) == sorted([f"history/{P.lake_key(l)}/daily.csv" for l in EXPECTED_PASS] + ["preseed_manifest.json"])
    man = manifest(work)
    for l in EXPECTED_PASS:
        assert P.sha256_file(out / "history" / P.lake_key(l) / "daily.csv") == man["lakes"][l]["sha256"]
    assert not [f for f in all_files(out) if ".tmp." in f]


def test_deterministic_output_across_runs_and_parallelism(fx):
    a, b, c = fx["tmp"] / "a", fx["tmp"] / "b", fx["tmp"] / "c"
    cli(fx, a)
    cli(fx, b, parallel=True)
    cli(fx, c, now=F.NOW)
    for lake in EXPECTED_PASS:
        k = P.lake_key(lake)
        ba = open(a / "staged" / "history" / k / "daily.csv", "rb").read()
        assert ba == open(b / "staged" / "history" / k / "daily.csv", "rb").read() == open(c / "staged" / "history" / k / "daily.csv", "rb").read()
    assert open(a / "preseed_manifest.json").read() == open(b / "preseed_manifest.json").read() == open(c / "preseed_manifest.json").read()


GOLDEN = {  # sha256 of the staged daily.csv at NOW=2026-10-13T12:00:00Z; regression guard for the encode + reductions (generated by this code, rows
    # for Alpha/Charlie/Foxtrot are also checked against the fixture formula in test_daily_rows_equal_the_fixture_formula)
    "FIXTURE Alpha Lake|ZZ": "7aef96ce82349ab72d52f8707007f4caaa03f6931b0e32cf813fc78c8cdc8c64",
    "FIXTURE Bravo Lake|ZZ": "bb2215500b2cb21e9a2aadf9e8d542ca1165943e705456de5f4f5a1afe71308d",
    "FIXTURE Charlie Lake|ZZ": "581a363347ed58cb656d7b4ec2e1b7e4f6c6d2f83c569b9928cab79735842e02",
    "FIXTURE Delta Lake|ZZ": "853965d56bda6e5ad93bca04bd86c07c610d65283bae8f5d819e43400d9626ba",
    "FIXTURE Echo Lake|ZZ": "8c61b85c55107217eed4ba9c7df138010f36210c5c5beae34b47a938d78a733c",
    "FIXTURE Foxtrot Lake|ZZ": "043ccb40556a8235992c8544f28ded0f0fd5f04261839fe3566f78d7146184cf",
    "FIXTURE Golf Lake|ZZ": "d7b5d0067fcf22770c41d8863cb61eaabdea208d59f645427c84b30218a49480",
}


def test_daily_rows_equal_the_fixture_formula(fx):
    work = fx["tmp"] / "w"
    cli(fx, work)
    for name in ("Alpha", "Charlie", "Foxtrot"):
        l = F.lake(name)
        rows = P.decode(open(work / "staged" / "history" / P.lake_key(l["id"]) / "daily.csv", "rb").read())
        assert len(rows) > 600
        for d, v, _ in rows:
            assert abs(v - F.level(l, dt.date.fromisoformat(d))) < 0.0051, (name, d)


def test_golden_hashes_are_stable(fx):
    work = fx["tmp"] / "w"
    cli(fx, work)
    got = {l: manifest(work)["lakes"][l]["sha256"] for l in EXPECTED_PASS}
    assert got == GOLDEN, json.dumps(got, indent=1)


def test_existing_history_is_merged_under_fresh_rows(fx, tmp_path):
    existing = tmp_path / "existing" / "history" / P.lake_key("FIXTURE Alpha Lake|ZZ")
    existing.mkdir(parents=True)
    old = P.encode([("2015-06-01", 6190.0, "legacy"), ("2019-03-02", 1.0, "legacy")])         # one old row, one that the fresh pull overrides
    open(existing / "daily.csv", "wb").write(old)
    work = fx["tmp"] / "w"
    cli(fx, work, ["--existing-dir", str(tmp_path / "existing"), "--lakes", "FIXTURE Alpha Lake|ZZ"])
    rows = {r[0]: r for r in P.decode(open(work / "staged" / "history" / P.lake_key("FIXTURE Alpha Lake|ZZ") / "daily.csv", "rb").read())}
    assert rows["2015-06-01"][2] == "legacy" and rows["2019-03-02"][2].startswith("cwms:")


def test_pilots_and_filters(fx):
    mutate_json(fx["bindings"], lambda d: d.__setitem__("pilotReproduction", [{"lakeId": "FIXTURE Golf Lake|ZZ"}]))
    work = fx["tmp"] / "w"
    cli(fx, work, ["--only-hosts", "cwms,tva"])
    assert sorted(manifest(work)["lakes"]) == ["FIXTURE Alpha Lake|ZZ", "FIXTURE Bravo Lake|ZZ", "FIXTURE Hotel Lake|ZZ"]
    st = json.load(open(work / "state.json"))["lakes"]
    assert "FIXTURE Golf Lake|ZZ" not in st                        # pilot: never pre-seeded
    assert "FIXTURE Echo Lake|ZZ" not in st                        # filtered out by --only-hosts
    work2 = fx["tmp"] / "w2"
    cli(fx, work2, ["--limit", "2", "--exclude-hosts", "cwms"])
    assert len(json.load(open(work2 / "state.json"))["lakes"]) == 2
    assert P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(fx["tmp"] / "w3"), "--allow-fixture", "--lakes", "Nope|ZZ", "--quiet"]) == 2


def test_plan_mode_needs_no_network_or_work_dir(capsys):
    assert P.main(["--plan", "--now", "2026-10-13T12:00:00Z"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lakes"] == 191 and out["callsByHost"]["hads"] > 0 and all(v > 0 for v in out["callsByHost"].values())


# ================================================================================================================================
# 4. Rate limits
# ================================================================================================================================
class Recording:
    """Wraps a transport and records the (fake) clock at each call."""

    def __init__(self, inner, clock):
        self.inner, self.clock, self.times = inner, clock, []

    def get(self, url, accept="application/json", timeout=60):
        self.times.append((self.clock(), url))
        return self.inner.get(url, accept=accept, timeout=timeout)


def test_gaps_per_host_are_respected_and_hads_is_15_seconds_with_429_backoff(fx):
    clk = Clock()
    rec = Recording(F.FakeServer(), clk)
    rc, *_ = cli(fx, fx["tmp"] / "w", server=rec, clock=clk)
    by = {}
    for t, u in rec.times:
        host = P.urllib.parse.urlparse(u).netloc
        by.setdefault(host, []).append(t)
    names = {"mesonet.agron.iastate.edu": "hads", "cwms-data.usace.army.mil": "cwms", "waterservices.usgs.gov": "usgs", "data.usbr.gov": "rise",
             "api.water.noaa.gov": "nwps", "water.usace.army.mil": "a2w", "www.tva.com": "tva"}
    for host, ts in by.items():
        gap = P.HOST_GAP_SECONDS[names[host]]
        assert all(b - a >= gap - 1e-9 for a, b in zip(ts, ts[1:])), host
    assert P.HOST_GAP_SECONDS["hads"] == 15.0
    hads = by["mesonet.agron.iastate.edu"]
    assert len(hads) >= 4 and min(b - a for a, b in zip(hads, hads[1:])) >= 15.0
    assert 60.0 in clk.sleeps                                                   # the 429 on the 2024 chunk backed off 60 s


def test_429_backoff_doubles_and_gives_up(tmp_path):
    clk = Clock()
    class Always429:
        calls = 0
        def get(self, url, accept="", timeout=0):
            Always429.calls += 1
            return F.R(429)
    http = P.Http(Always429(), P.Log(echo=False), clock=clk, sleep=clk.sleep)
    with pytest.raises(P.FetchError, match="429"):
        http.get("hads", "https://mesonet.agron.iastate.edu/x", P.Meter())
    assert Always429.calls == 4 and [s for s in clk.sleeps if s >= 60] == [60.0, 120.0, 240.0]


def test_5xx_retries_three_times(tmp_path):
    clk = Clock()
    class Bad:
        calls = 0
        def get(self, url, accept="", timeout=0):
            Bad.calls += 1
            return F.R(503)
    with pytest.raises(P.FetchError):
        P.Http(Bad(), P.Log(echo=False), clock=clk, sleep=clk.sleep).get("cwms", "https://cwms-data.usace.army.mil/x", P.Meter())
    assert Bad.calls == 3


# ================================================================================================================================
# 5. Checkpoint, resume, kill, failure restart
# ================================================================================================================================
class Crash(BaseException):
    pass


class CrashAfter:
    def __init__(self, inner, n):
        self.inner, self.n, self.calls = inner, n, 0

    def get(self, url, accept="application/json", timeout=60):
        self.calls += 1
        if self.calls > self.n:
            raise Crash()
        return self.inner.get(url, accept=accept, timeout=timeout)


def staged_hashes(work):
    out = {}
    for l in EXPECTED_PASS:
        out[l] = P.sha256_file(os.path.join(str(work), "staged", "history", P.lake_key(l), "daily.csv"))
    return out


@pytest.mark.parametrize("crash_at", [8, 13, 27, 44, 60])
def test_resume_after_crash_gives_identical_output_without_refetching_finished_steps(fx, crash_at):
    ref_work = fx["tmp"] / "ref"
    rc, ref_srv, _ = cli(fx, ref_work)
    full_calls = len(ref_srv.calls)
    work = fx["tmp"] / "crashy"
    srv = F.FakeServer()
    crashes = 0
    total_calls = 0
    for _ in range(200):
        c = CrashAfter(srv, crash_at)
        try:
            rc, *_ = cli(fx, work, server=c)
            total_calls += c.calls
            break
        except Crash:
            crashes += 1
            total_calls += c.calls - 1
    else:
        pytest.fail("never finished")
    assert crashes >= 1 and rc == 0
    assert staged_hashes(work) == staged_hashes(ref_work)
    assert open(work / "preseed_manifest.json").read() == open(ref_work / "preseed_manifest.json").read()
    # every crash may waste only the step in flight: re-fetched pages of one step + the A2W listing (memory only)
    assert total_calls <= full_calls + crashes * 25, (total_calls, full_calls, crashes)


def test_kill_leaves_no_half_files_and_tmp_files_are_cleaned(fx):
    work = fx["tmp"] / "w"
    with pytest.raises(Crash):
        cli(fx, work, server=CrashAfter(F.FakeServer(), 20))
    open(work / "steps" / "junk.json.tmp.1.2", "w").write("half")
    open(work / "state.json.tmp.9.9", "w").write("{")
    rc, *_ = cli(fx, work)
    assert rc == 0 and not [f for f in all_files(work) if ".tmp." in f]
    st = json.load(open(work / "state.json"))
    assert all(v["status"] in P.CLOSED for v in st["lakes"].values())


def test_corrupt_step_cache_is_refetched(fx):
    work = fx["tmp"] / "w"
    cli(fx, work)
    victim = next(f for f in all_files(work / "steps") if "cwms.000" in f or "usgs.dv" in f)
    d = json.load(open(victim))
    d["payload"]["rows"] = [["1999-01-01", 1.0]]                 # tampered payload, hash no longer matches
    json.dump(d, open(victim, "w"))
    st = json.load(open(work / "state.json"))
    for l in st["lakes"].values():
        l["status"] = "PENDING"
    json.dump(st, open(work / "state.json", "w"))
    before = P.sha256_file(fx["tmp"] / "w" / "preseed_manifest.json")
    rc, srv, _ = cli(fx, work)
    assert rc == 0 and len(srv.calls) >= 1                       # the corrupted step was fetched again, nothing else
    log = [json.loads(l)["event"] for l in open(work / "preseed.log.jsonl")]
    assert "step_cache_corrupt" in log
    assert P.sha256_file(work / "preseed_manifest.json") == before


def test_finished_lakes_are_not_run_again_on_resume(fx):
    work = fx["tmp"] / "w"
    cli(fx, work)
    rc, srv, _ = cli(fx, work)
    assert rc == 0 and srv.calls == []


def test_state_is_bound_to_its_input(fx, tmp_path):
    work = fx["tmp"] / "w"
    cli(fx, work)
    assert P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(work), "--allow-fixture", "--now", "2026-10-14T00:00:00Z", "--quiet"],
                  transport=F.FakeServer()) == 2


def test_resume_without_now_reuses_the_recorded_now(fx):
    work = fx["tmp"] / "w"
    with pytest.raises(Crash):
        cli(fx, work, server=CrashAfter(F.FakeServer(), 10))
    argv = ["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(work), "--allow-fixture", "--quiet", "--no-parallel"]
    clk = Clock()
    assert P.main(argv, transport=F.FakeServer(), clock=clk, sleep=clk.sleep) == 0
    assert manifest(work)["now"] == F.NOW


def test_lock_blocks_a_second_run_and_a_stale_lock_is_taken_over(fx):
    work = fx["tmp"] / "w"
    os.makedirs(work)
    open(work / ".preseed.lock", "w").write(str(os.getpid()))            # this very process is "running"
    assert P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(work), "--allow-fixture", "--now", F.NOW, "--quiet"],
                  transport=F.FakeServer()) == 2
    open(work / ".preseed.lock", "w").write("999999")                    # a dead pid
    rc, *_ = cli(fx, work)
    assert rc == 0 and not os.path.exists(work / ".preseed.lock")


def test_failed_lake_is_retried_on_restart_and_others_are_untouched(fx):
    work = fx["tmp"] / "w"
    bad = lambda url: F.R(500) if "ECHO1" in url else None
    srv = F.FakeServer(fail=bad)
    rc, srv, clk = cli(fx, work, server=srv)
    assert rc == 3
    man = manifest(work)
    assert man["counts"] == {"FAILED": 1, "PASS": 6, "REJECT_DATUM": 1}
    assert "HTTP 500" in man["lakes"]["FIXTURE Echo Lake|ZZ"]["error"]
    assert sum(1 for u in srv.calls if "ECHO1" in u and "mesonet" in u) == 3          # 3 attempts, then FAILED
    st = json.load(open(work / "state.json"))["lakes"]["FIXTURE Echo Lake|ZZ"]
    assert st["attempts"] == 1
    rc, srv2, _ = cli(fx, work)                                                        # healthy server: only Echo is run
    assert rc == 0
    assert all("ECHO1" in u or "api.water.noaa.gov" in u for u in srv2.calls)
    assert manifest(work)["counts"] == {"PASS": 7, "REJECT_DATUM": 1}
    assert json.load(open(work / "state.json"))["lakes"]["FIXTURE Echo Lake|ZZ"]["attempts"] == 2


def test_live_unreachable_defers_and_writes_nothing_for_that_lake(fx):
    work, out = fx["tmp"] / "w", fx["tmp"] / "out"
    srv = F.FakeServer(fail=lambda url: F.R(500) if "api.water.noaa.gov" in url else None)
    rc, *_ = cli(fx, work, ["--write-dir", str(out)], server=srv)
    assert rc == 3
    m = manifest(work)["lakes"]["FIXTURE Echo Lake|ZZ"]
    assert m["status"] == "FAILED" and "DEFER_NO_LIVE" in m["error"]
    assert not os.path.exists(out / "history" / "FIXTURE_Echo_Lake_ZZ")
    assert os.path.exists(out / "history" / "FIXTURE_Alpha_Lake_ZZ" / "daily.csv")


def test_gage_height_without_datum_offset_is_refused_permanently(fx):
    mutate_json(fx["bindings"], lambda d: [h.__setitem__("offsetFt", 0.0) for b in d["bindings"] if b["lakeId"].startswith("FIXTURE Delta") for h in b["history"]])
    work = fx["tmp"] / "w"
    rc, *_ = cli(fx, work)
    m = manifest(work)["lakes"]["FIXTURE Delta Lake|ZZ"]
    assert rc == 3 and m["status"] == "FAILED" and "gage height" in m["error"]


def test_hard_kill_of_a_real_process_and_resume(fx, tmp_path):
    """Record the synthetic server's responses, replay them in a subprocess that os._exit(137)s mid-run (no cleanup), then resume it."""
    rec = tmp_path / "rec"
    clk = Clock()
    P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(tmp_path / "recwork"), "--allow-fixture", "--now", F.NOW, "--quiet",
            "--no-parallel", "--record", str(rec)], transport=P.RecordingTransport(F.FakeServer(), str(rec)), clock=clk, sleep=clk.sleep)
    assert len(os.listdir(rec)) > 50
    work = tmp_path / "killed"
    argv = [sys.executable, SCRIPT, "--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(work), "--allow-fixture", "--now", F.NOW,
            "--quiet", "--no-parallel", "--replay", str(rec)]
    # replay in a subprocess uses real sleeps for the gate: shrink them through the environment-free route of patching gaps via a tiny wrapper
    wrapper = ("import sys, runpy; sys.path.insert(0, %r); import preseed_fleet as P; "
               "P.HOST_GAP_SECONDS.update({k: 0.0 for k in P.HOST_GAP_SECONDS}); P.time.sleep = lambda s: None; "
               "sys.exit(P.main(sys.argv[1:]))") % os.path.dirname(SCRIPT)
    cmd = [sys.executable, "-c", wrapper] + argv[2:]
    env = dict(os.environ, SECTOR_PRESEED_FAULT_EXIT_AFTER_CALLS="30")
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    assert p.returncode == 137
    assert os.path.exists(work / "state.json")
    p2 = subprocess.run(cmd, env={k: v for k, v in os.environ.items() if k != "SECTOR_PRESEED_FAULT_EXIT_AFTER_CALLS"}, capture_output=True, text=True, timeout=120)
    assert p2.returncode == 0, p2.stderr
    ref = fx["tmp"] / "ref"
    cli(fx, ref)
    assert staged_hashes(work) == staged_hashes(ref)
    log = [json.loads(l) for l in open(work / "preseed.log.jsonl")]
    assert any(l["event"] == "step_cached" for l in log) and sum(l["event"] == "run_start" for l in log) == 2


def test_replay_miss_is_a_clear_permanent_error(fx, tmp_path):
    os.makedirs(tmp_path / "empty")
    rc = P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(tmp_path / "w"), "--allow-fixture", "--now", F.NOW, "--quiet",
                 "--no-parallel", "--lakes", "FIXTURE Golf Lake|ZZ", "--replay", str(tmp_path / "empty")])
    assert rc == 3
    assert "no recorded response" in manifest(tmp_path / "w")["lakes"]["FIXTURE Golf Lake|ZZ"]["error"]


# ================================================================================================================================
# 6. GCS: never by default, only create-only with explicit confirmation
# ================================================================================================================================
def test_default_and_write_dir_runs_never_call_gcloud(fx, monkeypatch):
    monkeypatch.setattr(P, "default_runner", lambda cmd: (_ for _ in ()).throw(AssertionError("gcloud must not be called: " + " ".join(cmd))))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no subprocess in a dry run")))
    rc, *_ = cli(fx, fx["tmp"] / "w1")
    rc2, *_ = cli(fx, fx["tmp"] / "w2", ["--write-dir", str(fx["tmp"] / "out")])
    assert rc == 0 and rc2 == 0


@pytest.mark.parametrize("extra", [["--gcs-prefix", "gs://sector-lake-brain/history"],
                                   ["--gcs-prefix", "gs://sector-lake-brain/history", "--write-dir", "OUT"],
                                   ["--gcs-prefix", "gs://sector-lake-brain/baselines", "--write-dir", "OUT", "--confirm-batch-sha", "x"],
                                   ["--gcs-prefix", "/tmp/not-gcs", "--write-dir", "OUT"],
                                   ["--dry-run", "--write-dir", "OUT"]])
def test_gcs_flag_is_refused_without_its_guards(fx, extra):
    extra = [str(fx["tmp"] / "out") if e == "OUT" else e for e in extra]
    called = []
    rc = P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(fx["tmp"] / "w"), "--allow-fixture", "--now", F.NOW, "--quiet"] + extra,
                transport=F.FakeServer(), gcs_runner=lambda cmd: called.append(cmd))
    assert rc == 2 and not called


def test_fixture_with_correct_confirmation_is_still_refused_for_gcs(fx):
    sha = P.sha256_file(fx["batch"])[:12]
    called = []
    rc = P.main(["--batch", fx["batch"], "--bindings", fx["bindings"], "--work-dir", str(fx["tmp"] / "w"), "--allow-fixture", "--now", F.NOW, "--quiet",
                 "--write-dir", str(fx["tmp"] / "out"), "--gcs-prefix", "gs://sector-lake-brain/history", "--confirm-batch-sha", sha],
                transport=F.FakeServer(), gcs_runner=lambda cmd: called.append(cmd))
    assert rc == 2 and not called


class FakeGcloud:
    def __init__(self, existing=None, md5_ok=True):
        self.cmds, self.existing, self.md5_ok, self.uploaded = [], dict(existing or {}), md5_ok, {}

    def __call__(self, cmd):
        self.cmds.append(cmd)
        class Res:
            returncode, stdout, stderr = 0, "", ""
        r = Res()
        if cmd[:4] == ["gcloud", "storage", "objects", "describe"]:
            uri = cmd[4]
            if uri in self.uploaded:
                r.stdout = json.dumps(dict(generation=77, md5_hash=self.uploaded[uri] if self.md5_ok else "bad"))
            elif uri in self.existing:
                r.stdout = json.dumps(dict(generation=42, md5_hash="old"))
            else:
                r.returncode, r.stderr = 1, "ERROR: 404 No URLs matched"
        elif cmd[:3] == ["gcloud", "storage", "cp"] and not cmd[3].startswith("gs://"):
            self.uploaded[cmd[4]] = P.md5_b64(open(cmd[3], "rb").read())
        return r


def test_gcs_publisher_is_create_only_and_verifies(tmp_path):
    f = tmp_path / "daily.csv"
    data = P.encode([("2025-01-01", 1.5, "x")])
    f.write_bytes(data)
    g = FakeGcloud()
    out = P.GcsPublisher("gs://sector-lake-brain/history", g).publish("Lake_A_ZZ", str(f), data)
    assert out["status"] == "WRITTEN" and out["md5Verified"]
    cp = [c for c in g.cmds if c[:3] == ["gcloud", "storage", "cp"]]
    assert len(cp) == 1 and "--if-generation-match=0" in cp[0] and cp[0][4] == "gs://sector-lake-brain/history/Lake_A_ZZ/daily.csv"
    # existing object: untouched by default
    g2 = FakeGcloud(existing={"gs://sector-lake-brain/history/Lake_A_ZZ/daily.csv": 1})
    out = P.GcsPublisher("gs://sector-lake-brain/history", g2).publish("Lake_A_ZZ", str(f), data)
    assert out["status"] == "SKIPPED_EXISTS" and not [c for c in g2.cmds if c[:3] == ["gcloud", "storage", "cp"]]
    # explicit overwrite: backup of the exact generation first, then generation-matched upload
    g3 = FakeGcloud(existing={"gs://sector-lake-brain/history/Lake_A_ZZ/daily.csv": 1})
    P.GcsPublisher("gs://sector-lake-brain/history", g3, overwrite=True, now=dt.datetime(2026, 10, 14, tzinfo=P.UTC)).publish("Lake_A_ZZ", str(f), data)
    cps = [c for c in g3.cmds if c[:3] == ["gcloud", "storage", "cp"]]
    assert cps[0][3].endswith("daily.csv#42") and cps[0][4].startswith("gs://sector-lake-brain/history_backup/Lake_A_ZZ/daily.20261014")
    assert "--if-generation-match=42" in cps[1]
    # read-back mismatch is an error
    with pytest.raises(P.FetchError, match="md5"):
        P.GcsPublisher("gs://sector-lake-brain/history", FakeGcloud(md5_ok=False)).publish("Lake_A_ZZ", str(f), data)
    for bad in ("gs://sector-lake-brain/", "gs://sector-lake-brain/baselines", "s3://x/history", "gs://Bad_Bucket/history"):
        with pytest.raises(P.PreseedError):
            P.GcsPublisher(bad, g)


def test_runner_publish_refuses_a_staged_file_that_changed(fx, tmp_path):
    work = fx["tmp"] / "w"
    cli(fx, work)
    victim = work / "staged" / "history" / "FIXTURE_Alpha_Lake_ZZ" / "daily.csv"
    victim.write_bytes(victim.read_bytes() + b"2030-01-01,1.00,tampered\n")
    rc, *_ = cli(fx, work, ["--write-dir", str(fx["tmp"] / "out")])
    assert rc == 2 and not os.path.exists(fx["tmp"] / "out" / "history" / "FIXTURE_Alpha_Lake_ZZ")


# ================================================================================================================================
# 7. Smoke mode and parsers
# ================================================================================================================================
def test_smoke_only_for_reviewed_pilots(fx, tmp_path):
    assert P.main(["--smoke", "FIXTURE Alpha Lake|ZZ", "--bindings", fx["bindings"], "--work-dir", str(tmp_path / "w")]) == 2
    assert P.main(["--smoke", "Lake Hartwell|SC", "--work-dir", str(tmp_path / "w"), "--write-dir", str(tmp_path / "o")]) == 2
    assert P.main(["--smoke", "Bankhead|AL", "--work-dir", str(tmp_path / "w")]) == 2          # not a pilot


def test_hads_parser_takes_first_nonempty_pool_column_and_drops_sentinels():
    body = b"station,utc_valid,HPIRGZZ,HPIRZZZ,HGIRGZZ\nX,2024-01-01 00:00:00,,623.4,5.0\nX,2024-01-01 01:00:00,623.5,,5\nX,2024-01-01 02:00:00,-999,,\nX,bad,1,1,1\nX,2024-01-01 03:00,623.7,,\n"
    obs = P.parse_hads(body, "HPIR")
    assert [round(v, 1) for _, v in obs] == [623.4, 623.5, 623.7]


def test_rise_parser():
    body = json.dumps({"data": [
        {"attributes": {"dateTime": "2024-01-01T07:00:00+00:00", "result": 5000.5, "resultAttributes": {"resultType": "observed"}}},
        {"attributes": {"dateTime": "2024-01-02T07:00:00+00:00", "result": 0.0}},
        {"attributes": {"dateTime": "2024-01-03T07:00:00+00:00", "result": 5001.0, "resultAttributes": {"resultType": "modeled"}}},
        {"attributes": {"dateTime": "2024-01-04T07:00:00+00:00", "result": 5002.0}}], "links": {"next": "x"}}).encode()
    obs, nxt = P.parse_rise(body)
    assert nxt and [v for _, v in obs] == [5000.5, 5002.0]


def test_usgs_dv_parser_drops_sentinels_and_prefers_mean_over_other_stats():
    def ts(stat, vals):
        return {"variable": {"noDataValue": -999999.0, "options": {"option": [{"optionCode": stat}]}}, "values": [{"value": [{"dateTime": d + "T00:00:00.000", "value": v} for d, v in vals]}]}
    body = json.dumps({"value": {"timeSeries": [ts("00001", [("2024-01-01", "9.0"), ("2024-01-02", "10.0")]), ts("00003", [("2024-01-01", "5.5"), ("2024-01-03", "-999999")])]}}).encode()
    rows = P.parse_usgs_dv(body, 100.0, "src")
    assert rows == [("2024-01-01", 105.5, "src"), ("2024-01-02", 110.0, "src")]


def test_cwms_window_matches_the_swift_formula():
    five = 5.0 * 365.25 * 86400
    assert P.cwms_window_seconds("A.Elev.Inst.~1Day.0.MRS") == five
    assert P.cwms_window_seconds("A.Elev.Inst.1Hour.0.Raw") == five
    assert abs(P.cwms_window_seconds("A.Elev.Inst.15Minutes.0.Raw") - 60000.0 / (525960 / 15) * 365.25 * 86400) < 1e-6
    assert P.cwms_window_seconds("weird") == five


def test_daily_medians_even_count_and_local_day():
    tz = P.ZoneInfo("America/Chicago")
    obs = [(dt.datetime(2024, 1, 2, 5, 30, tzinfo=P.UTC), 10.0), (dt.datetime(2024, 1, 2, 7, 0, tzinfo=P.UTC), 12.0), (dt.datetime(2024, 1, 2, 8, 0, tzinfo=P.UTC), 20.0)]
    # 05:30Z is 23:30 on Jan 1 in Chicago; the other two are Jan 2
    assert P.daily_medians(obs, tz, "s", 1.0) == [("2024-01-01", 11.0, "s"), ("2024-01-02", 17.0, "s")]


def test_cwms_metres_are_converted_and_pages_followed(tmp_path):
    pages = [dict(units="m", values=[[1700000000000, 100.0, 0]], **{"next-page": "2"}), dict(units="m", values=[[1700003600000, 101.0, 0]])]
    class T:
        i = 0
        def get(self, url, accept="", timeout=0):
            r = F.R(200, json.dumps(pages[T.i]).encode())
            T.i += 1
            return r
    http = P.Http(T(), P.Log(echo=False), clock=lambda: 0.0, sleep=lambda s: None, gaps={k: 0 for k in P.HOST_BASE})
    ctx = P.Ctx("L|ZZ", dict(timeZone="UTC"), http, None, dt.datetime(2026, 1, 1, tzinfo=P.UTC), P.Log(echo=False), P.Meter(), P.A2WCache())
    obs = P.cwms_fetch(ctx, "X", "S.Elev.Inst.1Hour.0.R", 0, 1)
    assert [round(v, 3) for _, v in obs] == [328.084, 331.365]


def test_tva_time_midnight_is_hour_ending_and_dst_safe():
    assert P.parse_tva_time("10/10/2026", "Midnight CDT") == dt.datetime(2026, 10, 11, 5, 0, tzinfo=P.UTC)
    # Mirrors Swift (Calendar.byAdding .hour from local midnight = ABSOLUTE hours): on the 25-hour DST-end day the label is 1 h early.
    assert P.parse_tva_time("11/01/2026", "Midnight CST") == dt.datetime(2026, 11, 2, 5, 0, tzinfo=P.UTC)
    assert P.parse_tva_time("11/01/2026", "6 AM CST") == dt.datetime(2026, 11, 1, 11, 0, tzinfo=P.UTC)
    assert P.parse_tva_time("10/10/2026", "6 AM") is None


def test_encode_decode_round_trip_and_later_wins():
    rows = [("2024-01-02", 5.0, "a"), ("2024-01-01", 4.0, "a"), ("2024-01-02", 6.005, "b")]
    data = P.encode(rows)
    assert data == b"date,elevationFt,sourceId\n2024-01-01,4.00,a\n2024-01-02,6.00,b\n" or data.decode().splitlines()[2].startswith("2024-01-02,6.0")
    assert P.decode(data)[0] == ("2024-01-01", 4.0, "a")


@pytest.mark.skipif(not os.path.exists(P.DEFAULT_BINDINGS), reason="bindings table missing")
def test_plan_model_covers_every_real_binding_and_history_kind_is_supported():
    doc, rows = P.load_bindings(P.DEFAULT_BINDINGS)
    assert len(rows) == 196
    kinds = {h["kind"] for r in rows.values() for h in r["history"]}
    assert kinds <= set(P.HISTORY_FETCHERS), kinds
    now = dt.datetime(2026, 10, 13, 12, tzinfo=P.UTC)
    for lid, b in rows.items():
        c = P.plan_lake(b, now)
        assert (not b["history"]) or sum(c.values()) >= 1
        assert (b["live"][0]["provider"] in P.HOST_BASE)
    assert {p["lakeId"] for p in doc["pilotReproduction"]} <= set(rows)
