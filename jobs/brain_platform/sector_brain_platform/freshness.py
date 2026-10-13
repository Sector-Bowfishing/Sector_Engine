"""The per-state freshness envelope (contract section 4)."""
from __future__ import annotations

import datetime as dt

from .enums import STALENESS_MODEL
from .timeutil import iso, parse_time


def freshness(generated_at: dt.datetime | str, now: dt.datetime, stale_after_hours: float, staleness_model: str = "TIME",
              source_observation_at: dt.datetime | str | None = None, next_check_at: dt.datetime | str | None = None,
              evidence_stale: bool = False, evidence_reasons=(), refresh_reason: str = "scheduled") -> dict:
    """`stale` is the TIME rule only; `evidenceStale` is the brain's own rule. Never one from the other."""
    if staleness_model not in STALENESS_MODEL:
        raise ValueError(f"not a staleness model: {staleness_model!r}")
    gen = parse_time(generated_at) if isinstance(generated_at, str) else generated_at
    if gen is None:
        raise ValueError("generated_at is required")
    out = {"generatedAt": iso(gen), "refreshReason": refresh_reason, "evidenceStale": bool(evidence_stale)}
    reasons = list(evidence_reasons) if evidence_stale else []
    if staleness_model == "TIME":
        fresh_until = gen + dt.timedelta(hours=stale_after_hours)
        stale = now > fresh_until
        out["freshUntil"] = iso(fresh_until)
        out["stale"] = stale
        if stale:
            reasons.insert(0, f"state is {round((now - gen).total_seconds() / 3600, 1)} h old (> {stale_after_hours} h)")
    else:
        out["stale"] = False
    if source_observation_at is not None:
        out["sourceObservationAt"] = iso(parse_time(source_observation_at) if isinstance(source_observation_at, str) else source_observation_at)
    if next_check_at is not None:
        out["nextCheckAt"] = iso(parse_time(next_check_at) if isinstance(next_check_at, str) else next_check_at)
    elif staleness_model == "TIME":
        out["nextCheckAt"] = out["freshUntil"]
    if reasons:
        out["staleReasons"] = reasons
    return out
