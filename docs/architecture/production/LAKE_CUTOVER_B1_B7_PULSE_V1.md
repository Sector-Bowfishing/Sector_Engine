# Lake cutover B1–B7 with Pulse as the runner (DRAFT, Sector_Ops #48 / #50)

**Status: draft plan and tools. Nothing here has been run against production, deployed, granted or enabled.** Every B step is owner-gated. Identity
and bucket details live in the private Sector_Ops #50, not in this public repository.

**What is already done (code, merged):**
- Lake A1–A4: the CWMS retry fix on main (#97), the artifact entry (#98), health made Orchestrator-derived (#99), the knowledge release (#100).
- The order review L-2: Lake goes before Water Temp, recorded in `cutover_order.json`.
- A read-only Brain database identity exists (2026-11-03).

**Why #48's B steps change.**
- #48 assumed Cloud Run: a Lake job deploy, a cloud Lake identity and cloud Publisher executions.
- The owner's standing rule is no cloud jobs until Pulse works. So Lake runs on the Mac under Pulse, from a pinned `origin/main` snapshot, the same way Water Clarity does (#51).
- The one exception is B5: it needs a database **write** by the Publisher, which Pulse V1 never holds.

| # | Step (Pulse) | Replaces in #48 | Who | Tools / commands | Check |
|---|---|---|---|---|---|
| B1 | **Lake runs on the Mac.** A Pulse catalog entry `lake-central` (`WHILE_LEASE_HELD`, like `water-clarity-central`) runs `brains/lake/runtime/artifact_entry.py --job LakeBrainJob --scope pilots --read-rtdb <db> --archive <LOCAL dir> --seed-archive <history bucket, read-only>`, with `SECTOR_ENGINE_COMMIT` set to the snapshot commit. The Swift toolchain is prepared on the Mac mini. **The history archive is local**: the job writes it, so it must never be a bucket from the Mac | deploy `lake-brain` from main | Pulse session (catalog), owner (Mac mini) | Pulse repo | a dry run on the Mac seals one artifact; the snapshot commit is on main |
| B2 | **Identities for the Mac:** database reads use the existing read-only identity. The artifact upload uses the Pulse uploader identity (O2), whose create-only scope grows to `artifacts/lake-brain/`. A read grant on Lake's private history/presence buckets is needed for `--seed-archive` / `--presence`. Denial probes: a database write and an overwrite of an existing artifact must both be refused | a cloud Lake job identity | owner (IAM) | exact commands on Sector_Ops #50 | probes denied |
| B3 | **Baseline capture (G5), read-only and private:** `BRAIN_ACCESS_TOKEN=<1-hour read token> python tools/cutover/rtdb_capture.py --brain lake-brain --out "<Sector Research>/lake-brain/cutover/baseline-<date>"`. It GETs the five pilots' whole `/lakes/{k}`, `/lakeFleet/{k}` and `/snapshots/{k}/latest` (so every consumer slot is captured), `/brains/lake-brain`, `/validation/lake-brain`, `/health/brains/lake-brain`, Lake's `/sources` and `/health/sources`, `/schemaVersion` and `/activity` (the job reads it). It refuses a folder inside a git checkout and never overwrites a capture | same | owner, laptop | `tools/cutover/rtdb_capture.py` | `MANIFEST.json` sha256 recorded in the closeout |
| B4 | **Rehearsal on a fake (G6):** `python tools/cutover/lake_rehearsal.py --capture <B3 folder> --job <built LakeBrainJob> --out <private folder> [--seed-archive gs://… --presence …]`. It serves the capture through a GET-only fake RTDB on 127.0.0.1 (any write is refused and recorded), runs the real artifact entry against it, and compares every sealed mutation with the capture, ignoring only Lake's registered volatile keys | same | laptop | `tools/cutover/lake_rehearsal.py` | `REHEARSAL.json`: no write attempt, nothing read outside the capture, and every non-volatile difference explained (input changes between capture and run are expected and must be explained by source) |
| B4b | **Forced CWMS failure:** the same rehearsal with CWMS unreachable. **Open:** CWMS's address is hard-coded, so this needs either a dry-run-only fault switch (a small follow-up PR) or a network block for that host during the run. The run must degrade honestly and never blank a lake | same | laptop | follow-up | no lake blanked; degraded lakes say why |
| B5 | **One publish (G7).** A cutover entry, `lake-brain` CENTRAL with an approvalRef and the L-2 `orderReviewRef` (draft PR, **do not merge before approval**). Then one Lake artifact from the Mac, one Publisher dry run, then **one live publish**. The live publish is a database write, so it needs either (a) the owner-approved "Level 3" change that gives Pulse a Publisher token for one run, or (b) one cloud Publisher execution, which is an exception to the standing rule | Publisher cloud executions | owner | Engine draft PR (cutover entry); Sector_Ops #50 decision | readback; the Water Temp, Water Clarity, Depth and Vegetation readers' outputs diffed before and after |
| B6 | **Retire (G8):** remove the Swift database write path (`--rtdb`) from `LakeBrainJob` and set `CUTOVER_COMPLETE` in the same change, with an AST pin that no writer is left. Merged only after B5 | same | code PR after B5 | — | the old writer is gone |
| B7 | **Resume Lake:** `execution_control.py enable --brains water-clarity,lake-brain`, with the Orchestrator in runner mode `local` granting Pulse the Lake lease (about every 26 h) | same | owner | `tools/ops/execution_control.py` | 3-day watch as in #46 |

**Also in this change:**
- `LakeBrainJob` now refuses `--read-rtdb` without `--dry-run DIR`, or a bare `--dry-run`, instead of falling through to the live writer. This is the same guard Water Temp got (#104).

**Smoke check (2026-11-04, local, empty capture):**
- the real `LakeBrainJob` ran 5 lakes through the fake;
- it made 12 GETs (`/activity`, `/brains/lake-brain`, and each pilot's `/lakes/{k}/brain` and `/lakes/{k}/states/lake`) and no write;
- it sealed one `lake-publication-v1` artifact with 63 mutations;
- all 63 were correctly reported as "not in capture".

**Halts, abort and rollback:** unchanged from #48. Stop on any of these:
- a blanked lake;
- OBSERVED without a source;
- a write outside Lake's registered families;
- a consumer change at B5;
- CWMS failing for a whole day;
- more than $1 a day.
