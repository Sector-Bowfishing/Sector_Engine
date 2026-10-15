# Brain Certification V1: shared foundation

**Status:** **APPROVED by Michael, 2026-10-14** (foundation + CERT decisions below). Architecture and planning only; nothing has been implemented or changed live. Next: Wind Brain Architecture Certification V1.
**Plan:** certify **Wind** → **Fish Brain** (`biological-state`) → STOP → **Architecture Audit #1** → continue Brain by Brain (Lake → Water Temperature → Water Clarity → Depth → Vegetation → Sector Intelligence, reorderable by the audit, with Intelligence last).

| Document | Defines |
|---|---|
| `BRAIN_CERTIFICATION_V1.md` | the 13-step process, statuses, exit evidence A–J, Architecture Audit #1 |
| `BRAIN_IDENTITY_AND_LINEAGE_V1.md` | brainId / executionId / publishId / requestId / artifactId, lineage block, publication record, freshness, score identity, Engine-score warning |
| `BRAIN_DATA_CLASSIFICATION_V1.md` | RESEARCH, CANONICAL, OBSERVATION_VALIDATION, DERIVED, RUNTIME, HISTORY, OBSOLETE_CANDIDATE |
| `BRAIN_READ_WRITE_SECURITY_V1.md` | target read/write model, artifact handoff, Publisher validation, Ops control via API, rules + IAM + code enforcement |
| `BRAIN_PATH_OWNERSHIP_V1.md` | path families per owner, required rejections, path statuses, 14-step retirement, source acquisition owner vs consumers |
| `BRAIN_RESEARCH_WORKSPACE_V1.md` | locked local research paths, workspace layout, shared-folder rules, research migration policy |
| `WIND_CERTIFICATION_ENTRY_CHECKLIST.md` | what the Wind certification session inventories and checks before changing anything |

Background inventory and matrices: `../data/` (partly superseded; see the header notes there).

## Locked by this foundation (approved 2026-10-14)
1. The specialist Brain owns domain truth; the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`. This is the **target**, not current fact.
2. Specialist Brains read published contracts and produce artifacts; they never read another Brain's private research.
3. Ops is read-only on `sector-brain`; its actions go through an authenticated Engine/Orchestrator API.
4. Customer clients get no internal Brain database access unless separately designed and approved.
5. Stable `brainId`s are preserved (`biological-state` displays as **Fish Brain**); UUIDs are used for executions, publications, requests and artifacts.
6. Standard lineage block, publication record, freshness fields/states and score identity (one authoritative `ENGINE_READINESS_SCORE` per Brain at `/scores/{brainId}`).
7. The seven data classes; irreplaceable classes require a private versioned backup that is not the local Mac.
8. Path ownership enforced as `brainId → schema → path family`; cross-domain writes are rejected; 14-step retirement; duplication never justifies deletion.
9. Species identity is owned by the Species Registry (Engine Platform); Fish Brain owns species intelligence; Lake Brain owns lake species presence and waterbody environment; Policy owns legality and conservation.
10. Research root `/Users/mcather/Desktop/Development/Sector Research` with `shared/` and per-Brain folders; Wind's canonical local workspace is `Sector Research/wind-brain`.
11. Certification never moves a score; BEFORE/AFTER under the same definition.

## CERT decisions (Michael, 2026-10-14)
| ID | Question | Decision | Status |
|---|---|---|---|
| CERT-1 | Where the Publisher runs | The Publisher lives in the Orchestrator platform, with a small authenticated Orchestrator API sharing the Publisher identity | **APPROVED** |
| CERT-2 | When the Publisher is built | **Publisher V1** is built as a **separate, shadow-only platform task** before Wind can complete certification. Wind may proceed through its read-only/inventory steps first | **APPROVED** |
| CERT-3 | Artifact/history storage | One private, versioned artifact/history bucket with prefixes `artifacts/`, `publishes/`, `scores/`, `exports/` | **APPROVED** |
| CERT-4 | Research backup location | One private, versioned research-backup bucket with a prefix per Brain workspace | **APPROVED** |
| CERT-5 | Fish profile serving path | Decided during Fish certification; the preferred direction remains `/speciesProfiles/{id}` | **DEFERRED to Fish certification** |
| CERT-6 | Overall Engine score definition | Remains provisional; not redefined during current certification work | **DEFERRED** |
| CERT-7 | Ops per-user preferences | Must stay outside domain truth; exact storage chosen during Ops implementation | **APPROVED IN PRINCIPLE** |
| CERT-8 | Species Registry | Platform-owned; exact release mechanics settled before Fish publishing work | **APPROVED IN PRINCIPLE** |
| CERT-9 | Writer-identity hardening | Required; exact IAM/service-account implementation decided privately during each Brain certification | **APPROVED IN PRINCIPLE** |

Approval of these decisions authorizes **no implementation by itself**. Bucket creation, Publisher build/deploy, rules/IAM changes, scheduler changes, research moves and path changes each still need their own session-level approval.

## Wind certification record (2026-10-15)
Status **`WIND_PUBLISHER_V2_ADOPTION_READY`** (Phase 3, 2026-10-15; PARTIAL — LIVE CUTOVER PENDING; Phase 2 `SHADOW_INTEGRATION_READY`; Phase 1 `BLOCKED: PUBLISHER`); see `wind/WIND_CERTIFICATION_STATUS.md` and the baseline, inventory, ownership matrix, reader/writer trace, score reconciliation, publish artifact and migration plan in `wind/`. Public-safe only; security and private-location detail is in the private Wind handoff.

Phase 2 adds `wind/WIND_RESEARCH_PRESERVATION_PLAN.md`, `WIND_RESEARCH_MANIFEST_PLAN.md`, `WIND_PUBLISHER_SHADOW_INTEGRATION_REPORT.md`, `WIND_SNAPSHOT_MIGRATION_PLAN.md`, `WIND_CUTOVER_PLAN.md` and the Wind artifact builder (`jobs/wind-hourly/sector_wind/brain/artifact.py`, shadow-only, not wired into the job).

Phase 3 adds `wind/WIND_PUBLISHER_V2_ADOPTION_REPORT.md` (Publisher Gate P adoption, one-artifact v2 bundle, equivalence result) and rewrites `wind/WIND_PUBLISH_ARTIFACT_V1.md` for `publish-artifact-v2`.

Preservation pass (2026-10-15): `wind/WIND_RESEARCH_PRESERVATION_PLAN.md` §6 records the verified local snapshot and the pending storage approval (`WIND_RESEARCH_PRESERVATION_BLOCKED_ON_STORAGE_APPROVAL`).
