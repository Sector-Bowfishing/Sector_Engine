Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: run 2026-11-04 (2), Sector_Ops #50 follow-ups

**Approved:**
- merging #111, #112 and #113 after review;
- drafting the Lake dry-run CWMS fault switch, and Sector Intelligence SI-A1 and SI-A3.

**Not decided:** decision 4, the Lake B5 database write.

**Limits:** no cloud jobs, deploys, IAM or write tokens.

| # | Item | Outcome | Where |
|---|---|---|---|
| 1 | Review of #111, #112, #113 | An independent read-only review found **two blockers and several notes. All were fixed before merge, except one, which is decision-required** (below). #112 had no blocker | — |
| 2 | Merge #111 | **Merged** `3ba36828`. Before merge, Water Temp also retires `latestError`, and Lake gets the same derive-or-retire treatment, with a coverage test against its golden write set. **Review blocker, not fixable in scope:** the Orchestrator writes through the `brain-platform` client, and the code ownership guard (`ownership.path_allowed`) refuses `/health/brains/*` and `/health/sources/*`. So a live mirror write would raise and mark the cycle's publication FAILED. This predates #111; merging changed nothing for the worse. A narrow fix broke the Cortex-registry consistency check (FD-15 `PLATFORM_WRITES_BRAIN_FAMILY`) and Publisher refusal codes, so it was discarded unpushed. **It needs an ownership-model decision (CG-3.1-15)** | Engine #111 |
| 3 | Merge #112 | **Merged** `5b39ac9f`. UNKNOWN rows carry an empty `knowledge` block | Engine #112 |
| 4 | Merge #113 | **Merged** `1933690c`. **Review blocker fixed:** a DELETE of a value that exists now (a blanked lake) fails the rehearsal, ops are matched case-insensitively, and reads outside the capture fail it. Registered volatile paths are expected to change. The capture refuses a non-https or non-firebaseio URL and writes owner-only files. The rehearsal strips real database tokens from the job's environment. `--seed-archive` and `--presence` are now declared by Lake's artifact entry and forwarded. #114 was retargeted to main and is still DO NOT MERGE | Engine #113, #114 |
| 5 | Lake CWMS fault | **Draft, green:** `LakeBrainJob --fault cwms-unreachable`, dry run only; the artifact entry refuses it without a local `--artifact-dir`; the rehearsal passes it. **Smoke run with the real job:** Hartwell flagged the CWMS error, fell back to USGS (OBSERVED), the run was WARNING, and no lake was blanked | Engine #117 |
| 6 | SI-A1 | **Draft, green:** `run.py --artifact` seals one artifact, create-only, with the consumption lineage; no database write. `ENGINE_REVISION` (and optionally `ENGINE_IMAGE_DIGEST`) is supplied by the runner, and is reported unverified without the digest | Engine #118 |
| 7 | SI-A3 | **Draft, green:** Intelligence health becomes Orchestrator-derived (registry, artifact builder, brain.json, contract and mirror spec). No effect until it is CENTRAL | Engine #119 |

**Checks**
- brain_platform 850–853; brain-orchestrator 136; brain-publisher 18;
- Fish 407; Intelligence 100–106; Lake 64–67;
- tools/cutover 10; Swift CWMS retry + fault 19;
- tools/architecture 187; brain certification 32; verification 35.
- Every PR was green before merge.

**Not done / gated:**
- Decision 4 is open.
- The ownership-model question is decision-required.
- Nothing deployed, enabled or granted.

**Cortex gaps:** CG-3.1-15.
