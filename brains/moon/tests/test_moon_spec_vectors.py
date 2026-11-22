"""The Brain's ephemeris IS the shared moon spec: it must pass contracts/moon/moon-v1.json exactly as the Engine's MoonSpecTests do."""
import datetime as dt
import json
import os

import pytest

from moon_brain import ephemeris as eph

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SPEC = json.load(open(os.path.join(REPO, "contracts", "moon", "moon-v1.json"), encoding="utf-8"))


def test_spec_identity():
    assert SPEC["specId"] == "sector-moon-v1" and len(SPEC["vectors"]) == 52


@pytest.mark.parametrize("v", SPEC["vectors"], ids=lambda v: v["at"])
def test_vector(v):
    t = float(v["epochSeconds"])
    assert dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") == v["at"]
    assert abs(eph.moon_illumination(t) - v["illumination"]) <= SPEC["tolerance"]["illumination"]
    assert abs(eph.moon_phase_fraction(t) - v["phaseFraction"]) <= SPEC["tolerance"]["phaseFraction"]
    assert eph.moon_phase_name(t) == v["phaseName"]


def test_topocentric_altitude_matches_the_engine_formula():
    """moonAltitudeDeg = geocentric altitude - parallax * cos(altitude) (Astronomy.swift); the Brain keeps that definition."""
    t = dt.datetime(2026, 11, 23, 4, 0, tzinfo=dt.timezone.utc).timestamp()
    alt, par = eph.moon_geocentric(t, 34.42, -86.26)
    assert eph.moon_altitude(t, 34.42, -86.26) == pytest.approx(alt - par * eph.cosd(alt))
    assert 0.88 < par < 1.03                      # lunar horizontal parallax is 54'..61'
