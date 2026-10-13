# Water Clarity Brain: integration

**Branch** `brain/water-clarity` (worktree `Sector_Engine-clarity-brain`), based on the deployed tag `deployed/sector-engine-00072-way`.

**Code** `jobs/water-clarity-brain/`

**Status (2026-10-12):** **Brain v1.1.0** (semantic contract). Built, tested (32/32), and run manually from the developer Mac to publish the full fleet into the Brain RTDB `sector-brain`.
- **Not deployed** as a job.
- No production code, science, endpoint, job or customer path was changed.

Field-by-field mapping: `WATER_CLARITY_BRAIN_MAPPING.md`.

## 0. Semantic contract (v1.1.0): Engine publishes facts, Ops owns presentation

Sector Engine / WaterClarityBrain is the authoritative source for every item below. All values are codes, numbers, IDs or references; there are no display labels or prose. Vocabularies are published at `/brains/water-clarity/vocabularies`.

| Fact | Where (Brain RTDB) | Values |
|---|---|---|
| Active production model | `/brains/water-clarity/activeModel` {modelIds, selectionRule PER_LAKE_ENGINE_SOURCE, servedBy, processingPathId, engineRevision}; per lake `states/waterClarity.activeModel` | secchi-power-v1 / rain-decay-v0 |
| Certified candidate | `/brains/water-clarity/candidateModel` and per lake `.candidateModel` | {modelId r3.1, lifecycle CANDIDATE, certificationStatus CERTIFIED, deploymentStatus NOT_DEPLOYED, publishesLakeState false, researchScore {8,10}, certificationRef} |
| Model lifecycle / status | `/brains/water-clarity/modelRoster[]` | lifecycle, deploymentStatus, certificationStatus, servesCustomers, coverage, processingPathId |
| R3.1 certification summary | `/brains/water-clarity/certifications/r3_1` | public: certificationStatus, result ALL_FROZEN_BARS_PASS, certifiedAt, deploymentStatus, `detailRef` (private). Detail fields come only from the private overlay |
| Research score | `certifications/r3_1.researchScore`, `modelRoster[r3.1].researchScore` | private overlay only |
| Per-lake readiness | `states/waterClarity.readiness` (+ `provenance.readiness`), `/lakeFleet/{k}/readiness/waterClarity` | rule `readinessRule` (clarity-readiness-v1) |
| State type / provenance | `states/waterClarity.stateType`, `.basis`, `.processingPathId`, `.provenance` | vocabularies.stateType |
| Strong state + policy | per lake `.strong` {state, evaluated, strong, counts, policyId, policyVersion, reasonCode}; `/brains/water-clarity/strongPolicy` | state NOT_EVALUATED for every lake (the active model has no multi-scene consensus) |
| Sensor authority by processing path | `/brains/water-clarity/sensorAuthority/byProcessingPath/{pathId}`; per lake `.authority` and `.satellite.authority` | FULL / LOWER / UNTIERED / NOT_CERTIFIED / NOT_USED |
| Source health | `/sources/{id}`, `/health/sources/{id}` | health + structured `coverage` |
| Brain health | `/health/brains/water-clarity`, `/health/jobs/*` | status, runs, errors, versions, publisher deployment status |
| Validation artifacts | `/validation/water-clarity.artifacts[]`, `.candidates.r3_1`, `certifications/r3_1.artifacts[]`, `sensorAuthority…evidenceRef` | {kind, repo, branch, commit, path, visibility PUBLIC_REPO / LOCAL_BRANCH} |

**Kept only because the Ops v1 contract requires them:**
- registry `displayName` / `question`;
- `layers[].label`;
- job `displayName` (now the job ID);
- source `provider` (the provider's name);
- activity `title`.

**Production text, not Brain prose:** `engine.provenance` and `engine.limitations` are the production engine's own text, restated as served to customers.

**Removed in v1.1:** `statusLabel`, model `displayName` / `role` / `summary`, `statusBasis`, `strongDefinition` prose, validation `statusNote` / `notes`, source `notes`, `reason` strings, and prose `rainfallSource` / `trendBasis` / `clarityQuantity` / `product`.

## 1. What existed before (production Clarity)

| Piece | Where | Who sees it |
|---|---|---|
| **Customer clarity estimate** `clarityVisibility` {centralFt, lowFt/highFt (80% range), confidence medium/low, model, source, provenance, limitations}, plus `clarityRain`, `clarityGauges`, and the clarity factor in the score | Swift engine `/conditions` (`SectorEngineAPI.clarityVisibilityDTO`, `ClarityFactor.visibilityFt`, `VisibilityModel`); live revision **sector-engine-00072-way** | iOS and Android, every lake |
| **Models behind it** | `secchi-power-v1` (USGS turbidity gauge, FNU → ft, 11.123·FNU^−0.637, validated: 81,661 WQP pairs, median error 1.22 ft) | wherever a turbidity gauge drives the estimate |
| | `rain-decay-v0` (MRMS 72 h watershed rain, else Open-Meteo 48 h point; "Not calibrated") | everywhere else |
| | neutral `noRainData` fallback | when there are no inputs |
| **Nightly satellite pass** | Cloud Run job `lake-surface-daily` (03:00 CT, 8 tasks; live code = `Sector_Engine-fusion/jobs/lake-surface`). Sentinel-2 L2A C1 via Earth Search, Dogliotti 2015 red band → FNU field, written to public `gs://sector-lake-surface/lakes/<slug>/clarity/` (`latest.json`, `history.json`, data PNGs, pass meta) and `index.json` (566 of the 599 outlined lakes have a pass) | **no shipping client**: iOS ships one bundled Guntersville pass; the S2 repair branches are unmerged |
| Hydrology | `hydrology-hourly` job (catchment rain, flows) → bucket | review / Current Clarity |
| Current Clarity (Fusion Stage 5) | review tag `clarity` (00071-cuw, 0% traffic) + `clarity-current-hourly` job | master-account iOS beta |
| R0 candidate shadow | `clarity-candidate-shadow` job (17 pilot lakes, private bucket) | nobody; **scheduler paused** 2026-10-02 |
| R3.1 | private research, certified 2026-10-12 | nobody; **not deployed** |

**Also true of production:**
- **Canonical lakes:** Engine `/lakes` (621 lakes, `"<name>|<state>"` IDs). The lake-surface job keys storage by the slug `re.sub(r"[^A-Za-z0-9]+","_",id)`; no slug collisions.
- **Firebase:** production Clarity writes no Firebase/RTDB data. Shared clarity reports are DEV-only.
- **Freshness:** the satellite job reads only passes ≤ 14 days old (`LOOKBACK_DAYS`); the approved S2 repair withholds passes > 14 days.
- **No Strong, no authority tiers:** production has no Stage 19 multi-scene Strong, and no sensor-authority tiers.

## 2. What was added

```
Engine /lakes ──────────────┐
Engine /conditions (prod) ──┤
gs://sector-lake-surface ───┼──► WaterClarityBrain (jobs/water-clarity-brain) ──► sector-brain RTDB ──► Sector Ops (read-only)
Cloud Run / Scheduler API ──┘        reads only; separate process
```

| File | What it does |
|---|---|
| `brain_platform.py` | Brain Platform plumbing, no clarity knowledge: lake key with a collision check; REST client with atomic multi-path PATCH, 5xx/429/network retries with backoff, no retry on 4xx; refuses the app DBs `sector-9393c-default-rtdb` and `sector-dev-1f4d0`; `/schemaVersion` check; token from the metadata server (Cloud Run) or gcloud (Mac) |
| `clarity_brain.py` | `WaterClarityBrain`, pure functions: adapters (engine estimate, satellite evidence, map layers); `build_state` (WaterClarityState); `build_profile` (WaterClarityProfile); readiness; registry / health / sources / activity builders |
| `catalog.json` | Fixed facts with references: models (production + candidates incl. R3.1 certification), sensor authority, Strong definition, readiness rule, state types, production validation, R3.1 certification summary, clarity jobs, sources |
| `run.py` | The run: directory → bucket reads → `/conditions` per lake (bounded concurrency) → atomic per-batch publish → fleet records |
| `tests/` | 32 unittest cases on real fixtures (incl. "no display labels or prose in the payload") |
| `Dockerfile`, `deploy-job.sh` | **Not run** |

## 3. WaterClarityProfile (`/lakes/{k}/profiles/waterClarity`)

`lakeId, brainId, schemaVersion, profileVersion, updatedAt, modelFamily, modelVersion,`
`lakeClarityClass (null), hydrologicClass (null), geometryReady, satelliteSupported, sentinel2Supported,`
`landsatSupported (false), satelliteAvailable, weatherRunoffInputs[], precipitationInputsAvailable,`
`runoffInputsAvailable, observationSources[], historicalObservationCount{satellitePasses, inSituSecchi: null},`
`sourceCoverage{inSituTurbidity, rainfall, satellite}, spatialModelSupported, mapLayerSupported,`
`validationStatus, readiness, candidateModel{…, perLakeOutput: null}, activeModels[], observationSourceIds[],`
`limitationCodes[] (UNCALIBRATED_MODEL, SINGLE_POINT_ESTIMATE, SATELLITE_NOT_IN_CUSTOMER_ESTIMATE), engineLimitations[] (engine text), validation{ref}`.

Unknowns are written as `null`, never defaulted.

## 4. WaterClarityState: the BrainResult payload (`/lakes/{k}/states/waterClarity` = `/snapshots/{k}/latest/waterClarity`)

**Envelope:** `lakeId, schemaVersion, brainId, brainVersion, generatedAt, evaluationTime, readiness, provenance{brainId, brainVersion, modelVersion, processingVersion, generatedAt, sources[], inputAgeHours, readiness, qualityFlags[], validationRef}`.

**v1.1 semantic fields:**
- `processingPathId` ("engine-conditions") and `activeModel` (the model that produced this lake's number).
- `candidateModel{modelId, lifecycle, certificationStatus, deploymentStatus, publishesLakeState, researchScore, certificationRef}`.
- `authority{customerEstimate: NOT_APPLICABLE, satelliteEvidence, satelliteProcessingPathId}`.
- `strong{state, evaluated, strong, evidenceCount, fullAuthorityEvidenceCount, consensusWindowDays, authority, policyId, policyVersion, reasonCode}`.
- `rainfallSource`: MRMS_WATERSHED_72H or OPEN_METEO_POINT_48H.
- `trendBasis{sourceType, sourceId, gaugeTrend, relation INVERSE}`.
- `clarityQuantity`: SECCHI_EQUIVALENT_VISIBILITY.
- `satellite{…, reasonCode, productId, modelId, processingPathId, authority}`.
- `layers[]{id, label, url, observedAt, kind, field}`.

**Domain fields:**
- **Estimate:** `stateType, basis, clarityFt, lowFt, highFt, clarityUnit ("ft"), clarityQuantity, clarityClass (null), trend, trendBasis`.
- **Rain and engine:** `recentRainfallIn72h, rainfallSource, rainfallWindowHours, engine{model, source, confidenceLabel, provenance, limitations, resolvedLakeId}, gauges[]`.
- **Satellite:** `satelliteObservationAt, satelliteAgeHours, spatialCoveragePct, satellite{status, freshWithinDays, inCustomerEstimate:false, observedAt, ageHours, date, platform, sceneIds, coveragePct, openWaterReadPct, grassPct, fnu{p25,p50,p75}, visibilityAtMedianFnu{centralFt, lowFt, highFt, model, source, basis}, passCount, publishedAt, product}`.
- **Map:** `mapLayerAvailable, mapLayerVersion, layers[], layerGeometry`.
- **Strong:** `strong{evaluated, strong, evidenceCount, fullAuthorityEvidenceCount, consensusWindowDays, authority, reason}`.
- **Models:** `models{active, candidate{modelId, status, publishesState}}, sensorAuthorityRef, stale`.

**State types.** These are the real production semantics, not the brief's example names.

| stateType | basis | engine `source` | meaning |
|---|---|---|---|
| `GAUGE_OBSERVED` | OBSERVATION | inSituGauge | USGS turbidity gauge, converted by secchi-power-v1 |
| `RAINFALL_MODELED` | MODEL | rainDecayModel | rain-decay heuristic (MRMS, else Open-Meteo) |
| `FALLBACK_NEUTRAL` | FALLBACK | noRainData | no gauge and no rain: neutral estimate |
| `UNAVAILABLE` | NONE | — | engine did not answer this run |

Production fuses no satellite data into the customer number, so there is no `SATELLITE_OBSERVED` or `SATELLITE_MODEL_FUSED` type. Staleness is a flag (`stale`), not a state type.

**Trend** (IMPROVING / WORSENING / STABLE / UNKNOWN) comes only from the driving turbidity gauge's own trend, inverted. Otherwise it is UNKNOWN. The Brain computes no trend from rain or satellite passes.

**No fake confidence.**
- The engine's `confidence` (medium / low) is passed as `engine.confidenceLabel`, the Engine's word.
- No percentages.
- `clarityClass` stays null because production has no class taxonomy. The research Clear / Normal / Stained / Limited classes are not production semantics.

**Strong.** Production has no Stage 19 consensus, so every state carries `strong.evaluated=false` with all counts null and a reason. Strong keeps its frozen meaning, published in the registry `strongDefinition`: ≥ 2 full-authority scenes within W = 10 d, M-agree, conf ≥ 0.90, no disjoint scene. Strong is evaluated only by R3.1 and R0, and neither is deployed.

## 5. Readiness (`clarity-readiness-v1`, official Ops enum)

| stateType | readiness | why |
|---|---|---|
| GAUGE_OBSERVED | PRODUCTION | served and validated (secchi-power-v1) |
| RAINFALL_MODELED | BETA | served but explicitly uncalibrated |
| FALLBACK_NEUTRAL | DEGRADED | no measurement of any kind |
| UNAVAILABLE | DEGRADED | engine miss on first sight; a later miss keeps the last good state |

**Not readiness inputs:**
- Satellite availability does not change readiness, because the pass is not in the customer number.
- `VALIDATED` and `CALIBRATION` are unused until a per-lake validation exists.

**Brain-level status:** `BETA`, because most lakes are on rain-decay and the publisher is not yet scheduled.

## 6. Exact RTDB paths written (instance `sector-brain`, project `sector-9393c`, schema 1)

**Per lake.** One atomic multi-path PATCH per 25-lake batch:
- `/lakes/{k}/states/waterClarity` (replaced: Clarity-owned)
- `/lakes/{k}/profiles/waterClarity` (replaced: Clarity-owned)
- `/snapshots/{k}/latest/waterClarity`, `/snapshots/{k}/latest/brainVersions/water-clarity`, `/snapshots/{k}/latest/lakeId`, `/snapshots/{k}/latest/snapshotVersion`, `/snapshots/{k}/latest/generatedAt` (**leaf writes**: the snapshot is shared)
- `/lakeFleet/{k}/lakeId`, `/lakeFleet/{k}/lastUpdatedAt`, `/lakeFleet/{k}/readiness/waterClarity`, `/lakeFleet/{k}/modelVersions/waterClarity`, `/lakeFleet/{k}/slots/waterClarity` (**leaf writes**: the row is shared)
- On an engine miss with a previous state: only `/lakeFleet/{k}/slots/waterClarity/{stale,lastErrorAt,lastError}`. The last good state is kept.

**Fleet-level.** One PATCH after the lakes:
- `/brains/water-clarity`
- `/health/brains/water-clarity`
- `/validation/water-clarity` (production plus `candidates/r3_1`)
- `/sources/{sentinel-2-l2a | usgs-nwis-turbidity | noaa-mrms}` and `/health/sources/{same}`
- `/health/jobs/{lake-surface-daily | hydrology-hourly | clarity-current-hourly | clarity-candidate-shadow | water-clarity-brain}`
- `/activity/{time-sortable id}`, plus deletes of this brain's own events older than 30 days or beyond 200

**Never written:**
- `/schemaVersion` (read and checked; a mismatch aborts the run)
- `/lakes/{k}/brain` (Lake Brain)
- `/validationOps` (no per-lake runs exist)
- `/access`
- any other brain's slot
- lake-level `issueCount` / `stale` / `hasObservations` (Lake Brain aggregates)

The Wind Brain session published into the same instance during this run. Leaf writes keep both brains' fields side by side; verified on `/lakeFleet/Guntersville_AL`.

## 7. Provenance

Every state names:
- the brain and model version;
- the Engine revision (`processingVersion`, read from Cloud Run traffic);
- the engine evaluation time;
- each source with its time: engine, driving USGS gauges (time unknown in the DTO), MRMS / Open-Meteo (latest rain day), Sentinel-2 scene ID and acquisition time;
- `inputAgeHours`, readiness, quality flags and `validationRef`.

**Quality flags:** `uncalibratedModel:rain-decay-v0`, `rainfallFallback:open-meteo-48h`, `noMeasurement`, `noValidatedRange:algal`, `resolvedLakeMismatch:<id>`, `satelliteStale:<d>d>14d`, `satelliteNone`, `satelliteUnsupported`, `engineUnavailable`.

## 8. Health

**Brain run** (`/health/brains/water-clarity`):
- status;
- lastRun / lastSuccess;
- durationMs;
- staleLakeCount;
- errorCount;
- latestError;
- deployedVersion and engineRevision;
- lakes attempted / published;
- the lake-surface run summary (day, tasks, outcomes {published, upToDate, noUsablePass, noPassInWindow, error}).

Status thresholds are ops rules, not science:

| Status | Rule |
|---|---|
| HEALTHY | ≥ 95% of lakes answered and the satellite job ran in the last 36 h |
| WARNING | ≥ 80% answered |
| DEGRADED | below 80% answered, or a publish failed |
| FAILED | the run aborted |

**Jobs** (`/health/jobs/*`) come from the Cloud Run v2 executions and Cloud Scheduler APIs: last run, last success, duration, failures, PAUSED.

**Sources:** health is derived from this run. For example, Sentinel-2 is HEALTHY when ≥ 80% of lakes with a pass are fresh.

Recorded on 2026-10-12:
- `lake-surface-daily` HEALTHY: 10-11 run, 0 errors, 226 "no usable pass" (cloudy windows, which are not errors).
- `clarity-candidate-shadow` PAUSED.

## 9. Validation

**Production** (`/validation/water-clarity`): secchi-power-v1, from `docs/data/hydrology/guntersville/visibility_validation.json` (be1d8932):

| Metric | Value |
|---|---|
| Median abs error, in situ national | 1.22 ft (42% within ±30%, n = 81,661) |
| By class: Alabama / TN River reservoirs | 0.81 / 0.94 ft |
| Sentinel-2 FNU | 2.18 ft (31%, n = 905) |
| Status | `VALIDATED_NO_GATE`: no pass/fail gate was defined |
| `lakeCount` | null (not recorded) |

`rain-decay-v0`, which serves most lakes, has **no validation**.

The contract's `secchiMaeFt` is not used, because the measured metric is a *median* absolute error. It is named `secchiMedianAbsErrorFt`.

**Candidate** (`/validation/water-clarity/candidates/r3_1`):
- The public catalog publishes status only: CERTIFIED, CANDIDATE, NOT_DEPLOYED, last run 2026-10-12.
- Metrics, samples and classes come only from the private overlay (see §17).

## 10. Models, R3.1 and sensor authority

**Active production:** secchi-power-v1, rain-decay-v0, plus the lake-surface Sentinel-2 pass as `PRODUCTION_OBSERVATION` (evidence, not in the customer number).

**Certified candidate: R3.1**
- lifecycle `CANDIDATE`, certificationStatus `CERTIFIED`, deploymentStatus `NOT_DEPLOYED` (Ops chooses the wording).
- `publishesLakeState: false`. No R3.1 prediction is published as lake state: it is not running in production.
- Certification detail, research score and deployment prerequisites live in the private research store and reach the Brain RTDB only through the private overlay.

**Other models in `modelRoster`:** R0 (lifecycle SHADOW, deploymentStatus PAUSED) and Current Clarity Stage 5 (lifecycle REVIEW, RUNNING_NOT_SERVING, 0% traffic).

**Sensor authority** (`/brains/water-clarity/sensorAuthority/byProcessingPath`), owned by this brain:

| Model path | S2A | S2B | S2C | Landsat |
|---|---|---|---|---|
| `lake-surface-l2a-red` (production pass) | UNTIERED | UNTIERED | UNTIERED | NOT_USED |
| `r0-acolite-l1c` (R0) | FULL | FULL | **LOWER** | NOT_CERTIFIED |
| `r3-usgs-aqr` (R3.1) | FULL | FULL | **FULL** (certified 2026-10-12, AQR path only) | NOT_CERTIFIED |

S2C is not promoted on the ACOLITE path.

## 11. Map layers

`layers[]` hold public HTTPS URLs to the bucket's PNGs (clarity, satellite footprint, distance to reading, algal NDCI). `layerGeometry` holds the encoding (log10 FNU, 0–254), corners and projection.

**These PNGs are 8-bit grayscale data rasters, not rendered colour maps.** Each layer carries `kind: "encoded-data"`, and Ops captions them that way.

Rasters stay in Cloud Storage; RTDB holds only references (about 4 KB per state).

## 12. Production compatibility

- **No production code changed.** The branch adds only `jobs/water-clarity-brain/` and `docs/brains/`.
- **No deploy:** engine, jobs, rules and clients are unchanged.
- **The publisher only reads production:**
  - one `/conditions` call per lake, bounded to 2 at a time (the engine runs at concurrency 1 per instance, max 30);
  - public bucket reads;
  - Cloud Run / Scheduler status.
- **A Brain RTDB outage cannot affect customers:**
  - separate process;
  - the schema check fails first and exits non-zero;
  - per-batch publish failures are counted and the run continues;
  - tested in `EndToEnd.test_brain_rtdb_outage_exits_without_touching_production`.
- **Writes only to the Brain RTDB:** the client refuses the app DB URLs.

## 13. Contract notes (Ops docs amended on Sector_Ops `brain/water-clarity`)

1. **Additive fields:**
   - registry `models`, `sensorAuthority`, `strongDefinition`, `readinessRule`, `stateTypes`, `layerCatalog`, `statusBasis`;
   - validation `candidates{}`, `statusNote`, `notes`;
   - `/lakeFleet/{k}/slots/{slot}` per-brain summary;
   - state fields in §4.

   The Wind Brain adopted the same `slots` convention.
2. **RTDB drops empty arrays and objects** (`failedGates: []` reads back absent). Readers must treat an absent list as empty; Ops crashed on this and is fixed.
3. **RTDB returns map keys sorted.** A "first metric" convention is not stable; the Ops by-class chart now uses a metric the class rows carry.
4. **Stale thresholds:** the Ops proposal was a satellite observation older than 5 days. Clarity publishes Engine's existing 14-day satellite freshness, with `staleAfterHours: 26` for the daily run.
5. **Readiness location:** Ops read per-lake readiness only from `/lakes/{k}/brain` (the Lake Brain, not built). Ops now falls back to each brain's own `snapshot.*.provenance.readiness`. Writing a partial Lake Brain node would have broken the Lake page.
6. **Contract names not used:**
   - `secchiMaeFt` → `secchiMedianAbsErrorFt` (it is a median).
   - `clarityClass` stays null.
   - State-type names are the real taxonomy above.
7. **Layer chips:** Ops' hard-coded chips (Observation age, Cloud cover) had no Engine counterpart. Ops now shows the layers Engine publishes.

## 14. Deployment (not done; needs Michael's review)

1. Review and merge `brain/water-clarity` (Engine). It is local only: **do not push** without deciding on the public repo (the catalog carries R3.1 summary metrics).
2. Ops: review and merge Sector_Ops `brain/water-clarity`; `npm run deploy:ops`.
3. IAM for a new SA `water-clarity-brain@sector-9393c`:
   - `roles/firebasedatabase.admin` (project-wide; see the open item);
   - `roles/run.viewer`;
   - `roles/cloudscheduler.viewer`.

   `deploy-job.sh` does this.
4. `jobs/water-clarity-brain/deploy-job.sh` creates the Cloud Run job (1 task, 1 vCPU / 1 GiB, 2 h timeout) and the Scheduler `30 4 * * *` America/Chicago, after lake-surface-daily.
5. First execution: `gcloud run jobs execute water-clarity-brain --region us-central1`. Then check `/health/brains/water-clarity` and `/health/jobs/water-clarity-brain`.
6. Optional: the Ops allowlist (`/access/opsUsers`) already lists Michael; nothing else is needed for reading.

## 15. Open items

- **IAM scope:** RTDB IAM is project-wide. Least privilege would be REST `auth_variable_override={"uid":"water-clarity-brain"}` plus sector-brain rules granting that uid only Clarity paths. That is a rules change (Ops-owned file).
- **Shared plumbing:** `brain_platform.py` is Clarity-local. Promote it to a shared module once Water Temp and Wind settle their publishers.
- **Lake-level fleet fields:** `issueCount`, `stale` and `hasObservations` need the Lake Brain aggregator.
- **Profiles in Ops:** profiles are written but Ops has no path key to read them.
- **Per-lake validation:** `/validationOps` and per-lake validation runs need in-situ Secchi matching, which production does not do.
- **Load:** the publisher calls `/conditions` 621 times a day. A slim engine clarity endpoint would cut upstream load; that is an engine change, not done.

### Scientific weaknesses (documented, not changed)

- rain-decay-v0 is uncalibrated and serves most lakes.
- The satellite pass is not used in the customer number.
- The production satellite job accepts S2C untiered.
- secchi-power-v1 on satellite FNU is ±2.5× at 80%.
- All these belong to later research phases.

## 16. First publish (2026-10-12, Brain v1.1.0, manual run from the Mac)

**Run:** `python3 run.py --engine-concurrency 3`.

| Measure | Result |
|---|---|
| Duration | 27.3 min |
| Lakes answered by the engine | 621 / 621 |
| Published | 621 |
| Engine misses / publish failures | 0 / 0 |
| RTDB traffic | 26 atomic PATCHes, 7.0 MB |
| Health | HEALTHY |
| Engine revision | sector-engine-00072-way |

| Breakdown | Count |
|---|---|
| Readiness | PRODUCTION 18 (GAUGE_OBSERVED, secchi-power-v1); BETA 603 (RAINFALL_MODELED, rain-decay-v0); FALLBACK_NEUTRAL 0 |
| Satellite evidence | FRESH 526, STALE 40, NONE 33, UNSUPPORTED (no outline) 22 |
| Pass platform | S2C 249, S2B 192, S2A 125 |
| Rainfall source | MRMS 592, Open-Meteo fallback 26, none 3 (gauge lakes with no rain payload) |

**Gauge-observed lakes** include Allatoona GA, Chatfield Reservoir CO, Cheney Reservoir KS, Detroit Lake OR, Fox Lake IL and John Redmond Reservoir KS.

**Other brains:** the Water Temp and Wind Brains wrote the same instance during the run. Their fields coexist with Clarity's in `/lakeFleet` and `/snapshots`.

**RTDB note for readers:** RTDB drops `null`. The Strong counts, `strong.strong` and `lakeCount` therefore read back as absent; absent means unknown, and nothing defaults it.

## 17. Public catalog and private overlay

This repo is public, so `catalog.json` holds status-level facts and the contract semantics only.

| Status | What |
|---|---|
| Public | lifecycle; certification / deployment status; sensor-authority levels per processing path; Strong policy; readiness rule; production validation |
| Private | R3.1 certification detail (bars, populations, metrics, research score, S2C evidence, prerequisites, artifact paths) |

**Where the private detail lives:**
- `catalog.private.json`, gitignored, beside the code;
- the private research backup in `gs://sector-clarity-candidate/research-archive/2026-10-12-closeout/`.

**How the publisher uses it:**
- It merges the overlay when present: `$CLARITY_PRIVATE_CATALOG` (a path or gs:// URI), else the local file.
- It reports `catalogDetail` on the registry: PUBLIC_ONLY, PRIVATE_OVERLAY_LOADED or PRIVATE_OVERLAY_UNAVAILABLE.
- Merged, the result is identical to the catalog published on 2026-10-12. Science and contract are unchanged.
