"""Preregistered confirmatory analysis (BIOLOGICAL_VALIDATION_PREREGISTRATION_v1). Constants are FROZEN with that document and pinned by tests; changing a
value here without a new, dated preregistration file is a protocol violation.

Per (species, lake): shootable encounters per effort-hour in FAVOURED vs OTHER zones, matched to the single latest prior prediction, trip-level bootstrap.
It computes nothing below the minimum sample and promotes nothing: a candidate for VALIDATED still needs two systems, independent review and a human decision.
"""
from __future__ import annotations

import datetime as dt
import random

import features as ft

PREREG = "BIOLOGICAL_VALIDATION_PREREGISTRATION_v1"
MIN_TRIPS = 30                 # independent trips per (species, system) before any verdict
MIN_HOURS_EACH_GROUP = 10.0    # effort-hours in FAVOURED and in OTHER
MIN_PAIRED_TRIPS = 10          # trips containing both groups
POINT_ESTIMATE_MIN = 1.5
ALPHA = 0.05
BOOTSTRAP_N = 10000
SEED = 20261014
MATCH_WINDOW_H = 36.0
CONFIRMATORY_SPECIES = ("common_carp", "spotted_gar", "silver_carp", "longnose_gar")


def _t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def matched_rows(predictions, observations, species, lake):
    """[(tripId, group, effortHours, shootable|None)] for CONFIRMED/LIKELY observations of one species on one lake, each against its one latest prior prediction."""
    rows = []
    for o in observations:
        if o["lakeId"] != lake or o["speciesId"] != species or o["speciesIdConfidence"] not in ("CONFIRMED", "LIKELY"):
            continue
        ot = _t(o["observedAt"])
        c = [p for p in predictions if p["lakeId"] == lake and p["speciesId"] == species and (p.get("expected") or {}).get("habitat")
             and _t(p["predictedAt"]) <= ot and (ot - _t(p["predictedAt"])).total_seconds() / 3600.0 <= MATCH_WINDOW_H]
        if not c:
            continue
        p = max(c, key=lambda x: x["predictedAt"])
        rows.append((o["tripId"], "favoured" if o["zone"] in p["expected"]["habitat"] else "other", o["effortMinutes"] / 60.0, o.get("shootableCount")))
    return rows


def _ratio(rows):
    h = {"favoured": 0.0, "other": 0.0}
    n = {"favoured": 0, "other": 0}
    for _, g, hrs, s in rows:
        h[g] += hrs
        n[g] += s or 0
    if h["favoured"] <= 0 or h["other"] <= 0 or n["other"] == 0:
        return None
    return (n["favoured"] / h["favoured"]) / (n["other"] / h["other"])


def analyse(predictions, observations, species, lake, *, k_comparisons: int = 1, n_boot: int = BOOTSTRAP_N, seed: int = SEED) -> dict:
    rows = matched_rows(predictions, observations, species, lake)
    trips = {r[0] for r in rows}
    hours = {g: sum(r[2] for r in rows if r[1] == g) for g in ("favoured", "other")}
    by_trip: dict[str, set] = {}
    for tid, g, _, _ in rows:
        by_trip.setdefault(tid, set()).add(g)
    paired = sum(1 for g in by_trip.values() if len(g) == 2)
    out = {"preregistration": PREREG, "species": species, "lake": lake, "confirmatory": species in CONFIRMATORY_SPECIES, "independentTrips": len(trips),
           "effortHours": {g: round(v, 3) for g, v in hours.items()}, "pairedTrips": paired}
    missing = []
    if len(trips) < MIN_TRIPS:
        missing.append(f"independent trips {len(trips)} < {MIN_TRIPS}")
    if min(hours.values()) < MIN_HOURS_EACH_GROUP:
        missing.append(f"effort-hours in the smaller group {min(hours.values()):.1f} < {MIN_HOURS_EACH_GROUP:g}")
    if paired < MIN_PAIRED_TRIPS:
        missing.append(f"paired trips {paired} < {MIN_PAIRED_TRIPS}")
    if any(r[3] is None for r in rows if r[1] in ("favoured", "other")) and any(r[3] is None for r in rows):
        missing.append("some observations lack shootableCount (rate not computed, never imputed)")
    if missing:
        return out | {"status": "BELOW_MINIMUM_SAMPLE", "verdict": None, "reasons": missing,
                      "note": "No verdict. Any ratio is withheld below the preregistered minimum sample."}
    point = _ratio(rows)
    adj = 1.0 - ALPHA / max(1, k_comparisons)
    rng = random.Random(seed)
    tid = sorted(trips)
    grouped = {t: [r for r in rows if r[0] == t] for t in tid}
    ratios = []
    for _ in range(n_boot):
        samp = []
        for _i in range(len(tid)):
            samp += grouped[tid[rng.randrange(len(tid))]]
        r = _ratio(samp)
        if r is not None:
            ratios.append(r)
    ratios.sort()
    lo = ratios[int(((1 - adj) / 2) * len(ratios))] if ratios else None
    hi = ratios[min(len(ratios) - 1, int((1 - (1 - adj) / 2) * len(ratios)))] if ratios else None
    met = bool(point is not None and lo is not None and lo > 1.0 and point >= POINT_ESTIMATE_MIN)
    reverse = bool(hi is not None and hi < 1.0)
    return out | {"status": "CRITERION_MET" if met else "CRITERION_NOT_MET", "ratio": point, "interval": [lo, hi], "intervalLevel": adj, "bootstrapResamples": len(ratios),
                  "reverseEffect": reverse, "verdict": "MET" if met else "NOT_MET",
                  "note": "One (species, system) result. VALIDATED needs two independent systems, independent reviewer sign-off and a recorded human decision; no code promotes a species."}
