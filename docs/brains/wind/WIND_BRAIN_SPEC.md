# WIND_BRAIN_SPEC (Sector Brain Model v1 conformity pass — documentation only; no science, rubric, schedule or deploy change)

| | |
|---|---|
| Brain ID | `wind` (version `wind-brain-1.0.0`, candidate `wind-candidate-2026.10.stage2-baseline`) |
| Lifecycle | **SHADOW** for the Brain/candidate; **CALIBRATION** for Sector-derived exposure/surface (needs field truth). Customer wind remains Open-Meteo via Engine `/conditions`. |
| Mission | Say where wind is from, how hard, tonight's trend, which banks are hit or sheltered, how confident Sector is. |
| Bowfishing decision improved | WHEN to go (tonight, easing/breezy risk), WHICH bank (exposed vs protected), WHAT is limiting (chop), HOW confident. |
| Owns | Wind truth and wind-derived exposure/surface intelligence. |
| Does not own | Lake identity/level (Lake), water temp/clarity, depth, vegetation, species, "is tonight good" synthesis (Intelligence). |
| Upstream | NOAA NBM v5.0, RTMA-RU, IEM METAR (candidate); Open-Meteo (customer); Lake Registry v1 (geometry/identity). |
| Downstream | Sector Intelligence (contract `WIND_INTELLIGENCE_CONTRACT.md`), Sector Ops (`wind-ops-summary-v1`, unpublished), Engine (unchanged). |

## Claims by level and maturity (per claim, not per Brain)
| Claim | Level | Maturity | Validation owed / status |
|---|---|---|---|
| Wind speed (NBM/Open-Meteo) | 1 | PROVIDER_VERIFIED | source, units, freshness: done; night MAE 0.84 mph, bias −0.04 |
| Wind direction | 1 | PROVIDER_VERIFIED | within 22.5° 0.81 night/fcst ≥5 mph; 0.758 all hours |
| Forecast gust | 1 | PROVIDER_VERIFIED (display, with "runs low in strong wind") | strong-gust skill poor (NBM ≥20 kt POD 0.04) is a provider limitation, not a display blocker |
| Trend (easing/steady/rising) | 1/2 | VERIFIED (easing precision 65%); "rising" and lay-down NOT claimed | arithmetic on provider hours |
| Direction relative to bank | 2 | VALIDATED | FROM-wind convention tested |
| Effective fetch (9-ray CEM) | 2 | VALIDATED | independent exact-geometry median diff 0.05 |
| Breezy-risk flag (P90 ≥ 10 mph) | 2 | CALIBRATION | lift 19×; sealed H2 before any stronger claim |
| Exposed/protected bank | 3 | CALIBRATION (v2 rules post-date original failure; NOT independently validated) | frozen prereg + field pack; blocker FIELD |
| Surface/chop (LIKELY CALM/MODERATE/ROUGH/UNKNOWN) | 3 | NOT_VALIDATED | blocker FIELD |
| Tonight usefulness | 3 | CALIBRATION | internal only |
A failed Level-3 claim does not make Level-1 fields unusable.

## Canonical runtime state (compact)
`state`, `speedMph`, `directionDeg`, `gustMph` (forecast), `trend`, per-bank `exposure` (EXPOSED/PROTECTED/UNKNOWN + geometry tier), `surfaceClass`, `confidence`, reason codes, `generatedAt`, `sourceUpdatedAt`, `stateVersion`, `inputFingerprint` (see below), `stale`, `limitations`. Runtime image = 644 KB package incl. 208 KB geometry; no research archive is read at customer time.

## Confidence and UNKNOWN policy
UNKNOWN for POINT_ONLY geometry, below-resolution banks, boundary-class chop, missing/stale provider data, or ESTIMATED bank without margin; never PROTECTED without chop ≤ 2 (ESTIMATED uses ×1.5 fetch margin). Tonight/lay-down/gust-impact claims are withheld, not guessed.

## Freshness
Max acceptable state age 90 min (scorer's median-age gate); NBM cycle hourly, METAR hourly.

## EXECUTION / SCHEDULING MATRIX
| Component | Current trigger | Recommended trigger | Needs schedule? | Fingerprint? | Reason |
|---|---|---|---|---|---|
| Provider ingestion (NBM/RTMA/METAR → archive) | wind-hourly Cloud Run Job, `5 * * * *` UTC | unchanged | YES (A: provider changes hourly; B: prospective validation needs timed snapshots; reliability clock) | provider cycle timestamp | cheap scale-to-zero job, ~1 call set/hour |
| Brain compute (per-lake state) | same job, after archive, opt-in publish | recompute only lakes whose inputs changed (NBM cycle, rules/geometry version) | rides on ingestion | proposed: hash(NBM cycle, RTMA time, rulesVersion, geometryTier) | inputs change hourly, so savings small today; matters at fleet scale |
| Validation logging (ledger, reliability) | same job / weekly `run_cycle.py` (manual) | unchanged; dual-wind logging only after its prerequisite | YES (B) | n/a | prospective snapshots must be timed |
| Score publication (certification score) | shared brain-orchestrator publishes baked artifact, only after a brain state change | unchanged (owned by shared platform; stale-score guard on deploy) | no Wind clock | artifact content compare | durable 3.3 verified over two cycles |
| Control-plane publication | orchestrator, after state change | unchanged | no | existing | Ops reads cached control state |
| Maintenance/health | `monitor.py` inside the hourly job | unchanged | rides on ingestion | n/a | cheap |
Fleet (621 lakes): no recomputation beyond the 4 development lakes + 50 directory lakes; fleet exposure stays offline (build tool), not a runtime or customer-triggered job.

## Score dimensions and critical dimensions
Rubric `wind-certification-rubric-v1` (frozen). Critical-dimension proposal and the speed/gust gate mismatch: `WIND_CRITICAL_DIMENSIONS_PROPOSAL.md`, `WIND_PRODUCT_RUBRIC_MISMATCH_PROPOSAL.md` (awaiting Michael). Production gate (unchanged): overall ≥ 8.0 and critical ≥ 7.5.

## Production requirements
Customer wind stays on Open-Meteo until: reliability gate (projected 2026-11-08), H2 (sealed to 2027-01-01), field-validated exposure/surface, Michael approval. No customer deploy from this lane.

## Storage budget and research stop conditions
Local: `Sector_Research_Data/wind-brain` 52 MB; `~/Library/Caches/sector-wind` 1.9 GB (provider-bakeoff 0.7 GB live ledger, historical corpus 0.46 GB, venv 0.5 GB) — below the 5 GB review line; no dataset >2 GB retained. Stop conditions: provider skill gaps are documented, not researched; no gust/speed campaign; fleet exposure is not extended beyond what moves a product decision.

## Ops summary / customer exposure
`wind-ops-summary-v1` ready, unpublished (Ops presentation of displayed vs underlying score, gates, claim maturity = OPS PRESENTATION blocker, Sector Ops lane). Customer exposure: none from Brain; ESTIMATED exposure internal as EXPOSED/PROTECTED/UNKNOWN only.

## Cost and runtime
One hourly Cloud Run Job + GCS archive + small RTDB writes; no customer-triggered compute. Runtime depends on no large artifact.

## Shared field-validation compatibility (future platform; not built here)
Wind needs per trip: trip id, lake, time, GPS of bank, bank facing, observed exposure (one-minute record), observed surface class, local anemometer reading when available, weather/time. Schema already in `field_schema.py` (v2) and `WIND_FIELD_OBSERVATION_PROTOCOL.md`; it should be a subset of the shared trip record so one trip also feeds Depth/Biological/Vegetation.
