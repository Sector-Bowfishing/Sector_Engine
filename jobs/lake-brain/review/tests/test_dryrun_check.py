"""The read-only dry-run gauge check (tools/ops/lake_binding_dryrun_check.py): a normal seasonal drawdown must not fail it (2026-11-21)."""
import datetime as dt
import importlib.util
import os
import types

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
_spec = importlib.util.spec_from_file_location("lake_binding_dryrun_check", os.path.join(ROOT, "tools", "ops", "lake_binding_dryrun_check.py"))
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

TODAY = dt.date(2026, 11, 21)
LAKE = "Summersville Lake|WV"


def _archive(tmp_path, rows):
    d = tmp_path / "history" / chk.lake_key(LAKE)
    d.mkdir(parents=True)
    with open(d / "daily.csv", "w", encoding="utf-8") as fh:
        fh.write("date,elevationFt\n")
        for day, ft in rows:
            fh.write(f"{day},{ft}\n")
    return str(tmp_path)


def _args(archive):
    return types.SimpleNamespace(archive=archive, history_ft=5.0, history_days=7, full_pool_ft=25.0, fallback_ft=0.5)


def _state(ft, **extra):
    return {"currentElevationFt": ft, "kind": "OBSERVED", "sourceCapability": "DIRECT_OPERATOR_POOL",
            "freshness": {"stale": False}, "provenance": {"sources": [{"sourceId": "cwms:LRH"}]}, **extra}


def test_a_steady_drawdown_passes_the_recent_history_check(tmp_path):
    # summer pool 1652 for a year, then a ~1 ft/day drawdown: the 365-day median would be ~1650, far from today's 1598
    rows = [((TODAY - dt.timedelta(days=i)).isoformat(), 1652.0) for i in range(60, 365)]
    rows += [((TODAY - dt.timedelta(days=i)).isoformat(), 1598.0 + i * 0.9) for i in range(1, 60)]
    row = chk.check_lake(LAKE, {"provider": "cwms", "live": [{"provider": "cwms"}]}, _state(1598.06), _args(_archive(tmp_path, rows)), TODAY, False)
    assert row["c"].startswith("PASS"), row["c"]


def test_a_real_jump_against_recent_days_still_fails(tmp_path):
    rows = [((TODAY - dt.timedelta(days=i)).isoformat(), 1652.0) for i in range(1, 40)]
    row = chk.check_lake(LAKE, {"provider": "cwms", "live": [{"provider": "cwms"}]}, _state(1598.0), _args(_archive(tmp_path, rows)), TODAY, False)
    assert row["c"].startswith("FAIL") and row["result"] == "FAIL"


def test_history_is_na_with_fewer_than_three_recent_values(tmp_path):
    rows = [((TODAY - dt.timedelta(days=i)).isoformat(), 1652.0) for i in (40, 50, 60, 1)]
    row = chk.check_lake(LAKE, {"provider": "cwms", "live": [{"provider": "cwms"}]}, _state(1598.0), _args(_archive(tmp_path, rows)), TODAY, False)
    assert row["c"] == "n/a"


def test_reference_prefers_the_guide_curve_then_the_operating_zone():
    assert chk.reference_distance(_state(1598.0, differenceFromGuideFt=-2.0, differenceFromNormalPoolFt=-54.0)) == (2.0, "vs guide curve")
    assert chk.reference_distance(_state(1598.0, operatingZone={"bottomFt": 1574.4, "topFt": 1600.0}, differenceFromNormalPoolFt=-54.0)) == (0.0, "outside operating zone")
    assert chk.reference_distance(_state(1598.0, differenceFromNormalPoolFt=-54.0)) == (54.0, "vs directory full pool")
    assert chk.reference_distance(_state(1598.0)) == (None, "")


def test_a_drawdown_inside_its_operating_zone_passes_the_reference_check(tmp_path):
    st = _state(1598.06, operatingZone={"bottomFt": 1574.4, "topFt": 1652.0}, differenceFromNormalPoolFt=-53.9)
    row = chk.check_lake(LAKE, {"provider": "cwms", "live": [{"provider": "cwms"}]}, st, _args(None), TODAY, False)
    assert row["d"].startswith("PASS") and row["result"] == "PASS"
