from sector_wind.brain import bowfisher_readiness as BR

BASE = {"providerSpeed": "VERIFIED", "providerDirection": "VERIFIED", "providerGust": "VERIFIED", "forecastReliability": "IN_PROGRESS", "fetch": "VALIDATED",
        "bankExposure": "CALIBRATION", "surfaceChop": "NOT_VALIDATED", "tonight": "CALIBRATION", "confidenceRefusal": "VERIFIED"}


def test_answers_follow_maturity_and_never_pose_as_canonical():
    r = BR.build(BASE, {"displayed": 3.3}, {})
    assert r["wouldUseToChooseSide"] == "PARTIALLY" and r["isCanonical"] is False and "Bank exposure" in r["because"]
    yes = {**BASE, "forecastReliability": "VALIDATED", "bankExposure": "VALIDATED", "surfaceChop": "WITHHELD"}
    assert BR.build(yes, {}, {})["wouldUseToChooseSide"] == "YES"
    assert BR.build({**yes, "surfaceChop": "NOT_VALIDATED"}, {}, {})["wouldUseToChooseSide"] == "PARTIALLY"          # surface must be validated or honestly withheld
    assert BR.build({**BASE, "providerSpeed": "NOT_VALIDATED"}, {}, {})["wouldUseToChooseSide"] == "NO"
