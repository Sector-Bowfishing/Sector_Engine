# Depth Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Depth session. It states rules and decisions, never evidence, findings, handoffs or run logs; platform rules are cited, not copied.
> Contract version **0.1.0 (DRAFT, descriptive)**, Cortex 2.1 structural completion, 2026-10-20. Depth is **migrated** into this canonical package from `feat/depth-brain-foundation` (`jobs/depth-brain/`, which stays on that branch). This contract restates the branch's `BRAIN_SPEC.md` and the code; it adds **no new policy and no science**. Undecided items say **NOT ESTABLISHED** and name who decides.

## 1. IDENTITY
`brainId` **`depth`** (stable machine id, never renamed). Display name "Depth Brain", slot `depth`, snapshot field `depth`. Domain: effective depth. Lifecycle **PROFILED** (control manifest); the Brain's own model lifecycle is SHADOW; activity state **PARKED**; validation `NOT_VALIDATED`. Package `brains/depth/`. Runtime `runtime/` (`run.py`, `depth_brain/`, `knowledge/`; stdlib Python). Version `depth-brain-0.1.1-shadow`, model `effective-depth-shift-v1`. Owner: the Depth lane (Michael approves).

## 2. MISSION
Depth answers: **how much deeper or shallower than its reference is this lake right now, and where real contour or rating evidence exists, how much of the lake falls in each depth band?** Effective-depth shift first; zones only where evidence and licence allow.

## 3. BOWFISHER DECISION
Whether familiar flats are shallower or deeper than usual tonight. No customer reads Depth; no bowfisher decision changes until a validated, approved release exists and publication is approved.

## 4. OWNERSHIP
`/lakes/{k}/states/depth`, `/lakeFleet/{k}/slots/depth`, `readiness/depth`, `modelVersions/depth`, the snapshot field `depth` and `brainVersions/depth` for published lakes, `/brains/depth`, `/validation/depth`, `/health/brains/depth` (domain facts), its own activity events. The Depth knowledge release in `runtime/knowledge/` (candidate manifest, claim levels, operator stage-area ratings).

## 5. NON-OWNERSHIP
Depth does **not** own the lake level (Lake Brain owns it; Depth reads published `states/lake` only), lake identity, fish depth preference (Biological), vegetation, clarity, any combination of these (Sector Intelligence), or any score: **Depth has no official score** and the shared scorer has no Depth entry. It never reads Lake's implementation, raw level feeds or the Engine request path.

## 6. DEPENDENCIES
- Lake Brain published state (`lakes/{k}/states/lake`, one `lakeFleet` read), Brain RTDB GET only.
- Lake's reviewed-bindings contract `brains/lake/contracts/reviewed-lake-bindings-v1.json` (offline manifest builder only).
- Platform: `sector_brain_platform` (resolved by `depth_brain/__init__.py`).

## 7. COMMUNICATION CONTRACTS
Published: `depth-publication-v1` (SHADOW; `contracts/depth-publication-v1.json`, derived from the Publisher registry). State schema `depth-state-v1` (`contract.STATE_SCHEMA`). Allowed path: Lake state reads → `publish()` → one ownership-checked multi-path update (LEGACY), **only** from an APPROVED knowledge release and with operator intent `DEPTH_SHADOW_WRITE_APPROVED=1`.

## 8. RESEARCH WORKSPACE
`research/` holds the offline tooling (`research/tools/depth_research`: manifest builder, datum proposals, field-validation scorer, research maturity rubric, unratified score proposals), small research records (`research/tools/depth_research/records`) and `GAPS.json`. Research datasets live in the research workspace (`$DEPTH_RESEARCH_DATA`, branch `docs/depth-brain-research`), never in this repository.

## 9. RESEARCH INITIATION RULES
New research needs Michael's approval (PROJECT §7). Gaps are listed in `research/GAPS.json`.

## 10. RESEARCH STOP RULES
Each gap names its stop condition (`research/GAPS.json`).

## 11. EVIDENCE HIERARCHY
Operator and survey documents over inferred relationships; a datum is proven only by a document, a stamped series or a paired-series test. Unknown stays unknown.

## 12. CANONICALIZATION
Lake ids from the Lake Registry; datums normalized by `datum.normalize_datum`; the manifest is built only by `depth_research.candidates.build` and released as a new `releaseId`.

## 13. VALIDATION
`NOT_VALIDATED`. Field validation is preregistered (`research/tools/depth_research/records/field_validation_prereg.json`) and not started.

## 14. PUBLISHING
The runtime verifies the knowledge release on load. Missing or tampered → refuse (exit 2). Not APPROVED → **abstain**: `--plan` reports `BLOCKED_AWAITING_APPROVED_RELEASE`, `--write` refuses, `--dry-run` needs `--allow-unapproved-release` and never writes. Research tooling has no publish route.

## 15. PATH OWNERSHIP
Enforced by the platform ownership table (`sector_brain_platform.ownership`) and the Publisher registration `depth_specs`.

## 16. SCORING
No score. The research maturity rubric runs offline and is never published; score proposals v1/v2 are unratified research. Any official score would be a shared-scorer change (approval-gated).

## 17. COST RULES
No cloud job, no schedule, no executor (control manifest `executionTarget.kind: none`).

## 18. SECURITY
No credentials in the package; RTDB access only through the platform token provider; no developer-machine paths.

## 19. SESSION CLOSEOUT FORMAT
Cortex session record in `docs/cortex/sessions/`; compliance ledger row updates; standing memory checks for any runtime, knowledge or data-access change.
