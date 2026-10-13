# Sector Brain Platform — Contract v1.0

**Owner:** Sector Engine. **Status:** RATIFIED 2026-10-12 (consolidation Phase 4). Supersedes the
proposed-v1 wording in Sector_Ops `docs/SECTOR_BRAIN_RTDB_SCHEMA.md` wherever the two differ; Ops
renders, Engine defines. Machine-readable fixtures that every implementation must pass live in
`docs/brains/conformance/`. Implementations: Swift `Sources/SectorEngine/Brain/`, Python
`jobs/brain_platform/sector_brain_platform/`.

Principle: **Engine owns truth, Ops owns presentation.** A Brain publishes what it knows; it never
fills in a default for what it doesn't (unknown stays absent). Sector Intelligence synthesizes and
never owns specialist science. Scheduling belongs to the (future) Brain Orchestrator; each Brain
only describes what makes it stale and when a run is warranted.

---

## 1. Instance, keys, atomicity

| | |
|---|---|
| Database | `https://sector-brain.firebaseio.com` (project `sector-9393c`). Writers **must** refuse any URL naming an app database (`sector-9393c-default-rtdb`, `sector-dev-1f4d0`) and any URL not containing `sector-brain`. |
| Credential | Server credential (Cloud Run service account via metadata server; `gcloud` locally; a static token only in tests). Bypasses rules. Ops reads only. |
| Lake key | `lakeKey = re.sub("[^A-Za-z0-9]+", "_", lakeId)` over the canonical directory id `"<name>|<state>"`. Lossy → **every lake-scoped node stores `lakeId`**. A writer re-verifies collision-freedom over the directory it was given and fails the whole run on a collision. This is the only key scheme; Wind's short ids (`guntersville`) are mapped before writing. |
| Key legality | Keys never contain `. $ # [ ] /` or control characters; a writer walks its payload and rejects the run on an illegal key. `NaN`/`Infinity` are rejected at serialization. |
| Atomic unit | One multi-location `PATCH` at the root per unit. The unit is **one lake** (all of that lake's paths together) or a chunk of ≤ 50 lakes; the registry/health/activity tail is its own unit written **after** the lakes. A reader therefore never sees a half-written lake. |
| Schema gate | Before any write, read `/schemaVersion`; abort if present and ≠ the version the writer speaks (currently `1`). Additive fields never bump it. |

## 2. Identity: brain ids, slots, snapshot fields

| brainId | slot (`/lakes/{k}/states/{slot}`, `/lakeFleet/{k}/readiness/{slot}`) | snapshot field | displayName |
|---|---|---|---|
| `lake-brain` | `lake` | `lakeState` | Lake Brain |
| `water-temp` | `waterTemp` | `waterTemperature` | Water Temperature |
| `water-clarity` | `waterClarity` | `waterClarity` | Water Clarity |
| `wind` | `wind` | `wind` | Wind |
| `biological-state` | `biology` | `biologicalState` | Biological Brain |
| `sector-intelligence` | `intelligence` | `sectorIntelligence` | Sector Intelligence |
| `depth`, `vegetation` | `depth`, `vegetation` | `depth`, `vegetation` | reserved |

Ops' hard-coded catalog (`src/lib/brainCatalog.ts`) must match this table; the table is the source.

## 3. Vocabularies (closed sets; Ops renders unknown strings verbatim and never remaps)

| Set | Values | Meaning |
|---|---|---|
| **health** (`/health/brains/{id}.status`, `/brains/{id}.health`, sources, jobs) | `HEALTHY` `WARNING` `DEGRADED` `FAILED` `UNKNOWN` `NOT_CONFIGURED` | runtime condition of the last run. `FAILED`: run aborted or publish failed. `DEGRADED`: > 25 % of attempted lakes unavailable, or a publish partially failed. `WARNING`: 5–25 % unavailable, or a partial run. `HEALTHY`: otherwise. `UNKNOWN`: never run / not observable. `NOT_CONFIGURED`: registered, no runtime. |
| **readiness** (per lake-slot; the promotion ladder) | `DISCOVERED` `PROFILED` `CALIBRATION` `BETA` `VALIDATED` `PRODUCTION` `DEGRADED` `BLOCKED` | *How far this lake's state for this brain has been promoted.* Order for "promotion" events: DISCOVERED < PROFILED < CALIBRATION < BETA < VALIDATED < PRODUCTION. `DEGRADED`/`BLOCKED` are off-ladder conditions. **Readiness is never an evidence class** (Water Temp's `PRODUCTION`/`BETA` = measured/modeled misuse is retired; that fact is `evidenceClass`). |
| **brain status** (`/brains/{id}.status`, brain-level lifecycle) | `DISCOVERED` `PROFILED` `CALIBRATION` `BETA` `VALIDATED` `PRODUCTION` | the brain as a whole. A brain that is unscheduled / internal-only is at most `CALIBRATION`. |
| **model lifecycle** (`models.*.status`) | `RESEARCH` `CANDIDATE` `SHADOW` `REVIEW` `PRODUCTION` `RETIRED` | `PRODUCTION` only for the model production customers actually consume. Wind's `ACTIVE_PRODUCTION`→`PRODUCTION`, `RESEARCH_CANDIDATE`→`CANDIDATE`; Clarity's `PRODUCTION_EVIDENCE`→`PRODUCTION` + `evidenceOnly: true`. |
| **version status** (`versions[].status`) | `CURRENT` `SHADOW` `CANDIDATE` `RETIRED` | |
| **state kind** (`states/{slot}.kind`, lowercase) | `measured` `modeled` `observed` `proxy` `analysis` `forecast` `evaluated` `not_evaluated` `unavailable` | what the current value *is*. Replaces `stateType` and the uppercase `kind`. A brain may keep a richer brain-specific field beside it. |
| **staleness model** (`/brains/{id}.stalenessModel`) | `TIME` `VERSION` `FINGERPRINT` | how this brain's state goes stale (age; input version; upstream fingerprint). |
| **activity severity** | `info` `success` `warning` `critical` | |
| **activity kind** (dotted, lowercase) | `brain.registered` `brain.version` `brain.updated` `run.failed` `run.degraded` `health.changed` `readiness.promoted` `readiness.changed` `model.changed` `source.changed` `score.changed` | the only kinds; a new kind is a contract change. |
| **evidence class** (brain field, where applicable) | brain-defined, documented in the brain's INTEGRATION doc | e.g. Water Temp `measured`/`modeled`. |

## 4. Per-lake state envelope — `/lakes/{k}/states/{slot}`

Every state is the brain's payload inside this envelope. Required keys in **bold**.

```jsonc
{
  "lakeId": "Guntersville|AL",            // bold
  "brainId": "water-temp", "slot": "waterTemp",
  "schemaVersion": 1, "stateSchema": "sector-brain-water-temp-state-v1",   // bold: shape version of the payload
  "kind": "measured",                     // bold: §3 state kind
  "provenance": {                         // bold
    "brainId": "water-temp", "brainVersion": "2.0.0", "modelVersion": "surface-energy-balance-v2",
    "processingVersion": "…", "generatedAt": "2026-10-12T04:20:00Z",
    "sources": [{ "sourceType": "usgsLakeSensor", "sourceId": "usgs-nwis-00010", "lastObservationAt": "…" }],
    "inputAgeHours": 0.4, "readiness": "VALIDATED", "qualityFlags": ["…"], "validationRef": "/validation/water-temp"
  },
  "freshness": {                          // bold — the ONE staleness envelope (Lake Brain's, adopted for all)
    "generatedAt": "…",                   // when this state was computed (== provenance.generatedAt)
    "sourceObservationAt": "…",           // newest input observation behind it (absent if none)
    "freshUntil": "…",                    // generatedAt + staleAfterHours (TIME) — absent for VERSION/FINGERPRINT
    "nextCheckAt": "…",                   // when the brain itself would look again (orchestrator input)
    "stale": false,                       // TIME rule: now − generatedAt > staleAfterHours, as of the write
    "evidenceStale": false,               // the brain's own evidence rule (sensor missing, forecast cycle old, …)
    "staleReasons": [],                   // human-readable, empty when neither is true (absent in RTDB)
    "refreshReason": "scheduled"          // why this write happened
  },
  // …brain payload (documented per brain)
}
```

`stale` is **time** only; `evidenceStale` is **evidence** only; readers never infer one from the
other. A VERSION/FINGERPRINT brain writes `stale: false` and omits `freshUntil`.

## 5. Shared-field ownership (ends last-writer-wins)

| Path | Who may write | Rule |
|---|---|---|
| `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId` | any brain | value must equal the directory id (idempotent) |
| `/lakeFleet/{k}/readiness/{slot}`, `/modelVersions/{slot}`, `/slots/{slot}/*` | the slot's brain **only** | `slots/{slot}` = `{readiness, kind, stale, evidenceStale, issueCount, generatedAt, lastUpdatedAt, lastErrorAt, lastError}` |
| `/lakeFleet/{k}/riverSystem`, `/lakeType` | `lake-brain` only | denormalized from the profile; absent when unknown |
| `/lakeFleet/{k}/lastUpdatedAt`, `/stale`, `/issueCount`, `/hasObservations` | **nobody in v1** (Orchestrator rollup, later) | until the rollup exists these are absent; Ops derives fleet freshness from `slots/*` |
| `/snapshots/{k}/latest/<snapshot field>` and `/brainVersions/{brainId}` | that brain only | the field carries its own `provenance.generatedAt` |
| `/snapshots/{k}/latest/generatedAt`, `/snapshotVersion`, `/evaluationTime` | **nobody in v1** (Orchestrator rollup) | |
| `/lakes/{k}/brain`, `/lakes/{k}/speciesPresence/*` | `lake-brain` only | presence is lake context; knowledge lives under `/species` (biological-state) |
| `/species/{id}` | `biological-state` only | |
| `/sources/{id}` record | the **owner brain** (§6) | non-owners write only `/sources/{id}/brains/{brainId}: true` |
| `/sources/{id}/brains` | map `{brainId: true}` | never an array (an array would be replaced whole) |
| `/health/sources/{id}` | owner brain only | |
| `/brains/{id}`, `/health/brains/{id}`, `/validation/{id}`, `/health/jobs/{jobId}` | that brain / that job | |
| `/activity/{eventId}` | the brain named in the event; pruned only by that brain | §7 |
| `/schemaVersion`, `/access/*`, `/health/engine`, `/health/rtdb`, `/validationOps`, `/engine/*` | the **platform writer** (`brainId = "brain-platform"`: the Engine's own score/health publisher), never a brain | |
| `/brains/{id}/score` | that brain **or** the platform writer | the Engine-owned score publisher (Phase 5) computes every brain's score from published facts and frozen rubrics; a brain may also publish its own if it carries the same rubric |

A conforming writer validates every multi-path update against this table before sending it
(`assert_owned` / `BrainOwnership.check`) and refuses the whole update on a violation.

## 6. Sources

`/sources/{sourceId}` = `{sourceId, provider, type, ownerBrainId, brains{brainId:true}, lakeCount, health,
lastFetchAt, latestObservationAt, staleThresholdHours, failures24h?, failuresLastRun?, provides?, notes?}`.
**`failures24h` is written only when a 24 h ledger exists; unknown is absent, never `0`.**

Owner table (the ids the Brains actually write, verified 2026-10-12):

| sourceId | owner | also consumed by |
|---|---|---|
| `tva-restapi`, `usace-cwms-pool`, `usgs-nwis-lake-elevation` | `lake-brain` | |
| `usgs-nwis-00010`, `usace-cwms-water-temp`, `open-meteo-forecast` | `water-temp` | |
| `sentinel-2-l2a`, `usgs-nwis-turbidity`, `noaa-mrms` | `water-clarity` | |
| `noaa-nbm-v5`, `noaa-rtma-ru`, `iem-metar-wind` | `wind` | |
| any id not listed | the first brain to register it; it must set `ownerBrainId` | |

## 7. Activity

- Event: `{id, at, kind, title, brainId, lakeId?, severity}`; `brainId` is **required** (an event
  without one cannot be pruned by anyone but the Orchestrator).
- **Event id** = `"{ms13}-{brainId}-{nnn}"`: `ms13` = event time as 13-digit zero-padded Unix
  milliseconds, `nnn` = 3-digit sequence within the run. Lexical order == time order across brains.
  Legacy Swift keys (`yyyyMMddTHHmmssSSS-…`) remain valid *records*; they are not re-keyed.
- **Pruning**: after each run a brain deletes **only its own** events (`brainId == self`), ordered by
  the `at` field — never by key — keeping at most **80** per brain and nothing older than **30 days**.
  The database-wide cap of 500 therefore holds with 6 brains; a global sweep is the Orchestrator's.
  This replaces the Water Temp pruner that compared date-style keys against ms-style keys and would
  have deleted every other brain's events.
- Per-lake readiness events are capped at 15 per run with one `readiness.changed` summary beyond that.

## 8. Transport policy (both implementations)

| | |
|---|---|
| Retries | 4 attempts; backoff `1.5 · 2^n` s (1.5, 3, 6). Retry on transport errors, 5xx and 429 **only**; never on other 4xx. |
| Timeouts | connect 10 s, read 30 s, per-request 60 s cap. |
| Token | refreshed when < 120 s to expiry; never cached for the writer's lifetime. |
| Payload | `PATCH <root>/.json?print=silent` with `{path: value}`; `null` deletes; ≤ 50 lakes per PATCH. |
| Reads | `GET path.json`, `?shallow=true` for keys; a `"null"` body means absent. |
| Dry run | every implementation offers an in-memory and/or directory store with identical semantics. |

## 9. Registry entry — `/brains/{brainId}`

Required: `brainId, displayName, domain, question, version, schemaVersion, enabled, status (§3 brain
status), health, supportedLakeCount, readinessCounts{readiness→n}, staleLakeCount,
lastSuccessfulRun|null, lastError{at,message}|null, staleAfterHours, stalenessModel, dependsOn[brainId],
schedule{cadence, jobId?, nextCheckAt?, running?, lockedUntil?}, models{active{modelId,status,version}?,
candidates[]}, versions[{version,date,note,status}], validation{ref,status}, sourceIds[], blockers[],
descriptor{components{name→{status, inputs[], staleness, recomputeWhen[]}}}`.

Optional (Phase 5/6 fill these): `score{value|null, scoreVersion, scoreRubric, scoreUpdatedAt,
scoreBreakdown{dim→{value, weight, evidence}}, scoreBlockers[], nextScoreOpportunity}`,
`deploymentVersion`, `breakdowns{}`, brain-specific blocks (Clarity `sensorAuthority`, Wind extras).

`readinessCounts` and `supportedLakeCount` are written **only from a full run**; a partial run keeps
the previous values and sets `health/brains/{id}.partial = true`.

## 10. Failure behavior

On any run failure a brain writes, in one unit: `/health/brains/{id}{status: FAILED, lastRun,
latestError, errorCount}`, `/brains/{id}/health = FAILED`, `/brains/{id}/lastError{at,message}`,
and an activity event `run.failed` (`critical`). Per-lake failures inside an otherwise successful
run: the lake's `slots/{slot}.lastError/lastErrorAt` are set, the previous state is **carried** with
`freshness.stale` re-evaluated (Clarity's `stale_carry`), and health follows §3 thresholds. A
publish failure after partial success is `DEGRADED`, never silently `HEALTHY`.

## 11. Plan / recompute semantics (Orchestrator-facing)

Each brain exposes a pure `plan(published, now, …) → {action: PUBLISH|SKIP, reasons[]}` and a
`descriptor` (registry `descriptor.components`) listing inputs, staleness model and
`recomputeWhen`. Reasons are the orchestrator's audit trail. Page views never trigger recompute.

## 12. Conformance

`docs/brains/conformance/*.json` is the single fixture set. Each implementation has a test that
loads every fixture and asserts the same expectations: lake keys and collisions, illegal keys,
event-id format and ordering, pruning decisions (own-brain, by `at`, caps), retry decisions,
health thresholds, freshness/stale evaluation, ownership checks, and the closed vocabularies.
A brain lands on `main` only when its publisher passes the suite (or is listed below as an adapter).

## 13. Implementation status (2026-10-12, after Phase 7)

| Brain | Publisher | Conforms | Notes |
|---|---|---|---|
| Lake | Swift `Sources/SectorEngine/Brain` (shared) | **yes** (on main) | contract event ids/kinds, ownership-checked stores, own-brain pruning, `platform` ref |
| Water Temp | Swift (shared) | **yes** (on main) | replayed from `brain/water-temp` @ `ec0ae0fa`; readiness = CALIBRATION, evidence in `evidenceClass`; no rollup-field writes |
| Water Clarity | Python `sector_brain_platform` (vendored) | **yes** (on main) | `kind` + freshness beside `stateType`; no rollup-field writes; `failures24h` absent when unknown |
| Biological | Python `sector_brain_platform` | **yes** (on main) | event kinds `brain.registered`/`brain.version` |
| Sector Intelligence | Python `sector_brain_platform` | **yes** (on main) | states carry `kind: not_evaluated` |
| Wind | **temporary adapter**: its own `sector_wind/brain/writer.py` | NO (documented) | live job; event ids `{ms}_wind_{n}`, global pruning by `at`, no retries, `sources.brains` array. Migrates to `sector_brain_platform` in the Wind reconciliation (Phase 8 ownership work); until then it must not prune other brains' events (it prunes by `at` globally — Orchestrator sweep will replace this). |

Each conforming registry entry publishes `platform{implementation, contract, conformant}`.
