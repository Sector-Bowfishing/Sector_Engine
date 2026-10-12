# WindBrain — Sector Brain Platform integration (wind only)

**Brain ID:** `wind`. **Slot:** `wind`. **Snapshot field:** `wind`. **Brain version:** `wind-brain-1.0.0`. **Schema:** 1.

**Question:** what are the wind and water-surface conditions doing on this lake?

WindBrain does **not** decide good shorelines, protected fishing spots, whether tonight is good, or species behaviour.
Sector Intelligence consumes WindBrain for that.

**Contract:** Sector Ops `docs/BRAIN_INTEGRATION_REQUIREMENTS.md` §5 and `docs/SECTOR_BRAIN_RTDB_SCHEMA.md` (Brain RTDB
`sector-brain`, project `sector-9393c`). This file ratifies the wind section for Engine.

## Architecture

```
NOAA NBM v5.0 (NODD) ─┐
NOAA RTMA-RU (NODD) ──┼─> wind-hourly Cloud Run Job ──> gs://sector-wind-candidate/wind/v1 (Candidate archive, unchanged)
IEM METAR (8 stns) ───┘                │
                                       └─(opt-in, after the archive run)─> sector_wind.brain.publish ──> Brain RTDB (wind paths only)
                                                                                                           │ read-only
Engine /conditions (Swift, Open-Meteo Best Match) ── production wind, unchanged ─────────────────────────> Sector Ops (live Engine cards)
```

- **Additive adapter.** It reads only what the Candidate already archived and adds **no new science**: the frozen CEM, duration rule and fetch tables are mirrored, and the Python mirror is verified identical to the app's Swift `wind-cem`.
- **Production is untouched.** Nothing in Engine `/conditions`, the app, or the archive changes.
- **`publish()` never raises.** It does not alter the job's exit code, so a Brain RTDB outage cannot affect the archive.
- **Writes only wind-owned paths.** Shared nodes are written field by field. It never writes `/schemaVersion`, `/health/engine`, `/health/rtdb`, `/access`, `/validationOps`, or another brain's slot.

## Models: active production vs research candidate (never silently promoted)

| | Active production model | Research candidate |
|---|---|---|
| Id | `open-meteo-best-match` | `wind-candidate-2026.10.stage2-baseline` |
| What | Open-Meteo `/v1/forecast`, no `models` parameter. HRRR (about 0–46 h), then GFS | NOAA NBM v5.0 + RTMA-RU + METAR; frozen CEM surface physics |
| Where | Engine `/conditions` (Swift `WeatherService`), app conditions card | `wind-hourly` archive. **This brain publishes it** |
| Registry | `versions[]` status `CURRENT`; `activeProductionModel` | `versions[]` status `SHADOW`; `researchCandidate.promoted = false` |
| Brain output | **No.** Ops already reads production wind live from `/conditions` | Yes: per-lake state |

## Canonical lakes

The only registry is the Engine directory (`GET /lakes`). The research keys are mapped explicitly and verified on every
run:

| Research key | Canonical ID | RTDB key |
|---|---|---|
| `guntersville` | `Guntersville\|AL` | `Guntersville_AL` |
| `wheeler` | `Wheeler\|AL` | `Wheeler_AL` |
| `wilson` | `Wilson\|AL` | `Wilson_AL` |
| `pickwick` | `Pickwick Lake\|TN` | `Pickwick_Lake_TN` |

**Verification:**
- each ID must exist in the directory;
- its directory coordinate must lie inside the wind cut-out box;
- the whole-directory slug set must be collision-free.

Any failure writes only `health/brains/wind` = FAILED and nothing else. Name matching alone is wrong: `Wilson Lake|KS`
and `|HI` exist. National fetch-table lakes use the manifest's directory `name|state`.

## Paths written

| Path | When | Content |
|---|---|---|
| `/lakes/{k}/states/wind` | each run, 4 live lakes | `WindState` (below) |
| `/snapshots/{k}/latest/{wind, lakeId, snapshotVersion, generatedAt, brainVersions/wind}` | same atomic update as the state | snapshot field |
| `/lakes/{k}/profiles/wind` | live lakes each run; national lakes when the table SHA changes | `WindProfile` |
| `/lakes/{k}/validation/wind` | live lakes | per-lake validation (frozen evidence) |
| `/lakeFleet/{k}/{lakeId, readiness/wind}` | all 621 directory lakes | readiness |
| `/lakeFleet/{k}/{modelVersions/wind, lastUpdatedAt, slots/wind}` | live lakes | `slots/wind = {readiness, stale, stateType, issueCount, lastUpdatedAt}`: the same per-brain fleet record the Water Clarity brain writes |
| `/brains/wind` | each run | registry entry |
| `/validation/wind` | each run | fleet validation summary |
| `/sources/{noaa-nbm-v5, noaa-rtma-ru, iem-metar-wind}` + `/health/sources/…` | each run | from the 24 h ledger |
| `/health/brains/wind`, `/health/jobs/wind-hourly` | each run | runtime health |
| `/activity/{ms}_wind_{i}` | on version change, lake readiness change, or first run error | bounded to 500 / 30 days |

**Not written:**
- `lakeFleet/{k}.stale`, `issueCount`, `hasObservations`: lake-level aggregates that belong to the Lake Brain. Wind staleness is in the state and the registry.
- `/validationOps`: live skill checks are **sealed until 2027-01-01** (H2 holdout).

Per-bank surface rows go to storage, not RTDB: `brain/wind/latest/{k}.json.gz`.

## Readiness (Engine-owned vocabulary, wind meaning)

| Value | Meaning | Lakes today |
|---|---|---|
| DISCOVERED | In the directory; no frozen fetch geometry, no forcing archive | 547 |
| PROFILED | Frozen fetch tables built and QA'd (50 PASS + 20 relative-gate FLAGGED); no live forcing, so no state | 70 |
| CALIBRATION | Profiled + live hourly NBM/RTMA-RU/METAR archive + atmospheric validation at local stations; surface/exposure NOT field-validated | 4 |
| DEGRADED | A CALIBRATION lake whose state is stale, partial or unavailable this run | 0 |
| BETA / BLOCKED | not used | — |
| VALIDATED / PRODUCTION | **not reached:** field exposure and surface validation required; candidate not promoted | — |

**Health:** `HEALTHY · WARNING · DEGRADED · FAILED · UNKNOWN · NOT_CONFIGURED`.

**State kind:**

| Kind | Meaning |
|---|---|
| `analysis` | RTMA-RU at the lake point |
| `forecast` | No fresh analysis; NBM for this hour |
| `unavailable` | Values are null |

## Three things kept separate

1. **Model / science validation:** `/validation/wind`.
   - Frozen evidence from the pre-registered NBM v5.0 corpus (CAL + H1, 140,462 rows, 8 stations, forcing untuned).
   - The production proxy (HRRR) on identical rows.
   - Buoy surface physics (untouched 2020–23).
   - Wind Certification 3.1/10 and BWIS 5.4/10.
   - Status `PARTIAL`, with failed gates listed.
2. **Lake readiness:** `/lakeFleet/{k}/readiness/wind` and the profile.
3. **Runtime health:** `/health/brains/wind`, `/health/jobs/wind-hourly`, `/health/sources/*`.

## WindState (`sector-brain-wind-state-v1`)

| Field | Meaning |
|---|---|
| `kind` | `analysis` \| `forecast` \| `unavailable` |
| `sustainedMph`, `gustMph`, `directionDeg`, `directionCardinal` | current value from `kind` (never labelled as an observation); null when unknown or calm direction |
| `trend` | `rising` \| `easing` \| `steady`, from the NBM forecast at +3 h vs current (±2 mph); `trendBasis` says so |
| `hourly[≤24]` | NBM forecast `{at, mph, gustMph, dirDeg, leadHours}` from the newest cycle |
| `transitions[]` | forecast crossings of 5 / 10 / 15 / 20 mph (`basis: NBM forecast`) |
| `surfaceCondition` | modal modeled surface class + "(modeled, not field-validated)" |
| `surfaceState` | `{model, validated:false, durationH, chopClassPct, surfaceClassPct, textureClass, medianHm0In, p90Hm0In, boundaryBankPct, resolvableBanks, unknownBanks}` |
| `exposure` | `{protectedPct (Hm0 < 1 in), exposedPct (≥ 6 in), basis}`: a physical share of bank segments, not a recommendation |
| `forecast` | `{model, initTime, retrievedAt, status, horizonHours, kind:"forecast"}`; `forecastGeneratedAt` = NBM init |
| `analysis` | RTMA-RU `{product, analysisTime, retrievedAt, ageHours, sustainedMph, gustMph, directionDeg}` |
| `observation` | nearest frozen METAR `{station, network, distanceKm, observedAt, ageHours, …, stale}`; `observationTime` only when fresh |
| `representativePoint` | the directory coordinate (single point) |
| `stale`, `staleReasons[]` | NBM cycle > 3 h, or no current value |
| `provenance` | `brainId, brainVersion, modelVersion, processingVersion, generatedAt, sources[], inputAgeHours, readiness, qualityFlags[], validationRef` |

There are no confidence percentages. Unknown values are `null`, with a quality flag.

## WindProfile (`sector-brain-wind-profile-v1`)

- `readiness` (+ meaning), `geometry` (source, table and geometry SHA-256, banks, below-resolution share), `fetchQa`
- `fetchModel`, `exposureModel`, `surfaceConditionModel` (field-validated: false)
- `dominantExposure` (direction with the longest median effective fetch), `medianEffectiveFetchByDirectionM`
- `protectedAreas: null` (a location judgement, left to Sector Intelligence)
- `forcing` (null for national lakes), `activeProductionModel`, `researchCandidate`, `validation.ref`, `qualityFlags`, `knownLimitations`

## Running

```
python -m sector_wind.brain publish --store local:<mirror> --dry-run out.json          # build everything, write nothing remote
python -m sector_wind.brain publish --store gs://sector-wind-candidate/wind/v1 --rtdb https://sector-brain.firebaseio.com   # manual
```

**Inside the job:** set `SECTOR_WIND_BRAIN_RTDB_URL=https://sector-brain.firebaseio.com`. Unset means no publish.

## Deployment (DONE 2026-10-12, approved by Michael)

1. **Fetch tables:** the 4 frozen development fetch tables were copied to `gs://sector-wind-candidate/wind/v1/fetch/dev/<lake>.windfetch.json.gz`. Each table SHA-256 was verified before upload.
2. **IAM:** `wind-hourly-job@sector-9393c.iam.gserviceaccount.com` was granted `roles/firebasedatabase.admin` on `sector-9393c`.
   - An instance-scoped IAM condition (`resource.name.endsWith("/instances/sector-brain")`) was tried first. RTDB returned 401 for 15 min, so **RTDB does not honour it**, and the plain grant replaced it.
   - The role is project-wide, so it also reaches the app databases. `RtdbWriter` refuses any URL other than `sector-brain` (code guard).
   - A stricter option for later is an Admin SDK identity with `databaseAuthVariableOverride` plus Brain rules that allow only that uid to write the wind paths. That rules change belongs in Sector_Ops.
3. **Job:** `wind-hourly` was redeployed from `brain/wind` (generation 3). All existing settings were kept; env added: `SECTOR_WIND_BRAIN_RTDB_URL=https://sector-brain.firebaseio.com`, `SECTOR_WIND_BUILD=brain/wind@<sha>`.
   - Verified by execution `wind-hourly-b67j6`: archive OK, `windbrain ok`, `publishMode: scheduled`.
   - The earlier 401 runs also proved the isolation: the archive still succeeded.
4. **Rollback:** `gcloud run jobs update wind-hourly --region us-central1 --remove-env-vars SECTOR_WIND_BRAIN_RTDB_URL` (the archive is unaffected). To remove data, delete the wind paths.
