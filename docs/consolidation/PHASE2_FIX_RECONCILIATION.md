# Phase 2 — Production fix reconciliation (2026-10-12)

Which never-shipped or lost fixes went onto `main`, which were superseded, and which are
preserved for a decision. Base: `main` = production `bc9e09fb` (+ Phase 1 docs).

Rule applied: integrate a change only if it (a) restores a proven regression, (b) is a
sanctioned migration, or (c) is ops tooling with no customer effect. Anything that changes
customer-visible semantics without being a proven regression is **preserved, not merged**,
and listed for Michael.

## Integrated onto `main`

| Source | What | Why it qualifies | Conflict handling |
|---|---|---|---|
| `e88f7002` (fix/level-play-copy) | Falling-water card copy in fish terms | **Regression restore** — served customers 09-17→09-23 (rev 00040-deg), dropped by the 09-23 deploy | clean cherry-pick |
| `23232a49` (fix/forecast-rain-gate) | Rain gate reads the night's window and odds; caps softly; +92-line test | **Regression restore** — same | clean cherry-pick |
| `d4b67085` (fix/forecast-severe-warning-parity) | Tonight's outlook/curve capped like the gauge under an active NWS warning; `ConditionsSnapshot.engineInput` is the one snapshot→input mapping; +test20b | Parity bug fix: two different "tonight" numbers on one screen was a defect, not a semantic; the gauge cap already shipped | Production had since added Stage 2E `resolvedWaterTemp` + `clarityDischarge` to the builder call. `engineInput` now carries the full production list; `/conditions` keeps its single resolution via `engineInput(coordinate:date:resolvedWaterTemp:)` |
| `42032991` (fix/usgs-ogc-migration) | USGS Water Data OGC API first, legacy WaterServices fallback; `USGSWaterData.swift`; recorded-fixture tests | **Sanctioned migration** — USGS retires waterservices Q1 2027 with blackouts from Nov 2026 | Production had moved to AsyncHTTPClient and added the surface-sensor filter and the lake-sensor `sites=` path. Resolution: OGC client ported to `HTTP.get`; OGC used only for plain bbox queries (`sites`/`siteType` stay legacy, exact production semantics); surface filter kept on legacy decode and applied on the OGC sensor pick via `sublocation_identifier` |
| `2c53d64c` + `0df27076` + `a396a6cb` (deploy.sh) | One canonical `deploy.sh`: clean-tree + on-main gate, commit label, candidate tag, smoke test, promote, prod verify, auto-rollback, `--rollback` | Deployment safety tooling; no customer effect until a deploy is run | Reconciled by hand; sizing set to what production runs (cpu 2 / 1Gi / max 30); smoke test only requires fields production emits |
| `487c3631` + `a396a6cb` (`ops/setup_alerting.py`) | Idempotent Cloud Monitoring setup (uptime checks, log metrics, alert policies) | Ops tooling; **not run** in this phase (running it creates monitoring resources) | taken at `a396a6cb` |

### Deploy prerequisite introduced (for Michael)
- `USGS_API_KEY` (api.data.gov) on the Cloud Run service before the next deploy. Without it
  the OGC API rate-limits by IP and the engine **falls back to legacy** — i.e. today's
  behavior — so the merge is safe, but the migration only takes effect with the key.
  Setting a secret on the service is a credential action: left for Michael.

### Known follow-ups created
- `Hydrology/ClarityStateLoader.swift` and `Hydrology/TributaryFlow.swift` still call
  `waterservices.usgs.gov` directly (hydrology path, Guntersville only). Same decommission
  applies; migrate in the Clarity-ownership phase.
- The reconciled `deploy.sh` adds HTTP startup/liveness probes and a `commit=` label on the
  next deploy (runtime-config changes, not source). Note them in that deploy's tag message.

## Superseded (evidence)

| Branch / commit | Superseded by | Evidence |
|---|---|---|
| `32f21c4c` USGS A7.2 (on `feat/lake-environment-snapshot`) | `42032991` | Same migration, 09-19 vs 10-07; no tests/fixtures/doc; A7.2's `USGSWaterData.swift` is 206 lines vs 391; branch preserved on origin |
| `feat/level-play-copy`, `fix/forecast-rain-gate` | integrated above | fully contained |
| `fix/forecast-severe-warning-parity`, `fix/usgs-ogc-migration` | integrated above | patch-equivalent (conflict-resolved) |
| `0f13f0bc` lake-zone Open-Meteo times (hardening) | largely by production | production reads Open-Meteo with `timezone=auto` and has `WaterTemp/LakeLocalDate.swift`; `OpenMeteoTime.swift` never shipped. Re-check only if a TZ defect is reported |
| `a021de86`, `77fa75ab` USGS search sizing / 12 s budget (hardening) | by `HTTP.get`'s 8 s cap and the OGC client | both rewrite `WaterLevelService` fetch internals that no longer exist |

## Preserved, not merged — need Michael's call (customer semantics or build-system risk)

All on `fix/pressure-consistency` (⊃ `feat/engine-hardening`), never deployed, written
2026-09-14/15 against a tree that predates the lake directory, lake gauges, Stage 2E water
temp and Clarity Fusion. Each conflicts with production on 2–12 files; integration means a
re-implementation against today's code, not a cherry-pick.

| Commit | Change | Why it needs a decision |
|---|---|---|
| `0e865d2e` | Never score without weather; cache degraded renders briefly | Changes what customers see when Open-Meteo is down (an error/degraded render instead of a partial score) |
| `abc793f2` | Per-call budgets; every failed input reported as `degradedInputs` | Adds a response field and changes partial-failure behavior |
| `b57cfe7d` | Score the fishing night *in progress* at the lake | Changes which night the gauge scores after midnight |
| `f04ae4e3` | Compute Tonight/nights from the render's own inputs | Removes a second fetch; may shift tonight numbers; touches the deleted `SingleFlightCache` |
| `198d5dce` | Anchor current pressure to the hourly series so the trend can't contradict the chart (+tests) | Consistency fix, but the displayed pressure value changes; cheapest to re-apply (1 file) if approved |
| `f67e42e9` | Hedge Open-Meteo across hosts; log upstream failures; validate Remote Config | Production's `WeatherService` already races two Open-Meteo hosts; Remote Config validation is the live part — re-derive if wanted |
| `4dd43e7d` | Swift 6 language mode, data-race-free engine, `swift-tools-version: 6.0` | Build-system change for the serving image (Dockerfile base is `swift:6.1`, so feasible); needs a Linux build + load test, not a cherry-pick |

Also preserved (Phase 0): `wip/gauge-context-2026-09-14` — gauge role/selection/water
context; changes which gauge drives inputs (has a `gaugeSelection.enabled` kill switch);
never built; belongs to Lake Brain source bindings (Phase 7/8), not to Conditions.

## Not touched (policy)
- `deploy/intel-guardrails-5a` / `feat/intel-guardrails-5a` — customer/policy behavior
  (L7 conservation gate, `policyNotAssessed` fail-closed). Requires explicit approval.
