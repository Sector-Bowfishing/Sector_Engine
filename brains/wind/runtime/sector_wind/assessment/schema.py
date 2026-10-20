"""Identity and enums of the Wind Exposure Assessment contract (`sector-wind-exposure-assessment-v1`).

JSON Schema: brains/wind/contracts/wind-exposure-assessment-v1.json. This module holds the enums the builder emits and a
dependency-free invariant check (`check`) that the builder runs on every assessment it returns."""
from __future__ import annotations

ASSESSMENT_SCHEMA = "sector-wind-exposure-assessment-v1"
KNOWLEDGE_VERSION = "wind-exposure-assessment-1.0.0"   # bump when any assessment rule, label or threshold below changes

# Assessment status. Only READY carries shoreline results; every other status carries none (unknown stays unknown).
STATUS = {
    "READY": "Wind and geometry available and fresh enough; shoreline results are present.",
    "INPUT_STALE": "The wind input failed its freshness rule; no shoreline results (a stale wind would rank the wrong banks).",
    "WIND_UNAVAILABLE": "No usable current wind (speed missing); no shoreline results.",
    "DIRECTION_UNKNOWN": "Wind speed is known but direction is not, at a speed where direction decides exposure; no shoreline results.",
    "GEOMETRY_UNAVAILABLE": "No frozen fetch table for this lake; no shoreline results.",
    "UNSUPPORTED_LAKE": "The lake has no Wind geometry coverage; no shoreline results.",
}
INPUT_KINDS = ("analysis", "forecast", "observation", "synthetic", "unavailable")
CONFIDENCE = {
    "MODERATE": "Physically consistent model output from fresh inputs, wind below the regime where the forecast is known to fail. "
                "Not field-validated.",
    "LOW": "Inputs or conditions where the model is known to be weak (forecast wind >= 10 mph, strong-wind regime, boundary class, "
           "forecast lead > 12 h, or synthetic input).",
    "UNKNOWN": "No assessment could be made.",
}
# HIGH is deliberately not emitted: no bank-scale field validation exists (Wind Certification dims 6/7 = 0 observations).
VALIDATION_STATUS = {"capability": "IMPLEMENTED", "observedAccuracy": "NOT_FIELD_VALIDATED", "lifecycle": "SHADOW",
                     "customerExposure": "NOT_AUTHORIZED", "validated": False}

import re

# Specialist boundary (Wind owns wind; Sector Intelligence owns cross-Brain synthesis and bowfishing recommendations).
# No key may name another domain or a recommendation, and no text may talk about fish or fishing quality, except the explicit
# disclaimers that say what Wind does NOT assess.
FORBIDDEN_KEY = re.compile(r"fish|recommend|opportunit|suitab|best|catch|goodfor|score", re.I)
FORBIDDEN_TEXT = re.compile(r"\bfish(es|ing)?\b|bowfish|best place|good place|terrible|excellent spot|go fishing|shoot", re.I)
DISCLAIMER_PATHS = ("scope.", "limitations.WIND_ONLY_SCOPE", ".note", "provenance.rankingRules")


def boundary_problems(obj, path: str = "") -> list[str]:
    """Cross-domain leaks in an assessment (empty = specialist-clean)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if FORBIDDEN_KEY.search(k):
                out.append(f"{path}.{k}: key outside the wind domain")
            sub = f"{path}.{k}" if path else k
            if isinstance(obj.get("id"), str) and path.startswith("limitations"):
                sub = f"limitations.{obj['id']}.{k}"
            out += boundary_problems(v, sub)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += boundary_problems(v, f"{path}[{i}]" if not path.startswith("limitations") else path)
    elif isinstance(obj, str):
        if FORBIDDEN_TEXT.search(obj) and not any(d in path for d in DISCLAIMER_PATHS):
            out.append(f"{path}: fishing language in a wind assessment")
    return out


REQUIRED_KEYS = ("assessmentSchema", "knowledgeVersion", "lakeId", "status", "evaluatedAt", "reference", "wind", "scope",
                 "shorelines", "lakeSummary", "confidence", "limitations", "explanation", "provenance", "validation")


def check(d: dict) -> list[str]:
    """Invariants every assessment must satisfy (returns problems; [] = ok). Kept independent of the builder on purpose."""
    p = [f"missing {k}" for k in REQUIRED_KEYS if k not in d]
    if p:
        return p
    p += boundary_problems(d)
    if d["assessmentSchema"] != ASSESSMENT_SCHEMA:
        p.append("wrong schema id")
    if d["status"] not in STATUS:
        p.append(f"unknown status {d['status']}")
    if d["confidence"]["level"] not in CONFIDENCE:
        p.append("unknown confidence level")
    if d["validation"].get("validated") is not False:
        p.append("assessment claims validation")
    sh = d["shorelines"]
    if d["status"] != "READY":
        if sh is not None or d["lakeSummary"] is not None:
            p.append("non-READY assessment carries shoreline results")
        if d["confidence"]["level"] != "UNKNOWN":
            p.append("non-READY assessment carries a confidence level")
        return p
    if not d["limitations"]:
        p.append("READY assessment without limitations")
    for group in ("sheltered", "exposed", "requested"):
        for b in sh.get(group, []):
            p += [f"{b.get('bankId')}: {x}" for x in check_bank(b)]
            if group == "sheltered" and b["windExposure"]["code"] == "UNKNOWN":
                p.append(f"{b['bankId']}: UNKNOWN bank listed as sheltered")
    return p


def check_bank(b: dict) -> list[str]:
    """Exposure/surface semantic invariants for one bank result."""
    p = []
    ex = b["windExposure"]["code"]
    if ex == "UNKNOWN":
        if b.get("predictedSurface") is not None:
            p.append("UNKNOWN bank carries a surface prediction")
        if b.get("confidence") != "unknown":
            p.append("UNKNOWN bank confidence is not 'unknown'")
        return p
    s = b["predictedSurface"]
    order = ("PROTECTED", "LOW_EXPOSURE", "MODERATE_EXPOSURE", "HIGH_EXPOSURE", "EXTREME_EXPOSURE")
    chop = order.index(ex) + 1
    if s["class"] < chop:
        p.append("surface class below the wave (chop) class")
    if s["driver"] == "WAVES" and s["class"] != chop:
        p.append("driver WAVES but surface class differs from wave class")
    if s["driver"] == "WIND_TEXTURE" and s["class"] <= chop:
        p.append("driver WIND_TEXTURE but texture does not raise the surface class")
    lo, hi = s["waveHeightRangeIn"]
    if not (lo <= s["waveHeightIn"] <= hi):
        p.append("wave height outside its own range")
    if not b.get("explanation"):
        p.append("no explanation")
    return p
