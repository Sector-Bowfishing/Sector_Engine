"""Dual-wind logging record (PREPARED, NOT WIRED): the customer provider's wind next to the candidate provider's wind, for later comparison.

Design rules
  * No extra provider calls. The customer value is recorded where Engine already has it (the /conditions request path) and, for pilot lakes only,
    by one scheduled low-volume lookup. Fleet-wide hourly Open-Meteo calls would add ~15,000 calls/day and are NOT part of this design.
  * The candidate value comes from the Brain's own archive (NBM point + P90) - no new network access.
  * A disagreement is PROVIDER_DISAGREEMENT, never "accuracy". Truth is attached later by `attach_truth`, which refuses to attach any truth to a
    record from the sealed H2 window before 2027-01-01, so the log cannot be used to peek at H2 skill.
  * Unknown stays null. A provider that is down is recorded as such, never as zero or calm."""
from __future__ import annotations

from datetime import datetime, timezone

from .brain import contract as C
from .brain import tonight as TN

SCHEMA = "sector-wind-dual-log-v1"
H2_START = datetime(2026, 10, 7, tzinfo=timezone.utc)
TRUTH_MAX_AGE_MIN = 30


def _dir_diff(a, b):
    if a is None or b is None:
        return None
    d = abs(a - b) % 360
    return round(min(d, 360 - d))


def build_record(lake_id: str, logged_at: datetime, valid_at: datetime, customer: dict | None, candidate: dict | None, brain: dict | None = None) -> dict:
    """customer: {'speedMph','directionDeg','gustMph'?,'fetchedAt','host'?: 'primary'|'fallback','requestedModel'?} or None when unavailable.
    candidate: {'speedMph','directionDeg','p90Mph'?,'forecastInit','initAgeHours'?} or None. brain: {'published': bool, 'generatedAt', 'stale': bool}."""
    c, k = customer or {}, candidate or {}
    p90 = k.get("p90Mph")
    flag = TN.breezy_flag(p90)
    both_dir = c.get("directionDeg") is not None and k.get("directionDeg") is not None and (c.get("speedMph") or 0) >= 5 and (k.get("speedMph") or 0) >= 5
    init = k.get("forecastInit")
    init_age = None
    if init:
        t = datetime.strptime(init, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        init_age = round((logged_at - t).total_seconds() / 3600, 2)
    horizon = round((valid_at - logged_at).total_seconds() / 3600, 1)
    return {
        "schema": SCHEMA, "lakeId": lake_id, "loggedAt": C.iso(logged_at), "validAt": C.iso(valid_at), "forecastHorizonHours": horizon,
        "forecastInit": init, "forecastInitAgeHours": init_age,
        "customerProvider": {"id": "open-meteo-best-match", "available": customer is not None, "directionDeg": c.get("directionDeg"), "speedMph": c.get("speedMph"),
                             "gustMph": c.get("gustMph"), "category": TN.category(c.get("speedMph")), "fetchedAt": c.get("fetchedAt"), "host": c.get("host"),
                             "usedFallbackHost": c.get("host") == "fallback"},
        "candidateProvider": {"id": "nbm-v5.0", "available": candidate is not None, "directionDeg": k.get("directionDeg"), "speedMph": k.get("speedMph"),
                              "p90Mph": p90, "riskFlag": flag, "category": TN.category(k.get("speedMph")), "stale": None if init_age is None else init_age > C.STALE_FORECAST_CYCLE_H},
        "brainPublication": {"published": bool((brain or {}).get("published")), "generatedAt": (brain or {}).get("generatedAt"), "stale": (brain or {}).get("stale")},
        "comparison": {"kind": "PROVIDER_DISAGREEMENT", "accuracyClaim": False,
                       "speedDiffMph": None if c.get("speedMph") is None or k.get("speedMph") is None else round(k["speedMph"] - c["speedMph"], 1),
                       "directionDiffDeg": _dir_diff(c.get("directionDeg"), k.get("directionDeg")) if both_dir else None,
                       "categoryAgree": None if not c or not k else TN.category(c.get("speedMph")) == TN.category(k.get("speedMph")),
                       "directionComparedOnlyWhenBothAtLeast5mph": True},
        "truth": None,
    }


def attach_truth(rec: dict, obs: dict | None, now: datetime | None = None) -> dict:
    """Returns a NEW record with truth attached. obs: {'station','observedAt','speedMph','directionDeg','distanceKm','overWater': bool}.
    Refuses H2-window records before the seal opens; refuses observations more than 30 min from validAt."""
    now = now or datetime.now(timezone.utc)
    valid = datetime.strptime(rec["validAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if valid >= H2_START and now < C.H2_SEALED_UNTIL:
        raise PermissionError(f"record validAt {rec['validAt']} is inside the H2 window; truth cannot be attached before {C.iso(C.H2_SEALED_UNTIL)}")
    out = {**rec, "comparison": dict(rec["comparison"])}
    if not obs:
        return out
    t = datetime.strptime(obs["observedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if abs((t - valid).total_seconds()) / 60 > TRUTH_MAX_AGE_MIN:
        raise ValueError("observation is more than 30 minutes from the valid time")
    out["truth"] = {"station": obs["station"], "observedAt": obs["observedAt"], "speedMph": obs.get("speedMph"), "directionDeg": obs.get("directionDeg"),
                    "distanceKm": obs.get("distanceKm"), "overWater": bool(obs.get("overWater")), "landReferenced": not obs.get("overWater")}
    out["comparison"]["kind"] = "ACCURACY_ELIGIBLE"
    out["comparison"]["accuracyClaim"] = False          # a record is eligible; an accuracy claim needs the aggregate under a pre-registration
    for who, key in (("customer", "customerProvider"), ("candidate", "candidateProvider")):
        sp = rec[key]["speedMph"]
        out["comparison"][f"{who}SpeedErrMph"] = None if sp is None or obs.get("speedMph") is None else round(sp - obs["speedMph"], 1)
    return out


def growth_model(lakes: int = 621, pilot_lakes: int = 10, record_bytes: int | None = None) -> dict:
    """Storage/call growth if wired as designed (hourly fleet record from the Brain archive; customer value only where Engine already has it)."""
    import json
    sample = build_record("Sample Lake|XX", datetime(2026, 10, 14, 1, tzinfo=timezone.utc), datetime(2026, 10, 14, 7, tzinfo=timezone.utc),
                          {"speedMph": 6.2, "directionDeg": 225, "gustMph": 9.0, "fetchedAt": "2026-10-14T01:00:03Z", "host": "primary"},
                          {"speedMph": 5.4, "directionDeg": 231, "p90Mph": 8.1, "forecastInit": "2026-10-14T00:00:00Z"}, {"published": True, "generatedAt": "2026-10-14T01:06:00Z", "stale": False})
    import gzip, random
    rng = random.Random(7)
    batch = []
    for i in range(lakes):                                       # one fleet-hour of varied (deterministic) records to measure a realistic gzip ratio
        sp, p90 = round(rng.uniform(0, 14), 1), None
        p90 = round(sp + rng.uniform(0.5, 4), 1)
        batch.append(build_record(f"Lake {i}|XX", datetime(2026, 10, 14, 1, tzinfo=timezone.utc), datetime(2026, 10, 14, 7, tzinfo=timezone.utc),
                                  {"speedMph": sp, "directionDeg": rng.randrange(360), "gustMph": round(sp + 3, 1), "fetchedAt": "2026-10-14T01:00:03Z", "host": "primary"},
                                  {"speedMph": round(sp + rng.uniform(-3, 3), 1), "directionDeg": rng.randrange(360), "p90Mph": p90, "forecastInit": "2026-10-14T00:00:00Z"},
                                  {"published": True, "generatedAt": "2026-10-14T01:06:00Z", "stale": False}))
    raw = json.dumps(batch, separators=(",", ":")).encode()
    gz_ratio = len(gzip.compress(raw)) / len(raw)
    b = record_bytes or len(json.dumps(sample, separators=(",", ":")))
    per_day = lakes * 24 * b
    return {"recordBytes": b, "rowsPerDayFleet": lakes * 24, "gzRatioMeasured": round(gz_ratio, 3), "rawMBPerDay": round(per_day / 1e6, 2), "gzMBPerDay": round(per_day * gz_ratio / 1e6, 2),
            "gzMBPerMonth": round(per_day * gz_ratio * 30 / 1e6, 1), "objectsPerDay": 24,
            "extraProviderCallsPerDay_fleetHourlyOpenMeteo": lakes * 24, "extraProviderCallsPerDay_designed": pilot_lakes * 24,
            "note": "designed path logs the customer value only on Engine requests plus a small pilot-lake lookup; fleet-hourly Open-Meteo logging would add ~15k calls/day and is not proposed"}
