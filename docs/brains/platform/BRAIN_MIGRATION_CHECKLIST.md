# Brain Migration Checklist (to Model v1)

For the **owner lane of each Brain**. The platform lane does not edit specialist branches or science; this is what each owner does when ready. Nothing here is urgent or blocking — Model v1 is additive.

## 1. Generic steps (per Brain)
1. Write/refresh the Brain Spec (`BRAIN_SPEC_TEMPLATE.md`): claim table with **level and maturity as separate columns**; dependencies with freshness authority; execution type and schedule reason.
2. Publish additive registry fields (no removals): `model:"sector-brain-model-v1"`, `lifecycle` (mapped via `LEGACY_LIFECYCLE_MAP`; resolve any `lifecycleMappingAmbiguous` yourself), `executionType`, `claims[]`, `dependencies[]`.
3. Run `validate_claim` over the claim table and `validate_dependency` over dependencies in your own test suite.
4. If your score is a **generated artifact**: it must carry `scoreUpdatedAt`; list it in `docs/brains/scoring/score-artifact-sources.json`. The publisher now holds it if stale. Never commit a regenerated block with an older timestamp than the live one.
5. If you run a thread/process pool, clamp with `bounded_workers`; add an empty-work-list test.
6. Fingerprint: choose material ingredients; compute with `fingerprint.fingerprint`; store the **planned** fingerprint.
7. Do not deploy the shared orchestrator from your branch. Rebase/merge onto the newest shared lineage first (§6) and run the pre-deploy checklist (`jobs/brain-orchestrator`, `SCORE_ARTIFACT_DURABILITY.md` §4).

## 2. Per Brain (state read from live RTDB/Cloud Run 2026-10-14)
| Brain | Live registry | Proposed v1 lifecycle | Proposed executionType | Staleness | Score source | Specific migration notes |
|---|---|---|---|---|---|---|
| **lake-brain** | CALIBRATION, TIME 3 h, manual/orchestrated | CALIBRATION | `DEPENDENCY_DRIVEN` for state refresh via orchestrator TIME backstop; ledger = `PROSPECTIVE_VALIDATION` | TIME | computed by platform from facts | register the ledger as a separate execution reason (reason B); claim table: provider levels L1, rate/geometry L2, predictions L3 NOT_VALIDATED; owner-authoritative freshness is already the Lake pattern |
| **water-temp** | CALIBRATION, TIME 6 h; Cloud Run job `water-temp-brain` (orchestrated, fleet scope) | CALIBRATION | `PROVIDER_INGESTION` (TVA archive hourly) + `DEPENDENCY_DRIVEN` for the model run | TIME | FROZEN 3.0 (Stage 3C.3 decision) | **audit zero-concurrency pattern** (§4); frozen score has `scoreUpdatedAt 2026-10-11` so the guard protects it; model L3, observations L1 |
| **water-clarity** | `BETA`, MANUAL, not deployed | CALIBRATION (ambiguous BETA: owner decides SHADOW vs CALIBRATION) | `MANUAL_SHADOW` | `staleAfterHours 26`, `stalenessModel` absent → declare | FROZEN 8.0 (research score; *not* production quality) | the 8.0 is a **research** certification: publish it as `researchMaturity` semantics in the Clarity block and keep `customerReadiness: NONE`; do not let 8.0 read as production-ready (production policy also needs critical dims ≥ 7.5 and deployment) |
| **wind** | CALIBRATION, TIME 1.5 h, `wind-hourly` cron `5 * * * *` | CALIBRATION | `PROVIDER_INGESTION` (reason A) | TIME | generated block 3.3 (score entry from Wind branch) | (a) generator should emit RTDB-safe dimension names (platform sanitises, but fix at source); (b) retire registry duplicate `scores.windCertificationScore` in favour of `scores.canonicalRef` on next Wind deploy; (c) its score block is the live user of the stale guard; (d) **Wind deployment currently blocked** per prior handoff |
| **biological-state** | PROFILED, VERSION | PROFILED (Brain Spec notes it is between PROFILED and SHADOW; owner chooses) | `DEPENDENCY_DRIVEN` (bundle version) | VERSION | computed by platform | `IN_PROGRESS` capability states are **not** lifecycle values — keep as capability vocabulary; claim table: species presence L1/L2, response predictions L3 NOT_VALIDATED; species-level `researchMaturity` stays a separate axis |
| **sector-intelligence** | CALIBRATION, FINGERPRINT, dependsOn 5 specialists | SHADOW or CALIBRATION (owner) | `DEPENDENCY_DRIVEN` | FINGERPRINT | computed by platform | all claims L3; consumes dependencies with `minClaimMaturity`; adopt `dependencies.evaluate` for its per-dependency `connectionStatus`; keep planned-fingerprint fix (`7a563c18`) |
| **depth** | PROFILED, FINGERPRINT, dependsOn lake-brain, shadow version | SHADOW | `DEPENDENCY_DRIVEN`; `MANUAL_SHADOW` until orchestrator approval | FINGERPRINT | unscored | **do not label Lake input stale independently** — consume Lake's `freshness` (owner-authoritative) or declare a `stricterMaxAgeHours` with reason; `bathymetry`/effective-depth claims L2/L3 |
| **vegetation** | not yet in live registry (surface-only shadow V1 on branch) | SHADOW | `MANUAL_SHADOW` → `DEPENDENCY_DRIVEN` (geometry from Lake) | FINGERPRINT | unscored on platform (internal maturity 2.70, NOT_VALIDATED) | its `claimMaturity` already matches the closed vocabulary — validate with `validate_claim`; `submergedVegetation` stays `NOT_OBSERVABLE`; register slot `vegetation` is already reserved |

## 3. Claim-maturity words already in use (no rewrite needed)
Vegetation `claimMaturity` (uses NOT_OBSERVABLE, NOT_VALIDATED); Lake validation `NOT_VALIDATED`; Biological `researchMaturity` (separate research axis, keep); Wind/Clarity "research"/"candidate" wording belongs to lifecycle/model-lifecycle, not claim maturity.

## 4. Audit requests for owners (platform did not edit these)
- **Water Temp:** search the runner for any pool/worker count derived from config, fleet size or an empty list (`max_workers`, `Pool(`, `ThreadPoolExecutor`, `concurrency`, `parallelism`); clamp with `bounded_workers`; test an empty lake list and `--workers 0`. A grep of `feat/water-temp-brain-adoption` found no `ThreadPoolExecutor` in `jobs/water-temp-brain`, so any concurrency lives in the Swift runner (`Sources/SectorEngine/Brain/WaterTemperatureBrainRunner.swift`) — owner to check that side.
- **Every Brain:** an empty work list must exit success with `attempted: 0`, and health must not read "HEALTHY, 0 failures" when `attempted == 0` without saying so.

## 5. Rubric issues that are actually platform issues (handed over, not edited)
- *Wind score key names contain `/`* — generator-side (platform sanitises only on publish).
- *Frozen blocks without `scoreUpdatedAt`* — would now be `UNDATED`/held once a published timestamp exists. All three current frozen blocks carry one.
- *Two truths for Wind's number* (registry vs canonical) — platform rule: canonical block owns score truth.
- *Control rollups rewritten for `lastUpdatedAt`-only drift* — cost/semantics, DECISION D-4.

## 6. Shared-lineage rule (no backward rollouts)
The shared orchestrator is deployed from the newest safe lineage, not from a specialist branch. Today: deployed commit `5fd727ef` (`feat/lake-opsvis-on-durability`); the platform branch `feat/brain-platform-model-v1` is based on it. Before any deploy: `git merge-base --is-ancestor <deployed-sha> HEAD`; diff only touches intended shared paths; guard + tests green; dry-run shows only intended Brain moves; confirm scheduler/job config unchanged; verify across a full cycle.
