# Conditions consolidation, build spec V1 (Sector_Ops #53)

Shared by every repository: Sector_Engine, Sector_Ops, iOS_Sector, Android_Sector and Web_Sector. Field and flag names here are binding. If a change is needed, raise it; do not invent a variant.

## 0. Owner rules (every change)
1. **Phone contract frozen.** `contracts/phone/conditions-phone-contract-v1.json` and the goldens in `verification/fixtures/phone-contract/` must pass (`PhoneContractTests`, `verification/test_phone_contract.py`). `/conditions` keeps the same URL, fields and meanings. Additive fields only. Dates are ISO 8601 with seconds precision (`SectorEngineAPI.makeEncoder()`).
2. **Fallback.** A tile served from a new source falls back to today's live answer when the new source has none, or has a stale or failed value. No tile may go blank because of a step.
3. **Shadow first.** Compute old and new, serve old, log the difference.
4. **One tile per flag.** A flag rolls back without an app update or a deploy.
5. **Nothing removed while used.** Old code paths and fields stay.
6. **Per-tile watch with automatic rollback** (the circuit breaker, §3).
7. **Every flag defaults to `off`.** Code merges with all flags off. Turning a flag to `shadow` or `serve` is the owner's decision.

## 1. Tiles and flag keys
| Tile | Flag key | Old path (today) | New path | Source id (new) |
|---|---|---|---|---|
| Humidity | `humidity` | Open-Meteo `weather.humidity` | NWS/NBM | `nws-nbm` |
| Barometric Pressure | `pressure` | Open-Meteo `weather.pressure`, `pressureTrend`, `pressureChange` | NWS/NBM | `nws-nbm` |
| Temperature | `temperature` | Open-Meteo `weather.temperature` | NWS/NBM | `nws-nbm` |
| Sky | `sky` | Open-Meteo `weather.cloudCover`, `weatherCode`, `conditionSymbol`, `conditionDescription` | NWS/NBM, mapped to WMO codes and SF Symbols | `nws-nbm` |
| Wind | `wind` | Open-Meteo `weather.windSpeed`, `windDirection` | NWS/NBM | `nws-nbm` |
| Wind outlook model | `windOutlookModel` | env `SECTOR_WIND_FORECAST_MODEL` (#125) | Wind Brain customer copy `/customer/wind/outlookModel` | `wind-brain` |
| Water Level | `waterLevel` | `water` (nearest gauge; FROZEN meaning) | Lake Brain customer copy, in the **additive** field `lakeLevel` | `lake-brain` |
| Clarity | `clarity` | the Engine's `VisibilityModel` (clarity factor) | Water Clarity Brain customer copy, in the **additive** `clarityBrain`; in `serve` it also feeds the clarity factor | `water-clarity-brain` |
| H2O Temp | `waterTemp` | `waterTempModel` (FROZEN) and `waterTemp`/`waterTempState` | Water Temp Brain customer copy, in the **additive** `waterTempBrain` | `water-temp-brain` |
| Generation | `generation` | Engine `GenerationService` + `TailwaterRegistry` | Lake Brain dam bindings `/customer/lakes/{k}/generationBinding`; the live fetch stays in the Engine | `lake-brain-bindings` |
| Moon Phase | – (app) | app math | app math to `contracts/moon/moon-v1.json` | `app` |

Flag modes: `off` | `shadow` | `serve`.
- `off`: the new path is not computed.
- `shadow`: compute both, serve old, log the difference.
- `serve`: use new when it is AVAILABLE and the breaker is closed, otherwise old.
- **Frozen fields are never overwritten in `serve`.** `water`, `waterTempModel` and `discharge` keep their build 28 meaning. Weather fields keep their units: deg F, mph, hPa, % and WMO codes.

## 2. Flag store
- Firebase Remote Config parameter **`conditions_tiles_v1`**: a JSON string, read through the same REST and metadata-token path as `conditions_config` (`RemoteConfigStore`), with a 10-minute TTL and last-good fallback. Shape:
  ```json
  {"version":1,"tiles":{"humidity":{"mode":"off"},"waterLevel":{"mode":"shadow","lakes":["Guntersville|AL"]}}}
  ```
  `lakes` (optional) limits `shadow`/`serve` to those lake ids. A missing, invalid or unknown key means `off`.
- Local and test override: env `SECTOR_CONDITIONS_TILES_V1` (same JSON); it wins over Remote Config. Production never sets it.

## 3. Circuit breaker (rule 6)
Per tile, in process. It is evaluated only for tiles in `serve`.
- Window: the last 15 minutes of new-path attempts, with at least 20 samples.
- **Trips** when, over the window, any one of these holds:
  - the new-path failure or blank rate is more than 10 percentage points above the old path's rate in the same window;
  - the new path's p95 fetch latency is more than 3 s above the old path's.
- When tripped, serve old for 30 minutes, then half-open: try new on 10% of requests until 20 good samples.
- Log line: `[tile-breaker] {"tile":"humidity","state":"open","reason":"...","window":{...}}`
- The thresholds are constants in one file, `TileBreaker.swift`.

## 4. Additive response fields (`/conditions`)
All optional, and all omitted when there is nothing to say.

```json
"tileSources": {
  "humidity":   {"flag":"off","path":"engine","source":"open-meteo","status":"AVAILABLE","observedAt":"2026-11-10T15:00:00Z"},
  "waterLevel": {"flag":"serve","path":"brain","source":"lake-brain","status":"AVAILABLE","observedAt":"…","freshUntil":"…","runner":"pulse","publishId":"7def2674"},
  "moon":       {"flag":"off","path":"app","source":"moon-v1","status":"AVAILABLE"}
}
```
- `path`: `engine` | `brain` | `app`
- `status`:
  - `AVAILABLE`
  - `ESTIMATE` (modeled or nearby source)
  - `FALLBACK` (serve was on, but old was served)
  - `UNKNOWN` (no value)
- `runner`: `pulse` | `cloud` | `engine`
- All 10 tile keys are always present once the foundation ships, so the apps can rely on `tileSources[key]` existing.

`lakeLevel` uses the existing `LakeLevelOutput` shape (`LakeLevelOutputAPI.swift`), present only when the `waterLevel` flag is `serve` and the lake is eligible.

`clarityBrain`:
```json
{"lakeId":"Guntersville|AL","status":"AVAILABLE","centralFt":2.25,"lowFt":1.5,"highFt":3.0,"confidence":"medium","observedAt":"…","freshUntil":"…","runner":"pulse","publishId":"…"}
```

`waterTempBrain`:
```json
{"lakeId":"…","status":"AVAILABLE","valueF":64.2,"kind":"measured|modeled","observedAt":"…","freshUntil":"…","runner":"…","publishId":"…"}
```

`generation` (additive keys inside the existing object; build 28 ignores unknown keys):
```json
"history":[{"at":"…","dischargeCfs":3200,"generators":2}],
"tailwaterHistory":[{"at":"…","ft":553.2}],
"source":"tva-restapi",
"fetchedAt":"…",
"bindingSource":"engine-registry|lake-brain"
```

## 5. Customer-lane copies (written by the Publisher, read by the Engine)
| Path | Schema | Writer gate |
|---|---|---|
| `/customer/lakes/{k}/level` | `sector-customer-lake-level-v1` (exists) | existing |
| `/customer/lakes/{k}/clarity` | `sector-customer-clarity-v1` `{schema, lakeId, status, centralFt, lowFt, highFt, confidence, observedAt, freshUntil, runner, publishId}` | Publisher env `PUBLISHER_CUSTOMER_CLARITY=1` (default off) |
| `/customer/lakes/{k}/waterTemp` | `sector-customer-water-temp-v1` `{schema, lakeId, status, valueF, kind, observedAt, freshUntil, runner, publishId}` | `PUBLISHER_CUSTOMER_WATER_TEMP=1` (default off) |
| `/customer/lakes/{k}/generationBinding` | `sector-customer-generation-binding-v1` `{schema, lakeId, operatorId, damId, damName, cwmsOffice?, tvaCode?, updatedAt}` | `PUBLISHER_CUSTOMER_GENERATION_BINDING=1` (default off) |
| `/customer/wind/outlookModel` | `sector-customer-wind-outlook-model-v1` `{schema, tonight:"best_match", nights2to7:"ncep_nbm_conus", decidedBy, evidence, updatedAt}` | `PUBLISHER_CUSTOMER_WIND_MODEL=1` (default off) |

- The Engine reads them only through `BrainOutputReader`, which is read-only. With no reader (no IAM yet) every copy is `UNKNOWN`, which means old path.
- `{k}` is `BrainPlatform.lakeKey(lakeId)`, and a copy's `lakeId` must match.
- Any **database rules or IAM** for these paths ship as a proposed file in the PR and are applied only on the owner's approval.

## 6. Request log (rule 5)
One line per `/conditions` request (cache hits included):
```
[conditions-request] {"app":"ios","appBuild":"28","cache":"hit","ms":42,"lakeId":"Guntersville|AL","latR":34.4,"lonR":-86.3,"tiles":{"humidity":{"flag":"off","status":"AVAILABLE","blank":false}}}
```
- `app`/`appBuild` come from the User-Agent:

  | User-Agent | `app` | `appBuild` |
  |---|---|---|
  | `Sector/<build> CFNetwork/...` | `ios` | build |
  | `Sector-Android/<versionName> (<versionCode>)` | `android` | versionCode |
  | `okhttp/...` | `android` | `unknown` |
  | `Sector-Web/<v>` | `web` | `<v>` |
  | anything else | `other` | – |

- Coordinates are rounded to 0.1 degree. No user ids, ever.

Shadow lines:
```
[tile-shadow] {"tile":"humidity","old":61,"new":58,"delta":-3,"oldSource":"open-meteo","newSource":"nws-nbm","lakeId":"…","latR":…,"lonR":…}
```

## 7. Ops projection
The Orchestrator, behind env `CONDITIONS_SOURCES_PROJECTION=1` (default off), writes **`/control/conditionsSourcesV1`** every cycle (≥15 min). It probes Engine `/conditions` at the 17 points in `verification/fixtures/phone-contract/points-v1.json` (the normal request path, which hits the 5-minute cache) and reads `tileSources`. It merges in each Brain's `/brains/{id}/lastSuccessfulRun` and the runner lease (pulse or cloud). Shape:
```json
{"schema":"sector-conditions-sources-v1","generatedAt":"…","engineRevision":"…",
 "tiles":{"humidity":{"class":2,"flag":"off","sourcePath":"engine:open-meteo","fresh":"green|amber|red","lastUpdate":"…","runner":"engine",
                      "coverage":{"ok":17,"total":17},"breaker":"closed","contractOk":true,
                      "lakes":{"Guntersville|AL":{"status":"AVAILABLE","observedAt":"…","path":"engine","source":"open-meteo"}}}}}
```
Freshness: green when within `freshUntil` (class 2: within 2× the source cadence); amber when within 2× that; red when stale or UNKNOWN.

**Amendment 1 (2026-11-06, from the Ops review):**
- **Two times per tile and per lake.** `lastUpdate` is the source's own observation time, never a run time. `fetchedAt` is when the Engine fetched it, or when the Publisher published the Brain copy. Both are optional ISO strings.
- **Eligibility.** Every `lakes[id]` entry carries `"eligible": true|false`. Eligible means the tile's flag applies at that point: a `lakes` list in the flag limits it to those lakes, otherwise every probe point is eligible. A tile whose flag is `off` has every point eligible for the old path.
- **Coverage.** `coverage = {"ok": n, "fallback": n, "unknown": n, "total": n}` counts ELIGIBLE points only.
- **Banner.** It fires when `coverage.fallback / coverage.total > 0.10` for any tile, or when `contractOk` is false.

## 8. Apps
- Every new field is decoded as optional. A new build must work against today's server, where none of these fields exist.
- Android sends `User-Agent: Sector-Android/<versionName> (<versionCode>)`. iOS keeps its CFNetwork default (`Sector/<build>`). Web sends `Sector-Web/<version>` where browsers allow it, or an `X-Sector-Client: web/<version>` header (the Engine logs either).
- Display rules (new builds):
  - **Level:** `lakeLevel` AVAILABLE shows the level, its trend and "as of"; otherwise today's `water` view.
  - **H2O Temp:** `waterTempBrain` AVAILABLE shows it; otherwise `waterTemp`/`waterTempState`; otherwise `waterTempModel`.
  - **Clarity:** `clarityBrain` AVAILABLE shows it; otherwise today's view, with an "Estimate" chip when `tileSources.clarity.status == "ESTIMATE"`.
  - **Every tile:** an "as of" time from `tileSources[tile].observedAt` when present.
- **Generation sheet:** read the Engine's `generation` (plus the additive `history`/`tailwaterHistory`) first, and fall back to the on-device fetch only when the Engine block is absent.
- **Moon:** unit tests run `contracts/moon/moon-v1.json` (copy the file into the app repo's test resources, citing its source).

## Amendment 2 (2026-11-06, from the Android build)
- **Additive keys inside `water` and `discharge`:** `siteCode` (string), `siteName` (string), `distanceMiles` (number), `observedAt` (ISO). Optional; build 28 ignores unknown keys. The Engine fills them from the gauge it already used (WaterLevelReading has them).
- **Apps go Engine-first for the Water Level card only when `water.siteName` is present.** Otherwise they keep today's on-device view, so the station name and distance never disappear.

## Engine implementation note: Web CORS (Sector_Engine, foundation PR)
*Added in the Engine repo only; not part of the shared spec text above.*

`GET /conditions` and `GET /health` answer browser requests from this allow-list only (`Sources/SectorEngine/Conditions/CORSPolicy.swift`). Origins come from the Web repo (Sector-Web): the `firebase.json` / `.firebaserc` hosting targets (prod `sector-9393c`, dev `sector-9393c-dev`) and the custom domain.
- `https://sectorbowfishing.com`
- `https://www.sectorbowfishing.com`
- `https://sector-9393c.web.app`
- `https://sector-9393c.firebaseapp.com`
- `https://sector-9393c-dev.web.app`
- `https://sector-9393c-dev.firebaseapp.com`
- `http://localhost:3000`, only when env `SECTOR_CORS_DEV=1`

Rules: the allowed origin is echoed in `Access-Control-Allow-Origin`, never `*`, and no credentials. Every response to a request with an `Origin` carries `Vary: Origin`. The preflight `OPTIONS` answers 204 with `Access-Control-Allow-Methods: GET`, `Access-Control-Allow-Headers: X-Sector-Client, Accept` and `Access-Control-Max-Age: 600`. A request without an `Origin` (the apps) is unchanged, and `OPTIONS` without an `Origin` is still 404.
