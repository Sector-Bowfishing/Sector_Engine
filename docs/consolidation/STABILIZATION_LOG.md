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

---

## Phase 4 — Unified Brain Platform contract — PASS (Wind on a documented adapter)

**Goal:** one Engine-owned contract; conforming Swift and Python implementations; one shared
conformance suite; the Water Temp pruning bug fixed.

**Delivered on main**
- `docs/brains/BRAIN_PLATFORM_CONTRACT.md` v1.0 — instance/keys/atomicity, brain↔slot table, closed
  vocabularies (health, readiness ladder, brain status, model lifecycle, version status, lowercase
  state `kind`, staleness model, severity, activity kinds), the per-lake state envelope with the
  single freshness block (`stale` = time rule, `evidenceStale` = brain rule), shared-field ownership
  (no `lastUpdatedAt`/snapshot `generatedAt` writes by brains; `sources.brains` as a map; source owner
  table), activity id `{ms13}-{brainId}-{nnn}` + own-brain pruning by `at`, transport policy, registry
  shape incl. the Phase 5 `score` block, failure path, plan/descriptor, migration status.
- `docs/brains/conformance/*.json` — 8 fixture files (keys, event ids, pruning, retry, health,
  freshness, ownership, vocabularies).
- Python `jobs/brain_platform/sector_brain_platform/` (stdlib-only; keys, timeutil, enums, activity,
  freshness, health, ownership, rtdb with DryRunStore, failure) — **12/12** conformance tests.
- Swift `Sources/SectorEngine/Brain/{BrainPlatform,BrainContract,BrainRTDBStore}.swift` (keeps the
  lake-brain/water-temp API names; adds vocabularies, activity, freshness, health, ownership,
  failure path, policy-compliant `RTDBRestStore`, `InMemoryBrainStore`) — **11/11** conformance tests;
  full suite **180/180**.
- **Water Temp pruning bug fixed** at the source: `brain/water-temp` @ `ec0ae0fa` (pushed; 17/17
  Brain tests incl. a regression test). The shared Swift platform carries the same correct pruner.
- Wind: **temporary adapter** (own writer, no pruning expected of it) documented in contract §13.

**Vocabulary resolutions:** `stale`/`evidenceStale` split; readiness is never an evidence class;
`ACTIVE_PRODUCTION`→`PRODUCTION`, `RESEARCH_CANDIDATE`→`CANDIDATE`; `stateType`→`kind` (lowercase);
`failures24h` unknown → absent; last-writer-wins fields reassigned to the Orchestrator rollup.

**Not done here (Phase 7):** migrating each Brain's publisher onto the shared implementations.

**Checkpoint:** this commit. **Rollback:** `git reset --hard a9a7a272` (Phase 3).

---

## Phase 5 — Brain Score System — PASS

**Goal:** every active Brain has a legitimate, versioned, Engine-owned published score.

- `docs/brains/scoring/SCORING.md` + machine-readable rubrics `lake-brain-score-v1.json`,
  `biological-state-score-v1.json`, `sector-intelligence-score-v1.json`, and `frozen-scores.json`.
- Evaluator `sector_brain_platform/scoring.py` (pure; UNKNOWN stays unknown; gates cap, never add;
  `completenessPct` excludes UNKNOWN). Tests: 8 scoring + 12 conformance = **20/20**.
- Publisher `jobs/brain-scores/score_brains.py` (platform writer `brain-platform`; contract §5
  amended so `brains/{id}/score` is writable by the brain or the platform writer; fixtures + both
  implementations updated, Swift 11/11, Python 12/12). Manual only — no scheduler.
- **Published 2026-10-12 to `/brains/{id}/score`** (read-back verified):

| Brain | Score | Basis | Why |
|---|---|---|---|
| Lake | **3.0** (uncapped 4.3) | COMPUTED | 5/621 profiled → coverage cap 3.0; NOT_VALIDATED → cap 5.0; pilots score 10 on source authority, operator plan, trend; 20 % on history/baseline |
| Water Temp | **3.0** | FROZEN | Stage 3C.3 Level-4 protected-truth gate FAILED (2 of 4 protected lakes < 25 casts) |
| Water Clarity | **8.0** (research) | FROZEN | R3.1 CERTIFIED candidate, NOT_DEPLOYED; production clarity unscored |
| Wind | **3.1** (certification; BWIS 5.4) | FROZEN | frozen Stage 1/2 rubric v1; caps 6/7 active; production wind unscored |
| Biological | **3.5** | COMPUTED | 27/29 assessed but median species-v2 depth 1.0; Biological State NOT_STARTED → cap 4.0; no VALIDATED species → cap 6.0 |
| Sector Intelligence | **1.0** | COMPUTED | 0/621 evaluated → cap 1.0; 0/5 consumed → cap 2.0; NOT_VALIDATED → cap 5.0 |

Existing scores keep their original semantics (not rescored). Ops computes nothing.
**Rollback:** delete `/brains/{id}/score` nodes (platform-owned) and `git reset --hard 04eff0b4`.

---

## Phase 6 — Sector Engine Score / readiness — PASS

**Goal:** an explainable Engine-level score that is not a naive average, computed from Engine-owned facts.

- `docs/brains/scoring/engine-score-v1.json` frozen **before** first computation; prose in SCORING.md.
  Dimensions: specialist Brain maturity 25, integration completeness 20, lake coverage 10, scientific
  validation 15, runtime reliability 10, production consistency 10, platform health 10. Gates:
  synthesis disconnected → 4.0; lineage unverified → 3.0; any Brain FAILED → 5.0.
- `sector_brain_platform.scoring.score_engine` + 3 tests (23/23 Python total); publisher writes
  `/engine/score` as `brain-platform`.
- **Published 2026-10-12: Engine Score 4.0 / 10** (uncapped 4.1, completeness 90 %).
  Strongest: lake coverage (621/621 lakes have a specialist slot ≥ CALIBRATION). Weakest:
  integration (0/5 Brains consumed by Intelligence) — the gate that caps it. Other facts it
  surfaced: validation mean 1.7 (only Water Temp holdout-only), runtime 7.9 (5/6 brains, 6/8 jobs
  HEALTHY), serving lineage verified, platform conformance UNKNOWN until Phase 7.
- Engine Score, Brain scores, lifecycle, health, coverage and beta readiness are separate nodes.

**Rollback:** delete `/engine/score`; `git reset --hard 7b3fc88a`.

---

## Phase 7 — Land Brain implementations on main — PASS

**Goal:** every active Brain on canonical `main`, publishing through the shared platform; customer
path unchanged; no private research.

| Brain | How it landed | Adaptations | Tests |
|---|---|---|---|
| Biological | merge `brain/biological` @ 99c18f78 (clean) | shim over `sector_brain_platform`; event kinds `brain.registered`/`brain.version`; ownership-checked store; `platform` ref | 29/29 (+ conformance test) |
| Sector Intelligence | merge `brain/sector-intelligence` @ df138c49 (clean) | shim; `kind: not_evaluated`; `platform` ref | 26/26 |
| Water Clarity (public-safe) | merge `brain/water-clarity` @ 6220491b (clean) | shim + vendoring in deploy; no `lastUpdatedAt`/snapshot `generatedAt`/`snapshotVersion`; `kind` + freshness envelope; `sources.brains` map + `ownerBrainId`; `failures24h` absent when unknown | 35/35 |
| Lake | merge `sector/lake-brain` @ eda56c90 (platform files kept from main) | throwing ownership-checked stores; contract event ids/kinds; `platform` ref; own-brain pruning; `brains` map | 19/19 |
| Water Temp | **replayed by file** from `brain/water-temp` @ ec0ae0fa (its Clarity-Stage-5 base left behind); `WaterTempBrainJob` product/target; Dockerfile builds the job binary into the serving image (request path untouched) | readiness → ladder (`CALIBRATION`), evidence → `evidenceClass`; contract event ids/kinds; shared pruner; no rollup-field writes; `brains` map; `platform` ref | 17/17 |
| Wind | already on main (Phase 3) | **temporary adapter** (contract §13); migrates in Phase 8 | 55 |

Platform fixes made while landing: `BrainStoreError(description:)` compatibility init; `BrainPlatformRef`
shared conformance ref; `BrainRtdb` accepts the pre-contract `retries`/`backoff_s`/`timeout_s`
kwargs so existing brain tests keep their meaning; the contract's source-owner table now lists the
ids the Brains actually write.

**Private boundary:** nothing from `research/clarity-candidate`, the private `brain/water-clarity`
or `feat/clarity-candidate-shadow` entered main (merge was the public-safe branch only).
**Conditions Score path:** unchanged (no file under `Engine/`, `Forecast/` or `API/` touched in
this phase). **Full Swift suite 216/216**; Python 23 + 29 + 26 + 35.

**Rollback:** `git reset --hard ddb34c4b` (Phase 6) on main.

---

## Phase 8 — Brain ownership / boundary cleanup — PASS (HIGH client-side duplicates as explicit exceptions)

**Goal:** one canonical owner per important fact/model/rule; no silent customer-semantics change.
Matrix: `docs/brains/OWNERSHIP_MATRIX.md` (status per asset; 7 HIGH exceptions named with owners).

**Changed on main (all behavior-preserving or additive):**
- **Wind off its adapter:** `sector_wind/brain/writer.py` is now a thin wrapper over
  `sector_brain_platform` (contract retries, refusal, key/ownership checks); contract event ids and
  kinds; own-brain pruning by `at`; no `lakeFleet.lastUpdatedAt` / snapshot `generatedAt` /
  `snapshotVersion`; `sources.brains` map + `ownerBrainId`; `platform` ref; vendoring in
  Dockerfile/deploy-job.sh. Tests 55/55. **All six Brains now conform.** The live `wind-hourly` job
  keeps running the pre-migration code until redeployed (not done).
- **Lake-key divergence fixed:** `ClarityStateLoader.slug` → the one `BrainPlatform.lakeKey`
  algorithm (was `|`→`_` only; diverged for 565/621 lakes; only ever worked for Guntersville). Test
  pins all 621 directory ids. Customer impact: none (`/clarity/state` is not called by iOS).
- **Dead code removed:** `BowfishingConditions.windScore` (no callers; contradicted `WindFactor`).
- **Conditions Score versioned:** additive `scoreVersion = conditions-score-v1` and
  `engineRevision` on `/conditions` (`ConditionsScoreVersion.swift`); clients ignore unknown keys.
- **Gin-clear rule de-duplicated:** `WhereToLookEngine` reads `ConditionsConfig.Clarity` constants
  (same defaults 12 ft / 3 mph) instead of its own literals.

**Deliberately not changed (documented exceptions):** client water-temp `k = 0.20` (iOS/Android),
Android directory copy, Engine-vs-iOS spawn temperatures, iOS presence models, the production TVA
midnight parser (decision D8 — customer-visible timing), the Swift/Python wind-physics mirror and
iOS-generated fetch geometry, the L7 conservation gate (D5). Threshold centralization beyond
gin-clear is OPEN (values unchanged, now versioned).

**Tests:** Swift **217/217**; Python platform 23, Biological 29, Intelligence 26, Clarity 35, Wind 55.
**Rollback:** `git reset --hard a03ac84f` (Phase 7).

---

## Phase 9 — Sector Intelligence normalized integration (pilot) — PASS

**Goal:** Intelligence consumes real specialist Brain states for the 5 pilot lakes with full
provenance; failures degrade safely; nothing invented; customer path unchanged.

- `jobs/sector-intelligence-brain/evaluation.py` (`intelligence-eval-v1`): normalized input per slot
  (status PUBLISHED/STALE/DEGRADED/NOT_PUBLISHED, exact Brain + model version, generatedAt, age,
  stale/evidenceStale, readiness, lowercase kind, the specialist's own values restated) and a
  normalized evaluation (inputsUsed, drivers as facts, limiting factors, degradedInputs, synthesis,
  validation NOT_VALIDATED, customerPath `consumesThisEvaluation: false`, provenance with one
  `brainState` source per input, FINGERPRINT freshness). Biological input = Lake Brain presence ∩
  Biological knowledge (gaps are limiting factors). **No fishing judgment and no customer score.**
- Publisher: pilot evaluations computed before `plan()`; `inputs_fingerprint` joins the republish
  fingerprint; a lake that cannot evaluate is recorded under `evaluation.errors` and stays
  NOT_EVALUATED. Dependency status now separates `consumedByCustomerPath` (still false for all) from
  `consumedByPilotEvaluation`; `connectionStatus` = CONNECTED when the pilot consumed the brain.
  Catalog `normalized-sector-intelligence` → lifecycle PILOT, reads all 5 Brains; `catalogVersion 2026-10-12.2`.
- **Published 2026-10-12:** 5/5 pilots evaluated (Guntersville, Wheeler, Wilson, Pickwick, Hartwell),
  0 errors. Honest degradations surfaced: Lake and Water Temp inputs STALE on every pilot (those
  brains last ran > 3 h / 6 h ago — they are unscheduled), Hartwell has no Wind state; connection:
  lake-brain & water-temp CONNECTED_DEGRADED, clarity/wind/biological CONNECTED.
- **Scores re-published:** Intelligence 1.0 → **4.5** (connectivity 10, provenance 10, evaluations
  1/10, validation 0 → cap 5.0), Biological 3.5 → **4.0** (now consumed), **Engine 4.0 → 6.1**
  (synthesis gate lifted; weakest = scientific validation 1.7, strongest = integration).
- Tests: Intelligence **32/32** (26 + 6 evaluation); platform 23.

**Customer behavior:** unchanged — `/conditions` does not read any of this. **Rollback:** `git reset
--hard 76fcdd79`; delete the 5 pilots' `lakes/{k}/states/intelligence` + snapshot fields and rerun
`run.py --no-pilot --write`.

---

## Phase 10 — Ops control-plane data — PASS (Ops not deployed)

**Goal:** Engine publishes enough normalized state for Ops to be a truthful command center and to
compute nothing. Contract: `docs/brains/OPS_CONTROL_PLANE_CONTRACT.md`.

- `sector_brain_platform/control.py` → **`/control/overview`** (`control-plane-v1`): per Brain —
  lifecycle, health, Engine-computed `stale` + reason, scheduled, score, coverage, active/candidate
  model, validation, blockers, dependencies, next opportunity, platform conformance; Engine — score,
  breakdown, blockers, serving revision + lineage, dependency completeness (consumed 5/5, by the
  customer path 0/5), worst Brain health, conformant count; fleet counts; source health/staleness;
  `workNext[]`. **`/control/fleet/{k}`** — the Orchestrator rollup per lake (max `lastUpdatedAt`,
  any-stale, evidenceStale, issueCount, slotsPublished) that brains no longer write to `lakeFleet`.
- **Scores relocated to `/scores/{id}` and `/scores/engine`** (platform-only root): the Biological
  republish showed a brain's whole-node registry write clobbers a platform sub-node, so
  `/brains/{id}/score` is retired (mirrors removed); contract §5/§9, fixtures, both implementations,
  publisher and `control` updated. `/engine/score` kept as an alias.
- Published 2026-10-12: overview for 6 Brains + 621 fleet rollups; worst health WARNING (Lake Brain,
  stale and unscheduled); work-next order lake-brain 3.0, water-temp 3.0, wind 3.1, biological 4.0,
  intelligence 4.5, clarity 8.0. Engine Score 6.1 → **6.4** once platform conformance became
  measurable (2/6 registries republished with the ref; the others publish it on their next run).
- Ops reconciliation documented per branch (biological species-first, intelligence portal, lake-brain
  views, clarity/wind/temp views) and the browser-side computations to retire. **No Ops deploy.**
- Tests: platform 27 → 33 (control + orchestrator); Swift conformance 11/11.

## Phase 11 — Orchestrator foundation — PASS (design + planning core; NOT deployed)

- `docs/brains/ORCHESTRATOR_DESIGN.md`: inputs every Brain publishes, the planning guarantees, the
  (unbuilt) executor, and the stop condition (new recurring cloud work needs approval).
- `sector_brain_platform/orchestrator.py`: pure `plan()` with dependency order, deduplication,
  single-flight (running/lock), conditional refresh (TIME by age / VERSION-FINGERPRINT by the brain's
  own verdict), retry backoff 5/15/45 min then "needs attention", failure isolation (downstream runs
  flagged `degradedUpstream`, never blocked), lake targeting; `descriptor_gaps()`. 6 tests.
- **All six Brains now publish `schedule`, `stalenessModel`, `dependsOn`** (and a descriptor where
  missing) — Python and Swift publishers updated; Biological and Intelligence republished (gaps now
  only on the four Brains awaiting their next run). No per-Brain cron added or changed.

**Rollback:** `git reset --hard 568d6bb1` (Phase 9); `/control`, `/scores` are platform-owned nodes.

---

## Phase 12 — Beta readiness model — PASS (all pilots NOT_READY, explainably)

- `docs/brains/scoring/beta-readiness-v1.json` + `sector_brain_platform/beta.py` (+4 tests): hard blockers
  (required slot not published / stale / evidence-stale / unavailable / below CALIBRATION; no Intelligence
  evaluation; Intelligence not VALIDATED; a required Brain FAILED) → NOT_READY; warnings (readiness below
  VALIDATED, degraded Intelligence input, species-knowledge median < 5, no presence, Brain NOT_VALIDATED,
  stale source) → CANDIDATE; READY needs neither. Never averaged from Brain scores; every item names its slot
  and published fact. Not a customer rollout decision.
- Published `/control/beta/{k}` for the 5 pilot lakes + `_summary`. Result 2026-10-12: **5 × NOT_READY** —
  blockers trace to the Lake and Water Temp slots being stale (unscheduled brains), Intelligence
  NOT_VALIDATED, and Hartwell's missing wind; warnings list the sub-VALIDATED readiness of every slot.
- Intelligence score 4.5 → 4.8 after it republished with `schedule` (runtime dimension).

**Rollback:** `git reset --hard 26276088`; `/control/beta` is platform-owned.

---

## Phase 13 — Cleanup plan (not deletion) — PASS
`docs/consolidation/CLEANUP_PLAN.md`: every worktree and branch classified KEEP / ARCHIVE /
REMOVE-CANDIDATE / BLOCKED from a fresh containment check against `main`. **Nothing deleted.**

## Final self-audit — PASS (independent re-check of the run)
- Production lineage: `sector-engine-00080-wes` still 100 %; the six jobs unchanged; `main == origin/main`.
- Git history: linear consolidation commits on top of `bc9e09fb`; tags intact; no force-push, no rewrite.
- Private boundary: 132 private-only commits unchanged; no private path on `main`.
- Customer behavior: nothing deployed; the `main` diff vs production under `Engine/ Forecast/ API/
  Fetchers/ Hydrology/ Support/` is exactly the Phase 2 restores + USGS migration + additive score
  version + gin-clear config read + slug fix + dead-code removal (14 files).
- Duplicated truth / stale constants: tracked in `OWNERSHIP_MATRIX.md` (7 explicit exceptions).
- Forgotten flags: `SECTOR_CURRENT_CLARITY_ROUTES` / `SECTOR_CLARITY_CANDIDATE_ROUTES` remain set on
  the live revision and inert (documented in `PRODUCTION_LINEAGE.md`).
- Paths pointing at feature worktrees: only inside historical hand-off docs.
- IAM / service accounts: none changed; `score_brains.py` and the brain publishers used the gcloud user
  credential for manual publishes.
- Water Temp pruning regression: fixed on `brain/water-temp` and in the shared pruner; tested in both.
- Lake slugs: one algorithm, fixture-pinned for all 621 ids.
- Candidates presented as production: none — R3.1 and the wind candidate are CANDIDATE/NOT_DEPLOYED
  everywhere; frozen scores say what they score.
- Strong: untouched (frozen Stage 19 semantics; Clarity Brain publishes `NOT_EVALUATED`).
- Presence vs knowledge: Lake Brain owns presence, Biological owns knowledge; Intelligence joins them.
- Intelligence owning specialist science: no — it restates and references; no thresholds of its own.
- Tests re-run at close: Swift 217/217; Python 38 + 29 + 32 + 35 + 55 + 14.
- Beta readiness corrected during the audit: brain-level staleness is now a blocker (was missed when
  only `slots.stale` was read).

**Handoff:** `docs/consolidation/HANDOFF_2026-10-12.md` (also placed in the Desktop handoff folder).
