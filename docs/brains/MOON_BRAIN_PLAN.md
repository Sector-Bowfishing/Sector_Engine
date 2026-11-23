# Moon and Night Light Brain — plan

**Decision.** Owner, chat 2026-11-22 19:37Z, recorded on Sector_Ops #51: build it, everything approved. This document is the plan and the record of what was built. The package is `brains/moon` (`brainId` `moon`).

**Runtime effect of merging: none.** The Brain is registered in the control manifest as `PARKED` with `executionTarget.kind: none`, it is absent from the execution control (`/control/executionControlV1`; absent means disabled), it has no live writer, and `run.py --write` refuses. Customer publication is off.

## 1. What it answers

For each of the 621 lakes in the lake registry, for tonight:

| Output | Definition |
|---|---|
| Moon phase name, phase fraction, waxing | sector-moon-v1 (`contracts/moon/moon-v1.json`), at local solar midnight |
| Illumination fraction | sector-moon-v1 (true Sun–Moon elongation), at local solar midnight |
| Moonrise, moonset | Moon's upper limb on the horizon with 34′ refraction: geocentric altitude of the centre = 0.7275 × parallax − 0°34′ (Meeus ch. 15, USNO) |
| Sunset, sunrise | Sun's centre at −0°50′ |
| Civil, nautical, astronomical dusk and dawn | Sun's centre at −6°, −12°, −18° |
| Fishing window | astronomical dusk (else sunset + 80 min) to the next sunrise — the Engine's and the app's window |
| Moonlight across the window | mean of max(0, sin(moon altitude)) every 15 min — the Engine's `moonAltitudeFraction` |
| On-water darkness class | DARKNESS_RULE_V1 (§3) |

"Tonight" for date D runs from local solar noon on D to local solar noon on D+1 (`D 12:00 UTC − lon/15 h`). Every instant is UTC. An event that does not happen in that span (polar day, polar night, a day without a moonrise) is `null` with a `sunState` reason. It is never interpolated.

## 2. What was reused, and why the event finder is new

**Reused.** The Engine already computes moon data. Step 0 of the conditions consolidation froze it as `contracts/moon/moon-v1.json` (specId `sector-moon-v1`, 52 vectors; reference `Sources/SectorEngine/Engine/Astronomy.swift`, identical to the iOS copy apart from one extension). The iOS moon tile (`specs/weather-metric-detail.md` §9) and the darkness factor (`specs/conditions-engine.md`) are the behavioural source of truth. `ephemeris.py` is a line-for-line port of that file, and `tests/test_moon_spec_vectors.py` runs all 52 vectors at the spec's tolerances. A change to the moon math goes to the spec and every copy.

**New.** The Engine's `sunEvents` and `moonRiseSet` are fine for a tile but do not meet a ±2 min USNO check:
- `sunEvents` computes the Sun once, at the request instant, and solves the hour angle from that single position.
- `moonRiseSet` puts the Moon's *centre* at 0° topocentric, with no refraction or semidiameter. That is about 0.8° from the USNO definition, which is several minutes of time.
- `moonRiseSet` scans the **UTC** day, so at US longitudes it can return the previous evening's moonrise. This explains the "9:59 PM moonrise" in the 2026-08-03 Langston measurement in `specs/conditions-engine.md`. The Brain's noon-to-noon span gives 10:22 PM CDT for that night.

`events.py` keeps the same ephemeris. It applies the USNO standard altitudes, samples every 10 min, and bisects each crossing to 1 s, recomputing positions at every trial instant. Sidereal time uses Meeus eq. 12.4, which is about 1 s from Schlyter's L+180. The Engine is not changed by this PR. Whether the Engine should adopt the same event definitions is a separate decision (§7).

## 3. DARKNESS_RULE_V1, stated before scoring

This is the machine-readable rule in `contracts/moon-night-light-v1.json` → `darknessRule`. The constants are the Engine's `DarknessFactor` and `ConditionsConfig.Darkness`, so the Brain and the app classify a night the same way.

```
I = illumination at local solar midnight              P = moon presence across the fishing window
C = clamp((cloudPct − 50) / 50, 0, 1) × (1 − 0.8 × 0.3)      (0.3 = Engine default city glow; no per-lake skyglow input)
A = I × P × (1 − C)
DARK  A < 0.15   |   MOSTLY_DARK  < 0.35   |   SOME_MOONLIGHT  < 0.60   |   BRIGHT_MOON  ≥ 0.60   |   NO_NIGHT  Sun never sets
```

- **Cloud missing, partial or invalid → MOON_ONLY.** The class uses A = I × P (the clear-sky upper bound). The state says so in `statement` and names the reason. No cloud value is assumed: the Engine's `cloud ?? 0` default is not copied.
- `moonOnly` is reported on every night, so a consumer can always see the cloud's effect.
- The labels are the Engine's ("97% moon · bright — moon up"). The copy makes no fish-behaviour claim, per the iOS "Copy accuracy (moon)" rules. A test enforces this.
- Cloud use: the mean of the hourly values within ±30 min of the window. At least 75 % of the window's hours must have a value.

## 4. Weather Brain input

The input is the Weather Brain's per-lake state (`sector-brain-weather-state-v1`, `/lakes/{k}/states/weather`). It is OPTIONAL and declared in `brain.json` `consumes` (§7.2). Only these fields are read:
- `forecast.hourly[].cloudCoverPct`: the NWS forecast grid, at most 12 hours after the run. A row without the key counts as null.
- `sky.cloudCoverPct {value, at, origin}`: the current hour.
- `generatedAt`.

**Limits (stated, #236 review):**
- **What the cloud span covers.** A Weather state cannot describe hours before its run. The cloud adjustment covers `[max(window start, the Weather run's hour), window end]` and reports that span in `cloudCover.span` and in the statement. An evening run judges the whole window; a mid-night run judges the hours still ahead.
- **Run timing.** With 12 forecast hours, only Weather runs from about 3 h before astronomical dusk cover a whole November night (Guntersville: from 21Z). An earlier run gives MOON_ONLY with INSUFFICIENT_COVERAGE. When enabled, Moon should therefore run after each evening and night Weather run (§7.1).
- **Coverage.** Coverage counts distinct hours, and at least 75 % of the span's hours need a value. Values are checked only inside the span.
- **Refusals.** A timestamp without an explicit UTC offset refuses the document. A Weather run after the window has ended gives WEATHER_AFTER_WINDOW.
- **Labelling.** The statement says the cloud is an NWS forecast, and names an observed current hour when that is the origin.
- **Tests.** They use four states the Weather Brain built from its recorded NWS fixtures (Guntersville at 20:51Z and 01:00Z, Champlain at 20:51Z and 23:00Z: the afternoon runs give MOON_ONLY, the evening runs MOON_AND_CLOUD), plus schema-valid variants. Every fixture is validated against `brains/weather/contracts/weather-state-v1.schema.json`.
- **No live check yet.** No live Weather state has been read: both Brains are disabled.

The deliberate differences from the app's Moon tile and Darkness label are listed in the contract under `divergences`: the illumination instant, the fixed 0.3 city glow, forecast cloud over the remaining window, and the event definitions.

## 5. Package and registrations

| Where | What |
|---|---|
| `brains/moon/` | `brain.json` (CALIBRATION, customerPublication NOT_ELIGIBLE, INTERNAL only), operating contract, README, `contracts/` (state contract + Publisher declaration), `runtime/`, `tests/`, `research/` (CHARTER, GAPS) |
| `runtime/knowledge/` | Packaged knowledge release: a projection of the Engine lake directory (lakeId, name, state, lat, lon), approval NOT_RECORDED. A test fails if it drifts from `LakeDirectory.swift`. A tampered or missing release refuses the run |
| `control_manifest.json` | `moon`: PARKED, executionTarget none, schedule MANUAL, triggers MANUAL/ADMIN, costClass NONE, customerPublication false |
| Execution control | Not added. A Brain absent from `brains` is disabled (fail closed). Only the owner CLI writes it |
| `control.py` | `moon` in SHADOW_BRAINS/SHADOW_SLOTS: visible, never in a roll-up or the Engine score |
| `keys.py`, `BrainPlatform.swift`, `stable_brain_ids.json` | slot `moon`, snapshot field `moonNightLight` |
| `publisher/registry.py` | `moon-lake-state-v1`, `moon-registry-v1`, bundle `moon-publication-v1` (describes the dry-run write set so the Brain can be certified; authorizes no writer) |
| `cutover_order.json` | `moon` blocked (no cutover plan) |
| `platform/security/*` | Plan documents only: `moon` current identity NONE, target `brain-job` (like Depth and Vegetation). The publisher plan is regenerated from the model. No IAM is changed |
| Engineering status | Memory-standing row and status layers for `moon`; certification re-collected |

## 6. Verification

- `cd brains/moon && python -m pytest -q`: 262 tests. That covers the moon-spec vectors; the USNO cross-check (10 place-days of rise/set and civil twilight, 12 nautical/astronomical table rows including one "Sun never below −12°" case, 20 principal phases); the night window (including the 2026-08-03 "window ends before it starts" regression and polar day/night); DARKNESS_RULE_V1; the lake directory; run entry; the dry-run write set against the contract schema; and Brain Cert Kit V1 (all proofs and mutations).
- USNO tolerances: rise/set and twilight ±2 min (observed worst case 40 s against the minute-rounded USNO values), principal phases ±20 min (observed worst case 17 min, from the Schlyter ephemeris), illumination at a principal phase within 0.003.
- The full 621-lake directory computes in about 4 s on one CPU. On 2026-11-22 (a 97 % waxing moon, no cloud input), every lake is MOON_ONLY: 470 SOME_MOONLIGHT, 150 BRIGHT_MOON, 1 MOSTLY_DARK (Teshekpuk, AK, polar night).

## 7. Not done here (owner decisions or later work)

1. **Enable execution**: these are gated owner decisions. The checklist, done together:
   - add `moon` to the execution control;
   - give it an executor and an approved writer;
   - set the control manifest `activityState` ACTIVE with a real schedule, and `brain.json` `operations.execution.trigger` back to TIME with its `minIntervalHours`. Run Moon hourly through the evening and night after each Weather run, so the remaining-window cloud stays current (§4);
   - read each lake's Weather state from RTDB with the dependency's freshness rule, instead of the `--weather` file;
   - decide whether moon presence P should use the same remaining span as the cloud (today P covers the whole window, while the cloud covers only the span still ahead at the Weather run). Check the Weather state's age against the dependency's maxAgeHours (`run.py --weather` does not check it today). Report a missing `generatedAt` with its own reason (today it is MALFORMED_HOURLY_ROW);
   - remove the `moon` carve-out in `jobs/brain-orchestrator/tests/test_central_scheduling.py` (`registered_disabled`) so the test again requires an execution path for every manifest Brain.
   **Prepared 2026-11-23** (branch `feat/brain-writers-weather-moon-generation-2026-11-23`): the gated writer, the live Weather read with the
   maxAgeHours check, `deploy/`, the inert executor and the after-Weather trigger. What remains is §7.1.
2. **Weather Brain consumes entry** (MOON-INP-001): done once Weather (#234) reached main. `brain.json` `consumes` lists `{kind: brain, brainId: weather, contractId: weather-publication-v1, requirement: OPTIONAL}`, the control manifest lists an OPTIONAL `weather` dependency (maxAgeHours 3, Weather's own staleAfterHours), and Weather's `authorizedConsumers` include `moon`. What remains is a live read of `/lakes/{k}/states/weather`, which belongs to enablement (§7.1).
3. **Validate DARKNESS_RULE_V1** against measured on-water illuminance (MOON-VAL-001).
4. **Per-lake skyglow** (MOON-INP-002).
5. **Engine event definitions**: whether the Engine and the apps should adopt the USNO altitudes and the noon-to-noon span for the moonrise/sunset they display. That would be a `moon-v2` spec change across iOS, Android and Web.
6. **Cortex**: Moon is not one of the Cortex target Brains, and its families are not in the Cortex data registry (CG-3.1-19). Cortex is read-only here.

### 7.1 How to turn it on (prepared, all inert today)

**Run after each Weather run.** Expressed as the platform's dependency trigger: Moon accepts `DEPENDENCY_CHANGED` on its OPTIONAL `weather` edge,
and Weather's output fingerprint includes `lastSuccessfulRun`, so every completed Weather run is a material change for Moon. Because Weather is due
on every hourly grant, the edge sets `deferIfUpstreamStarted: false` (new, default true for every other edge): Moon runs at the next grant on
Weather's last completed states while Weather's new run is in flight, instead of being deferred every cycle (tested both ways in
`jobs/brain-orchestrator/tests/test_prepared_brain_executors.py`). A live run uses a lake's Weather state only if it was generated within 3 h.
Inert today: Moon is PARKED, so `DEPENDENCY_CHANGED` is `SKIP_PARKED`.

Cost: a full live run is about 5 s of compute plus up to 3 x 621 small RTDB requests (Weather read, own-state read, changed-lake writes);
estimate 1-3.5 USD/month at list price for hourly runs. Proposed cap 4 USD/month; the execution control's `maxCostPerDay` bounds each day.

| # | Who | Action | What it flips |
|---|---|---|---|
| 0 | | Weather is on first (WEATHER_BRAIN_PLAN.md §6.1): without Weather states Moon publishes MOON_ONLY | |
| 1 | Michael, then an Engine PR | Approve the lake-directory release `moon-knowledge-candidate-2026-11-22.1`: `knowledge-release.json` `approval` APPROVED with its record; `brain.json` knowledge approval | write gate (a) |
| 2 | Cortex maintenance session, then an Engine PR | Register Moon's families and Moon as a target Brain (CG-3.1-19); re-sync `data_ownership.json` (dispatch refuses `moon` until then) | dispatch |
| 3 | Michael (IAM) | Service account `brain-job-moon`, write access to `sector-brain` only | identity |
| 4 | Michael (creates a cloud job: cost) | `MICHAEL_APPROVED_MOON_DEPLOY=yes MOON_WRITE_APPROVED=1 brains/moon/deploy/deploy-job.sh` (1 vCPU, 512 MiB, 30 min, no retries, args `--write`; no scheduler) | write gate (b) |
| 5 | Engine PR (config) | `control_manifest.json` `moon`: `activityState` `ACTIVE`; `executionTarget` `{"kind": "cloud-run-job", "job": "moon-brain", "startedByOrchestrator": true, "scoped": false}`; `costClass` `LOW`, `resources` `{"cpu": 1, "memoryGiB": 0.5, "tasks": 1}`, `timeoutSeconds` 1800; a `jobs.moon-brain` entry (`estMonthlyUsdWhenEnabled` 3.5). The same PR removes `moon` from the `registered_disabled` guards (`test_central_scheduling.py`, `test_prepared_brain_executors.py`, Moon's own registration tests); then redeploy the orchestrator | executor joins |
| 6 | Michael (resumes recurring spend) | `python3 tools/ops/execution_control.py brain --changed-by michael --brain moon --enable-brain --max-runs-per-day 24 --reason "<approvalRef>"`. Check `maxStartsPerCycle` (default 2) still covers every enabled Brain: Moon and Weather both start in the same cycle once both are on | execution control |

Off again: `execution_control.py brain --brain moon --disable`, then `activityState PARKED`; delete the job to stop all cost.
