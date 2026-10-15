# Repository Architecture V1: Decision Lock

**Status: `REPOSITORY_ARCHITECTURE_V1_APPROVED_FOR_PHASE_1`**
Locked by Michael after review of the audit (commit `082921b1`). Means: **architecture approved for additive foundation work (Phase 1A/1B).** It does NOT mean: repository migrated, Wind migrated, Publisher deployed, any Brain certified, or any live cutover approved. Nothing under `Sources/`, `jobs/`, `Tests/`, `scripts/` or any deploy path has changed.

Detail lives in: `REPOSITORY_AUDIT_DECISIONS.md` (RA-1…RA-23), `TARGET_REPOSITORY_ARCHITECTURE_V1.md`, `STANDARD_BRAIN_PACKAGE_V1.md`, `REPOSITORY_MIGRATION_PLAN_V1.md`, `REPOSITORY_DEPENDENCY_MAP.md`. This page records only what changed in the lock and the rules that must not drift.

## 1. Refinements made by the lock (vs the audit proposal)

| # | Refinement | Where applied |
|---|---|---|
| 1 | **Entity identity ≠ intelligence.** Platform owns canonical entity identity through explicit **entity registries** (Lake Registry, Species Registry). Lake Brain owns intelligence *about* lakes; Fish Brain owns intelligence *about* fish. Consumers resolve lake identity from the Lake Registry contract, not from Lake Brain. | Target tree, dependency map, Brain inventory |
| 2 | **No ambiguous "registry".** `platform/registries/{brains,lakes,species}/`: Brain Registry (generated from `brain.json`), Lake Registry, Species Registry. Provider registry is `providers/PROVIDERS.json` (a catalog, not an entity registry). | Target tree |
| 3 | `customerDirect` replaced by **`customerIntegrationMode: none | embedded | published`** with strict semantics; dependency direction is *Customer Engine → approved Brain contract/library*, never Brain → customer Engine. | Target, Standard package, dependency map |
| 4 | Ownership split (RA-10): `acquisitionOwner`, `healthOwner`, `authorizedConsumers`, `domainInterpreter`. | Provider model, Target |
| 5 | Brain-exclusive single-consumer acquisition may stay with its Brain if registered; shared/customer-serving acquisition converges on `providers/`. | Provider model |
| 6 | Research artifacts are **classified per Brain**, not bulk-moved. Three destinations: GitHub / research workspace / canonical versioned storage. | Standard package, Target |
| 7 | Wind gate (RA-6) tightened: needs A–D, not just "Publisher exists". | Migration plan |
| 8 | Migration split into **1A (additive skeleton, no moves)** and **1B (baseline CI/golden gates, report-only architecture tests)**; Publisher/Wind gate runs in the Publisher/Wind lanes. | Migration plan |
| 9 | Clarity **D4 recorded as a hard Clarity-phase blocker** (not decided here). | Decisions, Migration plan |
| 10 | Package standard: no ceremonial empty directories; `artifact/`, `scoring/`, `validation/` become mandatory when their trigger occurs; `ARCHITECTURE_CERTIFIED_V1` requires README + contract + `brain.json` + required contracts/runtime/tests. | Standard package |
| 11 | Architecture invariants (16) defined, **report-only** in Phase 1B. | Target §7a, Migration plan |
| 12 | Wind/Publisher shadow findings F-1…F-9 and the Publisher production-security gate recorded as **prerequisites owned by other lanes**. | Migration plan §Gate P, Decisions |

## 2. Rules that must not drift
1. Directory expresses ownership. Roots: `engine/ providers/ platform/ contracts/ brains/ tests/ tools/ deploy/ docs/` + root build/bootstrap files.
2. `brain.json` = structured identity and edges only, JSON, never prose/reasoning, never a physical Desktop path; research workspace is a **logical id** (e.g. `wind-brain`); `SECTOR_RESEARCH_ROOT`/config resolves the physical root. `BRAIN_OPERATING_CONTRACT.md` is authoritative for behavior and research instructions. `brain.json` must not become a seventh hand-synchronized registry; generated registries derive from it; old copies retire only after proven equivalence.
3. Machine ids never change (`biological-state` stays; directory is `fish`).
4. Unknown is not zero; research is bounded by a named gap and a stop condition; a Brain is not a university.
5. No runtime dependency on `docs/`. No raw research data in Git. No private IAM/security detail in the public repo.
6. Nothing deletes branches/worktrees; no TVA consolidation before D8; no silent customer-result change.
7. No Publisher change or security decision is made by the repository sessions.

## 3. Publisher / Wind prerequisites (owned by Publisher + Wind lanes, not this session)
F-1 … F-9 and the security gate are listed in `REPOSITORY_MIGRATION_PLAN_V1.md` §"Gate P". They gate **Wind's final Publisher/cutover certification** and, via RA-6(D), **Phase 2 (Wind migration)**. They do **not** gate Phase 1A/1B.

## 4. Remaining items before Phase 1
None are hard blockers. Confirmations Michael may want to make while Phase 1A is prepared (all defaulted in the docs):
* the exact names `platform/registries/{brains,lakes,species}/` (chosen to satisfy "obviously different"; rename is cheap before Phase 1A);
* Phase 1B baseline: which pre-existing failures (if any) are recorded rather than fixed (decided by the 1B run, not in advance);
* the RA-14 read-only private-content review is **not** a Phase 1A/1B blocker (those phases relocate no historical docs or snapshots; only conformance fixtures move, in 1B) but **is** a blocker for any later relocation of `docs/brains/platform/cost-freeze/**` or other historical/lineage docs.

## 5. Implementation status
Phase 1A (additive skeleton + schemas + report-only architecture tooling) is implemented: see `docs/architecture/repository-foundation-v1/PHASE_1A_IMPLEMENTATION.md` (`REPOSITORY_FOUNDATION_PHASE_1A_COMPLETE`). Phase 1B not started.
