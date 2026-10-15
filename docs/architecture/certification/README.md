# Brain Certification V1: shared foundation

**Status:** PROPOSED, for Michael's approval (2026-10-14). Architecture and planning only; nothing live has changed.
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

## Locked by this foundation (subject to Michael's approval of the foundation as a whole)
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

## Unresolved (need Michael's decision; recommendation given)
| ID | Question | Recommendation |
|---|---|---|
| CERT-1 | Where does the Publisher run? (The Orchestrator is a scheduled Cloud Run job today; Ops requests need an always-available API) | Publisher as a shared library used by the Orchestrator job, plus a small authenticated Orchestrator API service that shares the Publisher identity |
| CERT-2 | Build the Publisher before Wind, or inside Wind certification? | A separate **platform** task, "Publisher V1 (shadow only)", on the shared lineage. Wind certification steps 1–7 can run before it; the Wind cutover (step 8+) waits for it |
| CERT-3 | Artifact store and history store: one private bucket or two; names | One private versioned bucket with prefixes `artifacts/`, `publishes/`, `scores/`, `exports/` |
| CERT-4 | Private versioned backup location for research workspaces | One private versioned research bucket, prefix per Brain workspace; chosen and approved during Wind certification |
| CERT-5 | Fish profile serving path (`/speciesProfiles/{id}` vs nested) | Decide in Fish certification; the earlier audit recommends `/speciesProfiles/{id}` (wholesale `/species` reads) |
| CERT-6 | Overall Engine score definition (included Brains, type, version, lifecycle eligibility, missing/stale handling) | Defer; label the aggregate provisional; not recomputed during certification |
| CERT-7 | Ops per-user UI preferences | Allowed as a client-writable per-user node outside all domain paths, or browser-local; never domain truth |
| CERT-8 | Where canonical species identity is authored and released (Species Registry is platform-owned, but its release mechanics are undefined) | A small platform-owned registry release (same release pattern), published by the Publisher; settle before Fish certification step 6 |
| CERT-9 | Writer-identity hardening approach | Assessed privately; decided per Brain at step 9 |
