# Sector Data Architecture (v1, PROPOSED)

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


Start with **`SECTOR_DATA_OWNERSHIP_ARCHITECTURE.md`**. Read it with the existing `docs/brains/OWNERSHIP_MATRIX.md`: that file says who owns which science, and this folder says where each piece of data lives, who may write it, how it becomes production, and how it is versioned and rolled back.

| Document | Use it for |
|---|---|
| `CURRENT_DATA_INVENTORY.md` | what exists today (measured live sizes, readers, writers, stores) |
| `RTDB_PATH_OWNERSHIP_MATRIX.md` / `.json` | every current `sector-brain` path → owner, writers, readers, problem, target |
| `SOURCE_OF_TRUTH_MATRIX.md` / `.json` | every data type → canonical owner, storage, serving path, mutability, retention, rollback |
| `TARGET_SECTOR_BRAIN_SCHEMA.md` / `.json` | proposed `sector-brain` tree + cost model |
| `BRAIN_DATA_CONTRACT_V1.md` | the per-Brain `data` block (extends the control manifest) |
| `PUBLISHING_AND_PROMOTION_MODEL.md` | promotion stages, `publish()`, lineage, partial-publish safety |
| `RESEARCH_AND_EVIDENCE_STORAGE.md` | research store, boundary to production, immutability classes |
| `ENVIRONMENT_AND_SPECIES_CLASSIFICATION.md` | species identity, environments, `/speciesProfiles` |
| `DATA_RETENTION_AND_ROLLBACK.md` | retention per data type, rollback per artifact, RTDB export |
| `DATA_MIGRATION_PLAN.md` | staged migration plan + implementation campaigns C1 to C8 |
| `DATA_ARCHITECTURE_DECISION_QUEUE.md` | DA-1 to DA-24 for Michael |

Nothing in this folder changed live data, rules or deployments. This is a public repo, so per-lake species presence, live dumps, user identifiers and the details of app-database security findings are kept in the private handoff.
