# Water Temperature Brain (`water-temp`): Engine side of the Sector Brain Platform

**Question:** what is the water temperature doing?

The brain does **not** judge fish activity, species behaviour, fishing quality or the Sector Intelligence score.

**Status:** built on branch `brain/water-temp` (from production commit `79b966cc`, revision `sector-engine-00072-way`). **Not deployed.**

Contracts: Sector_Ops `docs/BRAIN_INTEGRATION_REQUIREMENTS.md` §3, `docs/SECTOR_BRAIN_RTDB_SCHEMA.md` and `src/types/brain.ts`. This file ratifies the Engine-owned vocabularies for `water-temp`.

## Architecture

```
directory lake (LakeDirectory.all, 621, canonical "<name>|<state>")
   │  same fetch + resolve as /conditions:
   │    lake tempSensor (USGS / CWMS) → else USGS lake gauge ≤ 10 mi → surface-energy-balance-v2 (Open-Meteo)
   │    → WaterTemperatureResolver (measured ≤ 6 h & ≤ 15 mi, else modeled, else unavailable)
   ▼
WaterTemperatureBrain (Sources/SectorEngine/Brain/)  —  Profile · State · Registry · Validation · Health
   ▼
WaterTempBrainJob (Cloud Run job, every 3 h)  ──REST, service account──▶  sector-brain RTDB  ──read-only──▶  Sector Ops
```

- **Additive.** No existing source file changed. The service never imports the Brain code.
- A Brain RTDB failure fails only the job (it exits non-zero and writes FAILED health best-effort). `/conditions` is untouched.
- The measurement selection is restated from `ConditionsSnapshot`, not shared, so the customer path is not edited. Tests pin the resolver semantics.

## Three separate things

| | What it is | Where |
|---|---|---|
| **Model / science validation** | Documented evidence only. Global LOLO on 17 USGS lakes (RMSE 3.40 °F, bias −0.06 °F, n 8,110), status `GLOBAL_HOLDOUT_ONLY`. Per-lake records exist only for the 4 protected development lakes (`INSUFFICIENT_TRUTH`, not scored). | `/validation/water-temp`, `/lakes/{k}/validation/water-temp` |
| **Lake readiness** | The static evidence class of a lake | `readiness` on profile / state / fleet row |
| **Runtime health** | This run's fetch and write outcome | `/health/brains/water-temp`, `/health/jobs/water-temp-brain` |

## Vocabularies (Engine-owned)

**Readiness**

| value | meaning |
|---|---|
| `PRODUCTION` | The lake has its own configured authoritative in-lake surface sensor (directory `tempSensor`). Production shows the measurement when it is ≤ 6 h old, and the model otherwise. |
| `BETA` | Production serves the modelled value. The model is validated globally only; there is no lake-specific held-out validation. |

**State `kind`:** production vocabulary, verbatim. `observationType` is a normalised alias.

| kind | observationType |
|---|---|
| `measured` | `OBSERVED` |
| `modeled` | `MODELED` |
| `unavailable` | `UNKNOWN` |

- `OBSERVED_MODEL_CORRECTED` is **not emitted**: production does no assimilation. It belongs to the research candidate.
- FALLBACK is not a separate kind. The model's internal air-only fallback is not observable from its output.

**Health:**
- `FAILED`: the write failed, or there were no lakes.
- `DEGRADED`: > 25 % of lakes unavailable or the model fetch failed.
- `WARNING`: > 5 %.
- `HEALTHY`: otherwise.

**Stale:**
- `evidenceStale` / `stale` = the lake has a configured sensor but no fresh reading was shown.
- The registry publishes `staleAfterHours = 6`: two missed 3-hourly runs.

## RTDB paths written

Per lake `k = lakeKey(lakeId)` (Engine slug), one atomic multi-path update per 50 lakes:
- `lakes/{k}/states/waterTemp`
- `lakes/{k}/profiles/waterTemp`
- `snapshots/{k}/latest/{lakeId, generatedAt, snapshotVersion, waterTemperature, brainVersions/water-temp}`
- `lakeFleet/{k}/{lakeId, readiness/waterTemp, modelVersions/waterTemp, lastUpdatedAt}`

Then:
- `validation/water-temp`
- `lakes/{Guntersville_AL, Wheeler_AL, Wilson_AL, Pickwick_Lake_TN}/validation/water-temp`

Then, **full-fleet runs only**:
- `brains/water-temp`
- `health/brains/water-temp`
- `health/jobs/water-temp-brain`
- `sources/{open-meteo-forecast, usgs-nwis-00010, usace-cwms-water-temp}` and `health/sources/…`
- `activity/{time-sortable id}` on registration, version, model, readiness or health change, or a failed run (pruned to 500 events / 30 days)

**Not written** (shared lake-level fields owned by the Lake Brain):
- `lakeFleet/{k}`: `stale`, `issueCount`, `hasObservations`, `riverSystem`, `lakeType`
- `/schemaVersion`
- `/health/engine`, `/health/rtdb`
- `/validationOps`

## State (`lakes/{k}/states/waterTemp` = `snapshots/{k}/latest/waterTemperature`)

| field | source | unknown when |
|---|---|---|
| `kind`, `currentTempF`, `lakeLocalDate`, `spatialSupport`, `lastObservationAt`, `sourceAgeHours`, `measurementDistanceMiles` | `WaterTemperatureResolver` | no measurement / no model |
| `modelCurrentF` | `WaterTempModel.currentF` | model fetch failed |
| `measuredMinusModelF` | measured − model, only when measured | not measured (a live residual, not validation) |
| `trend24hF` + `trendBasis` | model, lake-local today − yesterday | no model, or lake date unknown |
| `sensorTrend` | the sensor reading's own trend label, verbatim | not measured |
| `forecast[] {at: lake-local date, tempF}` | model days after today, gauge-anchored like `ConditionsForecast` when measured | no model |
| `depthM` | resolver | always unknown today |
| `provenance` | brain, model, revision, `generatedAt`, sources, `inputAgeHours`, readiness, `qualityFlags`, `validationRef` | — |

There is **no confidence value**: none is calibrated.

## Profile (`lakes/{k}/profiles/waterTemp`)

- `baseModel`, `modelVersion`
- `observationSources` (the configured lake sensor), `nearbyGaugeLookup`
- `assimilation: none`
- `directoryTempSource` (directory classification, verbatim)
- `thermalClass`: null; `lakeType`: null (unknown)
- `measurementRule` (6 h, 15 mi, 72 h fetch tolerance, 10 mi gauge radius)
- `validation` refs, `readiness`, `knownLimitations[]`

## Registry (`brains/water-temp`)

- The shared shell, plus `staleAfterHours`.
- `breakdowns`: `stateKind`, `sourceKind`, `directoryTempSource`.
- `versions[]`: `CURRENT` production model, the `RESEARCH` V2 candidate, the `RETIRED` k = 0.20 model.
- `activeProductionModel`.
- `researchCandidate` (`certified: false`, blocker stated). **It is never promoted by this code.**
- The readiness, kind and health definitions.

## Run it

```
swift build --product WaterTempBrainJob
.build/debug/WaterTempBrainJob --dry-run /tmp/brain            # every path as a JSON file; no database
.build/debug/WaterTempBrainJob --dry-run /tmp/brain --lake "Guntersville|AL"
I_HAVE_MICHAELS_APPROVAL=yes ./jobs/water-temp-brain/deploy-job.sh   # after an engine image containing the job is deployed
```
