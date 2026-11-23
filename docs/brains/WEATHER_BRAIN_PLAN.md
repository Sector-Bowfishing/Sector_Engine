# Weather Brain plan

Owner decision: chat 2026-11-22 19:37Z, recorded on Sector_Ops #51: build the Weather Brain; real measured or official forecast data only,
never invented estimates. Package: `brains/weather` (`brainId: weather`). Status: **CALIBRATION, registered DISABLED, customer
publication off.** Merging the package changes nothing at runtime (§6 step 0).

## 1. What it answers

Per lake, for all 621 directory lakes: the app tiles **Sky** (cloud cover, precipitation), **Barometric Pressure** (with the 3 h trend),
**Air Temperature** and **Humidity**, with the iOS app's meaning (contract: `brains/weather/contracts/weather-state-v1.md` §2), and the
**weather-change signal** (CHANGE / WATCH / STEADY) that Lake and Water Temp refresh on. Not wind (the Wind Brain), not a score, not a
recommendation.

## 2. Data

| Need | Source | Notes |
|---|---|---|
| Pressure, air temperature, humidity, dew point, present weather, last-hour precipitation | NWS station observations (`api.weather.gov/stations/{id}/observations`), the 3 nearest ASOS/AWOS stations NWS lists for the lake's grid cell | 13 h window per run; selection rules ported from the Engine NWS adapter (`docs/architecture/conditions/NWS_WEATHER_ADAPTER_V1.md`) so the Brain and `/conditions` read NWS identically |
| Cloud cover %, next-12 h temperature / humidity / dew point / cloud / precipitation probability, forecast rain | NWS forecast grid (`/gridpoints/{wfo}/{x},{y}`), which is the NBM-based NDFD | official forecast, labelled `forecastGrid` |
| Lake list and coordinates | Engine `GET /lakes` (Lake Registry) | |

- **NBM:** the Wind Brain reads NBM GRIB2 for wind only (`noaa-nbm-v5`: 10 m wind, gust, quantiles). Reading NBM temperature / sky from
  GRIB here would duplicate the NBM-based NWS grid with a heavier decoder, so v1 uses the NWS grid. Whether an NBM GRIB field could
  supply a pressure forecast is not verified (gap WX-003). Revisit only if the grid's hourly values prove insufficient in §5.
- **Pressure forecast:** none. The NWS grid has no pressure layer; the state says so (`pressure.forecast: null`, gap WX-003).
- **Terms:** U.S. Government data, public domain; a self-identifying User-Agent is required; documented API; no key or account. This
  meets the owner's source-access rule (`brains/weather/docs/NWS_PROVIDER.md`).
- **Requests:** `/points` + station list once per lake per 30 days (cached); per run one grid read per distinct grid cell and one
  observation read per distinct station among the due lakes. At most about 2,500 requests in a full-directory hour, paced 0.25 s.

## 3. Cadence

The Lake Brain's adaptive freshness (#216), with the tier taken from the weather-change signal (contract §5):

| Tier | When | Current for (from the observation) | Recomputed |
|---|---|---|---|
| CHANGE | an observed event fired | 90 min (held to run + 75 min) | every hourly grant |
| WATCH | rain forecast within 6 h, or a 3 h rule could not be evaluated | 150 min | every hourly grant |
| STEADY | every rule evaluated, none fired, no rain forecast | 240 min | at most every second grant |

Hard limit: an observation older than 4 h is never current. Brain level: `dueAfterHours 0.75` (every hourly Orchestrator grant),
`staleAfterHours 3`. The per-lake planner fetches only lakes whose `nextCheckAt` is reached, so a steady night costs about half the
requests of a changing one.

## 4. How Lake and Water Temp consume the signal (not wired in this PR)

Both read `/lakes/{k}/states/weather/weatherChange` (`level`, `events`, `signature`). The registry projection
`/brains/weather/weatherChange` (`changeLakeCount`, `signature` over the CHANGE lakes) is a declared material field, so the Orchestrator
sees a material change when a lake enters or moves within CHANGE.

- **Lake.** Manifest: an OPTIONAL dependency `{"id": "weather", "usesFields": ["weatherChange"], "onStale": "DEPENDENCY_STALE"}` and
  `DEPENDENCY_CHANGED` in Lake's allowed triggers. Per lake, `LakeLevelValidity` treats Weather `CHANGE` with `RAIN_ONSET` or
  `FRONT_PASSAGE`, or a `RAIN_EXPECTED` event, as at least the CHANGING tier and sets `nextCheckAt` to the next grant. Lake's own QPF read
  (`nws-forecast-qpf`) can later be replaced by `sky.rain.forecastNext12hIn` (same source, same proportional-overlap rule),
  removing a duplicate NWS read. An absent or stale Weather state changes nothing: Lake keeps its own rule.
- **Water Temp.** Manifest: the same OPTIONAL dependency, `DEPENDENCY_CHANGED` allowed, and `dueAfterHours ≤ 6` so every lake is
  refreshed at least every 6 h. Per lake, the run recomputes a lake early when its Weather `level` is `CHANGE` and the `signature` differs
  from the one recorded in the lake's last Water Temp state; otherwise every 6 h.
- Each consumer change is its own PR with its own review, because it changes that Brain's runtime decisions.

## 5. Validation (pre-registered 2026-11-22, before any data)

Data is captured prospectively from activation day (the observation API keeps about 7 days; nothing can be back-filled). Raw pairs go to
the research workspace `weather-brain`, never to Git. Thresholds, metrics and windows below are fixed now; a failed criterion keeps the
gap open and is reported, it is not tuned away.

### 5.1 Fidelity (the "never invented" check)
Every published pressure and air temperature is re-read from the same station's observation API within 6 h. Pass: ≥ 99.5 % of values
match the station's own value at the same timestamp (pressure within 0.05 hPa after the recorded offset, temperature within 0.1 °F), and
100 % of published values carry a station and an observation time. Window: first 14 days, all lakes.

### 5.2 Representativeness (WX-001)
Truth: an **independent** station, the nearest station NWS lists for the lake's grid cell that the Brain did not use, within 25 mi; lakes
without one are excluded and counted. Pairs: the Brain's published value and the independent station's observation within ±30 min.
Pressure is compared altimeter-to-altimeter (raw `barometricPressure`) so the SLP offset cannot mask a difference.

| Metric | Pass | Why |
|---|---|---|
| pressure MAE | ≤ 1.0 hPa | about two thirds of the app's 1.5 hPa 12 h trend band |
| 3 h trend class (rising / falling / steady at ±0.02 inHg) agreement | ≥ 80 % | the tile trend must describe the area, not one instrument |
| air temperature MAE | ≤ 3.0 °F | well under the 8 °F swing the signal reacts to |

Window: 30 days from activation. Minimum sample: 500 pairs and 20 lakes; below that the result is INSUFFICIENT, not PASS. Reported
overall and by state kind (`seaLevel` vs `altimeter`) and by station distance (< 10 mi, 10-25 mi).

### 5.3 Change signal (WX-002)
Window: 60 days from activation, all lakes with a STEADY/CHANGE history.
- `RAIN_ONSET`: truth = the independent station (5.2) reports ≥ 0.01 in in the last hour within ±2 h. Pass: POD ≥ 0.8, FAR ≤ 0.3.
- `FRONT_PASSAGE`: truth = an NWS Weather Prediction Center surface analysis front (coded surface bulletin) passing within 50 mi of the
  lake within ±3 h. Pass: POD ≥ 0.6, FAR ≤ 0.4.
- `PRESSURE_*_FAST`, `AIR_TEMP_SWING`: arithmetic on measured data; checked by 5.1, not scored here.
- Also reported (no pass mark): CHANGE-hours per lake per week, the refresh load it would put on Lake and Water Temp.
A failure produces a `weather-change-thresholds-v2` proposal with its reason and a new knowledge release; v1 results are kept.

### 5.4 Amendment 2026-11-23: retrospective grading on past data (WX-RETRO-2026-11-23)
§5 waits for activation because the NWS observation API keeps about 7 days. The same METAR reports are archived by the Iowa
Environmental Mesonet, and WPC coded surface bulletins are archived as NWS text products, so §5.1–§5.3 can also be graded **now** on a
past window by replaying the Brain's own pure logic (`reading.assemble`, `signal.evaluate`) at hourly instants. The protocol was
pre-registered and hashed before any data was fetched:
[`weather-retro-validation/WX-RETRO-2026-11-23.protocol.json`](weather-retro-validation/WX-RETRO-2026-11-23.protocol.json)
(sha256 `6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8`, commit `c8d2e526`). Runner: `tools/research/weather_retro_validation.py`.

- **Same criteria, same marks** as §5.1–§5.3; windows 2026-11-05→11-19 (5.1), 2026-10-20→11-19 (5.2), 2026-09-20→11-19 (5.3), all UTC.
- **Station rule as the Brain selects it:** the first 3 NWS-listed stations; the independent station is the nearest other NWS-listed
  station within 25 mi with archive data.
- **Added by the amendment (not in §5):** a substitution check (R-SUB: the archive must reproduce the NWS API's reports for the last 7
  days, otherwise no criterion may be reported PASS); a 5.3 minimum sample (30 truth and 30 Brain events per kind, 10 lakes); WPC bulletins
  at 0.1° resolution only; RAIN_EXPECTED, cloud cover and WATCH shares are not replayed (no archive of the NWS forecast grid).
- **What it cannot do:** retrospective 5.1 replays the reading logic; it does not test the live publication path. Prospective §5.1 on
  published values, and a prospective WX-001 window, remain the confirmation. How retrospective results map to `/validation/weather`
  is an owner decision (protocol `resultStates.rubricMapping`); nothing here writes that node or changes a score.

## 6. Rollout (each owner step is separate; none is done by this PR)

0. **This PR.** Package, contract, tests, Publisher registration and control-manifest entry with `activityState PARKED`,
   `executionTarget none`, no executor, no cloud job, absent from `/control/executionControlV1` (absent = disabled), `run.py --write`
   refusing. Merging changes nothing at runtime.
1. **Read-only dry run** (pre-approved read-only check; a cloud session, never the MacBook): `run.py --dry-run` on 10 lakes, then all
   621. Record request count, run time, BLOCKED count, state kinds, and the CHANGE / WATCH / STEADY mix with the `unknown` reasons behind
   each WATCH: every rule that cannot be evaluated is WATCH (owner decision 2026-11-22), so a high WATCH share measures data gaps, not
   weather, and must be read before Lake and Water Temp consume the signal. No database write.
2. **Owner: thresholds release approval** (`weather-knowledge-candidate-2026-11-22.1`, now NOT_RECORDED), or explicit acceptance of
   internal use without it.
3. **Cortex maintenance session:** register the Weather families (`/lakes/{k}/states/weather`, `/lakeFleet/{k}/…/weather`,
   `/brains/weather/{child}`, `/validation/weather`) and add Weather to the target Brain architecture (BA-01 needs owner direction and a
   Cortex release); then re-sync the Engine mirror `data_ownership.json` (CG-W-1). In the same reviewed change, register Weather as the
   producer of the Signal Registry's DECLARED signals it serves (`platform/registries/signals/signals.json`: `barometric-pressure`,
   `pressure-trend`, `precipitation`, `air-temperature`, `humidity`, `cloud-cover`); until then any consumer of those signals stays
   UNAVAILABLE.
4. **Live writer PR:** a Publisher artifact (or the platform client, as Water Temp) behind the registration above, plus `deploy/`
   (`deploy-job.sh` refusing without approval). Independent review.
   **Prepared 2026-11-23** (branch `feat/brain-writers-weather-moon-generation-2026-11-23`): the platform client (`run.py --write`, as Depth
   and Generation), `deploy/` and an inert orchestrator executor. Nothing is enabled; the steps that remain are in §6.1.
5. **Owner: create the `weather-brain` Cloud Run job** (cost: the manifest cap, 2 USD/month), set the NWS contact User-Agent
   (`SECTOR_WEATHER_USER_AGENT`), then a manifest PR: `executionTarget` `cloud-run-job` started by the orchestrator, an `EXECUTORS` entry,
   `activityState ACTIVE`.
6. **Owner: enable** with the execution-control CLI (`tools/ops/execution_control.py`, `--brains … weather`, an approvalRef). Validation
   capture (§5) starts that day.
7. **Consumers:** the Lake and Water Temp PRs of §4, after at least 7 days of Weather states with no FAILED run.

### 6.1 How to turn it on (prepared, all inert today)

Nothing below has been done. Each step is the owner's or a reviewed PR; the order matters. Cost: the manifest cap is **2 USD/month**
(`schedule.exception.maxMonthlyUsd`); the execution control also bounds each day (`maxCostPerDay`, default 1 USD).

| # | Who | Action | What it flips |
|---|---|---|---|
| 1 | Session (pre-approved read-only) | Step 1 dry run on all 621 lakes; record requests and run time. **Cost check:** the job's point cache (`--point-cache /tmp/...`) is ephemeral, so every run re-resolves `/points` and `/stations` (about 2 x 621 extra NWS requests at 0.25 s pacing). If one run exceeds about 2 min, the 2 USD cap is at risk. **Open owner decision before step 7:** persist the point cache (a Weather-owned Brain DB node or a small GCS object owned by `weather`; a new write path needing registration and approval) or accept the extra requests (`docs/NWS_PROVIDER.md`). Not implemented | nothing |
| 2 | Michael, then an Engine PR | Record the thresholds approval (given in chat: Sector_Ops #51 comment 7085207021): `runtime/knowledge/knowledge-release.json` `approval` -> `{"status": "APPROVED", "record": "<repo path of the approval record>"}`, `brain.json` `knowledge.stores[0].approval` and `operations.knowledgeLoading.approved`. The file digests do not change | write gate (a) |
| 3 | Cortex maintenance session, then an Engine PR | §6 step 3: register the Weather families and Weather as a target Brain; re-sync `jobs/brain_platform/sector_brain_platform/data_ownership.json`. Until then the orchestrator's M08 dispatch refuses `weather` (`UNREGISTERED_BRAIN`) | dispatch |
| 4 | Michael (IAM) | Create the service account `brain-job-weather` with write access to the Brain RTDB `sector-brain` only (identity split, Sector_Ops #19). The deploy script never creates or grants an identity | identity |
| 5 | Michael (creates a cloud job: cost) | `MICHAEL_APPROVED_WEATHER_DEPLOY=yes WEATHER_WRITE_APPROVED=1 SECTOR_WEATHER_USER_AGENT="Sector-WeatherBrain/1.0 (<contact>)" brains/weather/deploy/deploy-job.sh`. Creates `weather-brain` (1 vCPU, 512 MiB, 30 min, no retries, args `--write`), grants `brain-orchestrator` `run.invoker` on it, creates **no** scheduler | write gate (b) |
| 6 | Engine PR (config) | `control_manifest.json` `weather`: `activityState` `ACTIVE`; `executionTarget` `{"kind": "cloud-run-job", "job": "weather-brain", "startedByOrchestrator": true, "scoped": true}`; add a `jobs.weather-brain` entry (`brainId` weather, `kind` cloud-run-job, `scheduler` null, `classification` ORCHESTRATOR_OWNED, `estMonthlyUsdWhenEnabled` 2). The same PR moves `weather` out of the `registered_disabled` guards (`jobs/brain-orchestrator/tests/test_central_scheduling.py`, `test_prepared_brain_executors.py`, `brains/weather/tests/test_run_and_registration.py`): those tests are meant to fail on this flip. Then redeploy the orchestrator image (the manifest is packaged in it) | executor joins (`orchestrate.planned_executors`) |
| 7 | Michael (resumes recurring spend) | `python3 tools/ops/execution_control.py brain --changed-by michael --brain weather --enable-brain --max-runs-per-day 24 --reason "<approvalRef>"`. Check `maxStartsPerCycle` (default 2) still covers every enabled Brain | execution control |

Off again: `execution_control.py brain --brain weather --disable` (immediate), then `activityState PARKED`; delete the job to stop all cost.

## 7. Open questions for the owner

1. Approve the v1 thresholds release now, or run internally on the candidate (as Wind and Vegetation do)?
2. The NWS User-Agent contact: reuse the Lake Brain's contact address?
3. Weather is not one of the nine Cortex target Brains (BA-01): confirm it as a tenth Brain (Cortex release), or fold it under an
   existing target in the architecture?
4. Should Lake's own NWS rain read (`nws-forecast-qpf`) be retired in favour of the Weather state once Weather is live?
