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
                          "coveragePct": 100, "yearsCovered": 1, "baselineStatus": "INSUFFICIENT",
                          "baselineMethod": "doy15-percentile-v1", "baselineVersion": "…",
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
  "seasonalPercentile": 8.6, "rateOfChangePercentile": 55, "rapidChangeThresholdFt": 0.25,
  "seasonalBand": { "p02": 643.34, "p10": 649.89, "p50": 655.58, "p90": 660.54, "p98": 661.89,
                    "basisYears": 30, "windowDays": 7, "sampleCount": 450 },
  "baselineStatus": "SUFFICIENT",
  "facts": [ "649.32 ft at Oct 12, 7:00 PM EDT (USGS 02187010).", "…" ],   // ordered, factual, no fish wording
  "freshness": { "generatedAt": "…", "sourceObservationAt": "…", "freshUntil": "…", "nextCheckAt": "…",
                 "stale": false, "refreshReason": "scheduled: stable lake, 2 h" },
  "provenance": { "brainId": "lake-brain", "brainVersion": "1.0.0", "modelVersion": "lake-level-rules-v1",
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
- A state is published only from a **reviewed** binding (`LakeSourceBindings.swift`, version `bindings-2026-10-13.1`).
- Every other lake gets a `CANDIDATE` class. A candidate never publishes a state.

### 5.1 Where bindings come from

| Set | Source | Status |
|---|---|---|
| Pilots (5) | hand-written in `LakeSourceBindings.handWritten` (probed by hand 2026-10-12) | `REVIEWED` |
| Generated (196 rows; the 5 pilots among them stay hand-written, so 191 candidates) | `jobs/lake-brain/data/bindings.proposed.v1.json` -> `scripts/generate-lake-bindings.py` -> `LakeSourceBindingsGenerated.swift` | `CANDIDATE`, unless the lake is in `accepted_batch.json` |

`LakeSourceBindings.binding(for:)` returns the hand-written pilot first, then the generated row. `LakeSourceBindings.reviewed` (the only list a run publishes from) holds `REVIEWED` rows only; `LakeSourceBindings.candidates` holds the rest. The runner, the planner and the classifier each require `.reviewed` independently, and a normal run's scope is the reviewed lakes only.

**The version bump.** `bindings-2026-10-12.1` -> `bindings-2026-10-13.1`. The planner compares the published binding version with the current one, so the five pilots **republish once** on the first run after this change (new profile fields: identity pointer, context features, source text). Their states do not change. Accepting a batch adds the suffix `+accepted.<n>.<fingerprint>`, which republishes the lakes again once.

### 5.2 The proposed table (`build_bindings_table.py`)

`jobs/lake-brain/bindings/build_bindings_table.py` is reproducible from the cached research data (no network): it reads `verified_bindings_v2.csv`, `plan_flood_evidence.csv`, `lake_features.csv`, `history_extension.csv` and the bulk probe data (inputs and their sha256 are recorded in the output) and writes the proposed table plus `bindings.proposed.v1.excluded.json`.

**Eligible** = Michael's final decisions: only STRICT rows (waves `w1` and `w2-v1`, status `VERIFIED` or `VERIFIED_CORROBORATED`, `binding-review-v1` as pre-registered); never v1.1 extensions, R7h / `VERIFIED_ENVELOPE` or other post-hoc promotions; Clinton Lake|IL excluded; allow-listed providers only (`tva, cwms, cwms-saw, usgs, a2w, rise, nwps, twdb`; HADS/IEM only as a history source); no lake whose directory coordinate is flagged (`point_flag != ok`); not one of the 57 wave-1 flagged rows (including Red Lake|MN, which the wave-2 audit re-labelled); and not one of the 14 lakes whose research history series differs from the live series by more than 15 ft (rules-v2 hold-out QA: held back "pending datum resolution", no offset guessed).

| | Count |
|---|---|
| Research-bound lakes (rows in `verified_bindings_v2.csv`) | 427 |
| **Proposed (MACHINE_VERIFIED)** | **196**: a2w 75, cwms 42 (incl. 1 `cwms-saw`), usgs 28, nwps 21, rise 19, tva 11 |
| Excluded | 231: post-hoc / not strict 130, coordinate flag 58, flagged 19, history/live mismatch 14, undocumented provider 9, wave-1 flagged 1 (primary reason; every reason is listed per lake) |
| History | 176 SUFFICIENT (>= 5 complete years), 6 LIMITED, 14 NONE |
| Operator plan evidence (strict, verified match) | 125 lakes: 84 with a guide curve or a zone, 111 with a flood-pool bottom |

The five pilots are reproduced (asserted on every build): the four TVA rows exactly; Hartwell with the same station + parameter (`usgs 02187010 00062`, the hand-written fallback; the machine probe found the CWMS pool feed silent) and the same CWMS daily history.

**Time zones.** `timeZone` is the lake's state with a longitude/latitude refinement for states that straddle a boundary (documented in the script; the 5 pilots keep theirs). It sets the lake-local day of the history and the baseline.

**Live fallbacks.** Other series of the same lake that independently passed `binding-review-v1` (R1-R8) in the research candidate table, on an adapter-backed provider, at most two. A fallback is never silent (`primarySourceStale`, `fallbackSource`, `fallbackDatumDisagreement`).

**History.** The series the research history table used: `cwmsDaily`, `usgsDaily` (daily values or instantaneous reduced to a daily median; a gage height only with its datum offset), `riseDaily`, `hadsDaily` (IEM HADS, NWPS gauges), `tvaOperatingGuide`. Composites list the lowest precedence first (the runner's merge lets the last entry win a date). The complete-year counts are the research's (`historyCompleteYears`, `historyClass`); a research extension the Brain cannot read (NWS RVDHUN text, CO-OPS) falls back to the base series, and the count follows.

**Operator plan evidence** appears only where `plan_flood_evidence.csv` has `verifiedMatch` and a strict column (`planStrict`: a seasonal guide curve, or a zone with BOTH a top and a bottom; `floodStrict`: an operator flood-pool bottom). Each level is `{name, value | ref, source}`: constants are embedded (`static`), seasonal levels are read each run (`a2w` from the district listing already fetched for the live value, `cwmsLevel` from `/levels/{id}/timeseries`, `cwmsSeries` for a CWMS `Elev-Guide Curve` series). A guide series that stopped publishing is not claimed. They flow into the state's `operatingZone`, `guideFt`, `operatorLevels` and `floodPoolState` through `LakeGuideSource.operatorLevels`; the pilots are unaffected.

### 5.3 The acceptance gate

1. Michael reviews the proposed table (sampled review, flagged rows first; see `docs/research/lake-brain/LAKE_BRAIN_MICHAEL_ACTION_QUEUE.md`).
2. A work package writes `jobs/lake-brain/data/accepted_batch.json` **only after that review**. Formats: a JSON array of lakeIds, an array of `{"lakeId": ...}`, or `{"lakeIds": [...], "reviewedAt": "YYYY-MM-DD", "reviewedBy": "..."}`. The file does not exist today; a missing file is an empty list.
3. `python3 scripts/generate-lake-bindings.py` embeds the ids. It refuses an id that is not in the proposed table (or was excluded). `LakeGeneratedBindings.make(records:accepted:)` is the only place a status is decided: `.reviewed` iff the lakeId is accepted.
4. Tests prove the gate (`LakeBrainBindingsTests`): with the real (empty) batch no generated binding is reviewed and a candidate triggers no fetch, no plan and no state, even with `force`; a synthetic batch flips exactly its ids.

Nothing in this change publishes to any RTDB or bucket, and nothing is deployed.

### 5.4 Provider adapters

`LevelSeriesRef.Provider` is `tva | cwms | usgs | a2w | rise | nwps` (`LakeLevelFeedsFleet.swift`; provider table, traps and live dry-run results in `docs/brains/LAKE_BRAIN_PROVIDERS.md`). TWDB has no strict lake in the proposed table, so it has no adapter yet.

### 5.5 Candidate dry run

`LakeBrainJob --dry-run DIR --include-candidates [--lake ID]...` evaluates CANDIDATE bindings as if reviewed: local files only (history archive `DIR/_archive`; a `gs://` archive is refused; `--rtdb` is refused; the shared TVA archive is not read), every output marked `dryRunCandidate` (state quality flag, profile note, `bindingStatus` stays `CANDIDATE`). Every run, candidate or not, also flags `historyLiveMismatch:+/-Nft` and records an error when the seeded history of the last 365 days has a median more than 15 ft from the live level (a series/datum mismatch that would give a wrong "unusual" label).

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

## 6. Baselines (`doy15-percentile-v1`)

**Daily history** is one value per lake-local day:
- TVA: the guide's midnight elevation. Each run merges it forward, so history grows past TVA's 2-year window.
- CWMS: the district's published daily value.

**Basis years** are the most recent **30 complete calendar years**. A year is complete when it has ≥ 90 % of its days (329).

| Status | Rule |
|---|---|
| `SUFFICIENT` | ≥ 5 complete years |
| `LIMITED` | 2–4 |
| `INSUFFICIENT` | some history, < 2 |
| `NONE` | no history |

**Level climatology:**
- For each day of year: every basis-year value within ±7 days, which is 15 days.
- Stored as a quantile grid (0, 2, 5, 10 … 95, 98, 100), type-7 interpolation.
- Built only with ≥ 2 basis years.

**Rate climatology:**
- |Δ24h| between consecutive days, same window, every year in the last 30 (partial years included).
- Kept only when the window has ≥ 20 samples. Otherwise the flag is `rateBaselineUnavailable`.

**Artifacts:** `gs://sector-lake-brain/baselines/{k}/{baselineVersion}.json`, where `baselineVersion = method@historyEnd#fingerprint`. Each is written once, so artifacts are immutable.

**Method cross-check (not validation).** For Hartwell on Oct 12, the 30-year band is p10 649.89 / p50 655.58 / p90 660.54. The CWMS-published period-of-record series (1962+) is 649.09 / 655.90 / 660.90. The gap is the expected basis difference.

## 7. Classification rules (`lake-level-rules-v1`)

| Field | Rule |
|---|---|
| `levelState` | **Operator first.** Above the operator's flood-pool bottom (CWMS top of conservation) → `FLOOD_POOL`. Below the operator zone → `BELOW_ZONE`, above it → `ABOVE_ZONE`, inside → `IN_ZONE`. No operator zone → `UNKNOWN`. |
| `historicalState` | `SUFFICIENT` baseline only: inside p10–p90 → `NORMAL`; outside → `UNUSUAL`; outside p02–p98 → `VERY_UNUSUAL`. Otherwise `INSUFFICIENT_HISTORY` |
| `trendState` | Δ24h from the hourly series (±90 min). **Rapid** when \|Δ24h\| > this lake's seasonal p95 \|Δ24h\|. **Stable** when \|Δ24h\| ≤ max(0.10 ft, seasonal p50). Otherwise `RISING` / `FALLING`. Without a rate baseline there is no rapid, and the floor is 0.10 ft. With a non-SUFFICIENT baseline the flag is `rateBaselineLimited` |
| `floodPoolState` | Only where the operator publishes a flood-pool bottom (CWMS). Otherwise `UNKNOWN` with flag `noOperatorFloodPoolThreshold`. TVA's `TopOfGates` is not a flood pool |
| `differenceFromNormalPoolFt` | Only for directory `poolBasis = fullPool` with confidence med/high. Natural-lake surfaces never get one |
| `change` | Δ over 1 h / 6 h / 24 h / 3 d / 7 d. The tolerances are ±20 / 45 / 90 / 180 / 180 minutes. Absent when no reading falls in the window |

Each classification is its own field; none is folded into another.

**The STABLE rule (0.10 ft floor, seasonal p50)** fills a gap the approved decisions left open. It is an Engine choice and versioned with the rules.

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
| `BETA` | `OBSERVED` + operator guide + `SUFFICIENT` baseline: every classification computed, not validated |
| `DEGRADED` | Reviewed source, but the current reading is stale or unavailable (last value kept and flagged) |
| `VALIDATED` / `PRODUCTION` | Not used until classification checks exist |

**Brain status:** `CALIBRATION`. `/validation/lake-brain` reads `NOT_VALIDATED`.

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
| `gs://sector-lake-brain` | Private: uniform access, public access prevention enforced, versioning on, us-central1. Created 2026-10-12. Holds `history/{k}/daily.csv`, `baselines/{k}/*.json` and `presence/…` |
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
- `--include-candidates` (with `--dry-run` only): evaluate the CANDIDATE bindings, see §5.5.

## 13. Known limits (v1)

- **TVA history** is 2025-01-01 onward (the guide's two years). Pilots stay `INSUFFICIENT` until 2027 and `SUFFICIENT` only in 2030, unless a deeper TVA source is found. That is why `historicalState` is withheld there.
- **No navigation or run-of-river facts.** No reviewed source states them; they stay unknown.
- **Only the 5 pilots are reviewed.** 191 generated bindings (the 196-row table minus the 5 pilots, which stay hand-written) are `CANDIDATE` until `accepted_batch.json` exists (§5.3); the other lakes have no binding (research: unbound, post-hoc only, or held back for a flagged coordinate, an undocumented provider or a history/live series mismatch).
- **A2W gives the latest value and its 24 h change, not a history**: 1 h / 6 h / 3 d / 7 d changes are unknown for A2W-primary lakes.
- **Daily sources** (RISE about 48 h latency; CWMS daily series) are stale after `lag + 3 x cadence`; operator levels from Access2Water are today's value only.
- **HADS history** is rate-limited by IEM (one request per 15 s, 3-year chunks): a first seed of a 15-year NWPS lake takes minutes.
- **The geometry pointer** (`identity.geometry`) names a registry URL another service creates; nothing here reads it.
- **The shared fleet fields** (`stale`, `issueCount`, `hasObservations`) need a cross-brain rule from the platform.
