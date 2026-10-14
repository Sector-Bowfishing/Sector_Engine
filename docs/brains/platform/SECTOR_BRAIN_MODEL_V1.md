# Sector Brain Model v1

**Owner:** Sector Engine — Brain Platform lane. **Status:** DRAFT-FOR-RATIFICATION 2026-10-14 (not yet merged to `main`; nothing in it changes a live value).
**Machine-readable:** `docs/brains/conformance/model_v1.json` · **Code:** `jobs/brain_platform/sector_brain_platform/{model_v1,fingerprint,publication,dependencies,field_validation,control_contract}.py` · **Tests:** `jobs/brain_platform/tests/test_model_v1.py`, `test_architecture.py`, `jobs/brain-scores/test_cross_brain_publication.py`.

Builds on, and does not replace, `BRAIN_PLATFORM_CONTRACT.md` (RTDB keys, envelopes, ownership) and `OPS_CONTROL_PLANE_CONTRACT.md`. Model v1 adds the *shared language* those contracts lack: what a claim is, how mature it is, where a Brain is in its life, why it runs, what "score" means, and how a score is published safely.

> ## RESEARCH DOES NOT REQUIRE A RUNNING PRODUCTION SYSTEM.
> We pay for **information we need, when we need it.** We do **not** pay to keep **unfinished Brains, idle research, internal dashboards or static scores artificially fresh.**
> Pre-production Brains are **OFF by default**. A capability score does not decay hourly; if code, evidence, validation and coverage are unchanged, the score is unchanged and nothing needs to run.


> **Specialist Brains own the science. The platform owns the rules that let the science operate safely.**
> Engine owns truth · Ops owns presentation · specialists own domain science · platform owns shared mechanics.

## 1. The six independent axes
Every statement about a Brain sits on one of these axes. Conflating them is the root of most past confusion.

| Axis | Question | Vocabulary | Doc |
|---|---|---|---|
| **Claim level** | What *kind* of claim is this? Fixed by construction | 1 provider/observed · 2 deterministic derivation · 3 Sector-derived/predictive | `CLAIM_LEVEL_MODEL.md` |
| **Claim maturity** | How far has *this claim* been tested? Changes over time | closed set of 11 | `CLAIM_MATURITY_MODEL.md` |
| **Brain lifecycle** | Where is the *Brain as a whole* in its life? | RESEARCH → PROFILED → SHADOW → CALIBRATION → PRODUCTION_READY → PRODUCTION | `LIFECYCLE_MODEL.md` |
| **Execution type** | *Why* does this Brain run? | PROVIDER_INGESTION · DEPENDENCY_DRIVEN · PROSPECTIVE_VALIDATION · MAINTENANCE · MANUAL_SHADOW | `EXECUTION_MODEL.md` |
| **Score** (six distinct things) | How capable / how ready? | researchMaturity, underlyingScore, canonicalScore, displayedScore, claim maturity, customerReadiness | `SCORING_SEMANTICS.md` |
| **Freshness** | Is this state/evidence current? | owner-authoritative; `stale` (TIME) vs `evidenceStale` | `FRESHNESS_MODEL.md` |

Hard invariants (each has a test):
1. Claim level never changes because a claim was validated. Validation moves *maturity*.
2. Claim maturity ≠ Brain lifecycle. (`CALIBRATION` is the only word in both vocabularies; the field name says which.)
3. `executionType` (why a Brain runs) ≠ `/jobs.executionMode` (how a job record is triggered: SCHEDULED/MANUAL/EVENT_DRIVEN/DISABLED).
4. No shared field is called bare `score`.
5. UNKNOWN is a value: never `0`, `false`, `poor`, `failed`.
6. The production policy is unchanged: overall ≥ 8.0 **and** every required critical dimension ≥ 7.5.
7. A publish run can only move the Brains it intends to move; a stale artifact is held, not written.
8. A customer request never triggers Brain compute; opening Ops never triggers Brain compute.

## 2. Ownership
| Owner | Owns |
|---|---|
| Specialist Brain | evidence, domain rubric inputs and score calculation, thresholds, validation results, its claim table |
| Platform | registration, vocabularies, claim/lifecycle/execution schema, fingerprint mechanics, dependency metadata, safe durable score publication, stale protection, control-plane mirroring, shared field-validation envelope, shared tests |
| Ops | presentation only; never computes score, staleness, readiness |
| Sector Intelligence | synthesis from specialist outputs; owns no specialist science |

The platform never edits a specialist threshold, evidence record or validation result to normalise architecture. Where a specialist rubric is *itself* a platform problem it is recorded in `BRAIN_MIGRATION_CHECKLIST.md` §5 and handed to the owner.

## 3. What a Brain declares (the Brain Spec)
`BRAIN_SPEC_TEMPLATE.md` is the one-page spec. Machine-facing minimum for registration (additive fields on `/brains/{id}`; all optional until a Brain migrates):
```jsonc
{ "model": "sector-brain-model-v1",
  "lifecycle": "SHADOW",                       // v1 lifecycle, section 4 of LIFECYCLE_MODEL.md
  "executionType": "DEPENDENCY_DRIVEN",        // EXECUTION_MODEL.md
  "claims": [ {"id":"…","level":2,"maturity":"DETERMINISTIC_VERIFIED"} ],
  "dependencies": [ {"id":"lake-brain","requirement":"REQUIRED","minClaimMaturity":"DETERMINISTIC_VERIFIED","stateVersion":"…","fallback":"WITHHOLD"} ],
  "fingerprint": { "ingredients": ["lake.stateVersion","rulesVersion"] } }
```

## 4. Dependencies (kept simple)
No DAG engine. A dependency is `{id, requirement REQUIRED|OPTIONAL, minClaimMaturity?, stateVersion?, fallback DEGRADE|WITHHOLD|SKIP|USE_LAST_GOOD}`. The existing `dependsOn[]` and the orchestrator's topological sort stay. `dependencies.evaluate()` returns SATISFIED / DEGRADED / UNSATISFIED for a consumer, applying **owner-authoritative freshness** (see `FRESHNESS_MODEL.md`). Example graph: Depth ← Lake; Biological ← Lake, Water Temp, Clarity (future Depth, Vegetation); Intelligence ← all specialists.

## 5. Safe score publication (the stale-score solution)
The durable canonical score store is **already** RTDB `/scores/{brainId}`. A frozen/generated block inside an image or worktree is therefore only a *proposal*; the publisher accepts a proposal only if it is not older than what is published (`publication.judge/apply_guard`, wired into `score_brains.py`). This removes the dependency on whichever artifact is baked into a deployment, with no new infrastructure. Details and rejected alternatives: `SCORING_SEMANTICS.md` §6.

## 6. Runtime rules
- **Customer hot path:** read compact canonical state → synthesise → return. No research data, imagery, CSV archives, fleet recompute, provider fan-out, validation, or Brain re-run. Enforced statically by `test_architecture.py`.
- **Ops hot path:** Ops reads cached control state, registry and durable scores. Load/reload/navigation/tabs/focus/reconnect trigger no specialist compute. `OPS_CONTROL_CONTRACT.md`.
- **Orchestrator:** coordinates freshness checks, dependency changes, safe publication, recovery, stale detection and control updates. It does not run every Brain because an hour passed; the existing cheap hourly backstop stays.

## 7. Document map
`BRAIN_SPEC_TEMPLATE` · `CLAIM_LEVEL_MODEL` · `CLAIM_MATURITY_MODEL` · `LIFECYCLE_MODEL` · `EXECUTION_MODEL` (incl. fingerprints, hot paths, cost, zero-concurrency lesson) · `FRESHNESS_MODEL` · `SCORING_SEMANTICS` · `VALIDATION_MODEL` · `FIELD_VALIDATION_MODEL` · `OPS_CONTROL_CONTRACT` · `BRAIN_MIGRATION_CHECKLIST` (per-Brain plan) · `NEW_BRAIN_ONBOARDING_CHECKLIST` · `HANDOFF_GOVERNANCE` · `PLATFORM_CURRENT_STATE` · `DECISION_QUEUE`.

## 8. What is deliberately NOT here
Kafka, an event bus, Pub/Sub topology, a workflow engine, a persistent queue, a distributed scheduler, a handoff database, a second field framework. Fingerprints + the existing jobs + the one orchestrator are sufficient; add machinery only when a measured failure demands it.

## 9. PRE-PRODUCTION COST POLICY (effective 2026-10-14)
A Brain may spend **recurring** cloud money before Production only when **all** hold: (1) it advances a **named readiness gate**; (2) the evidence **cannot reasonably be reconstructed later**; (3) the cost is **bounded**; (4) a **stop condition** is defined; (5) **cheaper alternatives were considered** (manual, on-demand, lighter capture). Everything else is manual, on-demand, dependency-driven, paused, or local.
- Valid exceptions: **A** irreplaceable prospective validation; **B** external provider ingestion needed for an active readiness gate; **C** minimal platform health function a required active system depends on; **D** current customer production (no Brain has one yet).
- Per-job financial gate (answer all or **pause**): job; production gate advanced; irreplaceable data lost if paused; why not manual; estimated monthly cost; customer depends (Y/N); stop date/condition; verdict KEEP TEMPORARILY / PAUSE / MANUAL ONLY.
- Ops and scores are not reasons to run: an internal dashboard showing old timestamps honestly is acceptable; a score is published after a legitimate capability/evidence change or an approved development cycle, never because an hour passed. Stale-score protections stay.
- **Production activation gate:** before a Brain moves toward `PRODUCTION_READY` its owner files an activation proposal — required jobs, cadence and why, expected monthly cost, freshness target, dependency triggers, failure behaviour, rollback, scale behaviour. Only then do recurring operations come back on.
- **Reactivation** needs a recorded form (Brain, readiness gate, why recurring is necessary, expected cost, expected duration, stop condition) — a specialist asking to "turn my hourly job back on" is not sufficient.
- Pause, never destroy: previous state, schedule, target, image and reason are recorded (`cost-freeze/PREPRODUCTION_PAUSED_JOBS.md`); restore is one command. Enforced by `jobs/brain-orchestrator/check_preproduction_schedules.py` against `cost-freeze/schedule-policy.json`.
- Cloud Run: pre-production services default `min instances = 0`; jobs have no compute between invocations.
- Current application (2026-10-14): enabled = `wind-hourly` (Wind reliability gate, ≈ $4/mo) and `lake-brain-ledger-daily` (Lake prediction ledger, ≈ $0.08/mo); everything else paused. See `cost-freeze/`.
