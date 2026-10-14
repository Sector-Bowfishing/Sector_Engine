# BRAIN_SPEC — Lake Brain (Sector Brain Model v1 conformity pass, 2026-10-13)

One conformity pass against the Sector Brain Model. It documents what exists; it changes no rubric, threshold, lifecycle or validation status and restarts no research.
Sources: `LAKE_BRAIN_PRODUCT_RESET_REVIEW.md`, `LAKE_BRAIN_VALIDATION_READINESS.md`, `LAKE_BRAIN_PRODUCTION_READINESS_MATRIX.md`, `LAKE_BRAIN_INTEGRATION.md`,
`LAKE_BRAIN_CROSS_BRAIN_CONTRACTS.md`, `LAKE_BRAIN_OPS_VISIBILITY_GAP.md`.

| Section | Lake Brain |
|---|---|
| Brain ID | `lake-brain` (slot `lake`) |
| Mission | Know each lake's water level now, against its own history and the operator's pools, and say how fresh and how sure that is. |
| Bowfishing decision improved | *Which lake, and when*: is it high/low/normal for the season, rising or falling, how fast, is the data current. For flood-controlled lakes, where it sits against the operator pools. |
| Owns | lake identity and context, current level, operator pool context, seasonal lake behaviour, flood/drawdown context, species presence on the lake profile |
| Does not own | water temperature, clarity, wind, depth (effective depth is Depth's), vegetation, species response (Biological), synthesis (Intelligence) |
| Upstream | providers only: TVA RestApi, USACE CWMS and Access2Water, USGS NWIS, USBR RISE, NWS NWPS, CO-OPS; TWDB built but gated off. No upstream Brain. |
| Downstream | Sector Intelligence (restates level and trend), Depth (pool elevation, reference pool, datum, freshness), Vegetation (level delta). Customer path consumes nothing from Lake Brain yet (`consumedByCustomerPath: 0`). Gaps in the contract: `LAKE_BRAIN_CROSS_BRAIN_CONTRACTS.md`. |

## Claims by level and claim-level maturity
| Claim | Level | Maturity | Evidence |
|---|---|---|---|
| Current pool elevation, source id, observation time | 1 | PROVIDER_VERIFIED (5 reviewed pilots; 196 machine-verified candidates not yet accepted) | units/datum/freshness checked; cross-source agreement 123 pairs, median 0.015 ft |
| Operator guide curve, normal pool, flood-pool bottom | 1 | VERIFIED_WHERE_AVAILABLE | operator-published only; UNKNOWN where none (e.g. TVA publishes no flood-pool bottom) |
| Difference from guide / normal pool; operator zone | 2 | DETERMINISTIC_VERIFIED | rules v2 conformance fixtures; Swift matches the Python mirror |
| 72 h mean-rate trend label (STABLE/RISING/FALLING) | 2 | DETERMINISTIC_VERIFIED; H-D (label stability) PASS, narrowly | floors 0.10 ft reservoirs, 0.05 ft natural |
| Historical state NORMAL / UNUSUAL against the lake's own history | 3 | CALIBRATION | H-A PASS (80.4 %), H-B PASS (0.0529); tier rules gate VERY_UNUSUAL to ≥ 15 y |
| RAPID change flag | 3 | NOT_VALIDATED (H-C FAIL preserved: 66.8 % vs 70 %) | still published for the pilots; withholding is a Michael decision |
| Species presence on the profile | 3 | separate evidence rules, outside the level score | private research bundle, not in Git |

A failed Level-3 claim (RAPID) does not make the Level-1/2 fields unusable.

## Canonical runtime state (small, compact)
`/lakes/{key}/states/lake`: level state, historical state, trend, rate, differences, freshness (`stale`, `nextCheckAt`), source, qualityFlags, `rulesVersion`, `bindingVersion`,
`baselineMethod`, `profileHash`. `/brains/lake-brain`: registry with `breakdowns` (incl. `fleetBindingStatus`), `predictionLedger`. `/scores/lake-brain`: score, uncapped, gates, dimensions.
**Not published yet (gaps):** `confidence`, a drought state, the reference-pool value (only a pointer), `datum` for 4 of 5 pilots. Runtime reads only `history/` and `baselines/` (small per-lake files) and the provider
APIs; it never opens the research warehouse.

## Confidence, UNKNOWN and refusal policy
UNKNOWN / `INSUFFICIENT_HISTORY` / `UNAVAILABLE` are valid and used: no VERY_UNUSUAL under 15 complete years; no level state from a proxy gauge (trend only); no flood state where the operator publishes
none; a lake with no REVIEWED binding publishes nothing. A numeric `confidence` is a proposal (P1) in the cross-Brain contract, not published.

## Freshness policy
State is stale when the source is more than two cadences past due or the published state is older than 3 h (`staleAfterHours: 3`). TVA 48 h window; CWMS/USGS ~hourly; RISE ~48 h latency;
Access2Water latest only. History for a baseline may lag a day.

## Execution model
| Component | Current trigger | Recommended trigger | Needs schedule? | Fingerprint? | Reason |
|---|---|---|---|---|---|
| Provider ingestion | inside the lake-brain job, per due lake | same | Cadence is the providers' (A) | yes: `nextCheckAt` per lake | each lake read only when due |
| Brain compute (`lake-brain` job) | `brain-orchestrator` hourly wake-up (`:50` UTC) starts it when the Brain is stale, due, or a version changed; observed ~every 4 h | keep; at fleet scale, shard by provider group | one cheap hourly wake-up only (C, D) | yes: `profileHash`, rules/binding version, input times; "SKIP: published state is current" | state can go stale with time |
| Baseline recompute | every run (old) → content fingerprint + weekly recompute + `latest.json` (new, awaiting deploy) | fingerprint-driven, weekly | no | yes (SHA-256 over inputs) | cuts baseline objects ~86 % |
| Validation logging (prediction ledger) | each lake-brain run that publishes | same, create-only objects | Timed snapshots (B), no extra schedule | n/a (append-only) | prospective evidence clock started 2026-10-13T18:53:14Z |
| Monthly ledger scorer | manual | scheduled monthly **after Michael approves** (commands prepared, not run) | yes once approved (B) | n/a | first run 2026-11-01 |
| Score publication | orchestrator after a Brain change, `--write --if-changed` | same; stale deployment must not replace a newer score (durability protections on `feat/orchestrator-wind-score-durability`) | no | content fingerprint | durable, no churn |
| Control-plane publication | same cycle as score | same | no | content fingerprint | Ops reads cached state only |
| Maintenance / health | health block each run | same | covered by the hourly wake-up | n/a | lightweight |

Maximum acceptable state age 3 h. Fleet scope today: reviewed lakes only (5). A customer page view never triggers provider fan-out or recompute.

## Score dimensions
Rubric `lake-brain-score-v1` (unmodified): coverage 20, validation 15, sourceAuthority 15, historyQuality 15, operatorPlan 10, seasonalBaseline 10, trendQuality 10, floodDroughtContext 5.
Gates: coverage < 10 % caps 3.0; NOT_VALIDATED caps 5.0. **Critical dimensions** are not published by the Engine; PROPOSAL (Option A, needs Michael): validation, sourceAuthority, historyQuality, seasonalBaseline, trendQuality.
Rubric mismatches (proposals, nothing applied): per-claim validation; flood-pool denominator; lighter review for machine-corroborated provider bindings.

## Lifecycle
Published status `CALIBRATION` (validation NOT_VALIDATED), unchanged. Against the common lifecycle this is a SHADOW/CALIBRATION Brain: it runs internally, no customer dependency, evidence for its Level-3 claims
accumulating. No promotion is proposed or made. Production requires overall ≥ 8.0 and every critical dimension ≥ 7.5 (policy unchanged).

## Storage, cost, runtime
Research directory 1.0 GB after cleanup (review threshold 5 GB / 2 GB per dataset); largest retained item is a 214 MB NHD query cache. Runtime payloads are small (per-lake history ≈ 1.7 MB, baseline ≈ 90 KB).
Job: 70–148 s per run for 5 lakes, about $0.0019 per run, 1 GiB memory limit (peak not measured). Growth estimates in `LAKE_BRAIN_STORAGE_LIFECYCLE_AND_COST.md`. A 196-lake run is modelled at 485–1,374 s against a 900 s timeout (raise before batch C).

## Research stop conditions
Provider fields: stop at source, units, freshness, sanity. Derived fields: stop at formula and edge cases. Level-3: stop at the pre-registered criteria. No new research without a product question; paused: TWDB,
shoreline slope in Lake, plan/flood evidence hunting beyond operator-published values.

## Ops summary and customer exposure
Ops reads `/control/overview` (cached). After the next orchestrator deploy it also receives the underlying score, gates and dimensions (`LAKE_BRAIN_OPS_VISIBILITY_GAP.md`). No customer exposure; weak claims (RAPID) must not
reach customers before H-C passes prospectively.
