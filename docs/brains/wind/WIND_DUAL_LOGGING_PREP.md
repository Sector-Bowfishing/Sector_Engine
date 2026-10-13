# Dual-wind logging — exact implementation plan (prepared; NOT wired; waits for the prerequisite branch)

Goal: collect, going forward, the customer provider's wind (Open-Meteo Best Match) next to the Brain's NBM value so that later, with truth attached, the provider decision rests on evidence about the **live** period. Until truth exists every statistic is labelled **PROVIDER DISAGREEMENT**, never accuracy. Code ready and tested: `jobs/wind-hourly/sector_wind/dual_log.py` (`build_record`, `attach_truth`, `growth_model`; `tests/test_dual_log.py`).

## Record (one per lake per logging hour)
`lakeId · loggedAt · validAt · forecastHorizonHours · forecastInit (+age) · customerProvider{directionDeg, speedMph, gustMph, category, fetchedAt, host (primary|fallback), available} · candidateProvider{directionDeg, speedMph, p90Mph, riskFlag, category, stale, available} · brainPublication{published, generatedAt, stale} · comparison{kind: PROVIDER_DISAGREEMENT, speedDiffMph, directionDiffDeg (only when both ≥ 5 mph), categoryAgree, accuracyClaim: false} · truth: null`.
Unavailable provider ⇒ `available:false` and null values (never zero/calm); a customer value from the fallback host is flagged `usedFallbackHost`.

## Where the pieces go (after `feat/cost-efficient-scheduling` resolves)
1. **Candidate side (Python job, no new network):** in `wind-hourly`, after the Brain build, read the point NBM value + P90 for each served lake (from the fleet sampler / archive) and build the candidate half.
2. **Customer side — two phases, lowest risk first**
   - **Phase 1 (pilot lakes only, ≈ 240 provider calls/day):** the job performs one Open-Meteo `/v1/forecast` request per pilot lake per hour with the **same parameters as production** (`wind_speed_10m,wind_direction_10m,wind_gusts_10m`, mph, no `models=`, same host preference), records `host` and `fetchedAt`. Same data product as customers receive; not literally the served bytes.
   - **Phase 2 (request path):** `SectorEngineAPI.conditions(lat:lon:date:)` (Swift) already holds the served `WeatherReading` (`windSpeed`, `windDirection`, hourly gust). Add one structured log line (lake key, served values, host) rate-limited to one per lake per hour; a small Python reader joins it with the Brain archive. This captures the real served value and the fallback-host behavior at **zero extra provider calls**. Needs a Swift change (Engine owns it) and review.
   - Not proposed: hourly Open-Meteo calls for all 621 lakes (+14,904 calls/day, free-tier and terms risk).
3. **Storage:** `dual_wind/<YYYYMMDDHH>.json.gz` (24 objects/day; ≈ 0.4 MB/day gz, ≈ 12 MB/month at 621 lakes; `growth_model`). Private bucket `sector-wind-candidate`, never RTDB.
4. **Truth later:** `attach_truth(record, obs)` joins METAR (or the over-water instrument when one exists) within 30 minutes of `validAt`. **It refuses any record whose `validAt` is in the H2 window (≥ 2026-10-07) before 2027-01-01**, so the log cannot be used to read H2 skill early; after the seal opens, accuracy statistics still need a pre-registration.
5. **Publish nothing to Ops:** only aggregate counts (rows logged, availability, disagreement rates labelled as disagreement) in `opsSummary` if desired.

## Rollout / rollback
Feature flag env var (`SECTOR_WIND_DUAL_LOG=pilot|request|off`, default off). Rollback = flag off; no schema or customer path depends on it. Gates before enabling: prerequisite branch merged; Open-Meteo terms for the pilot lookups reviewed (Michael); log bucket lifecycle set; no customer-visible change.

## What it will and will not tell us
Will: how often and by how much the two providers disagree by lake, hour, speed class, horizon, and when each is unavailable or stale; fallback-host frequency. Will not: which is right (no truth), over-water accuracy, or anything about H2 skill before 2027-01-01.
