"""Tests for ingest_coordinate_review.py: validation against the pack manifest, tamper detection, dry-run default, no side effects."""
import csv
import hashlib
import json
import os

import pytest

import build_coordinate_review_pack as B
import ingest_coordinate_review as I
from test_coordinate_pack import make_rows

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data"))
COLS = ["pack_id", "lake_id", "lake_name", "state", "computer_recommendation", "current_lat", "current_lon", "proposed_lat", "proposed_lon",
        "row_digest", "decision", "notes", "decided_at_utc", "reviewer", "exported_at_utc"]


@pytest.fixture()
def pack(tmp_path):
    rows = make_rows()
    pid = B.pack_id_for(rows, "2026-10-13")
    meta = dict(snapshot="2026-10-13", registryGeneratedAt="x", registrySha256="ab" * 32, researchFlagged=4, registryOnly=0, decisions=list(B.DECISIONS))
    d = tmp_path / "pack"
    man = B.write_pack(str(d), rows, meta, pid, dict(byClass={}))
    return d, man


def export(path, man, decide=None, mutate=None, drop=(), extra=()):
    """Write an export CSV like the HTML form would. decide: lake_id -> decision (default: KEEP_CURRENT, or ACCEPT_PROPOSED when there is a proposal)."""
    rows = []
    for l in man["lakes"]:
        if l["lakeId"] in drop:
            continue
        dec = (decide or {}).get(l["lakeId"], "ACCEPT_PROPOSED" if l["proposedLat"] is not None else "KEEP_CURRENT")
        rows.append(dict(pack_id=man["packId"], lake_id=l["lakeId"], lake_name=l["name"], state=l["state"], computer_recommendation=l["recommendation"],
                         current_lat=l["currentLat"], current_lon=l["currentLon"], proposed_lat="" if l["proposedLat"] is None else l["proposedLat"],
                         proposed_lon="" if l["proposedLon"] is None else l["proposedLon"], row_digest=l["digest"], decision=dec, notes='looks ok, "quoted", comma',
                         decided_at_utc="2026-10-14T10:00:00Z", reviewer="Michael", exported_at_utc="2026-10-14T11:00:00Z"))
    if mutate:
        for r in rows:
            mutate(r)
    rows.extend(extra)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return path


def ingest(tmp_path, pack_dir, rv, write=False):
    out = tmp_path / "out"
    argv = ["--review-csv", str(rv), "--pack-dir", str(pack_dir), "--out-dir", str(out), "--now", "2026-10-14T12:00:00Z"]
    if write:
        argv.append("--write")
    return I.main(argv), out


def test_happy_path_dry_run_writes_nothing(tmp_path, pack, capsys):
    d, man = pack
    rv = export(tmp_path / "rv.csv", man)
    code, out = ingest(tmp_path, d, rv)
    assert code == 0 and not out.exists()
    assert "dry run" in capsys.readouterr().out


def test_write_creates_only_the_decisions_file_and_does_not_apply(tmp_path, pack):
    d, man = pack
    rv = export(tmp_path / "rv.csv", man)
    watched = [os.path.join(DATA, "bindings.proposed.v1.json"), os.path.join(HERE, "..", "held_lakes.json")]
    before = [hashlib.sha256(open(p, "rb").read()).hexdigest() for p in watched]
    code, out = ingest(tmp_path, d, rv, write=True)
    assert code == 0 and os.listdir(out) == ["coordinate_review_decisions.json"]
    res = json.load(open(out / "coordinate_review_decisions.json"))
    assert res["applied"] is False and "does not change" in res["note"] and res["schema"].startswith("lake-brain-coordinate-review-decisions/")
    assert res["counts"]["lakes"] == 4
    # accepted coordinates are exactly the manifest's proposed ones
    prop = {l["lakeId"]: (l["proposedLat"], l["proposedLon"]) for l in man["lakes"] if l["proposedLat"] is not None}
    assert {a["lakeId"]: (a["lat"], a["lon"]) for a in res["acceptedCoordinates"]} == prop
    assert all("Missing Lake" not in a["lakeId"] for a in res["acceptedCoordinates"])
    assert before == [hashlib.sha256(open(p, "rb").read()).hexdigest() for p in watched]       # no binding / hold file touched
    assert res["reviewCsvSha256"] == hashlib.sha256(open(rv, "rb").read()).hexdigest()
    assert res["decisions"][0]["notes"] == 'looks ok, "quoted", comma'


@pytest.mark.parametrize("blank", ["", "PENDING", "maybe"])
def test_missing_or_invalid_decision_is_refused(tmp_path, pack, blank, capsys):
    d, man = pack
    rv = export(tmp_path / "rv.csv", man, decide={"In Lake|AR": blank})
    code, out = ingest(tmp_path, d, rv, write=True)
    assert code == 2 and not out.exists()
    assert "In Lake|AR" in capsys.readouterr().err


def test_missing_row_is_refused(tmp_path, pack, capsys):
    d, man = pack
    rv = export(tmp_path / "rv.csv", man, drop={"Far Lake|AR"})
    code, out = ingest(tmp_path, d, rv, write=True)
    assert code == 2 and not out.exists() and "Far Lake|AR: no decision row" in capsys.readouterr().err


def test_unknown_and_duplicate_ids_are_refused(tmp_path, pack, capsys):
    d, man = pack
    extra = [dict(pack_id=man["packId"], lake_id="Not A Lake|ZZ", decision="KEEP_CURRENT", current_lat="1", current_lon="2", proposed_lat="", proposed_lon="",
                  computer_recommendation="FLAG", row_digest="x")]
    rv = export(tmp_path / "rv.csv", man, extra=extra)
    code, _ = ingest(tmp_path, d, rv, write=True)
    err = capsys.readouterr().err
    assert code == 2 and "Not A Lake|ZZ" in err and "not part of this pack" in err
    dup = [dict(pack_id=man["packId"], lake_id="In Lake|AR", decision="KEEP_CURRENT", current_lat=36.0, current_lon=-90.0, proposed_lat=36.0, proposed_lon=-90.0,
                computer_recommendation="PASS", row_digest="x")]
    rv2 = export(tmp_path / "rv2.csv", man, extra=dup)
    code, _ = ingest(tmp_path, d, rv2, write=True)
    assert code == 2 and "duplicate lake id 'In Lake|AR'" in capsys.readouterr().err


def test_tampered_proposed_coordinate_is_refused(tmp_path, pack, capsys):
    d, man = pack

    def m(r):
        if r["lake_id"] == "Near Lake|AR":
            r["proposed_lat"] = float(r["proposed_lat"]) + 0.01
    rv = export(tmp_path / "rv.csv", man, mutate=m)
    code, out = ingest(tmp_path, d, rv, write=True)
    assert code == 2 and not out.exists() and "proposed coordinate" in capsys.readouterr().err


def test_proposed_added_where_pack_has_none_is_refused(tmp_path, pack, capsys):
    d, man = pack

    def m(r):
        if r["lake_id"] == "Missing Lake|AR":
            r["proposed_lat"], r["proposed_lon"] = 36.0, -90.0
    rv = export(tmp_path / "rv.csv", man, mutate=m)
    assert ingest(tmp_path, d, rv)[0] == 2
    assert "proposed coordinate" in capsys.readouterr().err


@pytest.mark.parametrize("field,value,needle", [("current_lat", "40.5", "current coordinate"), ("computer_recommendation", "PASS", "computer_recommendation"),
                                                ("row_digest", "deadbeef", "row_digest"), ("pack_id", "LBC-other", "pack_id")])
def test_other_tampering_is_refused(tmp_path, pack, capsys, field, value, needle):
    d, man = pack

    def m(r):
        if r["lake_id"] == "Far Lake|AR":
            r[field] = value
    rv = export(tmp_path / "rv.csv", man, mutate=m)
    assert ingest(tmp_path, d, rv)[0] == 2
    assert needle in capsys.readouterr().err


def test_accept_proposed_without_a_proposal_is_refused(tmp_path, pack, capsys):
    d, man = pack
    rv = export(tmp_path / "rv.csv", man, decide={"Missing Lake|AR": "ACCEPT_PROPOSED"})
    assert ingest(tmp_path, d, rv)[0] == 2
    assert "no proposed coordinate" in capsys.readouterr().err


def test_override_of_flag_and_agreement_stats_are_recorded(tmp_path, pack):
    d, man = pack
    flag_with_prop = [l["lakeId"] for l in man["lakes"] if l["recommendation"] == "FLAG" and l["proposedLat"] is not None]
    assert flag_with_prop                                              # Far Lake|AR and (no) others
    rv = export(tmp_path / "rv.csv", man, decide={flag_with_prop[0]: "ACCEPT_PROPOSED"})
    code, out = ingest(tmp_path, d, rv, write=True)
    res = json.load(open(out / "coordinate_review_decisions.json"))
    row = [r for r in res["decisions"] if r["lakeId"] == flag_with_prop[0]][0]
    assert code == 0 and row["overridesFlag"] is True and row["acceptedLat"] is not None
    rv_stats = res["recommendationVsDecision"]
    assert rv_stats["passRows"] + rv_stats["flagRows"] == 4 and rv_stats["flagAccepted"] >= 1


def test_keep_current_and_needs_info_record_no_accepted_coordinate(tmp_path, pack):
    d, man = pack
    rv = export(tmp_path / "rv.csv", man, decide={"Near Lake|AR": "KEEP_CURRENT", "In Lake|AR": "NEEDS_INFO"})
    code, out = ingest(tmp_path, d, rv, write=True)
    res = json.load(open(out / "coordinate_review_decisions.json"))
    for r in res["decisions"]:
        if r["lakeId"] in ("Near Lake|AR", "In Lake|AR"):
            assert r["acceptedLat"] is None and r["acceptedLon"] is None
    assert res["counts"]["keepCurrent"] >= 1 and res["counts"]["needsInfo"] == 1


def test_wrong_file_and_missing_manifest(tmp_path, pack):
    d, man = pack
    empty = tmp_path / "empty.csv"
    empty.write_text("pack_id,lake_id,decision\n")
    assert ingest(tmp_path, d, empty)[0] == 2
    assert I.main(["--review-csv", str(empty), "--pack-dir", str(tmp_path / "nope")]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    assert ingest(tmp_path, d, bad)[0] == 2


def test_binding_rereview_flag_is_carried(tmp_path):
    rows = make_rows()
    rows[0]["bindings"] = [dict(provider="usgs", station="1", stationName=None, status="VERIFIED", capability="x", held=False, distFromPinM=1, stationLat=1, stationLon=1,
                                code="AT_RISK", changes=True, text="x", toWaterM=9000)]
    pid = B.pack_id_for(rows, "s")
    d = tmp_path / "p"
    man = B.write_pack(str(d), rows, dict(snapshot="s", registryGeneratedAt="x", registrySha256="ab" * 32, researchFlagged=4, registryOnly=0), pid, dict(byClass={}))
    rv = export(tmp_path / "rv.csv", man)
    code, out = ingest(tmp_path, d, rv, write=True)
    res = json.load(open(out / "coordinate_review_decisions.json"))
    assert code == 0 and res["bindingRereviewLakes"] == [rows[0]["lakeId"]]
    assert [r for r in res["decisions"] if r["lakeId"] == rows[0]["lakeId"]][0]["bindingTargetChanges"] is True
