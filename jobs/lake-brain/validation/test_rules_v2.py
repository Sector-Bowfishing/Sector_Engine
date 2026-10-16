"""Runs the shared conformance fixture contracts/conformance/lake_rules_v2.json against the Python mirror of the Lake Brain rules v2.
The Swift rules run the very same file (Tests/SectorEngineTests/LakeRulesV2Tests.swift). Run:  python -m pytest jobs/lake-brain/validation -q"""
import datetime as dt
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules_v2 as R  # noqa: E402

FIX = os.path.join(HERE, "..", "..", "..", "contracts", "conformance", "lake_rules_v2.json")
with open(FIX) as f:
    FX = json.load(f)


def series(spec):
    out = {}
    for y in range(spec["years"][0], spec["years"][1] + 1):
        d = dt.date(y, 1, 1)
        while d.year == y:
            n = d.timetuple().tm_yday
            if not (y in spec.get("gapYears", []) and n > 300):
                out[d] = 100 + ((y * 7 + n * 3) % 11) * 0.1 + (y - 2000) * 0.01
            d += dt.timedelta(days=1)
    pt = spec.get("partialYear")
    if pt:
        d, end = dt.date(pt["year"], 1, 1), dt.date.fromisoformat(pt["through"])
        while d <= end:
            n = d.timetuple().tm_yday
            out[d] = 100 + ((d.year * 7 + n * 3) % 11) * 0.1 + (d.year - 2000) * 0.01
            d += dt.timedelta(days=1)
    return out


@pytest.mark.parametrize("c", FX["tier"], ids=lambda c: f"tier-{c['basisYears']}")
def test_tier(c):
    assert R.tier(c["basisYears"]) == c["expect"]


@pytest.mark.parametrize("c", FX["historical"], ids=lambda c: f"hist-{c['tier']}-{c['current']}")
def test_historical(c):
    state, flags = R.historical_state(c["current"], c["p02"], c["p10"], c["p90"], c["p98"], c["tier"])
    assert state == c["expect"]["state"]
    assert flags == c["expect"]["flags"]


@pytest.mark.parametrize("i", range(len(FX["trend"])))
def test_trend(i):
    c = FX["trend"][i]
    label, thr, flags = R.trend(c["delta24h"], c["delta72h"], c["rateP95"], c["regulated"])
    e = c["expect"]
    assert label == e["state"], c
    assert (thr is None) == (e["rapidThresholdFt"] is None)
    if thr is not None:
        assert thr == pytest.approx(e["rapidThresholdFt"], abs=1e-12)
    assert flags == e["flags"], c


@pytest.mark.parametrize("c", FX["baseline"], ids=lambda c: c["name"])
def test_baseline(c):
    b = R.build_baseline(series(c["series"]), dt.date.fromisoformat(c["today"]), regulated=c["poolBasisIsFullPool"])
    e = c["expect"]
    assert len(b.complete_years) == e["completeYears"]
    assert len(b.basis_years) == e["basisYears"]
    assert (b.basis_years[0] if b.basis_years else None) == e["firstBasisYear"]
    assert b.status == e["status"] and b.tier == e["tier"]
    for doy, x in e["doy"].items():
        i = int(doy) - 1
        assert int(b.level_n[i]) == x["levelN"] and int(b.rate_n[i]) == x["rateN"]
        for p, want in zip((2, 10, 50, 90, 98), x["level"]):
            assert b.p(int(doy), p) == pytest.approx(want, abs=1e-9)
        got = b.rate_q[i, R.G[95]]
        if x["rateP95"] is not None:
            assert got == pytest.approx(x["rateP95"], abs=1e-9)


def test_p50_term_is_gone():
    # a very high seasonal median must not widen STABLE (the v1 behaviour)
    assert R.trend(0.15, 0.45, 0.5, True)[0] == "RISING"


def test_rounding_matches_swift():
    assert R.r2(0.125) == 0.13 and R.r2(-0.125) == -0.13 and R.round_half_away(2.0005, 3) == pytest.approx(2.001)
    assert R.doy365(dt.date(2024, 2, 29)) == 59 and R.doy365(dt.date(2024, 3, 1)) == 60 and R.doy365(dt.date(2024, 12, 31)) == 365
