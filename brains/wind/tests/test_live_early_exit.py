"""run_hourly skips any NBM cycle already archived complete for every lake (newest included) and still does
RTMA-RU / METAR / bundles. Network calls are stubbed."""
from datetime import datetime, timedelta, timezone

from sector_wind import live
from sector_wind.store import LocalStore

CFG = {"lakes": {"guntersville": {"bbox": [-86.5, 34.3, -85.6, 34.9]}, "wheeler": {"bbox": [-87.4, 34.5, -86.6, 34.9]}}}
NOW = datetime(2026, 10, 13, 4, 5, tzinfo=timezone.utc)
NEWEST = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)


def _stub(monkeypatch, calls):
    monkeypatch.setattr(live, "latest_nbm_cycle", lambda now=None, max_back_h=4: NEWEST)
    monkeypatch.setattr(live, "ingest_nbm_cycle", lambda store, cfg, c, leads, q: calls.append(("nbm", c)) or {l: "complete" for l in cfg["lakes"]})
    monkeypatch.setattr(live, "ingest_rtma", lambda store, cfg, t: calls.append(("rtma", t)) or {})
    monkeypatch.setattr(live, "ingest_metar_day", lambda store, cfg, d: calls.append(("metar", d)) or 0)
    monkeypatch.setattr(live, "write_latest_bundle", lambda store, lake, now: calls.append(("bundle", lake)) or {})


def test_newest_cycle_already_complete_is_not_reingested(tmp_path, monkeypatch):
    store = LocalStore(str(tmp_path))
    for lake in CFG["lakes"]:
        for back in range(0, live.NBM_CATCHUP_H + 1):
            c = NEWEST - timedelta(hours=back)
            store.put_json(live._nbm_key(lake, c), {"status": "complete"})
    calls = []
    _stub(monkeypatch, calls)
    s = live.run_hourly(store, CFG, NOW)
    assert not [c for c in calls if c[0] == "nbm"], "no NBM cycle should be re-read"
    assert s["newestNbmAlreadyArchived"] is True and s["nbmSkipped"][0] == "2026-10-13T03:00:00Z"
    assert any(c[0] == "rtma" for c in calls) and any(c[0] == "metar" for c in calls) and len([c for c in calls if c[0] == "bundle"]) == 2
    assert s["errors"] == []


def test_partial_or_missing_cycles_are_still_ingested(tmp_path, monkeypatch):
    store = LocalStore(str(tmp_path))
    # newest complete for both lakes; previous hour partial for one lake; two hours back missing entirely
    for lake in CFG["lakes"]:
        store.put_json(live._nbm_key(lake, NEWEST), {"status": "complete"})
    prev = NEWEST - timedelta(hours=1)
    store.put_json(live._nbm_key("guntersville", prev), {"status": "complete"})
    store.put_json(live._nbm_key("wheeler", prev), {"status": "partial"})
    calls = []
    _stub(monkeypatch, calls)
    s = live.run_hourly(store, CFG, NOW)
    nbm = sorted(c[1].hour for c in calls if c[0] == "nbm")
    assert 3 not in nbm and 2 in nbm and 1 in nbm, nbm
    assert s["newestNbmAlreadyArchived"] is True


def test_fresh_newest_cycle_is_ingested(tmp_path, monkeypatch):
    store = LocalStore(str(tmp_path))
    calls = []
    _stub(monkeypatch, calls)
    s = live.run_hourly(store, CFG, NOW)
    assert NEWEST in [c[1] for c in calls if c[0] == "nbm"]
    assert s["newestNbmAlreadyArchived"] is False
