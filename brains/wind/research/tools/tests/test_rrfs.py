"""RRFS / REFS prospective archive: the operational bucket and key layout (recorded listing, 2026-10-31) and the flagged backfill. Offline only."""
import json
import os
from datetime import datetime, timezone

import pytest

from sector_wind.grib import read_idx
import sector_wind_research.rrfs as R

FX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "rrfs_ops_listing_2026103012.json"), encoding="utf-8"))
INIT = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


def _listing(ops=True):
    keys = FX["rrfsKeys"] + FX["rrfsensKeys"]
    def fake(prefix, bucket=R.OPS):
        return [k for k in keys if k.startswith(prefix)] if (bucket == R.OPS) == ops else []
    return fake


def test_discover_finds_operational_deterministic_and_member_wind_files(monkeypatch):
    monkeypatch.setattr(R, "_s3_keys", _listing())
    f = R.discover(INIT)
    assert set(f["det"]) == {1, 3} and set(f["ens"]) == {1, 2} and all(set(v) == {1, 3} for v in f["ens"].values())
    assert f["det"][3] == f"{R.OPS}/rrfs.20261030/12/rrfs.t12z.2dfld.3km.f003.conus.grib2"          # 2dfld: where 10 m U/V and GUST live
    assert f["ens"][2][3] == f"{R.OPS}/rrfsens.20261030/12/m002/rrfs.t12z.m002.2dfldnomads.3km.f003.conus.grib2"
    assert f["where"] == [f"{R.OPS}/rrfs.20261030/12/", f"{R.OPS}/rrfsens.20261030/12/"]
    urls = list(f["det"].values()) + [u for v in f["ens"].values() for u in v.values()]
    assert not any(x in u for u in urls for x in ("prslev", "subh", "awipsubset", ".ak.", ".hi.", ".pr.", ".na."))


def test_the_old_patterns_find_nothing_usable_in_the_operational_layout():
    """The bug this fixes: the old member pattern matches no operational key, and the old deterministic pattern matches only prslev, which has no 10 m wind."""
    bases = [k.rsplit("/", 1)[-1] for k in FX["rrfsKeys"] + FX["rrfsensKeys"]]
    assert not [b for b in bases if R.ENS_PDS.search(b)]
    assert all(".prslev." in b for b in bases if R.DET_PDS.search(b))


def test_the_pre_operational_bucket_is_only_a_fallback(monkeypatch):
    monkeypatch.setattr(R, "_s3_keys", lambda prefix, bucket=R.OPS: [])
    monkeypatch.setattr(R.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert R.discover(INIT) is None
    seen = []
    monkeypatch.setattr(R, "_s3_keys", lambda prefix, bucket=R.OPS: seen.append(bucket) or [])
    R.discover(INIT)
    assert seen[:2] == [R.OPS, R.OPS] and R.S3 in seen


def test_member_messages_are_found_by_their_ens_tail(monkeypatch):
    lines = "\n".join(FX["memberIdxExcerpt"]).split("\n")
    monkeypatch.setattr("sector_wind.grib.fetch", lambda url, *a, **k: "\n".join(dict.fromkeys(lines)).encode())
    ent = read_idx("https://example.invalid/member.grib2")
    for var, level in (("UGRD", "10 m above ground"), ("VGRD", "10 m above ground"), ("GUST", "surface")):
        e = R._entry(ent, var, level, "3 hour fcst")
        assert e is not None and e.tail == "ENS=+1", (var, e)
    assert R._entry(ent, "UGRD", "10 m above ground", "6 hour fcst") is None


def _fake_cycle(monkeypatch, tmp_path, fail_at=None):
    monkeypatch.setattr(R, "ROOT", str(tmp_path))
    def disc(init):
        if init.day == 13 and init.hour == 0:
            return None                                                                       # a cycle NOAA never published
        return {"det": {L: f"det{L}" for L in R.LEADS}, "ens": {m: {L: f"m{m}f{L}" for L in R.LEADS} for m in (1, 2, 3)}, "where": ["x"]}
    def samp(url, lead):
        if fail_at and fail_at in url:
            raise RuntimeError("decode failed")
        pts = {p: {"speedMS": 7.0, "dirFromDeg": 180.0, "u": 0.0, "v": 7.0, "gustMS": 9.0, "cell": 1} for p in R.POINTS}
        return pts, {"u": b"u", "v": b"v", "gust": b"g"}, {"gridKey": "k", "uvRelativeToGrid": False}
    monkeypatch.setattr(R, "discover", disc)
    monkeypatch.setattr(R, "sample_file", samp)


def test_backfill_flags_every_row_keeps_no_grib_and_is_idempotent(monkeypatch, tmp_path):
    _fake_cycle(monkeypatch, tmp_path)
    start, end = datetime(2026, 8, 12, 3, tzinfo=timezone.utc), datetime(2026, 8, 13, 6, tzinfo=timezone.utc)
    res = R.backfill(start, end, now=datetime(2026, 10, 31, tzinfo=timezone.utc), run_id="t1")
    assert [r["init"] for r in res] == ["2026-08-12T06:00:00Z", "2026-08-12T12:00:00Z", "2026-08-12T18:00:00Z", "2026-08-13T00:00:00Z", "2026-08-13T06:00:00Z"]
    assert [r["status"] for r in res].count("not published") == 1 and all(r["backfill"] for r in res)
    rows = [json.loads(l) for l in open(tmp_path / "normalized" / "rrfs-backfill-t1.jsonl")]
    assert rows and all(r["backfill"] is True and r["asIssued"] is False and r["backfillRunId"] == "t1" for r in rows)
    assert {r["provider"] for r in rows} == {"rrfs", "refs"} and len(rows) == 4 * len(R.LEADS) * len(R.POINTS) * 2
    assert not (tmp_path / "raw").exists()                                                    # point samples only
    again = R.backfill(start, end, now=datetime(2026, 10, 31, tzinfo=timezone.utc), run_id="t3")
    assert [r["init"] for r in again] == ["2026-08-13T00:00:00Z"]                             # only the unpublished cycle is re-checked


def test_a_failing_cycle_is_recorded_as_an_error_and_retried_not_archived(monkeypatch, tmp_path):
    _fake_cycle(monkeypatch, tmp_path, fail_at="m2f6")
    res = R.backfill(datetime(2026, 8, 12, tzinfo=timezone.utc), datetime(2026, 8, 12, tzinfo=timezone.utc), now=datetime(2026, 10, 31, tzinfo=timezone.utc), run_id="e")
    assert res[0]["status"] == "error" and "decode failed" in res[0]["error"] and res[0]["samples"] == 0
    assert "2026-08-12T00:00:00Z" not in R._ledger_done()


def test_backfill_never_reaches_beyond_now(monkeypatch, tmp_path):
    _fake_cycle(monkeypatch, tmp_path)
    res = R.backfill(datetime(2026, 10, 30, 18, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc), now=datetime(2026, 10, 31, 1, tzinfo=timezone.utc), run_id="n")
    assert [r["init"] for r in res] == ["2026-10-30T18:00:00Z", "2026-10-31T00:00:00Z"]
