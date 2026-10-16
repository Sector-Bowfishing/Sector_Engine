# New Brain Onboarding Checklist

Do these in order. A Brain that skips a step is not "late", it is not on the platform.

**A. Define (RESEARCH)**
- [ ] Brain Spec from `BRAIN_SPEC_TEMPLATE.md`; question in one customer-comprehensible sentence.
- [ ] Claim table with level (1/2/3) **and** maturity as separate columns; every Level-3 claim starts `NOT_VALIDATED`/`PROPOSED`.
- [ ] Dependencies with REQUIRED/OPTIONAL, min maturity, fallback; freshness authority = owner unless a documented stricter rule.
- [ ] Execution type chosen; any recurring schedule justified by reason A/B/C/D, else fingerprint-driven.
- [ ] Slot reserved in `BRAIN_PLATFORM_CONTRACT.md` §2 and `conformance/vocabularies.json` (platform lane change).

**B. Build (PROFILED → SHADOW)**
- [ ] Compact canonical state at `/lakes/{k}/states/{slot}` with the standard envelope (provenance, freshness).
- [ ] stdlib `sector_brain_platform` for keys, RTDB writes (schema gate, app-db refusal), activity events, failure path.
- [ ] Fingerprint of material inputs; `--plan` CLI returns RUN/SKIP; planned fingerprint stored.
- [ ] Runners: worker count via `bounded_workers`; empty work list = successful no-op.
- [ ] UNKNOWN/NOT_OBSERVABLE/WITHHELD published as such — never 0/false.
- [ ] No research dataset, imagery or CSV is a runtime input; customer path reads compact state only.
- [ ] Field-validation block registered (if the Brain has field truth).

**C. Score (platform-compatible)**
- [ ] Rubric id/version; `underlyingScore` vs `canonicalScore` semantics; critical dimensions declared.
- [ ] Score computed by the platform from published facts **or** a generated artifact with `scoreUpdatedAt` and an entry in `score-artifact-sources.json`.
- [ ] Unscored until a rubric exists (no `0`).

**D. Register & expose (SHADOW)**
- [ ] Registry fields: `lifecycle`, `executionType`, `stalenessModel`, `dependsOn`/`dependencies`, `claims`, `schedule`, `lastSuccessfulRun`.
- [ ] `/jobs` manifest entry (owner, purpose, classification, cost).
- [ ] Appears in `control.brains[id]` with only honest fields.

**E. Validate (CALIBRATION)**
- [ ] Validation plan pre-registered (gate, metric, truth type) before outcomes are seen.
- [ ] Prospective ledger or hold-out; field trips through the shared envelope.

**F. Promote (PRODUCTION_READY → PRODUCTION)**
- [ ] Production policy: overall ≥ 8.0 **and** each required critical dimension ≥ 7.5 (unchanged).
- [ ] Recorded approval; deploy plan and rollback; customer path read-only/compact; `customerReadiness` set.
- [ ] Shared-lineage deploy checklist (`BRAIN_MIGRATION_CHECKLIST.md` §6); full-cycle verification.

**G. Hygiene**
- [ ] Handoffs append-only with `HANDOFF_INDEX.md` (`HANDOFF_GOVERNANCE.md`).
- [ ] Tests: claim validation, dependency validation, fingerprint no-op, empty work list.
