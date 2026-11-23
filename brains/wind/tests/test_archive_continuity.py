"""Wind archive continuity check (tools/ops/wind_archive_continuity.py, decision D5). Local only: a tmp folder stands in for the bucket, its listing is
built the way `gcloud storage objects list --format=json` reports it. The check must never change the local archive."""
import base64
import gzip
import hashlib
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "ops"))
import wind_archive_continuity as C                                                # noqa: E402


def _gz(obj) -> bytes:
    return gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), mtime=0)


FILES = {
    "fetch/national/MANIFEST.json": json.dumps({"lakes": [
        {"name": "Kentucky Lake", "state": "KY", "slug": "kentucky-ky", "status": "PASS", "tableSha256": "t1"},
        {"name": "Lake Barkley", "state": "KY", "slug": "barkley-ky", "status": "FLAGGED", "tableSha256": "t2"},
        {"name": "Nowhere", "state": "TX", "slug": "nowhere-tx", "status": "FAIL", "tableSha256": "t3"}]}).encode(),
    "fetch/national/kentucky-ky.windfetch.json.gz": _gz({"tableSha256": "t1"}),
    "fetch/national/barkley-ky.windfetch.json.gz": _gz({"tableSha256": "t2"}),
    "fetch/dev/guntersville.windfetch.json.gz": _gz({"tableSha256": "d1"}),
    "grids/rtma/guntersville.json": b'{"cells":[]}',
    "brain/wind/last_publish.json": json.dumps({"at": "2026-10-23T05:00:00Z", "profileShas": {"Kentucky Lake|KY": "t1"}}).encode(),
    "brain/wind/profile_cache/t1.json": b"{}",
    "rtma/guntersville/20261023/0500.json.gz": _gz({}),
    "metar/20261023.json.gz": _gz({"observations": []}),
}


def _tree(root, files):
    for k, data in files.items():
        p = root / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def _listing(files, camel=False):
    rows = []
    for k, data in files.items():
        md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
        rows.append({"name": f"wind/v1/{k}", "md5Hash" if camel else "md5_hash": md5, "size": len(data)} if not camel else
                    {"storage_url": f"gs://sector-wind-candidate/wind/v1/{k}", "md5Hash": md5, "size": len(data)})
    return rows


def _digest(root):
    h = hashlib.sha256()
    for dp, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            h.update(open(os.path.join(dp, f), "rb").read())
    return h.hexdigest()


@pytest.fixture
def seeded(tmp_path):
    _tree(tmp_path / "local", FILES)
    return tmp_path / "local", C.parse_listing(_listing(FILES))


def test_a_faithful_seed_is_continuous_and_nothing_is_written(seeded):
    local, remote = seeded
    before = _digest(local)
    out = C.compare(str(local), remote)
    assert out["verdict"] == "CONTINUOUS", out
    assert out["required"]["remoteObjects"] == 5 and out["profileDigests"] == {**out["profileDigests"], "status": "PASS", "checked": 2}
    assert out["watchdogScope"]["status"] == "PASS" and out["watchdogScope"]["d3Lakes"] >= 2
    assert out["series"]["remote"]["rtma"]["newest"] == "202610230500"
    assert _digest(local) == before


def test_a_missing_table_needs_a_seed(seeded):
    local, remote = seeded
    os.remove(local / "fetch/national/barkley-ky.windfetch.json.gz")
    out = C.compare(str(local), remote)
    assert out["verdict"] == "SEED_NEEDED" and out["required"]["missingSample"] == ["fetch/national/barkley-ky.windfetch.json.gz"]


def test_a_changed_grid_is_divergence(seeded):
    local, remote = seeded
    (local / "grids/rtma/guntersville.json").write_bytes(b'{"cells":[1]}')
    out = C.compare(str(local), remote)
    assert out["verdict"] == "DIVERGED" and out["required"]["differSample"] == ["grids/rtma/guntersville.json"]


def test_a_table_whose_digest_disagrees_with_the_manifest_is_flagged(tmp_path):
    files = dict(FILES, **{"fetch/national/barkley-ky.windfetch.json.gz": _gz({"tableSha256": "OTHER"})})
    _tree(tmp_path / "local", files)
    out = C.compare(str(tmp_path / "local"), C.parse_listing(_listing(files)))
    assert out["verdict"] == "DIVERGED" and out["profileDigests"]["mismatched"] == ["Lake Barkley|KY"]


def test_bookkeeping_differences_are_information_only(seeded):
    local, remote = seeded
    (local / "brain/wind/last_publish.json").write_text(json.dumps({"at": "2026-11-24T01:00:00Z", "profileShas": {}}))
    out = C.compare(str(local), remote, {"at": "2026-10-23T05:00:00Z"})
    assert out["verdict"] == "CONTINUOUS"
    assert out["bookkeeping"]["sameBytes"] is False and out["bookkeeping"]["localAt"] > out["bookkeeping"]["remoteAt"]


def test_listing_formats_and_cli_exit_codes(tmp_path, seeded):
    local, _ = seeded
    assert set(C.parse_listing(_listing(FILES, camel=True))) == set(FILES)
    (tmp_path / "l.json").write_text(json.dumps(_listing(FILES)))
    assert C.main(["--local", str(local), "--remote-listing", str(tmp_path / "l.json")]) == 0
    os.remove(local / "fetch/dev/guntersville.windfetch.json.gz")
    assert C.main(["--local", str(local), "--remote-listing", str(tmp_path / "l.json")]) == 3
    (tmp_path / "empty.json").write_text("[]")
    assert C.main(["--local", str(local), "--remote-listing", str(tmp_path / "empty.json")]) == 2
    assert C.main(["--local", "gs://sector-wind-candidate/wind/v1", "--remote-listing", str(tmp_path / "l.json")]) == 2
    shutil.rmtree(local)
