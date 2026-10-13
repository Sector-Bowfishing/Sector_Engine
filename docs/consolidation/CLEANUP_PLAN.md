# Worktree and branch cleanup plan (proposal — nothing deleted)

Prepared 2026-10-12 after consolidation Phases 0–12. Containment was re-checked against `main` with
`git merge-base --is-ancestor` (ancestry) and `git cherry` (patch equivalence). **No worktree, branch,
tag or research artifact was removed; this is the plan for Michael to approve.**

Legend: **KEEP** (still the working home of something) · **ARCHIVE** (preserve the ref; the worktree can
go) · **REMOVE-CANDIDATE** (fully contained in `main` or superseded; branch + worktree can go after a
final check) · **BLOCKED** (a decision or a private-boundary rule prevents removal).

## Worktrees

| Worktree | Branch | Containment vs `main` | Class | Precondition / note |
|---|---|---|---|---|
| `Sector_Engine` | `main` | — | **KEEP** | the canonical checkout |
| `Sector_Engine-wt-release` | `fix/water-temp-shown-scored` @ bc9e09fb | CONTAINED (= production source) | REMOVE-CANDIDATE | tags `deployed/sector-engine-00072-way`, `00080-wes` preserve it |
| `Sector_Engine-lakes` | `fix/water-temp-lake-gauges` | CONTAINED | REMOVE-CANDIDATE | — |
| `Sector_Engine-surface` | `feat/lake-surface-job` | CONTAINED | REMOVE-CANDIDATE | — |
| `Sector_Engine-biological` | `brain/biological` | CONTAINED (merged Phase 7) | REMOVE-CANDIDATE | keep the branch ref until Ops reconciliation references it |
| `Sector_Engine-intelligence` | `brain/sector-intelligence` | CONTAINED (merged) | REMOVE-CANDIDATE | same |
| `Sector_Engine-clarity-brain` | `brain/water-clarity-public` | CONTAINED (merged) | REMOVE-CANDIDATE | its ignored `catalog.private.json` is backed up in GCS (sha verified) |
| `Sector_Engine-lake-brain` | `sector/lake-brain` | CONTAINED (merged) | REMOVE-CANDIDATE | — |
| `Sector_Engine-brain-wt` | `brain/water-temp` @ ec0ae0fa | **not contained** (replayed by file; its base is the unshipped Clarity Stage 5 line) | **ARCHIVE** | keep the branch (pushed) as the record of the Brain's development on that base; the worktree (1.6 GB) can go |
| `Sector_Engine-water-temp` | `intelligence/water-temp` | not contained (⊂ brain/water-temp); its `jobs/water-temp-tva-archive` is on main | ARCHIVE | source of the live TVA archiver (now on main) |
| `Sector_Engine-wind` | `brain/wind` | not contained (based on old main); its `jobs/wind-hourly` is on main and migrated | ARCHIVE | **the live `wind-hourly` job still runs this tree** until redeployed from main — keep until then |
| `Sector_Engine-fusion` | `feat/clarity-algal-warning` @ 03937913 | not contained | **BLOCKED (D4)** | source of the live `lake-surface-daily` and `clarity-current-hourly` jobs; `jobs/lake-surface/LINEAGE.md` |
| `Sector_Engine-candidate` | `feat/clarity-candidate-shadow` (PRIVATE, never pushed) | not contained; in the GCS bundle | **BLOCKED (private)** | verified bundle `sector-clarity-private-branches-2026-10-12.bundle`; remove only after a restore test from the bundle |
| `Sector_Engine-research` | `research/clarity-candidate` (PRIVATE) | not contained; in the GCS bundle; 52 GB of artifacts in Tier A/B archives | **BLOCKED (private)** | same; largest disk win when approved |
| `Sector_Engine-5a-deploy` | `deploy/intel-guardrails-5a` | not contained | **BLOCKED (D5)** | customer/policy behavior |
| `Sector_Engine-guardrails` | `feat/intel-guardrails-5a` | superseded by `deploy/…-5a` | REMOVE-CANDIDATE | after D5 is decided |
| `Sector_Engine-hardening` | `wip/gauge-context-2026-09-14` (pushed, Phase 0) | not contained | ARCHIVE | 8.5 GB (7.2 GB build caches); the work is preserved on origin; belongs to Lake Brain bindings |
| `Sector_Engine-pressure` | `fix/pressure-consistency` | not contained (13 never-shipped commits) | **BLOCKED (D3)** | preserved pending the hardening decision |
| `Sector_Engine-levelcopy` | `feat/lake-environment-snapshot` (pushed, Phase 0) | not contained; its USGS migration superseded by the OGC one | ARCHIVE | per-value provenance + environment snapshot remain unreviewed features |
| `Sector_Engine-severe` | `fix/forecast-severe-warning-parity` | integrated by cherry-pick (conflict-resolved) | REMOVE-CANDIDATE | `git cherry` shows 1 "unmerged" because the resolved patch differs; content is on main (test20b passes) |
| `Sector_Engine-usgs` | `fix/usgs-ogc-migration` | integrated by cherry-pick (resolved) | REMOVE-CANDIDATE | same |

## Branches without a worktree

| Branch | Containment | Class |
|---|---|---|
| `feat/async-http-client`, `fix/conditions-response-cache`, `feat/lake-directory-endpoint`, `fix/water-temp-calibration`, `fix/level-play-copy` | CONTAINED | REMOVE-CANDIDATE |
| `fix/forecast-rain-gate` | 2 code commits on main; `deploy.sh` reconciled by hand | REMOVE-CANDIDATE |
| `feat/clarity-fusion-stage1`, `feat/clarity-current-estimate`, `feat/clarity-production` | stages of `feat/clarity-algal-warning` | BLOCKED (D4) |
| `intelligence/wind` | ⊂ `brain/wind` | REMOVE-CANDIDATE |
| `feat/engine-hardening` | ⊂ `fix/pressure-consistency` | BLOCKED (D3) |
| `brain/water-clarity` (PRIVATE local, 2 commits over public) | in the GCS bundle | BLOCKED (private) |
| 6 August remote-only branches (`night-*`, `ribbon-*`, `band-thresholds`, `decodable`) | fully in main | REMOVE-CANDIDATE (remote) |
| `consolidation/phase*` | all fast-forwarded into main | REMOVE-CANDIDATE |

## Order of execution (when approved)
1. Remove worktrees of REMOVE-CANDIDATE branches (`git worktree remove`), keep the branches one more cycle.
2. Delete REMOVE-CANDIDATE branches locally and on origin after `git branch --merged main` re-confirms each.
3. ARCHIVE: remove worktrees only (free ~12 GB); keep branches on origin.
4. BLOCKED items wait for D3, D4, D5 and a bundle restore test for the private Clarity set.
5. Never: force-push, history rewrite, deleting the `deployed/*` or `archive/*` tags.
