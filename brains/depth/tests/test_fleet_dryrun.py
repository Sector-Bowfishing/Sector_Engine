"""Fleet-scale dry run: a synthetic observed level (reference pool - 2 ft) for EVERY shift-defensible lake builds a valid state, with no exception, plausible shares and a bounded size.
Guards the 'new Lake states are picked up by fingerprint change' path at the size Lake will eventually publish (Lake states are synthetic here; nothing is written)."""
import json
import os

from depth_brain.state import build_state, plan
from helpers import NOW, lake_state

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = json.load(open(os.path.join(HERE, "runtime", "knowledge", "candidates.json")))
OK = [c for c in MAN["candidates"] if c["shiftPossible"]]


def _state(c, drop=2.0):
    ls = lake_state(elev=c["reference"]["poolFt"] - drop, datum=None, cap=c["levelSource"]["capability"])
    return build_state(c, ls, NOW, manifest_version=MAN["manifestVersion"]), ls


def test_every_defensible_lake_builds_an_observed_state_with_the_right_shift():
    assert len(OK) >= 220
    zoned = 0
    for c in OK:
        if c["levelSource"].get("scale") == "DUKE_RELATIVE_100":
            continue                                                         # these publish on the 100-based scale: covered by tests/test_campaign_2026_10.py
        (s, meta), _ = _state(c)
        assert s["kind"] == "observed", (c["lakeId"], s["effectiveDepth"])
        assert abs(s["effectiveDepth"]["shiftFt"] + 2.0) < 0.06, c["lakeId"]
        assert len(json.dumps(s)) < 12000, c["lakeId"]
        ez = s.get("effectiveZones")
        if ez and ez.get("available"):
            zoned += 1
            for k, v in ez["shares"].items():
                assert 0.0 <= v["lo"] <= v["hi"] <= 1.0, (c["lakeId"], k, v)
            assert ("shareToleranceAbs" in ez) == (s["referenceZones"]["evidenceKind"] == "stage-area-rating"), c["lakeId"]
    assert zoned >= 80


def test_a_new_lake_state_for_a_non_pilot_lake_triggers_publish_and_an_unchanged_one_skips():
    c = next(x for x in OK if x["rollout"] != "PILOT_VERIFIED" and x["levelSource"].get("scale") != "DUKE_RELATIVE_100")
    (s, _), ls = _state(c)
    assert plan(None, c, ls, MAN["manifestVersion"])["action"] == "PUBLISH"
    assert plan(s, c, ls, MAN["manifestVersion"])["action"] == "SKIP"
    ls2 = dict(ls); ls2["currentElevationFt"] = ls["currentElevationFt"] - 0.1
    assert plan(s, c, ls2, MAN["manifestVersion"])["action"] == "PUBLISH"
    assert plan(s, c, ls, MAN["manifestVersion"] + "x")["action"] == "PUBLISH"
