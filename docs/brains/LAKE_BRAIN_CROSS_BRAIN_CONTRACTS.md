# Lake Brain: cross-Brain contracts (what Lake Brain actually supplies to Intelligence, Depth and Vegetation)

Interface document. It specifies what the **Lake Brain** supplies today and what it could supply, field by field, grounded in what the Engine publishes now. It changes no code, no RTDB path and no other Brain's branch. Proposals are labelled **PROPOSAL** with a cost and are not implemented.

Principles (unchanged from `LAKE_BRAIN_INTEGRATION.md`):
- **Lake Brain owns lake-level facts:** water level, its change, its position against the operator's levels and against the lake's own history, flood-pool state, source authority and freshness. It does not own depth (Depth Brain computes effective depth; there is no bathymetry in Lake Brain), vegetation (Vegetation Brain), clarity, temperature, wind, species knowledge, or what fish do about the level.
- **Consumers restate and combine; they never recompute lake science.** Intelligence takes `trendState` as published, Depth takes `currentElevationFt` as published, Vegetation takes `differenceFromNormalPoolFt` and `change` as published.
- **Absent is unknown.** An unknown value is not written, never defaulted.

Written 2026-10-13. Evidence: live read-only reads of the Brain RTDB (`sector-brain`) for the five pilot lakes (`/lakes/{k}/states/lake`, `/lakes/{k}/brain`, `/snapshots/{k}/latest/lakeState`, `/lakeFleet`, `/brains/lake-brain`, `/validation/lake-brain`); the Swift contract (`Sources/SectorEngine/LakeBrain/LakeBrainContract.swift`, `LakeLevelFeedsFleet.swift`, `LakeBrainProfiles.swift`); and read-only looks at the other Brains' branches for field names (`Sector_Engine-depth-adoption` `docs/brains/depth/DEPTH_CROSS_BRAIN_CONTRACTS.md`; `Sector_Engine-intelligence-adoption` `jobs/sector-intelligence-brain/evidence.py`, `evaluation.py`, `docs/brains/SECTOR_INTELLIGENCE_EVIDENCE_LAYER.md`; `Sector_Engine-intelligence-research` `docs/research/intelligence/INTELLIGENCE_REQUIRED_UPSTREAM_CONTRACTS.md`; `Sector_Engine-vegetation-research` `docs/research/vegetation-brain/VEGETATION_LEVEL_DEPTH_INTERACTION.md`, `VEGETATION_CROSS_BRAIN_OPPORTUNITIES.md`).

## 1. What is published today

| Fact | Value |
|---|---|
| Lakes with a published lake state / profile | **5** (Guntersville, Wheeler, Wilson, Pickwick, Lake Hartwell). `/lakeFleet` has 621 rows; 5 carry `slots.lake` and `readiness.lake` (`BETA`); the other 616 have no lake slot, no `/lakes/{k}/brain`, no `/lakes/{k}/states/lake`. `/brains/lake-brain.fleetScope` is `pilots`. |
| Lake key | `lakeKey` = every run of non-alphanumeric characters replaced by one underscore (`docs/brains/conformance/lake_keys.json`): `Guntersville\|AL` is `Guntersville_AL`, `Lake Hartwell\|SC` is `Lake_Hartwell_SC`. |
| Brain / rules | `brainVersion 1.0.0`, `modelVersion lake-level-rules-v2`, `baselineMethod doy15-percentile-v2`, `bindingVersion bindings-2026-10-13.1`, state `schemaVersion 1`. |
| Validation | `/validation/lake-brain.status` = `NOT_VALIDATED`. Every state carries `provenance.validationRef: "/validation/lake-brain"`, and `provenance.readiness: "BETA"` (computed, not validated). |
| Copies | The snapshot node `/snapshots/{k}/latest/lakeState` is **identical** to `/lakes/{k}/states/lake` for all five (compared key for key on 2026-10-13). Read either; do not write either. |
| Consumers read | Intelligence reads `trendState` (factor `lakeLevelTrend`), `kind`, `freshness.stale`, `confidence`, `evidenceStale`, `readiness` (`evidence.py` `FACTOR_SPECS`; `evaluation.py` lines 54 to 105). Depth's contract reads `currentElevationFt, unit, datum, observationTime, sourceCapability, kind, differenceFromNormalPoolFt, freshness.stale`. Vegetation research names `poolAnomalyFt, poolTrend7dFt, basis, confidence, asOf`. |

Status words below: **PUBLISHED** (present for every published lake whenever the underlying evidence exists), **PARTIAL** (present for some pilots, or only a pointer or proxy exists), **NOT PUBLISHED**. "Path" is relative to `/lakes/{k}/states/lake/` unless it starts with `/`. Types are the JSON types seen live.

## 2. Contract to Sector Intelligence

Intelligence needs a dependable, restatable description of the lake's water level situation, with explicit unknowns.

| Needed | Field and exact path | Type / values | Status | Notes |
|---|---|---|---|---|
| Current level | `currentElevationFt` | number, ft (2 decimals); with `unit` string `"ft"`, `observationTime` ISO-8601 UTC string, `sourceAgeHours` number | **PUBLISHED** | Hartwell 649.37 ft at 2026-10-13T17:00Z. |
| Reference / guide difference | `differenceFromGuideFt` (number), `guideFt` (number, today's operator guide value); `differenceFromNormalPoolFt` (number) with `normalPoolRef` (string `engine-directory:fullPoolFt`) | numbers, ft | **PARTIAL** | Guide fields exist on 4 of 5 pilots (**Wilson publishes none**: TVA has a zone but no guide curve). `differenceFromNormalPoolFt` is present on all 5, but only where the directory full pool is an operator pool of acceptable confidence (never for natural-lake surfaces). The pool value itself is not in the state. |
| Trend | `trendState` | string enum `STABLE, RISING, FALLING, RISING_RAPIDLY, FALLING_RAPIDLY, UNKNOWN`; plus `change` object `{h1, h6, h24, d3, d7}` numbers, ft | **PUBLISHED** | Rule: 72 h mean rate against a 0.10 ft/day (regulated) or 0.05 (natural) floor; RAPID when 24 h change exceeds max(seasonal p95, 0.25 ft). `change.d7` appears only when 7 days of data exist. **The RAPID labels have a failed pre-registered criterion (H-C), see `LAKE_BRAIN_VALIDATION_READINESS.md`: Intelligence should not rank on RAPID.** Intelligence's fixture maps only RISING, STABLE, FALLING (`test_evidence.py`); `RISING_RAPIDLY` and `FALLING_RAPIDLY` have no mapping there. |
| Change rate | `rapidChangeThresholdFt` (number, effective RAPID threshold), `rateOfChangePercentile` (number 0 to 100) | numbers | **PUBLISHED** | Same caveat. |
| Seasonal anomaly | `historicalState` (string `NORMAL, UNUSUAL, VERY_UNUSUAL, INSUFFICIENT_HISTORY`), `seasonalPercentile` (number 0 to 100), `seasonalBand` `{p02,p10,p50,p90,p98,basisYears,windowDays,sampleCount}`, `historicalTier` (`NONE, PROVISIONAL, STANDARD, FULL`), `baselineStatus` (`SUFFICIENT, LIMITED, INSUFFICIENT, NONE`) | as listed | **PUBLISHED** | `VERY_UNUSUAL` is published only at tier `FULL` (at least 15 complete years). H-A and H-B passed narrowly, retrospectively. |
| Operating-zone state | `levelState` (string `BELOW_ZONE, IN_ZONE, ABOVE_ZONE, FLOOD_POOL, UNKNOWN`), `operatingZone` `{bottomFt, topFt, bottomLabel, topLabel, source}`, `operatorLevels[]` `{name, ft, source}` | | **PUBLISHED** | `operatorLevels` is present only for Hartwell today (generated bindings will fill it). Operator-defined, so correctness is binding plus level meaning, not statistics. |
| Flood state | `floodPoolState` | string `NORMAL, IN_FLOOD_POOL, UNKNOWN` | **PUBLISHED** | `UNKNOWN` is a valid answer: the four TVA pilots carry flag `provenance.qualityFlags: ["noOperatorFloodPoolThreshold"]`. 1 of 5 pilots has a known value (Hartwell). |
| Drought state | none | | **NOT PUBLISHED** | Operator drought levels exist only where an operator publishes them (Hartwell "Drought Level 1/2/3" appear as `operatorLevels` names). Across the 196 accepted-eligible lakes only Hartwell has them. No `droughtState` field exists. See P5. |
| Freshness | `freshness` `{generatedAt, sourceObservationAt, freshUntil, nextCheckAt, stale (bool), refreshReason}`; `sourceAgeHours`; `provenance.inputAgeHours` | | **PUBLISHED** | `stale` is true when the source is more than two cadences past due or the published state is older than 3 h. No `evidenceStale` field (Intelligence reads it, absent means false). |
| Confidence | none | | **NOT PUBLISHED** | Intelligence reads `confidence` (string `INSUFFICIENT, LOW, MEDIUM, HIGH`) and `engine.confidenceLabel` if a Brain publishes them (`build_factor`), and caps its own level with it. Lake Brain publishes only inputs to a confidence: `provenance.readiness`, `provenance.qualityFlags[]`, `baselineStatus`, `historicalTier`, `sourceCapability`. See P1. |
| Source authority | `sourceCapability` (state; string `DIRECT_OPERATOR_POOL, DIRECT_LAKE_GAUGE, NEARBY_GAUGE_PROXY, HISTORICAL_ONLY, MODELED, NO_SOURCE`) and `kind` (`OBSERVED, PROXY, UNAVAILABLE`); profile `/lakes/{k}/brain/sourceCapability.{level, bindingStatus, bindingVersion, primary{sourceId,provider,capability,cadenceMin,lagMin}, fallbacks[], proxyOnly, reviewedAt}`; `/lakes/{k}/brain/trustedSources/{slug}.{authority:"operator", status, lastObservationAt}` | | **PUBLISHED** | `bindingStatus` is `REVIEWED` for all five (hand-written pilots). A fallback in use is flagged `fallbackSource`. |
| Lake class | `/lakes/{k}/brain/characteristics/context/lakeClass/value` | string e.g. `R1_run_of_river_pool`, with sibling `quality` `"derived"` and `source` | **PUBLISHED** | Nine classes; derived from the research `lake_features.csv` (morphometry, operator family, residence time). Not a state field. |
| Regime | `/lakes/{k}/brain/characteristics/context/regime/value` | string `reservoir`, `regulated_natural`, `natural`, `MEGA` | **PUBLISHED** | |
| Region | `/lakes/{k}/brain/characteristics/context/region/value`; `/lakes/{k}/brain/identity/riverSystem` | string `SE`, `W`, ...; `Tennessee` | **PUBLISHED** | `riverSystem` also mirrored in `/lakeFleet/{k}/riverSystem`. |
| Chain position | `/lakes/{k}/brain/characteristics/context/chainPosition` `{chainId, upLakes, downLakes, nearestDown, quality, source}` | `chainId` string, counts numbers, `nearestDown` lake id | **PARTIAL** | Gives membership (`chain-CherokeeLake`) and counts, not an ordinal rank or the list of upstream lakes. Enough to group lakes into one-system clusters (`LAKE_BRAIN_REPRESENTATIVE_VALIDATION_FLEET.md`). |
| Shoreline context | `/lakes/{k}/brain/characteristics/context/shorelineSlope` `{medianSlopeDeg, shareUnder2Deg, runPerVerticalFtMedian, quality, source}` | numbers | **PARTIAL** (5 pilots) | Context only; see `LAKE_BRAIN_SHORELINE_SLOPE_NOTE.md`. |

What Intelligence should not do: recompute a percentile or band, infer drought from a number, treat `UNKNOWN` as normal, or treat `NOT_VALIDATED` BETA labels as validated. It should carry `provenance.readiness` and `/validation/lake-brain` into its confidence basis.

## 3. Contract to Depth Brain

Depth computes effective depth from a level shift against a reference; Lake Brain supplies the level and the reference, **not** a depth.

| Needed | Field and exact path | Type | Status | Notes |
|---|---|---|---|---|
| Pool elevation | `currentElevationFt`, `unit`, `observationTime`, `kind`, `sourceCapability` | number, strings | **PUBLISHED** | `kind` must be `OBSERVED`; a `PROXY` state carries no level fields Depth may use as pool elevation. |
| Reference / normal pool | `differenceFromNormalPoolFt` and `normalPoolRef` (pointer string `engine-directory:fullPoolFt`) | number, string | **PARTIAL** | The pool **value** is not published by Lake Brain; it lives in the Engine directory (`GET /lakes`, `fullPoolFt`, with `poolConfidence`, `poolBasis`). Depth can recover it as `currentElevationFt - differenceFromNormalPoolFt` to the precision of the two-decimal fields, which is an inference, not a published fact. |
| Datum | `datum` (string) on the state; `/lakes/{k}/brain/operatingPools/datum/value` | string e.g. `NGVD29` | **PARTIAL**: 1 of 5 | **Hartwell publishes `datum: "NGVD29"`; Guntersville, Wheeler, Wilson, Pickwick publish no `datum` at all.** This is the request Depth already filed (`DEPTH_CROSS_BRAIN_CONTRACTS.md` section 5: "stamp `datum` on every state, and publish the reference pool's datum with `normalPoolRef`"). No reference-pool datum is published for any lake. |
| Level delta | `change.{h1,h6,h24,d3,d7}`, `differenceFromNormalPoolFt`, `differenceFromGuideFt` | numbers | **PUBLISHED** | Depth flags `lakeBrainDeltaDisagrees` when its own shift and `differenceFromNormalPoolFt` differ by more than 0.15 ft at the same reference, so both numbers must stay on the same datum. |
| Freshness | `freshness.stale`, `freshness.freshUntil`, `sourceAgeHours`, `observationTime` | | **PUBLISHED** | |
| Confidence | none (see Intelligence) | | **NOT PUBLISHED** | Depth needs to know whether the pool value is high-confidence. The directory `poolConfidence` ("high", "low") is the only measure, and `differenceFromNormalPoolFt` is already withheld when low. |
| Source | `provenance.sources[]` `{sourceId, sourceType, lastObservationAt}`; `sourceCapability`; profile `sourceCapability.primary` | | **PUBLISHED** | |
| Bathymetry, depth, volume | none | | **NOT PUBLISHED, by design** | Lake Brain owns no depth. The shoreline slope proxy is morphology context, not depth truth. |

## 4. Contract to Vegetation Brain

Vegetation derives its own state from its own optics plus Lake Brain level context. It names the shape `levelContext: { poolAnomalyFt, poolTrend7dFt, basis, confidence, source:"lake-brain", asOf }`.

| Vegetation name | Lake Brain field | Status |
|---|---|---|
| current level | `currentElevationFt` | **PUBLISHED** |
| `poolAnomalyFt` | `differenceFromNormalPoolFt` (number, ft) | **PUBLISHED** (all 5; withheld where the pool is low-confidence or natural) |
| `poolTrend7dFt` | `change.d7` (number, ft) | **PARTIAL** (present when 7 days of data exist; Guntersville's live state had no `d7`; Hartwell's had 0.22) |
| `basis` | `normalPoolRef` (pointer string) | **PARTIAL** (names the directory field; no pool value, no pool basis such as `fullPool` or `naturalSurface`) |
| `confidence` | none | **NOT PUBLISHED** |
| `asOf` | `observationTime` (ISO-8601 string) | **PUBLISHED** |
| flooded shoreline context | `levelState` (`ABOVE_ZONE`, `FLOOD_POOL`), `floodPoolState`; `differenceFromNormalPoolFt` | **PARTIAL**: the level facts are published; the **flooded or dry shoreline area is not computed**, and per the Vegetation research it is a Vegetation-owned fact ("a 2 ft rise on a 1:50 slope moves the shoreline about 100 ft") |
| dry / exposed shoreline context | `levelState` `BELOW_ZONE`, negative `differenceFromNormalPoolFt` | **PARTIAL**: same |
| shoreline morphology | `/lakes/{k}/brain/characteristics/context/shorelineSlope` | **PARTIAL** (5 pilots; static; proxy quality) |
| seasonal hydrologic state | `historicalState`, `seasonalPercentile`, `seasonalBand`; `guideFt` and `differenceFromGuideFt` where an operator guide exists | **PUBLISHED**; there is **no** "phase" label (spring fill, summer drawdown) |
| lake-level support | `/lakes/{k}/brain/characteristics/context/grassPct` (satellite grass share, a **consume-only copy** of Water Clarity's snapshot) | **PUBLISHED, not Lake Brain's science**: Vegetation must not treat it as a Lake Brain fact |

Vegetation research also asks that lakes with a suspect polygon be refused (`VEGETATION_CROSS_BRAIN_OPPORTUNITIES.md`). That is the Lake Registry geometry contract's `pointFlag` (`LAKE_REGISTRY_GEOMETRY_CONTRACT.md`), not a Lake Brain field.

## 5. Gaps and proposals (PROPOSAL; none implemented; all additive, none changes a rule, a score, or a status)

Common cost for any new profile or state field: Swift change in `LakeBrainContract.swift` and the builder (`LakeBrainProfiles.swift` or `LakeLevelClassifier.swift`), conformance fixture and Swift tests, doc update, a `profileHash` change that republishes the pilots once (the planner handles this), no rules version bump because no rule changes. Rough size S = under half a day, M = about a day, L = several days or an external dependency.

| # | Proposal | Who benefits | Cost | Dependency / risk |
|---|---|---|---|---|
| P1 | `confidence` on the state: string `HIGH, MEDIUM, LOW, INSUFFICIENT`, plus `confidenceBasis[]` of short strings, derived only from existing facts (source capability and kind, staleness, fallback in use, `historicalTier`, directory `poolConfidence`, readiness). Name it `confidence` so Intelligence's existing reader (`build_factor`) picks it up with no change. | Intelligence, Depth, Vegetation | M | A mapping rule that must be written down and not tuned; it is a restatement, not new science. It must never read as validation. |
| P2 | `datum` on **every** state (string), from the binding's datum identification (rule R8 of `binding-review-v1` already requires a datum to be identified; the research candidates carry it in `alts[].datum`), carried through `bindings.proposed.v1.json` and the generated bindings; `unknown` stays absent. | Depth (filed), Vegetation | M | The generated table does not carry the datum today (only `datumOffsetFt`). Needs a one-time carry-through and a spot check; wrong datum is worse than none. |
| P3 | `referencePool` object on the state or profile: `{valueFt, datum, basis (fullPool or naturalSurface), confidence, source: "engine-directory:fullPoolFt"}`. Copies one number the Engine already has. | Depth (filed), Vegetation | S, but needs P2 for `datum` | Directory `poolConfidence` low ⇒ omit `valueFt`, as `differenceFromNormalPoolFt` already does. |
| P4 | `levelContext` convenience object for Vegetation: `{poolAnomalyFt, poolTrend7dFt, basis, confidence, asOf}` populated from existing fields. | Vegetation | S after P1 to P3 | Pure restatement; may be unnecessary if Vegetation maps the existing names (table in section 4). |
| P5 | Drought state: `droughtState` (`NORMAL, DROUGHT_L1, DROUGHT_L2, DROUGHT_L3, UNKNOWN`) **only** where the operator publishes named drought levels. | Intelligence, Vegetation | S | Evidence today: 1 lake of the 196 (Hartwell; Russell is outside). Low yield, not recommended until more operators publish drought levels. |
| P6 | `chainPosition.upstream[]` (lake ids, nearest first) and an ordinal `position`. | Intelligence (chain reasoning), validation clustering | S | Data exists (NLDI navigation in the research); the profile only stores counts. |
| P7 | Fleet scale: publish `states/lake` for the accepted fleet. All field availability above for the 616 non-pilot lakes is NOT PUBLISHED until their bindings are accepted and a fleet run happens. | all | L (human review, history backfill) | Gated by the binding review (`LAKE_BRAIN_PRODUCTION_READINESS_MATRIX.md`). |
| P8 | `evidenceStale` is not needed from Lake Brain (`freshness.stale` is read); no change. | | | |

Recommended order if Michael wants the cross-Brain surface improved before the fleet runs: P2 and P3 (Depth already asked), then P1 (one name serves all three consumers), then P6. P4, P5 and P8 are optional.

## 6. Ownership guardrails (restated so no consumer drifts)

- Depth reads `states/lake`; it never writes any Lake Brain path and never reads raw level feeds. Lake Brain never reads Depth.
- Intelligence reads the published state; it carries `UNKNOWN` as unknown and never "improves" an unknown lake. A `PROXY` state is trend only.
- Vegetation reads level facts; it computes its own flooded or dry shoreline and its own confidence, and passes through the weakest upstream confidence (including Lake Brain's pool confidence).
- None of the three may present a Lake Brain value as validated while `/validation/lake-brain` is `NOT_VALIDATED`.
- The shared snapshot and `/lakes/{k}/states/lake` are written only by the Lake Brain job; this document does not authorise any write to them.
