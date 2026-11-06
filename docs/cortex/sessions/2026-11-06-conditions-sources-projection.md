# Session record: Orchestrator conditions-sources projection (Sector_Ops #53)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine. Date: 2026-11-06. Branch: `feat/conditions-sources-projection-2026-11-06`.

## Scope
The Orchestrator projection that feeds the Sector Ops "Conditions sources" panel: `CONDITIONS_CONSOLIDATION_SPEC_V1` §4 (`tileSources`) and §7 (projection). Code only; nothing deployed or switched on.

## Done
- `jobs/brain-orchestrator/conditions_sources.py`: behind env `CONDITIONS_SOURCES_PROJECTION=1` (default off), at most every 15 min (the throttle reads the written document's own `generatedAt`), it probes `GET /conditions` at the 17 points in `verification/fixtures/phone-contract/points-v1.json`. Requests are sequential, share a 120 s budget, time out after 30 s each, and send `User-Agent: Sector-Orchestrator/<commit>`. The base URL is `SECTOR_ENGINE_URL`, else `ENGINE_URL` (already set on the deployed job). It reads `tileSources`; without them (today's Engine) it derives class and source from today's paths and sets `flag: "unknown"`. It merges `brains/{id}/lastSuccessfulRun` and the runner (a fresh runner-lease holder, else the runner-policy primary), computes green/amber/red freshness, coverage, breaker (`unknown` unless `tileSources` carries one) and `contractOk` (phone-contract validator), then writes `control/conditionsSourcesV1` (`sector-conditions-sources-v1`). A failed probe is listed under `errors` and never fails the cycle.
- **§7 Amendment 1** (coordinator, same day, Ops panel Sector_Ops #54): each tile and each `lakes[id]` carries `lastUpdate` (the source's own observation time; never a run time, and a future-dated stamp never becomes a tile's `lastUpdate`) and `fetchedAt` (the Engine's `generatedAt`, a `tileSources` `fetchedAt`, or a Brain copy's `publishedAt`). `lakes[id].eligible` comes from an explicit `eligible`, else the flag's `lakes` list (an `off` flag never limits). `coverage = {ok, fallback, unknown, total}` counts eligible points only; a failed probe counts as eligible and unknown. Today's Engine gives an observation time only for `generation`, so most tiles have `fetchedAt` but no `lastUpdate`, and their freshness is aged from `fetchedAt`.
- `orchestrate.py` step 5e calls it only when the switch is on, and never with `--health-only` or `--control-only`. With the switch off nothing is probed, read or written.
- `deploy-job.sh`: stages the points file, the phone contract and its validator into the image, and passes `CONDITIONS_SOURCES_PROJECTION` (default `0`, only `0` or `1` accepted).
- `RTDB_PATH_OWNERSHIP_MATRIX.json`/`.md`: `/control/conditionsSourcesV1` registered as Orchestrator-owned, `NOT_VERIFIED` (not yet live).
- Tests: `jobs/brain-orchestrator/tests/test_conditions_sources.py` (34 tests, no network) on the redacted 2026-11-06 goldens and a synthetic `tileSources` overlay.

## Database rules
None needed. Ops already reads `/control` as a whole (`platform/security/rtdb.rules.target.json`: `control/.read` for `sectorOpsReader`), the same grant that serves `control/healthV1` and `control/engineeringStatusV1`. The platform writer guard (`ownership.py`) already allows `control/*`.

## Findings
- On 2026-11-06 an uncached `/conditions` call took about 9.4 s (Step 0 record). With a cold cache, 17 sequential calls do not fit in 120 s; the points not reached are listed as `not attempted: probe budget exhausted` and count against coverage. The spec expects the 5-minute cache to absorb this; that is not verified.
- The Cortex registry has no family for `/control/conditionsSourcesV1` (CG-3.1-16). The code names the path without a leading slash, like `control/shadowLaneV1`, so `data-check` reports no new finding; the gap is real and recorded.

## Verification
- `brain_platform` 891, `brain-orchestrator` 202, `brain-scores` 37, `brain-publisher` 19, `tools/runner` 7, `tools/cutover` 10: all passed.
- pytest `verification tools/architecture tools/research`: passes after the digests are re-recorded (the 6 pre-record failures were the stale certification digests).
- Cortex `data-check`: 125 findings before and after; none new.

## Not done / gated
- Not deployed and not switched on. Turning on `CONDITIONS_SOURCES_PROJECTION` is the owner's decision.
- Not run against production; no production read or write.
