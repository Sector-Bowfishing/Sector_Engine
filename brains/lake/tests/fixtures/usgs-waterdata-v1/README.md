# USGS Water Data API (v1) fixtures — NOT recordings

Every file in this folder was **hand-built on 2026-11-22** from the published OGC API v1 documentation
(https://api.waterdata.usgs.gov/docs/ogcapi/, the migration guide and the collection queryables). The session that wrote
them could not reach `api.waterdata.usgs.gov` (egress proxy refusal; `robots.txt` also disallows crawlers on
`/ogcapi/*/collections/*/items*`). Each JSON file carries a `_fixture_note` saying so. Values are illustrative.

The multi-sensor tests also use the **real** 2026-10-07 recordings in `Tests/SectorEngineTests/Fixtures/USGS/fortworth-level-*.json`
(two series at USGS-08062095, one Primary; two Primary series at USGS-08048890).

| File | Pins |
|---|---|
| `stage_04082500_continuous_00065.json` | D2 (UTC, no fraction), D4 (`null` value); the same readings as `../usgs-stage/04082500_iv_00065.json` |
| `location_04082500.json` | `monitoring-locations` `altitude` / `vertical_datum` (D5). Unverified: that the datum code is the string `NAVD88` |
| `daily_01314500_62614.json` | D3 statistic precedence (00003 over 30800, a null 00003 filled by 30800) |
| `tsmeta_01314500_30800.json` | a daily 30800 series exists (`computation_period_identifier` `Daily`; property name unverified) |
| `empty.json` | D4: "no data" is a 200 with zero features |
| `continuous_395540082291600_page{1,2}.json` | paging via `rel=next`, 15-digit site id, `qualifier: ["ICE"]` |
| `blackout.html` | D10: a non-JSON 200 body |

## Replacing them with recordings

Record from an allowed runner (the Pulse Mac mini or Cloud Run), never from the MacBook, with `USGS_API_KEY` set. The PR that
added this folder lists the exact requests.
