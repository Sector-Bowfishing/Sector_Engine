"""Field validation record v2: simple enough to collect, strict enough to score later.

Extends (does not replace) the Stage 3 protocol in field_qa.py / fieldops.py / field.py (sector-wind-field-v1: four development
lakes, surface class 1-5, texture T1-T4, sealed keys). v2 adds what the bowfishing vocabulary needs and drops the four-lake
restriction so any lake with an AUDITED or ESTIMATED tier can be validated:

  * a bank-impact judgement (DIRECT / CROSS / PROTECTED) made by the observer from the water,
  * practical boatability and roughness,
  * wind truth with its device and sensor height (never assumed),
  * paired-bank sessions (same lake, same time, same wind, different predicted exposure).

Blinding rule: an observation NEVER carries the model prediction. Predictions are generated from the archive at the observation
time and stored separately (sealed key), keyed by `id`, so the observer cannot be anchored by the model."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

SCHEMA = "sector-wind-field-v2"
BANK_IMPACT = ("EXPOSED", "DIRECT", "CROSS", "PROTECTED", "UNSURE")   # EXPOSED = coarse call (all testers); DIRECT/CROSS = richer optional call for AUDITED validation
ROUGHNESS = ("calm", "light", "choppy", "rough")      # ordinal 0..3. Mapping to the frozen chop classes: calm = 1 (<1 in), light = 2 (ripple), choppy = 3-4 (light/moderate chop), rough = 5
BOATABILITY = ("easy", "noticeable", "difficult")      # boat control: easy / noticeable effort / difficult
WIND_SOURCES = ("handheld", "fixedAnemometer", "boatMounted", "visualEstimate", "nearbyStation")
MEASURED_SOURCES = ("handheld", "fixedAnemometer", "boatMounted")
PAIR_WINDOW_MIN = 60
PAIR_MAX_KM_NOTE = "pairs should be on the same water body within a short run (<= 10 km) so the wind is shared"


def _t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def validate_observation(r: dict, now: datetime | None = None) -> list[str]:
    """Every reason the record cannot be used. Empty list = usable. Never repairs."""
    now = now or datetime.now(timezone.utc)
    why = []
    if r.get("schema") != SCHEMA:
        why.append(f"schema != {SCHEMA}")
    for k in ("id", "lakeId", "observer"):
        if not r.get(k):
            why.append(f"{k} missing")
    if not (r.get("bankId") or r.get("zoneId")):
        why.append("bankId or zoneId required")
    try:
        t = _t(r["observedAtUtc"])
        if t > now + timedelta(minutes=5):
            why.append("observedAtUtc in the future")
    except Exception:
        why.append("observedAtUtc missing or not ISO-8601 UTC (YYYY-MM-DDTHH:MM:SSZ)")
    if r.get("roughnessObserved") not in ROUGHNESS:
        why.append("roughnessObserved missing/invalid")
    if r.get("bankImpactObserved") not in BANK_IMPACT:
        why.append("bankImpactObserved missing/invalid")
    if r.get("boatability") not in BOATABILITY:
        why.append("boatability missing/invalid")
    if r.get("observerConfidence") not in (1, 2, 3):
        why.append("observerConfidence must be 1 (guess) / 2 / 3 (sure)")
    if not isinstance(r.get("observerSawPrediction"), bool):
        why.append("observerSawPrediction (blinding) must be true/false")
    if "prediction" in r or "predicted" in r:
        why.append("observation must not carry the model prediction (sealed separately)")
    w = r.get("wind")
    if not isinstance(w, dict):
        why.append("wind block missing")
    else:
        src = w.get("source")
        if src not in WIND_SOURCES:
            why.append("wind.source invalid")
        if src in MEASURED_SOURCES:
            if w.get("speedMph") is None:
                why.append("measured wind without speedMph")
            if not w.get("deviceId"):
                why.append("measured wind without deviceId")
            if not isinstance(w.get("heightM"), (int, float)) or w["heightM"] <= 0:
                why.append("measured wind without sensor height (never assumed)")
            if not isinstance(w.get("averagingSec"), (int, float)) or w["averagingSec"] <= 0:
                why.append("measured wind without averaging period")
        d = w.get("directionFromDeg")
        if d is not None and not (0 <= d < 360):
            why.append("directionFromDeg outside 0-359 (meteorological FROM bearing)")
        if w.get("gustMph") is not None and src not in MEASURED_SOURCES:
            why.append("gust only accepted from a measuring device")
    role, pid = r.get("pairRole"), r.get("pairId")
    if pid and role not in ("A", "B"):
        why.append("pairId set but pairRole is not A/B")
    if role in ("A", "B") and not pid:
        why.append("pairRole without pairId")
    return why


def validate_pair(a: dict, b: dict) -> list[str]:
    """A pair is usable for concordance only if both records are usable and share lake, pair id, time window and wind source family."""
    why = []
    for r in (a, b):
        bad = validate_observation(r)
        if bad:
            why.append(f"{r.get('id')}: {bad[0]}")
    if why:
        return why
    if a["lakeId"] != b["lakeId"]:
        why.append("different lakes")
    if a.get("pairId") != b.get("pairId") or {a.get("pairRole"), b.get("pairRole")} != {"A", "B"}:
        why.append("pair ids/roles do not match")
    if abs((_t(a["observedAtUtc"]) - _t(b["observedAtUtc"])).total_seconds()) > PAIR_WINDOW_MIN * 60:
        why.append(f"observations more than {PAIR_WINDOW_MIN} min apart")
    if (a["bankId"] if a.get("bankId") else a.get("zoneId")) == (b["bankId"] if b.get("bankId") else b.get("zoneId")):
        why.append("same bank twice")
    return why


def roughness_index(r: str) -> int:
    return ROUGHNESS.index(r)


def _rank(label: str) -> int:
    return {"PROTECTED": 0, "EXPOSED": 1, "CROSS": 1, "DIRECT": 2}[label]


def pair_concordance(pairs: list[dict]) -> dict:
    """pairs: {'predictedLabelA','predictedLabelB','predictedHm0A','predictedHm0B','obsA','obsB'} where obs are roughness indices 0-3 (`roughness_index`).
    Counts only pairs where the model made a call (labels differ, or Hm0 differs by >= 20%). 'Concordance' = share where the bank
    the model called more exposed was observed rougher (ties count 0.5). Volume reported; no pass line here (scoring is the
    canonical scorer's job)."""
    elig, ties = [], 0
    for p in pairs:
        la, lb = p["predictedLabelA"], p["predictedLabelB"]
        if "UNKNOWN" in (la, lb) or "UNSURE" in (la, lb):
            ties += 1; continue
        if _rank(la) != _rank(lb):
            a_more = _rank(la) > _rank(lb)
        else:
            hi, lo = max(p["predictedHm0A"], p["predictedHm0B"]), min(p["predictedHm0A"], p["predictedHm0B"])
            if hi <= 0 or (hi - lo) / hi < 0.20:
                ties += 1; continue
            a_more = p["predictedHm0A"] > p["predictedHm0B"]
        oa, ob = (p["obsA"], p["obsB"]) if a_more else (p["obsB"], p["obsA"])
        elig.append(1.0 if oa > ob else 0.5 if oa == ob else 0.0)
    return {"n": len(elig), "predictionTies": ties, "concordance": None if not elig else round(sum(elig) / len(elig), 3)}
