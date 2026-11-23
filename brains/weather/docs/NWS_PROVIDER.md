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
and their cost against the 2 USD/month cap. Nothing persists the cache today.

## Coverage

`/points` returns 404 outside the NWS grid (outside the US, some territories): the lake is `BLOCKED` and gets no state. The observation API
keeps about 7 days; there is no archive, so validation data must be captured prospectively (plan §5).
