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
import bands as bd           # noqa: E402
import species_profile as spf      # noqa: E402

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
                           "confidence": {"enum": list(rl.CONFIDENCE) + ["UNKNOWN"]}, "evidenceBasis": {"type": "object"},
                           **{k: {} for k in vl.PRED_OPTIONAL}}, "description": "optional context fields are frozen with the prediction so it can be judged without hindsight"}
    obs = {"$schema": S, "title": "Structured Sector biological observation", "type": "object", "required": list(vl.OBS_REQUIRED),
           "properties": {"observationId": {"type": "string"}, "tripId": {"type": "string", "description": "observations of one trip are ONE evidence stream"},
                          "observerId": {"type": "string", "description": "pseudonymous; no contact details"}, "lakeId": {"type": "string"}, "observedAt": {"type": "string"},
                          "speciesId": {"type": "string"}, "speciesGroup": {"enum": list(vl.SPECIES_GROUPS)}, "speciesIdConfidence": {"enum": list(vl.SPECIES_ID_CONFIDENCE)},
                          "encountered": {"type": "boolean"}, "count": {"type": "integer", "minimum": 0}, "effortMinutes": {"type": "number", "minimum": 1, "maximum": 720},
                          "zone": {"enum": list(ft.HABITAT_CLASSES) + ["openWater", "unknown"]}, "depthClass": {"enum": list(ft.DEPTH_CLASSES)},
                          "vegetation": {"enum": list(vl.VEG)}, "waterTempF": {"type": "number"}, "clarityBand": {"enum": list(ft.REGISTRY["clarityBand"]["states"])},
                          "windBand": {"enum": list(vl.WIND_BANDS)}, "levelContext": {"enum": list(vl.LEVEL_CONTEXT)},
                          "shootableCount": {"type": "integer", "minimum": 0, "description": "shootable fish in this zone/trip; the validation outcome is shootable encounters per effort-hour"},
                          "spawnBehaviorObserved": {"enum": [True, False, "UNKNOWN"]}, "notes": {"type": "string", "maxLength": 280},
                          "observerConfidence": {"enum": list(vl.OBSERVER_CONF)}}}
    ctx = {"type": "object", "properties": {"months": {"oneOf": [{"const": "all"}, {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 12}}]},
                                            "regions": {"type": "array", "items": {"enum": list(rl.REGIONS)}}, "waterbodyTypes": {"type": "array", "items": {"enum": list(rl.WATERBODIES)}},
                                            "lifeStage": {"enum": list(rl.LIFE_STAGES)}}}
    common = {"context": ctx, "confidence": {"enum": list(rl.CONFIDENCE) + [None]}, "ruleVersion": {"type": "object", "required": ["ruleIds", "versions"]},
              "transferability": {"enum": list(rl.TRANSFER)}, "sourceCount": {"type": "integer", "minimum": 1}, "evidenceKind": {"enum": list(bd.EVIDENCE_KIND)},
              "confidenceBasis": {"type": "object", "required": ["independentStreams", "confidenceCap"]}, "validationTier": {"enum": list(bd.VALIDATION_TIER)},
              "reason": {"type": "string", "maxLength": bd.MAX_REASON}, "limitations": {"type": "array", "items": {"type": "string"}}}
    sp_bands = {"$schema": S, "title": "Biological species response bands (biological-response-bands-v1): the Biological-owned object under species/{id}.responseBands",
                "description": "Omitted when a species has no usable rule (=> UNSUPPORTED downstream). PROPOSED until every contributing rule is APPROVED. A feature absent from bands is UNKNOWN. The RTDB stores no empty arrays, so an absent bands/habitatPreferences/spawn means none.",
                "type": "object", "required": ["contractVersion", "speciesId", "status", "evidenceTier", "rulesVersion", "featuresVersion", "generatedAt"],
                "properties": {"contractVersion": {"const": bd.CONTRACT_VERSION}, "speciesId": {"type": "string"}, "status": {"enum": list(bd.BAND_STATUS)},
                               "evidenceTier": {"enum": ["RESEARCH", "REVIEWED"], "description": "VALIDATED is never asserted by the compiler"},
                               "rulesVersion": {"type": "string"}, "featuresVersion": {"type": "string"}, "generatedAt": {"type": "string"},
                               "coveredFeatures": {"type": "array", "items": {"type": "string"}},
                               "bands": {"type": "array", "items": {"type": "object", "required": ["bandId", "featureId", "featureStates", "band", "conflict", *common],
                                                                    "properties": {"bandId": {"type": "string"}, "featureId": {"type": "string"}, "featureStates": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                                                                                   "behavior": {"type": ["string", "null"]}, "band": {"enum": list(bd.BAND_VALUES)}, "conflict": {"type": "boolean"},
                                                                                   "conflictsWith": {"type": "array", "items": {"type": "string"}}, **common}}},
                               "habitatPreferences": {"type": "array", "items": {"type": "object", "properties": {"habitatClass": {"enum": list(ft.HABITAT_CLASSES)}, "direction": {"enum": list(rl.DIRECTIONS)},
                                                                                                                  "depthClass": {"enum": list(ft.DEPTH_CLASSES) + [None]}, "requires": {"type": "array"}, **common}}},
                               "spawn": {"type": "array", "items": {"type": "object", "properties": {"event": {"const": "spawn"}, "tempC": {"type": "object", "required": ["min", "max"]}, **common}}},
                               "limitations": {"type": "array", "items": {"type": "string"}}}}
    cov_cell = {"type": "object", "required": ["status", "completeness", "evidence", "note"], "properties": {"status": {"enum": list(spf.COVERAGE)}, "completeness": {"type": ["number", "null"], "minimum": 0, "maximum": 10, "description": "internal 0-10; null (or absent in RTDB) when status is UNKNOWN: UNKNOWN is never shown as 0"},
                                                                                                    "evidence": {"enum": ["NONE", "UNVERIFIED", "SINGLE_SOURCE", "MULTI_SOURCE", "RULE_TRANSFER"]}, "note": {"type": "string"}}}
    month = {"type": "object", "required": ["month", "season", "movementStates", "shallowLikelihood", "spawnState", "precision", "confidence", "regionalConfidence", "claimIds"],
             "properties": {"month": {"enum": list(spf.MONTHS)}, "season": {"enum": ["WINTER", "SPRING", "SUMMER", "FALL"]}, "movementStates": {"type": "array", "minItems": 1, "items": {"enum": list(spf.MOVEMENT_STATES)}},
                            "shallowLikelihood": {"enum": list(spf.SHALLOW)}, "typicalDepthBehavior": {"type": "string"}, "favoredHabitat": {"type": "array", "items": {"enum": list(ft.HABITAT_CLASSES)}},
                            "spawnState": {"enum": list(spf.SPAWN_STATE)}, "temperatureContext": {"type": "string"}, "hydrologyContext": {"type": "string"}, "dayNightContext": {"type": "string"},
                            "bowfisherMeaning": {"type": "string"}, "confidence": {"enum": list(spf.CONF)}, "regionalConfidence": {"enum": list(spf.CONF)},
                            "precision": {"enum": list(spf.PRECISION), "description": "MONTH = month-bounded evidence; SEASONAL = season-level statement shown across its months; INFERRED = adjacent to a known window; UNKNOWN stays unknown"},
                            "claimIds": {"type": "array", "items": {"type": "string"}, "description": "keys of evidenceSummary.claims"}}}
    section = {"type": "object", "required": ["coverage", "statements", "openQuestions"], "properties": {"coverage": {"enum": list(spf.COVERAGE)}, "completeness": {"type": ["number", "null"]},
               "statements": {"type": "array", "items": {"type": "object", "required": ["label", "text", "claimIds"], "properties": {"label": {"type": "string"}, "text": {"type": "string"}, "confidence": {"enum": list(spf.CONF)}, "regionalConfidence": {"enum": list(spf.CONF)}, "claimIds": {"type": "array", "items": {"type": "string"}}}}},
               "openQuestions": {"type": "array", "items": {"type": "string"}, "description": "sub-questions with no recorded answer: shown as UNKNOWN, never filled"}, "rules": {"type": "array", "items": {"type": "string"}}}}
    profile_v1 = {"$schema": S, "title": spf.CONTRACT + ": a deterministic, self-describing species study guide (Ops renders it; Biological owns the interpretation)",
                  "type": "object", "required": ["contract", "generatedFrom", "identity", "summary", "yearlyMovement", "seasonalGuide", *spf.SECTIONS, "bowfisherGuide", "knowledgeCoverage", "knowledgeGapMatrix", "knowledgeGaps",
                                                   "researchPriorities", "rulesSummary", "evidenceSummary", "reviewSummary", "validationSummary"],
                  "properties": {"contract": {"const": spf.CONTRACT}, "generatedFrom": {"type": "object"},
                                 "identity": {"type": "object", "required": ["speciesId", "sectorLabel", "role", "habitatClass", "canonical"], "properties": {"speciesId": {"type": "string"}, "sectorLabel": {"type": "string", "description": "the existing customer label; never renamed"}, "scientificName": {"type": ["string", "null"]},
                                              "role": {"enum": ["TARGET", "SECONDARY", "KNOWLEDGE_ONLY"]}, "targetTier": {"enum": ["TARGET", "SECONDARY", "KNOWLEDGE_ONLY"]}, "habitatClass": {"enum": ["FRESHWATER", "SALTWATER"]}, "habitatFlag": {"enum": ["FRESHWATER_ONLY", "SALTWATER_ONLY", "BRACKISH_ESTUARINE", "ANADROMOUS", "CATADROMOUS", "CROSS_HABITAT"]}, "canonical": {"type": "boolean"}, "doNotResearch": {"type": "string"}}},
                                 "summary": {"type": "object", "required": ["knowledgeStatus", "generalConfidence", "regionalConfidence", "reviewStatus", "fieldValidationStatus", "ruleCount", "lastUpdated", "profileFreshness"],
                                             "properties": {"knowledgeStatus": {"enum": ["PROFILED", "THIN", "NOT_ASSESSED", "PROPOSED"]}, "bowfisherKnowledge": {"type": ["number", "null"], "description": "read-only diagnostic 0-10, NOT field validation"}, "speciesV2Score": {"type": ["number", "null"]},
                                                            "generalConfidence": {"enum": list(spf.CONF)}, "regionalConfidence": {"enum": list(spf.CONF)}, "reviewStatus": {"enum": ["UNREVIEWED", "ACCEPTED", "IN_PROGRESS"]}, "fieldValidationStatus": {"enum": list(spf.FIELD)},
                                                            "ruleCount": {"type": "object"}, "lastUpdated": {"type": ["string", "null"]}, "profileFreshness": {"enum": ["CURRENT_WITH_BUNDLE"]}, "strongest": {"type": "array"}, "weakest": {"type": "array"}}},
                                 "yearlyMovement": {"type": "object", "required": ["months", "conditionModifiers"], "properties": {"precisionNote": {"type": "string"}, "spawnWindowMonths": {"type": ["array", "null"], "items": {"enum": list(spf.MONTHS)}}, "spawnWindowBasis": {"enum": ["RULE", "CARD_TEXT", None]},
                                                    "months": {"type": "array", "minItems": 12, "maxItems": 12, "items": month}, "conditionModifiers": {"type": "array", "description": "base pattern vs modifiers: these change location WITHIN the base pattern; seasonality UNBOUNDED rules that are not YEAR_ROUND do not fire"},
                                                    "unboundedSeasonalModifiers": {"type": "array", "items": {"type": "string"}}, "evidenceConflicts": {"type": ["array", "null"]}}},
                                 "seasonalGuide": {"type": "object"}, **{k: section for k in spf.SECTIONS}, "bowfisherGuide": {"type": "object"},
                                 "knowledgeCoverage": {"type": "object", "required": list(spf.CATEGORIES), "properties": {c: cov_cell for c in spf.CATEGORIES}},
                                 "knowledgeGapMatrix": {"type": "object", "required": list(spf.CATEGORIES)}, "knowledgeGaps": {"type": "array", "items": {"type": "object", "required": ["category", "coverage", "researchPriority", "ifWeLearnThis", "researchStatus"],
                                                    "properties": {"researchPriority": {"enum": list(spf.PRIORITY)}, "researchStatus": {"const": "RESEARCH_NOT_AUTHORIZED"}}}},
                                 "researchPriorities": {"type": "object"}, "rulesSummary": {"type": "array", "items": {"type": "object", "required": ["ruleId", "when", "expects", "bowfisherMeaning", "status", "review", "field", "seasonality", "seasonReview", "fires"],
                                                    "properties": {"review": {"enum": list(spf.REVIEW)}, "field": {"enum": list(spf.FIELD)}, "status": {"enum": list(rl.STATUSES)}, "seasonality": {"enum": ["BOUNDED", "UNBOUNDED"]}, "seasonReview": {"enum": ["BOUNDED", "YEAR_ROUND", "NEEDS_REVIEW", "NOT_ESTABLISHED"]}}}},
                                 "evidenceSummary": {"type": "object", "required": ["sourceCount", "inspected", "claims", "sources"]}, "reviewSummary": {"type": "object"}, "validationSummary": {"type": "object", "properties": {"status": {"enum": list(spf.FIELD)}}}},
                  "description": "RTDB drops null and empty values: an absent field means UNKNOWN / not applicable. Per-lake species presence never appears here (Lake Brain owns it); current conditions are a separate payload (biological-movement-outlook-v1)."}
    return {"species_response_bands.schema.json": sp_bands, "condition_features.json": contract, "biological_rule.schema.json": rule, "response_band.schema.json": band,
            "prediction.schema.json": pred, "observation.schema.json": obs, "biological_species_profile_v1.schema.json": profile_v1}


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
