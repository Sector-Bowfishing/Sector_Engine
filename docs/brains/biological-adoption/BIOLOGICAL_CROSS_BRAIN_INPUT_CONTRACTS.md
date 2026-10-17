# Biological Brain: input contracts with the specialist Brains

Biological **consumes** environmental truth and **converts** it into species-response knowledge. It calculates none of the environment and reads no weather. Everything a specialist does not publish, or publishes in an unrecognised, stale or implausible form, becomes `UNKNOWN` for the dependent feature (never a placeholder). Code: `jobs/biological-brain/contracts_in.py`, `features.py`, `bio_state.normalize_inputs`. Contract version `biological-input-contracts-v1`. **Provisional for Depth and Vegetation** until those Brains publish; shapes follow their own documents (Depth: `docs/brains/depth/DEPTH_STATE_CONTRACT.md`; Vegetation: its architecture proposal). Nothing here modifies another Brain.

| Ownership | Specialist owns | Biological owns | Intelligence |
|---|---|---|---|
| Temperature | temperature, trend | species temperature response (bands, spawn range) | matches the two |
| Lake level | pool level, trend, rate, operating context | species response to rising/falling water | |
| Depth | environmental depth | species depth preference | |
| Vegetation | actual plant state | species vegetation association | |
| Clarity | clarity state | species clarity tolerance | |

## 1. Water Temp (consumed today)
| Field | Use | Rule |
|---|---|---|
| `waterTemperature.currentTempF` | `waterTempBand`, `warmRise`, `spawnWindow`, crossings | outside 28-110 F is dropped (UNKNOWN); a model fault is not a fish signal |
| `waterTemperature.trend24hF` | `temperatureTrend` (noise floor ±1.0 F), `temperatureCrossing15C/18C/20C` | outside ±25 F dropped; only a **24 h** crossing is knowable from the published trend |
| `provenance.generatedAt`, `stale`, `observationType`, `provenance.readiness` | freshness / degraded handling | stale (> 36 h or flagged) → UNKNOWN; DEGRADED lowers band confidence one level |
Requests (not made): a multi-day temperature history (to know "crossed 15 C within 5 days"), and zone/surface-versus-depth temperature if it ever becomes evidence-relevant.

## 2. Lake (consumed today) and the pool-level / tributary-discharge distinction
| Field | Use |
|---|---|
| `lakeState.trendState` ∈ `STABLE, RISING, FALLING, RISING_RAPIDLY, FALLING_RAPIDLY` (anything else → UNKNOWN) | `stageTrend`, `risingStage`, `fallingStage`, `warmRise`, `coldRise` |
| `lakeState.levelState`, `floodPoolState` | carried for context; no rule consumes them yet |

**Lake pool trend is NOT tributary discharge.** In pool-controlled rivers stage and discharge decouple; several researched responses (silver, grass carp, gars, quillback) are to river/tributary discharge. Biological therefore defines `rapidDischargeIncrease` separately and it stays `UNKNOWN` until the input exists; a rising pool never populates it (tested). Rules that cite `risingStage` carry the limitation "lake pool trend is a proxy for river/tributary stage" in the published band.

### Exact upstream contract requested from Lake / Hydrology (not implemented anywhere)
Per lake, `lakeState.inflow` (or an `inflow` state beside it):
```
{ "gaugeId", "gaugeKind": "tributary"|"mainstem"|"tailwaterRelease", "observedAt",
  "dischargeCfs", "change24hPct", "trendState": same vocabulary as lakeState.trendState,
  "trendBasis": "lake-seasonal p95 of |24 h change|" (same method the pool trend uses),
  "poolOperations": { "mode": "runOfRiver"|"storage", "spillwayActive": bool?, "releaseCfs": number? },
  "sourceKind": "observed"|"modeled", "confidence", "stale" }
```
Biological would read `inflow.trendState` as `tributaryDischargeTrend` (already wired, vocabulary-checked) and `poolOperations` for spillway/tailwater rules (smallmouth buffalo, longnose gar, silver carp tailwater schools). Until published: UNKNOWN.


### The data already exists (Guntersville), but has no Brain publisher
The Clarity Fusion job `jobs/hydrology-hourly` writes, hourly, `gs://sector-lake-surface/hydrology/{lakeKey}/hourly/{date}.json` with `rows[hour].flows[arm] = {usgs?: …, nwm?: {cfs, validTime, reach}}` (measured USGS gauge where an arm has one, National Water Model analysis where it has a reach; both kept, never merged) and `rows[hour].tva` (Guntersville/Nickajack dam release, pool, tailwater; measured), with a 30-day backfill. It is a Clarity input, published to Cloud Storage, not a Brain state, and it covers one lake; when checked its newest row was about a day old.
Recommendation to the Lake/hydrology owner: publish a Brain-normalised `inflow` state from it (measured gauges preferred; NWM flagged `sourceKind: modeled`; `tva.releaseCfs` into `poolOperations.releaseCfs`), with the trend classified against a lake-seasonal baseline built from the existing hourly history (the 24 h change distribution; "rapid" = above its p95, exactly like the pool trend). Biological would then read `inflow.trendState` as `tributaryDischargeTrend` and lower band confidence one level for modeled input. **Biological must not read that bucket itself** (ownership), and until a Brain publishes the state `rapidDischargeIncrease` stays UNKNOWN.

## 3. Clarity (consumed today)
`waterClarity.clarityFt` → `clarityBand` (turbid < 1.3 ft, moderate, clear ≥ 3.3 ft; coarse engineering bands, not biological thresholds). Used only by the few rules with clarity evidence (carp tolerance, spotted gar preference).

## 4. Depth (consumption contract; validators and tests exist)
Input: `sector-brain-depth-state-v1` (`effectiveDepth{mode, shiftFt, uncertaintyFt, confidence, resolvable}`, `referenceZones{shareUnder3Ft, share3To6Ft, share6To10Ft}`, `effectiveZones{available, …(lo,hi) bounds}`, `freshness`, `provenance`).
* A state that is unrecognised, stale (> 48 h or self-flagged), or whose `effectiveDepth.mode` is `unknown` yields no shares.
* **Reference shares are used only when the level is not resolvably different from the reference pool** (otherwise they describe a different water level). `effectiveZones` bounds are used when `available: true`.
* `depth_availability(depth, depthClass)` returns a **lower and upper bound** on the share of surface in a Biological depth class (`LT_0_5M`, `M0_5_1_5`, `M1_5_3`, `GT_3M`), because those classes straddle the Depth Brain's 3 / 6 / 10 ft edges. It never interpolates a point and never invents a flat, drop-off or morphology.
* Today the Depth Brain publishes a level-shift, not zoned shares, and `effectiveZones` is unavailable for every lake: depth availability is `UNKNOWN` fleet-wide. That is the honest current answer.
Biological supplies species depth *preference* (spawn depths, shootable-zone use) as rule `depthClass`; matching it to a map zone is Intelligence's job.

## 5. Vegetation (consumption contract; validators and tests exist)
Input: one cell or segment `{class, density, surfaceTopped, tier, observedAt, confidence}` with the proposed classes `EMERGENT | FLOATING | SUBMERGED | FLOODED_TERRESTRIAL | NONE_SIGNIFICANT | UNKNOWN` and density `NONE | SCATTERED | MODERATE | DENSE`.
* `vegetation_habitat_state(cell, 'shallowVegetatedHabitat' | 'floodedVegetation')` returns TRUE / FALSE / UNKNOWN.
* **Only an observation counts:** tiers `OBSERVED_SATELLITE` and `OBSERVED_SURVEY`. `PRIOR_MAPPED`, `SEASONAL_EXPECTATION`, `POTENTIAL_HABITAT`, a refusal, an unrecognised class, a missing density, a missing or future date, or an observation older than **45 days** (an explicit engineering default, not a biological threshold) are UNKNOWN. `NONE_SIGNIFICANT` is FALSE only from a valid observation.
* `floodedVegetation` is TRUE only for an observed `FLOODED_TERRESTRIAL` cell; submerged plants are not flooded terrestrial vegetation.
Biological supplies species vegetation association (spawn substrate, feeding association, e.g. grass carp ↔ submerged vegetation) as `HABITAT` rules; Vegetation supplies the actual plant state.
Request: the seasonal state (growing / senescent) per cell, because a few associations (bowfin residency strongest in fall/winter as plants senesce) depend on it.

## 6. Wind
No evidence-backed Biological wind response is currently encoded (one common-carp fetch association is a single-system finding and is not a rule). Biological does not consume wind. If evidence appears, the request will be zone/bank exposure from the Wind Brain, not a lake-wide number.

## 7. What each missing input costs
| Missing input | Consequence |
|---|---|
| tributary discharge change | every flow-driven rule (silver, grass, alligator, quillback) is UNKNOWN for its strongest trigger |
| zoned depth shares | no species depth-preference match; spawn-depth rules stay knowledge, not matched bands |
| observed vegetation | no vegetation-association match for grass carp, gars, bowfin, snakehead |
| pool operations (spillway, release) | smallmouth buffalo / longnose gar / silver carp tailwater rules cannot activate |

## Consumption readiness (2026-10-14)
All three pending inputs are already validated and tested on the Biological side (`contracts_in.py`, `tests/test_contracts_in.py`); nothing else is needed from Biological when an owner publishes. Absent, stale or unrecognised input → the dependent feature is UNKNOWN; Biological never substitutes a proxy (the Lake pool trend never populates the discharge feature).

| Input | Owner | Accepted shape | Biological switch-on when published | Until then |
|---|---|---|---|---|
| Tributary discharge change | Lake Brain (tributary hydrology) | `lake.tributaryDischargeTrend` ∈ the stage-trend vocabulary; `RISING_RAPIDLY` ⇒ `rapidDischargeIncrease` TRUE | read the published field in `normalize_inputs` (already wired) | UNKNOWN |
| Depth zone shares | Depth Brain | shares within the 3/6/10 ft edges, valid only when level is not resolvably different | map the owner's canonical path in `normalize_inputs` | area-level habitat UNKNOWN |
| Observed vegetation | Vegetation Brain | observed tier only, age ≤ 45 days | map the owner's canonical path in `normalize_inputs` | UNKNOWN |

Biological does not recreate any owner's science and does not read their private internals.
