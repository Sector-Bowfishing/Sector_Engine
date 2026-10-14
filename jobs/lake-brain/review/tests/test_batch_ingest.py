"""Tests for ingest_batch_review.py (individual acceptance). Synthetic packet + synthetic exports; every output goes to tmp_path, never to the
real jobs/lake-brain/data."""
import copy
import hashlib
import json
import os

import pytest

import consolidated_common as CC
import held_lakes
import ingest_batch_review as I
from consolidated_helpers import mk_row, write_export, write_manifest_and_export, write_table

REAL_DATA = CC.DATA_DIR


def sub(tmp, name):
    d = tmp / name
    d.mkdir()
    return d


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


class World:
    """Synthetic packet: 6 Section A rows (in the table) + 3 Section B rows (not in the table), a table with the 6 + 4 other lakes + a pilot."""

    def __init__(self, tmp, suffix="TEST000001", n_a=6, n_b=3, start=1, decision_of=lambda sec, lid: "ACCEPT", b_in_table=()):
        self.tmp = tmp
        self.a = [mk_row(i) for i in range(start, start + n_a)]
        self.b = [mk_row(i) for i in range(start + 100, start + 100 + n_b)]
        self.pilot = "Synth pilot Lake|ZZ"
        extra_ids = [f"Synth other {i} Lake|ZZ" for i in range(4)] + [self.pilot]
        self.table = write_table(str(tmp / "table.json"), [r["id"] for r in self.a] + list(b_in_table) + extra_ids, pilots=[self.pilot])
        self.mp, self.ep, self.manifest, self.erows = write_manifest_and_export(tmp, self.a, self.b, suffix, decision_of, pilots=[self.pilot])
        self.data = tmp / "data"
        os.makedirs(self.data, exist_ok=True)

    def args(self, **kw):
        a = ["--export", self.ep, "--manifest", self.mp, "--bindings", self.table, "--data-dir", str(self.data)]
        for k, v in kw.items():
            a += [f"--{k.replace('_', '-')}"] + ([] if v is True else [str(v)])
        return a

    def rewrite(self, fn):
        rows = copy.deepcopy(self.erows)
        fn(rows)
        write_export(self.ep, rows)


def run(w, capsys, **kw):
    code = I.main(w.args(**kw))
    return code, capsys.readouterr().out


def decide(accept=(), reject=(), review=()):
    def f(sec, lid):
        return "ACCEPT" if lid in accept else "REJECT" if lid in reject else "NEEDS REVIEW" if lid in review else "REJECT"
    return f


# ------------------------------------------------------------------------------------------------ dry run and happy path
def test_dry_run_is_the_default_and_writes_nothing(tmp_path, capsys):
    w = World(tmp_path)
    code, out = run(w, capsys)
    assert code == 0 and "DRY RUN" in out
    assert os.listdir(w.data) == []
    assert "profiled lakes would be 5 + 6 = 11 (threshold 63)" in out and "52 more needed" in out
    assert not os.path.exists(os.path.join(REAL_DATA, "accepted_batch.json")) and not os.path.exists(os.path.join(REAL_DATA, "review_batches", "consolidated_result.json"))


def test_write_produces_result_cumulative_batch_and_cumulative_result(tmp_path, capsys):
    w = World(tmp_path)
    ids = [r["id"] for r in w.a]
    w.rewrite(lambda rows: [r.__setitem__("decision", {ids[0]: "REJECT", ids[1]: "needs review"}.get(r["lake_id"], "ACCEPT")) for r in rows])
    code, out = run(w, capsys, write=True)
    assert code == 0, out
    batch = json.load(open(w.data / "accepted_batch.json"))
    assert batch == sorted(ids[2:]) and len(batch) == 4                      # ONLY the Section A rows decided ACCEPT; B accepts are not in the table
    res = json.load(open(w.data / "review_batches" / "consolidated_result.json"))
    assert res["acceptedIds"] == sorted(ids[2:]) and res["rejectedIds"] == [ids[0]] and res["needsReviewIds"] == [ids[1]]
    assert res["reviewCsvSha256"] == sha(w.ep) and res["packManifestSha256"] == sha(w.mp) and res["packId"] == w.manifest["packId"]
    assert res["sectionB"]["accepted"] == 3 and res["sectionB"]["acceptedCountableIds"] == [] and len(res["sectionB"]["acceptedForLaterTableInclusionIds"]) == 3
    assert not set(res["sectionB"]["acceptedForLaterTableInclusionIds"]) & set(batch)
    cum = json.load(open(w.data / "binding_review_result.json"))
    assert cum["acceptedBatchSha256"] == sha(w.data / "accepted_batch.json") and cum["acceptedBatchCount"] == 4 and cum["reviewKind"] == CC.REVIEW_KIND
    assert cum["verdict"] == "ACCEPTED_INDIVIDUALLY" and cum["criteriaVersion"] == "binding-review-v1" and cum["profiledLakes"] == 9
    assert cum["components"][0]["resultSha256"] == sha(w.data / "review_batches" / "consolidated_result.json") and cum["components"][0]["reviewCsvSha256"] == sha(w.ep)
    assert "profiled lakes would be 5 + 4 = 9 (threshold 63)" in out
    assert sorted(os.listdir(w.data)) == ["accepted_batch.json", "binding_review_result.json", "review_batches"]


def test_reject_and_needs_review_rows_are_recorded_and_excluded(tmp_path, capsys):
    w = World(tmp_path, decision_of=lambda s, l: "REJECT" if s == "A" else "NEEDS REVIEW")
    code, out = run(w, capsys, write=True)
    assert code == 0
    res = json.load(open(w.data / "review_batches" / "consolidated_result.json"))
    assert res["acceptedIds"] == [] and len(res["rejectedIds"]) == 6 and len(res["needsReviewIds"]) == 3
    assert json.load(open(w.data / "accepted_batch.json")) == []
    assert {d["decision"] for d in res["decisions"]} == {"REJECT", "NEEDS REVIEW"}


def test_decisions_are_normalised_but_only_the_allowed_set_passes(tmp_path, capsys):
    w = World(tmp_path)
    w.rewrite(lambda rows: [r.__setitem__("decision", " accept ") for r in rows[:2]] + [r.__setitem__("decision", "Needs_Review") for r in rows[2:4]])
    code, out = run(w, capsys)
    assert code == 0
    w.rewrite(lambda rows: rows[0].__setitem__("decision", "UNSURE"))
    code, out = run(w, capsys)
    assert code == 2 and "UNSURE" in out and "not one of" in out
    w.rewrite(lambda rows: rows[0].__setitem__("decision", "YES"))
    assert run(w, capsys)[0] == 2


# ------------------------------------------------------------------------------------------------ Section B
def test_section_b_accept_counts_only_when_the_lake_is_in_the_table(tmp_path, capsys):
    b_id = "Synth 101 Lake|ZZ"                                                  # the first Section B row of World()
    w = World(sub(tmp_path, "w"), b_in_table=[b_id])
    code, out = run(w, capsys, write=True)
    assert code == 0
    res = json.load(open(w.data / "review_batches" / "consolidated_result.json"))
    assert res["sectionB"]["acceptedCountableIds"] == [b_id]
    assert b_id in json.load(open(w.data / "accepted_batch.json"))
    assert len(res["sectionB"]["acceptedForLaterTableInclusionIds"]) == 2 and not set(res["sectionB"]["acceptedForLaterTableInclusionIds"]) & set(json.load(open(w.data / "accepted_batch.json")))


def test_section_b_pilot_or_held_accept_never_counts(tmp_path, capsys):
    w = World(tmp_path)
    held = sorted(held_lakes.SERIES_MISMATCH)[0]
    w.manifest["held"] = [w.b[1]["id"]]
    json.dump(w.manifest, open(w.mp, "w"))
    table = json.load(open(w.table))
    table["bindings"] += [dict(lakeId=w.b[1]["id"], status="MACHINE_VERIFIED"), dict(lakeId=held, status="MACHINE_VERIFIED")]
    json.dump(table, open(w.table, "w"))
    code, out = run(w, capsys, write=True)
    assert code == 0
    res = json.load(open(w.data / "review_batches" / "consolidated_result.json"))
    assert w.b[1]["id"] not in res["acceptedIds"] and w.b[1]["id"] in res["sectionB"]["acceptedForLaterTableInclusionIds"]


def test_section_b_may_be_left_undecided(tmp_path, capsys):
    w = World(tmp_path)
    w.rewrite(lambda rows: [r.__setitem__("decision", "PENDING") for r in rows if r["section"] == "B"])
    code, out = run(w, capsys, write=True)
    assert code == 0
    res = json.load(open(w.data / "review_batches" / "consolidated_result.json"))
    assert res["sectionB"]["notDecided"] == 3 and len(res["notDecidedIds"]) == 3


# ------------------------------------------------------------------------------------------------ validation / tamper
def refused(w, capsys, needle, **kw):
    code, out = run(w, capsys, **kw)
    assert code == 2 and "REFUSED" in out and needle in out, out
    assert os.listdir(w.data) == []                      # nothing written, even with --write
    return out


def test_wrong_pack_id_is_refused(tmp_path, capsys):
    w = World(tmp_path)
    w.rewrite(lambda rows: rows[0].__setitem__("pack_id", "LBR-CONSOLIDATED-OTHER"))
    refused(w, capsys, "is not this packet", write=True)


def test_unknown_duplicate_and_missing_rows_are_refused(tmp_path, capsys):
    w = World(tmp_path)
    w.rewrite(lambda rows: rows.append(dict(rows[0], lake_id="Synth stranger Lake|ZZ")))
    refused(w, capsys, "unknown row", write=True)
    w.rewrite(lambda rows: rows.append(dict(rows[0])))
    refused(w, capsys, "duplicate row", write=True)
    w.rewrite(lambda rows: rows.pop(1))
    refused(w, capsys, "missing row", write=True)


def test_undecided_section_a_is_refused_unless_allow_partial(tmp_path, capsys):
    w = World(tmp_path)
    w.rewrite(lambda rows: rows[0].__setitem__("decision", "PENDING"))
    refused(w, capsys, "not decided", write=True)
    code, out = run(w, capsys, allow_partial=True, write=True)
    assert code == 0
    assert json.load(open(w.data / "review_batches" / "consolidated_result.json"))["acceptedIds"] == sorted(r["id"] for r in w.a[1:])


@pytest.mark.parametrize("col,val", [("lake_name", "Another Lake"), ("state", "TX"), ("provider", "usgs"), ("provider_identifier", "usgs: 12345"),
                                     ("computer_recommendation", "FLAG"), ("row_digest", "0" * 64), ("section", "B")])
def test_locked_fields_are_tamper_checked(tmp_path, capsys, col, val):
    w = World(tmp_path)
    w.rewrite(lambda rows: rows[0].__setitem__(col, val))
    out = refused(w, capsys, "", write=True)
    assert col in out or "unknown row" in out or "duplicate" in out or "missing row" in out


def test_section_a_pilot_held_or_non_table_lake_is_refused(tmp_path, capsys):
    w = World(tmp_path)
    # the packet itself (hand-edited manifest) lists a pilot
    w.manifest["pilots"] = [w.a[0]["id"]]
    json.dump(w.manifest, open(w.mp, "w"))
    refused(w, capsys, "REVIEWED pilots", write=True)
    w = World(sub(tmp_path, "h"))
    w.manifest["held"] = [w.a[2]["id"]]
    json.dump(w.manifest, open(w.mp, "w"))
    refused(w, capsys, "held back", write=True)
    w = World(sub(tmp_path, "t"))
    table = json.load(open(w.table))
    table["bindings"] = [b for b in table["bindings"] if b["lakeId"] != w.a[3]["id"]]
    json.dump(table, open(w.table, "w"))
    refused(w, capsys, "not in the bindings table", write=True)


def test_export_without_the_review_columns_is_refused(tmp_path, capsys):
    w = World(tmp_path)
    open(w.ep, "w").write("lake_id,decision\nx,ACCEPT\n")
    code, out = run(w, capsys)
    assert code == 2 and "lacks column" in out


def test_manifest_must_be_a_consolidated_packet(tmp_path, capsys):
    w = World(tmp_path)
    m = json.load(open(w.mp))
    m["schema"] = "something-else"
    json.dump(m, open(w.mp, "w"))
    code, out = run(w, capsys)
    assert code == 2 and "not a consolidated packet" in out
    m["schema"] = CC.SCHEMA_PACK
    m["decisions"] = ["ACCEPT", "REJECT", "UNSURE"]
    json.dump(m, open(w.mp, "w"))
    assert run(w, capsys)[0] == 2


# ------------------------------------------------------------------------------------------------ cumulative and union rules
def two_packets(tmp_path):
    w1 = World(sub(tmp_path, "p1"), suffix="TESTPACK001", start=1)
    w2 = World(sub(tmp_path, "p2"), suffix="TESTPACK002", start=50)
    w2.data = w1.data                                          # same data dir: the second packet joins the first
    table = json.load(open(w1.table))
    table["bindings"] += json.load(open(w2.table))["bindings"]
    json.dump(table, open(w1.table, "w"))
    w2.table = w1.table
    return w1, w2


def test_cumulative_batch_is_the_sorted_union_and_never_loses_an_id(tmp_path, capsys):
    w1, w2 = two_packets(tmp_path)
    assert run(w1, capsys, write=True)[0] == 0
    first = json.load(open(w1.data / "accepted_batch.json"))
    assert len(first) == 6
    code, out = run(w2, capsys, write=True)
    assert code == 2 and "DIFFERENT packet" in out                    # same default label: the first packet's result is never overwritten
    code, out = run(w2, capsys, write=True, label="second")
    assert code == 0, out
    both = json.load(open(w1.data / "accepted_batch.json"))
    assert both == sorted(set(first) | {r["id"] for r in w2.a}) and len(both) == 12 and len(set(both)) == 12
    cum = json.load(open(w1.data / "binding_review_result.json"))
    assert [c["packId"] for c in cum["components"]] == [w1.manifest["packId"], w2.manifest["packId"]] and cum["profiledLakes"] == 17
    assert sorted(os.listdir(w1.data / "review_batches")) == ["consolidated_result.json", "second_result.json"]


def test_reingesting_a_packet_with_fewer_accepts_needs_allow_revoke(tmp_path, capsys):
    w = World(tmp_path)
    assert run(w, capsys, write=True)[0] == 0
    ids = [r["id"] for r in w.a]
    w.rewrite(lambda rows: [r.__setitem__("decision", "REJECT" if r["lake_id"] == ids[0] else "ACCEPT") for r in rows])
    code, out = run(w, capsys, write=True)
    assert code == 2 and "never loses an id" in out
    assert json.load(open(w.data / "accepted_batch.json")) == sorted(ids)             # untouched
    code, out = run(w, capsys, write=True, allow_revoke=True)
    assert code == 0 and json.load(open(w.data / "accepted_batch.json")) == sorted(ids[1:])
    assert json.load(open(w.data / "binding_review_result.json"))["revokedAcceptIds"] == [ids[0]]


def make_sample_dir(tmp_path, ids, rejected=(), verdict="ACCEPT_BATCH", rule_met=True, extra=None):
    d = tmp_path / "sample_out"
    os.makedirs(d, exist_ok=True)
    json.dump(sorted(ids), open(d / "accepted_batch.json", "w"), indent=1)
    res = dict(criteriaVersion="binding-review-v1", packId="LBR-SAMPLE-TEST000001", reviewCsvSha256="a" * 64, sampleSize=60, reviewed=60, accepted=60 - len(rejected), rejected=len(rejected),
               unsure=0, pending=0, acceptRule=dict(maxErrors=1), ruleMet=rule_met, verdict=verdict, rejectedIds=sorted(rejected), fullReviewStrata=[],
               acceptedBatchCount=len(ids), acceptedBatchFile="accepted_batch.json", heldBackLakes=[])
    res.update(extra or {})
    json.dump(res, open(d / "binding_review_result.json", "w"), indent=1)
    return d


def test_union_with_a_sample_result_individual_decisions_win(tmp_path, capsys):
    w = World(tmp_path, decision_of=lambda s, l: "ACCEPT")
    ids = [r["id"] for r in w.a]
    # the sample accepted 3 lakes that Michael also accepted individually, 1 he rejects individually, plus 2 he never looked at
    w.rewrite(lambda rows: rows[1].__setitem__("decision", "REJECT"))
    sample_ids = ids[:3] + ["Synth other 0 Lake|ZZ", "Synth other 1 Lake|ZZ"]
    sd = make_sample_dir(tmp_path, sample_ids)
    code, out = run(w, capsys, write=True, sample_dir=sd)
    assert code == 0, out
    batch = json.load(open(w.data / "accepted_batch.json"))
    assert batch == sorted((set(ids) - {ids[1]}) | {"Synth other 0 Lake|ZZ", "Synth other 1 Lake|ZZ"})
    assert ids[1] not in batch                                                       # his individual REJECT beats the sample extrapolation
    cum = json.load(open(w.data / "binding_review_result.json"))
    kinds = [c["kind"] for c in cum["components"]]
    assert kinds == ["individual", "sample"] and cum["components"][1]["excludedByIndividualDecision"] == [ids[1]]
    assert cum["components"][1]["resultSha256"] == sha(w.data / "review_batches" / "sample_review_result.json")
    assert (w.data / "review_batches" / "sample_accepted_batch.json").exists()
    # a later run without --sample-dir still carries the stored sample component
    w2 = World(sub(tmp_path, "late"), suffix="TESTLATE001", start=300)
    w2.data = w.data
    table = json.load(open(w.table))
    table["bindings"] += json.load(open(w2.table))["bindings"]
    json.dump(table, open(w.table, "w"))
    w2.table = w.table
    assert run(w2, capsys, write=True, label="late")[0] == 0
    assert "Synth other 0 Lake|ZZ" in json.load(open(w.data / "accepted_batch.json"))


def test_sample_result_that_is_not_an_accepted_batch_is_refused(tmp_path, capsys):
    w = World(tmp_path)
    sd = make_sample_dir(tmp_path, ["Synth other 0 Lake|ZZ"], verdict="REJECT_BATCH", rule_met=False)
    code, out = run(w, capsys, sample_dir=sd)
    assert code == 2 and "sample result refused" in out
    sd2 = make_sample_dir(sub(tmp_path, "s2"), ["Synth other 0 Lake|ZZ"], extra=dict(pending=2))
    assert run(w, capsys, sample_dir=sd2)[0] == 2


def test_lake_individually_accepted_but_rejected_in_the_sample_is_a_conflict(tmp_path, capsys):
    w = World(tmp_path)
    sd = make_sample_dir(tmp_path, ["Synth other 0 Lake|ZZ"], rejected=[w.a[0]["id"]])
    code, out = run(w, capsys, sample_dir=sd, write=True)
    assert code == 2 and "REJECTED in the sample" in out and os.listdir(w.data) == []


def test_module_never_writes_into_the_repository_data_folder(tmp_path, capsys):
    before = sorted(os.listdir(REAL_DATA))
    w = World(tmp_path)
    run(w, capsys, write=True)
    assert sorted(os.listdir(REAL_DATA)) == before and not os.path.exists(os.path.join(REAL_DATA, "accepted_batch.json"))
