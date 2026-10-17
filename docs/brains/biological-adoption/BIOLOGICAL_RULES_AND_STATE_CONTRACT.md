# Biological Brain: machine rules, condition features, response bands, Biological State pilot and validation foundation

**Status:** IMPLEMENTED on `feat/biological-brain-adoption` (not merged, not deployed, nothing published). Extends `BIOLOGICAL_BRAIN_INTEGRATION.md` (species-knowledge side). Code: `jobs/biological-brain/`.

## 1. Ownership
| Question | Owner |
|---|---|
| Current water temperature, lake level/trend, clarity, wind, tributary discharge, vegetation, depth, habitat map | specialist Brains (Water Temp, Lake, Clarity, Wind, Depth, Vegetation) |
| What a researched species TENDS to do under a condition (and with what confidence) | **Biological Brain** |
| Combining the two into guidance for a bowfisher | Sector Intelligence |

Biological never fetches live environmental data. `bio_state.normalize_inputs` accepts already-published states; a missing, stale or unpublished input makes the dependent feature `UNKNOWN`. Nothing is substituted.

## 2. Where things live
| Artifact | Location | Visibility |
|---|---|---|
| Rule **content** for real species, evidence trace, source ledgers | private bundle (`gs://sector-biology-private/...`) and the private research store | private |
| Rule schema, feature registry, evaluator, state builder, validation log code, schemas, synthetic fixtures, tests | `jobs/biological-brain/` | public |
| Counts only (usable/draft rules per species, frozen rules, predictions logged) | Brain RTDB species/registry summaries | Ops allowlist |

A repository test fails if a rule JSON, a private path or a private release path appears in the public tree.

## 3. Rule (`biological-rule-v1`)
Kinds: `RESPONSE` (species response to a feature state), `HABITAT` (habitat-class preference, optionally gated by `requires` features), `PHENOLOGY` (spawn window: months + a temperature **range**). Status: `DRAFT` (excluded), `RECONCILED`, `APPROVED` (needs a recorded reviewer; nothing approves rules automatically), `RETIRED`.

The validator enforces evidence discipline, so a rule cannot claim more than its evidence carries:
* snippet-only / unopened / profile-carried sources never count (`counts` forced false);
* confidence is capped by **independent evidence streams** (one cohort or dataset = one stream however many papers report it): 1 → LOW, 2 → MEDIUM, ≥3 → HIGH only if the rule transfers to Southeast reservoirs;
* RECONCILED/APPROVED needs at least one counting source that was actually read;
* `TRANSFERS` needs a counting stream flagged `southeast`;
* no single optimum or peak temperature is allowed: spawn temperature is a range; applicability carries months, regions, waterbody types and life stage.

## 4. Condition features (`condition_features.json`, generated from code)
Registered only when evidence supports a species response, a specialist Brain can supply the input, and the meaning is documented.

| Feature | Meaning | Input owner | Availability |
|---|---|---|---|
| `waterTempBand` | `<10 / 10-15 / 15-18 / 18-21 / 21-26 / 26-30 / >=30` C, lower bound inclusive | Water Temp | published |
| `temperatureTrend` | warming / steady / cooling; noise floor ±1.0 F per 24 h | Water Temp | published |
| `temperatureCrossing15C/18C/20C` | line crossed within the last 24 h (only 24 h is knowable) | Water Temp | published |
| `stageTrend`, `risingStage`, `fallingStage` | Lake trend (24 h); a **proxy** for river stage (in pooled rivers stage and discharge decouple) | Lake | published |
| `warmRise` | rising stage AND water ≥ 15 C | Biological (Lake + Water Temp) | published |
| `coldRise` | rising stage AND water < 15 C | Biological | published |
| `rapidDischargeIncrease` | tributary/inflow discharge classified RISING_RAPIDLY | Lake (tributary hydrology) | **not published**: always `UNKNOWN` today |
| `clarityBand` | turbid <1.3 ft, moderate, clear ≥3.3 ft (engineering bands) | Clarity | published |
| `daypart` | day / twilight / night (solar elevation) | Engine calendar | published |
| `spawnWindow` | in-window / month-only / temp-only / outside, species-evaluated from the species phenology rule | Biological | published |
| habitat classes (`backwaterHabitat`, `tributaryMouth`, `tailwaterHabitat`, `shallowVegetatedHabitat`, `floodedVegetation`, `channelBorder`, `deepChannelPool`, `woodyCover`, ...) | per-area map layers | Lake / Depth / Vegetation | area-level: Intelligence applies them per area |

Temperature bands are coarse input classes anchored on recurring cue values; they are not biological optima.

## 5. Biological response bands (Biological → Intelligence)
`speciesId, featureId, featureState, response, confidence, evidenceBasis{ruleIds, independentStreams, directness}, regionApplicability, seasonApplicability, transferability, behavior, reason, sourceVersion`. Schema: `schemas/response_band.schema.json`.

`response` ∈ `FAVORABLE | WORKABLE | LIMITING | BLOCKING | UNKNOWN` meaning support for the fish being **present and findable in shootable habitat** under that feature state. It is not a fishing score. A band is emitted only where an applicable rule covers the feature; a feature input that is unknown yields `UNKNOWN` with the reason; a state no rule covers yields `UNKNOWN`; **rules that disagree yield `UNKNOWN` with the conflict named**, never a guess. Degraded input lowers confidence one level. `BLOCKING` is reserved for evidence of absence/inactivity and is not used by any current rule.

## 6. Biological State (internal pilot)
`bio_state.build_lake_state` → `{lakeId, status: PILOT_INTERNAL, context, inputs, features, species[{presence, evaluated, seasonState{calendarSeason, spawnWindow}, responses[], habitat[], nightMovementSupported, knowledge{maturity, rules}, unknowns[]}], unknowns, provenance{rulesVersion, featuresVersion}, validation NOT_VALIDATED, customerPath{consumed:false}}`. Species whose Lake-Brain presence state is outside the relevance policy (default: established, reported, stocked, inRangeUnconfirmed) are reported as `evaluated:false`, never silently dropped. The state is never written to `/lakes/{k}/states/biology` by this code.

Pilot lake: **Guntersville|AL** only (`run_state.py`).

## 7. Lifecycle is derived, never set
`capability.assess` returns `IN_PROGRESS` only if the bundle carries: valid rules with ≥1 usable rule; a hash-chained frozen-rule register covering every usable rule with matching hashes; and a pilot state that verifies against those rules/features and used ≥1 published specialist input. Anything missing or tampered returns `NOT_STARTED` with blockers listed. It can never return `LIVE` or `VALIDATED`. The canonical scorer then moves only because that capability exists.

## 8. Validation foundation (`validation_log.py`)
Local, append-only, hash-chained stores. Nothing is written to a cloud service.
1. **Frozen rule register**: a usable rule version is frozen before use; a frozen `(ruleId, ruleVersion)` can never change content (bump the version).
2. **Prediction log**: each prediction references frozen rule hashes (rejected if not frozen, hash mismatch, or frozen after the prediction time); no update/delete API; any rewrite or reordering breaks the chain.
3. **Observation store and schema**: structured Sector observations including **non-encounters with effort**, species-ID confidence, group-level IDs for unreliable species (buffalo, gar), vegetation/depth/zone/level/wind/clarity context, pseudonymous observer, no contact details; hash-chained.
4. **Evaluation**: joins predictions to later observations; group-level or earlier observations never score; one trip = one evidence stream; reports counts, hit rate and a naive-baseline lift; `claim` stays `INSUFFICIENT_EVIDENCE` below 30 independent trips and even above it is not a validation verdict (the VALIDATED criterion is a Michael/science decision).

Validation tiers are preserved (independent studies; regional holdout; state survey/tournament occurrence; structured Sector observations), with repeated reporting of one cohort counted once.
