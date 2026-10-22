import json
import random

import pytest
from depth_research import field_validation as F


def rows(n=80, lakes=6, noise=0.2, bias=0.0, seed=1):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        obs = rnd.uniform(-0.5, 6)
        out.append({"lake": f"L{i % lakes}", "flat": f"f{i}", "obsAt": "2026-11-01", "observedDepthFt": obs,
                    "predictedDepthFt": obs + rnd.gauss(bias, noise), "sigmaFt": 0.3})
    return out


def test_prereg_is_frozen_and_hash_pinned(tmp_path):
    assert F.verify_prereg()
    p = tmp_path / "p.json"
    d = json.load(open(F.PREREG)); d["criteria"]["classAccuracy"]["min"] = 0.5
    p.write_text(json.dumps(d))
    assert not F.verify_prereg(str(p))


def test_thresholds_are_the_ones_in_the_brief():
    c = json.load(open(F.PREREG))["criteria"]
    assert c["shiftVsObservedMaeFt"]["max"] == 0.5 and c["classAccuracy"]["min"] == 0.80
    assert c["forbiddenErrors"]["max_count"] == 0 and (c["withinOneSigma"]["min"], c["withinOneSigma"]["max"]) == (0.53, 0.83)


def test_class_bins():
    assert [F.depth_class(x) for x in (-1, 0, 0.5, 1, 2.9, 3, 5, 5.1)] == ["DRY", "DRY", "TOO_SHALLOW", "SHOOTABLE", "SHOOTABLE", "GOOD", "GOOD", "DEEP"]


def test_good_model_passes_and_bad_model_fails():
    good = F.analyze(rows(noise=0.2))
    assert good["maeFt"] < 0.5 and good["n"] == 80 and good["lakes"] == 6
    bad = F.analyze(rows(noise=0.2, bias=1.5))
    assert bad["criteria"]["shiftVsObservedMaeFt"] is False and bad["passed"] is False and bad["status"] == "FAILED"


def test_dry_called_good_is_a_hard_fail_even_with_good_averages():
    r = rows(noise=0.05)
    r[0].update(observedDepthFt=-0.2, predictedDepthFt=3.5)
    out = F.analyze(r)
    assert out["forbiddenDryAsShootableOrGood"] >= 1 and out["criteria"]["forbiddenErrors"] is False and out["passed"] is False


def test_insufficient_data_is_not_a_pass():
    out = F.analyze(rows(n=10, lakes=2))
    assert out["passed"] is False and out["status"] in ("INSUFFICIENT_DATA", "FAILED")
    assert F.analyze([])["status"] == "INSUFFICIENT_DATA"


def test_exclusions_are_reported_not_silent():
    r = rows(n=70)
    r[0]["excluded"] = "true"
    out = F.analyze(r)
    assert out["excluded"] == 1 and out["n"] == 69
