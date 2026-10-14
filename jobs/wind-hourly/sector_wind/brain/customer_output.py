"""PREPARED, NOT ACTIVATED: compact bowfisher-facing wind output. Nothing imports or publishes this; it is a reviewed contract + tested logic.

Modes (a deployment/approval decision, never automatic):
  FULL      exposure words + surface words (needs surface sufficiently validated)
  BANK_ONLY exposure words only (fallback if exposure is trustworthy but surface/chop is not): surface withheld
  ENVELOPE  BANK_ONLY, and anything outside the NORMAL OPERATING ENVELOPE becomes CAUTION instead of a bank call
Customer text never contains scoring jargon. Confidence is capped by claim maturity: while exposure is CALIBRATION the highest word is "medium"."""
from __future__ import annotations

from . import quick_observation as Q

MODES = ("FULL", "BANK_ONLY", "ENVELOPE")
ENVELOPE_MIN_MPH, ENVELOPE_MAX_MPH, ENVELOPE_MAX_FORECAST_AGE_H = 5.0, 12.0, 6.0     # PROPOSED constants (normal 5-12 mph guidance)
_WORDS = {"PROTECTED": "Protected bank tonight", "PARTIAL": "Moderately exposed", "EXPOSED": "Exposed to the wind", "UNKNOWN": "Not enough information for this bank"}
_SURF = {"CALM": "Calmer water likely", "MODERATE": "Some chop likely", "ROUGH": "Rougher water likely", "UNKNOWN": None}
_CHOP_TO_SURFACE = {1: "CALM", 2: "CALM", 3: "MODERATE", 4: "MODERATE", 5: "ROUGH"}
_RANK = {"PROTECTED": 0, "PARTIAL": 1, "EXPOSED": 2}


def _confidence(row: dict, tier: str, age_h: float, exposure_maturity: str) -> str:
    if row.get("bankImpact") == "UNKNOWN" or age_h is None or age_h > ENVELOPE_MAX_FORECAST_AGE_H:
        return "low"
    cap = "high" if exposure_maturity == "VALIDATED" else "medium"
    base = "high" if row.get("confidence") == "firm" and tier == "AUDITED" else "medium"
    return cap if (base == "high" and cap == "high") else "medium"


def bank_card(row: dict, tier: str, speed_mph: float, forecast_age_h: float, mode: str = "BANK_ONLY", exposure_maturity: str = "CALIBRATION") -> dict:
    assert mode in MODES
    outside = mode == "ENVELOPE" and not (ENVELOPE_MIN_MPH <= speed_mph <= ENVELOPE_MAX_MPH)
    if outside or forecast_age_h is None or forecast_age_h > ENVELOPE_MAX_FORECAST_AGE_H:
        why = ("Wind is lighter than Sector can tell banks apart" if speed_mph is not None and speed_mph < ENVELOPE_MIN_MPH
               else "Stronger wind than Sector can judge: use caution" if speed_mph is not None and speed_mph > ENVELOPE_MAX_MPH else "Forecast is out of date")
        return {"bankId": row.get("bankId"), "headline": "Use caution" if speed_mph and speed_mph > ENVELOPE_MAX_MPH else "Not enough information",
                "surface": None, "confidence": "low", "reason": why, "forecastAgeH": forecast_age_h, "mode": mode, "state": "CAUTION" if speed_mph and speed_mph > ENVELOPE_MAX_MPH else "UNKNOWN"}
    exp = Q.model_to_product(row.get("bankImpact", "UNKNOWN"), tier)
    surf = _SURF.get(_CHOP_TO_SURFACE.get(row.get("chopClass"))) if mode == "FULL" and row.get("confidence") == "firm" else None
    return {"bankId": row.get("bankId"), "headline": _WORDS[exp], "surface": surf, "confidence": _confidence(row, tier, forecast_age_h, exposure_maturity),
            "reason": f"Wind from {row.get('windFromDeg', '?')}° at about {round(speed_mph)} mph reaches this shoreline at an angle of {row.get('windAngleDeg', '?')}°" if exp != "UNKNOWN" else "Geometry or wind does not support a call",
            "forecastAgeH": forecast_age_h, "mode": mode, "state": exp}


def lake_summary(rows: list[dict], tier: str, speed_mph: float, wind_from_deg: float, forecast_age_h: float, mode: str = "BANK_ONLY", exposure_maturity: str = "CALIBRATION") -> dict:
    rows = [{**r, "windFromDeg": round(wind_from_deg)} for r in rows]
    cards = [bank_card(r, tier, speed_mph, forecast_age_h, mode, exposure_maturity) for r in rows]
    called = [c for c in cards if c["state"] in _RANK]
    if not called:
        return {"headline": cards[0]["headline"] if cards else "Not enough information", "bestBank": None, "confidence": "low", "mode": mode, "forecastAgeH": forecast_age_h,
                "reason": cards[0]["reason"] if cards else "No resolvable banks", "cards": cards}
    best = min(called, key=lambda c: _RANK[c["state"]])
    n_prot = sum(c["state"] == "PROTECTED" for c in called)
    return {"headline": f"{wind_dir_word(wind_from_deg)} wind tonight: " + (f"{n_prot} of {len(called)} banks are protected" if n_prot else "no clearly protected banks"),
            "bestBank": best["bankId"], "bestBankHeadline": best["headline"], "confidence": best["confidence"], "mode": mode, "forecastAgeH": forecast_age_h,
            "reason": best["reason"], "cards": cards}


def wind_dir_word(deg: float) -> str:
    return ("North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest")[int(((deg % 360) + 22.5) // 45) % 8]
