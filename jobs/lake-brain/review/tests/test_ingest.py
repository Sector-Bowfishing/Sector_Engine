"""Tests for the review ingestion script, using a synthetic pack and synthetic exports (no research data needed)."""
import csv
import json
import os

import pytest

import build_review_pack as B
import ingest_review_result as I
from review_stats import upper_bound

SAMPLE_PACK = "LBR-SAMPLE-test000001"
FLAGGED_PACK = "LBR-FLAGGED-test000001"
STRATA = {"a2w | DIRECT_OPERATOR_POOL": 40, "usgs | DIRECT_LAKE_GAUGE": 30, "tva | DIRECT_OPERATOR_POOL": 3}
SAMPLED = {"a2w | DIRECT_OPERATOR_POOL": 30, "usgs | DIRECT_LAKE_GAUGE": 27, "tva | DIRECT_OPERATOR_POOL": 3}  # 60 total


def make_pack(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    population, sample = [], []
    for s, size in STRATA.items():
        for i in range(size):
            lid = f"{s.split(' ')[0]}-lake-{i}|ST"
            insamp = i < SAMPLED[s]
            population.append([lid, s, "yes" if insamp else "no", s.split(" ")[0], s.split("| ")[1], "w1"])
            if insamp:
                sample.append(lid)
    with open(pack / "strict_population.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lake_id", "stratum", "in_sample", "provider", "capability_class", "found_in_wave"])
        w.writerows(population)
    with open(pack / "binding_review_sample.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lake_id", "stratum"])
        for r in population:
            if r[2] == "yes":
                w.writerow([r[0], r[1]])
    with open(pack / "held_back_coordinate_flags.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lake_id", "directory_coordinate_flag"])
        w.writerow(["held-lake-1|ST", "off_water"])
        w.writerow(["held-lake-2|ST", "identity_risk"])
    flagged = [f"flag-lake-{i}|ST" for i in range(57)]
    with open(pack / "binding_review_flagged57.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lake_id"])
        for lid in flagged:
            w.writerow([lid])
    json.dump(dict(criteria="binding-review-v1", samplePackId=SAMPLE_PACK, flaggedPackId=FLAGGED_PACK, seed=1, snapshotDate="2026-10-13",
                   acceptRule=dict(maxErrors=1)), open(pack / "pack_manifest.json", "w"))
    return pack, sample, flagged, population


def write_export(path, pack_id, ids, decision_of, extra_rows=()):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["pack_id", "lake_id", "lake_name", "stratum", "computer_recommendation", "decision", "notes", "decided_at_utc", "reviewer", "exported_at_utc"])
        for lid in ids:
            w.writerow([pack_id, lid, lid, "", "PASS", decision_of(lid), "", "2026-10-14T10:00:00Z", "Michael", "2026-10-14T11:00:00Z"])
        for r in extra_rows:
            w.writerow(r)


def run(tmp_path, review, flagged=None, write=True, pack=None):
    out = tmp_path / "out"
    argv = ["--review-csv", str(review), "--pack-dir", str(pack), "--out-dir", str(out), "--now", "2026-10-14T12:00:00Z"]
    if flagged:
        argv += ["--flagged-csv", str(flagged)]
    if write:
        argv.append("--write")
    code = I.main(argv)
    return code, out


def test_upper_bound_reference_values():
    assert round(100 * upper_bound(60, 0), 1) == 4.9
    assert round(100 * upper_bound(60, 1), 1) == 7.7
    assert round(100 * upper_bound(60, 2), 1) == 10.1
    assert round(100 * upper_bound(60, 3), 1) == 12.4
    assert round(100 * upper_bound(40, 0), 1) == 7.2
    assert upper_bound(0, 0) is None
    assert upper_bound(5, 5) == 1.0
    # exactness: P(X<=k | n, p_upper) == 0.05
    from review_stats import binom_cdf
    for n, k in ((60, 1), (137, 2), (23, 0)):
        assert abs(binom_cdf(k, n, upper_bound(n, k)) - 0.05) < 1e-9


def test_all_accepted_meets_rule_and_writes_batch(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    write_export(rv, SAMPLE_PACK, sample, lambda l: "ACCEPT")
    code, out = run(tmp_path, rv, pack=pack)
    assert code == 0
    res = json.load(open(out / "binding_review_result.json"))
    assert res["reviewed"] == 60 and res["rejected"] == 0 and res["ruleMet"] is True
    assert res["errorRateUpperBound95Percent"] == 4.87 or round(res["errorRateUpperBound95Percent"], 1) == 4.9
    batch = json.load(open(out / "accepted_batch.json"))
    assert isinstance(batch, list)
    assert sorted(batch) == sorted(r[0] for r in population)      # the whole eligible population (73), not just the sample
    assert not any(b.startswith(("held", "flag-")) for b in batch)
    assert res["verdict"] == "ACCEPT_BATCH" and res["fullReviewStrata"] == []


def test_dry_run_writes_nothing(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    write_export(rv, SAMPLE_PACK, sample, lambda l: "ACCEPT")
    code, out = run(tmp_path, rv, write=False, pack=pack)
    assert code == 0
    assert not out.exists()


def test_one_reject_passes_but_flags_its_stratum_and_drops_it_from_batch(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    bad = "usgs-lake-3|ST"
    write_export(rv, SAMPLE_PACK, sample, lambda l: "REJECT" if l == bad else "ACCEPT")
    code, out = run(tmp_path, rv, pack=pack)
    assert code == 0
    res = json.load(open(out / "binding_review_result.json"))
    assert res["ruleMet"] is True and res["rejected"] == 1
    assert round(res["errorRateUpperBound95Percent"], 1) == 7.7
    assert res["fullReviewStrata"] == ["usgs | DIRECT_LAKE_GAUGE"]
    batch = json.load(open(out / "accepted_batch.json"))
    assert bad not in batch
    assert not any(b.startswith("usgs-") for b in batch)           # whole stratum goes to full review
    assert len(batch) == 40 + 3
    strat = {s["stratum"]: s for s in res["strata"]}
    assert strat["usgs | DIRECT_LAKE_GAUGE"]["fullReviewRequired"] is True
    assert strat["a2w | DIRECT_OPERATOR_POOL"]["fullReviewRequired"] is False


def test_two_rejects_fail_rule_and_batch_is_empty(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    bad = {"a2w-lake-1|ST", "tva-lake-0|ST"}
    write_export(rv, SAMPLE_PACK, sample, lambda l: "REJECT" if l in bad else "ACCEPT")
    code, out = run(tmp_path, rv, pack=pack)
    assert code == 0
    res = json.load(open(out / "binding_review_result.json"))
    assert res["ruleMet"] is False and res["verdict"] == "REJECT_BATCH"
    assert round(res["errorRateUpperBound95Percent"], 1) == 10.1
    assert json.load(open(out / "accepted_batch.json")) == []
    assert set(res["fullReviewStrata"]) == {"a2w | DIRECT_OPERATOR_POOL", "tva | DIRECT_OPERATOR_POOL"}


def test_unsure_or_pending_keeps_batch_open(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    write_export(rv, SAMPLE_PACK, sample, lambda l: "UNSURE" if l == sample[0] else ("PENDING" if l == sample[1] else "ACCEPT"))
    code, out = run(tmp_path, rv, pack=pack)
    res = json.load(open(out / "binding_review_result.json"))
    assert code == 0 and res["ruleMet"] is False and res["verdict"] == "INCOMPLETE"
    assert res["reviewed"] == 58 and res["unsure"] == 1 and res["pending"] == 1
    assert json.load(open(out / "accepted_batch.json")) == []


def test_missing_rows_count_as_pending(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    write_export(rv, SAMPLE_PACK, sample[:50], lambda l: "ACCEPT")
    code, out = run(tmp_path, rv, pack=pack)
    res = json.load(open(out / "binding_review_result.json"))
    assert code == 0 and res["reviewed"] == 50 and res["pending"] == 10 and res["ruleMet"] is False


@pytest.mark.parametrize("case", ["unknown_id", "wrong_pack", "duplicate", "bad_decision", "held_id"])
def test_validation_errors_block_everything(tmp_path, case, capsys):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv = tmp_path / "rv.csv"
    pid = SAMPLE_PACK
    extra = []
    ids = list(sample)
    dec = lambda l: "ACCEPT"
    if case == "unknown_id":
        extra = [[pid, "not-in-pack|ST", "x", "", "PASS", "ACCEPT", "", "", "", ""]]
    elif case == "held_id":
        extra = [[pid, "held-lake-1|ST", "x", "", "PASS", "ACCEPT", "", "", "", ""]]       # held-back lakes can never be in a review export
    elif case == "wrong_pack":
        pid = "LBR-SAMPLE-other"
    elif case == "duplicate":
        extra = [[pid, sample[0], "x", "", "PASS", "REJECT", "", "", "", ""]]
    elif case == "bad_decision":
        dec = lambda l: "MAYBE" if l == sample[0] else "ACCEPT"
    write_export(rv, pid, ids, dec, extra)
    code, out = run(tmp_path, rv, pack=pack)
    assert code == 2
    assert not out.exists()
    assert "ERROR" in capsys.readouterr().err


def test_batch_never_contains_held_or_flagged_even_if_population_is_tampered(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    with open(pack / "strict_population.csv", "a", newline="") as f:
        csv.writer(f).writerow(["held-lake-1|ST", "a2w | DIRECT_OPERATOR_POOL", "no", "a2w", "DIRECT_OPERATOR_POOL", "w1"])
        csv.writer(f).writerow(["flag-lake-3|ST", "a2w | DIRECT_OPERATOR_POOL", "no", "a2w", "DIRECT_OPERATOR_POOL", "w1"])
    rv = tmp_path / "rv.csv"
    write_export(rv, SAMPLE_PACK, sample, lambda l: "ACCEPT")
    code, out = run(tmp_path, rv, pack=pack)
    batch = json.load(open(out / "accepted_batch.json"))
    assert "held-lake-1|ST" not in batch and "flag-lake-3|ST" not in batch
    assert len(batch) == 73


def test_flagged_csv_counts_and_never_in_batch(tmp_path):
    pack, sample, flagged, population = make_pack(tmp_path)
    rv, fv = tmp_path / "rv.csv", tmp_path / "fv.csv"
    write_export(rv, SAMPLE_PACK, sample, lambda l: "ACCEPT")
    dec = lambda l: "REJECT" if l.endswith("-5|ST") else ("UNSURE" if l.endswith("-6|ST") else "ACCEPT")
    write_export(fv, FLAGGED_PACK, flagged[:50], dec)
    code, out = run(tmp_path, rv, flagged=fv, pack=pack)
    res = json.load(open(out / "binding_review_result.json"))
    f = res["flagged57"]
    assert f["total"] == 57 and f["rejected"] == 1 and f["unsure"] == 1 and f["pending"] == 7 and f["accepted"] == 48 and f["complete"] is False
    batch = json.load(open(out / "accepted_batch.json"))
    assert not any(b.startswith("flag-") for b in batch)


def test_default_out_dir_is_repo_data_dir():
    assert I.DEFAULT_OUT.endswith(os.path.join("jobs", "lake-brain", "data"))


def test_accepted_batch_file_is_not_committed_with_ids():
    """The repository must not carry an accepted_batch.json with ids until the review is actually done."""
    p = os.path.join(I.DEFAULT_OUT, "accepted_batch.json")
    if os.path.exists(p):
        assert json.load(open(p)) == [] or os.environ.get("LAKE_BRAIN_REVIEW_DONE") == "1"


# ----------------------------------------------------------------------------- builder logic
def test_allocation_rules():
    sizes = {"a2w | OP": 78, "cwms | OP": 44, "nwps | LG": 22, "rise | OP": 25, "tva | OP": 11, "usgs | LG": 28, "x | LG": 3, "y | LG": 1, "z | LG": 1, "w | LG": 3}
    alloc = B.allocate(sizes, 60)
    assert sum(alloc.values()) == 60
    for s, n in sizes.items():
        if n <= 3:
            assert alloc[s] == n
        else:
            assert 2 <= alloc[s] <= n
    # proportional: larger strata get more
    assert alloc["a2w | OP"] > alloc["cwms | OP"] > alloc["tva | OP"]


def test_allocation_minimum_two_for_small_big_strata():
    sizes = {"a | OP": 200, "b | OP": 4, "c | LG": 5, "d | LG": 2}
    alloc = B.allocate(sizes, 60)
    assert alloc["d | LG"] == 2 and alloc["b | OP"] >= 2 and alloc["c | LG"] >= 2 and sum(alloc.values()) == 60


def test_draw_is_deterministic_for_a_seed():
    eligible = [dict(v2=dict(lake_id=f"L{i}|ST", provider="a2w" if i % 2 else "cwms", capability_class="DIRECT_OPERATOR_POOL")) for i in range(100)]
    a = B.draw_sample(eligible, 7, 60)[3]
    b = B.draw_sample(list(reversed(eligible)), 7, 60)[3]
    c = B.draw_sample(eligible, 8, 60)[3]
    assert a == b and a != c and len(a) == 60
