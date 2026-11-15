"""merge_bakeoff.py: joining the MacBook and Mac mini bake-off folders loses nothing (Sector_Ops #51)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import merge_bakeoff as M  # noqa: E402


def w(root, rel, data: bytes):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data)


def r(root, rel):
    with open(os.path.join(root, rel), "rb") as fh:
        return fh.read()


def test_the_hand_over_day_file_is_joined_line_by_line_src_first(tmp_path):
    src, dst = str(tmp_path / "s"), str(tmp_path / "d")
    w(src, "normalized/20261107.jsonl", b'{"t":1}\n{"t":2}\n')
    w(dst, "normalized/20261107.jsonl", b'{"t":2}\n{"t":3}\n')       # the overlapping cycle appears in both
    out = M.merge_tree(src, dst, "macbook")
    assert r(dst, "normalized/20261107.jsonl") == b'{"t":1}\n{"t":2}\n{"t":3}\n' and out["linesAdded"] == 1


def test_once_written_files_are_copied_create_only_and_differing_ones_kept_aside(tmp_path):
    src, dst = str(tmp_path / "s"), str(tmp_path / "d")
    w(src, "raw/nbm/a.grib2.gz", b"A"); w(src, "raw/nbm/b.grib2.gz", b"B-mac")
    w(dst, "raw/nbm/b.grib2.gz", b"B-mini")
    out = M.merge_tree(src, dst, "macbook")
    assert r(dst, "raw/nbm/a.grib2.gz") == b"A" and r(dst, "raw/nbm/b.grib2.gz") == b"B-mini"
    assert r(dst, "merged/macbook/raw/nbm/b.grib2.gz") == b"B-mac" and out["keptAside"] == 1


def test_it_is_idempotent_and_a_dry_run_writes_nothing(tmp_path):
    src, dst = str(tmp_path / "s"), str(tmp_path / "d")
    w(src, "rrfs_ledger.jsonl", b'{"a":1}\n'); w(src, "raw/x", b"x")
    os.makedirs(dst)
    assert M.merge_tree(src, dst, "macbook", dry_run=True)["copied"] == 1 and not os.listdir(dst)
    M.merge_tree(src, dst, "macbook")
    out = M.merge_tree(src, dst, "macbook")
    assert out["copied"] == 0 and out["lineFilesMerged"] == 0 and out["same"] == 2


def test_repeats_within_a_side_are_kept_and_logs_are_copied_whole(tmp_path):
    src, dst = str(tmp_path / "s"), str(tmp_path / "d")
    w(src, "normalized/20261107.jsonl", b'{"t":1}\n{"t":1}\n')
    w(dst, "normalized/20261107.jsonl", b'{"t":2}\n')
    w(src, "loop.log", b"ERROR x\nERROR x\n")
    M.merge_tree(src, dst, "macbook")
    assert r(dst, "normalized/20261107.jsonl") == b'{"t":1}\n{"t":1}\n{"t":2}\n'
    assert r(dst, "loop.log") == b"ERROR x\nERROR x\n"
