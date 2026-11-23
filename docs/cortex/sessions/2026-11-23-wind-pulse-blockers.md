# Wind onto Pulse: clearing the code and research blockers — Session Record

```text
Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with git archive; the loader reports "uncommitted" because the extract has no .git), pack sector/engine
Repository: Sector-Bowfishing/sector_engine · Branch: fix/wind-pulse-blockers-2026-11-23 (new worktree off origin/main) · Start commit: 8d421fe · Date: 2026-11-23
```

## 1. Scope
- **Request and mode:** guided implementation. Clear the Wind-to-Pulse blockers in `tools/ops/hybrid-stage/wind.json` that are code or research: W-H2, W-H3, the redesigned 7-day shadow (Sector_Ops #49), archive continuity; record the Wind knowledge release approval (M3) in a separate commit. Owner steps are left untouched. Draft flip PR #177 not touched.
- **Owner decisions applied (Sector_Ops #51):** D2 W-H2 = previous state read from the live database (comment 6889677881); D3 W-H3 lake list = live + national lakes; D4 shadow on Pulse with the #176 criteria; D5 archive seeded once from the candidate archive; M3 release approval (owner chat 2026-11-23 06:21Z, comment 7093271287).
- **Inspected:** `brains/wind/runtime/artifact_entry.py`, `sector_wind/brain/{publish,live_previous,state,profile,lakes}.py`, `sector_wind/{store,validate,retention}.py`, `tools/ops/{hybrid_stage,wind_watchdog_lakes,brain_watchdog_lakes,si_watchdog_lakes}.py`, `cycle_watchdog.py` (LAKE_PATH), `ownership.py`, the release resolver, `WIND_CUTOVER_PULSE_V1.md`, Engine PRs #176, #177, #180, #181, #182, the Water Clarity/Lake approval records, Pulse `catalog.json` (`wind-central`, `water-clarity-central`, read only).
- **Scope expansion:** the Pulse catalog was read (not changed) to see whether `wind-central` uses D2's `--read-rtdb`: it does not.
- **Not inspected / not accessible:** the Mac mini archive and `gs://sector-wind-candidate/wind/v1` (no credentials here; the continuity check is drafted for the Mac mini). Production RTDB was not read.

## 2. Findings
| ID | Status | Finding | Evidence |
|---|---|---|---|
| F1 | FAIL → fixed | The merged W-H2 (#180) read readiness from `lakes/{k}/states/wind/readiness`, a field Wind never writes (it is `lakeFleet/{k}/readiness/wind`), so read-live runs never emitted readiness events | `state.py` state dict has no top-level `readiness`; sealed artifact mutations; 3 new tests fail on the old path |
| F2 | FAIL → fixed | A hand-off without `--read-rtdb` still took its previous state from the local file a refused hand-off advances | `artifact_entry.py` before this branch |
| F3 | OPEN (other repo) | Pulse `wind-central` passes no `--read-rtdb` and declares no read credential | Sector-Pulse `service/sector_pulse/jobs/catalog.json`, `wind-central` argv |
| F4 | FAIL → fixed | D3's list (live + national) does not cover Wind's write set: `publish()` writes `lakeFleet/{k}/readiness/wind` for every directory lake and LAKE_PATH matches `lakeFleet/`, so the first publish would still halt | `publish.py` §2; `test_watchdog_scope.py::test_d3_alone_would_trip_publish_outside_lakes` |
| F5 | FINDING | A seal that takes its previous state from the local bookkeeping is not reproducible (it advances its own previous), so the shadow must run with `--read-rtdb` | `test_pulse_shadow.py` (first draft failed on the activity event) |
| F6 | NOT_VERIFIED | Whether each national table's own `tableSha256` equals the manifest's (D2 profile change detection depends on it) | needs the real archive; the continuity check tests it |

## 3. Plan and changes made
| Correction | Class | Finding | Files | Commit |
|---|---|---|---|---|
| W-H2: hand-off needs `--read-rtdb`; read-live seal never advances local bookkeeping; readiness path fixed; end-to-end tests | Safe (requested, D2) | F1, F2 | `artifact_entry.py`, `live_previous.py`, `test_live_previous.py`, `test_artifact_entry.py` | b3b4c4b |
| W-H3: list = whole directory (contains D3), pinned 621 lakes in the staged fragment; dated correction in the plan | Safe (requested; staged only) | F4 | `wind_watchdog_lakes.py`, `wind.json`, tests, `WIND_CUTOVER_PULSE_V1.md` | 80a0761 |
| Shadow protocol `wind-pulse-shadow-v1` + read-only runner | Safe (requested, D4) | F5 | `WIND_PULSE_SHADOW_PROTOCOL_V1.md`, `wind_pulse_shadow.py`, `test_pulse_shadow.py` | 78f0e37 |
| Archive continuity check | Safe (requested, D5) | F6 | `wind_archive_continuity.py`, `test_archive_continuity.py` | c94d394 |
| Repo-tool tests skip in the package gate's clean copy | Safe | — | 3 test files | 74a748a |
| Release approval record (separate commit) | Record of an owner approval | — | `knowledge-release.json`, `brain.json`, approval doc, `wind.json` | 28d93ad |

**W-H3 choice, stated:** the coordinator asked to implement D3 as decided. D3's list is contained in the pinned list; the whole directory is the smallest list that does not halt the first publish (F4), and it is how Water Clarity, Water Temp, Lake (owner direction 2026-11-20) and Sector Intelligence (SI-WD (a)) are handled. The fragment is staged only; the alternative (Wind stops writing fleet readiness for non-profiled lakes) changes Wind's outputs and is decision-required.

## 3a. Standing checks
| Check | Component | Result | Evidence | IDs |
|---|---|---|---|---|
| Memory 1 ownership/storage | wind | PASS | `brain.json` `knowledge.stores` | BR-11 b, c |
| Memory 2 dev-machine scan | wind + new tools | PASS | grep over runtime, deploy and the three tools: no hits | BR-10 |
| Memory 3 release loading/lineage | wind | PASS | digest unchanged `sha256:690adf50…`; lineage triple in artifacts | BR-11 a, e |
| Memory 4 memory unavailable | wind | PASS | exit 2 on release failure; read error seals nothing | BR-11 f, BR-16 |
| Memory 5 separation + approval | wind | PASS | approval record now exists | BR-11 d, g, PL-06 |
| Memory 6 Pulse independence | wind | PARTIAL | bounded staleness documented, failover off, not customer-eligible; offline behaviour not exercised | PL-13 |
| data-check | repo | 2 new heuristic false positives (CG-3.1-22) | 543 vs 541 on main | FD-01 |
| mission-audit | repo | no Wind finding (4 pre-existing) | `mission-audit --repo .` | BA-07 |
| ops-check `--repo` | repo | 0 findings | | IO |
| Security triggers | Wind producer / reader | SEC-06: no rules or grants changed; the live read is GET-only through the existing read token. rules-check and bundle-scan not applicable (no rules, no public build) | | SEC-01…13 |

## 4. Verification
| Check | Command | Result |
|---|---|---|
| Wind suite before | `cd brains/wind && pytest -q` | 284 passed, 6 skipped |
| Wind suite after | same | 313 passed, 6 skipped |
| Platform suites (CI list) | `pytest -q` in brain_platform, brain-orchestrator, brain-scores, brain-publisher, tools/runner, tools/cutover, tools/deploy | 1011, 339, 37, 35, 10, 35, 99 passed |
| Certification kit, ops tests | `pytest -q tools/brain_certification tools/ops/tests` | 32, 5 passed |
| Wind package gate | `SECTOR_REQUIRE_WIND_DEPS=1 pytest -q verification/integration/test_wind_package.py` | 7 passed |
| Hybrid stage | `python3 tools/ops/hybrid_stage.py check` | `wind: OK` before and after; blockers 9 → 7 |
| W-H3 list | `python3 tools/ops/wind_watchdog_lakes.py --check` | OK: 621 lakes pinned |
| Release | `verified_release()`; `PackagedReleaseResolver` | APPROVED, digest unchanged, resolver accepts |
| Engineering status | `collect_certification.py`; `build_engineering_status.py --write`; `--check` | see the PR (run after the last code commit) |

## 5. Open items
### Production integration blockers (Wind onto Pulse; remaining `wind.json` blockers, 7)
1. Sector-Pulse: `wind-central` must pass `--read-rtdb` and the `brain-rtdb-read-token` credential (F3). Code, not done here (other repository).
2. 7-day shadow: owner steps (schedule a Pulse shadow job, name the window, schedule retention; decide whether the flip waits for PASS).
3. Archive continuity: the Mac mini run (request drafted below), then the D5 seed if needed.
4. App wind source decisions WS-1..WS-4 (customer-visible).
5. IAM W-H1: Sector_Ops #51 comment 7093316526 reports it applied by Michael 2026-11-23 ~06:25Z. Left untouched here.
6. Mac mini power: the same comment reports the Mini set to never sleep. Left untouched here.
7. Owner approvals for the flip PR, the Orchestrator + Publisher deploys and the execution control.

## 6. Decisions required and approvals
| # | Item | Options | Recommendation |
|---|---|---|---|
| 1 | W-H3 list | (a) whole directory, pinned (done); (b) D3 list + Wind stops writing fleet readiness for non-profiled lakes in artifact mode | (a): no output change, same as every other Pulse Brain |
| 2 | Flip vs shadow order | (a) flip waits for a shadow PASS; (b) flip merges once code blockers clear, first publish held until PASS | Michael's call (protocol §"What remains") |

Approvals used: the standing owner approvals in `CLAUDE.md` (branch, push, PR). The release approval is the owner's (comment 7093271287); this session only recorded it.

## 6a. Cleanup
`worktree-check` (main checkout): 6 worktrees, all KEEP (this branch's worktree `KEEP_UNIQUE` until pushed). No research data downloaded or created; the Cortex extract and probe scripts are in the session scratchpad (DISPOSABLE). The worktree `/home/claude/se_wt_wind` stays until the PR merges.

## 7. Tested vs. intended
Tested: every code path above with local fixtures (no network, no database). Not run: the Mac mini check, any shadow window, any Pulse job, any live read. The shadow and continuity tools have never run on real archives.

## 8. Cortex gaps
CG-3.1-22 (data-check false positives on HTTP endpoint names and prefix filters; `ops-check --status` crashes on a non-JSON document).

## 9. Next step
The Sector-Pulse change for `wind-central` (`--read-rtdb` + the read credential), then the Mac mini continuity run.

## Appendix: drafted Mac mini request (NOT posted)

> **Claude request (under Owner approval 2026-11-22): Wind archive continuity check, read-only**
>
> Read-only: lists and reads the Wind candidate archive and the Mac mini's local Wind archives. Nothing is written to any database, bucket, binding, schedule or execution control, and no local archive file is changed, copied or seeded. Use Sector_Engine main at or after the merge of Engine #PR (it adds `tools/ops/wind_archive_continuity.py`). Write results to the research folder and post a summary here. No machine paths, account names or secrets in the comment.
>
> 1. Save the bucket listing and the bookkeeping file with the Mini's existing gcloud read access: `gcloud storage objects list "gs://sector-wind-candidate/wind/v1/**" --format=json > remote.json` and `gcloud storage cat gs://sector-wind-candidate/wind/v1/brain/wind/last_publish.json > remote_last.json`. If gcloud cannot read the bucket, stop and report; don't sign in, change an account or mint a token.
> 2. Run the check once for each local Wind archive Pulse holds: wind-central's job-data `archive` folder (it may not exist yet; report "absent"), and the older Wind history in Pulse's job data (about 100 MB, collected 2026-10-19..11-06): `python3 tools/ops/wind_archive_continuity.py --local <archive> --remote-listing remote.json --remote-last-publish remote_last.json`. Keep each JSON output in the research folder.
> 3. Post per archive: the verdict (CONTINUOUS / SEED_NEEDED / DIVERGED); required objects (in the bucket, missing locally, different, local-only); profile digests (checked, mismatched, missing; name any mismatched lake); watchdog scope (D3 lake count, any not on the pinned list); bookkeeping (local and bucket `at`, same bytes); and each series' oldest and newest in the bucket and locally (nbm, rtma, nbm-points, metar, runs).
> 4. Don't seed or copy anything. If a verdict is SEED_NEEDED or DIVERGED, say which archive wind-central should use and stop; the one-time seed (D5) is a separate step.
