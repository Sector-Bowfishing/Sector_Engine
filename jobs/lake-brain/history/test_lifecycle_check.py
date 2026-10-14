"""pytest for the lifecycle model (lifecycle_check.py) and its consistency with the Swift baseline store constants."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lifecycle_check as lc

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LISTING = os.path.join(HERE, "fixtures", "lake_brain_bucket_listing_2026-10-13.json")


def swift_const(name):
    src = open(os.path.join(REPO, "Sources/SectorEngine/LakeBrain/LakeBaselineStore.swift")).read()
    return int(re.search(r"static let %s = (\d+)" % name, src).group(1))


def test_rule_file_shape():
    rules = lc.RULES
    assert len(rules) == 3 and all(r["action"] == {"type": "Delete"} for r in rules)
    prefixes = {p for r in rules for p in r["condition"]["matchesPrefix"]}
    assert prefixes == {"baselines-archive/", "baselines/", "history/"}
    # predictions/ presence/ history_backup/ have no rule at all
    assert not any(p.startswith(("predictions", "presence", "history_backup")) for p in prefixes)
    # every rule on a prefix that can hold a live current object either targets noncurrent versions only or a prefix with no current object
    for r in rules:
        c = r["condition"]
        if "baselines/" in c["matchesPrefix"] or "history/" in c["matchesPrefix"]:
            assert c.get("isLive") is False and "daysSinceNoncurrentTime" in c and "age" not in c


def test_refresh_is_well_inside_archive_retention():
    age = next(r["condition"]["age"] for r in lc.RULES if r["condition"].get("matchesPrefix") == ["baselines-archive/"])
    refresh, recompute = swift_const("refreshDays"), swift_const("recomputeDays")
    assert age >= 2 * refresh, "a current archive object must be refreshed twice per retention window"
    assert recompute < refresh


def test_fleet_sim_keeps_every_pointer_and_its_object_live():
    for lakes in (5, 196, 621):
        r = lc.fleet_sim(lakes)          # asserts inside, day by day
        assert r["pointers_live"] == lakes
        assert r["archive_live"] < lakes * 14, "about 13 archive objects stand per lake (90 d / 7 d), not growth without bound"
        assert r["history_noncurrent_left"] <= 3 * 31


def test_job_stopped_pointers_survive_and_archive_is_retired():
    r = lc.fleet_sim(196, stop_at=100)
    assert r["pointers_live"] == 196 and r["archive_live"] == 0 and r["presence_untouched"] == 196


def test_real_listing_only_noncurrent_history_is_ever_removed():
    r = lc.real_listing(LISTING)
    assert r["objects"] == 47
    assert r["live_objects_changed"] == []
    assert r["noncurrent_removed_prefixes"] == ["history"]
    assert len(r["noncurrent_removed"]) == 15
    assert r["predictions_presence_backup_untouched"] is True
