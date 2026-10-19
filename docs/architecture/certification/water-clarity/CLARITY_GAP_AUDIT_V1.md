# Water Clarity — Structural Gap Audit V1 (Brain #3, Lane B)

**Date:** 2026-10-17 · **Branch:** `cert/water-clarity-architecture-v1` off `origin/main` `1b17fbdc` · **Procedure:** `audit-1/BRAIN_FACTORY_CHECKLIST_V1.md` Phase 0.
**Status:** `CLARITY_DISCOVERY_AND_D4_RECONCILIATION_READY` — **no implementation written; D4 not crossed; nothing deployed or written to production.**
> **Update 2026-10-18:** every gap in this audit was closed or recorded by the structural certification — see `CLARITY_STRUCTURAL_CERTIFICATION_REPORT.md` (status `WATER_CLARITY_STRUCTURALLY_CERTIFIED_V1_READY_FOR_REVIEW`). This audit is kept as the historical Phase 0 record.
Evidence: git (all branches/worktrees), read-only `gcloud run jobs/scheduler describe|list`, read-only shallow GETs of `sector-brain` (`brains/`, `health/brains/`, `scores/` for `water-clarity`), repository docs. No lake-level data was read.


> ## PASS 2 CORRECTIONS AND DECISIONS (2026-10-17, after Michael's D4 decisions) — read before §1–§9
> **Correction (my error in pass 1):** `main` does **not** hold a reduced "v1.0" publisher. `6220491b` is titled "Water Clarity Brain **v1.1.0** … (public-safe)": the same `brainVersion 1.1.0` code as the raw local branch `d206e01c`, minus the detailed R3.1 research content, plus a private-overlay mechanism (`CLARITY_PRIVATE_CATALOG`), later evolved by the shared Brain Platform shim and the `/jobs` contract. Raw-vs-main differences: catalog detail (bars, thresholds, populations, research-branch evidence refs), 3 docs, one test file, the overlay code. Statements in §1.3, §2, §3 (C1), §4, §8 Option 3 that call main's publisher "v1.0/older/reduced" are superseded. **C1 baseline = `jobs/water-clarity-brain` on main (sanitized v1.1.0) + a private catalog overlay**; the raw catalog is preserved privately.
> **Decisions recorded:** Option 1 Brain-first approved; split certification (C2/C3/C4 stay registered transitional/legacy); v1.1.0 → sanitize (option B); D4 plan approved, not by wholesale merge.
> **Exposure finding:** the repo is PUBLIC. The pass-1 push of `feat/clarity-candidate-shadow` (15,458 files, ~334 MB, 306 PDF/log/CSV files, 10 files with R3.1 certification-bar markers) and `campaign/clarity-readiness` (3 marker files) made that content public. `research/clarity-candidate` (17,793 files, ~472 MB, 13 marker files) was therefore **not pushed**; held for Michael. Raw `brain/water-clarity` history was scanned: both unique commits (`d206e01c`, `3c1d9736`) contain the detail, so the raw branch is not pushed either; private bundles + raw catalog are in `Sector Research/water-clarity/_private-preservation/2026-10-17/`.
> **D4 PR:** #26 (`feat/clarity-d4-runtime-source-v1`, draft) — runtime-source merge of `03937913`; provenance table in `D4_RUNTIME_SOURCE_RECONCILIATION.md` (on that branch).
> **Platform decision/debt (new):** consumption lineage covers RTDB reads only. GCS/HTTP reads (Clarity's real inputs) have no supported-read model; Clarity must NOT fake `stateVersion`/fingerprints. Record as a platform supported-read decision before Clarity lineage can be called complete.
> **Engine `/conditions`:** not to be declared a legitimate long-term dependency until the ownership problem (RA-20) is resolved.

## 1. Headline findings
1. **"Water Clarity" is five things, not one**, and only one of them is a Brain-shaped package (see §3). They live on different branches and none except the v0 publisher is on `main`.
2. **D4 is confirmed and is wider than "the job source is off-main".** Every Clarity Cloud Run job that exists was built off-main (§4). `jobs/lake-surface/LINEAGE.md` on main already says so.
3. **The live `sector-brain` Clarity data was produced by `brainVersion 1.1.0` run manually from the Mac (2026-10-12 06:52Z), and that code exists only on the local branch `brain/water-clarity` (`3c1d9736`)** — deliberately never pushed (public-repo concern about R3.1 research detail in `catalog.json`/docs). `main` carries a *different, older, reduced* v1.0 public publisher. So the data in production RTDB is not reproducible from anything on `origin`. This is a second durability exposure beyond the three approved refs. **I did not push it** (Michael's decision (a)/(b)/(c) in its own closeout note is still open).
4. All Clarity schedulers are **PAUSED** (cost freeze 2026-10-13/14). Nothing is running. No Clarity job is Orchestrator-started (`MANUAL by decision`).
5. Score today is a **research** score: 8.0/10 `FROZEN` `clarity-research-certification-r3.1` for a *CERTIFIED but NOT_DEPLOYED candidate*. Production clarity (`secchi-power-v1`/`rain-decay-v0`) is unscored/unvalidated. Structural work must not move it.

## 2. Branch / worktree inventory (re-verified 2026-10-17)

| Branch | SHA | vs `origin/main` (behind/ahead) | Remote | Worktree | Clean? | What it is |
|---|---|---|---|---|---|---|
| `main` | `1b17fbdc` | — | yes | — | — | v1.0 public publisher `jobs/water-clarity-brain` (3 py files 894 lines + 455-line test file, 35 tests), `lake-surface` v0 job, Swift `Clarity{Gauge,History,State,Factor}`, platform entries |
| `feat/clarity-candidate-shadow` | `82515896` | 163 / **51** | **pushed 2026-10-17 as-is** | `Sector_Engine-candidate` | clean | superset of the Swift/Stage-5 lineage + private candidate shadow job + 14,063 research-candidate files |
| `campaign/clarity-readiness` | `c4dc1727` | 126 / **2** | **pushed 2026-10-17 as-is** | `Sector_Engine-clarity-campaign` | clean | 2 commits on the v0 publisher: input-fingerprint/no-op publish, INVALID-satellite refusals, rain-since-scene invalidation, `BRAIN_SPEC`, readiness rubric proposal, `test_failure_modes.py` |
| `research/clarity-candidate` | `e8891326` | 174 / **111** | **NOT pushed — held** | `Sector_Engine-research` | **DIRTY: 14 untracked files** (2 TCEQ PDFs, `gx` task JSON, 9 `.log` files, `ext_build.log`) | R3.1 research tree (17,688 files). Diverged from candidate-shadow (merge-base `bbafc9ce`; 97 research-only vs 48 shadow-only commits) |
| `brain/water-clarity` (local) | `3c1d9736` | — / 2 | origin has `6220491b` (=`brain/water-clarity-public`, ⊂ main); local is **1 behind / 2 ahead → unpushed by decision** | `Sector_Engine-clarity-brain` is on `brain/water-clarity-public` | clean | **v1.1.0** (`d206e01c`) + closeout. Based on tag `deployed/sector-engine-00072-way`. This produced the live RTDB data |
| `brain/water-clarity-public` | `6220491b` | 161 / 0 | yes | `Sector_Engine-clarity-brain` | clean | already merged into main |
| `feat/clarity-algal-warning` | `03937913` | 163 / 18 | yes | `Sector_Engine-fusion` | — | **built and deployed the live `clarity-current-hourly` + `lake-surface-daily`** |
| `feat/clarity-production` | `214cfe9f` | 163 / 17 | yes | — | — | ancestor of algal-warning |
| `feat/clarity-current-estimate` | `d52b7ac3` | 163 / 8 | yes | — | — | ancestor |
| `feat/clarity-fusion-stage1` | `b3aa7345` | 163 / 4 | yes | — | — | ancestor |

Lineage proven by `merge-base --is-ancestor`: `fusion-stage1 ⊂ current-estimate ⊂ production ⊂ algal-warning ⊂ candidate-shadow`. `research/clarity-candidate` is **not** an ancestor of candidate-shadow (nor vice versa). Branches **only** on this machine now: `research/clarity-candidate` (all 111 commits) and `brain/water-clarity` `3c1d9736`/`d206e01c`.

Push method note: the plain `git push` returned HTTP 400 on the 15,156-object pack; it succeeded with `-c http.postBuffer` enlarged. No ref was rewritten; the remote refs equal the local SHAs above (verified by `ls-remote`).

## 3. The five Clarity components

| # | Component | Source | Runtime | Writes | On main? |
|---|---|---|---|---|---|
| C1 | **Brain publisher** (semantic facts → `sector-brain`) | `jobs/water-clarity-brain` | manual Python (`run.py`); `deploy-job.sh` never run; no Cloud Run job exists | `sector-brain` RTDB via `sector_brain_platform` `rtdb.update` (direct write) | v1.0 only; **v1.1.0 unpushed** |
| C2 | **lake-surface pipeline** (Sentinel-2 L2A → clarity rasters) | `jobs/lake-surface`, `jobs/lake-surface-dispatch`, `jobs/hydrology-hourly` | Cloud Run jobs `lake-surface-dispatch` (img updated 2026-10-13), `lake-surface-daily` (2026-09-29), `hydrology-hourly` (2026-09-27); schedulers PAUSED | GCS `sector-lake-surface` | main has v0 only; **live `daily` is the algal-warning code** (LINEAGE.md) |
| C3 | **ClarityPrecompute** (Swift Stage-5 current-clarity) | `Sources/ClarityPrecompute` | Cloud Run job `clarity-current-hourly`, cmd `/app/ClarityPrecompute`, img `sector-engine@sha256:62e15533…`, `SECTOR_ENGINE_COMMIT=03937913` | GCS `sector-lake-surface/clarity/current` | **no** |
| C4 | **Candidate shadow** (frozen Stage 16/17, private) | `jobs/clarity-candidate` | Cloud Run job `clarity-candidate-shadow`, img `clarity-candidate-shadow@sha256:f2058df6…`, `JOB_COMMIT=6855cb3d`, 6 h timeout; scheduler PAUSED | GCS `sector-clarity-candidate` (private) | **no** |
| C5 | **Production Engine clarity** (customer number) | Swift `ClarityFactor`, `ClarityState*` | Cloud Run service `sector-engine` rev `00072-way` (tag ⊂ main) | none from the Brain | yes |

All Clarity jobs: **no Firebase writes** except C1. C2–C4 write only GCS. Control manifest entry `water-clarity`: lifecycle `CALIBRATION`, `executionTarget` = `lake-surface-dispatch`/`lake-surface-daily`, `dependencies: []`, `staleAfterHours: 26`, `allowedTriggers MANUAL|VALIDATION|ADMIN`, schedule `PAUSED`, `customerPublication: false`. `jobs.py` already records `sourceLineage: "feat/clarity-algal-warning @ 03937913 (explicit exception)"` for C2/C3.

## 4. What main has vs. what production runs vs. what each branch has (D4 facts)
- **Main has:** C1 v1.0 (public, status-level), C2 v0, C5, platform registrations.
- **Production RTDB data (C1 output):** v1.1.0, `lakesPublished 621/621`, `status HEALTHY`, `publisherDeployment: MANUAL_RUN_NOT_DEPLOYED`, `engineRevision sector-engine-00072-way`, `lakeSurfaceRun.day 2026-10-11`. Read-only shallow check confirms `brains/water-clarity`, `health/brains/water-clarity`, `scores/water-clarity` exist.
- **Deployed Cloud Run:** C2 daily, C3, C4 from the algal-warning/candidate-shadow lineage (`03937913`, `6855cb3d` — both ⊂ `feat/clarity-candidate-shadow`); `lake-surface-dispatch` image of 2026-10-13 — **source commit not recorded in env; unresolved** (needs a build-provenance lookup, §7 Q3).
- **D4 (RA-18, HARD CLARITY-PHASE BLOCKER):** `main` cannot be declared the Clarity runtime source because (i) C3/C4 have no code on main, (ii) C2 on main ≠ deployed C2, (iii) C1 production publisher ≠ C1 on main. Swift merge of algal-warning into main conflicts in `Package.swift` and `Dockerfile` only (+ auto-merges in `ClarityStateLoader.swift`, `ClarityStateTests.swift`); `research/clarity-candidate` conflicts only in `.gitignore`. Mergeable with history, no rewrite. B vs C (v1.1.0 vs campaign) conflict in ~10 files — they cannot both be taken wholesale.

## 5. Factory gap table (what Clarity lacks vs `BRAIN_FACTORY_V1`)

| Area | Today | Gap |
|---|---|---|
| Canonical location | `jobs/water-clarity-brain` | no `brains/water-clarity/`; D4 decides what moves |
| Machine `brainId` | `water-clarity` (in `stable_brain_ids.json`, `control_manifest.json`, conformance JSON, RTDB). **Unchanged — no rename.** | none |
| `brain.json` | absent | write (blocked on D4 for runtime kind/entrypoint) |
| Operating contract / README | prose docs under `docs/brains/WATER_CLARITY_BRAIN_*`, `campaign` BRAIN_SPEC | 19-section contract absent |
| Runtime kind | C1 manual python; no Cloud Run job; execution is C2 `cloud-run-job` | decide `job` (Wind path; no Orchestrator code needed) — **which job** is a D4 matter |
| Inputs (real, from v1.1.0 code) | Engine `/lakes`, `/conditions` (customer API — RA-20 says stop), `gs://sector-lake-surface` (C2 output), Cloud Run run status, Cloud Scheduler status, own `catalog.json` | classify §6; customer-API read is a violation candidate |
| Declared deps | manifest `dependencies: []` | must be re-derived from code; do **not** inherit |
| Artifact | writes many RTDB nodes directly; no `publish-artifact-v2` bundle; no `require_freshness` choice | build bundle; freshness model is *TIME* (satellite + provider) — owner statement needed |
| Publisher registry | no Clarity specs/bundles (ownership.json marks `jobs/lake-surface-daily` writer not allowed) | register in SHADOW; data only |
| Lineage / consumption | none | instrument `ConsumptionRecorder` on the RTDB client; GCS/HTTP reads need a supported-read decision (recorder covers RTDB reads only today — **platform gap to confirm, don't fake**) |
| healthV1 | Clarity writes its own `health/brains/water-clarity` (`lastSuccess`, `status`, `staleLakeCount`…) | healthV1 must derive from engine truth; Brain-authored status fields are legacy |
| Freshness | `staleAfterHours 26`, `satelliteFreshDays`, `lastRun`/`lastSuccess` | multiple concepts (scene time, hydrology time, model/generation, publish time) must be kept distinct; `lastSuccess` must not be freshness |
| Direct-write audit | none | classify every `rtdb.update` site in C1 (and the legacy GCS writers C2–C4 as non-RTDB) |
| Score | 8.0 FROZEN research score | record BEFORE; AFTER must equal BEFORE |
| Research workspace | `Sector Research/water-clarity` exists, **empty (0 B)**; actual research is 17,688 files in `research/clarity-candidate` + private GCS `gs://sector-clarity-candidate/research-archive/2026-10-12-closeout/` + `Sector_Research_Data` has no clarity dir | inventory and adopt into the existing workspace; do not create another |
| Large-file policy | 12 MB `guntersville.clarity_evidence…json`; 7.5 MB polygon blob; 856 `docs/data` files in algal-warning | needs policy before any of that lands on main |
| Public-repo hygiene | R3.1 certification detail inside C1 `catalog.json`/docs in v1.1.0 | Michael decision (a)/(b)/(c) pending |
| Tests | main: 35 unittest cases; v1.1.0: 32; campaign: +`test_failure_modes.py` | no certification suite |
| CI | `.github/workflows/python-jobs-tests.yml` references water-clarity | `registered-brains` loop will pick up `brain.json` |

## 6. Dependency classification (provisional, from code — to be verified, not declared yet)
| Input | Class | Note |
|---|---|---|
| Sentinel-2 L2A scenes (via C2 → GCS) | PROVIDER_DATA | sourceOwner `water-clarity` already |
| NOAA MRMS rain, USGS NWIS turbidity | PROVIDER_DATA | owner already `water-clarity`; only if the chosen runtime reads them |
| `gs://sector-lake-surface` clarity/latest.json | **OWN_MODEL output** (C2 is the same Brain's pipeline) — not a Brain dependency | do not model as BRAIN edge |
| Lake directory (`/lakes`) | PLATFORM_REGISTRY (Lake Registry) | currently read through the customer API — RA-20 |
| Engine `/conditions` | **none of the five classes** — it is the production model output via the customer API | RA-20 violation candidate; replace with provider/registry/own-model read |
| Cloud Run / Scheduler status | operational metadata, not a dependency | belongs to Orchestrator/health plane |
| `catalog.json` (R3.1 etc.) | OWN_RESEARCH / OWN_MODEL | public-repo question |
| Other Brains | **none found in the Clarity code read** | downstream consumers of Clarity (Ops panels, beta readiness `waterClarity` slot) are Q5, not verified |
No signals are declared; none will be fabricated.

## 7. Open questions that need evidence before implementation
Q1 Is the C1 v1.1.0 `rtdb.update` set exactly what `sector-brain` holds, i.e. can the stored shape be reproduced from d206e01c? (compare, read-only). Q2 Which of C2–C4 are "Clarity runtime" for the Brain: the Brain *reads* C2's bucket and presently ignores C3/C4. Q3 Source commit of the 2026-10-13 `lake-surface-dispatch` image (check Cloud Build / Artifact Registry provenance). Q4 Does `lake-surface-daily@3d056d3e…` actually equal `03937913`'s `jobs/lake-surface` (reproducible build?). Q5 Does anything consume Clarity RTDB nodes (Ops panels; Lake Brain/Water Temp) so that moving paths is safe — **no path will move in structural work**.

## 8. "Decision A" — which baseline becomes canonical (Michael's choice; I do not choose)

Because Clarity is five components, the real decision is a **composition**:

**Option 1 — Brain-first (recommended).** Baseline for the *Brain package* = **v1.1.0 (`brain/water-clarity`)**, because it is the code that produced the live RTDB state and has the 32-test + semantic-contract work; fold in `campaign/clarity-readiness`' fingerprint/INVALID/no-op logic as a *reviewed follow-up* (it conflicts file-for-file, so it is a manual re-application, not a merge). Resolve D4 for the *runtime source* separately: merge `feat/clarity-algal-warning` @ `03937913` **with history** (C2 `daily.py`, C3 Swift) onto main in a dedicated, reviewed PR, with the large-file policy applied; keep C4 candidate shadow and the 14k research files **off main** (research workspace + archive, referenced by manifest/hash per RA-17). Prerequisite: Michael's catalog decision (a)/(b)/(c) so v1.1.0 can be pushed at all.
**Option 2 — Runtime-first.** Make `feat/clarity-candidate-shadow` (superset) the baseline: merge it with history. Pros: one lineage, matches every deployed image. Cons: brings 14k research files + 856 data files + PDF-class large files into the public repo; mixes research with runtime; contradicts RA-17 / research-vs-runtime separation.
**Option 3 — Main-first.** Certify the v1.0 publisher already on main, treat v1.1.0 and C2–C4 as later adoption. Pros: zero D4 risk now. Cons: certifies code that is **not** what produced production data; weakest evidence; do not recommend.
**Option 4 — Split certification.** Certify only C1 (Brain) as `brains/water-clarity`, leave C2–C4 as registered legacy jobs with `sourceLineage` (already done in `jobs.py`) until a later pass. Compatible with Option 1.

**Recommendation: Option 1 (+4 wording).** It follows the factory (Brain owns domain truth, jobs are inputs), keeps the research off the public main, and makes D4 a bounded runtime-source merge instead of an everything-merge.

## 9. D4 reconciliation plan (proposal; nothing executed)
1. **Decide catalog exposure (a/b/c)** for v1.1.0. If (c), v1.1.0 stays private and Option 1 needs a private-repo or reduced-catalog path.
2. **Push-protect `brain/water-clarity` and `research/clarity-candidate`** (needs Michael: second approval — the first covered only the three named refs; research branch also needs the 14 untracked files triaged).
3. Build-provenance lookup for each deployed image (Q3/Q4); record in the handoff.
4. Dedicated PR "adopt Clarity runtime source (D4)": merge `feat/clarity-algal-warning` with history; resolve `Package.swift`/`Dockerfile`; large-file policy for `docs/data`; replace `LINEAGE.md` warning with a pointer; **no deploy**. Gate: Swift build/tests + the Python job tests green.
5. Only then Phase 1 onward of the factory: `git mv` v1.1.0 into `brains/water-clarity/runtime/`, `brain.json`, contract, artifact, lineage, health, Publisher SHADOW, direct-write audit, certification suite, score BEFORE=AFTER.
6. Final status wording: `STRUCTURALLY_CERTIFIED_V1` only; never "certified".

## 10. Structural risks flagged (not blocking discovery)
- Durability: `brain/water-clarity` (live-data code) and `research/clarity-candidate` are single-machine.
- The deployed images and RTDB data are not reproducible from `origin` today.
- `ownership.json` forbids `jobs/lake-surface-daily` as a writer; yet C2 writes GCS — path-family semantics for GCS are undefined in the Publisher (RTDB-only) → classify C2–C4 writes as non-Publisher "archive" writes; confirm with platform lane.
- Baselines recorded: architecture `report.py --legacy --baseline` → KNOWN 21, NEW 0, RESOLVED 0; `score_baseline.py --check` → water-clarity 8.0/10 (unchanged).
