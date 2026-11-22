# Session record: Lake Brain USGS reads on the Water Data API (v1), behind a switch that defaults to legacy

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine (briefing run by hand from the local Cortex checkout; `CORTEX_HOME` unset). Date: 2026-11-22. Branch: `feat/lake-usgs-waterdata-v1-2026-11-22` off main 9431f998 (PR #219, the CDEC / CO-OPS / USGS-stage readers, merged; main 12aa532c merged in). Cloud session, owner asleep: only work covered by the standing approvals.

## Scope
Step 1 (Wave 1 + the stage reader of Wave 2 + Wave 3) of the USGS WaterServices → Water Data API migration plan (2026-11-22) for the
Lake Brain only: live level (`LakeLevelFeeds.swift` `usgs`), history (`LakeLevelFeedsFleet.swift` `usgsDaily`, `dv` and the `iv` year
walk) and the gage-height + altitude reader (`LakeLevelFeedsUSGSStage.swift`). Not in scope and not done: the Engine server's
`WaterLevelService` / Clarity / Tributary paths (customer-facing, separate PR after the owner decides), the Python jobs and tools,
deploys, job environment, IAM / secrets, rules, bindings.

## Plan (execution.md §9)
| Finding | Files | Risk | Verification | Rollback |
|---|---|---|---|---|
| Every Lake Brain USGS read times out from 2027-01-11 | new `LakeLevelFeedsUSGSWaterData.swift`; routing in the three readers | Default `legacy` keeps today's requests and answers; `shadow` doubles USGS requests | Swift tests in CI (no toolchain here) | Revert the PR; or leave `LAKE_USGS_API` unset |

## Done
- `LAKE_USGS_API` = `legacy` (default, also unset / empty / unknown) | `v1` | `shadow`, read from the job environment. The legacy readers are unchanged (moved behind the router; the history body is renamed `usgsDailyLegacy`, byte-identical).
- v1 client: `continuous`, `daily`, `time-series-metadata`, `monitoring-locations`; optional `X-Api-Key` from `USGS_API_KEY`; 429 retried twice after a pause; `rel=next` paging with a 20-page refusal.
- Plan differences: D1 series selection (single, else the one Primary, else refused; gage height: more than one refused), D2 both time forms, D3 legacy statistic precedence and refusal of an unserved named statistic, D4 empty 200 / `null`, D10 non-JSON body = failure.
- Shadow comparison with the plan's §5 agreement rule (live, daily, site), one `[usgs-shadow]` line per read, legacy answer served.
- Fixtures hand-built from the published docs, labelled as not recordings; the D1 tests also use the real 2026-10-07 Fort Worth recordings.
- Provider doc section 8.

## Review findings fixed before shadow (same branch, 2026-11-22)
- M1: every v1 failure has a code and reason in the shadow line (`reason=ogc-failed:<code>`, `ogcWhy="..."`); the v1 history reader returns a reason, not nil.
- M2: shadow reads v1 concurrently with legacy, under a 20 s per-read deadline and a 300 s per-run waiting budget; without a key, 3 or more 429s turn shadow off (logged once). Job facts: 3 lakes at a time, reads within a lake sequential, Cloud Run task timeout 60 min, no in-process limit.
- M3: `dv` selects each statistic on its own and drops only the ambiguous ones.
- LOWs: key only to the API host (manual redirects); `dv` matches legacy's fallback statistics; the legacy test suites pin `.legacy` and an offline v1 client; field values escaped; `DailyLevel` cannot carry the statistic (documented).

## Knowledge release
`LakeSourceBindings.swift`, `LakeGeneratedBindings.swift` and `LakeSourceBindingsGenerated.swift` are unchanged: the switch is an environment variable outside the packaged release. `build_release_manifest.py brains/lake/runtime --check` OK (`lake-knowledge-2026-11-22.1`). No new release id.

## Verification
- No Swift toolchain in this container (swift.org and Docker Hub refused by the egress proxy): Swift build and tests run in CI (`swift-tests.yml`, macOS + Linux) on the PR.
- Python: `brains/lake` and `verification` suites pass; knowledge manifest `--check` OK.

## Closeout (operating contract section 19)
Gap: the Lake Brain's USGS reads stop working when WaterServices slows to 10 s (2027-01-11). Bowfisher decision: none (default unchanged). Score unchanged.
Not changed: live systems, schedulers, job environment, bindings, served values, rules, IAM.
Open (owner): `USGS_API_KEY` for the Lake Brain job (IAM); recording real v1 fixtures from an allowed runner; setting `LAKE_USGS_API=shadow` on the job (a deploy/env change); the flip to `v1` after the promotion gate.
