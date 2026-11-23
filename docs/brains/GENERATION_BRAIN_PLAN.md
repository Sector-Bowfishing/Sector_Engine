# Generation Brain plan

Owner decision: Michael, chat 2026-11-22 19:37Z, recorded on Sector_Ops #51 (comment 7084558461): build the Generation Brain (dam releases and generation for the app's Generation tile, refreshed when release schedules change); real measured or official operator data only; customer-visible steps stay Michael's. Package: `brains/generation`. Providers and access: `GENERATION_BRAIN_PROVIDERS.md`.

Status on merge of this PR: **nothing changes at runtime.** The Brain is registered in the control manifest PARKED with no execution target, has no execution-control entry, no job, no image and no schedule; its knowledge release is a candidate (approval NOT_RECORDED), so `run.py --write` refuses (BLOCKED_AWAITING_APPROVED_RELEASE); customer publication is off.

## 1. What the Brain publishes

One state per directory lake with a dam (`/lakes/{k}/states/generation`, schema `generation-dam-state-v1`): release status (GENERATING, SPILLING, RELEASING, OFF, or UNKNOWN as an abstention), measured discharge / turbine / spill (cfs), generation (MW), units on **only as the operator states them**, the operator's schedule with the next start and stop, tailwater elevation as published with the release, the last 48 h, the agencies named, and an adaptive freshness block. It never publishes pool level (Lake Brain), never derives units or discharge from megawatts, and never fills a missing value. This matches what the iOS app shows today from the old Engine's TVA / SWPA / CWMS adapters (`DamGeneration`, the current / generation factor and the tailwater regime), minus the values the old Engine derived (SWPA unit counts and cfs). Today the app's Generation tile is still fed by the customer Engine's own live adapters (`Sources/SectorEngine/Engine/Adapters/*Generation*`, `CWMSObservedService`, `TailwaterRegistry`); this Brain does not change that path.

## 2. Sources per lake group, with coverage counts

The Engine lake directory has **621 lakes; 401 have a dam, 220 do not** (no dam, so no release: natural lakes, stated reason "no dam"). Counts are from the committed catalog `brains/generation/runtime/knowledge/dams.json` (`generation-dams-2026-11-22.1`, rebuilt and checked by `research/tools/generation_research/build_catalog.py`).

| Group (directory operator) | Lakes | Source(s) | Bound now | Pending (why) |
|---|---|---|---|---|
| TVA | 17 | TVA REST API: unit schedule + hourly release + tailwater | 11 | 6: TVA LocationID not evidenced in the repo (Cherokee, Chickamauga, Fontana, Hiwassee, Kentucky Lake KY and TN): resolve against TVA `/locations` |
| USACE Nashville (Cumberland; published through the TVA API) | 7 | TVA REST API; CWMS LRN as the measured fallback | 6 | 1: Laurel River Lake (TVA id not evidenced; CWMS series pending) |
| SWPA-marketed USACE projects | 15 | SWPA schedule page (MW) + CWMS measured release | 15 SWPA bindings, **not readable**: SWPA access check open | CWMS release series pending for all 15 |
| Other USACE | 123 | CWMS Data API (outflow, turbine, spill, MW, tailwater) | 0 | 123: release series ids not yet bound (CWMS location known for most from Lake's reviewed bindings; 8 lakes have no CWMS office in the directory) |
| Reclamation (USBR) | 65 | RISE release items (+ CWMS where a Corps division publishes the project, 11) | 0 | 65: RISE release item ids not yet bound (21 have a known RISE elevation item to start from) |
| Utilities and power authorities | 84 | operator pages (permission first); CWMS where USACE publishes the project | 0 | 11 CWMS-covered (pending discovery); 73 PERMISSION_REQUIRED |
| Other operators (state, local, water supply, river authorities, other federal, private) | 90 | none known; USGS discharge below the dam where a gauge exists | 0 | 6 CWMS-covered (pending); 84 NO_KNOWN_PUBLIC_RELEASE_DATA |

Every one of the 401 records carries a coverage state and a reason (`BOUND` 17, `BOUND_ACCESS_CHECK` 15, `DISCOVERY_PENDING` 212, `PERMISSION_REQUIRED` 73, `NO_KNOWN_PUBLIC_RELEASE_DATA` 84). Every lake also carries `usgsTailwater: PROBE_PENDING`: a downstream USGS discharge gauge (00060) has not been located for any lake yet.

## 3. Honest coverage estimate

- **Readable today (if enabled): 17 of 401 dam lakes** (TVA and Cumberland projects with evidenced TVA LocationIDs). TVA's robots.txt is still to be confirmed (decision D-G).
- **After one discovery pass on allowed official services, likely 150 to 230 lakes**: the 17, plus +7 TVA-API lakes, +15 SWPA lakes once access is confirmed, and the share of the ~173 CWMS-covered lakes and 65 Reclamation lakes whose operators actually publish a release series. That share is **unknown until the probe runs**: many USACE flood-control projects publish only a daily total outflow, some publish nothing current, and RISE release items lag about 48 h (a RISE-only dam can show measured release but no schedule). The range is a planning estimate, not a measurement; the probe pass replaces it with counts.
- **Unlikely without operator permission: 73 utility lakes**; **no known public release data: 84 lakes**. A USGS gauge below the dam can add measured river flow (labelled as such) for some of these 157; how many is unknown until the NLDI probe.
- **Schedules (start / stop times) exist only for TVA, the TVA-published Cumberland projects and SWPA**: about 39 lakes. Everywhere else the tile can show measured release now and its trend, never a forecast.

## 4. Refresh cadence (smart freshness)

Implemented in `brains/generation/runtime/generation_brain/freshness.py` (pure, tested). Each dam carries its own `freshness` block; once enabled, the hourly Orchestrator grant reads only the dams whose `nextCheckAt` is reached.

| Tier | When | Next read |
|---|---|---|
| TRANSITION | the operator's schedule changed since the last published state; or the release status changed (a release started or stopped); or the schedule starts or stops generation within 120 min; or the measured release moved >= 25 % and >= 500 cfs in 3 h | 60 min |
| ACTIVE | water is moving and none of the above | 120 min |
| STEADY | OFF and nothing scheduled soon | 180 min, but never later than 60 min before the next scheduled start or stop |
| UNKNOWN | no usable reading (source down or stale) | 120 min (back off) |

Also: when the posted schedule ends within 12 h (next day not yet posted), the next read is at most 120 min away, so the afternoon posting is picked up the same day. The 60 min floor is the owner's access rule (no series more than hourly). A published value stays current for `min(reading + source stale ceiling, max(reading + tier window, now + 150 min))` (ceiling = lag + 3 x cadence per series, the earliest among the series used, the Lake Brain rule; 150 min = one grant + one publish cycle + run time); a schedule-only state stays current until its window ends, at most 6 h; any status that rests on the schedule hour is capped at the end of that window. Thresholds are pre-set, not fitted; the validation week tunes them.

## 5. Validation (pre-registered)

Registered here before any run; nothing has been run.

- **Window:** 7 consecutive days, starting the first full day after the Brain is enabled for INTERNAL dry runs, at least 2 weekdays and 1 weekend day.
- **Sample:** every lake with a schedule bound and readable (TVA, Cumberland, and SWPA once allowed); at least the 17 lakes bound today.
- **Truth:** the operator's own published schedule, captured hourly in the same run (TVA `generation-releases`, SWPA page), and the operator's published hourly release for the same hours (TVA observed rows, CWMS outflow).
- **Metrics and thresholds (PASS needs all):**
  1. Hour agreement: for every scheduled hour, the published status agrees with the operator's schedule (units > 0 -> GENERATING or a measured release; 0 -> OFF or RELEASING): **>= 95 %** of lake-hours.
  2. Transition latency: every scheduled start or stop is reflected in a published state within **90 min** of its scheduled time (one grant + one publish cycle), in **>= 95 %** of transitions.
  3. Schedule fidelity: the published windows equal the operator's posted windows (same start, end, units / MW) in **100 %** of captures (parsing must be exact).
  4. No invented values: zero states carry a unit count where the operator stated none, a discharge with no source, or a status other than UNKNOWN when no source answered (checked mechanically on every published state).
  5. Freshness: zero states served past `freshUntil`; reads per series never more than one per hour.
- **Recording:** a validation record under `docs/cortex/` with the raw captures in the research workspace (not in Git), PASS / FAIL per metric, and the lakes that failed. A FAIL is reported as a FAIL; thresholds are not moved after the run.

## 6. Rollout (each step gated; nothing here is done by this PR)

1. **This PR** (merged changes nothing): package, contract, catalog, registration DISABLED, tests.
2. **Access checks** (D-G): TVA robots.txt + the iOS note; SWPA robots.txt and terms. New release if any status changes.
3. **Discovery pass** (GEN-BIND-001..003): CWMS release series, RISE release items, TVA LocationIDs, USGS tailwater gauges, recorded with evidence; real responses recorded as fixtures; new catalog version and release.
4. **Cortex**: a Cortex maintenance session adds Generation as a target Brain and moves dam releases and reservoir operations (not pool level) from Lake Brain (D-H, CG-3.1-20).
5. **Owner approvals** (Michael): approve the knowledge release (G-2); give the Brain an execution target (an in-process executor in the Orchestrator or a job: a job costs money and needs approval) and an execution-control entry; then internal dry runs.
6. **Validation week** (section 5) on internal runs. PASS or FAIL recorded.
7. **Customer path** (Michael's own steps): a customer-lane copy, app reading it, tile flip. Not proposed until validation passes. The existing draft customer copy `customer/lakes/{k}/generationBinding` (Sector_Ops #53, `publisher_live/customer_generation_binding.py`, not wired) waits on a dam binding the Lake contract does not carry; the Generation catalog's bound `operator + LocationID` records are the natural source for it, as a separate reviewed change.

### 6.1 How to turn it on (prepared 2026-11-23, all inert today)

Prepared on `feat/brain-writers-weather-moon-generation-2026-11-23`: `deploy/` (refuses without the owner's approval, no scheduler) and an inert
orchestrator executor (`generation-brain`). The gated writer (`run.py --write`: APPROVED release AND `GENERATION_WRITE_APPROVED=1`) already
existed. **Still blocked on D-G and D-I (§7): do not start step 3 before both are decided.** Source access statuses are unchanged.

Cost: a run reads only the bound dams whose nextCheckAt is reached; estimate about 1-2 USD/month at list price for hourly runs. Proposed cap
2 USD/month; the execution control's `maxCostPerDay` bounds each day.

| # | Who | Action | What it flips |
|---|---|---|---|
| 0 | Michael | Decide D-G (TVA/SWPA access) and D-I (one read per series per hour across Brains); a new release if any access status changes | blockers |
| 1 | Michael, then an Engine PR | G-2: approve the knowledge release (after the validation week); `knowledge-release.json` `approval` APPROVED with its record | write gate (a) |
| 2 | Cortex maintenance session, then an Engine PR | D-H: Generation as a target Brain (CG-3.1-20); re-sync `data_ownership.json` (dispatch refuses `generation` until then) | dispatch |
| 3 | Michael (IAM) | Service account `brain-job-generation`, write access to `sector-brain` only | identity |
| 4 | Michael (creates a cloud job: cost) | `MICHAEL_APPROVED_GENERATION_DEPLOY=yes GENERATION_WRITE_APPROVED=1 brains/generation/deploy/deploy-job.sh` | write gate (b) |
| 5 | Engine PR (config) | `control_manifest.json` `generation`: `activityState` `ACTIVE`; `executionTarget` `{"kind": "cloud-run-job", "job": "generation-brain", "startedByOrchestrator": true, "scoped": false}`; `allowedTriggers` add `SCHEDULE`; `schedule` `{"class": "ORCHESTRATOR_OWNED", "owner": "ORCHESTRATOR", "scheduler": "brain-orchestrator", "exception": {gate, notReconstructable, "maxMonthlyUsd": 2, stop, approvedAt}}` (all five keys, or `schedule_policy` refuses); `freshness` add `"dueAfterHours": 0.75, "staleAfterHours": 3`; `costClass` `LOW`, `resources`; a `jobs.generation-brain` entry. The same PR removes `generation` from the `registered_disabled` guards; then redeploy the orchestrator | executor joins, hourly grant |
| 6 | Michael (resumes recurring spend) | `python3 tools/ops/execution_control.py brain --changed-by michael --brain generation --enable-brain --max-runs-per-day 24 --reason "<approvalRef>"` | execution control |

Off again: `execution_control.py brain --brain generation --disable`, then `activityState PARKED`; delete the job to stop all cost.

### 6.2 Running on Sector Pulse instead of a cloud job (decision 2026-11-23; prepared, all inert)

Decision recorded in chat (Michael, 2026-11-23 01:44 CT), not an Owner approval comment: the new Weather, Moon and Generation Brains run on the
Mac mini through Sector Pulse instead of as Cloud Run jobs, so a run costs nothing. **`brains/generation/deploy/deploy-job.sh` is superseded by Pulse, pending
Michael's enablement**: it stays in the repository unchanged (not deleted) and is not to be run while this route is chosen. Nothing below is
enabled, deployed or run by the PR that prepared it (branch `ops/new-brains-on-pulse-2026-11-23`).

Prepared: `runtime/artifact_entry.py` (the shared `sector_brain_platform.python_artifact_entry`): the unchanged publish step into the Brain's
DryRunWriter, the previous state read from the live Brain database (GET only, `--read-rtdb`, the read token), ONE sealed artifact stored
create-only and handed off with `--emit`. It keeps `run.py --write`'s gates: an APPROVED knowledge release (exit 2) AND
`GENERATION_WRITE_APPROVED=1` (exit 3). It writes no database and no bucket; the central Publisher is the only writer once the Brain is CENTRAL.
Sector-Pulse catalog entry `generation-central` (disabled; WHILE_LEASE_HELD: no cron of its own, it runs once per cycle the Orchestrator grants Pulse
the lease: hourly, reading only dams whose nextCheckAt is reached).

D-G and D-I (§7) still block enablement on this route.

| # | Who | Action (replaces the cloud-job steps above) |
|---|---|---|
| 1 | Michael, then an Engine PR | Approve the knowledge release (step "approve" above) |
| 2 | Cortex maintenance session, then an Engine PR | Register the Brain's families / target Brain (dispatch refuses it until then) |
| 3 | Michael | Order review: the Brain is not in `cutover_order.json` (PL-10); a hybrid-stage fragment `tools/ops/hybrid-stage/generation.json` and `hybrid_stage.py apply` follow the order review (as Wind, Water Temp) |
| 4 | Michael (IAM) | The per-Brain lease/artifact bindings for Pulse (the W-H1 / WT-H1 pattern, B=generation) |
| 5 | Engine PR (config) | `control_manifest.json`: `activityState` ACTIVE and an execution target the Orchestrator grants to the runner (as the CENTRAL Brains); remove the Brain from the `registered_disabled` guards; redeploy the Orchestrator and Publisher |
| 6 | Michael on the Mac mini | Merge the Sector-Pulse PR, update Pulse; set `jobs.dataRoot` to the data SSD folder; Keychain items as the catalog entry declares; enable `generation-central` in Pulse; set `GENERATION_WRITE_APPROVED=1` for the Pulse job environment |
| 7 | Michael (resumes execution) | `tools/ops/execution_control.py brain --brain generation --enable-brain ...` with the approvalRef |

## 7. Blocking enablement (owner decisions, not code)

Nothing in this section is changed by code; each must be decided before the Brain is given an execution target.

1. **TVA access (D-G).** `tva` stays ALLOWED in the candidate release only provisionally: it becomes ALLOWED for enablement only after `www.tva.com/robots.txt` has been read and the iOS conditions-spec note "TVA blocks automated access" (2026-07-16) has been resolved. If either forbids automated use, TVA's status changes to PERMISSION_REQUIRED in a new release and TVA is asked first.
2. **One read per series per hour across Brains (D-I).** The owner rule caps each official series at one read an hour. The Lake Brain already reads the same TVA `observed-data-48-hours/{LocationID}` URL hourly for the pool level, so an enabled Generation Brain would double the reads of those URLs. Options: (a) one shared reader and archive for TVA observed rows that both Brains consume (Lake keeps pool, Generation takes release and tailwater); (b) Generation reads only `generation-releases` and consumes Lake's published release readout for TVA dams; (c) the owner accepts two reads an hour per URL. Until decided, Generation must not be enabled for TVA lakes. (The reviewer of #235 called this D-H; it is recorded as D-I because D-H is the Cortex architecture decision.)

## 8. Open decisions (batched)

- **G-2** approve a Generation knowledge release (after D-G and the validation week).
- **D-G** TVA and SWPA access checks (and permission requests if either forbids automated use); blocking enablement (section 7.1).
- **D-I** cross-Brain read budget for TVA observed data (section 7.2).
- **D-H** Cortex architecture: Generation as a tenth target Brain; dam releases move from Lake Brain to Generation; Lake keeps pool level and stops publishing its own release readout once Generation serves it (CG-3.1-20).
- Operator permission requests for the 73 utility lakes (drafting approved 2026-11-22 19:34Z; sending is Michael's).
