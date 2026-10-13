# Biological → Intelligence response-band contract

**Owner:** Biological Brain. **Version:** `biological-response-bands-v1`. **Status:** implemented and tested on `feat/biological-brain-adoption`; **not published** (needs Michael's approval); Intelligence has **not** been modified. Code: `jobs/biological-brain/bands.py`, `rules.py`, `features.py`. Schemas: `schemas/species_response_bands.schema.json` (published object), `schemas/response_band.schema.json` (one evaluated band), `schemas/condition_features.json` (feature definitions), all generated from code.

**Rule: NO APPROVED BAND = UNSUPPORTED / UNKNOWN.** Biological never publishes an approved band without a recorded reviewer, and Intelligence must never invent one.

## 1. Two shapes, one meaning
| Shape | Where | Use |
|---|---|---|
| **Static** `species/{id}.responseBands` | Brain RTDB species node (when the bundle carries validated rules) | what a species tends to do under which feature states; for review and display |
| **Evaluated** `species[].responses[]` | per-lake Biological State (`PILOT_INTERNAL` today; `/lakes/{k}/states/biology` only after approval) | the band for THIS lake NOW, already evaluated against the specialist Brains' inputs |

**Recommendation: Intelligence consumes the evaluated shape.** The meaning of `warmRise`, a temperature band or `spawnWindow` is Biological's; re-evaluating the static bands in Intelligence would re-implement species science and let the two drift.

## 2. Static object (`responseBands`)
`contractVersion, speciesId, status (PROPOSED|APPROVED|WITHDRAWN), evidenceTier (RESEARCH|REVIEWED; never VALIDATED), rulesVersion, featuresVersion, generatedAt, coveredFeatures[], bands[], habitatPreferences[], spawn[], limitations[]`.

Each `bands[]` entry: `bandId, featureId, featureStates[], behavior, band (FAVORABLE|WORKABLE|LIMITING|BLOCKING|UNKNOWN), conflict, conflictsWith[], context{months|"all", regions[], waterbodyTypes[], lifeStage}, confidence (LOW|MEDIUM|HIGH|null), confidenceBasis{independentStreams, confidenceCap}, evidenceKind (DIRECT|INFERRED|MIXED), ruleVersion{ruleIds, versions}, transferability (UNTESTED|PARTIAL|TRANSFERS), sourceCount, validationTier (NONE|T1|T2|T3|T4), reason, limitations[]`.

* `status` is `PROPOSED` unless **every** contributing rule is `APPROVED` (a recorded reviewer). Today all are `PROPOSED`.
* `band: UNKNOWN` appears only as a **conflict band** (overlapping rules disagree) and carries no confidence.
* A feature absent from `bands` is **UNKNOWN** for that species. Species with no usable rule have **no** `responseBands` object.
* `confidence` is capped by independent evidence streams (1 → LOW, 2 → MEDIUM, ≥3 → HIGH only if the rule transfers to the Southeast). One cohort reported in several papers is one stream.
* Free-text rule statements and evidence text are not carried; `reason` is templated, `limitations` come from structured fields.
* `habitatPreferences[]` and `spawn[]` are area-level / phenology knowledge (habitat class, direction, optional depth class, `requires`; spawn temperature as a **range**, never an optimum).

## 3. Evaluated band (per lake, per species, per feature)
`speciesId, featureId, featureState, response, confidence, evidenceBasis{ruleIds, independentStreams, directness}, regionApplicability, seasonApplicability, transferability, behavior, reason, conflict?` plus state-level `provenance{rulesVersion, featuresVersion, stateVersion}`. Anything unknown yields `response: UNKNOWN` with the reason (unknown input, no rule for that state, or a named conflict). Degraded input lowers confidence one level.

Band semantics: support for the fish being **present and findable in shootable habitat** under that feature state. It is not a fishing score and not a probability.

## 4. Differences from Intelligence's provisional parser (`evidence.parse_bands`, branch `feat/intelligence-evidence-layer`, read-only review)
| Provisional parser expects | Biological contract | Adaptation needed (later, not made) |
|---|---|---|
| `responseBands.status == "APPROVED"` | `PROPOSED` today; `APPROVED` only with a reviewer on every rule | none: Intelligence's UNSUPPORTED path is the intended behaviour until approval |
| `evidenceTier ∈ {RESEARCH, REVIEWED, VALIDATED}` | `RESEARCH` or `REVIEWED`; `VALIDATED` never asserted by the compiler | none; E7 tier→confidence cap matches |
| `decidingFactors[]` / `supportingFactors[]` chosen by the Biological node | **Not published.** Which factor "decides" a night is not an evidence-backed species fact; Biological states only what is supported and how confidently | decide in the reconciliation session: derive from band confidence, or define a Biological `decisionRole` only where evidence supports it. Do not invent one |
| `bands{factorId: …}` dict keyed by **Intelligence factor** (`waterTempF`, `clarityFt`, `lakeLevelTrend`, `windSustainedMph`, …) with `unit`, numeric cuts `{lt, state}` + `else`, or `categorical` map | `bands[]` **list** keyed by **Biological feature** (`waterTempBand` in °C classes, `stageTrend`, `warmRise`, `clarityBand`, `daypart`, …) with feature **states** and a `context` | map only where lossless: `waterTempBand` edges 10/15/18/21/26/30 °C ↔ `waterTempF` cuts 50/59/64.4/69.8/78.8/86; `stageTrend` ↔ `lakeLevelTrend` (same vocabulary); `clarityBand` ↔ `clarityFt` (1.3/3.3 ft). Derived features (`warmRise`, `coldRise`, crossings, `spawnWindow`, `rapidDischargeIncrease`) have **no** Intelligence factor and must come from Biological's evaluation |
| ordinal states `BLOCKING…FAVORABLE` only | adds `UNKNOWN` (conflict bands) | treat as unknown (`None`), never as a rating input |
| no seasonal/regional applicability | `context.months/regions/waterbodyTypes/lifeStage` per band | pass the lake's month/region/waterbody; a band that does not apply must not be used |
| no per-band confidence | `confidence`, `confidenceBasis`, `transferability`, `evidenceKind`, `sourceCount`, `validationTier`, `limitations` | feed `confidence` into the weakest-link confidence (E4); never raise it |
| one `version` | `ruleVersion{ruleIds, versions}` per band and `rulesVersion` per object | record in the Intelligence provenance |

## 5. Unsupported behaviour (stated, not hidden)
* No `BLOCKING` band exists in any current rule; Biological has no evidence of a condition that excludes a researched species outright.
* `rapidDischargeIncrease` (strongest cross-species signal) is **always UNKNOWN**: no Brain publishes tributary discharge change. `stageTrend` is the lake pool trend, a proxy for river stage.
* Night behaviour is supported for few species and is LOW confidence; several species have none.
* Area-level classes (backwater, tailwater, vegetated shallows, flooded vegetation) need Depth/Vegetation/Lake map layers; until those publish they are knowledge for Intelligence to apply per area, not lake-level bands.
* No band has any T2-T4 validation; every `validationTier` is `T1` (literature).
* Species outside the Lake Brain's assessed set, and species with only DRAFT rules, have **no** object: Intelligence must show them as NOT_ASSESSED / UNSUPPORTED, never rated.

## 6. Verified compatibility check (read-only; Intelligence untouched)
On 2026-10-14 the candidate's published species nodes were passed through the unmodified `parse_bands` from `feat/intelligence-evidence-layer` (extracted to a scratch directory):
* Species with `responseBands` (status `PROPOSED`) → **UNSUPPORTED** ("status is 'PROPOSED', not APPROVED"; "decidingFactors missing or empty"). No crash, no rating.
* Species with no object (e.g. the unresolved tilapia row) → **UNSUPPORTED** ("no responseBands published").
* A band **forced** to `APPROVED`/`REVIEWED` is still **rejected** ("decidingFactors missing or empty"): the provisional parser cannot misread the Biological shape as one of its own. This is the desired failure mode until the reconciliation session adapts one side.
So publishing the Biological `responseBands` cannot cause Intelligence to invent a rating.
