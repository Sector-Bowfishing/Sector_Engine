"""Effective-depth SHIFT engine (pure functions; no I/O, no clock).

    shiftFt = levelFt - referencePoolFt         (negative = lower than reference; see contract.py)

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
    basis: str | None = None              # directory poolBasis: fullPool | naturalSurface | ...
    confidence: str | None = None         # high | medium | low
    datum: str | None = None              # canonical datum or None
    datum_verified: bool = False
    source: str | None = None
    assessment: DatumAssessment | None = None
    relative_scale_pool: float | None = None   # Duke publishes some lakes on a 100-based scale (100.0 = full pond); the same pool in that frame


@dataclass
class LevelObservation:
    elevation_ft: float | None
    unit: str | None = "ft"
    datum: str | None = None
    observed_at: datetime | None = None
    capability: str | None = None         # Lake Brain sourceCapability
    kind: str | None = None               # Lake Brain kind OBSERVED | PROXY | UNAVAILABLE
    lake_difference_ft: float | None = None   # Lake Brain differenceFromNormalPoolFt (cross-check only)


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

    def as_dict(self) -> dict:
        d = {"mode": self.mode}
        if self.mode == "shiftOnly":
            d.update({"shiftFt": round(self.shift_ft, 1), "uncertaintyFt": round(self.sigma_ft, 2), "confidence": self.confidence,
                      "evidenceKind": C.SHIFT_EVIDENCE_KIND, "resolvable": self.resolvable,
                      "sigmaComponentsFt": {k: round(v, 3) for k, v in self.sigma_parts.items()},
                      "sigmaAssumed": list(C.SIGMA_ASSUMED)})
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
    if ref is None or ref.pool_ft is None or not math.isfinite(ref.pool_ft):
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
    if ref.basis != "fullPool":
        return _unknown("REFERENCE_NOT_A_POOL_ELEVATION", flags=[f"basis:{ref.basis}"], age=age)
    if ref.confidence not in C.REFERENCE_CONF_ALLOWED:
        return _unknown("REFERENCE_POOL_CONFIDENCE_LOW", flags=[f"confidence:{ref.confidence}"], age=age)
    # A datum stamped on the live Lake Brain state must agree with the datum the audit assumed for this level source.
    live_d, man_d = normalize_datum(level.datum), normalize_datum(manifest_level_datum)
    if live_d and man_d and live_d != man_d:
        return _unknown("LEVEL_DATUM_CONFLICT", flags=[f"live:{live_d} audited:{man_d}"], age=age)
    a = ref.assessment
    if a is None or not a.usable:
        return _unknown("DATUM_UNKNOWN" if (a is None or a.status == "UNKNOWN") else "DATUM_INCOMPATIBLE",
                        flags=list(a.reasons) if a else ["datum not assessed"], age=age)

    level_in_ref = level.elevation_ft + (a.conversion_ft if a.status == "CONVERTED" else 0.0)
    pool_in_frame, frame_flags = ref.pool_ft, []
    if ref.relative_scale_pool is not None:          # two documented frames for one lake; the frames are far apart (hundreds of ft vs ~100), never ambiguous
        if abs(level_in_ref - ref.relative_scale_pool) <= C.MAX_PLAUSIBLE_SHIFT_FT and abs(level_in_ref - ref.pool_ft) > C.MAX_PLAUSIBLE_SHIFT_FT:
            pool_in_frame, frame_flags = ref.relative_scale_pool, ["levelFrame:relativeScale100"]
        elif abs(level_in_ref - ref.relative_scale_pool) <= C.MAX_PLAUSIBLE_SHIFT_FT:
            return _unknown("LEVEL_FRAME_AMBIGUOUS", age=age)
    shift = level_in_ref - pool_in_frame
    if abs(shift) > C.MAX_PLAUSIBLE_SHIFT_FT:
        return _unknown("IMPLAUSIBLE_SHIFT", flags=[f"shift:{shift:.1f}ft"], age=age)

    parts = {"pool": C.SIGMA_POOL[ref.confidence], "level": C.SIGMA_LEVEL[level.capability], "datum": a.sigma_ft}
    sigma = math.sqrt(sum(v * v for v in parts.values()))
    flags = (list(a.reasons) if a.status != "SAME_SOURCE" else []) + frame_flags
    if level.lake_difference_ft is not None and a.status != "CONVERTED":
        if abs(level.lake_difference_ft - shift) > C.LAKE_DELTA_DISAGREE_FT:
            flags.append(f"lakeBrainDeltaDisagrees:{level.lake_difference_ft:+.2f} vs {shift:+.2f}")
    stale = age > C.LEVEL_FRESH_HOURS
    if stale:
        flags.append("levelObservationOlderThanFreshWindow")
    return ShiftResult("shiftOnly", shift, sigma, confidence_label(sigma), abs(shift) > 2 * sigma, flags=flags,
                       sigma_parts=parts, level_age_hours=age, evidence_stale=stale)


def apply_shift(reference_depth_ft: float, shift_ft: float) -> float:
    """Effective depth of a point whose REFERENCE depth is known. <= 0 means dry. Only call with a real reference depth."""
    return reference_depth_ft + shift_ft
