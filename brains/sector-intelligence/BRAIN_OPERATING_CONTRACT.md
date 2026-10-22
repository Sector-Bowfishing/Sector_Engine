# Sector Intelligence Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Sector Intelligence session. It states rules and decisions, never evidence, findings, handoffs or run logs; platform rules are cited, not copied.
> Contract version **0.2.0 (DRAFT, descriptive)** — Cortex standardization and architecture completion, 2026-10-20. Sector Intelligence is **migrated** into this canonical package (Standard Brain Package V1) (`runtime/`, moved from `jobs/sector-intelligence-brain/`); it is registered (`brain.json`) and adopts Brain Certification Kit V1. This contract **restates** the ratified integration docs and the code; it adds **no new policy and no science**. Undecided items say **NOT ESTABLISHED** and name who decides. Where this file and the integration contract disagree, the integration contract wins until this file is corrected.

## 1. IDENTITY
`brainId` **`sector-intelligence`** (stable machine id, never renamed). Display name "Sector Intelligence", slot `intelligence`, snapshot field `sectorIntelligence`. Domain: synthesis. Lifecycle **CALIBRATION** while pilot evaluations exist (`DISCOVERED` otherwise); activity state **PARKED**; validation `NOT_VALIDATED`. Package `brains/sector-intelligence/`. Runtime: `runtime/` (`run.py`, `sector_intelligence_brain.py`, `evaluation.py`, `orchestration.py`, `catalog.json`; stdlib Python). Versions: `sector-intelligence-brain-0.1.0`, evaluation `intelligence-eval-v1`. Owner: the Intelligence lane (Michael approves).

## 2. MISSION
Sector Intelligence answers: **what does everything Sector knows mean for the bowfisher?** It is the only Brain allowed to combine specialist assessments into bowfishing opportunities, explanations and recommendations. **Today** it does far less: it publishes the inventory of what constitutes Sector Intelligence (four implementations, `catalog.json`), the truth about each upstream Brain's availability and consumption, and, for five pilot lakes, a normalized evaluation that restates specialist states with provenance. It produces **no rating, score or recommendation**.

## 3. BOWFISHER DECISION
The target decision is *where and when to go bowfishing tonight, and why*. That decision is served to customers today by the Engine Conditions Score (`engine-conditions-score`, PRODUCTION, NOT_VALIDATED), which reads no Brain. The pilot evaluation changes no bowfisher decision and no customer consumes it. Activating Intelligence recommendations for customers is approval-gated.

## 4. OWNERSHIP
`/brains/sector-intelligence` (registry: status, dependencies, implementations roster, blockers, vocabularies, orchestration descriptor), `/health/brains/sector-intelligence`, `/validation/sector-intelligence`, `/lakes/{k}/states/intelligence`, `/lakeFleet/{k}/slots/intelligence`, and — for pilot lakes — the snapshot field `sectorIntelligence`, `/lakeFleet/{k}/readiness/intelligence` and `modelVersions/intelligence`; its own activity events. The implementation catalog `catalog.json` (hand-reviewed; the only place implementation facts are declared).

## 5. NON-OWNERSHIP
Sector Intelligence does **not** own any specialist's science or domain values: it never re-derives a lake level, temperature, clarity, wind or biological value, and it reads them only from published Brain state with provenance. It does not own lake identity, species identity, the customer Conditions Score, the iOS FishIntel or guardrail implementations (it catalogs them), Ops labels, or scores (`/scores/sector-intelligence` is written by the platform scorer). It must not silently substitute for a missing specialist.

## 6. DEPENDENCIES
- Brains (read through the Brain RTDB only): `lake-brain`, `water-temp`, `water-clarity`, `wind`, `biological-state` — registry, health, validation status; per pilot lake `lakeFleet/{k}`, `snapshots/{k}/latest`, `lakes/{k}/speciesPresence`, `/species`.
- Engine directory `GET /lakes`; the Cloud Run service document for `sector-engine` (serving revision, image digest).
- Declared roles disagree (open decision): `catalog.json` marks the five dependencies `REQUIRED`; `control_manifest.json` marks them `OPTIONAL` with its own `maxAgeHours`; the code uses each upstream Brain's own `staleAfterHours`.
- Platform: `sector_brain_platform` through the `brain_platform.py` shim.

## 7. COMMUNICATION CONTRACTS
- Published: the registry, dependency, per-lake and evaluation shapes in the integration contract §2–§3 and the "Current state on main" note. The pilot evaluation has a versioned contract, **`intelligence-evaluation-v1`** (`contracts/intelligence-evaluation-v1.schema.json`, validated against real output); the publication contract is **`sector-intelligence-publication-v1`** (SHADOW). The future normalized input contract is still **PROPOSED** prose (`catalog.json` `inputContract`). The planned consumption of `fish-biological-assessment-v1` and `wind-exposure-assessment-v1` is not implemented.
- Consumers: Sector Ops renders the dependency and evaluation fields and never derives them. No customer path reads this Brain.
- Allowed path today: Brain RTDB + Engine `/lakes` reads → publisher → one atomic, ownership-checked RTDB update (LEGACY until a Publisher cutover is approved).

## 8. RESEARCH WORKSPACE
Logical workspace id **`sector-intelligence`** (`BRAIN_RESEARCH_WORKSPACE_V1.md`). Physical roots are never recorded here. Intelligence research stays in the workspace; nothing in the runtime reads it.

## 9. RESEARCH INITIATION RULES
**NOT ESTABLISHED** as a gap register: no `research/GAPS.json` exists yet (created only when a named research gap is approved). Until then work starts only from a declared catalog blocker or a named item in the integration contract and is approved by Michael. Expanding Intelligence functionality is outside the Cortex architecture mission.

## 10. RESEARCH STOP RULES
Stop when more work no longer changes a bowfisher-facing decision, when it needs a specialist Brain's output that does not exist, outcome validation, or Michael's approval (customer activation, new consumers, AI inference). A stop is recorded, not worked around.

## 11. EVIDENCE HIERARCHY
Specialist outputs are used only as published, with their provenance, freshness and validation status; a validated specialist output outranks an unvalidated one, and a stale or degraded input is labelled as such (`STALE`, `DEGRADED`, `NOT_PUBLISHED`). Intelligence never upgrades a specialist's confidence and never fabricates a missing input.

## 12. CANONICALIZATION
Implementation facts become canonical only by a reviewed `catalog.json` change with a bumped `catalogVersion`. A normalized evaluation becomes canonical for customers only by a separately approved activation; nothing in this repository promotes it.

## 13. VALIDATION
Exists: software tests (`tests/`, including the Certification Kit V1 adapter) for dependency truth, lake inputs, published paths, serving lineage, planning, catalog validation and the pilot's degrade/abstain behaviour. **Not validated:** any evaluation (`predictiveValidation.status: NONE`); the customer Conditions Score is also `NOT_VALIDATED`. Known gaps: a failed RTDB read or `GET /lakes` aborts the run instead of degrading.

## 14. PUBLISHING
One atomic multi-path update per run, decided by `plan()`: PUBLISH when the fingerprint changes (upstream registration, status, health, version, lifecycle, serving revision/image, catalog, pilot inputs) or the last publish is > 24 h old. Executed in-process by the Brain Orchestrator (FINGERPRINT trigger); PARKED. `customerIntegrationMode`: none. An evaluation's freshness keeps two times apart: its generation (now) and its evidence (`sourceObservationAt`, the oldest input used).

## 15. PATH OWNERSHIP
The families in §4, enforced client-side by `ownership.py`. Intelligence never writes a specialist's slot, state or registry. The Publisher registry registers Intelligence in SHADOW (`intelligence-lake-state-v1`, `intelligence-registry-v1`, bundle `sector-intelligence-publication-v1`); it writes nothing in production.

## 16. SCORING
Score type `ENGINE_READINESS_SCORE` at `/scores/sector-intelligence`, computed only by the platform scorer (`scoring.py`, rubric id `sector-intelligence-score-v1`; caps for no evaluations, no consumed Brain, validation). Certification, migration and documentation never move it.

## 17. COST RULES
In-process inside the orchestrator; no job, service or scheduler of its own; a few RTDB reads per run. Cost-freeze rules apply; no new scheduled cloud work without approval.

## 18. SECURITY
This repository is public: no secrets, IAM detail, private species presence or private research. Presence is read from the Brain RTDB at run time and is never committed. No LLM or AI inference is used (adding any is approval-gated). The code refuses app-database URLs.

## 19. SESSION CLOSEOUT FORMAT
Every Sector Intelligence session closes with: gap or blocker addressed; bowfisher decision affected; evidence; files changed; tests run with PASS/FAIL/NOT_RUN; score before/after (equal unless an approved scoring change); open gaps; validation needed; confirmation of what was not changed (customer path, apps, live systems, catalog facts, activation state).
