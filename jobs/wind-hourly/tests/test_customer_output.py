from sector_wind.brain import customer_output as CO

P = {"bankId": "b1", "bankImpact": "PROTECTED", "chopClass": 1, "confidence": "firm", "windAngleDeg": 120}
D = {"bankId": "b2", "bankImpact": "DIRECT", "chopClass": 4, "confidence": "firm", "windAngleDeg": 10}
C = {"bankId": "b3", "bankImpact": "CROSS", "chopClass": 3, "confidence": "boundary", "windAngleDeg": 70}


def test_words_and_confidence_cap_while_exposure_is_calibration():
    s = CO.lake_summary([P, D, C], "AUDITED", 9, 315, 2.0)
    assert s["headline"].startswith("Northwest wind tonight: 1 of 3") and s["bestBank"] == "b1" and s["confidence"] == "medium"      # never "high" before validation
    cards = {c["bankId"]: c for c in s["cards"]}
    assert cards["b1"]["headline"] == "Protected bank tonight" and cards["b2"]["headline"] == "Exposed to the wind" and cards["b3"]["headline"] == "Moderately exposed"
    assert all(c["surface"] is None for c in s["cards"])                                                                            # BANK_ONLY withholds surface
    assert CO.lake_summary([P], "AUDITED", 9, 315, 2.0, exposure_maturity="VALIDATED")["confidence"] == "high"


def test_full_mode_adds_surface_words_only_for_firm_banks():
    s = CO.lake_summary([P, D, C], "AUDITED", 9, 315, 2.0, mode="FULL")
    cards = {c["bankId"]: c for c in s["cards"]}
    assert cards["b1"]["surface"] == "Calmer water likely" and cards["b2"]["surface"] == "Some chop likely" and cards["b3"]["surface"] is None


def test_estimated_tier_never_says_partial():
    assert CO.bank_card(C, "ESTIMATED", 9, 2.0)["headline"] == "Exposed to the wind"


def test_envelope_turns_strong_wind_and_stale_forecast_into_caution_not_a_bank_call():
    strong = CO.bank_card(P, "AUDITED", 16, 2.0, mode="ENVELOPE")
    assert strong["state"] == "CAUTION" and strong["surface"] is None and "Stronger wind" in strong["reason"]
    assert CO.bank_card(P, "AUDITED", 3, 2.0, mode="ENVELOPE")["state"] == "UNKNOWN"
    assert CO.bank_card(P, "AUDITED", 9, 9.0)["state"] == "UNKNOWN" and CO.bank_card(P, "AUDITED", 9, 2.0, mode="ENVELOPE")["state"] == "PROTECTED"


def test_unknown_banks_never_read_as_protected_and_text_has_no_scoring_jargon():
    c = CO.bank_card({"bankId": "u", "bankImpact": "UNKNOWN", "confidence": "firm"}, "AUDITED", 9, 2.0)
    assert c["state"] == "UNKNOWN" and c["confidence"] == "low" and "Protected" not in c["headline"]
    blob = str(CO.lake_summary([P, D], "AUDITED", 9, 315, 2.0)).lower()
    for jargon in ("rubric", "calibration", "score", "fingerprint", "cem", "fetch"):
        assert jargon not in blob, jargon
