# Wind Brain: Certification BEFORE baseline (step 1, exit A/H)

**Captured:** 2026-10-15 ~02:30Z, read-only, against live `sector-brain`, Cloud Scheduler/Run metadata and the candidate bucket, plus the repo at `fab115e9`. Nothing was changed. Public-safe: no identities, no raw dumps.

## 1. Identity (exit A)
| Field | Value |
|---|---|
| `brainId` | `wind` (unchanged) |
| Display name | Wind Brain (registry `displayName`: "Wind") |
| Domain | `condition` ("what are the wind and water-surface conditions doing?") |
| Lifecycle | `CALIBRATION` (control plane). Registry `status`: CALIBRATION. Candidate science: `RESEARCH_CANDIDATE`, shadow, `promoted=false` |
| Brain version | `wind-brain-1.0.0` (registry schemaVersion 1) |
| Model ids | active production (NOT a Brain output): `open-meteo-best-match`; candidate: `wind-candidate-2026.10.stage2-baseline` (SHADOW) |
| Deployed build | job label / `deploymentVersion` `main@e6a5026f5d0f` (that commit is an ancestor of `fab115e9`; `jobs/wind-hourly` is byte-identical to the deployed code) |
| Validation status | `/validation/wind.status = PARTIAL`; lake-local records `PARTIAL`. Field validation: none (0 real observations). H2 holdout sealed until 2027-01-01. 30-day live reliability gate: 5 of 30 valid days at last scoring, projected gate ~2026-11-07 |
| Customer exposure | **none** (`customerPublication = false`). Customer `/conditions` wind is Open-Meteo Best Match in-process; no customer path reads Wind Brain state (see `WIND_READER_WRITER_TRACE.md` §4) |

## 2. Fleet distribution (live)
547 DISCOVERED / 70 PROFILED / 4 CALIBRATION over 621 lakes. 74 profiles (70 national + 4 development), 4 lake states, 4 lake-local validation records, 4 snapshot copies (byte-equal to the 4 states), 4 fleet slots, 4 `modelVersions` rows, 621 `readiness` rows. (The earlier note "621 rows" holds for `readiness` only.)

## 3. Jobs and schedules
| Job | Schedule | State | Role |
|---|---|---|---|
| `wind-hourly` (Cloud Run Job) | Cloud Scheduler `5 * * * *` UTC | **ENABLED**, healthy, ~198 s/run, 1 vCPU / 2 GiB, retries 1 | archives NBM/RTMA-RU/METAR to the private bucket, then publishes Wind to `sector-brain` in-process |
| Policy class | `VALIDATION_EXCEPTION` (approved 2026-10-14; gate = 30 valid live days; cap $5/mo; re-decide ~2026-11-08) | | |
| Orchestrator | does not start Wind (`startedByOrchestrator=false`); writes `/jobs/wind-hourly` and Wind projections | | |

## 4. Paths, readers, writers, storage
Full detail: `WIND_RTDB_OWNERSHIP_MATRIX.md` (paths) and `WIND_READER_WRITER_TRACE.md` (code). Summary: **one specialist writer** (`wind-hourly` in-process publisher + a manual CLI), three platform writers that write Wind *projections* (score publisher, orchestrator), readers = Ops, Sector Intelligence (PARKED), orchestrator/score publisher. Private storage: `gs://sector-wind-candidate/wind/v1` (4,409 objects, 50.76 MB, no versioning, 7-day soft delete, no lifecycle rules, one manifest). Local research: see `WIND_RESEARCH_INVENTORY.md`.

## 5. Sources and dependencies
`noaa-nbm-v5` (forecast, stale >3.0 h), `noaa-rtma-ru` (analysis, >2.0 h), `iem-metar-wind` (observation, >1.5 h; 8 frozen stations). All three have `ownerBrainId = wind` and `brains: {wind: true}`; no other consumer is recorded. Wind depends on **no** Brain. Wind is an OPTIONAL, provisional, 6 h dependency of `biological-state` and `sector-intelligence` (manifest). Production Open-Meteo wind is consumed by Engine `/conditions` only.

## 6. Health / freshness semantics today
- `/health/brains/wind` HEALTHY, `lastSuccessfulRun` = last run; this is **process health**.
- Evidence freshness exists only as `stale` (bool) on the state and `staleAfterHours = 1.5` / rule on the registry: "stale when the newest NBM cycle is > 3 h old, no current value exists, or `generatedAt` is > 90 min old". No `staleAfter`, `expiresAt` or `freshnessStatus` fields. State carries `observationTime`, `forecastGeneratedAt`, `provenance.generatedAt`, `provenance.inputAgeHours`. Gap list in `WIND_PUBLISH_ARTIFACT_V1.md` §5.

## 7. Scores (BEFORE; do not change)
| Value | Where | scoreType (proposed) | Version |
|---|---|---|---|
| **3.3** (raw 32.65/100, uncapped 3.27, `COMPUTED`, updated 2026-10-13T21:13:49Z) | `/scores/wind`, plus control projections | **`ENGINE_READINESS_SCORE`** (authoritative) | `wind-certification-rubric-v1` |
| 3.1 | `/brains/wind.scores.windCertificationScore`, `/validation/wind.scores` | duplicate of the above, **stale mirror** | same rubric, earlier computation |
| 5.4 (total 54.16/100) | `/scores/wind/secondary`, `/brains/wind.scores`, `/validation/wind.scores` | `BWIS` | BWIS v1 (definition sha256 `21e2a326…`) |

Explanation and rules: `WIND_SCORE_RECONCILIATION.md`. Engine overall score at capture: 7.1 (`engine-score-v1`, provisional per CERT-6; not recomputed).

## 8. Local research locations
Canonical future workspace `Sector Research/wind-brain` (empty). Existing: `Sector_Research_Data/wind-brain` (4,598 files, 38.5 MB logical / 52 MB on disk, not in git, no backup), a 2.1 GB local cache holding the largest local-only material, five Engine branches plus the private iOS repo (all pushed), and three handoff files. See `WIND_RESEARCH_INVENTORY.md`.
