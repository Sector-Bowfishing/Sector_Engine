"""One shared field-validation trip envelope with per-Brain blocks (docs/brains/platform/FIELD_VALIDATION_MODEL.md).

Not four frameworks: the envelope is common; each Brain contributes only a block of named fields. A value is a real number/string/bool,
absent, or an explicit unknown marker (model_v1.unknown_marker). `None` is rejected so null can never be read as zero.
"""
from __future__ import annotations

from .model_v1 import UNKNOWN_KINDS, ModelError

ENVELOPE_REQUIRED = ("tripId", "lakeId", "zoneId", "timestamp", "location", "observer", "conditionsRef", "consentVersion", "blocks")
# Registered Brain blocks: field -> expected python types. A new Brain registers here (additive); fields are optional unless listed in `required`.
BLOCKS = {
    "wind": {"fields": {"predictedExposure": (str, int, float), "observedExposure": (str, int, float), "predictedSurface": (str,), "observedSurface": (str,),
                        "providerWindMph": (int, float), "providerGustMph": (int, float)}, "required": ()},
    "depth": {"fields": {"predictedEffectiveDepthFt": (int, float), "observedSonarDepthFt": (int, float), "dryOrWet": (str,), "shootable": (bool,)}, "required": ()},
    "biological": {"fields": {"species": (list,), "encounters": (int,), "shootableCount": (int,), "effortMinutes": (int, float)}, "required": ()},
    "vegetation": {"fields": {"surfaceVegetationObserved": (bool,), "coverageClass": (str,), "vegetationType": (str,)}, "required": ()},
}


def is_unknown(v) -> bool:
    return isinstance(v, dict) and v.get("unknown") in UNKNOWN_KINDS


def validate_trip(trip: dict, blocks=BLOCKS) -> dict:
    for k in ENVELOPE_REQUIRED:
        if k not in trip or trip[k] is None or trip[k] == "":
            raise ModelError(f"trip missing required envelope field {k!r}")
    b = trip["blocks"]
    if not isinstance(b, dict) or not b:
        raise ModelError("trip needs at least one Brain block")
    for brain, block in b.items():
        spec = blocks.get(brain)
        if spec is None:
            raise ModelError(f"no registered field block for Brain {brain!r}")
        for field, v in block.items():
            if field not in spec["fields"]:
                raise ModelError(f"{brain}.{field}: not a field of the {brain} block")
            if v is None:
                raise ModelError(f"{brain}.{field}: null is not allowed; omit the field or use an explicit unknown marker")
            if is_unknown(v):
                continue
            if isinstance(v, bool) and bool not in spec["fields"][field]:
                raise ModelError(f"{brain}.{field}: bool where {spec['fields'][field]} expected")
            if not isinstance(v, spec["fields"][field]):
                raise ModelError(f"{brain}.{field}: wrong type {type(v).__name__}")
        for req in spec["required"]:
            if req not in block:
                raise ModelError(f"{brain}.{req}: required")
    return trip
