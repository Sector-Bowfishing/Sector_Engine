"""End-to-end through the real publisher pieces (guard -> Engine score -> plan_writes): a stale generated artifact in the image
cannot move Wind, any other Brain, or the Engine score, whichever Brain's change triggered the publish."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_brains import UPSTREAM, plan_writes  # noqa: E402
from sector_brain_platform import guard_scores, score_engine  # noqa: E402

NOW = dt.datetime(2026, 10, 14, 6, 0, tzinfo=dt.timezone.utc)


def blk(v, at, basis="COMPUTED", version="v1"):
    return {"value": v, "scale": 10, "basis": basis, "scoreVersion": version, "scoreUpdatedAt": at, "scoreBlockers": [],
            "scoreBreakdown": {"d": {"value": v, "weight": 100, "status": "SCORED", "evidence": "x"}}, "completenessPct": 100}


PUBLISHED = {"lake-brain": blk(5.0, "2026-10-14T04:00:00Z"), "water-temp": blk(3.0, "2026-10-11T00:00:00Z", "FROZEN"),
             "water-clarity": blk(8.0, "2026-10-12T00:00:00Z", "FROZEN"), "wind": blk(3.3, "2026-10-13T21:13:49Z", version="wind-v1"),
             "biological-state": blk(4.6, "2026-10-14T03:00:00Z"), "sector-intelligence": blk(5.5, "2026-10-14T02:00:00Z")}
ENGINE_FACTS = {"intelligenceRegistry": {}, "validation": {}, "healthBrains": {}, "healthJobs": {}, "fleetReadiness": {}}


def publish(candidates):
    eff, held = guard_scores(candidates, PUBLISHED)
    engine = score_engine(ENGINE_FACTS, eff, NOW)
    old_engine = score_engine(ENGINE_FACTS, PUBLISHED, NOW)
    updates, changed = plan_writes(eff, {b: {} for b in UPSTREAM}, NOW, engine, old_engine, PUBLISHED)
    return updates, held, engine, old_engine


def test_biological_update_with_stale_wind_artifact_does_not_regress_wind():
    cand = dict(PUBLISHED, **{"biological-state": blk(5.0, "2026-10-14T06:00:00Z"), "wind": blk(3.1, "2026-10-12T06:16:16Z", version="wind-v1")})
    updates, held, _, _ = publish(cand)
    assert "scores/wind" not in updates and [h["brainId"] for h in held] == ["wind"]
    assert updates["scores/biological-state"]["value"] == 5.0


def test_lake_update_with_stale_wind_artifact_does_not_regress_wind_or_engine():
    cand = dict(PUBLISHED, **{"lake-brain": blk(5.2, "2026-10-14T06:00:00Z"), "wind": blk(3.1, "2026-10-12T06:16:16Z", version="wind-v1")})
    updates, held, engine, old_engine = publish(cand)
    assert "scores/wind" not in updates and set(u for u in updates if u.startswith("scores/") and u != "scores/engine") == {"scores/lake-brain"}
    # the Engine score moved only by Lake's own contribution, not by a Wind regression
    assert engine["engineScore"] >= old_engine["engineScore"]


def test_stale_wind_artifact_alone_is_a_complete_noop():
    cand = dict(PUBLISHED, wind=blk(3.1, "2026-10-12T06:16:16Z", version="wind-v1"))
    updates, held, engine, old_engine = publish(cand)
    assert updates == {} and held and engine["engineScore"] == old_engine["engineScore"]


def test_a_depth_or_unrelated_brain_cannot_rewrite_lake():
    # an image carrying an old Lake block (e.g. a Depth branch cut before Lake improved) loses to the published one
    cand = dict(PUBLISHED, **{"lake-brain": blk(2.0, "2026-10-10T00:00:00Z")})
    updates, held, _, _ = publish(cand)
    assert "scores/lake-brain" not in updates and held[0]["brainId"] == "lake-brain"
