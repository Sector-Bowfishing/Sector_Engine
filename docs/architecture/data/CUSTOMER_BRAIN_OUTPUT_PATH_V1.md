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
`GET /lake/level?lake=<lakeId>` returns one `LakeLevelOutput` (`Sources/SectorEngine/API/LakeLevelOutputAPI.swift`):

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
   reviewed PR. It is empty until the owner approves lakes from the scored validation.
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
- `data-check` will report the new path as undeclared until the family is declared in Cortex (step 1 of §5). That is expected and is
  the Cortex gap, not something to work around in the Engine.

Option B (declare the customer Engine a reader of `fam.lake-states` and move it to the CUSTOMER lane) was not chosen: it would expose
the full internal record at the customer boundary.

## 7. What this does not decide
- Which screen shows the level, and its wording beyond the chip and the limitation line.
- Any other Brain's customer path. Each follows this pattern with its own copy and eligibility rule.
- The registry's `customerIntegrationMode` for Lake. It changes only when the output is turned on.
