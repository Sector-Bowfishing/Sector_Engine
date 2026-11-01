# Customer path for Brain output, V1: Lake level and trend

**Status:** DRAFT design (Sector_Ops #43, 2026-11-01). The owner chose Lake level and trend at the Beta-A lakes as the first
customer-visible Brain output. This build is a draft PR behind gates that all default to UNKNOWN. Nothing is deployed, no flag is on,
and no lake is eligible.

## 1. Why a path is needed
- Every Brain is registered `customerIntegrationMode: none`, and no Engine endpoint serves Brain output. A fully published Brain
  would still not reach the app.
- The data architecture keeps the Engine API as the only customer boundary (`SECTOR_DATA_OWNERSHIP_ARCHITECTURE.md`). The app never
  reads the Brain database, and that does not change here.

## 2. What the Engine serves
`GET /lake/level?lake=<lakeId>` returns one `LakeLevelOutput` (`Sources/SectorEngine/API/LakeLevelOutputAPI.swift`):

| Field | Meaning |
|---|---|
| `status` | `AVAILABLE` (observed level at the lake), `ESTIMATE` (a nearby gauge stands in) or `UNKNOWN` |
| `reason` | Why it is `UNKNOWN` or an `ESTIMATE`: `NOT_ENABLED`, `NOT_VALIDATED_HERE`, `NO_READER`, `BRAIN_NOT_BETA`, `NO_PUBLICATION`, `STALE`, `NO_SOURCE`, `NEARBY_GAUGE` |
| `elevationFt`, `datum`, `observationTime`, `sourceAgeHours` | The published observation, unchanged. The observation time is never replaced by a run time. |
| `trend`, `change24hFt` | Lake's trend vocabulary (`STABLE`, `RISING`, `FALLING`, `RISING_RAPIDLY`, `FALLING_RAPIDLY`, `UNKNOWN`) and the 24 h change |
| `freshUntil` | No newer observation is expected before this time |
| `limitation` | One plain sentence shown beside an `ESTIMATE` |

- **Additive only.** `/conditions` and every existing field are unchanged. The projection reads the Lake publication contract
  (`lake-state-v1`) and ignores fields it does not know, so a Lake schema addition cannot break it.
- **Read-only.** The server reads through `BrainOutputReader`, which has `get` and nothing else.
- **Not in the customer server:** the Lake Brain target. The projection decodes the published JSON itself (`Package.swift`: nothing in the
  customer server imports a Brain target).

## 3. Eligibility rule (every gate fails closed to UNKNOWN)
1. **Switched on:** `SECTOR_LAKE_LEVEL_OUTPUT=1` on the Engine service. Off by default.
2. **Validated at this lake:** the lake is in `LakeLevelEligibility.validatedLakeIds`. This list is code, not configuration, so adding a
   lake is a reviewed PR. It is empty until the frozen Lake Beta validation (level and trend against an independent gauge) is scored
   and the owner approves the lakes that passed.
3. **A reader exists:** the server can read the published state. This build has none. Giving the customer service read access to
   published Brain state is an IAM change and needs its own approval.
4. **Brain readiness:** `/brains/lake-brain/status` is `BETA` or higher. Lake is `CALIBRATION` today.
5. **A publication for this lake:** `/lakes/{key}/states/lake` exists and its stored `lakeId` matches (lake keys are lossy).
6. **Fresh:** the publication is not stale, and it has a value and an observation time.
7. **Source class:** an observed operator pool or lake gauge is `AVAILABLE`. A nearby-gauge proxy is an `ESTIMATE`. Anything else is
   `UNKNOWN`.

## 4. How the app shows it (iOS reader)
- `AVAILABLE`: the level, its trend and "as of" time.
- `ESTIMATE`: the same, with the "Estimate" chip already used for clarity and the `limitation` line.
- `UNKNOWN`: the app keeps what it shows today. It never fills in a level of its own and never shows the reason code as text.
- The reader decodes unknown `status` values as `UNKNOWN`, so a later vocabulary addition is safe.
- The draft iOS reader is not wired to any screen. Wiring it in ships with an app release the owner approves.

## 5. Turning it on (each step needs the owner)
| Step | Gate |
|---|---|
| Score the frozen Lake Beta validation; owner approves the passing lakes into `validatedLakeIds` | owner + PR |
| Lake promoted to `BETA` and publishing again (Brain execution is paused) | owner (resume, readiness) |
| Read access for the customer service to published Brain state | owner (IAM) |
| Merge and deploy the Engine with `SECTOR_LAKE_LEVEL_OUTPUT=1` | owner (deploy) |
| Wire the iOS reader into a screen and release the app | owner (App Store) |

## 6. What this does not decide
- Which screen shows the level, and its wording beyond the chip and the limitation line.
- Any other Brain's customer path. Each follows this pattern with its own eligibility rule.
- The registry's `customerIntegrationMode` for Lake. It changes only when the output is turned on.
