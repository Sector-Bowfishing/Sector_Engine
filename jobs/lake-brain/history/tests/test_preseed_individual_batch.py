"""Tests for the SECOND legitimate accepted-batch form of preseed_fleet.validate_batch: an individually reviewed, cumulative batch written by
jobs/lake-brain/review/ingest_batch_review.py (reviewKind 'individual-cumulative'), alone or unioned with a sample-based result.

Everything is FIXTURE data (fixture_lib.py); the REAL ingest builds the batch; nothing touches jobs/lake-brain/data or the real review folders.
The existing tamper tests of the sample form stay in test_preseed_fleet.py."""
import json
import os
import hashlib

import pytest

import fixture_lib as F
import preseed_fleet as P


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture
def ib(tmp_path):
    b, r, bp = F.make_fixture_individual_batch(str(tmp_path / "data"), str(tmp_path / "work"))
    return dict(batch=b, result=r, bindings=bp, data=tmp_path / "data", tmp=tmp_path)


def validate(x, **kw):
    return P.validate_batch(x["batch"], x["result"], x["bindings"], allow_fixture=True, **kw)


def mutate(path, fn):
    d = json.load(open(path))
    fn(d)
    json.dump(d, open(path, "w"), indent=1)


def refresh_sha(x):
    """Keep acceptedBatchSha256 consistent after a deliberate edit of the batch, so the tamper test reaches the NEXT check."""
    mutate(x["result"], lambda r: r.__setitem__("acceptedBatchSha256", sha(x["batch"])))


def test_individual_cumulative_batch_validates(ib):
    v = validate(ib)
    assert len(v["batch"]) == 8 and v["fixture"] is True
    res = v["result"]
    assert res["reviewKind"] == "individual-cumulative" and res["verdict"] == "ACCEPTED_INDIVIDUALLY" and res["acceptedBatchSha256"] == sha(ib["batch"])
    assert [c["kind"] for c in res["components"]] == ["individual"] and res["components"][0]["resultSha256"] == sha(ib["data"] / "review_batches" / "consolidated_result.json")


def test_only_accepted_lakes_are_in_the_individual_batch(tmp_path):
    b, r, bp = F.make_fixture_individual_batch(str(tmp_path / "d"), str(tmp_path / "w"), decision=lambda lid: "REJECT" if ("Golf" in lid or "Alpha" in lid) else ("NEEDS REVIEW" if "Echo" in lid else "ACCEPT"))
    batch = json.load(open(b))
    assert len(batch) == 5 and not any(k in " ".join(batch) for k in ("Golf", "Alpha", "Echo"))
    assert P.validate_batch(b, r, bp, allow_fixture=True)["batch"] == batch


def test_the_pipeline_runs_on_an_individual_batch(ib, tmp_path):
    """End to end through the pre-seed CLI on fixture lakes (dry run, synthetic provider server): the individual form is accepted, not just validated."""
    import test_preseed_fleet as T
    fx = dict(batch=ib["batch"], result=ib["result"], bindings=ib["bindings"])
    rc, srv, _ = T.cli(fx, tmp_path / "w")
    assert rc == 0 and T.manifest(tmp_path / "w")["counts"]["PASS"] == 7


# ---------------------------------------------------------------------------------------------------------------- tamper: the new form
def test_edited_accepted_batch_json_is_refused(ib):
    mutate(ib["batch"], lambda b: b.pop())                                         # an id silently dropped, sha not updated
    with pytest.raises(P.PreseedError, match="acceptedBatchSha256"):
        validate(ib)


def test_wrong_sha_is_refused(ib):
    mutate(ib["result"], lambda r: r.__setitem__("acceptedBatchSha256", "0" * 64))
    with pytest.raises(P.PreseedError, match="does not match the batch file"):
        validate(ib)


def test_missing_sha_is_refused_for_the_individual_form(ib):
    mutate(ib["result"], lambda r: r.pop("acceptedBatchSha256"))
    with pytest.raises(P.PreseedError, match="acceptedBatchSha256"):
        validate(ib)
    mutate(ib["result"], lambda r: r.__setitem__("acceptedBatchSha256", "abc"))
    with pytest.raises(P.PreseedError, match="not a sha256"):
        validate(ib)


def test_id_not_in_any_batch_result_is_refused_even_with_a_consistent_sha_and_count(ib):
    extra = "FIXTURE Delta Lake|ZZ"
    # a packet where Delta was REJECTED, then the batch file is hand-edited to contain it, with sha and count kept consistent
    b, r, bp = F.make_fixture_individual_batch(str(ib["tmp"] / "d2"), str(ib["tmp"] / "w2"), decision=lambda lid: "REJECT" if "Delta" in lid else "ACCEPT")
    assert extra not in json.load(open(b))
    batch = sorted(json.load(open(b)) + [extra])
    json.dump(batch, open(b, "w"), indent=1)
    mutate(r, lambda d: (d.__setitem__("acceptedBatchCount", len(batch)), d.__setitem__("acceptedBatchSha256", sha(b))))
    with pytest.raises(P.PreseedError, match="in no batch result"):
        P.validate_batch(b, r, bp, allow_fixture=True)


def test_an_id_added_to_the_batch_that_no_packet_accepted_is_refused(ib):
    batch = sorted(json.load(open(ib["batch"])) + ["FIXTURE Zulu Lake|ZZ"])
    json.dump(batch, open(ib["batch"], "w"), indent=1)
    mutate(ib["result"], lambda r: r.__setitem__("acceptedBatchCount", len(batch)))
    refresh_sha(ib)
    with pytest.raises(P.PreseedError, match="in no batch result"):
        validate(ib)


def test_an_accepted_id_missing_from_the_batch_file_is_refused(ib):
    batch = json.load(open(ib["batch"]))[:-1]
    json.dump(batch, open(ib["batch"], "w"), indent=1)
    mutate(ib["result"], lambda r: r.__setitem__("acceptedBatchCount", len(batch)))
    refresh_sha(ib)
    with pytest.raises(P.PreseedError, match="missing from the batch file"):
        validate(ib)


def test_edited_component_result_file_is_refused(ib):
    f = ib["data"] / "review_batches" / "consolidated_result.json"
    mutate(str(f), lambda d: d["acceptedIds"].append("FIXTURE Zulu Lake|ZZ"))
    with pytest.raises(P.PreseedError, match="sha256 differs from the recorded one"):
        validate(ib)


def test_component_result_file_with_matching_sha_but_other_ids_is_refused(ib):
    f = str(ib["data"] / "review_batches" / "consolidated_result.json")
    mutate(f, lambda d: d.__setitem__("acceptedIds", d["acceptedIds"][:-1]))
    mutate(ib["result"], lambda r: r["components"][0].__setitem__("resultSha256", sha(f)))
    with pytest.raises(P.PreseedError, match="equal to the component's"):
        validate(ib)


def test_missing_component_file_and_path_games_are_refused(ib):
    os.remove(ib["data"] / "review_batches" / "consolidated_result.json")
    with pytest.raises(P.PreseedError, match="component file not found"):
        validate(ib)
    for bad in ("../consolidated_result.json", "/etc/passwd", "consolidated_result.json", "review_batches/../x.json"):
        mutate(ib["result"], lambda r: r["components"][0].__setitem__("resultFile", bad))
        with pytest.raises(P.PreseedError, match="review_batches/<file>"):
            validate(ib)


@pytest.mark.parametrize("name,edit,match", [
    ("verdict", lambda r: r.__setitem__("verdict", "ACCEPT_BATCH"), "ACCEPTED_INDIVIDUALLY"),
    ("criteria", lambda r: r.__setitem__("criteriaVersion", "binding-review-v2"), "criteriaVersion"),
    ("count", lambda r: r.__setitem__("acceptedBatchCount", 9), "acceptedBatchCount"),
    ("file name", lambda r: r.__setitem__("acceptedBatchFile", "other.json"), "accepted_batch.json"),
    ("component kind", lambda r: r["components"][0].__setitem__("kind", "magic"), "unknown component kind"),
    ("no components", lambda r: r.__setitem__("components", []), "no components"),
    ("only a sample component", lambda r: r.__setitem__("components", [dict(kind="sample")]), "review_batches/<file>"),
    ("held lake", lambda r: r["heldBackLakes"].append("FIXTURE Bravo Lake|ZZ"), "held back"),
    ("rejected id in batch", lambda r: r["rejectedIds"].append("FIXTURE Bravo Lake|ZZ"), "rejected ids"),
    ("missing field", lambda r: r.pop("rejectedIds"), "lacks field"),
])
def test_other_tampering_of_the_cumulative_result_is_refused(ib, name, edit, match):
    mutate(ib["result"], edit)
    with pytest.raises(P.PreseedError, match=match):
        validate(ib)


def test_individual_batch_still_needs_a_machine_verified_table_row_and_the_fixture_gate(ib):
    mutate(ib["bindings"], lambda d: d["bindings"][0].__setitem__("status", "CANDIDATE"))
    with pytest.raises(P.PreseedError, match="MACHINE_VERIFIED"):
        validate(ib)
    with pytest.raises(P.PreseedError):
        P.validate_batch(ib["batch"], ib["result"], P.DEFAULT_BINDINGS, allow_fixture=True)                 # real table: unknown ids and fixture
    with pytest.raises(P.PreseedError, match="fixture"):
        validate(ib, gcs=True)


def test_sample_form_files_are_not_accepted_as_individual_and_vice_versa(ib, tmp_path):
    os.makedirs(str(tmp_path / "st"))
    b, r, bp = F.make_fixture_batch(str(tmp_path / "sb"), str(tmp_path / "st"))
    res = json.load(open(r))
    res["reviewKind"] = "individual-cumulative"                                    # a sample result dressed up as the new form
    json.dump(res, open(r, "w"))
    with pytest.raises(P.PreseedError, match="lacks field"):
        P.validate_batch(b, r, bp, allow_fixture=True)
    mutate(ib["result"], lambda d: d.pop("reviewKind"))                            # the new form without its kind falls to the sample checks
    with pytest.raises(P.PreseedError, match="lacks field"):
        validate(ib)


# ---------------------------------------------------------------------------------------------------------------- union with a sample result
@pytest.fixture
def union(tmp_path):
    """Sample batch (the real sample ingest on the fixture pack) accepting 8 lakes; Michael individually rejected Golf and accepted the rest."""
    os.makedirs(str(tmp_path / "sample_work"))
    F.make_fixture_batch(str(tmp_path / "sample_out"), str(tmp_path / "sample_work"))
    b, r, bp = F.make_fixture_individual_batch(str(tmp_path / "data"), str(tmp_path / "work"), only=("Alpha", "Golf", "Echo"),
                                               decision=lambda lid: "REJECT" if "Golf" in lid else ("ACCEPT" if "Alpha" in lid else "NEEDS REVIEW"), sample_dir=str(tmp_path / "sample_out"))
    return dict(batch=b, result=r, bindings=bp, data=tmp_path / "data", tmp=tmp_path)


def test_union_with_a_sample_result_validates_and_individual_decisions_win(union):
    v = validate(union)
    batch = v["batch"]
    assert [c["kind"] for c in v["result"]["components"]] == ["individual", "sample"]
    assert "FIXTURE Golf Lake|ZZ" not in batch                                      # individually rejected: extrapolation does not bring it back
    assert "FIXTURE Echo Lake|ZZ" not in batch                                      # NEEDS REVIEW: set aside, not extrapolated either
    assert "FIXTURE Alpha Lake|ZZ" in batch and "FIXTURE Bravo Lake|ZZ" in batch   # sample-accepted and not individually excluded
    assert len(batch) == 6 and batch == sorted(batch)


def test_union_rule_is_enforced_by_the_validator(union):
    batch = sorted(json.load(open(union["batch"])) + ["FIXTURE Golf Lake|ZZ"])      # an individually rejected lake put back
    json.dump(batch, open(union["batch"], "w"), indent=1)
    mutate(union["result"], lambda r: r.__setitem__("acceptedBatchCount", len(batch)))
    refresh_sha(union)
    with pytest.raises(P.PreseedError, match="in no batch result"):
        validate(union)


@pytest.mark.parametrize("fn,edit", [("sample_review_result.json", lambda d: d.__setitem__("rejected", 5)), ("sample_accepted_batch.json", lambda d: d.pop())])
def test_sample_component_files_are_sha_checked(union, fn, edit):
    mutate(str(union["data"] / "review_batches" / fn), edit)
    with pytest.raises(P.PreseedError, match="a file differs from its recorded sha256"):
        validate(union)


def test_sample_component_that_is_not_an_accepted_batch_is_refused(union):
    f = union["data"] / "review_batches" / "sample_review_result.json"
    mutate(str(f), lambda d: (d.__setitem__("ruleMet", False), d.__setitem__("verdict", "REJECT_BATCH")))
    mutate(union["result"], lambda r: r["components"][1].__setitem__("resultSha256", sha(str(f))))
    with pytest.raises(P.PreseedError, match="not an accepted binding-review-v1 sample batch"):
        validate(union)


def test_sample_rejected_lake_that_is_individually_accepted_is_refused(union):
    f = union["data"] / "review_batches" / "sample_review_result.json"
    mutate(str(f), lambda d: d.__setitem__("rejectedIds", ["FIXTURE Alpha Lake|ZZ"]))
    mutate(union["result"], lambda r: r["components"][1].__setitem__("resultSha256", sha(str(f))))
    with pytest.raises(P.PreseedError, match="individually accepted but rejected in the sample"):
        validate(union)


def test_a_result_with_only_a_sample_component_is_not_the_individual_form(union):
    mutate(union["result"], lambda r: r.__setitem__("components", [c for c in r["components"] if c["kind"] == "sample"]))
    with pytest.raises(P.PreseedError, match="no individual component"):
        validate(union)
