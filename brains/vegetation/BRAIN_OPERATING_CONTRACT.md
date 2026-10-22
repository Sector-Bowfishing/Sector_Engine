# Vegetation Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Vegetation session. It states rules and decisions, never evidence, findings, handoffs or run logs.
> Contract version **0.1.0 (DRAFT, descriptive)**, Cortex 2.1 structural completion, 2026-10-20. Vegetation is **migrated** into this canonical package from `feat/vegetation-brain-foundation` (`jobs/vegetation-brain/`, which stays on that branch). This contract restates the branch's `BRAIN.md`, the state contract and the code; it adds **no new policy and no science**.

## 1. IDENTITY
`brainId` **`vegetation`** (stable machine id, never renamed). Display name "Vegetation Brain", slot `vegetation`, snapshot field `vegetation`. Domain: aquatic vegetation. Lifecycle **SHADOW**; activity state **PARKED**; validation `NOT_VALIDATED`. Package `brains/vegetation/`. Runtime `runtime/` (`run.py`, `vegetation_brain/`, `knowledge/`; Python + numpy). Version `vegetation-brain-0.3.0-shadow`. Owner: the Vegetation lane (Michael approves).

## 2. MISSION
Vegetation answers: **is surface-reaching aquatic vegetation present on this lake, and where?** V1 observes SURFACE-reaching vegetation only.

## 3. BOWFISHER DECISION
Where vegetated shallows may hold fish. No customer reads Vegetation; nothing changes for a bowfisher until a validated, approved release exists and publication is approved.

## 4. OWNERSHIP
`/lakes/{k}/states/vegetation`, `/lakeFleet/{k}/slots/vegetation`, `readiness/vegetation`, `modelVersions/vegetation`, the snapshot field `vegetation` and `brainVersions/vegetation`, `/brains/vegetation`, `/validation/vegetation`, `/health/brains/vegetation` (domain facts). The Vegetation knowledge release in `runtime/knowledge/` (fleet observability manifest, Level-1 agency records).

## 5. NON-OWNERSHIP
Vegetation does **not** own lake identity, depth, clarity, wind, temperature, fish, any combination of these (Sector Intelligence), or any score: **Vegetation has no official score** and the shared scorer has no Vegetation entry. Submerged vegetation is **never** reported as observed.

## 6. DEPENDENCIES
- Lake Registry (fleet manifest, built offline). `lake-brain` is declared OPTIONAL (the control manifest's provisional edge); it and the other planned context Brains (`water-clarity`, `wind`, `water-temp`, `depth`) are not read by the V1 runtime today.
- Platform: `sector_brain_platform` (resolved by `vegetation_brain/__init__.py`).

## 7. COMMUNICATION CONTRACTS
Published contract `vegetation-publication-v1` (SHADOW; derived from the Publisher registry). **There is no live writer**: the only run mode builds the write set into an in-memory store.

## 8. RESEARCH WORKSPACE
`research/tools/vegetation_research` (fleet manifest builder, agency builders, shared-pass harnesses, preregistered gates, sealed holdout guard, research maturity rubric) and `research/GAPS.json`. Research evidence lives in the research workspace and branch `docs/vegetation-brain-research`.

## 9. RESEARCH INITIATION RULES
New research needs Michael's approval (PROJECT §7). Gaps are in `research/GAPS.json`.

## 10. RESEARCH STOP RULES
Each gap names its stop condition. Never relax a preregistered gate; amend with a dated A#.

## 11. EVIDENCE HIERARCHY
Independent truth (agency surveys, field) over satellite observation; consumed truth sets are never reused as a holdout.

## 12. CANONICALIZATION
Lake ids and geometry from the Lake Registry; the manifest and agency files are built only by research tooling and released as a new `releaseId`.

## 13. VALIDATION
`NOT_VALIDATED`. The shipped observer failed lake-level gates on held-out lakes; the A4 TEST set is consumed.

## 14. PUBLISHING
The runtime verifies the knowledge release on load: missing or tampered → refuse (exit 2). Not APPROVED → **abstain**: `--plan` reports `BLOCKED_AWAITING_APPROVED_RELEASE`; `--dry-run` needs `--allow-unapproved-release` and only writes a local file.

## 15. PATH OWNERSHIP
Enforced by the platform ownership table and the Publisher registration `vegetation_specs`.

## 16. SCORING
No score. The research maturity rubric runs offline and is never published.

## 17. COST RULES
No cloud job, no schedule, no executor; never a second Sentinel schedule. Cap network reads in research tooling.

## 18. SECURITY
No credentials in the package; no developer-machine paths; agency data is internalOnly with an unconfirmed licence.

## 19. SESSION CLOSEOUT FORMAT
Cortex session record in `docs/cortex/sessions/`; compliance ledger updates; standing memory checks for any runtime, knowledge or data-access change.
