# Lake Brain (`lake-brain`): integration contract

**Status:** RATIFIED by Sector Engine, 2026-10-12 (v1, pilot). It amends Sector_Ops `docs/BRAIN_INTEGRATION_REQUIREMENTS.md` §2 and `docs/SECTOR_BRAIN_RTDB_SCHEMA.md`. Sector Ops adapts to it.

- **Approvals:** all ten decisions in the Lake Brain audit §28 were approved by Michael on 2026-10-12, as recommended.
- **Not merged or deployed.** Branch `sector/lake-brain` stays unmerged until it is reviewed. There is no Cloud Run job or scheduler.
- **Implementation:** `Sources/SectorEngine/LakeBrain/` (Swift; reuses the production TVA/CWMS parsers without changing them) and the `LakeBrainJob` executable.

**Display name:** **Lake Brain**. Machine ID `lake-brain`; slot `lake`; snapshot field `lakeState`.

## 1. What it owns

| Owns | Does not own |
|---|---|
| **LakeProfile:** pools, operator characteristics, source capability, history coverage, species presence summary | Lake identity. The **Lake Registry stays the Engine directory** (`GET /lakes`, 621 lakes). No new IDs, and directory fields are never copied |
| **LakeState:** current elevation, change, and `levelState` / `trendState` / `historicalState` / `floodPoolState` as **separate** fields, plus freshness | What fish do about the level. That is Sector Intelligence and the Conditions Score (`WaterLevelFactor` is untouched) |
| **Explainable baselines:** operator guide/zone, day-of-year percentiles. No ML | Species knowledge (Biological Brain, `/species/{id}`) |
| **Lake → species presence** (`speciesPresence`) | Presentation (Sector Ops) |

Nothing in the request path imports this module. `/conditions`, `/lakes`, `/hydrology`, the apps and the app RTDBs are unchanged.

## 2. Brain RTDB paths (`sector-brain`)

| Path | Content | Write style |
|---|---|---|
| `/lakes/{k}/brain` | LakeProfile (§3) | whole node (Lake-Brain-owned) |
| `/lakes/{k}/states/lake` | LakeState (§4) | whole node |
| `/lakes/{k}/speciesPresence/{speciesId}` | presence record (§8) | whole `speciesPresence` node (Lake-Brain-owned) |
| `/snapshots/{k}/latest/lakeState` | the same LakeState | **leaf** (plus `lakeId`, `brainVersions/lake-brain`) |
| `/lakeFleet/{k}` | `readiness/lake`, `slots/lake`, `modelVersions/lake`, `riverSystem`, `lakeId` | **leaves only** |
| `/brains/lake-brain` | registry entry (§10) | whole node |
| `/validation/lake-brain` | `status: NOT_VALIDATED` | whole node |
| `/health/brains/lake-brain`, `/health/jobs/lake-brain` | run health | whole node |
| `/sources/{tva-restapi, usace-cwms-pool, usgs-nwis-lake-elevation}` (+ `/health/sources/…`) | source health, separate from brain health | whole node |
| `/activity/{eventId}` | registered / version / readiness / health changes | append |

**Never written:**
- another brain's slot;
- `/schemaVersion`;
- a whole `/lakes/{k}`, `/lakeFleet/{k}` or `/snapshots/{k}/latest` node;
- the shared lake-level fleet fields `stale`, `issueCount`, `hasObservations` and `lastUpdatedAt`. Those stay unwritten until the platform decides how to combine them across brains.

**What a run writes:**
- **Per lake:** one atomic multi-path update.
- **After the lakes:** the registry, validation, health, sources and activity.
- **A `--lake` subset:** writes per-lake nodes only.

**History never goes in RTDB.**

## 3. LakeProfile (`/lakes/{k}/brain`)

Extends the frozen `LakeBrain` shape additively. `Known<T> = {value, source, quality}`, and an unknown value is absent.

```jsonc
{ "lakeId": "Guntersville|AL", "schemaVersion": 1,
  "profileVersion": 1,                    // integer; +1 whenever profileHash changes
  "profileHash": "e94b3e3e1b7bce01", "updatedAt": "…",
  "identity": { "riverSystem": "Tennessee" },               // only when a reviewed source states it
  "hydrology": { "dam": Known<string> },
  "characteristics": { "hydropower": Known<bool>, "floodControl": Known<bool>, "controlled": Known<bool>,
                       "navigation": null, "runOfRiver": null, "naturalLake": null },   // absent = unknown
  "operatingPools": { "normalFullPoolRef": "engine-directory:fullPoolFt (GET /lakes)",
                      "topOfGatesFt": Known<number>, "guideCurve": { "available": true, "source": "…", "ref": "…" },
                      "operatingZoneSource": "TVA BtmOpZone–TopOpZone (daily)", "datum": Known<string> },
  "sourceCapability": { "level": "DIRECT_OPERATOR_POOL", "bindingStatus": "REVIEWED|CANDIDATE",
                        "bindingVersion": "bindings-2026-10-12.1",
                        "primary": { "sourceId": "tva:GVDA1", "provider": "TVA", "capability": "…", "cadenceMin": 60, "lagMin": 60 },
                        "fallbacks": [ … ], "history": [ "…" ], "proxyOnly": false, "reviewedAt": "2026-10-12" },
  "historicalCoverage": { "historyStart": "2025-01-01", "historyEnd": "2026-10-12", "observationCount": 650,
                          "coveragePct": 100, "yearsCovered": 1, "baselineStatus": "INSUFFICIENT", "historicalTier": "NONE",
                          "baselineMethod": "doy15-percentile-v2", "baselineVersion": "…",
                          "historyRef": "gs://sector-lake-brain/history/Guntersville_AL/daily.csv" },
  "speciesPresenceSummary": { "assessedSpecies": 12, "recordCount": 10, "byState": { "established": 3, … , "unknown": 2 },
                              "researchVersion": "lake-presence-2026-10-12.1", "ref": "/lakes/Guntersville_AL/speciesPresence" },
  "trustedSources": { "tva_GVDA1": { sourceId, provider, sourceType, station, status, lastObservationAt, authority, brains } },
  "readiness": { "lake": "CALIBRATION" },
  "activeIssues": [ { "id": "primary-source-stale", "severity": "warning", "kind": "source-stale", "title": "…", "lakeId": "…", "brainId": "lake-brain", "since": "…" } ] }
```

- **Directory fields are not duplicated.** Name, states, coordinates, operator, `fullPoolFt`, `poolBasis` and `poolConfidence` come from `GET /lakes`.
- **`trustedSources` keys are slugs** of `sourceId` (RTDB forbids `.` and `/`). Each record carries the real `sourceId`.

## 4. LakeState (`/lakes/{k}/states/lake`, snapshot `lakeState`)

```jsonc
{ "lakeId": "Lake Hartwell|SC", "schemaVersion": 1, "kind": "OBSERVED", "sourceCapability": "DIRECT_OPERATOR_POOL",
  "currentElevationFt": 649.32, "unit": "ft", "datum": "NGVD29",
  "observationTime": "2026-10-12T23:00:00Z", "sourceAgeHours": 0.13,
  "differenceFromNormalPoolFt": -10.68, "normalPoolRef": "engine-directory:fullPoolFt",
  "guideFt": 660, "differenceFromGuideFt": -10.68,
  "operatingZone": { "bottomFt": 656, "topFt": 660, "bottomLabel": "Drought Level 1",
                     "topLabel": "Top of Conservation (guide curve)", "source": "cwms:SAS" },
  "operatorLevels": [ { "name": "Drought Level 2", "ft": 654, "source": "…" }, … ],
  "change": { "h1": -0.03, "h6": -0.11, "h24": -0.08, "d3": 0.41, "d7": 0.16 },
  "levelState": "BELOW_ZONE", "trendState": "STABLE", "historicalState": "UNUSUAL", "floodPoolState": "NORMAL",
  "seasonalPercentile": 8.6, "rateOfChangePercentile": 55, "rapidChangeThresholdFt": 0.25,   // v2: the effective RAPID threshold, max(seasonal p95, 0.25 ft)
  "seasonalBand": { "p02": 643.34, "p10": 649.89, "p50": 655.58, "p90": 660.54, "p98": 661.89,
                    "basisYears": 30, "windowDays": 7, "sampleCount": 450 },
  "baselineStatus": "SUFFICIENT", "historicalTier": "FULL",          // rules v2 R1; baselineStatus keeps its v1 meaning
  "facts": [ "649.32 ft at Oct 12, 7:00 PM EDT (USGS 02187010).", "…" ],   // ordered, factual, no fish wording
  "freshness": { "generatedAt": "…", "sourceObservationAt": "…", "freshUntil": "…", "nextCheckAt": "…",
                 "stale": false, "refreshReason": "scheduled: stable lake, 2 h" },
  "provenance": { "brainId": "lake-brain", "brainVersion": "1.0.0", "modelVersion": "lake-level-rules-v2",
                  "processingVersion": "…", "generatedAt": "…", "sources": [ … ], "inputAgeHours": 0.13,
                  "readiness": "BETA", "qualityFlags": [ "primarySourceStale:…", "fallbackSource:…" ],
                  "validationRef": "/validation/lake-brain" } }
```

**How absent and proxy values behave:**
- Unknown values are absent.
- A `PROXY` state (nearby gage) has `levelState: UNKNOWN` and `historicalState: INSUFFICIENT_HISTORY`, with flag `proxyTrendOnly`.
- A `PROXY` state never carries a pool difference, guide difference, operating zone, percentile or band.

### Engine-owned enums

| Field | Values |
|---|---|
| `kind` | `OBSERVED` · `PROXY` · `UNAVAILABLE` |
| `sourceCapability` | `DIRECT_OPERATOR_POOL` · `DIRECT_LAKE_GAUGE` · `NEARBY_GAUGE_PROXY` · `HISTORICAL_ONLY` · `MODELED` (reserved) · `NO_SOURCE` |
| `bindingStatus` | `REVIEWED` · `CANDIDATE` |
| `levelState` | `BELOW_ZONE` · `IN_ZONE` · `ABOVE_ZONE` · `FLOOD_POOL` · `UNKNOWN` |
| `trendState` | `STABLE` · `RISING` · `FALLING` · `RISING_RAPIDLY` · `FALLING_RAPIDLY` · `UNKNOWN` |
| `historicalState` | `NORMAL` · `UNUSUAL` · `VERY_UNUSUAL` · `INSUFFICIENT_HISTORY` |
| `floodPoolState` | `NORMAL` · `IN_FLOOD_POOL` · `UNKNOWN` |
| `baselineStatus` | `SUFFICIENT` · `LIMITED` · `INSUFFICIENT` · `NONE` |
| `presenceState` | `established` · `reported` · `stocked` · `inRangeUnconfirmed` · `historical` · `failed/eradicated` · `unknown` (research vocabulary, verbatim) |

## 5. Source capability and the reviewed bindings

Production resolves dams and gages at request time by proximity. The Lake Brain **does not**:
- A state is published only from a **reviewed** binding (`LakeSourceBindings.swift`, version `bindings-2026-10-12.1`).
- Every other directory lake gets a `CANDIDATE` class from its directory hints. A candidate never publishes a state.

**Pilot probe record (2026-10-12):**

| Lake | Class | Live (best first) | Guide / zone | History |
|---|---|---|---|---|
| Guntersville\|AL | `DIRECT_OPERATOR_POOL` | TVA `GVDA1` | TVA operating guide: guide curve + zone | TVA guide daily midnight 2025-01-01 → today; shared hourly archive since 2026-10-06 |
| Wheeler\|AL | same | TVA `WHLA1` | same | same |
| Wilson\|AL | same | TVA `WLSA1` | zone only (TVA publishes no guide curve for Wilson) | same |
| Pickwick Lake\|TN | same | TVA `PICT1` | guide curve + zone | same |
| Lake Hartwell\|SC | `DIRECT_OPERATOR_POOL` | CWMS SAS `Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS` → fallback USGS `02187010` `00062` (`DIRECT_LAKE_GAUGE`) | CWMS `Elev-GC` (top of conservation) with zone bottom `Elev-L1` (Drought Level 1); L2/L3 shown | CWMS daily `Elev-Pool…1Day…Raw-SHEF_SAS`, 1961-12-31 → 2026-10-06 (23,656 days) |

**Probe findings:**
- **The audit's TVA IDs were wrong** for three pilots: `WHDA1`, `WLDA1` and `PKDT1` return empty. The TVA `/locations` IDs are `WHLA1`, `WLSA1` and `PICT1`.
- **Caveat C4 is resolved.** The operating-guide `Day` year is a stale template label, so only month and day are used.
  - `CurYrElev` is this calendar year's elevation at 00:00 of that day. Its last non-zero row equals `MidNightElevation` and the 48 h feed's midnight reading on all four dams.
  - `PrevYrElev` is the previous year.
  - A value of 0 means no value.
- **TVA "Midnight" rows** are the hour ending at midnight. `10/10 Midnight` is 10/11 00:00.
  - The Lake Brain parses this correctly.
  - Production `TVAGenerationService.date` places them 24 h early. That is a separate production fix, not made here.
- **Hartwell (C2) explained.** The CWMS hourly pool feed has been silent since 2026-10-08 10:00Z. That is past production's 36 h fresh window, so `/conditions` shows no pool.
  - USGS `02187010` is on the lake and live.
  - It agrees with the CWMS pool within 0.03 ft over 2026-10-01 to 10-08. USGS lists the site altitude in NAVD88; no offset is applied.
  - Every run re-checks the overlap and flags `fallbackDatumDisagreement` above 0.10 ft.
- **Using a fallback is never silent.** It adds `primarySourceStale:<id>@<last>` and `fallbackSource:<id>`, plus an active issue.

## 6. Baselines (`doy15-percentile-v2`)

Rules v2 were **pre-registered** in `LAKE_BRAIN_RULES_V2_PREREGISTRATION.md` before any v2 code or test existed. `doy15-percentile-v2` differs from v1 only in the basis-year cap (below) and the new `historicalTier`. The quantile grid, the ±7-day window, type-7 interpolation, the 329-day complete-year rule and the rate climatology are unchanged.

**Daily history** is one value per lake-local day:
- TVA: the guide's midnight elevation. Each run merges it forward, so history grows past TVA's 2-year window.
- CWMS: the district's published daily value.

**Basis years** (v2): the most recent **30 complete calendar years** for regulated lakes (directory `poolBasis = fullPool`); **all** complete years, capped at 60, for `naturalSurface` lakes. A year is complete when it has ≥ 90 % of its days (329). A lake with no `poolBasis` is treated like a natural surface.

**`baselineStatus`** is unchanged from v1, so the Lake score rubric reads the same facts:

| Status | Rule |
|---|---|
| `SUFFICIENT` | ≥ 5 complete basis years |
| `LIMITED` | 2–4 |
| `INSUFFICIENT` | some history, < 2 |
| `NONE` | no history |

**`historicalTier`** (new, separate field; rules v2 R1) says what the history may be used for:

| Tier | Complete basis years | `historicalState` that may be published |
|---|---|---|
| `NONE` | < 5 | `INSUFFICIENT_HISTORY` only |
| `PROVISIONAL` | 5–9 | `NORMAL` / `UNUSUAL`, with quality flag `historicalProvisional`. Never `VERY_UNUSUAL`: a value outside p02–p98 is reported `UNUSUAL` |
| `STANDARD` | 10–14 | `NORMAL` / `UNUSUAL`. Never `VERY_UNUSUAL` |
| `FULL` | ≥ 15 | `NORMAL` / `UNUSUAL` / `VERY_UNUSUAL` |

Recency weighting is not part of v2.0. Whether the score rubric should demand 10 years instead of 5 is a rubric decision and was not made here. Sensitivity (research score, not a change): a 10-year rubric would lower the fleet research score from about 6.6 to about 6.1.

**Level climatology:**
- For each day of year: every basis-year value within ±7 days, which is 15 days.
- Stored as a quantile grid (0, 2, 5, 10 … 95, 98, 100), type-7 interpolation.
- Built only with ≥ 2 basis years.

**Rate climatology:**
- |Δ24h| between consecutive days, same window, every year in the last 30 (partial years included; the 60-year cap applies to levels only).
- Kept only when the window has ≥ 20 samples. Without it, RAPID uses the 0.25 ft floor alone and the flag is `rateBaselineLimited`.

**Artifacts:** `gs://sector-lake-brain/baselines/{k}/{baselineVersion}.json`, where `baselineVersion = method@historyEnd#fingerprint`. Each is written once, so artifacts are immutable. The method string is part of the version, so the move to `doy15-percentile-v2` writes new artifacts and leaves the v1 ones untouched. (The path scheme itself is unchanged here.)

**Method cross-check (not validation).** For Hartwell on Oct 12, the 30-year band is p10 649.89 / p50 655.58 / p90 660.54. The CWMS-published period-of-record series (1962+) is 649.09 / 655.90 / 660.90. The gap is the expected basis difference.

## 7. Classification rules (`lake-level-rules-v2`)

| Field | Rule |
|---|---|
| `levelState` | **Operator first.** Above the operator's flood-pool bottom (CWMS top of conservation) → `FLOOD_POOL`. Below the operator zone → `BELOW_ZONE`, above it → `ABOVE_ZONE`, inside → `IN_ZONE`. No operator zone → `UNKNOWN`. |
| `historicalState` | Gated by `historicalTier` (§6). Inside p10–p90 → `NORMAL`; outside → `UNUSUAL`; outside p02–p98 → `VERY_UNUSUAL` only at tier `FULL` (otherwise `UNUSUAL`). Tier `NONE` → `INSUFFICIENT_HISTORY`. `PROVISIONAL` adds the flag `historicalProvisional` |
| `trendState` | **RAPID** (`RISING_RAPIDLY` / `FALLING_RAPIDLY`) when \|Δ24h\| > max(this lake's seasonal p95 \|Δ24h\|, 0.25 ft). Otherwise the **72 h mean rate** (Δ72h / 3 days, ±3 h) against a floor: `STABLE` when \|mean72\| ≤ floor, else `RISING` / `FALLING`. Floor: **0.10 ft/day regulated** (`poolBasis = fullPool`), **0.05 ft/day natural**. No 72 h change in the series → the 24 h change is used and the flag is `trend24hFallback`. No rate baseline → the 0.25 ft floor alone, flag `rateBaselineLimited`. The v1 seasonal-p50 term is removed |
| `rapidChangeThresholdFt` | The effective RAPID threshold, max(seasonal p95, 0.25 ft). Absent for a PROXY |
| `floodPoolState` | Only where the operator publishes a flood-pool bottom (CWMS). Otherwise `UNKNOWN` with flag `noOperatorFloodPoolThreshold`. TVA's `TopOfGates` is not a flood pool |
| `differenceFromNormalPoolFt` | Only for directory `poolBasis = fullPool` with confidence med/high. Natural-lake surfaces never get one |
| `change` | Δ over 1 h / 6 h / 24 h / 3 d / 7 d. The tolerances are ±20 / 45 / 90 / 180 / 180 minutes. Absent when no reading falls in the window |

Each classification is its own field; none is folded into another. `differenceFromGuideFt`, `differenceFromNormalPoolFt` and `rateOfChangePercentile` are unchanged. A PROXY gauge still gets a trend and nothing else (RAPID is demoted to RISING / FALLING).

**What changed against v1:**
- `historicalTier` is new. v1 published `VERY_UNUSUAL` for any `SUFFICIENT` baseline (≥ 5 years); v2 needs ≥ 15 years.
- The trend direction comes from the 72 h mean, not the last 24 h; STABLE no longer widens to the seasonal median.
- RAPID has a 0.25 ft floor and no longer needs a rate baseline; v1 never published RAPID without one.
- Natural lakes use a 0.05 ft/day STABLE floor (v1: 0.10 ft for all).
- Natural lakes use all complete years up to 60 (v1: 30 for all).
- **Unchanged:** `baselineStatus` and its thresholds, the score rubric, `NOT_VALIDATED`, the readiness ladder and vocabulary, `levelState`, `floodPoolState`, the freshness envelope.

**72 h data.** The classifier needs ≥ 72 h of readings. The non-TVA feeds are fetched for 192 h. The TVA observed-data feed carries 48 h only, so TVA lakes get their 72 h change from the shared hourly archive (8 days, merged for the primary source). When the archive is empty, or a fallback source is in use, the 24 h fallback applies and says so.

**Hold-out result.** The pre-registered hold-out (§2 of the pre-registration) ran once: H-A, H-B and H-D passed, **H-C failed** (see `LAKE_BRAIN_RULES_V2_RESULTS.md`). The failure is not re-tuned. Validation stays `NOT_VALIDATED`.

## 8. Lake → species presence

**Path:** `/lakes/{k}/speciesPresence/{speciesId}`. This takes the Biological Brain's §10 shape, replacing the audit's `/species`:

```jsonc
{ "lakeId": "Guntersville|AL", "speciesId": "grass_carp", "presenceState": "historical",
  "presenceAuthority": "canonical-research", "confidence": "medium", "nativeStatus": "introduced",
  "sourceTier": "T2", "latestRecord": "2005", "dataGaps": "…",
  "sourceRef": "gs://sector-lake-brain/presence/releases/lake-presence-2026-10-12.1/presence.json (private)",
  "researchVersion": "lake-presence-2026-10-12.1", "discrepancyIds": ["DISC-001"], "updatedAt": "…" }
```

**Rules:**
- **12 species are assessed:** 5 carp, 3 buffalo, 4 gar. Others are not assessed and absent.
- **`unknown` rows are not written.** Absent means unknown or not assessed. `speciesPresenceSummary.byState.unknown` still counts them.
- **Canonical overrides** come from the Biological Brain canonical release. Today none differ from the matrix: grass carp on Guntersville is `historical` in both (DISC-001).
- **Discrepancy IDs are attached and never resolved here.** DISC-001, DISC-002 and DISC-003 are on Guntersville. DISC-002 (smallmouth buffalo) is still Michael's decision.
- **Which states are "relevant"** is Sector Intelligence's call.

**Interface for Sector Intelligence:** `LakePresenceIndex.resolveLakeSpecies(lakeId)`.

**Data stays private:**
- The bundle is built in the private research repo (`lake_brain/presence/build_presence_bundle.py`) and stored in `gs://sector-lake-brain/presence/`.
- This public repo only validates it: vocabulary, snake_case species IDs, directory lake IDs, no duplicates, and an FNV-1a fingerprint checked against `latest.json`.
- A bad bundle publishes nothing.
- The builder repairs six HTML-escaped matrix lake IDs (`Chain O&apos;Lakes|IL` → `Chain O'Lakes|IL`, …) and reports each one.

## 9. Readiness (`lake-brain-readiness-v1`) and health

| Readiness | Rule |
|---|---|
| `DISCOVERED` | Directory lake, no reviewed binding (profile only) |
| `PROFILED` | Reviewed binding says `NO_SOURCE` |
| `CALIBRATION` | Current level from a reviewed source; history < 5 years or no operator guide |
| `BETA` | `OBSERVED` + operator guide + `SUFFICIENT` baseline (`baselineStatus`, ≥ 5 years): every classification computed, not validated |
| `DEGRADED` | Reviewed source, but the current reading is stale or unavailable (last value kept and flagged) |
| `VALIDATED` / `PRODUCTION` | Not used until classification checks exist |

**Brain status:** `CALIBRATION`. `/validation/lake-brain` reads `NOT_VALIDATED`. Rules v2 do not change the readiness ladder or its vocabulary: readiness still reads `baselineStatus`, not `historicalTier`. A passing hold-out would not by itself change the validation status (`LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`).

**Health:**

| Health | Rule |
|---|---|
| `FAILED` | Write failed or no lakes |
| `DEGRADED` | > 25 % of reviewed lakes unavailable |
| `WARNING` | Any reviewed lake stale, unavailable or on a fallback |
| `HEALTHY` | Otherwise |

## 10. Freshness and orchestration

**Freshness:**
- `freshUntil` = observation + cadence + lag. TVA is 60 + 60 min; CWMS 60 + 120; USGS 60 + 60.
- **Stale** = more than two cadences past due (`now > observation + lag + 3 × cadence`). The last known value is kept and flagged; no other source is substituted silently.
- `nextCheckAt`:
  - stale lake: now + 1 cadence;
  - rapid change: max(`freshUntil`, now + cadence);
  - stable lake: max(`freshUntil`, now + 2 h).
  - It is never faster than the source cadence.
- **Registry `staleAfterHours`:** 3.

**Orchestration (no Lake-specific cron):**
- `LakeBrainDescriptor.current` is published in the registry as `orchestration`. It lists the inputs, staleness rules and recompute triggers.
- `LakeBrainPlanner.planState()` is pure and returns PUBLISH or SKIP with reasons, like the Biological Brain's `plan()`.
- `LakeBrainSingleFlight` deduplicates concurrent refreshes of one lake in a process. A cross-instance lease belongs to the future Brain Orchestrator.
- Page loads read RTDB and never compute.

## 11. Storage

| Store | Content |
|---|---|
| `gs://sector-lake-brain` | Private: uniform access, public access prevention enforced, versioning on, us-central1. Created 2026-10-12. Holds `history/{k}/daily.csv`, `baselines/{k}/*.json`, `presence/…` and the prospective prediction ledger `predictions/{yyyy}/{MM}/{dd}/{HHmmss}Z-{runId}.jsonl` (immutable; see `LAKE_BRAIN_PREDICTION_LEDGER.md`) |
| `gs://sector-water-temp-archive/water-temp/tva/{loc}/{date}.json` | The Water Temp lane's hourly TVA archive. **Read-only** for the Lake Brain (shared, approved 2026-10-12; no new TVA poller). Covers GVDA1, WHLA1, WLSA1, PICT1 and NKJT1 since 2026-10-06 |
| Brain RTDB | Summaries only |

## 12. Running it

```bash
swift build --product LakeBrainJob
export SECTOR_GCS_ACCESS_TOKEN=$(gcloud auth print-access-token) SECTOR_BRAIN_ACCESS_TOKEN=$(gcloud auth print-access-token)
# dry run: read the live Brain RTDB (GET only), write files locally, history to the bucket
.build/debug/LakeBrainJob --dry-run /tmp/lake-brain --read-rtdb https://sector-brain.firebaseio.com --archive gs://sector-lake-brain
# first-time history: add --backfill; recompute regardless of plan(): add --force
# publish (needs Michael's approval for the first write): --rtdb https://sector-brain.firebaseio.com
```

Other options:
- `--scope fleet` also writes DISCOVERED profiles and presence for all 621 lakes.
- `--lake ID` limits the run to one lake.

## 13. Known limits (v1 and v2)

- **TVA history** is 2025-01-01 onward (the guide's two years). Pilots stay `INSUFFICIENT` until 2027 and `SUFFICIENT` only in 2030, unless a deeper TVA source is found. That is why `historicalState` is withheld there.
- **No navigation or run-of-river facts.** No reviewed source states them; they stay unknown.
- **Only the 5 pilots are reviewed.** The other 616 lakes are `CANDIDATE` and need probing (§5) before they publish a state.
- **The shared fleet fields** (`stale`, `issueCount`, `hasObservations`) need a cross-brain rule from the platform.
- **A `PROVISIONAL` or `STANDARD` history never says `VERY_UNUSUAL`.** A lake in the `BETA` readiness band with 5–14 years therefore publishes at most `UNUSUAL` (v2). In the hold-out, 17.5 % of `PROVISIONAL` lake-days and 8.7 % of `STANDARD` lake-days sat outside p02–p98, where v1 would have said `VERY_UNUSUAL`.
- **RAPID is rare on quiet lakes.** The 0.25 ft floor held the pooled RAPID rate at 3.5 % in the hold-out, but 59 of 193 lakes fell below the 2 % lower bound (H-C failed on the lake-share part). Treat RAPID as "a large 24 h move", not as a per-lake percentile.
- **Run-of-river and TVA mainstem pools** change daily with operations. Their trend label flips often, and 18 % of their STABLE days sit inside a ≥ 0.5 ft 3-day move (R1 class).
- **Natural lakes are barely tested.** Only 2 natural-surface lakes are in the strict binding set. The natural 0.05 ft floor and the 60-year basis have almost no hold-out evidence.
- **The 72 h trend needs the shared TVA archive** for TVA primaries; without it the label falls back to 24 h and is flagged.
