"""Trip timeline: how wind exposure and the modeled surface change hour by hour over a bowfishing trip.

Physics per hour is the frozen M0 surface model (CEM + frozen duration rule `brain.state.frozen_duration_h` over the hourly
series). Wave memory: M0 has none, so when the wind eases the modeled waves drop at once, while real chop lingers. The M4
fetch-scaled memory candidate FAILED its pre-registered promotion rule (docs: WIND_M4_PREREG.md; BWIS C3 = 0), so it is not run
here, not even in shadow; the timeline instead flags every hour where M0 recession is likely optimistic (`waveMemory`).
"""
from __future__ import annotations

from .. import bowfishing as BF
from ..brain.contract import TRANSITION_THRESHOLDS_MPH, cardinal, mph
from ..brain.state import _circ, frozen_duration_h
from . import semantics as S

SHIFT_DEG = 45.0             # a direction change this large re-orders which shores are exposed
SHIFT_MIN_MS = 2.2352        # 5 mph: below this, direction barely matters to the surface
EASING_FRACTION = 0.7        # speed below 70 % of the trip's running peak = easing after a blow
EASED_FROM_CLASS = 3         # ... at a bank whose modeled surface had reached Light chop or worse
MAX_HOURS = 24
WAVE_MEMORY = {"model": "M0", "memory": False,
               "candidate": "M4 fetch-scaled wave memory: FAILED its pre-registered promotion rule (kept as research only)",
               "effect": "Modeled waves fall as soon as the wind eases; real chop usually takes longer to lay down. Hours flagged "
                         "`recessionOptimistic` are likely rougher than modeled."}


def _hour_series(hourly, prior):
    ser = [(h.get("speedMS"), h.get("dirFromDeg")) for h in (prior or [])]
    return ser, [(h.get("speedMS"), h.get("dirFromDeg")) for h in hourly]


def timeline(L: dict, hourly: list[dict], bank_ids: list[str], prior: list[dict] | None = None) -> dict:
    """hourly: [{at, speedMS, dirFromDeg, gustMS?, kind, leadHours?}] oldest first (the trip window).
    prior: the same shape for the hours BEFORE the trip (duration memory); None = unknown history (flagged)."""
    hourly = hourly[:MAX_HOURS]
    ix = {b["id"]: i for i, b in enumerate(L["banks"])}
    pre, trip = _hour_series(hourly, prior)
    banks = [b for b in bank_ids if b in ix]
    per_bank = {b: [] for b in banks}
    hours, events = [], []
    peak = 0.0
    start_dir = next((d for s, d in trip if s is not None and d is not None and s >= SHIFT_MIN_MS), None)
    prev_mph = None
    for k, h in enumerate(hourly):
        s, d = trip[k]
        dur = frozen_duration_h(pre + trip[:k + 1])
        row = {"at": h["at"], "kind": h.get("kind"), "leadHours": h.get("leadHours"), "sustainedMph": mph(s), "gustMph": mph(h.get("gustMS")),
               "directionDeg": None if d is None else round(d), "directionCardinal": cardinal(d), "durationH": dur}
        if s is None:
            row["status"] = "WIND_UNAVAILABLE"
        elif d is None and s >= 0.5:
            row["status"] = "DIRECTION_UNKNOWN"
        else:
            row["status"] = "READY"
        hours.append(row)
        if s is not None:
            m = mph(s)
            if prev_mph is not None:
                for thr in TRANSITION_THRESHOLDS_MPH:
                    if prev_mph < thr <= m:
                        events.append({"at": h["at"], "type": "WIND_RISING", "text": f"wind rises above {thr} mph"})
                    elif prev_mph >= thr > m:
                        events.append({"at": h["at"], "type": "WIND_EASING", "text": f"wind drops below {thr} mph"})
            prev_mph = m
            if d is not None and start_dir is not None and s >= SHIFT_MIN_MS and _circ(d, start_dir) >= SHIFT_DEG:
                events.append({"at": h["at"], "type": "DIRECTION_SHIFT",
                               "text": f"wind has shifted from {cardinal(start_dir)} to {cardinal(d)}: different shores are now exposed"})
                start_dir = d
        if row["status"] != "READY":
            for b in banks:
                per_bank[b].append({"at": h["at"], "exposure": "UNKNOWN", "surfaceClass": None, "waveHeightIn": None, "confidence": "unknown"})
            continue
        dd = 0.0 if d is None else d          # calm: < 0.5 m/s gives Hm0 < 1 in at any fetch (same rule as brain.state)
        easing = s < EASING_FRACTION * peak
        peak = max(peak, s)
        for b in banks:
            r = BF.evaluate_bank(L, ix[b], s, dd, dur)
            if r["exposureRank"] == "UNKNOWN":
                per_bank[b].append({"at": h["at"], "exposure": "UNKNOWN", "surfaceClass": None, "waveHeightIn": None, "confidence": "unknown"})
                continue
            prior_max = max([x["surfaceClass"] or 0 for x in per_bank[b]] or [0])
            per_bank[b].append({"at": h["at"], "exposure": r["exposureRank"], "surfaceClass": r["predictedSurfaceClass"],
                                "surfaceLabel": S.SURFACE_LABEL[r["predictedSurfaceClass"]], "waveHeightIn": round(r["predictedHm0In"], 1),
                                "confidence": r["confidence"], "recessionOptimistic": bool(easing and prior_max >= EASED_FROM_CLASS)})
    bank_out = []
    for b in banks:
        seq = per_bank[b]
        bank_out.append({"bankId": b, "hours": seq, "changes": _changes(seq), "summary": _summary(b, seq)})
    return {"hours": hours, "events": events, "banks": bank_out, "waveMemory": WAVE_MEMORY,
            "durationBasis": "frozen duration rule over the supplied hourly series" + ("" if prior else
                             "; no wind history before the trip was supplied, so early-hour waves may be UNDER-estimated if wind was already blowing"),
            "priorHistoryHours": len(prior or [])}


def _changes(seq):
    out, last = [], None
    for x in seq:
        e = x["exposure"]
        grp = "UNKNOWN" if e == "UNKNOWN" else ("SHELTERED" if e in S.SHELTERED else "EXPOSED" if e in S.EXPOSED else "MODERATE")
        if last is not None and grp != last:
            out.append({"at": x["at"], "from": last, "to": grp})
        last = grp
    return out


def _summary(bank_id, seq):
    known = [x for x in seq if x["surfaceClass"] is not None]
    if not known:
        return f"{bank_id}: no usable wind during the trip window; exposure unknown."
    worst = max(known, key=lambda x: x["surfaceClass"])
    best = min(known, key=lambda x: x["surfaceClass"])
    s = f"{bank_id}: surface modeled from {S.SURFACE_LABEL[best['surfaceClass']].lower()} to {S.SURFACE_LABEL[worst['surfaceClass']].lower()}"
    s += f" (roughest at {worst['at']}, {worst['waveHeightIn']:g} in)."
    if any(x.get("recessionOptimistic") for x in known):
        s += " After the wind eases, real chop is likely to linger longer than modeled."
    return s
