# Sector Engine Navigation Refresh Report
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Snapshot compared: sector-engine@7dae705-2026-10-20
Engine repository: Sector-Bowfishing/Sector_Engine · HEAD 8a75b01bbfbc (session start; = origin/main 7dae7051 + local Cortex activation commit) · ref cortex/architecture-standardization-2026-10-20 · Date 2026-10-20
Drift command output (`cortex.py drift sector/engine --repo .`, session start):

```text
Snapshot sector-engine@7dae705-2026-10-20 (inspected 7dae7051825f, 2026-10-20)
Repository HEAD 8a75b01bbfbc
5 files changed between snapshot and HEAD.
  Brain inventory in jobs/brain_platform/sector_brain_platform/control_manifest.json matches the snapshot (8 Brains).
0 item(s) need verification.
```

The drift check was clean; every difference below was found by the Stage A audit (snapshot statements that were wrong or have since changed), plus the locations this session added.

## Changes
| # | Snapshot ID affected | Change type | Was (snapshot) | Now (HEAD) | Evidence | Label |
|---|---|---|---|---|---|---|
| 1 | `verify.01` | OBSERVATION_RESOLVED | Intelligence suite 32/33, failing test unidentified | 33/33 pass under pytest (CI's runner). The "32" is the README's `unittest discover`, which cannot collect the pytest-only function `tests/test_sector_intelligence_brain.py:281`; nothing fails | `cd jobs/sector-intelligence-brain && python -m pytest -q` → `33 passed` | VERIFIED_IMPLEMENTATION |
| 2 | `brain.sector-intelligence`, NAVIGATION §7 | CORRECTION | "pilot evaluation over 5 lakes that restates specialist values" (correct) but the Engine docs it points to say it evaluates nothing | Docs corrected in this session; `catalog.json` still contradicts the pilot (decision D-8) | `evaluation.py:27,189-192`; `sector_intelligence_brain.py:345-358,384-394`; commit `b0452ce1` | VERIFIED_IMPLEMENTATION |
| 3 | `obs.01` | OBSERVATION_CHANGED | Lake, Water Temp, Intelligence: no brain.json, no operating contract | Still no brain.json (the repo gate forbids one before migration). Operating contracts now exist at `docs/architecture/certification/{lake,water-temperature,sector-intelligence}/BRAIN_OPERATING_CONTRACT.md` (repo convention `STANDARD_BRAIN_PACKAGE_V1.md` §2), pinned by `tools/architecture/tests/test_unmigrated_brain_contracts.py` | commit `e622a10f`; `tools/architecture/tests/test_foundation.py` `test_real_repo_registers_only_migrated_brains` | VERIFIED_IMPLEMENTATION |
| 4 | NAVIGATION §2 "Do not create directories for absent Brains … creating a canonical package is approval-gated" | CORRECTION | Cites PROJECT.md §7 as gating package creation | PROJECT.md §7 gates moving/renaming referenced directories; the effective block is the Engine's own gate (row 3). Recorded as a Cortex gap | `PROJECT.md` §6, §7 | VERIFIED_IMPLEMENTATION |
| 5 | NAVIGATION §11 "Retired stubs: … `jobs/water-temp-brain/`" | CORRECTION | Listed as a retired stub | It is the **live** deploy script for the `water-temp-brain` Cloud Run job (no scheduler); now has a README | `jobs/water-temp-brain/deploy-job.sh:1-37`; commit `f900ec52` | VERIFIED_IMPLEMENTATION |
| 6 | `brain.water-temp` route | ROUTE_REMOVED (correction) | Water Temp job from the serving image, 3-hourly cron (Engine doc) | `brain-jobs` image, no scheduler, orchestrator-started when stale; registry still publishes `schedule = "every 3 h at :25 UTC"` | `jobs/water-temp-brain/deploy-job.sh:3-8,26-37`; `WaterTemperatureBrain.swift:37` | VERIFIED_IMPLEMENTATION |
| 7 | `obs.03` | OBSERVATION_CHANGED (still true) | Wind `staleHours 6` vs CM `1.5` | Unchanged; runtime uses 90 min (`brains/wind/runtime/sector_wind/brain/contract.py:47-48`), so `brain.json` is the outlier | `brains/wind/brain.json:13`; CM `:14` | VERIFIED_IMPLEMENTATION |
| 8 | `brain.water-clarity` (CM entry) | CORRECTION | CM `water-clarity` treated as the Brain's execution target | CM `executionTarget` names the C2 pipeline (`lake-surface-dispatch` / `lake-surface-daily`, HEAVY), not the C1 Brain job `water-clarity-brain` declared by `brain.json:10-13`; CM `jobs` has no `water-clarity-brain` entry | CM `:26-33,88-99`; `jobs.py:140-148` | VERIFIED_IMPLEMENTATION |
| 9 | `obs.11` | OBSERVATION_CHANGED (still true) | `lake-brain-ledger-daily` not created by any repo script | Still true; registered in CM as `VALIDATION_EXCEPTION` (`brains.lake-brain.schedule`, `jobs.lake-brain-ledger-daily`) | `grep -rn lake-brain-ledger-daily` (docs + CM only); `jobs/lake-brain/deploy-job.sh:40` "no scheduler" | VERIFIED_IMPLEMENTATION |
| 10 | `obs.02` | OBSERVATION_CHANGED (still true) | ID sets 8/6/5/3 | stable ids 6, CM 8, `ownership.BRAINS` (`keys.py`) 8, JM owners 8 (incl. `brain-platform`, `sector-engine`), JM `brainDependencies` 5, `brain.json` 3 | script over the registries (session record §4) | VERIFIED_IMPLEMENTATION |
| 11 | `obs.04`, `obs.09`, `obs.14`, `obs.12`, `obs.13` | OBSERVATION_CHANGED (still true) | as snapshot | Unchanged at HEAD | `publisher_live` imported only by tests/tooling; `ENGINE_READINESS_SCORE` in every `brain.json`; `brains/wind/runtime/sector_wind/brain/publish.py:249,271`; `Package.swift:24-44` | VERIFIED_IMPLEMENTATION |
| 12 | `brain.depth`, `brain.vegetation` | CORRECTION | Branch only | Still branch only; both branches 178 commits behind `origin/main` (40 / 19 ahead), packages at `jobs/depth-brain/`, `jobs/vegetation-brain/` on the branches (not `brains/`), no brain.json or operating contract; Depth branch `run.py:2` claims in-process orchestration, contradicting CM `kind: none` | `git rev-list --count`; `git ls-tree -r feat/depth-brain-foundation` | VERIFIED_IMPLEMENTATION |
| 13 | `platform.orchestrator` | CORRECTION | `orchestrator.py` "is the legacy planner" | Still imported and run each cycle (`orchestrate.py:40-41,258`), output saved to `/control/orchestrator`; it only drives execution with `--legacy-execution` (`:271`). Docstring corrected | commit `0af34d09` | VERIFIED_IMPLEMENTATION |
| 14 | NAVIGATION §6 "`platform/publisher/README.md` is stale (obs.08)" | OBSERVATION_RESOLVED (partly) | stale | Corrected, with `platform/registries/README.md` and `species/README.md`; `brains/README.md` migration text corrected (`4cffb28b`). The `jobs.py` clarity `purpose`/`sourceLineage` strings remain (published to `/jobs`, decision D-10) | commits `0af34d09`, `4cffb28b` | VERIFIED_IMPLEMENTATION |
| 15 | NAVIGATION §11 local verification | CORRECTION | `python -m pytest -q tools/brain_certification` etc. | Run each gate suite separately (as CI does): collecting `tools/architecture tools/brain_certification verification` in one pytest invocation errors at collection (3 errors) | session record §4 | VERIFIED_IMPLEMENTATION |
| 16 | NAVIGATION §2 Lake Brain fallback | DEPENDENCY_CHANGED (note) | — | Unmerged fix branch `fix/lake-brain-cwms-retry` (`125ddae4`) adds bounded CWMS retries | `git log -1 125ddae4` | VERIFIED_IMPLEMENTATION |

## Path verification
All new or changed paths cited above were checked at the work-branch HEAD with `git cat-file -e HEAD:<path>` (or `ls`) during the session: 0 missing. New paths: `docs/architecture/certification/{lake,water-temperature,sector-intelligence}/BRAIN_OPERATING_CONTRACT.md`, `jobs/water-temp-brain/README.md`, `tools/architecture/tests/test_unmigrated_brain_contracts.py`, `brains/{fish,wind,water-clarity}/tests/test_publication_specialist_boundary.py`, `docs/cortex/COMPLIANCE.md`.

## Not checked
- Production lineage (obs.07: job labels, deployed image commits), live scheduler states, IAM and deployed rules (verify.02, verify.03): need approved production read access.
- Sector Ops and Sector Pulse internals (verify.04, verify.05) and the mobile clients (verify.07): other projects.
- Depth and Vegetation branch contents beyond the file listing and the points named in row 12.
