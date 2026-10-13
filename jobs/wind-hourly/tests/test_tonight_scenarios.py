"""Regression fixtures for the practical bowfishing scenarios (WIND_TONIGHT_SCENARIO_TESTS.md). Offline, deterministic."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sector_wind import bowfishing as BF
from sector_wind.brain import contract as C
from sector_wind.brain import exposure as EX
from sector_wind.brain import fleet as FL
from sector_wind.brain import tonight as TN
from tests.test_adoption import INIT, NOW, W0, hrs, tonight

UTC = timezone.utc


def chop(mph, fetch_m):
    return BF.chop_class(BF.cem(mph * 0.44704, fetch_m, 6 * 3600))


def test_A_8mph_from_SW_long_fetch_NE_bank_is_direct_and_exposed():
    ne_bank = {"anchor": [34.50, -86.20], "standoff": [34.4997, -86.2003]}                 # faces SW
    c = chop(8, 9000)
    lab = EX.label_bank(225, 8, EX.facing_deg(ne_bank), c)
    assert lab["label"] == "DIRECT" and c >= 3
    s = TN.simple(tonight([8.0] * 7, p90=[8.5] * 7), {"bankImpact": lab["label"], "chopClass": c, "geometryTier": "AUDITED"})
    assert s["wind"] == "SW about 8 mph" and s["bank"] == "DIRECT" and s["fetch"] in ("MODERATE", "HIGH") and s["tonight"] == "LIGHT"


def test_B_8mph_from_SW_cove_is_protected_or_cross_by_geometry():
    sw_cove = {"anchor": [34.40, -86.30], "standoff": [34.4003, -86.2997]}                  # faces NE: land upwind
    assert EX.label_bank(225, 8, EX.facing_deg(sw_cove), chop(8, 60))["label"] == "PROTECTED"
    tiny = EX.label_bank(225, 8, 135.0, chop(8, 60))                                          # faces SE, ~60 m of water: sheltered by size
    assert tiny["label"] == "PROTECTED" and tiny["reason"] == "shortFetch"
    side_cove = EX.label_bank(225, 8, 135.0, chop(8, 400))                                    # faces SE, 400 m run: ripple, wind skims it
    assert side_cove["label"] == "CROSS" and side_cove["highFetch"] is False
    skim = EX.label_bank(225, 8, 135.0, chop(8, 3000))                                        # faces SE with a long run along it
    assert skim["label"] == "CROSS"
    # ESTIMATED geometry may not call a borderline cove PROTECTED
    assert EX.label_bank_estimated(225, 8, 45.0, chop(8, 600), chop(8, 900))["label"] in ("PROTECTED", "CROSS")


def test_C_3mph_variable_does_not_overstate_direction_or_bank_impact():
    t = tonight([3.0] * 7, p90=[5.0] * 7, dirs=[10, 100, 190, 280, 10, 100, 190])
    assert t["direction"]["shown"] is False and t["confidence"]["label"] in ("LOW", "MEDIUM")
    assert EX.label_bank(225, 3.0, 225.0, 3)["label"] == "UNKNOWN"                           # below 5 mph: no bank labels at all
    assert EX.label_bank(225, 4.9, 225.0, 2)["label"] == "UNKNOWN"
    s = TN.simple(t, {"bankImpact": "DIRECT", "chopClass": 3})
    assert s["bank"] is None and s["fetch"] is None and s["wind"].startswith("light and variable") and "direction not shown below 5 mph" in s["caveats"]
    assert s["risk"] is None and s["trend"] in (None, "STEADY")


def test_D_light_P50_with_breezy_P90_is_light_plus_risk():
    t = tonight([6.0] * 7, p90=[7, 8, 9, 10.5, 11, 9, 8])
    s = TN.simple(t)
    assert s["tonight"] == "LIGHT" and s["risk"] == "COULD TURN BREEZY" and s["confidence"] == "MEDIUM"
    assert t["speed"]["ifItBlowsCategory"] == "breezy" and "NOT a maximum" in t["speed"]["note"]


def test_D2_no_flag_is_not_low_risk():
    s = TN.simple(tonight([6.0] * 7, p90=[7.0] * 7))
    assert s["risk"] is None                                                                  # no statement, never 'LOW RISK'
    assert "low risk" not in json.dumps(s).lower() and "calm" not in json.dumps(s).lower()


def test_E_easing_forecast_is_easing_not_calm_by_a_time():
    t = tonight([10, 9, 8, 6, 5, 4, 3], p90=[11, 10, 9, 7, 6, 5, 4])
    s = TN.simple(t)
    assert s["trend"] == "EASING" and s["tonight"] == "LIGHT"
    j = json.dumps(s).lower()
    for banned in ("calm by", "lay down", "lays down", "will be calm", "dies down"):
        assert banned not in j
    assert t["withheld"]["layDown"]


def test_F_rising_forecast_makes_no_rising_claim_but_keeps_the_risk_flag():
    t = tonight([4, 5, 6, 8, 10, 11, 12], p90=[6, 7, 8, 10, 12, 13, 14])
    s = TN.simple(t)
    assert s["trend"] is None and s["risk"] == "COULD TURN BREEZY"


def test_G_strong_forecast_is_labelled_windy_without_gust_or_wave_claims():
    t = tonight([16.0] * 7, p90=[18.0] * 7)
    s = TN.simple(t)
    assert s["tonight"] == "WINDY" and "gust" not in json.dumps(s).lower() and "wave" not in json.dumps(s).lower() and "inch" not in json.dumps(s).lower()


def test_H_stale_forecast_is_low_confidence_and_says_so():
    s = TN.simple(tonight([8.0] * 7, init=INIT - timedelta(hours=8)))
    assert s["confidence"] == "LOW" and "forecast is stale" in s["caveats"]


def test_I_unavailable_forecast_gives_no_claims_at_all():
    t = TN.build_tonight([], None, None, None, NOW, "America/Chicago")
    s = TN.simple(t)
    assert s["wind"] is None and s["tonight"] is None and s["risk"] is None and s["trend"] is None and s["bank"] is None and s["confidence"] == "LOW"


def test_J_blocked_or_pointonly_lakes_never_get_bank_words():
    m = FL.load_manifest()
    for lid in ("Aleknagik|AK", "Andrews Lake|DE", "Lake Michigan|WI"):
        assert not FL.exposure_allowed(m["lakes"][lid])


def test_K_ESTIMATED_bank_gets_the_estimate_caveat():
    s = TN.simple(tonight([8.0] * 7, p90=[8.5] * 7), {"bankImpact": "CROSS", "chopClass": 3, "geometryTier": "ESTIMATED"})
    assert "bank exposure is an estimate" in s["caveats"]
    assert s["bank"] == "EXPOSED"                                       # ESTIMATED geometry does not separate DIRECT from CROSS
    assert TN.simple(tonight([8.0] * 7, p90=[8.5] * 7), {"bankImpact": "DIRECT", "chopClass": 3, "geometryTier": "AUDITED"})["bank"] == "DIRECT"
    assert EX.public_label("PROTECTED", "ESTIMATED") == "PROTECTED" and EX.public_label("UNKNOWN", "AUDITED") is None
