# Water Clarity Brain: field mapping

How each production Clarity output becomes a Water Clarity Brain field, where that field lives in the Brain RTDB, and where Sector Ops shows it.

**Paths:**
- `{k}` is the lake key: `re.sub(r"[^A-Za-z0-9]+", "_", lakeId)`. Every node also stores the canonical `lakeId`.
- `S` = `/lakes/{k}/states/waterClarity`, the same object as `/snapshots/{k}/latest/waterClarity`.

**Status codes:**
- **R** = real, read from production.
- **D** = derived here by a documented rule.
- **C** = catalog (fixed facts with a source reference).
- **U** = unavailable today (written as `null`).

## Per-lake state

| Existing output | WaterClarityBrain field | Brain RTDB path | Sector Ops | Status |
|---|---|---|---|---|
| Engine `/lakes` `id` | `lakeId` | `S.lakeId`, `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId` | fleet join, every page | R |
| `/conditions.clarityVisibility.centralFt` | `clarityFt` | `S.clarityFt` | Clarity Brain card (headline) | R |
| `clarityVisibility.lowFt`, `highFt` | `lowFt`, `highFt` | `S.lowFt`, `S.highFt` | Clarity Brain card (80% range) | R (null on rain-decay: no validated range) |
| `clarityVisibility.source` | `stateType` (GAUGE_OBSERVED / RAINFALL_MODELED / FALLBACK_NEUTRAL; engine miss → UNAVAILABLE) and `basis` | `S.stateType`, `S.basis` | Clarity Brain card chip | D (1:1 rename) |
| `clarityVisibility.model` | `engine.model`, `provenance.modelVersion` | `S.engine.model`, `S.provenance.modelVersion`, `/lakeFleet/{k}/modelVersions/waterClarity` | Clarity Brain card, Explainability | R |
| `clarityVisibility.confidence` (medium / low) | `engine.confidenceLabel` | `S.engine.confidenceLabel` | Clarity Brain card ("Engine label, not a probability") | R |
| `clarityVisibility.provenance`, `limitations` | `engine.provenance`, `engine.limitations` | `S.engine.*` | Clarity Brain card | R |
| `clarityRain.watershed72hIn` (source mrms) | `recentRainfallIn72h`, `rainfallSource` (MRMS_WATERSHED_72H / OPEN_METEO_POINT_48H), `rainfallWindowHours` | `S.*` | Clarity Brain card "Rain" | R (null when Open-Meteo fell back: that 48 h value exists only in engine text) |
| `clarityGauges[]` | `gauges[]` (siteCode, role, parameterCode, trend, driving) | `S.gauges` | provenance sources | R |
| driving turbidity gauge `trend` (rising / falling / steady) | `trend` (WORSENING / IMPROVING / STABLE), `trendBasis` | `S.trend`, `S.trendBasis` | Clarity Brain card | D (inverted: turbidity up = clarity down); UNKNOWN otherwise |
| `/conditions.resolvedLake.id` | `engine.resolvedLakeId`; flag `resolvedLakeMismatch` | `S.engine.resolvedLakeId` | quality flags | R |
| `/conditions.generatedAt` | `evaluationTime`, `provenance.inputAgeHours` | `S.evaluationTime` | provenance panel | R |
| Cloud Run traffic revision | `provenance.processingVersion`, registry `deploymentVersion` | `S.provenance.processingVersion` | provenance panel, registry | R (Run Admin API) |
| bucket `lakes/<k>/clarity/latest.json` `summary.time` | `satelliteObservationAt`, `satelliteAgeHours`, `satellite.observedAt` | `S.*` | Clarity Brain card "Satellite" | R |
| `summary.platform`, pass `sceneIds` | `satellite.platform`, `satellite.sceneIds` | `S.satellite.*` | Clarity Brain card, provenance source | R |
| `summary.measuredPct` | `spatialCoveragePct`, `satellite.coveragePct` | `S.*` | Clarity Brain card | R |
| `summary.openWaterReadPct`, `grassPct`, `fnuP25` / `p50` / `p75` | `satellite.*` | `S.satellite.*` | raw payload (dev toggle) | R |
| `summary.fnuP50` through secchi-power-v1 (11.123·FNU^−0.637; 80% range ×10^−0.356 / ×10^0.520) | `satellite.visibilityAtMedianFnu` | `S.satellite.visibilityAtMedianFnu` | Clarity Brain card "Satellite view" (labeled evidence only) | D (production formula, unchanged) |
| pass age vs 14 days (lake-surface LOOKBACK_DAYS) | `satellite.status` FRESH / STALE / NONE / UNSUPPORTED | `S.satellite.status`, `/lakeFleet/{k}/slots/waterClarity/satellite` | Clarity Brain card badge | D |
| `history.json` passes | `satellite.passCount`, profile `historicalObservationCount.satellitePasses` | `S.satellite.passCount` | raw payload | R |
| `latest.files.clarity`, `measured`, `distance`, `ndci` | `layers[]` {id, label, url, observedAt, kind: encoded-data} | `S.layers` | Clarity map card + layer chips | R (public HTTPS references, no rasters in RTDB) |
| pass meta `encoding`, `coordinates`, `projection`, `pixelWidth` / `Height`, `cellMetresMercator` | `layerGeometry` | `S.layerGeometry` | map caption | R |
| no production Stage 19 consensus | `strong` {state NOT_EVALUATED, evaluated:false, all counts null, policyId stage19-strong, policyVersion, reasonCode ACTIVE_MODEL_HAS_NO_MULTI_SCENE_CONSENSUS} | `S.strong` | Clarity Brain card (Strong) | R (honest null) |
| no production clarity class taxonomy | `clarityClass` | `S.clarityClass` | shows "unknown" | U |
| readiness rule clarity-readiness-v1 | `provenance.readiness` | `S.provenance.readiness`, `/lakeFleet/{k}/readiness/waterClarity`, `/lakeFleet/{k}/slots/waterClarity/readiness` | fleet matrix, Lake page per-brain readiness, brain KPIs | D |
| quality flags | `provenance.qualityFlags` | `S.provenance.qualityFlags` | provenance panel | D |
| catalog candidate | `candidateModel` {r3.1, lifecycle CANDIDATE, certificationStatus CERTIFIED, deploymentStatus NOT_DEPLOYED, publishesLakeState:false, researchScore, certificationRef} | `S.candidateModel` | Clarity Brain card (candidate) | C |
| model used for this lake | `activeModel` | `S.activeModel` | Clarity Brain card | R |
| authority of the evidence | `authority{customerEstimate NOT_APPLICABLE, satelliteEvidence}`, `satellite.authority` (from `sensorAuthority.byProcessingPath.lake-surface-l2a-red`) | `S.authority` | Clarity Brain card | C |

## Per-lake profile (`/lakes/{k}/profiles/waterClarity`)

| Field | Source | Status |
|---|---|---|
| `geometryReady`, `satelliteSupported`, `sentinel2Supported` | lake present in `jobs/lake-surface/polygons.geojson.gz` | R |
| `landsatSupported: false` | production Clarity uses no Landsat | R |
| `satelliteAvailable`, `spatialModelSupported`, `mapLayerSupported` | a published pass exists | R |
| `weatherRunoffInputs`, `precipitationInputsAvailable`, `runoffInputsAvailable` | this run's `clarityRain` / driving discharge gauge | R |
| `observationSources` | turbidity gauges in `clarityGauges` | R |
| `historicalObservationCount.satellitePasses` | `history.json` | R |
| `historicalObservationCount.inSituSecchi` | not tracked in production | U |
| `lakeClarityClass`, `hydrologicClass` | none in production | U |
| `validationStatus` | secchi-power-v1 → VALIDATED_NATIONALLY; rain-decay-v0 → NOT_VALIDATED | D |
| `readiness`, `candidateModels`, `knownLimitations` | rule / catalog / engine limitations | D, C, R |

Ops does not read profiles yet: there is no path key for them in `brainPaths.ts`.

## Fleet-level records

| Record | Brain RTDB path | Sector Ops | Status |
|---|---|---|---|
| Registry: version, health, counts, `staleAfterHours` (26), `breakdowns`, `versions[]`, `status` (BETA) | `/brains/water-clarity` | Overview cards, Brains registry, brain header + KPIs, Model versions tab | R / D |
| `activeModel`, `candidateModel`, `modelRoster[]` (lifecycle / deploymentStatus / certificationStatus), `certifications.r3_1` (status; detail via private overlay) | `/brains/water-clarity/{activeModel,candidateModel,modelRoster,certifications}` | Water Clarity → Overview → Models card (Ops maps codes to labels) | C |
| `sensorAuthority.byProcessingPath` | `/brains/water-clarity/sensorAuthority` | Water Clarity → Overview → Sensor authority card | C |
| `strongPolicy`, `readinessRule`, `stateTypes`, `processingPaths`, `vocabularies`, `layerCatalog`, `statusReasons` | `/brains/water-clarity/*` | Ops vocabulary / future | C |
| Run health | `/health/brains/water-clarity` | System Health, Overview | R |
| Job health: lake-surface-daily, hydrology-hourly, clarity-current-hourly, clarity-candidate-shadow, water-clarity-brain | `/health/jobs/{jobId}` | System Health → jobs | R (Cloud Run v2 + Scheduler APIs) |
| Sources: sentinel-2-l2a, usgs-nwis-turbidity, noaa-mrms | `/sources/{id}`, `/health/sources/{id}` | Data Sources, brain Source health tab | R / D |
| Production validation (secchi-power-v1) | `/validation/water-clarity` | brain Validation tab, Validation page | C (from `docs/data/hydrology/guntersville/visibility_validation.json`) |
| R3.1 certification | `/validation/water-clarity/candidates/r3_1` | brain Validation tab (candidate card; certificationStatus CERTIFIED, deploymentStatus NOT_DEPLOYED) | C (status public; metrics via private overlay) |
| Events | `/activity/{time-sortable id}` | Overview activity | D |
| `/validationOps` | not written: production Clarity has no per-lake validation runs | Validation runs table stays empty for Clarity | U |
