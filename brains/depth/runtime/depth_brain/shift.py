"""Effective-depth SHIFT engine (pure functions; no I/O, no clock).

    shiftFt = levelFt - referencePoolFt         (negative = lower than reference; see contract.py)

The reference is one of contract.REFERENCE_BASES: `fullPool` (directory pool, datum-verified), `lowWaterDatum` (Great Lakes chart datum,
IGLD 1985) or `seriesMedian` (the gauge's own seasonal median, read from Lake Brain's seasonalBand at run time; datum status SAME_SERIES).

A shift is NOT a depth. It says how far every reference depth has moved; it says nothing about what the depth of any
particular spot is. A result carries mode `shiftOnly` unless real contour evidence supplies reference depths (zones.py).
Unknown stays unknown: every refusal returns mode `unknown` with machine-readable reason codes."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from . import contract as C
from .datum import DatumAssessment, normalize_datum


@dataclass
class ReferencePool:
    pool_ft: float | None
    basis: str | None = None              # fullPool | seriesMedian | lowWaterDatum (manifest); anything else (naturalSurface, ...) is refused
    confidence: str | None = None         # high | medium | low
    datum: str | None = None              # canonical datum or None
    datum_verified: bool = False
    source: str | None = None
    assessment: DatumAssessment | None = None
    relative_scale_pool: float | None = None   # Duke publishes some lakes on a 100-based scale (100.0 = full pond); the same pool in that frame
    lake_pool_ft: float | None = None     # the normal pool Lake Brain's differenceFromNormalPoolFt uses, when Depth's reference differs from it (recorded)


@dataclass
class LevelObservation:
    elevation_ft: float | None
    unit: str | None = "ft"
    datum: str | None = None
    observed_at: datetime | None = None
    capability: str | None = None         # Lake Brain sourceCapability
    kind: str | None = None               # Lake Brain kind OBSERVED | PROXY | UNAVAILABLE
    lake_difference_ft: float | None = None   # Lake Brain differenceFromNormalPoolFt (cross-check only)
    seasonal_band: dict | None = None     # Lake Brain seasonalBand {p50, basisYears, windowDays, sampleCount, ...}: the seriesMedian reference
    source_fallback: bool = False         # Lake Brain sourceFallback present: the reading came from a fallback source, not the primary series


@dataclass
class ShiftResult:
    mode: str                             # shiftOnly | unknown
    shift_ft: float | None = None
    sigma_ft: float | None = None
    confidence: str | None = None         # HIGH | MEDIUM | LOW
    resolvable: bool | None = None        # |shift| > 2 sigma
    reasons: list = field(default_factory=list)      # machine codes (why unknown / what limited it)
    flags: list = field(default_factory=list)        # non-fatal quality flags
    sigma_parts: dict = field(default_factory=dict)
    level_age_hours: float | None = None
    evidence_stale: bool = False
    reference_basis: str | None = None
    reference_ft: float | None = None     # the reference actually subtracted (the run-time median for seriesMedian)

    def as_dict(self) -> dict:
        d = {"mode": self.mode}
        if self.mode == "shiftOnly":
            d.update({"shiftFt": round(self.shift_ft, 1), "uncertaintyFt": round(self.sigma_ft, 2), "confidence": self.confidence,
                      "evidenceKind": C.SHIFT_EVIDENCE_KIND, "resolvable": self.resolvable,
                      "sigmaComponentsFt": {k: round(v, 3) for k, v in self.sigma_parts.items()},
                      "sigmaAssumed": [k for k in self.sigma_parts if k in C.SIGMA_ASSUMED]})
            if self.reference_basis and self.reference_basis != "fullPool":         # fullPool states keep their v1 shape exactly
                d.update({"referenceBasis": self.reference_basis, "referenceFt": round(self.reference_ft, 2)})
        else:
            d["reasons"] = list(self.reasons)
        if self.flags:
            d["flags"] = list(self.flags)
        return d


def _unknown(*reasons, flags=(), age=None) -> ShiftResult:
    return ShiftResult("unknown", reasons=list(reasons), flags=list(flags), level_age_hours=age)


def confidence_label(sigma: float) -> str:
    if sigma <= C.CONF_HIGH_MAX_SIGMA:
        return "HIGH"
    if sigma <= C.CONF_MEDIUM_MAX_SIGMA:
        return "MEDIUM"
    return "LOW"


def compute_shift(level: LevelObservation | None, ref: ReferencePool | None, now: datetime, manifest_level_datum: str | None = None) -> ShiftResult:
    """Return a shift or an explicit refusal. Order of checks is the audit order; the first failing check names the refusal."""
    series = ref is not None and ref.basis == "seriesMedian"
    if ref is None or (not series and (ref.pool_ft is None or not math.isfinite(ref.pool_ft))):
        return _unknown("MISSING_REFERENCE_POOL")
    if level is None or level.elevation_ft is None or not math.isfinite(level.elevation_ft):
        return _unknown("MISSING_CURRENT_LEVEL")
    if level.kind and level.kind.upper() != "OBSERVED":
        return _unknown("LEVEL_NOT_DIRECT_OBSERVATION", flags=[f"lakeKind:{level.kind}"])
    if level.capability not in C.ALLOWED_LEVEL_CAPABILITIES:
        return _unknown("LEVEL_SOURCE_NOT_DIRECT", flags=[f"capability:{level.capability}"])
    if (level.unit or "ft").lower() not in ("ft", "feet", "foot"):
        return _unknown("LEVEL_UNIT_NOT_FEET")
    if level.observed_at is None:
        return _unknown("MISSING_OBSERVATION_TIME")
    age = (now - level.observed_at).total_seconds() / 3600.0
    if age < -0.25:
        return _unknown("OBSERVATION_IN_FUTURE", age=age)
    if age > C.LEVEL_MAX_AGE_HOURS:
        return _unknown("LEVEL_TOO_OLD", age=age)
    if ref.basis not in C.REFERENCE_BASES:
        return _unknown("REFERENCE_NOT_A_POOL_ELEVATION", flags=[f"basis:{ref.basis}"], age=age)
    if ref.basis == "fullPool" and ref.confidence not in C.REFERENCE_CONF_ALLOWED:
        return _unknown("REFERENCE_POOL_CONFIDENCE_LOW", flags=[f"confidence:{ref.confidence}"], age=age)
    if ref.basis == "lowWaterDatum" and normalize_datum(ref.datum) != "IGLD85":
        return _unknown("REFERENCE_DATUM_NOT_IGLD85", flags=[f"referenceDatum:{ref.datum}"], age=age)
    if ref.basis == "lowWaterDatum" and normalize_datum(level.datum) != "IGLD85":         # the reading itself must be stamped IGLD 1985; unstamped is refused
        return _unknown("LEVEL_DATUM_NOT_IGLD85", flags=[f"levelDatum:{level.datum}"], age=age)
    # A datum stamped on the live Lake Brain state must agree with the datum the audit assumed for this level source.
    live_d, man_d = normalize_datum(level.datum), normalize_datum(manifest_level_datum)
    if live_d and man_d and live_d != man_d:
        return _unknown("LEVEL_DATUM_CONFLICT", flags=[f"live:{live_d} audited:{man_d}"], age=age)
    a = ref.assessment
    if a is None or not a.usable:
        return _unknown("DATUM_UNKNOWN" if (a is None or a.status == "UNKNOWN") else "DATUM_INCOMPATIBLE",
                        flags=list(a.reasons) if a else ["datum not assessed"], age=age)

    pool_sigma = C.SIGMA_POOL.get(ref.confidence or "", C.SIGMA_POOL["high"])
    if series:
        why = _series_median_refusal(level, a)
        if why:
            return _unknown(why[0], flags=why[1], age=age)
        ref_ft, pool_sigma = float(level.seasonal_band["p50"]), C.SIGMA_SERIES_MEDIAN
    elif a.status == "SAME_SERIES":                                          # a same-series datum status only makes sense with the series reference
        return _unknown("DATUM_UNKNOWN", flags=["SAME_SERIES datum status without a seriesMedian reference"], age=age)
    else:
        ref_ft = ref.pool_ft

    level_in_ref = level.elevation_ft + (a.conversion_ft if a.status == "CONVERTED" else 0.0)
    pool_in_frame, frame_flags = ref_ft, []
    if ref.relative_scale_pool is not None and ref.basis == "fullPool":     # Duke's 100-based frame is a full-pool frame only          # two documented frames for one lake; the frames are far apart (hundreds of ft vs ~100), never ambiguous
        if abs(level_in_ref - ref.relative_scale_pool) <= C.MAX_PLAUSIBLE_SHIFT_FT and abs(level_in_ref - ref.pool_ft) > C.MAX_PLAUSIBLE_SHIFT_FT:
            pool_in_frame, frame_flags = ref.relative_scale_pool, ["levelFrame:relativeScale100"]
        elif abs(level_in_ref - ref.relative_scale_pool) <= C.MAX_PLAUSIBLE_SHIFT_FT:
            return _unknown("LEVEL_FRAME_AMBIGUOUS", age=age)
    shift = level_in_ref - pool_in_frame
    if abs(shift) > C.MAX_PLAUSIBLE_SHIFT_FT:
        return _unknown("IMPLAUSIBLE_SHIFT", flags=[f"shift:{shift:.1f}ft"], age=age)

    parts = {("reference" if series else "pool"): pool_sigma, "level": C.SIGMA_LEVEL[level.capability], "datum": a.sigma_ft}
    sigma = math.sqrt(sum(v * v for v in parts.values()))
    label = confidence_label(sigma)
    if ref.basis in C.NEW_REFERENCE_BASES and label == "HIGH":
        label = "MEDIUM"                                                       # new reference bases: never HIGH until field-validated
    flags = (list(a.reasons) if a.status != "SAME_SOURCE" else []) + frame_flags
    # Lake's difference is from the DIRECTORY full pool: comparable only with a fullPool reference (never with a median or the LWD)
    if level.lake_difference_ft is not None and a.status != "CONVERTED" and not frame_flags and ref.basis == "fullPool":          # Lake's difference-from-pool is in the absolute frame; skip the cross-check on a relative-scale level
        lake_diff = level.lake_difference_ft - ((ref.pool_ft - ref.lake_pool_ft) if ref.lake_pool_ft is not None else 0.0)   # Lake's delta, re-based on Depth's reference
        if abs(lake_diff - shift) > C.LAKE_DELTA_DISAGREE_FT:
            flags.append(f"lakeBrainDeltaDisagrees:{lake_diff:+.2f} vs {shift:+.2f}")
    stale = age > C.LEVEL_FRESH_HOURS
    if stale:
        flags.append("levelObservationOlderThanFreshWindow")
    return ShiftResult("shiftOnly", shift, sigma, label, abs(shift) > 2 * sigma, flags=flags,
                       sigma_parts=parts, level_age_hours=age, evidence_stale=stale, reference_basis=ref.basis, reference_ft=pool_in_frame)


def _series_median_refusal(level: LevelObservation, a: DatumAssessment):
    """seriesMedian gates (contract.SERIES_MEDIAN_*). -> (reason, flags) or None. The median must come from the same gauge's own history,
    over the stated window and with enough years; a reading from a fallback source is a different series and is refused."""
    if a.status != "SAME_SERIES":
        return "SERIES_REFERENCE_NOT_SAME_SERIES", [f"datumStatus:{a.status}"]
    if level.source_fallback:
        return "SERIES_LEVEL_FROM_FALLBACK_SOURCE", []
    b = level.seasonal_band or {}
    p50 = b.get("p50")
    if not isinstance(p50, (int, float)) or not math.isfinite(p50):
        return "SERIES_MEDIAN_UNAVAILABLE", []
    if (b.get("basisYears") or 0) < C.SERIES_MEDIAN_MIN_YEARS:
        return "SERIES_HISTORY_TOO_SHORT", [f"basisYears:{b.get('basisYears')} < {C.SERIES_MEDIAN_MIN_YEARS}"]
    if b.get("windowDays") != C.SERIES_MEDIAN_WINDOW_DAYS:
        return "SERIES_MEDIAN_WINDOW_MISMATCH", [f"windowDays:{b.get('windowDays')} != {C.SERIES_MEDIAN_WINDOW_DAYS}"]
    if (b.get("sampleCount") or 0) < C.SERIES_MEDIAN_MIN_SAMPLES:
        return "SERIES_MEDIAN_TOO_FEW_SAMPLES", [f"sampleCount:{b.get('sampleCount')} < {C.SERIES_MEDIAN_MIN_SAMPLES}"]
    return None


def apply_shift(reference_depth_ft: float, shift_ft: float) -> float:
    """Effective depth of a point whose REFERENCE depth is known. <= 0 means dry. Only call with a real reference depth."""
    return reference_depth_ft + shift_ft
