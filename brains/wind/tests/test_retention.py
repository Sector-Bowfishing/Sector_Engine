"""Wind archive retention (sector_wind.retention): raw NBM/RTMA cutouts older than 30 days go, the newest of each series and everything else stays.
Dry run by default. Local tmp folders only."""
import os
from datetime import datetime, timezone

from sector_wind import retention as R

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
OLD, NEW = "2026100100", "2026111410"


def _tree(tmp_path):
    files = [f"nbm/guntersville/{OLD}.json.gz", f"nbm/guntersville/{NEW}.json.gz",
             "nbm/wilson/2026090100.json.gz",                                  # the only (newest) wilson cycle: kept however old
             "rtma/guntersville/20261001/0015.json.gz", "rtma/guntersville/20261114/1015.json.gz",
             f"nbm-points/{OLD}.json.gz", f"nbm-points/{NEW}.json.gz",
             "metar/20261001.json.gz", "fetch/national/MANIFEST.json", "brain/wind/last_publish.json", "latest/guntersville.json.gz",
             "grids/nbm/guntersville.json", "runs/20261001/001500.json", "ledger/ingest.jsonl"]
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 10)
    return files


def test_plan_prunes_only_old_raw_cutouts_and_keeps_each_series_newest(tmp_path):
    _tree(tmp_path)
    assert R.plan(R._keys(str(tmp_path)), NOW) == sorted([f"nbm/guntersville/{OLD}.json.gz", "rtma/guntersville/20261001/0015.json.gz",
                                                          f"nbm-points/{OLD}.json.gz"])


def test_dry_run_deletes_nothing(tmp_path, capsys):
    files = _tree(tmp_path)
    assert R.main(["--store", f"local:{tmp_path}", "--now", "2026-11-15T12:00:00Z"]) == 0
    assert all((tmp_path / f).exists() for f in files)
    assert '"files": 3' in capsys.readouterr().out


def test_apply_deletes_exactly_the_plan_and_empty_raw_folders(tmp_path):
    files = _tree(tmp_path)
    assert R.main(["--store", f"local:{tmp_path}", "--now", "2026-11-15T12:00:00Z", "--apply"]) == 0
    gone = {f"nbm/guntersville/{OLD}.json.gz", "rtma/guntersville/20261001/0015.json.gz", f"nbm-points/{OLD}.json.gz"}
    assert {f for f in files if not (tmp_path / f).exists()} == gone
    assert not (tmp_path / "rtma/guntersville/20261001").exists()
    assert (tmp_path / "metar/20261001.json.gz").exists() and (tmp_path / "runs/20261001/001500.json").exists()


def test_refusals(tmp_path):
    assert R.main(["--store", "gs://sector-wind-candidate/wind/v1"]) == 2
    assert R.main(["--store", f"local:{tmp_path / 'nope'}"]) == 2
    assert R.main(["--store", f"local:{tmp_path}", "--keep-days", "0"]) == 2
