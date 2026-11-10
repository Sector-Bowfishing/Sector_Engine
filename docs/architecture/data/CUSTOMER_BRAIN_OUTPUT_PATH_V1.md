# Customer path for Brain output, V1: Lake level and trend

**Status:** DRAFT design (Sector_Ops #43, #44, 2026-11-01). The owner chose Lake level and trend at the Beta-A lakes as the first
customer-visible Brain output, and chose the lane on #44: **the Publisher writes a CUSTOMER-lane copy and the Engine reads only that**
(§6). This build is a draft PR behind gates that all default to UNKNOWN. Nothing is deployed, no flag is on, no copy is written and no
lake is eligible.

## 1. Why a path is needed
- Every Brain is registered `customerIntegrationMode: none`, and no Engine endpoint serves Brain output. A fully published Brain
  would still not reach the app.
- The data architecture keeps the Engine API as the only customer boundary (`SECTOR_DATA_OWNERSHIP_ARCHITECTURE.md`). The app never
  reads the Brain database, and that does not change here.
- Customer components read only CUSTOMER-lane families (Cortex `firebase-data.md` FD-13, `operations.md` IO-06). Lake's published
  state (`fam.lake-states`) is INTERNAL and stays INTERNAL.

## 2. What the Engine serves
`GET /lake/level?lake=<lakeId>` (routed only where `SECTOR_LAKE_LEVEL_OUTPUT=1`; with the flag off the server has no such route) returns one `LakeLevelOutput` (`Sources/SectorEngine/API/LakeLevelOutputAPI.swift`):

| Field | Meaning |
|---|---|
| `status` | `AVAILABLE` (observed level at the lake), `ESTIMATE` (trend from a nearby gauge) or `UNKNOWN` |
| `reason` | Why it is `UNKNOWN` or an `ESTIMATE`: `NOT_ENABLED`, `NOT_VALIDATED_HERE`, `NO_READER`, `NO_PUBLICATION`, `STALE`, `NO_SOURCE`, `NEARBY_GAUGE` |
| `elevationFt`, `datum` | `AVAILABLE` only. The observed level, unchanged. |
| `observationTime`, `sourceAgeHours` | When the source measured it. The observation time is never replaced by a run time. |
| `trend` | Lake's trend vocabulary (`STABLE`, `RISING`, `FALLING`, `RISING_RAPIDLY`, `FALLING_RAPIDLY`) |
| `change24hFt` | `AVAILABLE` only. The 24 h change. |
| `freshUntil` | No newer observation is expected before this time |
| `limitation` | One plain sentence shown beside an `ESTIMATE` |

- **A proxy is trend only.** An `ESTIMATE` never carries an elevation, a datum or a change in feet, even if a copy did (Cortex
  `lake.md` LC-06: a nearby-gauge proxy is never represented as observed lake elevation).
- **Additive only.** `/conditions` and every existing field are unchanged. The Engine ignores copy fields it does not know.
- **Read-only.** The server reads through `BrainOutputReader`, which has `get` and nothing else.
- **Not in the customer server:** the Lake Brain target, and any read of Brain INTERNAL paths (`/lakes/*/states`, `/brains/*`).

## 3. Eligibility (every gate fails closed to UNKNOWN)
The gates are split so each side checks what it owns.

**At publish time, in the Publisher** (it writes a copy only when all pass, and writes `status: UNKNOWN` over an earlier copy when
one stops passing):
1. Lake's readiness (`/brains/lake-brain/status`) is `BETA` or higher. Lake is `CALIBRATION` today.
2. The lake passed the frozen Lake Beta validation and the owner approved it (the same list as gate 5 below).
3. The Lake publication for this lake exists, its stored `lakeId` matches (lake keys are lossy), and it is not stale.
4. Source class: an observed operator pool or lake gauge gives `AVAILABLE`. A labelled nearby-gauge proxy gives `ESTIMATE` (trend
   only). Anything else gives no copy.

**On every request, in the Engine:**

5. **Switched on:** `SECTOR_LAKE_LEVEL_OUTPUT=1` on the Engine service. Off by default.
6. **Validated at this lake:** the lake is in `LakeLevelEligibility.validatedLakeIds`. This list is code, so adding a lake is a
   reviewed PR. It holds the 30 lakes the owner approved on Sector_Ops #45 from the scored Lake Beta validation (18 class A, 12
   class B). Same-instrument passes, failures, abstentions and the four home lakes are not on it.
7. **A reader exists.** This build has none. Read access to the copy is an IAM change and needs its own approval.
8. **A copy for this lake:** `/customer/lakes/{lakeKey}/level` exists, its `schema` is `sector-customer-lake-level-v1` and its
   `lakeId` matches.
9. **Still fresh:** the request time is not after `freshUntil`, and an `AVAILABLE` copy has a value and an observation time. A copy
   can go stale after it was written, so this is checked again on every request.

## 4. How the app shows it (iOS reader)
- `AVAILABLE`: the level, its trend and "as of" time.
- `ESTIMATE`: the trend and "as of" time with the "Estimate" chip already used for clarity, and the `limitation` line. No level.
- `UNKNOWN`: the app keeps what it shows today. It never fills in a level of its own and never shows the reason code as text.
- The reader decodes unknown `status` values as `UNKNOWN`, so a later vocabulary addition is safe.
- The draft iOS reader is not wired to any screen. Wiring it in ships with an app release the owner approves.

## 5. Turning it on (each step needs the owner)
| Step | Gate |
|---|---|
| Declare the CUSTOMER-lane family for the copy in Cortex (Cortex maintenance session; Engine Cortex gap CG-3.1-8) | owner + Cortex release |
| Publisher writes the copy (§6), reviewed and merged | owner + PR |
| Owner approves the passing lakes from the scored Lake Beta validation into `validatedLakeIds` and the Publisher's list | owner + PR |
| Lake promoted to `BETA` and publishing again (Brain execution is paused) | owner (resume, readiness) |
| Read access for the customer service to the copy only | owner (IAM) |
| Merge and deploy the Engine with `SECTOR_LAKE_LEVEL_OUTPUT=1` | owner (deploy) |
| Wire the iOS reader into a screen and release the app | owner (App Store) |

## 6. The CUSTOMER-lane copy (decided on Sector_Ops #44: option A)
- **Path:** `/customer/lakes/{lakeKey}/level`. One node per eligible lake.
- **Writer:** the Publisher only (the platform's single authorized writer), after it applies gates 1 to 4. No Brain writes it.
- **Reader:** the customer Engine only (`service.customer-engine`). Lane `CUSTOMER`. Proposed family id `fam.customer-lake-level`.
- **Schema `sector-customer-lake-level-v1`:**

| Field | Type | Rule |
|---|---|---|
| `schema` | string | `sector-customer-lake-level-v1` |
| `lakeId` | string | The Lake Registry id (keys are lossy) |
| `status` | string | `AVAILABLE`, `ESTIMATE` or `UNKNOWN` |
| `elevationFt`, `datum` | number, string | `AVAILABLE` only; else absent |
| `observationTime` | ISO 8601 | The source's observation time |
| `sourceAgeHours` | number | At write time |
| `trend` | string | Lake's trend vocabulary |
| `change24hFt` | number | `AVAILABLE` only |
| `freshUntil` | ISO 8601 | From the Lake publication |
| `brainId`, `sourceRelease`, `writtenAt` | string | Provenance: `lake-brain`, the Lake publication release, the write time |

- Nothing else from Lake's INTERNAL record is copied: no pool, zone, percentile, band, release, provenance detail or binding.
- **Publisher side (draft, Sector_Ops #47):** `jobs/brain_platform/sector_brain_platform/publisher_live/customer_lake_level.py` plans these writes from one Lake write set and applies gates 1 to 4.
  - The owner-approved list is `customer_lake_level_eligible.json`. A test keeps it equal to the Engine's `validatedLakeIds`.
  - A lake that stops passing, including one removed from the list or a demoted Brain, gets `status: UNKNOWN` over its old copy.
  - **It is not wired into the LivePublisher's atomic apply yet.** That needs Lake CENTRAL, the Cortex family (proposal `docs/cortex/proposals/CG-3.1-8-customer-lake-level-family.md`) and the owner's approval.
- `data-check` will report the new path as undeclared until the family is declared in Cortex (step 1 of §5). That is expected and is
  the Cortex gap, not something to work around in the Engine.

Option B (declare the customer Engine a reader of `fam.lake-states` and move it to the CUSTOMER lane) was not chosen: it would expose
the full internal record at the customer boundary.

## 7. What this does not decide
- Which screen shows the level, and its wording beyond the chip and the limitation line.
- Any other Brain's customer path. Each follows this pattern with its own copy and eligibility rule.
- The registry's `customerIntegrationMode` for Lake. It changes only when the output is turned on.

## 8. Conditions consolidation copies (Sector_Ops #53, spec §5)
Four more CUSTOMER-lane copies follow §3 and §6 exactly: a pure Publisher planner per copy (Brain-side gates; `status: UNKNOWN`
written once over a copy that stops passing) and a read-only Engine reader per copy (every gate fails closed to UNKNOWN with a
reason; freshness checked again on every request). Each Publisher writer also sits behind its own env switch, **default off**.
Nothing is wired: no writer is called by the LivePublisher, no reader is called by `/conditions`, and there is no reader identity.
Review fixes (#144): a switch turned off withdraws every live copy once with `status: UNKNOWN` (reason `NOT_ENABLED`); a source time more
than 10 minutes in the future is refused by writers and readers; clarity freshness is `min(freshUntil, evaluationTime + staleAfterHours)`
so a new run cannot make an old evaluation look fresh; a generation binding is `STALE` 30 days after its review time.

| Copy | Schema | Publisher writer (switch) | Source | Engine reader |
|---|---|---|---|---|
| `/customer/lakes/{k}/clarity` | `sector-customer-clarity-v1` | `customer_clarity.py` (`PUBLISHER_CUSTOMER_CLARITY=1`) | Water Clarity state; observed → AVAILABLE, modeled → ESTIMATE; `observedAt` = the state's `evaluationTime` | `ClarityBrainOutputAPI` → `clarityBrain` |
| `/customer/lakes/{k}/waterTemp` | `sector-customer-water-temp-v1` | `customer_water_temp.py` (`PUBLISHER_CUSTOMER_WATER_TEMP=1`) | Water Temp state; `measured` only; `freshUntil` = `lastObservationAt` + the Brain's `staleAfterHours` | `WaterTempBrainOutputAPI` → `waterTempBrain` |
| `/customer/lakes/{k}/generationBinding` | `sector-customer-generation-binding-v1` | `customer_generation_binding.py` (`PUBLISHER_CUSTOMER_GENERATION_BINDING=1`) | Lake reviewed bindings contract, proposed `damBinding` per record | `GenerationBindingOutputAPI` |
| `/customer/wind/outlookModel` | `sector-customer-wind-outlook-model-v1` | `customer_wind_outlook_model.py` (`PUBLISHER_CUSTOMER_WIND_MODEL=1`) | Wind `activeProductionModel.outlookModel` (proposed); stale after 14 days | `WindOutlookModelOutputAPI` |

Gaps (each needs the owning Brain, then the owner):
- **Water Temp modeled lakes** carry no source observation time, so they get no copy (`NO_OBSERVATION_TIME`); the spec's
  `kind: modeled` ESTIMATE needs the Brain to publish the model's valid time.
- **Lake dam bindings** are not published. `reviewed-lake-bindings-v1` binds lakes to pool-level sources, not to a generating dam,
  so every lake gets `NO_DAM_BINDING` and the Engine keeps `TailwaterRegistry`.
- **Wind outlook decision** is not published, so the writer writes nothing (`NO_PUBLICATION`) and the Engine keeps the env path.

Registered as `PLACEHOLDER` in `publisher/paths.py` (`CUSTOMER_COPY_FAMILIES`) and the path ownership matrix. Client rules: proposed in
`platform/security/rtdb.rules.customer-copies.PROPOSED.json` (deny every client, as today), not applied.

## 9. `GET /lakes/ready`: which lakes have Brain data (Sector_Engine #156)
The app's lake picker (iOS_Sector #227) lists only **ready** lakes. The app may not read the Brain database, and `/conditions`
answers for any coordinate, so the Engine serves the list from the same CUSTOMER-lane copies (`LakesReadyAPI.swift`).

- **Route:** `GET /lakes/ready`, registered only where `SECTOR_LAKES_READY_OUTPUT=1`. Off by default: no route, `404`, as
  `/lake/level`.
- **Reads:** one read of `customer/lakes` through the configured `BrainOutputReader` (`SECTOR_BRAIN_OUTPUT_READER`; none by default),
  cached 60 s. Each directory lake's `clarity`, `waterTemp` and `level` copies are then evaluated by their own readers (§2, §8) against
  that snapshot, which refuses every path other than `customer/lakes/{k}/{clarity|waterTemp|level}`. Never `/lakes/*/states` or
  `/brains/*`. One subtree read replaces ~1,900 per-copy reads per request; freshness is still checked on every request.
- **Ready rule:** a layer is ready when its reader returns `AVAILABLE` (served as `LIVE`) or `ESTIMATE`, with a source time no more
  than 10 minutes ahead; a lake is listed when at least one layer is ready. `level` also needs gates 5 and 6 (§3). No reader, no
  copies or a failed read give `200` with `lakes: []`: the app shows "no lakes yet".
- **Layers without a copy:** `wind` (its only copy is the global `customer/wind/outlookModel`, a model choice) and `intelligence`
  (no copy). v1 never emits them; a later copy adds them under the same name and shape (additive).
- **Shape and contract:** `contracts/phone/lakes-ready-v1.json`, golden `verification/fixtures/phone-contract/lakes-ready-v1.golden.json`
  (synthetic), checked by `LakesReadyAPITests` and `verification/test_lakes_ready_contract.py`.

```json
{"version":1,"generatedAt":"2026-11-10T15:30:00Z","lakes":[
  {"lakeId":"Berlin Lake|OH","name":"Berlin Lake","centroid":{"lat":41.03,"lon":-81.0},
   "layers":{"clarity":{"status":"LIVE","asOf":"2026-11-10T14:00:00Z"},"level":{"status":"LIVE","asOf":"2026-11-10T15:00:00Z"}}}]}
```

Turning it on needs the owner, in addition to §5: `SECTOR_LAKES_READY_OUTPUT=1` on a deploy, the reader env and its IAM read grant,
and the Publisher copy switches (`PUBLISHER_CUSTOMER_*`). Nothing in this build sets any of them.
