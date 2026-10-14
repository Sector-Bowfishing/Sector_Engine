"""One-tap bowfisher observation (target < 15 s) and its bridge to the frozen field schema v2. No new science.

Quick record (observer fills 3 taps + optional extras; lake/time/place are automatic):
  {"schema": "sector-wind-quick-v1", "tripId", "lakeId", "bankId" | "zoneId" | ("lat","lon"), "observedAtUtc", "observer",
   "exposureObserved": PROTECTED | PARTIAL | EXPOSED | UNKNOWN, "surfaceObserved": CALM | MODERATE | ROUGH | UNKNOWN,
   "sawPrediction": bool, optional "windMph", "windFromDeg", "notes"}
`sawPrediction` is REQUIRED (blinding is a validity condition, never defaulted). Predictions are generated from the archive at the observation
time and kept separate; an observation never carries one.
Vocabulary: model DIRECT -> EXPOSED, CROSS -> PARTIAL, PROTECTED -> PROTECTED (ESTIMATED tier only calls EXPOSED / PROTECTED / UNKNOWN)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

SCHEMA = "sector-wind-quick-v1"
EXPOSURE = ("PROTECTED", "PARTIAL", "EXPOSED")
SURFACE = ("CALM", "MODERATE", "ROUGH")
_TO_V2_IMPACT = {"PROTECTED": "PROTECTED", "PARTIAL": "CROSS", "EXPOSED": "EXPOSED"}
_TO_V2_ROUGH = {"CALM": "calm", "MODERATE": "choppy", "ROUGH": "rough"}
_BOAT = {"CALM": "easy", "MODERATE": "noticeable", "ROUGH": "difficult"}   # derived, flagged in `derived`
_MODEL = {"DIRECT": "EXPOSED", "CROSS": "PARTIAL", "PROTECTED": "PROTECTED", "EXPOSED": "EXPOSED"}


def model_to_product(label: str) -> str:
    return _MODEL.get(label, "UNKNOWN")


def validate_quick(r: dict, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc); why = []
    if r.get("schema") != SCHEMA:
        why.append(f"schema != {SCHEMA}")
    for k in ("tripId", "lakeId", "observer"):
        if not r.get(k):
            why.append(f"{k} missing")
    if not (r.get("bankId") or r.get("zoneId") or (r.get("lat") is not None and r.get("lon") is not None)):
        why.append("bankId, zoneId or lat/lon required")
    try:
        t = datetime.strptime(r["observedAtUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if t > now + timedelta(minutes=5):
            why.append("observedAtUtc in the future")
    except Exception:
        why.append("observedAtUtc missing or not ISO-8601 UTC")
    if r.get("exposureObserved") not in EXPOSURE + ("UNKNOWN",):
        why.append("exposureObserved must be PROTECTED / PARTIAL / EXPOSED / UNKNOWN")
    if r.get("surfaceObserved") not in SURFACE + ("UNKNOWN",):
        why.append("surfaceObserved must be CALM / MODERATE / ROUGH / UNKNOWN")
    if not isinstance(r.get("sawPrediction"), bool):
        why.append("sawPrediction (blinding) must be true/false")
    if "prediction" in r or "predicted" in r:
        why.append("observation must not carry the model prediction")
    return why


def to_v2(r: dict, now: datetime | None = None) -> dict | None:
    """Frozen field schema v2 record, or None when surface/exposure is UNKNOWN (v2 has no unknown value; keep the quick record for exposure/surface
    agreement). Boat control and confidence are DERIVED (flagged), never invented as observer input."""
    if r.get("exposureObserved") not in EXPOSURE or r.get("surfaceObserved") not in SURFACE or validate_quick(r, now):
        return None
    out = {"schema": "sector-wind-field-v2", "id": f"{r['tripId']}|{r.get('bankId') or r.get('zoneId') or 'pt'}|{r['observedAtUtc']}", "lakeId": r["lakeId"],
           "observedAtUtc": r["observedAtUtc"], "observer": r["observer"], "tripId": r["tripId"],
           "roughnessObserved": _TO_V2_ROUGH[r["surfaceObserved"]], "bankImpactObserved": _TO_V2_IMPACT[r["exposureObserved"]],
           "boatability": _BOAT[r["surfaceObserved"]], "observerConfidence": 2, "observerSawPrediction": r["sawPrediction"],
           "derived": ["boatability", "observerConfidence"], "tags": []}
    for k in ("bankId", "zoneId"):
        if r.get(k):
            out[k] = r[k]
    out["wind"] = {"source": "visualEstimate", "speedMph": r.get("windMph"), "directionFromDeg": r.get("windFromDeg")}   # unmeasured: never a truth claim
    return out


def nearest_bank(lat: float, lon: float, banks: list[dict], max_m: float = 400.0):
    """Nearest bank anchor within max_m, else None (an observation farther than that is a zone report, not a bank call)."""
    best, bd = None, 1e18
    for b in banks:
        if "anchor" not in b:
            continue
        la, lo = b["anchor"]
        d = math.hypot((la - lat) * 110574.0, (lo - lon) * 111320.0 * math.cos(math.radians(lat)))
        if d < bd:
            best, bd = b, d
    return (best, round(bd, 1)) if best is not None and bd <= max_m else (None, round(bd, 1) if best is not None else None)


def exposure_agreement(pairs: list[tuple[str, str]]) -> dict:
    """pairs: (predicted, observed) in PROTECTED / PARTIAL / EXPOSED / UNKNOWN. UNKNOWN predictions are coverage loss, never right/wrong.
    dangerous = predicted PROTECTED but observed EXPOSED (a bowfisher would pick that bank and get hammered); lostOpportunity = the reverse."""
    obs = [(p, o) for p, o in pairs if o in EXPOSURE]
    called = [(p, o) for p, o in obs if p in EXPOSURE]
    idx = {c: i for i, c in enumerate(EXPOSURE)}; n = len(called)
    conf = {p: {o: 0 for o in EXPOSURE} for p in EXPOSURE}
    for p, o in called:
        conf[p][o] += 1
    dang = sum(1 for p, o in called if p == "PROTECTED" and o == "EXPOSED")
    lost = sum(1 for p, o in called if p == "EXPOSED" and o == "PROTECTED")
    prot_calls = sum(1 for p, _ in called if p == "PROTECTED")
    return {"observations": len(obs), "called": n, "unknownShare": round(1 - n / len(obs), 3) if obs else None,
            "exact": round(sum(p == o for p, o in called) / n, 3) if n else None,
            "withinOne": round(sum(abs(idx[p] - idx[o]) <= 1 for p, o in called) / n, 3) if n else None,
            "dangerousMiss": dang, "dangerousMissRate": round(dang / prot_calls, 3) if prot_calls else None, "protectedCalls": prot_calls,
            "lostOpportunity": lost, "confusion(pred->obs)": conf}
