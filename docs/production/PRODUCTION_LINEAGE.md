# Sector Engine — Production Lineage and Deploy Policy

Last verified: 2026-10-12 (consolidation Phase 1).

## What is live

| Thing | Value |
|---|---|
| Cloud Run service | `sector-engine`, `us-central1`, project `sector-9393c` |
| Serving revision (100%) | `sector-engine-00080-wes` |
| Source commit | **`bc9e09fb`** — tags `deployed/sector-engine-00072-way`, `deployed/sector-engine-00080-wes` |
| `main` | `bc9e09fb` (fast-forwarded 2026-10-12; previous main preserved as tag `archive/main-pre-ff-2026-10-12` → `31d00c8c`) |
| Rollback | `00072-way` (same source, cpu=4/2Gi) or `00044-b6m` (`be1d8932`) |

How "source commit" was established: Cloud Run keeps the uploaded source zip for every
`gcloud run deploy --source` build. The zip for 00072/00080 was compared file-for-file
(git blob hashes) against every commit in the repo; `bc9e09fb` matches exactly. The
revision's image digest carries no commit label, so the zip is the proof.

### Runtime configuration (lives in Cloud Run, not in source)

`00080-wes` vs `00072-way`: same image; cpu 4→2, memory 2Gi→1Gi. Both: minScale 1,
maxScale 30, containerConcurrency 1 (see the outage note in `deploy.sh`), startup CPU boost.

Env on the live revision:

| Var | Value | Status |
|---|---|---|
| `SECTOR_CURRENT_CLARITY_ROUTES` | `1` | **inert** — not referenced by this source. Would activate if a Clarity Stage 3–5 lineage image were ever served. Do not deploy such an image. |
| `SECTOR_CLARITY_CANDIDATE_ROUTES` | `1` | inert, same caveat |
| `SECTOR_CANDIDATE_UIDS` | 3 master UIDs | used only by the inert routes |

Two 0%-traffic tag revisions share the service and are publicly invokable at their tag
URLs: `clarity` → `00078-kuv` (clarity-candidate lineage) and `fusion` → `00079-zab`
(= `00044-b6m`). Whether to keep them is an open decision (audit D6).

### Live jobs (Cloud Run Jobs + Cloud Scheduler)

| Job | Schedule | Source lineage | Customer-visible? |
|---|---|---|---|
| `hydrology-hourly` | `15 * * * *` | 09-27 build; `hourly.py` identical in prod and `03937913` | yes — prod `ClarityStateLoader` reads its output (via `/clarity/state`, which iOS does not call) |
| `clarity-current-hourly` | `40 * * * *` | `03937913` (`feat/clarity-algal-warning`) | no |
| `lake-surface-daily` | `0 3 * * *` | `03937913` era | no |
| `water-temp-tva-archive` | `20 * * * *` | `intelligence/water-temp` lineage | no (Lake Brain reads it) |
| `wind-hourly` | `5 * * * *` | `brain/wind` | no (writes Brain RTDB) |
| `clarity-candidate-shadow` | paused | private shadow branch | no |

Phase 3 of the consolidation brings job source onto `main`.

## How production drifted from main (and the rule that stops it)

From 2026-09-11 to 2026-10-07 every deploy was `gcloud run deploy --source .` from a
feature branch, each cut from the *previously deployed* branch, never merged back.
`main` fell 12 commits behind with zero divergence. One consequence was a real
regression: `fix/forecast-rain-gate` served customers 09-17→09-23 and was dropped by the
next deploy, which was built from a sibling branch (restored in Phase 2).

### Policy (effective 2026-10-12)

1. **Every production deploy of `sector-engine` is built from a commit on `main`.**
   Feature work merges to `main` first; the deploy follows.
2. **Every deploy is tagged** `deployed/sector-engine-<revision>` on the exact commit,
   with the runtime config noted in the tag message when it differs from the previous one.
3. `deploy.sh` must refuse to run from a dirty tree or a HEAD that is not on `main`
   (to be added with the Phase 2 deploy-script reconciliation; until then this is a manual rule).
4. Serving images are **never** built from `brain/*`, `research/*`, `feat/clarity-*`
   or any branch carrying unshipped Clarity Stage 3–5 code.
5. Jobs are deployed from `main` too, and each job image self-labels its commit
   (`SECTOR_ENGINE_COMMIT` / `SECTOR_WIND_BUILD` style env).

### Recommended GitHub branch protection for `main` (not applied by the consolidation run)

- Require a pull request before merging; no direct pushes except by the owner.
- Require status checks: `swift build` + `swift test` (Linux container, matching the Dockerfile).
- Block force pushes and deletions.
- Optionally require linear history (the production stack is already linear).

Applying protection is an administrative change and is left for Michael.
