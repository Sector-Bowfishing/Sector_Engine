# Session record: Weather Brain (new Brain, registered DISABLED)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine (briefing run by hand from the local Cortex checkout; `CORTEX_HOME` unset). The local Cortex HEAD ecaef70 does not match this repository's pin a785035 (reported, not changed). Date: 2026-11-22. Branch: `feat/weather-brain-2026-11-22` off main 0fc0682a. Cloud session; only work covered by the standing approvals (branch, commit, push the branch, open a PR).

## Scope
Owner decision (chat 2026-11-22 19:37Z, recorded on Sector_Ops #51): build the Weather Brain; real measured or official forecast data only, never invented estimates. Deliver one PR: the package, its contract and schema, runtime, tests, provider doc, registration DISABLED, the weather-change signal with pre-stated thresholds, and `docs/brains/WEATHER_BRAIN_PLAN.md`. Not in scope and not done: any deploy, cloud job, execution-control change, IAM, rules, live write, the Lake/Water Temp consumer changes.

## Pattern read before writing
Wind Brain (brain.json, runtime, publish/writer/contract, its NBM reader), the Lake Brain's adaptive freshness (#216, `LakeLevelValidity.swift`, `LakeRainSignal.swift`), the platform control manifest, orchestration decision model, execution control, Publisher registry and knowledge releases, the Depth/Vegetation registration pattern, and the iOS source of truth (`WeatherService.swift` `displayPressureTrend`, `MetricSheets.swift` `cloudWord`, `specs/weather-metric-detail.md`, `specs/conditions-engine.md`). The Engine's own NWS adapter (`NWSWeatherService.swift`, `NWS_WEATHER_ADAPTER_V1.md`) already fixes the NWS meaning rules; the Brain ports them value for value and its tests assert the adapter's own expected values on the same recordings.

## Done
- `brains/weather`: package, operating contract (19 sections), README, `brain.json` (CALIBRATION, customer publication off), contract `weather-state-v1.md` + JSON schema, Publisher-derived `weather-publication-v1.json`, runtime (`sector_weather`, stdlib only), research GAPS/CHARTER, provider doc.
- Pre-stated thresholds `weather-change-thresholds-v1` packaged as a verified knowledge release (`weather-knowledge-candidate-2026-11-22.1`, approval NOT_RECORDED); a tampered or missing release refuses.
- Registration, all DISABLED: `keys.BRAINS` + Swift mirror, `stable_brain_ids.json`, Publisher registry (`weather_specs`), control manifest (`activityState PARKED`, `executionTarget none`, no executor, no job), providers `nws-station-observations` and `nws-forecast-grid`, cutover order (blocked, W-1), identity and security plans (regenerated), engineering-status inputs (W-1).
- Platform behaviour change (one): `data_ownership.deployed_execution_order` orders a deployed Brain the target list does not know just before `biological-state` (was: after Sector Intelligence). Order of the eight existing Brains unchanged.
- Kit V1 certification suite (`tests/test_weather_kit_certification.py`) over a contract-only artifact builder (`publish_artifact.py`, not wired into any write path).
- Tests that pinned eight Brains now list nine; the central-scheduling test names Weather as the one registered-DISABLED Brain.

## Verification
Weather suite (99 offline tests: 48 Brain tests on recorded and hand-built fixtures plus the 51 shared Kit V1 certification proofs and mutations); every platform, orchestrator, scores, publisher, runner, cutover, deploy, verification, architecture, brain-certification and ops suite; knowledge release `--check`; architecture report (no Weather finding); Cortex `ops-check` 0 findings, `data-check` finding count unchanged (161). Two `tools/research` tests fail identically on main in this environment (read-only folder checks while running as root).

## Gaps and decisions
CG-W-1 (CORTEX_GAPS.md): Weather is not a Cortex target Brain (BA-01) and its families are not registry rows. W-1 (decisions.json): activation is a separate owner step list (plan §6).

## Review of #234 at ad0c177a (fixed on the same branch, merged with main after Moon #233)
- Sky code: a station's code is decoded from its own icon/text only (never from the grid's cloud %); the grid gives the code only when the station reports nothing about the sky, labelled `forecastGrid`. This deliberately differs from the Engine adapter, which has the same mislabel (`NWSWeatherService.assemble` passes the grid cover into `NWSCondition.weatherCode` and labels the result an observation; reported, not changed here).
- Missing data = WATCH for every rule (owner decision, Sector_Ops #51 comment 7085207021).
- `lastSuccessfulRun` is never written null; `lastRunOutcome` (SUCCESS / PARTIAL / FAILED) makes a partial run explicit.
- `kind` is `observation` when any tile is observed; `origins` + `mixedOrigin` describe mixed states; `pressure.origin` added.
- The ordering fallback is scoped to Weather (`ENVIRONMENTAL_PENDING_CORTEX`); Moon keeps main's order.
- Thresholds release approval unchanged (NOT_RECORDED).
