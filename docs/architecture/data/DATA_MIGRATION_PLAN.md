# Data Migration Plan (staged; nothing executed in this campaign)

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


**Principles:** no flag day; no deletion of old data during migration; new paths in shadow first; one reader at a time; old paths retired only after Michael's explicit approval; every live step has a backup, an inventory, a rollback and before/after counts. Respect the shared-lineage rule: platform changes ship on the newest safe shared lineage as additive commits; never redeploy shared jobs from an older lineage.

## Mandatory pre-flight for any live structural step
1. **RTDB export** of every affected top-level path to `gs://sector-brain-history/rtdb-exports/{date}/` with `INDEX.json` (bytes, child counts, sha256).
2. **Exact path inventory** for the step (from `RTDB_PATH_OWNERSHIP_MATRIX.json`): paths written, paths read, by whom.
3. **Writer coordination:** confirm which schedulers are enabled (`wind-hourly`, `lake-brain-ledger-daily` today); pause or sequence only the writers of the affected path; record in the paused-jobs restore register.
4. **Rollback procedure** written before the step (normally: revert reader to old path; old path untouched).
5. **Before/after counts** (children, bytes, fingerprints) for old and new paths.
6. **Validation:** new path content == derived from canonical (fingerprint match), schema-valid, size within `maxBytes`.
7. **Reader verification:** Ops build pointed at the new path shows identical values (screenshot diff / field diff) before the old path's reader is removed.

## Stages

| Stage | What | Live effect | Gate |
|---|---|---|---|
| **0** | Inventory (this campaign) | none | done |
| **1** | Schemas, contracts, validators, tests: `brain-data-contract-v1` blocks in the control manifest; `brain-lineage-v1`; ownership table generated from manifest; `BrainRtdb` refuses `brain_id=None`; explicit `--write` on every writer; env vars cannot enable writes; null/UNKNOWN validator; Ops lint for `LEAF_ONLY` paths and `?? 0` on unknowns | none (code only) | review |
| **2** | New paths in shadow: build `/speciesProfiles`, slim `/species`, `/speciesIndexes`, `/lakeFleet/{k}/rollup`, `/brains/{id}/publication`, `/requests` into `DryRunStore`; diff against current; add rules for `/speciesProfiles`, `/speciesIndexes`, `/requests` (create-only) in the Ops rules file **matching live** + rules tests | rules deploy only (additive read rules; create-only request rules) | Michael approves rules |
| **3** | Publish duplicate derived outputs to new paths where safe: Biological publishes `/speciesProfiles/*` + `/speciesIndexes/*` (old `/species` untouched); scorer writes `/lakeFleet/{k}/rollup` alongside `/control/fleet`; every Brain writes `publication` + lineage; history bucket starts | additive writes | per-Brain approval |
| **4** | Move readers one at a time: Ops Biological tab → `/speciesProfiles/{id}`; Ops lake page → `/lakes/{k}/states` (not snapshot); Ops fleet → `/lakeFleet` rollup (drop `/control/fleet` listener); Intelligence → states + profiles; Biological pilot → states; Ops `/engine/score` → `/scores/engine`; Ops orchestrator → V1 only | reader changes | each verified per pre-flight 7 |
| **5** | Verify no old readers/writers remain: code search across Ops/Engine/iOS/Android/Web on every deployed revision (RTDB has no per-path access log), plus the old path's content left frozen for ≥ 7 days with no complaint from Ops | none | report |
| **6** | Retire old paths **only after explicit approval**: stop writing `/snapshots`, `/control/fleet`, `/engine/score`, `/control/orchestrator`, `/health/jobs`, research metadata in `/species`; slim `/species`; then delete old nodes after a final export | removals | Michael, per path |

## Recommended implementation campaigns (in order)

| # | Campaign | Priority | Scope | Touches live? |
|---|---|---|---|---|
| **C1** | **Backups first** | P0 | private bucket `sector-research-private` (versioned) + rsync of `Sector_Research_Data`; private repo `Sector_Research` (text + bulk manifest); `gs://sector-brain-history` with daily RTDB export job (read-only on RTDB) | new buckets/repo; RTDB read-only |
| **C2** | **Close dangerous writes** | P0/P2 | Clarity `run.py --write` required; Swift jobs ignore env var without `--rtdb`; `BrainRtdb` requires `brain_id`; scorer exception list + honour `--db`; Wind no null-on-miss; Lake explicit presence NONE marker; activity pruning for Biological/Intelligence + key-range prune; `/access` removed from platform-writable set; scheduler drift check (manifest vs Cloud Scheduler) incl. `lake-brain-ledger-daily`; Clarity deploy script no longer creates an enabled scheduler; `ops/setup_alerting.py --apply` flag | code + next deploys (lineage rule) |
| **C3** | **Lineage + publication + history** | P1 | `brain-lineage-v1`, `publication` manifest, `outputFingerprint` for every Brain (feeds orchestrator material change), per-Brain own `codeCommit`, history bucket writes, single-PATCH publishes (Wind first), manifest-last for Clarity | additive fields |
| **C4** | **Species architecture** | P1/P3 | `/speciesProfiles`, slim `/species` (identity + environments + knowledge summary), `/speciesIndexes`, research metadata and per-lake text out of `/species` and `/brains/biological-state`; `run.py` flag for profiles; Ops reads profiles per species | Stage 2–6 |
| **C5** | **Requests** | P2 | `/requests/{control,review,research}` with create-only uid-bound rules; orchestrator consumes control (and actually executes RUN_NOW); Biological review tool consumes review requests into the ledger; research queue listing; outcomes written by Engine | rules + code |
| **C6** | **Duplicate retirement + retention** | P3 | `/snapshots`, `/control/fleet`, `/engine`, `/control/orchestrator`, `/health/jobs`; GCS lifecycle on DERIVED ledgers; AR cleanup with keep-list; `/jobs` pruning | Stage 4–6 |
| **C7** | **App-database hygiene** (owned by app repos, not Engine) | P0 for its security item | see private handoff; plus map app species catalogs to Engine `speciesId` | app rules |
| **C8** | **Doc reconciliation** | P4 | fix `/brains/{id}/score` vs `/scores` in OWNERSHIP_MATRIX / OPS_CONTROL_PLANE_CONTRACT; JOBS_CONTRACT and jobs/README cadence; PRODUCTION_LINEAGE; COST_EFFICIENT_SCHEDULING self-audit items #12/#24; Biological doc's "private research repository" reference | docs |
