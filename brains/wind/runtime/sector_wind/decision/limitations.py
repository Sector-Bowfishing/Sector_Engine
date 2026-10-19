"""Known limitations attached to every decision, with the evidence behind each number (no number is typed here).

Numbers are read from the frozen validation evidence that the Brain already publishes (`brain/validation_evidence.json`:
NBM v5.0 vs METAR, CAL+H1 2026-05-06 -> 10-06; buoy surface physics 2020-2023). H2 (2026-10-07 -> 12-31) is sealed until
2027-01-01 and is never read. The probabilistic strong-wind flag (NBM qmd exceedance) is EXPLORATORY: it is reported as a
limitation-context fact only and never used to raise a recommendation's confidence.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

EVIDENCE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "brain", "validation_evidence.json")
STRONG_WIND_MPH = 15.0
WINDY_MPH = 10.0
LONG_LEAD_H = 12


@lru_cache(maxsize=1)
def evidence() -> dict:
    return json.load(open(EVIDENCE))


def _m():
    return evidence()["metrics"]


def catalogue() -> dict:
    """Every limitation id -> (severity, text, evidenceRef). Severity: INFO < CAUTION < WARNING."""
    m, sp = _m(), evidence()["surfacePhysics"]
    window = f"{evidence()['window']['start']} -> {evidence()['window']['end']}"
    return {
        "STRONG_WIND_UNDERFORECAST": ("WARNING",
            f"The deterministic NBM forecast has not detected strong night wind: probability of detecting observed >= 15 mph events "
            f"was {m['event15mphPod']:.2f} in evaluation ({window}, 8 stations). A calm or moderate forecast does NOT rule out a "
            f"strong-wind night; gusts run about {abs(m['gustConditionalBiasMph']):.1f} mph low.",
            "validation_evidence.json metrics.event15mphPod / gustConditionalBiasMph"),
        "WINDY_HOUR_ERROR": ("CAUTION",
            f"On hours with observed wind >= 10 mph the forecast speed error averages {m['windyHourSpeedMaeMph']:.1f} mph, so which "
            f"surface class a bank reaches is uncertain exactly when it matters most.",
            "validation_evidence.json metrics.windyHourSpeedMaeMph"),
        "DIRECTION_ERROR": ("INFO",
            f"Forecast direction is within 22.5 deg of observed {m['directionWithin22_5Pct']:.0f}% of the time; banks near the edge "
            f"of shelter can swap with a small direction error.",
            "validation_evidence.json metrics.directionWithin22_5Pct"),
        "SURFACE_NOT_FIELD_VALIDATED": ("CAUTION",
            f"No bank has been checked on the water. Surface physics is checked only against lake buoys: exact class "
            f"{sp['chopClassExactPct']:.0f}%, within one class {sp['chopClassWithin1Pct']:.0f}%, modeled waves biased "
            f"{sp['hm0BiasM'] / 0.0254:.1f} in low.",
            "validation_evidence.json surfacePhysics"),
        "LAND_ONLY_WIND_VALIDATION": ("INFO",
            "Wind accuracy is measured at airport/AWOS stations on land; the over-water wind can be stronger. No over-water "
            "reference station exists yet.", "Wind Certification cap 7.0 (overwater.measuredStationComparisons = 0)"),
        "NO_WAVE_MEMORY": ("CAUTION",
            "The surface model has no wave memory: after a blow, modeled chop drops immediately while real chop lingers.",
            "M4 promotion rule failed (BWIS v1 C3 = 0)"),
        "WIND_ONLY_SCOPE": ("INFO",
            "Wind Brain describes wind exposure and the modeled surface only. It does not assess water clarity, fish presence, "
            "access, legality, private property or safety.", "BRAIN_OPERATING_CONTRACT.md §1"),
        "FORECAST_INPUT": ("INFO", "The wind used is a forecast, not an observation.", "state kind = forecast"),
        "LONG_LEAD": ("CAUTION", f"The wind used is more than {LONG_LEAD_H} h ahead; forecast error grows with lead time.", "NBM lead"),
        "SYNTHETIC_INPUT": ("WARNING", "The wind used is SYNTHETIC (a scenario), not a forecast or an observation. Nothing here describes "
                                       "real lake conditions.", "input kind = synthetic"),
        "GEOMETRY_SUBSET": ("INFO", "Only a subset of this lake's banks was evaluated.", "geometry subset"),
        "PROBABILISTIC_FLAG_EXPLORATORY": ("INFO",
            "A probabilistic strong-wind flag (NBM exceedance probabilities) is under study; its recalibration test waits for the "
            "sealed H2 holdout (2027-01-01). It is not used here.", "Score Acceleration prob_recal pre-registration"),
    }


def applicable(kind: str, speed_mph: float | None, gust_mph: float | None, lead_h: float | None, subset: bool) -> list[dict]:
    """Limitations for one decision, most severe first. STRONG_WIND_UNDERFORECAST is ALWAYS present: the failure mode is a
    missed event, so a light forecast cannot exempt a decision from it."""
    ids = ["STRONG_WIND_UNDERFORECAST", "SURFACE_NOT_FIELD_VALIDATED", "NO_WAVE_MEMORY", "LAND_ONLY_WIND_VALIDATION",
           "DIRECTION_ERROR", "WIND_ONLY_SCOPE", "PROBABILISTIC_FLAG_EXPLORATORY"]
    if speed_mph is not None and (speed_mph >= WINDY_MPH or (gust_mph or 0) >= STRONG_WIND_MPH):
        ids.insert(1, "WINDY_HOUR_ERROR")
    if kind == "forecast":
        ids.append("FORECAST_INPUT")
        if lead_h is not None and lead_h > LONG_LEAD_H:
            ids.append("LONG_LEAD")
    if kind == "synthetic":
        ids.insert(0, "SYNTHETIC_INPUT")
    if subset:
        ids.append("GEOMETRY_SUBSET")
    cat = catalogue(); rank = {"WARNING": 0, "CAUTION": 1, "INFO": 2}
    out = [{"id": i, "severity": cat[i][0], "text": cat[i][1], "evidenceRef": cat[i][2]} for i in ids]
    return sorted(out, key=lambda x: rank[x["severity"]])
