# Research Closeout — wind-brain — wind-strong-wind-method

```text
Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine
Task: WIND-CNF-001 strong-wind methods (pre-registration WSW-2026-11-23-R3, superseding R2 and WSW-2026-11-23, + read-only runner) · Folder: wind-brain (research home absent in this cloud session; CG-3.1-22) · Date: 2026-11-23 · Manifest task status: OPEN (blocked: the past-window run is on the Mac mini; H2 opens 2027-01-01)
```

## Preserved results
No local data was created or fetched. Committed on branch `research/wind-strong-wind-method-2026-11-23`: protocol WSW-2026-11-23-R3 (sha256 82f96596197d6af32e43b9e01ce152e922f3a0c0a42993641993a2da0fda68a2), the superseded never-run R2 (ba05492b…) and WSW-2026-11-23 (b9a55721…), both kept byte-identical with SUPERSEDED.md, MINI_REQUEST_DRAFT.md, the runner and its tests. These are rules and code, not research data.

## Manifests updated
none (the wind-brain manifest is on the Mac; the Mini registers the fit, rows and result there)

## Candidate knowledge
none (no method has been scored)

## Backups verified
none required (nothing retained locally)

## Deleted
none. The Cortex tree extracted read-only into the session scratchpad and a scratch check log are DISPOSABLE and go with the session.

## Worktrees
`/home/claude/se_wt_wind_strong` (this task): kept until the PR is reviewed; KEEP_DIRTY before the final commit, KEEP_ACTIVE after push (unmerged branch). Other worktrees listed by worktree-check belong to other sessions and were not touched; two are REMOVABLE_MERGED but unregistered, so their removal is the owner's call (DEV-04).

## Blockers
The past-window fetch and scoring need the Mac mini (this session's proxy refuses the NOAA bucket). Where the CAL+H1 corpus lives is not recorded in Git (research tools default to a per-user macOS cache, possibly on the MacBook Pro); if it is not on the Mac mini, the Mini re-fetches CAL+H1 for the fit. H2 scoring waits for 2027-01-01. Whether the bucket still serves the past window's NBM pre-v4.3 (v4.2) cycles with qmd percentiles is not verified.
