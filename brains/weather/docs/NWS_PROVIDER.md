# NWS provider (api.weather.gov) for the Weather Brain

Provider ids: `nws-station-observations`, `nws-forecast-grid` (`providers/PROVIDERS.json`, acquisition owner `weather`).

## Terms

- **Data status.** NWS data are U.S. Government works: public domain, free, no key, no account
  (https://www.weather.gov/disclaimer; API documentation https://www.weather.gov/documentation/services-web-api).
- **User-Agent required.** NWS asks every caller to send a User-Agent that identifies the application and gives a contact, and may block
  requests without one. The runtime sends `Sector-WeatherBrain/0.1 (io.sector.co; read-only public data)` by default; the deployed job sets
  `SECTOR_WEATHER_USER_AGENT` to the same string plus the owner's contact address, as the Lake Brain's `Sector-LakeBrain` agent does.
- **Documented API.** Only the documented endpoints are used: `/points/{lat},{lon}`, the station list it links, `/stations/{id}/observations`,
  and `/gridpoints/{wfo}/{x},{y}`. No scraping, no undocumented host. `Accept: application/geo+json`.
- **Rate.** NWS publishes no fixed limit and returns 429/5xx when a caller is too fast. The client paces requests (0.25 s), retries 429/5xx
  with backoff (1.5 · 2^n s, 4 attempts) and never retries other 4xx.
- **Source-access rule.** These terms satisfy the owner's source-access rule: a public, documented, free API whose terms permit automated
  reading with identification. Nothing here needs a login, a key, a purchase or an agreement.

## Requests per run (621 directory lakes)

| Request | When | Count |
|---|---|---|
| `/points` + station list | every run in the Cloud Run job today: `deploy-job.sh` points `--point-cache` at `/tmp`, which does not survive the run, so each lake due in a run is re-resolved. With a persistent cache it would be once per 30 days per lake (`PointCache`) | ≤ 2 × due lakes per run (≤ 2 × 621) |
| `/gridpoints/...` | per run, once per distinct grid cell among the due lakes | ≤ number of due lakes |
| `/stations/{id}/observations?start=now−13h&limit=200` | per run, once per distinct station among the due lakes' 3 nearest | ≤ 3 × due lakes, usually far fewer (shared stations) |

With the adaptive cadence (CHANGE/WATCH every hourly grant, STEADY every second grant) a full-directory hour is at most about 2,500
requests with a warm point cache, about 10 minutes at the 0.25 s pace; with today's ephemeral cache add up to 2 × 621 point and station
requests per run (about 5 more minutes). That must be measured on the first dry run before activation (plan §6 step 1).

**Open owner decision before turn-on step 7 (plan §6.1):** persist the point cache, for example as a Weather-owned node in the Brain DB or a
small GCS object owned by `weather` (either is a new write path and needs its own registration and approval), or accept the extra requests
and their cost against the 2 USD/month cap. The cloud job still persists nothing.

**Pulse route (decision recorded in chat, Michael 2026-11-23; WEATHER_BRAIN_PLAN.md §6.2):** the point cache is a durable local file in the
runner's data folder (`--point-cache` or `$SECTOR_WEATHER_POINT_CACHE`; never inside the checkout, never committed). Entries are keyed by lake id +
the coordinate at the 4 decimals `/points` is called with and kept 30 days. A cached gridpoint URL that answers 404 or a redirect (301/308) is
re-resolved in the same run (once per lake per run; if the re-resolve fails, the old entry is kept); a redirect target replaces the cached URL;
a cached station that answers 404 or redirects flags the entry for re-resolution next run. An entry at a lake's old coordinate is pruned.
An unreadable or foreign cache file is ignored and rewritten. With a warm cache a run makes no `/points` or station-list request.

**A `/points` 404 is not "out of coverage" for a US lake.** Every directory lake is in the US, so a 404 there is almost always an NWS outage:
nothing is cached, the lake keeps its last state while it is still fresh (else it has no state this run), and `/points` is retried next run.
BLOCKED is recorded only for a point outside the US NWS area boxes (CONUS, Alaska, Hawaii, Puerto Rico/USVI, Guam/CNMI, American Samoa), or
after 3 consecutive 404 runs spanning at least 24 h, and that answer is cached for 24 h only (`client.in_us_area`, `PointCache.record_points_404`).

## Coverage

`/points` returns 404 outside the NWS grid (outside the US, some territories): the lake is `BLOCKED` and gets no state. The observation API
keeps about 7 days; there is no archive, so validation data must be captured prospectively (plan §5).
