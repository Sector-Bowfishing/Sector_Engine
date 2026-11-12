"""merge_archive.py: the MacBook → Mac mini TVA archive merge loses nothing and never overwrites an observed hour (Sector_Ops #51)."""
import json
import os

import merge_archive as M


def day(dam="GVDA1", date="2026-11-06", observed=None, revisions=None, predicted=None):
    return {"schemaVersion": 1, "dam": dam, "localDate": date, "source": "x", "observed": observed or {},
            "revisions": revisions or [], "predicted": predicted or {}}


def write(root, rel, obj):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump(obj, fh) if not isinstance(obj, bytes) else None
    if isinstance(obj, bytes):
        with open(p, "wb") as fh:
            fh.write(obj)


def read(root, rel):
    with open(os.path.join(root, rel)) as fh:
        return json.load(fh)


D = "water-temp/tva/GVDA1/2026-11-06.json"


def test_missing_hours_are_added_and_existing_hours_are_never_overwritten(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(observed={"2026-11-06T01": {"raw": "a", "parsed": 1, "firstSeenAt": "t1"},
                                "2026-11-06T02": {"raw": "b2", "parsed": 2, "firstSeenAt": "t1"}}))
    write(dst, D, day(observed={"2026-11-06T02": {"raw": "b", "parsed": 2, "firstSeenAt": "t9"},
                                "2026-11-06T03": {"raw": "c", "parsed": 3, "firstSeenAt": "t9"}}))
    out = M.merge_tree(src, dst, "macbook")
    d = read(dst, D)
    assert sorted(d["observed"]) == ["2026-11-06T01", "2026-11-06T02", "2026-11-06T03"]
    assert d["observed"]["2026-11-06T02"]["raw"] == "b"                     # dst kept
    assert d["revisions"] == [{"hour": "2026-11-06T02", "raw": "b2", "parsed": 2, "seenAt": "t1", "mergedFrom": "macbook"}]
    assert out["observedAdded"] == 1 and out["revisionsAdded"] == 1


def test_a_second_run_changes_nothing(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(observed={"2026-11-06T01": {"raw": "a"}}, revisions=[{"hour": "2026-11-06T01", "raw": "z"}],
                      predicted={"2026-11-06T05Z": {"rows": 1}}))
    write(dst, D, day())
    M.merge_tree(src, dst, "macbook")
    first = read(dst, D)
    out = M.merge_tree(src, dst, "macbook")
    assert read(dst, D) == first and out["daysMerged"] == 0 and out["observedAdded"] == 0


def test_days_and_raw_files_only_in_src_are_copied_and_raw_is_create_only(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, "water-temp/tva/GVDA1/2026-11-03.json", day(date="2026-11-03", observed={"2026-11-03T00": {"raw": "q"}}))
    write(src, "water-temp/tva/raw/GVDA1/observed/2026-11-03T05Z.json", b"src-bytes")
    write(src, "water-temp/tva/raw/GVDA1/observed/2026-11-06T05Z.json", b"src-other")
    write(dst, "water-temp/tva/raw/GVDA1/observed/2026-11-06T05Z.json", b"dst-bytes")
    out = M.merge_tree(src, dst, "macbook")
    assert read(dst, "water-temp/tva/GVDA1/2026-11-03.json")["observed"] == {"2026-11-03T00": {"raw": "q"}}
    with open(os.path.join(dst, "water-temp/tva/raw/GVDA1/observed/2026-11-03T05Z.json"), "rb") as fh:
        assert fh.read() == b"src-bytes"
    with open(os.path.join(dst, "water-temp/tva/raw/GVDA1/observed/2026-11-06T05Z.json"), "rb") as fh:
        assert fh.read() == b"dst-bytes"                                    # never overwritten
    assert out["rawCopied"] == 1 and out["rawDiffering"] == 1 and out["daysNew"] == 1
    kept = os.path.join(dst, "water-temp/tva-merged/macbook/raw/GVDA1/observed/2026-11-06T05Z.json")   # the differing src copy is kept aside
    with open(kept, "rb") as fh:
        assert fh.read() == b"src-other"


def test_dry_run_writes_nothing(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(observed={"2026-11-06T01": {"raw": "a"}}))
    os.makedirs(dst)
    out = M.merge_tree(src, dst, "macbook", dry_run=True)
    assert out["daysNew"] == 1 and not os.path.exists(os.path.join(dst, D))


def test_mismatched_day_files_are_refused(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        M.merge_day(day(dam="GVDA1"), day(dam="WHLA1"), "x")


def test_a_differing_predicted_fetch_is_kept_aside_not_dropped(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(predicted={"2026-11-06T20Z": {"rows": "mac"}, "2026-11-06T21Z": {"rows": "only-mac"}}))
    write(dst, D, day(predicted={"2026-11-06T20Z": {"rows": "mini"}}))
    out = M.merge_tree(src, dst, "macbook")
    assert read(dst, D)["predicted"] == {"2026-11-06T20Z": {"rows": "mini"}, "2026-11-06T21Z": {"rows": "only-mac"}}
    aside = read(dst, "water-temp/tva-merged/macbook/GVDA1/2026-11-06.json")
    assert aside["predicted"] == {"2026-11-06T20Z": {"rows": "mac"}} and out["predictedDiffering"] == 1


def test_a_revision_equal_to_the_observed_value_is_not_added_and_the_earliest_first_seen_is_kept(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(observed={"2026-11-06T02": {"raw": "b", "firstSeenAt": "2026-11-06T08:20:00Z"}},
                      revisions=[{"hour": "2026-11-06T02", "raw": "b", "seenAt": "2026-11-06T09:20:00Z"}]))
    write(dst, D, day(observed={"2026-11-06T02": {"raw": "b", "firstSeenAt": "2026-11-06T10:20:00Z"}}))
    out = M.merge_tree(src, dst, "macbook")
    d = read(dst, D)
    assert d["revisions"] == [] and d["observed"]["2026-11-06T02"]["firstSeenAt"] == "2026-11-06T08:20:00Z"
    assert out["firstSeenEarlier"] == 1


def test_revisions_stay_in_time_order(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(revisions=[{"hour": "2026-11-06T01", "raw": "x", "seenAt": "2026-11-06T05:00:00Z"}]))
    write(dst, D, day(observed={"2026-11-06T01": {"raw": "a"}}, revisions=[{"hour": "2026-11-06T01", "raw": "y", "seenAt": "2026-11-06T09:00:00Z"}]))
    M.merge_tree(src, dst, "macbook")
    assert [r["raw"] for r in read(dst, D)["revisions"]] == ["x", "y"]


def test_a_corrupt_file_is_reported_and_the_rest_still_merges(tmp_path):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    write(src, D, day(observed={"2026-11-06T01": {"raw": "a"}}))
    write(src, "water-temp/tva/GVDA1/2026-11-07.json", day(date="2026-11-07", observed={"2026-11-07T01": {"raw": "z"}}))
    os.makedirs(os.path.join(dst, "water-temp/tva/GVDA1"))
    with open(os.path.join(dst, D), "w") as fh:
        fh.write('{"truncated": ')
    out = M.merge_tree(src, dst, "macbook")
    assert out["unreadable"] == [{"side": "dst", "file": D, "error": "JSONDecodeError"}]
    assert read(dst, "water-temp/tva/GVDA1/2026-11-07.json")["observed"] == {"2026-11-07T01": {"raw": "z"}}
    with open(os.path.join(dst, D)) as fh:
        assert fh.read() == '{"truncated": '                               # left for a person, never overwritten


def test_main_refuses_during_the_archive_jobs_minutes_and_exits_1_on_unreadable(tmp_path, monkeypatch):
    src, dst = str(tmp_path / "src"), str(tmp_path / "dst")
    os.makedirs(src); os.makedirs(dst)
    class Fixed(M.dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return M.dt.datetime(2026, 11, 7, 12, 20, tzinfo=M.dt.timezone.utc)
    monkeypatch.setattr(M.dt, "datetime", Fixed)
    assert M.main(["--src", src, "--dst", dst]) == 3
    assert M.main(["--src", src, "--dst", dst, "--dry-run"]) == 0             # a dry run is always allowed
    write(src, D, day())
    os.makedirs(os.path.join(dst, "water-temp/tva/GVDA1"), exist_ok=True)
    with open(os.path.join(dst, D), "w") as fh:
        fh.write("not json")
    assert M.main(["--src", src, "--dst", dst, "--any-minute"]) == 1
