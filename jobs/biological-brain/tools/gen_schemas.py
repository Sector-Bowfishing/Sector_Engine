"""Generate the public JSON Schemas / feature contract from the code constants (so docs, schemas and code cannot drift).

  python3 tools/gen_schemas.py          # write schemas/*.json
  python3 tools/gen_schemas.py --check  # exit 1 if the committed files differ (used by a test)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import features as ft      # noqa: E402
import rules as rl         # noqa: E402
import validation_log as vl  # noqa: E402

S = "https://json-schema.org/draft/2020-12/schema"


def evidence_schema():
    return {"type": "object", "required": ["evidenceId", "packet", "sourceNo", "readStatus", "streamId", "directness", "counts"],
            "properties": {"evidenceId": {"type": "string"}, "packet": {"type": "string", "description": "private packet file stem; never the packet text"},
                           "sourceNo": {"type": "string"}, "readStatus": {"enum": list(rl.READ_STATUS)}, "streamId": {"type": "string"},
                           "directness": {"enum": list(rl.DIRECTNESS)}, "counts": {"type": "boolean"}, "southeast": {"type": "boolean"},
                           "studyType": {"type": "string"}, "region": {"type": "string"}, "sample": {"type": "string"},
                           "strength": {"enum": ["weak", "moderate", "strong"]}, "note": {"type": "string"}}}


def build():
    feats = {fid: {k: (list(v) if isinstance(v, tuple) else v) for k, v in spec.items()} for fid, spec in ft.REGISTRY.items()}
    contract = {"contractVersion": ft.FEATURES_VERSION, "warmRiseMinC": ft.WARM_RISE_MIN_C, "trendNoiseF": ft.TREND_NOISE_F,
                "temperatureBandsC": [{"id": b[0], "minInclusive": (None if b[1] == float("-inf") else b[1]), "maxExclusive": (None if b[2] == float("inf") else b[2])} for b in ft.TEMP_BANDS],
                "clarityBandsFt": [{"id": b[0], "minInclusive": b[1], "maxExclusive": (None if b[2] == float("inf") else b[2])} for b in ft.CLARITY_BANDS],
                "habitatClasses": list(ft.HABITAT_CLASSES), "depthClasses": list(ft.DEPTH_CLASSES), "features": feats}
    rule = {"$schema": S, "title": "Biological machine rule (biological-rule-v1)", "type": "object",
            "required": ["schemaVersion", "ruleId", "ruleVersion", "speciesId", "kind", "status", "confidence", "transferability", "applicability", "evidence"],
            "properties": {"schemaVersion": {"const": rl.RULE_SCHEMA_VERSION}, "ruleId": {"type": "string", "pattern": rl.RULE_ID.pattern},
                           "ruleVersion": {"type": "integer", "minimum": 1}, "speciesId": {"type": "string", "pattern": rl.SPECIES_ID.pattern},
                           "kind": {"enum": list(rl.KINDS)}, "status": {"enum": list(rl.STATUSES)}, "confidence": {"enum": list(rl.CONFIDENCE)},
                           "lifeStage": {"enum": list(rl.LIFE_STAGES)}, "behavior": {"type": "string"}, "statement": {"type": "string"},
                           "transferability": {"type": "object", "required": ["southeastReservoir"], "properties": {"southeastReservoir": {"enum": list(rl.TRANSFER)}}},
                           "applicability": {"type": "object", "properties": {"months": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 12}},
                                                                              "regions": {"type": "array", "items": {"enum": list(rl.REGIONS)}},
                                                                              "waterbodyTypes": {"type": "array", "items": {"enum": list(rl.WATERBODIES)}}}},
                           "feature": {"type": "object", "properties": {"featureId": {"enum": [k for k, v in ft.REGISTRY.items() if v["availability"] != "AREA" and k != "spawnWindow"]}, "states": {"type": "array", "items": {"type": "string"}}}},
                           "response": {"enum": list(rl.RESPONSES)},
                           "habitat": {"type": "object", "properties": {"habitatClass": {"enum": list(ft.HABITAT_CLASSES)}, "direction": {"enum": list(rl.DIRECTIONS)}, "depthClass": {"enum": list(ft.DEPTH_CLASSES)}}},
                           "requires": {"type": "array", "items": {"type": "object", "properties": {"featureId": {"type": "string"}, "states": {"type": "array"}}}},
                           "phenology": {"type": "object", "properties": {"event": {"const": "spawn"}, "tempC": {"type": "object", "required": ["min", "max"], "properties": {"min": {"type": "number"}, "max": {"type": "number"}}}}},
                           "conflicts": {"type": "array", "items": {"type": "string"}}, "review": {"type": "object", "properties": {"reviewer": {"type": "string"}, "date": {"type": "string"}}},
                           "evidence": {"type": "array", "minItems": 1, "items": evidence_schema()}}}
    band = {"$schema": S, "title": "Biological response band (Biological -> Intelligence)", "type": "object",
            "description": "Support for the fish being present and findable in shootable habitat under the feature state. Never a fishing score.",
            "required": ["speciesId", "featureId", "featureState", "response", "sourceVersion"],
            "properties": {"speciesId": {"type": "string"}, "featureId": {"type": "string"}, "featureState": {"type": "string"},
                           "response": {"enum": list(rl.RESPONSE_OR_UNKNOWN)}, "confidence": {"enum": list(rl.CONFIDENCE)}, "conflict": {"type": "boolean"},
                           "evidenceBasis": {"type": "object", "properties": {"ruleIds": {"type": "array"}, "independentStreams": {"type": "integer"}, "directness": {"type": "array"}}},
                           "regionApplicability": {"type": "object"}, "seasonApplicability": {"type": "object"},
                           "transferability": {"enum": list(rl.TRANSFER)}, "behavior": {"type": "array"}, "reason": {"type": "string"},
                           "sourceVersion": {"type": "object", "properties": {"rulesVersion": {"type": "string"}, "featuresVersion": {"type": "string"}, "stateVersion": {"type": "string"}}}}}
    pred = {"$schema": S, "title": "Biological prediction (append-only log entry)", "type": "object", "required": list(vl.PRED_FIELDS),
            "properties": {"lakeId": {"type": "string"}, "speciesId": {"type": "string"}, "predictedAt": {"type": "string"},
                           "ruleRefs": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["ruleId", "ruleVersion", "ruleSha256"]}},
                           "seasonState": {"type": "object"}, "expected": {"type": "object", "properties": {k: {} for k in vl.EXPECTED_KEYS}, "additionalProperties": False},
                           "confidence": {"enum": list(rl.CONFIDENCE) + ["UNKNOWN"]}, "evidenceBasis": {"type": "object"}}}
    obs = {"$schema": S, "title": "Structured Sector biological observation", "type": "object", "required": list(vl.OBS_REQUIRED),
           "properties": {"observationId": {"type": "string"}, "tripId": {"type": "string", "description": "observations of one trip are ONE evidence stream"},
                          "observerId": {"type": "string", "description": "pseudonymous; no contact details"}, "lakeId": {"type": "string"}, "observedAt": {"type": "string"},
                          "speciesId": {"type": "string"}, "speciesGroup": {"enum": list(vl.SPECIES_GROUPS)}, "speciesIdConfidence": {"enum": list(vl.SPECIES_ID_CONFIDENCE)},
                          "encountered": {"type": "boolean"}, "count": {"type": "integer", "minimum": 0}, "effortMinutes": {"type": "number", "minimum": 1, "maximum": 720},
                          "zone": {"enum": list(ft.HABITAT_CLASSES) + ["openWater", "unknown"]}, "depthClass": {"enum": list(ft.DEPTH_CLASSES)},
                          "vegetation": {"enum": list(vl.VEG)}, "waterTempF": {"type": "number"}, "clarityBand": {"enum": list(ft.REGISTRY["clarityBand"]["states"])},
                          "windBand": {"enum": list(vl.WIND_BANDS)}, "levelContext": {"enum": list(vl.LEVEL_CONTEXT)},
                          "spawnBehaviorObserved": {"enum": [True, False, "UNKNOWN"]}, "notes": {"type": "string", "maxLength": 280},
                          "observerConfidence": {"enum": list(vl.OBSERVER_CONF)}}}
    return {"condition_features.json": contract, "biological_rule.schema.json": rule, "response_band.schema.json": band,
            "prediction.schema.json": pred, "observation.schema.json": obs}


def main():
    check = "--check" in sys.argv
    bad = 0
    for name, doc in build().items():
        path = os.path.join(ROOT, "schemas", name)
        text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
        if check:
            if not os.path.exists(path) or open(path).read() != text:
                print("OUT OF DATE:", name)
                bad += 1
        else:
            open(path, "w").write(text)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
