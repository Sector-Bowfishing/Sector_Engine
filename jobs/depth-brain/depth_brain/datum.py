"""Vertical-datum compatibility. A depth shift subtracts two elevations; that is only meaningful when both are in the same
vertical reference system. Anything not provably compatible is UNKNOWN and produces no shift. Never subtract by hope.

Statuses
  SAME_SOURCE   reference pool and level series come from the same operator record (e.g. one CWMS project: top of conservation vs
                the pool series); datum identical by construction.
  SAME_DATUM    both datums are known (document-verified or explicitly stamped on the data) and equal.
  CONVERTED     datums known and different, and an explicit conversion (ft, NAVD88 - NGVD29) was supplied. Adds sigma.
  INCOMPATIBLE  datums known and different, no conversion supplied.
  UNKNOWN       either side unknown / per-site / unverified. Includes `LOCAL` and `PROJECT` datums unless both sides name the same one.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

from . import contract as C

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USABLE = ("SAME_SOURCE", "SAME_DATUM", "CONVERTED")

_ALIASES = {
    "NGVD29": "NGVD29", "NGVD 29": "NGVD29", "NGVD1929": "NGVD29", "NGVD": "NGVD29", "MSL29": "NGVD29",
    "NAVD88": "NAVD88", "NAVD 88": "NAVD88", "NAVD1988": "NAVD88",
    "LOCAL": "LOCAL", "PROJECT": "PROJECT", "PER_SITE": "PER_SITE",
}


def normalize_datum(value) -> str | None:
    """Map a datum string to a canonical code; None / blank / unrecognized -> None (unknown)."""
    if value is None:
        return None
    s = str(value).strip().upper().replace("_", " ")
    s = " ".join(s.split())
    if s in ("", "NONE", "NULL", "UNKNOWN", "UNRECORDED", "UNSPECIFIED", "N/A"):
        return None
    for key in (s, s.replace(" ", ""), s.replace("-", "")):
        if key in _ALIASES:
            return _ALIASES[key]
    return None


@dataclass
class DatumAssessment:
    status: str
    sigma_ft: float = 0.0
    conversion_ft: float = 0.0          # added to the LEVEL (in level datum) to express it in the reference datum
    reasons: list = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in USABLE

    def as_dict(self) -> dict:
        d = {"status": self.status, "sigmaFt": round(self.sigma_ft, 3)}
        if self.status == "CONVERTED":
            d["conversionFt"] = round(self.conversion_ft, 3)
        if self.reasons:
            d["reasons"] = list(self.reasons)
        return d


def assess(level_datum, reference_datum, *, same_source: bool = False, level_datum_verified: bool = True,
           reference_datum_verified: bool = True, navd88_minus_ngvd29_ft: float | None = None) -> DatumAssessment:
    """Decide whether `level - reference` is defensible.

    `*_verified` means the datum is document- or data-stamped, not an assumption. An unverified datum is treated as unknown.
    `navd88_minus_ngvd29_ft` = (elevation in NAVD88) - (elevation of the same point in NGVD29) at this lake."""
    if same_source:
        return DatumAssessment("SAME_SOURCE", C.SIGMA_DATUM["SAME_SOURCE"], 0.0, ["reference and level share one operator record"])
    ld = normalize_datum(level_datum) if level_datum_verified else None
    rd = normalize_datum(reference_datum) if reference_datum_verified else None
    if ld is None or rd is None:
        why = []
        if ld is None:
            why.append("level datum unknown or unverified")
        if rd is None:
            why.append("reference-pool datum unknown or unverified")
        return DatumAssessment("UNKNOWN", 0.0, 0.0, why)
    if ld in ("PER_SITE",) or rd in ("PER_SITE",):
        return DatumAssessment("UNKNOWN", 0.0, 0.0, ["per-site datum not resolved for this lake"])
    if ld == rd:
        if ld in ("LOCAL", "PROJECT"):
            return DatumAssessment("UNKNOWN", 0.0, 0.0, [f"both sides say {ld}; that is not proof of the same local datum"])
        return DatumAssessment("SAME_DATUM", C.SIGMA_DATUM["SAME_DATUM"], 0.0, [f"both {ld}"])
    pair = {ld, rd}
    if pair == {"NGVD29", "NAVD88"}:
        if navd88_minus_ngvd29_ft is None or not math.isfinite(navd88_minus_ngvd29_ft):
            return DatumAssessment("INCOMPATIBLE", 0.0, 0.0, [f"level {ld} vs reference {rd}: conversion not supplied"])
        # express the level in the reference datum
        conv = navd88_minus_ngvd29_ft if (ld == "NGVD29" and rd == "NAVD88") else -navd88_minus_ngvd29_ft
        return DatumAssessment("CONVERTED", C.SIGMA_DATUM["CONVERTED"], conv, [f"{ld}->{rd} conversion {conv:+.2f} ft"])
    return DatumAssessment("INCOMPATIBLE", 0.0, 0.0, [f"level {ld} vs reference {rd}: no defined conversion"])


# ── Provider table (document audit; docs/brains/depth/DEPTH_DATUM_AUDIT.md) ───────────────────────────────
def load_provider_table(path: str | None = None) -> dict:
    p = path or os.path.join(DATA_DIR, "datum_providers.json")
    if not os.path.exists(p):
        return {"schema": "depth-datum-providers-v1", "providers": {}, "referencePoolSources": {}}
    with open(p) as f:
        return json.load(f)


def provider_level_datum(table: dict, provider: str | None) -> tuple[str | None, bool, str | None]:
    """-> (canonical datum or None, verified_from_document, rawDatumLabel). Per-site / unknown / unlisted provider -> (None, False, raw)."""
    rec = (table.get("providers") or {}).get((provider or "").lower())
    if not rec:
        return None, False, None
    raw = rec.get("levelDatum")
    d = normalize_datum(raw)
    verified = rec.get("levelDatumBasis") == "verified_doc"
    return d, bool(d and verified), raw
