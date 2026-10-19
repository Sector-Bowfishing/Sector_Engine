# Brain Factory V1

**Status:** defined by Architecture Audit #1 (`ARCHITECTURE_AUDIT_1_PASS_WITH_NON_BLOCKING_DEBT`). Every statement below is drawn from what Wind (Brain #1) and Fish (Brain #2) actually did; where they differ, the difference is stated. This document **adds no new platform rule**: it consolidates `BRAIN_CERTIFICATION_V1.md`, `STANDARD_BRAIN_PACKAGE_V1.md`, `BRAIN_IDENTITY_AND_LINEAGE_V1.md`, `consumption-lineage-v1`, `brain-health-v1` and the Publisher contracts into one path a new session can follow. If this file and one of those disagree, that file wins and this one is wrong.
Procedure: `BRAIN_FACTORY_CHECKLIST_V1.md`. Debt: `TECHNICAL_DEBT_AFTER_AUDIT_1.md`.

## 1. The path (what "the factory" is)

```
EXISTING / RESEARCH STATE ─► GAP AUDIT (written first) ─► DOMAIN OWNERSHIP ─► brains/<dir>/ ─► brain.json
   ─► DECLARED inputs/deps/providers/signals ─► VERSIONED ARTIFACT + publication contract ─► LINEAGE (actual consumption)
   ─► HEALTH (healthV1, zero Brain code) ─► PUBLISHER REGISTRATION (shadow) ─► DIRECT-WRITE AUDIT ─► CERTIFICATION TESTS
   ─► SHADOW ─(separate decision)─► CALIBRATION/SCIENCE VALIDATION ─(separate)─► PRODUCTION READY ─(separate)─► PRODUCTION
```
Everything left of the first "(separate)" is **structural certification** and is what a Brain-onboarding session does. Everything right of it is not structural and is never done by the same session.

## 2. Files every Brain has

| File / dir | Required | Owner | Notes |
|---|---|---|---|
| `brains/<dir>/brain.json` | **yes** | the Brain | validates `contracts/schemas/brain.schema.json`; the only authority for the Brain's declared edges |
| `brains/<dir>/BRAIN_OPERATING_CONTRACT.md` | **yes** | the Brain | 19 sections (inv 4); rules and decisions only, no evidence |
| `brains/<dir>/README.md` | **yes** | the Brain | ≤ 1 page; how to run tests and the dry run |
| `brains/<dir>/runtime/` | **yes**, real files only | the Brain | entrypoint named by `brain.json.runtime.entrypoint` |
| `brains/<dir>/contracts/<id>-publication-v1.json` | **yes** if it publishes | derived from the Publisher registry | via `describe_contract.py --check` |
| `brains/<dir>/tests/` + `pytest.ini` | **yes** | the Brain | contains the certification suite (§7) |
| `brains/<dir>/research/GAPS.json` (+ `MANIFEST.json`) | **yes** if there is research | the Brain | metadata only, validated; no data in Git |
| `docs/architecture/certification/<dir>/` | **yes** | the certifying session | gap audit first, then publish-artifact, direct-write audit, score reconciliation, certification report |
| `brains/<dir>/deploy/` | only for a Cloud Run job Brain | the Brain | Wind has one; Fish (in-process) has none |
| `scoring/`, `artifact/`, `validation/`, `config/`, `docs/` | when triggered | the Brain | never as empty directories |

Platform-side entries a Brain adds (each is a hand edit today — debt D-7): `tools/architecture/stable_brain_ids.json` (dir→id), `publisher/registry.py` (`<brain>_specs/_bundles`, plus `default_registry()`), `control_manifest.json` brain entry, and the per-Brain tables in `ownership.py`, `keys.py`, `scoring.py`, `jobs.py`, `tools/architecture/ownership_map.json`. For a Brain that already has an identity (Clarity does) most of these already exist; confirm rather than add.

## 3. Who owns what

| Thing | Owner | Mechanism |
|---|---|---|
| `brainId` | the Brain, immutable | `stable_brain_ids.json` + inv 3; directory name may differ (`fish`→`biological-state`) |
| Declared dependencies (consumes, providers, signals, registries) | **the Brain**, in `brain.json` | inv 17 rejects a platform-manifest edge the Brain does not declare |
| **Actual** dependencies | **observed**, never declared | `consumption-lineage-v1` recorder → `consumed[]` in the artifact lineage; `consumedNotDeclared` surfaces drift. Own-state reads are excluded; "unknown" is an absent key, never `[]` |
| Lake identity / Species identity | Platform registries (Lake / Species) | Species Registry is empty today → Fish carries identity in its bundle (D-6) |
| Path families a Brain may write | the Publisher registry (`brainId → schema → path family`) | typed rejections |
| Publication metadata, snapshot copies, job/process health | Publisher / Orchestrator | a Brain must not author them |
| Semantic fingerprint, volatile fields | Publisher (`VolatileContract`) | Brain declares *what is volatile* as data; it never hashes |
| Execution, schedule, retries | Orchestrator | Brain declares `runtime.trigger` |
| Score *value* | Brain's rubric, published by the score pipeline | certification never moves it |
| Architecture status | the certification record (§9) | not the score |

## 4. Output artifact contract
One run → **one** `publish-artifact-v2` bundle → one Publisher plan. Required content: `brainId`, schema ids, `lineage` (`brainId`, `lifecycle`, `reviewStatus`, `validationStatus`, execution identity, input/knowledge release reference, `consumed[]` when instrumented), sections whose paths fall inside the registered path families. Rules proven by both Brains:
- **Deterministic**: same inputs → same semantic fingerprint; `executionId` and per-run timestamps are volatile and must not change it.
- **Typed deletes** only; `null`/missing never means delete.
- **Release/freshness key**: a Brain declares *one* of `require_freshness` (observation-time Brain, Wind) or `require_release` (knowledge-release Brain, Fish) per schema. Both are legal.
- **Never optimistic**: `reviewStatus`/`validationStatus` default `UNREVIEWED`/`NOT_VALIDATED`; the Publisher refuses production lifecycles without an `approvalRef`.
- **Shadow only**: `PublisherMode` has no live member.
- The published contract JSON is **derived** from the registry, never hand-written.

## 5. Publisher requirements
(1) Brain id appears in the registry; (2) every path the artifact can emit is in a declared `PathFamily`; (3) wrong-brain, wrong-schema, wrong-path, foreign-root, reserved-path and node-replacement submissions are rejected with their named code (Fish: 11 path cases); (4) idempotent re-publish → `SKIP`; (5) end-to-end handoff test produces `SHADOW_READY` with `live_mutations == 0`; (6) `describe_contract.py --check` passes. Registration is data in `publisher/registry.py`; **no validator/planner code is changed to onboard a Brain** — if you find yourself changing `validate.py`/`plan.py`/`paths.py`, stop and treat it as a platform change needing its own review (the one Fish precedent, `foreign_owner`, was a precision bug fix with tests).

## 6. Health and freshness
- **healthV1** (`brain-health-v1`) needs **no Brain code**; it reads `brain.json`, the registries, execution records and the artifact. A Brain with zero declared dependencies yields `dependencyHealth SATISFIED`, `freshnessHealth UNKNOWN` — correct and expected.
- **UNKNOWN is a value.** Never substitute 0/false/fresh.
- **`lastSuccessfulRun` is process history, never evidence freshness** (tested in both Brains).
- **Freshness is owner-authoritative.** The Brain states its model via `stalenessModel ∈ {TIME, VERSION, FINGERPRINT}`; a consumer may be stricter but must say why. Observation-time Brains publish `staleAfter`/`staleAfterHours`; version Brains publish `stale:false` + release (explicit `freshnessBasis` statement is debt D-4, P2). Do not invent a model for a new Brain; pick one of the three and state it.

## 7. Mandatory tests (the certification suite)
Both Brains' suites cover the same proofs under different names. A new Brain must have each. **Update (D-7b, BRAIN_CERT_KIT_V1): these proofs now live once, in `tools/brain_certification` (P01–P19); a new Brain supplies a `BrainCertSpec` instead of copying a suite — see `docs/architecture/certification/brain-cert-kit/BRAIN_CERT_KIT_V1.md`.**
1 canonical location & single implementation · 2 `brain.json` valid and `brainId` stable · 3 ownership in contract · 4 declared dependencies validate and equal what the runtime really consumes · 5 no fabricated signals/providers · 6 artifact valid and deterministic · 7 fingerprint ignores execution identity/timestamps; real change changes it; unchanged → SKIP · 8 lineage complete and never fabricated · 9 consumption capture works; unknown stays absent · 10 healthV1 representable; UNKNOWN honest; no freshness from `lastSuccessfulRun` · 11 Publisher accepts (shadow) and rejects wrong brain/schema/path/release/lifecycle · 12 typed deletes · 13 every emitted child covered by the contract · 14 **AST-pinned direct-write set** (exact set equals the audit table) · 15 the artifact path cannot write · 16 no Mac/research/cache paths in runtime; runtime works with no workspace, no HOME, no `docs/` · 17 research separate from the production package · 18 no per-lake/private data in the public package (where applicable) · 19 **science preserved** (golden/equivalence from the pre-move tree) · 20 registered-Brain architecture gates: no NEW violations · 21 score unchanged BEFORE=AFTER. Plus the platform suites (§ report 9) green and Wind unchanged.

## 8. What each tier of "done" means

**Structural certification (`STRUCTURALLY_CERTIFIED_V1`) means:** the Brain has one canonical home and identity; declares real dependencies and nothing else; has a versioned, deterministic, Publisher-valid artifact in SHADOW; carries truthful lineage and health; every direct write is classified and the artifact path writes nothing; research is separated and preserved; science output is byte/semantically preserved; score unchanged; all gates green with no NEW violations.

**It explicitly does NOT mean:** the science is correct or validated; field-tested; research complete; production-ready; customer-visible; the Brain *cannot* write production (the legacy door still exists, merely classified); rules/IAM enforcement (exit evidence F); the Publisher is live; the score reflects architecture; the Orchestrator can run it from the registry; the deployed Orchestrator contains it.

**`ARCHITECTURE_CERTIFIED_V1`** (the full `BRAIN_CERTIFICATION_V1` status, exit evidence A–J) additionally requires a live Publisher, tested write-denial under rules **and** IAM, reader migration and a rollback exercise. Neither Wind nor Fish has it. Do not use the word "certified" unqualified.

## 9. Proposed status vocabulary (a clarification, not a new rule)
`BRAIN_CERTIFICATION_V1.md` §4 has `NOT_STARTED / IN_PROGRESS / PARTIAL / BLOCKED / FAILED / ARCHITECTURE_CERTIFIED_V1`. Wind used `PARTIAL — LIVE CUTOVER PENDING`; Fish used `…_READY_FOR_REVIEW`. Add **`STRUCTURALLY_CERTIFIED_V1`** between `PARTIAL` and `ARCHITECTURE_CERTIFIED_V1`: all structural proofs of §8 pass in SHADOW; exit evidence F (and live Publisher) outstanding. Wind and Fish both qualify today. Requires Michael's sign-off to adopt (D-12, P1); until then write the long form.

## 10. Domain-specific (stays per Brain, never abstracted)
Artifact content and schema fields; the rubric and its dimensions; staleness *model choice*; provider set and signals; keying (lake vs species); science tests and goldens; research tooling; whether the Brain is a job or in-process; legacy-path migration map.

## 11. Known limits of the factory today (read before promising "a day")
Registration is hand-edited in ~8 platform files; the certification suite and `describe_contract.py` are copied per Brain (rule of three: extract after Brain #3); an in-process Brain still needs Orchestrator path code; the Species Registry is empty; the template (`brains/_template/`) is stale — follow the checklist, not the template README.
