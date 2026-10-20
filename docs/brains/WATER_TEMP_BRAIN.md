> **Current state on main (Cortex standardization, 2026-10-20).** The deployment notes in this file are stale. On `main`:
> `WaterTempBrainJob` is built into the `brain-jobs` image (`jobs/brain-image-build.sh`), not the serving image, and is deployed as
> the Cloud Run job `water-temp-brain` by `jobs/water-temp-brain/deploy-job.sh` (`IMAGE=…` required; the script has no approval
> variable). There is **no scheduler**: the earlier `25 */3 * * *` cron is gone, and the Brain Orchestrator starts the job only when
> the 6-hour freshness rule requires it; the Brain is PARKED (`control_manifest.json` `water-temp`: `MANUAL`). The code still
> publishes `schedule = "every 3 h at :25 UTC"` in its registry (`WaterTemperatureBrain.swift:37`); correcting that published
> value is recorded as an open decision, not changed here. Operating contract (until the Brain migrates to
> `brains/water-temperature/`): `docs/architecture/certification/water-temp/BRAIN_OPERATING_CONTRACT.md`.

> **Consolidation note (2026-10-12, Phase 7).** This brain now lives on `main` (replayed from
> `brain/water-temp` @ `ec0ae0fa` onto the production lineage; the Clarity Stage 5 base it was
> built on did **not** come along). It publishes through the shared Brain Platform
> (`docs/brains/BRAIN_PLATFORM_CONTRACT.md`): readiness is the contract ladder — every lake is
> `CALIBRATION` — and the former `PRODUCTION`/`BETA` readiness values are now the **`evidenceClass`**
> (`sensor` | `modeled`) on each state and profile; the brain status is `CALIBRATION`; activity ids
> are `{ms13}-water-temp-{nnn}` with contract kinds; it prunes only its own events by `at`;
> `lakeFleet.lastUpdatedAt`, snapshot `generatedAt`/`snapshotVersion` are no longer written
> (Orchestrator rollups); `sources.brains` is a map with `ownerBrainId`. The job binary is built in
> the serving image (`/app/WaterTempBrainJob`) and deployed by `jobs/water-temp-brain/deploy-job.sh`
> from the serving revision; **not scheduled**. Sections below that say "PRODUCTION/BETA readiness"
> describe the pre-contract vocabulary.

# Water Temperature Brain (`water-temp`): Engine side of the Sector Brain Platform

**Question:** what is the water temperature doing?

The brain does **not** judge fish activity, species behaviour, fishing quality or the Sector Intelligence score.

**Status:** built on branch `brain/water-temp`, based on `intelligence/water-temp` @ `79b966cc`. **Not deployed.** (See *Closeout status* at the end: production is actually `bc9e09fb`.)

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
- `lakeFleet/{k}/slots/waterTemp` `{issueCount, lastUpdatedAt, readiness, stale, stateType}`: the per-brain summary the clarity and wind brains already write. `issueCount` = 1 when the sensor has no fresh reading or no value exists.

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

## Closeout status (2026-10-12)

**Connected once, not scheduled.** On 2026-10-12 06:40 UTC, a one-time run from Michael's Mac (gcloud user token) wrote all 621 lakes to `sector-brain`:
- `HEALTHY`;
- 32 measured, 589 modelled;
- `PRODUCTION` 29 / `BETA` 592.

No job and no scheduler is deployed. Michael will schedule it from the portal. The data stays a snapshot until then.

**Base correction.** Production's code is `bc9e09fb` (`fix/water-temp-shown-scored`, git tag `deployed/sector-engine-00072-way`). Since 2026-10-12 the live revision is `00080-wes`: the same image, right-sized to 2 vCPU / 1 GiB.

This branch's base, `79b966cc`, has a **byte-identical water-temperature path**:
- `WaterTemp/`, `Fetchers/`, `Forecast/`, `LakeDirectory`, `Deadline`.

So the Brain publishes exactly production's numbers. **But** the base also carries about 2,400 lines of Clarity Stage 5 code that production does not have:
- `CurrentClarityAPI`, `Clarity/*`, `ClarityPrecompute`, and `SectorEngineServer/main.swift` routes.

**Do not serve traffic from an image built off this branch** unless that Clarity code is meant to ship: the live env flags `SECTOR_CURRENT_CLARITY_ROUTES` / `SECTOR_CLARITY_CANDIDATE_ROUTES` would turn its routes on. For the job alone, build the image with no traffic, or cherry-pick the two Brain commits onto the production line.

**Tests at closeout:** `swift test` (filter water-temp + Brain) passes 41/41. The full suite passed 206/0 earlier on this branch.

**Open:**
- the scheduler (Michael);
- the service-account IAM breadth (`roles/firebasedatabase.admin` is project-wide);
- lake-level fleet fields owned by the Lake Brain;
- the `water-temperature` vs `water-temp` id (the Ops contract uses `water-temp`).
