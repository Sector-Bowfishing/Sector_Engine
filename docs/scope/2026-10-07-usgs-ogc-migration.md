# USGS WaterServices → Water Data OGC API migration

**Date:** 2026-10-07 · **Branch:** `fix/usgs-ogc-migration` · **Status:** engine done (not deployed); iOS planned

## Why

USGS is shutting down legacy WaterServices (`waterservices.usgs.gov/nwis/iv/`) in Q1 2027. From November 2026 through February 2027 it "may include intentional service degradation and blackouts" (USGS blog, `api-waterservices-decom`). The replacement is `https://api.waterdata.usgs.gov/ogcapi/v1/`. Parameter codes created after June 2026 exist only there.

## Engine (this PR)

`WaterLevelService.nearbyReadings` is the only USGS caller. It feeds `latestReading`, `nearestDischarge`, `nearestWaterTemp` and `nearestTurbidity`. The water-temp and turbidity readers are not edited; they move to the new API because they share this one fetch.

| Legacy | OGC replacement |
|---|---|
| `/nwis/iv/?bBox&parameterCd&period=PT12H&siteStatus=active` | `continuous/items?bbox&parameter_code&time=PT12H`, paged via `rel=next` |
| `sourceInfo.siteName` | `monitoring-locations/items?id=…` (cached per process) |
| first `values` block when a site has several sensors | `time-series-metadata` pick: Primary → no sublocation → oldest → id (cached) |
| `unitCode` / `variableName` | mapped back to the legacy spellings (`ft^3/s`→`ft3/s`, `degC`→`deg C`, `_FNU`→`FNU`) |

These are unchanged:
- Trend math, now `WaterLevelService.reading(from:)` and shared by both paths.
- The 12 h freshness window: a series with nothing in the window is absent from both APIs.
- The box widening (0.25° → 1.0° → 2.5°), the 40-mile cap and the NWPS reservoir override.

Legacy stays as a **fallback** until the decommission. If the new API returns 429 or fails, we get the slower legacy answer instead of no reading. Delete `legacySeries`/`decodeLegacy` once WaterServices is gone. The tests keep `decodeLegacy` as their reference, so move it into the test target at that point.

### Verified equivalence (2026-10-07)

Live, by box: Guntersville, Lake Lanier, Fort Worth, Kentucky Lake and Baton Rouge, across 00065/62614/00060/00010/63680. That covered 1,000+ series. Site set, names, coordinates, values, timestamps and point counts were identical apart from these:
- **OGC is fresher.** Some sites publish newer 15-minute values to OGC before legacy.
- **Legacy dropped live gauges.** At sites where a discontinued sensor is listed first, legacy kept that empty block and dropped the site. Example: turbidity at `05595000`.
- **Legacy showed secondary sensors.** At about 2% of sites, legacy put a secondary sensor first; at Fort Worth this read 5–14 ft off the primary. OGC now takes the Primary sensor.

The new API was 2–5× faster: 0.5–5 s vs 5–14 s. Legacy timed out outright several times during testing, which matters against the 9 s `withDeadline` budget.

`USGSWaterDataTests` pins all of this on fixtures recorded from both APIs at the same moment.

### ⚠️ Rate limit — needs an API key before deploy

With no key, the OGC API rate-limits by IP. In testing it returned 429 after roughly 100–200 requests and stayed throttled for over 10 minutes. It sends no `X-RateLimit` headers to show where the limit sits. Cloud Run egress will hit this quickly.

- Register a free key at https://api.waterdata.usgs.gov/signup/ (api.data.gov).
- Set it on the service: `gcloud run services update sector-engine --update-env-vars USGS_API_KEY=…`, or as a secret. The client sends it as `X-Api-Key`.
- If the keyed limit is still tight, USGS invites custom limits via wdfn@usgs.gov.
- Request cost per box after warm-up: 1 `continuous` request, plus 1 extra page only on very wide boxes. Name and metadata lookups are cached.

### Not done here: 62615 / 00062

62615 (lake elevation, NAVD88) and 00062 (reservoir elevation above datum) are live at about 250 and 89 sites, and the level lookup doesn't request them. Adding them is a **behaviour change**: on those lakes the nearest gauge flips from a river stage to the lake surface. It needs its own decision on:
- datum, since display values would be NAVD88 or local rather than NGVD29;
- the full-pool comparison (the operator-datum rule);
- parity with the iOS and Android fallbacks.

It's a one-line change to `parameterCodes` plus two `legacyParameterName` rows. Recommended as a separate PR after this one is live.

## iOS app (`Sector`, trunk `Michael-Master`) — plan, not in this PR

| File | Today | Change |
|---|---|---|
| `Sector/Utils/WaterLevelService.swift` (`USGSWaterDataAPI`) | OGC **v0** `latest-continuous`, then a per-site history call; legacy as fallback | Move to **v1**. Use the `continuous` + `time=PT12H` design from this PR: one request, with an implicit freshness filter. |
| same | `latest-continuous` returns series last updated **months ago**, and the nearest one wins regardless of age | Fixed by the change above. Today a gauge that died in August can be shown as "now". |
| same | OGC units shown raw (`ft^3/s`, `degC`) | Apply the same legacy-spelling map. |
| `Sector/FishIntel/Sources/TributaryFlowService.swift` | legacy `/nwis/iv/?sites=…&parameterCd=00060&period=PT48H` | `continuous/items?monitoring_location_id=USGS-a,USGS-b&parameter_code=00060&time=PT48H`. Group by series, take the Primary sensor, keep `maxAgeHours`. |
| `scripts/fishintel/build_lake_profile.py` | OGC v0 | Move to v1 (offline tool, low priority). |

Rate limits are per device IP on iOS, so no key is needed there. But v0 also returned 429 during this testing.
