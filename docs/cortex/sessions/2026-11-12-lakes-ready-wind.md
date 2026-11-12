# Session record: `GET /lakes/ready` lake-wide wind (Sector_Engine #158)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset, no briefing hook); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-12. Branch: `cortex/lakes-ready-wind-2026-11-12` (off main 68e8dd6). Scheduled cloud session (approved-work runner). No open PR for this work existed in the 2 hours before the start.

## Scope
Owner approval on Sector_Ops #51, comment "Owner approval (Michael, 2026-11-11 ~23:40Z …)", section "#158, wind and Intel": the
Engine computes a lake-wide wind (mph + FROM direction) for each ready lake from the forecast, labeled ESTIMATE, behind the
existing flag. Intel waits. No IAM, no deploy, no customer-copy switch; `SECTOR_LAKES_READY_OUTPUT` stays off.

## Done
- `LakeWind.swift`: `ReadyWindLayer {status ESTIMATE, asOf, speedMph, fromDeg, hourly[]}`; `LakeWindPoint` (extent bbox centre,
  else the directory centroid, rounded to 0.01°); one multi-location Open-Meteo request through `WeatherService.fetchForecastData`
  (hourly 10 m speed + direction, mph, UTC, `best_match` = the Wind Brain's tonight model, WS-5); `LakeWindCache` (30 min per
  point, 60 s after a failure, last good served up to 3 h, concurrent requests share a fetch, 100 points per request).
- `LakesReadyAPI.swift`: `layers.wind` added only to lakes already listed (`isEmpty` ignores it); server form waits at most 4 s
  (`withDeadline`) and answers without wind past that. Server builds the cache only inside the flag-on branch.
- Contract `lakes-ready-v1` 1.1.0 → 1.2.0 (additive; response `version` stays 1); golden updated (Berlin with 3 hours, Canyon with
  1, Flathead without wind); Swift tests (`LakesReadyWindTests`: parse, hour window, point, query, never-lists, budget, cache TTLs,
  failure backoff, coalescing, chunking) and Python contract tests (1.2 additive over 1.1, wind shape, validator). Design note §9.

## Decisions (reversible, stated in the PR)
- `asOf` is the forecast hour for "now" (top of the current UTC hour), so `hourly[0]` and the layer agree and the 10-minute
  future bound always holds. Open-Meteo `current` is not used: one hourly series serves both "now" and the play bar.
- `hourly` is always present (≥1 entry), current hour first, up to 12 h later.
- Model `best_match` only: the Wind Brain's outlook decision keeps tonight on `best_match`; the next 12 h are tonight.
- No separate wind switch: the approval puts it behind the existing flag.

## Verification
- No Swift toolchain in this container (download.swift.org refused by the egress proxy): Swift build and tests run in CI
  (`swift-tests.yml`, macOS + Linux) on the PR.
- pytest `verification` + `tools/architecture`: all pass. Engineering status re-recorded (`collect_certification.py`: failing none).

## Independent review (round 1) and fixes
- Blocking: none.
- Should-fix, fixed: the contract's general `layers.*.status` / `layers.*.asOf` meanings described copies only; they now point
  wind to `layers.wind`.
- Nits: test docstring fixed. Not changed (stated): wind is fetched after the snapshot (points need the extents; worst cold
  request ≈ 5 s + 4 s); unbounded-by-design cache maps (bounded by the directory); hh:59 shows the hh:00 value (documented).
- Open (pre-existing, also affects /conditions): the fallback host `historical-forecast-api.open-meteo.com` may serve a
  shorter future series if it wins the race; wind then degrades to absent or a shorter `hourly`, never a wrong hour.
