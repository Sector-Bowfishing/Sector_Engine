# Sector Intelligence: pilot evidence layer (`intelligence-eval-v2`, contract `intelligence-evidence-v1`)

**Status:** INTERNAL, NON-CUSTOMER, PILOT. 2026-10-13. Code: `jobs/sector-intelligence-brain/evidence.py` (pure, stdlib, no I/O), wired into `evaluation.py`. Tests: `tests/test_evidence.py`.
**What it is not:** not a score, not a customer feature, not a replacement for the Engine Conditions Score, not a change to `sector-intelligence-score-v1`, not validation. `customerPath.consumesThisEvaluation` stays `false`; nothing was deployed or published by this change.
**Why it exists:** the research campaign (`docs/research/intelligence/`, branch `docs/intelligence-deep-research`) found the production aggregator lets missing data raise a score, reports confidence detached from evidence, and combines species-blind. This layer makes the *internal* evaluation honest first.

## 1. What an evaluation now carries (`evaluation.evidence`)
```
evidence: { contractVersion, checkpoint ("NOW" | "+Nh"), decisionLevel: "LAKE", zones: "none: ...",
            gates: { status: NOT_EVALUATED | EVALUATED, hits[], reason },
            factors: { factorId: FactorEvidence },
            species: { speciesId: SpeciesAssessment },
            summary: { factorCount, knownFactors, unknownFactors[], staleFactors[], weakestKnownFactor,
                       speciesTotal, speciesByBandStatus, speciesByRating, ratingsIssued, customerScore } }
```
All v1 evaluation fields (`inputs`, `drivers`, `limitingFactors`, `inputsUsed`, `provenance`, `freshness`, `customerPath`, …) are unchanged.

### FactorEvidence (one per lake-level factor)
`factorId · name · source{brainId, slot, brainVersion, modelVersion, generatedAt} · status (PUBLISHED|STALE|DEGRADED|NOT_PUBLISHED) · known · value+unit (only when known) · kind (measured|observed|analysis|modeled|forecast|proxy|…) · support (LAKE in the pilot) · ageHours · stale · evidenceStale · leadHours · confidence · confidenceBasis[] · brainConfidence? · readiness? · carried? · reason · affectedRating · affectedRatingFor[]`.
- `state: "UNKNOWN"` is present for every factor that is not known. A known factor carries `ordinal: "PER_SPECIES"`: FAVORABLE…BLOCKING exist only against a species band.
- Factors: `lakeLevelTrend` (Lake Brain), `waterTempF` (Water Temp), `clarityFt` (Water Clarity), `windSustainedMph` (Wind). Values are restated from the published state, never recomputed.
- Always-UNKNOWN factors with a stated reason: `windExposure` (Wind publishes bank-scale exposure only as a storage file, the RTDB summary is lake-wide), `effectiveDepthFt` (no Depth Brain), `vegetation` (no Vegetation Brain). Even if a `depth` or `vegetation` object appears in a snapshot it is **not read** until a ratified shape exists (tested).

### SpeciesAssessment (one per species in Lake Brain presence)
`presence{state,confidence} · bandStatus (SUPPORTED|UNSUPPORTED|NOT_ASSESSED) · rating · confidence · confidenceBasis[] · weakestConfidenceFactor{factorId,level,reason} · factorStates · explanation{positive[],limiting[],blocking[],unknown[],stale[],counts} · caveats[] · affectedRating[] · bestCaseIfUnknownResolved?`
- `NOT_ASSESSED`: presence is historical / failed / unknown / not in the Lake Brain vocabulary.
- `UNSUPPORTED`: no approved, schema-valid Biological `responseBands` → rating `UNRANKED`, confidence `INSUFFICIENT`, no thresholds applied.
- `SUPPORTED`: ordinal states from the Biological band, rated by the rules below.

## 2. Rules (all tested)
| Rule | Statement |
|---|---|
| E1 | **UNKNOWN never improves a rating.** Replacing any known state, including BLOCKING, with UNKNOWN keeps or lowers the rating. An unknown deciding factor gives `UNRANKED`, which sits **below** `POOR`; an unknown supporting factor is treated as unfavourable. Exhaustively tested over every state vector, confidence level and gate status. |
| E2 | A known BLOCKING deciding factor ⇒ `POOR`; a gate hit ⇒ `NOT_TONIGHT`. |
| E3 | `START_HERE` needs every deciding factor known and none limiting, confidence ≥ MEDIUM and safety gates evaluated. The pilot has no weather/fog/warning/legal source, so gates are `NOT_EVALUATED` and **no species can reach the top rating**. |
| E4 | Confidence = the weakest deciding factor. No sum, mean, agreement bonus, or fixed countdown. |
| E5 | Stale evidence (or a Brain-reported `evidenceStale`) lowers a factor one level; lake-level support used for an area decision caps at MEDIUM; Brain readiness DEGRADED/BLOCKED caps at LOW; the Brain's own confidence label can only cap. |
| E6 | Beyond a Brain's forecast horizon a factor is UNKNOWN. The current value is shown under `carried` for reference and is never counted as forecast. Pilot evaluations run at `NOW`. |
| E7 | Confidence is also capped by presence evidence (`reported`/`inRangeUnconfirmed` ⇒ LOW, `stocked` ⇒ MEDIUM) and by the band's evidence tier (RESEARCH ⇒ LOW, REVIEWED ⇒ MEDIUM, VALIDATED ⇒ HIGH). |

Ladder: `NOT_TONIGHT < UNRANKED < POOR < LOW_PRIORITY < WORTH_A_LOOK < START_HERE`. No numeric score, weights, ML or generated text; explanation lines are templates over factor records.

*Difference from the research prototype:* the prototype made an unknown factor behave like LIMITING; this implementation is stricter (UNRANKED below POOR) so that even a known BLOCKING factor cannot improve by becoming unknown, as required for the pilot.

## 3. The Biological dependency (consumer expectation, not ratified)
Intelligence rates a species only when `species/{id}.responseBands` is an object with `status: "APPROVED"`, `evidenceTier ∈ {RESEARCH, REVIEWED, VALIDATED}`, non-empty `decidingFactors`, optional `supportingFactors`, and a `bands` entry for each, whose `unit` matches the factor and whose numeric cuts ascend (`[{lt, state}…]` + `else`) or whose categorical map uses valid states. Anything else ⇒ UNSUPPORTED with the first reasons listed. **The field name and shape are a proposal from the consumer side; the Biological campaign decides the real contract**, after which `parse_bands` is adapted. No Intelligence-authored bands exist anywhere in the code; test bands are labelled fixtures.

## 4. Depth, Vegetation, Wind
Placeholders exist in the factor registry so the schema is ready; both are UNKNOWN by construction until a Depth/Vegetation Brain publishes a ratified state. Intelligence reads no bathymetry, GLOBathy, NWI or `grassPct`. Wind exposure at bank scale is recorded as a dependency gap; Intelligence computes no wind or fetch.

## 5. Current pilot behaviour (fixture shaped like the 2026-10-12 live states)
A pilot lake whose Brain states look like the 2026-10-12 ones (the unit-test fixture; nothing was read live, and Hartwell has no wind state) shows: 4 known factors (level trend, water temp, clarity, wind; modeled/analysis ⇒ MEDIUM each), 3 unknown (wind exposure, depth, vegetation), every present species `UNSUPPORTED`/`UNRANKED`/`INSUFFICIENT`, `ratingsIssued: 0`, gates `NOT_EVALUATED`. Stale Lake/Water Temp inputs (unscheduled Brains) appear in `staleFactors` and cap confidence at LOW. This is the honest result today: the machinery works, the biological knowledge it needs does not yet exist in machine-readable form.

## 6. Publication and size
The block is part of the evaluation object the publisher already writes to `/lakes/{k}/states/intelligence` and `/snapshots/{k}/latest/sectorIntelligence` (≈12.5 KB per lake for a 3-species fixture vs ≈5.8 KB before). **This change publishes nothing**; bumping `EVAL_VERSION` changes `inputs_fingerprint`, so the next publisher run (whenever it is approved) will republish the pilot lakes once. The official score and rubric are untouched; the score evaluator does not read `evidence`.

## 7. Support for later validation (not started, nothing fabricated)
The block stores exactly what a blind expert-ranking or paired-visit log needs to join to: factor values with source/age, band version and tier, rating, confidence and its basis, all at an evaluation `generatedAt`. Outcome data, validation status and any `PARTIAL` claim remain absent (`NOT_VALIDATED`).
