# Session record: Weather, Moon and Generation on Sector Pulse (prepared, off) (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive` from the local Cortex checkout, whose HEAD `ecaef70` does not match the pin; `CORTEX_HOME` was unset in this cloud session), pack sector/engine

## Request
Decision recorded in chat (Michael, 2026-11-23 01:44 CT), not an Owner approval comment: the new Weather, Moon and Generation Brains run on the Mac mini through Sector Pulse instead of as cloud jobs, so a run costs nothing. Prepare it as PRs only: nothing enabled, deployed or run on the Mini.

Branch `ops/new-brains-on-pulse-2026-11-23` from `origin/main` `f5460aa`, worktree `/home/claude/se_wt_pulse_newbrains`. Companion: Sector-Pulse branch of the same name (catalog entries `weather-central`, `moon-central`, `generation-central`, all disabled).

## Changes
| Area | What |
|---|---|
| Weather `/points` cache | `client.PointCache` v2: durable JSON file `{schema, entries}` keyed by lake id + coordinate (4 decimals); 30-day TTL; a future stamp is not trusted; bad/foreign/v1 file ignored and rewritten; atomic save that creates the folder and never fails the run. Path: `--point-cache` or `$SECTOR_WEATHER_POINT_CACHE`; `run.py` refuses a path inside the checkout (exit 2). `NwsHttp.get(detect_moved=True)` raises `Moved` (subclass of FetchError, carrying the redirected body) for grid and observation reads. `publish.run`: a cached grid URL that answers 404 or a redirect is re-resolved in the same run (other lakes on the same stale URL re-resolve without refetching it); a cached station that answers 404/redirect drops the entry for the next run. A fresh resolution behaves as before (a redirected body is used, a 404 is a grid error). Cache stats in the run JSON |
| Runner entries | `jobs/brain_platform/sector_brain_platform/python_artifact_entry.py` (shared; the Python sibling of `swift_artifact_entry.py`) and `brains/{weather,moon,generation}/runtime/artifact_entry.py`: unchanged publish step into the Brain's DryRunWriter, previous state from the live Brain DB through a GET-only view with this run's writes overlaid, one sealed artifact (each Brain's `publish_artifact.build_artifact` with its release lineage), stored create-only, `--emit` hand-off. Same gates as `run.py --write`: APPROVED release (exit 2) AND `<BRAIN>_WRITE_APPROVED=1` (exit 3); `--emit` needs `--read-rtdb`. Weather also needs `SECTOR_WEATHER_USER_AGENT` (from the Mini's Keychain). Moon reads Weather's last completed states only (≤ 3 h): the `deferIfUpstreamStarted: false` edge semantics are unchanged; no manifest change |
| Docs | WEATHER §6.2, MOON §7.2, GENERATION §6.2: the decision, `deploy/deploy-job.sh` superseded by Pulse pending Michael's enablement (not deleted), the switch-on steps. `NWS_PROVIDER.md`: the Pulse-route cache |
| Tests | `brains/weather/tests/test_point_cache.py` (hit/miss/expiry/bad file/moved coordinate/revalidation/save failure/in-repo refusal), `brains/*/tests/test_artifact_entry.py`, `jobs/brain_platform/tests/test_python_artifact_entry.py` |

Choices (reversible, standing approval 6): one shared entry module instead of three copies; the hand-off is gated exactly like `--write` (a hand-off is the path to a write); exit 0 whenever an artifact is stored, the run's own outcome (PARTIAL/FAILED) travels inside the artifact as the Brain writes it, as `--write` writes on partial errors; `publishMode` says CENTRAL for these artifacts; no hybrid-stage fragments (the three Brains are not in `cutover_order.json`: an order review is the owner's, PL-10).

## Verification
- `brains/weather` 136 passed; `brains/moon` 316 passed; `brains/generation` 134 passed; `jobs/brain_platform` 1020 passed, 2 skipped; `jobs/brain-orchestrator` 339; `jobs/brain-publisher` 35; `tools/runner` 10; `verification` 51 passed, 3 skipped; `tools/brain_certification` 32; `tools/ops/tests` 5; `tools/architecture` 196 passed after the engineering-status digest.
- `data-check`: same output as `origin/main` (790 lines); `ops-check`: 0 findings; `mission-audit`: 4 findings on both (BA-01 mapping of weather/moon/generation, CG-3.1-19/20, unchanged).
- Security: no secret, no contact address, no machine path in the repository; the NWS contact is Keychain configuration on the Mini; the live database is reached only through a view with no write method.

## Decision-required / gated (batched for Michael)
1. Enable the route (each step gated: knowledge release approvals, Cortex registration, order review + hybrid-stage fragments, IAM lease/artifact bindings for Pulse, manifest execution target + Orchestrator/Publisher deploy, Pulse entries enabled, execution control). See the plans.
2. Cortex PROJECT.md §7: these Brains would run only on Pulse (CG-3.1-28).
3. `worktree-check`: `/home/claude/se_wt_wind` is REMOVABLE_MERGED (another session's worktree; not touched).

## Not done
No deploy, no cloud job, nothing enabled or run on the Mini, no manifest/policy/rules/IAM/score change, no merge. `deploy-job.sh` scripts unchanged.

## Review round 1 (independent review NOT CLEAN; fixed on the same branch)
- Gap ID: CG-3.1-25 collided with open PR #245 (and -26 with #246, -27 with #251); scanned `origin/main` and every open PR branch through `gh api`; renumbered to **CG-3.1-28**.
- Merged `origin/main` (not a rebase): #241 had regenerated the engineering-status files; the conflict was resolved by taking main's copy and re-running the digest sequence.
- HIGH: a `/points` 404 is no longer cached as out of coverage. Inside the US NWS area (`client.in_us_area`) it is an outage (`PointsUnavailable`): nothing cached, the last state kept while fresh (not rewritten), retried next run. BLOCKED only outside the US area or after 3 consecutive 404 runs spanning ≥ 24 h (`PointCache.record_points_404`), cached 24 h only. A failed re-resolve keeps the old grid entry; a cached station 404 flags the entry (`revalidate`) instead of deleting it. `test_out_of_coverage_lakes_are_blocked_with_no_state` now uses an out-of-US point (a US lake's 404 is an outage).
- LOW: entries at a lake's old coordinate are pruned; a redirect target replaces the cached grid URL, so a redirect costs at most one extra request per lake per run; plan step 6 states that write approval is the Pulse owner config `publication.<brain>WriteApproved` = "1".
- Tests: weather 143 passed (new: outage not cached and retried, last state kept while fresh, persistent 404 → BLOCKED with a 24 h TTL, real out-of-US point, revalidation during an outage keeps the old entry, coordinate pruning, redirect target stored).
