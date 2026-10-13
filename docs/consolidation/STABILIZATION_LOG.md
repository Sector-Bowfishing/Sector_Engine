# Sector Engine — Stabilization / Brain Platform Execution Log

Started 2026-10-12 from the read-only audit (`2026-10-12 Sector Engine Audit Handoff.md`,
kept outside the repo). One entry per phase. Nothing here was deployed; no customer
behavior changed unless a phase says so explicitly.

Conventions: every phase ends with a checkpoint commit on `main` and a rollback point.
Stop conditions (deploys, traffic, model promotion, policy gates, private research,
destructive git, deletions, credentials, IAM, ambiguous science) are never crossed
autonomously; they are recorded under "Stopped" and left for Michael.

---

## Phase 0 — Preservation / Security — PASS (one subtask stopped)

**Goal:** no valuable Engine work left uncommitted or unbacked-up; private boundary intact.

### A. Hardening worktree (`Sector_Engine-hardening`)
- Found: 9 modified + 13 new files, uncommitted since 2026-09-14, in no commit anywhere
  (~5,100 lines incl. a 1,359-line generator and 7 test files).
- Intent: gauge role classification (`GaugeClassifier`), gauge selection by role × water
  context × freshness (`GaugeSelector`), NHDPlus-reach water context (`WaterContext`),
  generated dam roster (`DamRoster` + `scripts/generate-dam-roster.py`), CWMS pool-history
  merge, thermal-lag/provenance touches. Stops `/conditions` borrowing the wrong water
  (Lanier taking Buford Dam release temps, etc.).
- Sensitivity: public-safe (USGS/NLDI/NHDPlus public data; secret scan clean).
- Ownership: gauge bindings / water context → **Lake Brain / Lake Registry**, not Conditions.
- Preserved as branch **`wip/gauge-context-2026-09-14` @ `76176a76`** (base
  `feat/engine-hardening` @ `a396a6cb`), pushed to origin. Not built, not reviewed, not merged.
- The worktree now has this branch checked out; `feat/engine-hardening` is untouched.
  `.build-*` caches (7.2 GB) and `scripts/__pycache__` were not committed and not deleted.

### B. `feat/lake-environment-snapshot` (`Sector_Engine-levelcopy`)
- 4 unpushed commits (`ac267e57`, `b9237aea`, `32f21c4c`, `e866d03b`): per-value
  provenance + parameterized thermal lag, lake-scoped environment snapshot + Guntersville
  pool gauge, USGS A7.2 migration, discharge-gage check. Public-safe (scan clean).
- Pushed; `origin/feat/lake-environment-snapshot` = local = `e866d03b`.

### C. Android Discord webhook credentials — **STOPPED (documented, no change made)**
- Confirmed: two Discord webhook URLs with embedded tokens in
  `app/src/main/java/io/sector/co/settings/feedbackSupport/{ContactUs,SuggestFeature}.kt`
  on the Android default branch `Michael-Master`, present since 2024-06-06. Values not
  reproduced anywhere in this log.
- Exposure: the Android repo is **private**, so the exposure is the shipped APK (the
  token is extractable from any client build), not GitHub.
- Why stopped: the project has no `BuildConfig`/`local.properties` secrets mechanism, so
  removing the literals either breaks the Contact Us / Suggest Feature forms or needs a
  new server-side relay (a deployment) plus token rotation — both stop conditions, and
  both alter customer app behavior.
- **What Michael must do:** (1) rotate both webhooks in Discord; (2) decide the mechanism —
  recommended: a tiny Cloud Function/Run relay that holds the webhook and accepts the app's
  Firebase ID token, with the app calling the relay; (3) ship an Android release.
  Until rotation, treat both webhooks as compromised.

### D. Brain preservation re-verification (2026-10-12, after A/B)
All expected heads present on their remotes: Engine `brain/wind` 948fd5e2,
`brain/sector-intelligence` df138c49, `sector/lake-brain` eda56c90, `brain/biological`
99c18f78, `brain/water-temp` e5faf091, `brain/water-clarity` 6220491b,
`intelligence/water-temp` 79b966cc, `intelligence/wind` c12867dd,
`fix/water-temp-shown-scored` bc9e09fb; iOS `intelligence/wind` cf6c629e,
`fix/wind-production-defects` ee1ffc55, `sector/lake-brain` 0713e22e,
`research/sector-intelligence-phase5b-evidence` 8826e80c (contains 1826b795),
`intelligence/water-temp` 1ce61102; Ops `feat/sector-intelligence-brain` 80a01a6,
`sector/lake-brain` 9132736, `feat/biological-brain-species-first` 18b7c89.
GCS: clarity closeout archive (8 objects, bundle sha256 verified in the audit),
`gs://sector-biology-private/biology/v1/latest.json`, `gs://sector-lake-brain/*` present.

**Private boundary:** the Engine repo is **public**. Private-only commit count
(`research/clarity-candidate`, `feat/clarity-candidate-shadow`, private `brain/water-clarity`
minus every origin ref) is still **132**, unchanged. Their `pushRemote = PRIVATE-DO-NOT-PUSH`
guards are intact.

### Acceptance
- No valuable Engine work uncommitted/unbacked-up: **pass** (A, B).
- No private Clarity research public: **pass** (132 private-only, unchanged).
- Preservation verification documented: **pass** (D).
- No branches/worktrees deleted: **pass**.
- Tests: not required (preservation only; no source on `main` changed).

**Commits:** `76176a76` (wip branch). **Rollback:** nothing to roll back — only new refs
were created. **Unresolved:** 0C (needs Michael).

---

## Phase 1 — Canonical production baseline — PASS

**Goal:** Git represents what production runs.

**Re-verified before acting (2026-10-12):** `sector-engine` 100% → `00080-wes`; image
`sha256:8fa35300…`; build-source zip `1791401447.590121-d320098e…` (the zip that matches
`bc9e09fb` file-for-file); `origin/main` `31d00c8c` is an ancestor of `bc9e09fb` with 0
commits of its own; `main` was checked out in no worktree.

**Actions**
1. Safety tag `archive/main-pre-ff-2026-10-12` → `31d00c8c` (pushed).
2. Canonical checkout switched from `fix/water-temp-calibration` to `main`;
   `git merge --ff-only bc9e09fb`; pushed `31d00c8c..bc9e09fb main -> main`.
3. No deploy. No traffic change. No Cloud Run change of any kind.
4. Tag `deployed/sector-engine-00080-wes` → `bc9e09fb`, annotated with the runtime config
   (cpu 2 / 1Gi, minScale 1, maxScale 30, concurrency 1, inert env flags) — pushed.
5. Policy written: `docs/production/PRODUCTION_LINEAGE.md` (deploy only from `main`, tag every
   deploy, never serve Brain/research/Clarity-stage lineages, jobs self-label commits).
6. Branch protection: **recommended only** (`main` currently unprotected; admin change left
   for Michael).

**Tests:** `swift test` on `main` @ `bc9e09fb`: **154 executed, 0 failures** (macOS host).

**Acceptance:** main = production ✓ · no traffic change ✓ · no feature branch lost ✓
(all 33 local branches + new `wip/` branch intact; `fix/water-temp-calibration` still exists,
just no longer checked out) · lineage documented ✓ · full suite passes ✓.

**Files changed (this checkpoint):** `docs/production/PRODUCTION_LINEAGE.md`,
`docs/consolidation/STABILIZATION_LOG.md`. **Rollback:** `git reset --hard
archive/main-pre-ff-2026-10-12` would un-fast-forward main (not needed; FF is additive).

---

## Phase 2 — Production fix reconciliation — PASS (customer-semantics items preserved for Michael)

**Goal:** known lost/never-shipped fixes represented correctly on canonical `main`.
Detail: `docs/consolidation/PHASE2_FIX_RECONCILIATION.md`.

**Integrated (cherry-picks onto main, conflicts resolved against production):**
- Regression restore: `e88f7002` falling-water copy, `23232a49` rain gate (+test) — the
  fix that served customers 09-17→09-23 and was dropped on 09-23.
- `d4b67085` severe-warning parity (tonight capped like the gauge) — resolved against Stage 2E
  via `ConditionsSnapshot.engineInput(...)` carrying production's full builder list.
- `42032991` USGS OGC migration (legacy fallback) — resolved: `HTTP.get` transport, OGC only
  for bbox queries, surface-sensor filter kept on both paths. **Deploy prerequisite:**
  `USGS_API_KEY` on Cloud Run (Michael); without it behavior = today's legacy path.
- One canonical `deploy.sh` (rain-gate + hardening lineages + on-main policy gate; live sizing).
- `ops/setup_alerting.py` checked in, not run.

**Superseded with evidence:** `32f21c4c` (older USGS migration), `0f13f0bc` (lake-zone
times; production handles TZ), `a021de86`/`77fa75ab` (USGS fetch internals rewritten).

**Preserved, not merged (customer semantics / build-system — need approval):** `0e865d2e`,
`abc793f2`, `b57cfe7d`, `f04ae4e3`, `198d5dce`, `f67e42e9`, `4dd43e7d` on
`fix/pressure-consistency`; `wip/gauge-context-2026-09-14`. `deploy/intel-guardrails-5a`
untouched (policy).

**Tests:** `swift test` **169 executed, 0 failures** (154 baseline + 15 new: rain gate,
severe-warning parity test20b, USGS fixture tests). **No deploy. No customer behavior
changed in production** (nothing deployed); the next deploy from main restores the rain gate.

**Checkpoint commits:** `c153ea01`, `e1a4e6ac`, `fbd6f4cf`, USGS pick, deploy/ops commit,
this log. **Rollback:** `git reset --hard 08f453ed` (Phase 1 checkpoint) on main.

---

## Phase 3 — Live job lineage normalization — PASS (two explicit exceptions)

**Goal:** every active job reproducible from canonical source or an explicit exception.
Registry: `jobs/README.md`.

| Job | Result |
|---|---|
| `hydrology-hourly` | already canonical on main (`hourly.py` identical in both lineages; deploy-copied inputs present on main) |
| `water-temp-tva-archive` | **landed** `jobs/water-temp-tva-archive` from `intelligence/water-temp` @ `79b966cc` (identical to live source and to `brain/water-temp`). Tests 14/14 |
| `wind-hourly` + `wind-candidate-read` | **landed** `jobs/wind-hourly` (84 files) from `brain/wind` @ `948fd5e2` (= live `4da234cb` tree). Tests 55 passed / 16 network deselected. Its Brain publisher (`sector_wind/brain/`) is conformed to the shared platform in Phase 4 |
| `lake-surface-daily` | **exception** — live source `feat/clarity-algal-warning` @ `03937913` (Clarity Stage 4 job semantics + data files not on main). `jobs/lake-surface/LINEAGE.md` warns that main's copy is older than live. Pending D4 |
| `clarity-current-hourly` | **exception** — runs ClarityPrecompute from `03937913`, depends on the unshipped Stage 5 engine sources. Pending D4 |
| `clarity-candidate-shadow` | **exception** — paused, private research branch; never public by design |

**No job was redeployed.** No serving image built. Private boundary unchanged (wind job
directory scanned; its docs say detail stays in the private iOS repo). Root `.gitignore`
now excludes `__pycache__/`, `.pytest_cache/`, `.venv/`.

**Acceptance:** canonical path or explicit exception for every live job ✓ · no private
research exposed ✓ · no serving image from Brain/research branches ✓ · tests pass ✓
(Swift suite unchanged since Phase 2 at 169/169; Python 14 + 55).

**Rollback:** `git reset --hard e7735791` (Phase 2 checkpoint).
