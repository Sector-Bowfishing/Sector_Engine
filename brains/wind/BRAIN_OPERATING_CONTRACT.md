# Wind Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Wind research or build session. It states rules and decisions, never evidence, findings, handoffs or run logs. Structured identity and edges live in `brain.json`; platform rules are cited, not copied. A Brain is not a university: research starts from a named gap and stops on a stop condition.
> Contract version **1.0.0** (Repository Phase 2, 2026-10-15). Written from the Wind certification record (`docs/architecture/certification/wind/`); it adds no new policy. Where this file and the certification record disagree, the certification record wins until this file is corrected.

## 1. IDENTITY
`brainId` **`wind`** (stable machine id, never renamed). Display name "Wind Brain", human name "Wind", domain `condition`, lifecycle **CALIBRATION** (science `NOT_VALIDATED`; candidate `wind-candidate-2026.10.stage2-baseline`). Contract version: see `brain.json` `contractVersion`. Owner: the Wind Brain lane (Michael approves). Home: `brains/wind/`.

## 2. MISSION
Wind answers one question per lake: **what are the wind and water-surface conditions doing?** It owns the wind forcing record (NOAA NBM forecast, RTMA-RU analysis, METAR/AWOS observations) for its lakes, the frozen fetch/exposure physics that turn wind into bank surface state, and the honest statement of how reliable that is. Since V2 (2026-10-19) it also produces a specialist **Wind Exposure Assessment** (`runtime/sector_wind/assessment/`, contract `sector-wind-exposure-assessment-v1`, SHADOW and nonproduction): banks exposed to or sheltered from the wind, wind-driven surface disturbance, wind-exposure alternatives (less-exposed and nearest wind-sheltered banks), an hourly wind timeline, confidence and limitations. **Specialist rule:** Wind is the expert in wind; Sector Intelligence owns cross-Brain synthesis and the final bowfishing recommendation. Wind never decides where to bowfish, fishing opportunity, where fish are, water clarity, access, legality or safety, or species behaviour, and no Wind output combines wind with another Brain's domain. Functional layers: Wind Intelligence (forcing + frozen physics), Wind Exposure Assessment (`assessment/`), Learning & Validation (`assessment/scenarios.py`, `contracts/wind-validation-entrypoints-v1.json`, `research/GAPS.json`); see `docs/WIND_BOWFISHING_FIRST_V2.md`.

## 3. BOWFISHER DECISION
Wind supplies the **wind part** of the bowfisher's decision: which banks are exposed to or sheltered from the wind that is forecast or observed, how much the wind disturbs the surface there, and when that changes during the night. Sector Intelligence combines that with the Fish, Water Clarity and Lake Brains to make the bowfishing recommendation. Outputs that do not inform that decision (for example raw model fields nobody reads) are out of scope. Wind does not tell a bowfisher where or whether to go; it describes wind exposure.

## 4. OWNERSHIP
- Wind domain truth: per-lake wind state and profile, per-lake Wind validation, fleet slot/readiness/modelVersions for the `wind` slot (Publisher-derived projections of the lake state), the approved `/brains/wind/{child}` registry children, `/validation/wind`, the domain health facts `/health/brains/wind/{status,staleLakeCount}`, its own `-wind-` activity events.
- Acquisition of its three Brain-exclusive sources: `noaa-nbm-v5`, `noaa-rtma-ru`, `iem-metar-wind` (`providers/PROVIDERS.json`; Wind is acquisition owner, health owner and the only consumer).
- The frozen science: decoder conventions, fetch/exposure physics, chop classes, duration rule, readiness definitions, provider interpretation (the Wind Candidate). Frozen means changed only through a pre-registered, approved science change.
- The Wind certification score definition (`wind-certification-rubric-v1`); the published value lives at `/scores/wind` and is written by the Platform scorer.
Exact authorised path families: `contracts/wind-publication-v1.json` (derived from the Publisher registry).

## 5. NON-OWNERSHIP
Wind does **not** own: canonical lake identity (`/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId` → Platform Lake Registry); Publisher publication metadata (`/brains/wind/publication`, `/brains/wind/certification`); generic job/process/execution health (`/health/jobs/wind-hourly`, `/health/brains/wind/{lastRun,lastSuccess,durationMs,errorCount,latestError,deployedVersion,publishMode}` → Orchestrator); `/activity` retention (platform); the snapshot compatibility copies `/snapshots/{k}/latest/wind` and `…/brainVersions/wind` (Publisher-derived); `/scores/*` (Platform); customer `/conditions` wind (Open-Meteo in the customer Engine); species, legality, lake presence, fishing locations; any other Brain's state. The authoritative list of stopped legacy paths is `compat.LEGACY_PATH_TABLE` in the Platform.

## 6. DEPENDENCIES
- Platform: `sector_brain_platform` (envelope, keys, ownership, freshness, health, Publisher `seal_bundle` and registry), currently at `jobs/brain_platform` (legacy location; vendored into the image).
- Lake identity: the Lake Registry contract (`registry.lakes` ≥ 1.0.0). Interim: `runtime/lakes.json` (4 lakes) is a derived reference copy, verified against the Sector lake directory by `verify_wind_lakes`; it retires when the Lake Registry publishes.
- Providers: the three sources in §4 (registered in `providers/PROVIDERS.json`).
- Other Brains: none (`brainDependencies: []`).

## 7. COMMUNICATION CONTRACTS
- Published: **`wind-publication-v1`** — ONE `publish-artifact-v2` per Wind execution, five sections (`wind-lake-state-v1` scopes `lake-live`, `lake-static`, `fleet-readiness`; `wind-registry-v1`; `wind-source-registry-v1`), sealed with the Publisher's `seal_bundle`, fingerprint `sector-semantic-fingerprint-v2`, volatile contract `wind-volatile-v1`, explicit typed DELETE only. Declaration: `contracts/wind-publication-v1.json`; builder: `runtime/sector_wind/brain/artifact.py`. **Shadow only**: proven against Publisher Gate P; not wired into the job.
- Consumers (`brain.json` `authorizedConsumers`): Ops, Sector Intelligence and the Fish Brain read published Wind state (today via the snapshot compatibility copy), never Wind's runtime or research.
- Allowed paths: providers → Wind runtime → artifact → Publisher → `sector-brain`. No Brain-to-Brain private import, no read of another Brain's research workspace, no call into the customer Engine.

## 8. RESEARCH WORKSPACE
Logical workspace id **`wind-brain`** (`brain.json` `researchWorkspace`). The physical root is resolved by the research operator, never written into code or architecture (this repository is public). Durable private backup: the research-backup bucket, `wind-brain/` prefix. The production runtime never reads the workspace, research caches or any Desktop path (enforced by `verification/integration/test_wind_package.py`). Research tools live in `research/tools/` (code only, no data); their pre-migration local default paths are research-only and are repointed only with Michael's approval and never while the provider bake-off collector runs.

## 9. RESEARCH INITIATION RULES
Research starts only to close a **named, OPEN** gap (product, confidence, readiness, validation or evidence) recorded in `research/GAPS.json` (schema `contracts/schemas/research-gaps.schema.json`). `GAPS.json` does not exist yet: the Wind research lane authors it from the certification blockers; until then no new research campaign starts from this repository. Sealed holdout data (H2, NBM inits 2026-10-07 → 12-31) is not opened, scored or published before 2027-01-01.

## 10. RESEARCH STOP RULES
Stop when more work no longer changes a bowfisher-facing decision, when the remaining question needs field validation (observed surface state on the water), when it needs another Brain or the Platform (Publisher, Orchestrator, Lake Registry), or when it needs Michael's approval (science changes, unsealing, spending, live changes). A stop is recorded, not worked around.

## 11. EVIDENCE HIERARCHY
Highest to lowest: (1) pre-registered prospective field truth on the water; (2) prospective live archive validation against observations (METAR/AWOS, over-water stations), never sealed-holdout skill before its date; (3) physics cross-checks (Python mirror vs the app's `wind-cem`, max |ΔHm0| = 0 recorded); (4) retrospective/historical evaluation; (5) provider bake-off comparisons (inform source choice, not skill claims); (6) exploratory analysis. Claim levels follow the platform `CLAIM_LEVEL_MODEL`; nothing below (1) supports a validated surface claim.

## 12. CANONICALIZATION
No canonical Wind release exists yet (`knowledgeRelease NONE` in artifact lineage). A release requires: a defined `wind-model-v1` manifest (versioned, hashed), evidence referenced by hash from the workspace manifest, Michael's approval, and storage in canonical versioned (CERT-3) storage. Rollback = republish the previous release. Research location never makes anything canonical.

## 13. VALIDATION
Exists: decoder trap tests, conventions, scoring-rule tests, prospective atmospheric reliability archive (4 lakes), physics mirror checks, Publisher V2 shadow proofs and equivalence (`EQUIVALENT_WITH_EXPECTED_DIFFS`). **Not validated:** surface/exposure physics against field truth (Wind certification caps active); live atomic publish and rollback. Architecture certification (`ARCHITECTURE_CERTIFIED_V1`, exit evidence A–J) is separate from scientific validation and is not complete.

## 14. PUBLISHING
Target: Wind produces the `wind-publication-v1` artifact; **only the Publisher** writes `sector-brain` (`publisherRequired.required = true`, cutover status **SHADOW**). Today the deployed `wind-hourly` job still writes directly (legacy writer, unchanged) until the approved cutover (`docs/architecture/certification/wind/WIND_CUTOVER_PLAN.md`). Cadence: hourly at :05 UTC (scheduler-owned). Freshness: `staleAfter` = earliest of `generatedAt + 90 min` and `NBM cycle + 3 h`; `expiresAt` undecided. `customerIntegrationMode` **none**: customers never consume Wind; customer wind is Open-Meteo in the Engine.

## 15. PATH OWNERSHIP
Authorised families and their schema: `contracts/wind-publication-v1.json`. Rejection order is the Publisher's: `brainId → bundle/section schema → path family` (`CROSS_DOMAIN_PATH`, `RESERVED_PATH`, `BRAIN_NODE_REPLACEMENT`, `PLATFORM_DERIVED_PATH`, `PATH_NOT_AUTHORIZED`). Wind never widens its own families; a change is a Publisher registry change reviewed with Wind certification.

## 16. SCORING
Score type `ENGINE_READINESS_SCORE` at `/scores/wind` (Platform writes it). Current value **3.3/10**, basis COMPUTED, `wind-certification-rubric-v1` (baseline: `verification/fixtures/scores/score_baseline.json`). The rubric generator lives on the Wind adoption lineage (`docs/brains/scoring/score-artifact-sources.json`). Moves only with new prospective evidence or an approved rubric change; **certification and repository migration never move a score**. BWIS and the stale 3.1 registry mirror are separate scoring-identity items (certification decision 6). **Three measurements (V2):** the platform scorer (`sector_brain_platform.wind_measurements`) evaluates Wind Capability `wind-specialist-capability-v2` (PROPOSED, pending Michael's review; never replaces the certification score or BWIS v1), Scientific Confidence `wind-scientific-confidence-v1` (evidence statuses, no number) and Production Readiness `wind-production-readiness-v1` (gates, no number). Wind supplies evidence only (`docs/brains/scoring/evidence/wind-measurements-evidence.json`); it never publishes a score. A newer certification block is admitted only through `wind_score_refresh.py` (live reliability refreshes automatically; anything else is HELD for review).

## 17. COST RULES
One Cloud Run job, hourly (≈1 vCPU, 2 GiB, 15 min ceiling), early-exit when the newest NBM cycle is already archived; private candidate archive bucket; free public sources only. Research collectors run locally, not in the cloud. Cost-freeze rules in `docs/brains/platform/` apply; no new scheduled cloud work without approval.

## 18. SECURITY
This repository is public: no secrets, service-account keys, IAM bindings, private bucket contents, live captures, equivalence evidence, research data or personal paths in Git. Wind's live write capability and its hardening are recorded privately; `PRODUCTION_WRITE_SECURITY_GATE_OPEN` remains until the cutover plan's steps 13–14. Deploy scripts refuse to run without `MICHAEL_APPROVED_WIND_DEPLOY=yes`.

## 19. SESSION CLOSEOUT FORMAT
Every Wind session closes with: gap addressed (id); bowfisher decision affected; evidence (references, hashes; private items by location id only); files changed; tests run with PASS/FAIL/BLOCKED_DEPENDENCY/NOT_RUN; score before/after (must be equal unless an approved scoring change); open gaps; human/field validation needed; confirmation of what was not changed (live systems, collector, research workspace, sealed data).
