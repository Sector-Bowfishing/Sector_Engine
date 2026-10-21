# Lake Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Lake Brain session. It states rules and decisions, never evidence, findings, handoffs or run logs; platform rules are cited, not copied.
> Contract version **0.2.0 (DRAFT, descriptive)** — Cortex standardization and architecture completion, 2026-10-20. Lake is **migrated** into this canonical package (Standard Brain Package V1) with its Swift runtime as SwiftPM targets `LakeBrain` + `LakeBrainJob`; it is registered (`brain.json`) and adopts Brain Certification Kit V1. This contract **restates** the ratified integration docs and the code; it adds **no new policy and no science**. Undecided items say **NOT ESTABLISHED** and name who decides. Where this file and the integration contract disagree, the integration contract wins until this file is corrected.

## 1. IDENTITY
`brainId` **`lake-brain`** (stable machine id, never renamed; `tools/architecture/stable_brain_ids.json`). Display name "Lake Brain", slot `lake`, snapshot field `lakeState`. Domain: lake level and hydrology state. Lifecycle **CALIBRATION**; validation **`NOT_VALIDATED`**. Package `brains/lake/`. Runtime: Swift — library target `LakeBrain` (`runtime/LakeBrain/`) and executable `LakeBrainJob` (`runtime/LakeBrainJob/`), on top of the shared `SectorEngine` library; offline research and validation tooling stays in `jobs/lake-brain/`. Owner: the Lake lane (Michael approves).

## 2. MISSION
Lake answers: **what is this lake's water level doing, against its own operating rules and history, and how sure is that?** It owns the LakeProfile (pools, operator characteristics, source capability, history coverage, presence summary) and the LakeState (current elevation, change, and `levelState` / `trendState` / `historicalState` / `floodPoolState` as separate fields, with freshness and provenance), computed by explainable baselines and rules (`doy15-percentile-v2`, `lake-level-rules-v2`; no ML).

## 3. BOWFISHER DECISION
Lake gives the bowfisher the level context for a lake tonight — normal, low, high, rising, falling, unusual for the season, in flood pool — and how fresh and reliable that reading is. It does **not** say what fish do about the level; that is Sector Intelligence (and, on the customer path today, the Engine Conditions Score's `WaterLevelFactor`, which Lake does not touch). An output that does not change that context is out of scope.

## 4. OWNERSHIP
- `/lakes/{k}/brain` (LakeProfile), `/lakes/{k}/states/lake` (LakeState), `/lakes/{k}/speciesPresence` (whole node), the leaf `/snapshots/{k}/latest/lakeState` (+ `lakeId`, `brainVersions/lake-brain`), the `/lakeFleet/{k}` leaves `readiness/lake`, `slots/lake`, `modelVersions/lake`, `riverSystem`, `lakeId`.
- `/brains/lake-brain`, `/validation/lake-brain`, `/health/brains/lake-brain`, `/health/jobs/lake-brain`, source health for `tva-restapi`, `usace-cwms-pool`, `usgs-nwis-lake-elevation` (`/sources/…`, `/health/sources/…`), and its own `/activity` events.
- The reviewed source bindings (`LakeSourceBindings.swift`, acceptance gate in the integration contract §5.3), the baselines and classification rules, the readiness ladder `lake-brain-readiness-v1`.
- The private bucket `gs://sector-lake-brain` (history, baselines, presence releases, the prospective prediction ledger).
Exact path rules: integration contract §2; client-side enforcement `ownership.py` / Swift `BrainOwnership`.

## 5. NON-OWNERSHIP
Lake does **not** own: **lake identity** (the Lake Registry is the Engine directory `GET /lakes`; directory fields are never copied); species knowledge (Fish Brain); what fish do about the level (Sector Intelligence); water temperature, clarity, wind (their Brains); the shared lake-level fleet fields `stale`, `issueCount`, `hasObservations`, `lastUpdatedAt` (a platform cross-Brain rule, not yet decided); `/schemaVersion`; presentation and labels (Sector Ops); scores (`/scores/lake-brain` is written only by the platform scorer).

## 6. DEPENDENCIES
- Lake Registry: the Engine directory `GET /lakes` (no registry contract version is read).
- Providers declared in `jobs.py` (`lake-brain`): TVA REST API, USACE CWMS pool, USGS NWIS lake elevation; archives: the Water Temp lane's TVA archive (`gs://sector-water-temp-archive`, read-only, approved 2026-10-12) and `gs://sector-lake-brain`.
- Observed but **not declared**: Access2Water, NWPS, Reclamation RISE, IEM HADS and USGS daily-value fetchers (`LakeLevelFeedsFleet.swift`), used by fleet and candidate runs. Reconciling the declaration is an open item.
- Other Brains: none consumed. Platform: shared Swift Brain platform (`Sources/SectorEngine/Brain/`).

## 7. COMMUNICATION CONTRACTS
- Published: the RTDB shapes in the integration contract §2–§4, §8–§10 (Swift types in `LakeBrainContract.swift`; key and rule conformance `contracts/conformance/lake_keys.json`, `lake_rules_v2.json`). Publisher contract **`lake-publication-v1`** (`contracts/lake-publication-v1.json`, derived from the Publisher registry; **SHADOW only**, builder `runtime/publish_artifact.py` over one run's write set). No separate versioned JSON schema for LakeState yet.
- Consumers: Sector Ops (display) and Sector Intelligence (`LakePresenceIndex.resolveLakeSpecies`, published states). Nothing in the customer request path imports this module.
- Allowed path today: providers/archives → `LakeBrainJob` → direct, ownership-checked RTDB updates (LEGACY until a Publisher cutover is approved).

- State contract **`lake-state-v1`** (`contracts/lake-state-v1.schema.json`): generated from the Swift Codable record by `tools/architecture/swift_state_schema.py` and validated against the recorded write set (`tools/architecture/tests/test_swift_state_schemas.py`).

## 8. RESEARCH WORKSPACE
Logical workspace id **`lake-brain`** (`docs/architecture/certification/BRAIN_RESEARCH_WORKSPACE_V1.md`). The physical root is never written into code or this public repository. Private research (binding research, presence matrix, history studies) stays in the workspace and the private bucket; this repository holds only code, generated binding tables and validation tooling.

## 9. RESEARCH INITIATION RULES
**NOT ESTABLISHED** as a gap register: Lake has no `research/GAPS.json` yet (created only when a named research gap is approved). Until then research starts only from a named item in the Lake docs' open lists (integration contract §13 *Known limits*, the rules-v2 pre-registration and results) and is approved by Michael. Pre-registered hold-outs are run once and never re-tuned.

## 10. RESEARCH STOP RULES
Stop when more work no longer changes the level context a bowfisher gets, when the answer needs field or operator truth, another Brain or the Platform (shared fleet fields, Publisher), or Michael's approval (binding acceptance, validation campaign, new providers, spending). A stop is recorded, not worked around.

## 11. EVIDENCE HIERARCHY
Highest to lowest: (1) the operator's own pool record and operating guide for the lake; (2) a direct lake gauge with a known datum; (3) a nearby-gauge proxy (trend only; never a pool, guide, percentile or band); (4) history-derived baselines, by tier (`historicalTier`); (5) unreviewed candidate bindings (never published as reviewed). A fallback reading is flagged, never presented as the primary source.

## 12. CANONICALIZATION
Bindings become canonical only through the acceptance gate (integration contract §5.3: Michael's sampled review → `jobs/lake-brain/data/accepted_batch.json` → `scripts/generate-lake-bindings.py`). Presence releases are canonical only as versioned private bundles validated by this repository. Rules and baselines change only by a versioned rules release with a pre-registration.

## 13. VALIDATION
Exists: Swift tests (`tests/swift/`, target `LakeBrainTests`, including the write-set fixture test), the rules-v2 pre-registered hold-out (ran once: H-A, H-B, H-D passed, **H-C failed**, not re-tuned), the Python validation/review/ledger suites in `jobs/lake-brain/`, and the prospective prediction ledger. **Not validated:** the Brain as a whole (`/validation/lake-brain` = `NOT_VALIDATED`); a passing hold-out alone would not change that (`LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`). Architecture certification is separate and never implies validation.

## 14. PUBLISHING
Direct ownership-checked RTDB writes: per lake one atomic multi-path update; then registry, validation, health, sources, activity. Freshness: `freshUntil` = observation + cadence + lag; stale after `lag + 3 × cadence`, last value kept and flagged, no silent substitution; registry `staleAfterHours` 3. Execution: Cloud Run job `lake-brain` (`deploy/deploy-job.sh`, `--scope pilots`), started by the Brain Orchestrator when due, and daily by the hand-created scheduler `lake-brain-ledger-daily` (VALIDATION_EXCEPTION; no repository script creates it). `customerIntegrationMode`: none. **Fallback reporting** (PL-03): a fallback reading is published as degraded but usable — `sourceFallback` names the primary, its last reading and error, and the source actually used with its own capability — with the flags kept and run health `WARNING`; the readiness ladder is unchanged.

## 15. PATH OWNERSHIP
The families in §4, enforced client-side by `ownership.py` and Swift `BrainOwnership`. Lake never writes another Brain's slot, a whole `/lakes/{k}`, `/lakeFleet/{k}` or `/snapshots/{k}/latest` node, or `/schemaVersion`. The Publisher registry registers Lake in SHADOW (`lake-state-v1`, `lake-registry-v1`, `lake-source-registry-v1`); it writes nothing in production.

## 16. SCORING
Score type `ENGINE_READINESS_SCORE` at `/scores/lake-brain`, computed only by the platform scorer (`scoring.py`, rubric id `lake-brain-score-v1`; caps for coverage, validation and health). Certification, migration and documentation never move it.

## 17. COST RULES
Pilot scope by default (`--scope pilots`, 1 vCPU / 1 GiB, 15 min). The ledger scheduler is a cost-capped validation exception (`maxMonthlyUsd` 1; stop condition in `control_manifest.json`). Cost-freeze rules in `docs/brains/platform/cost-freeze/` apply; no new scheduled cloud work without approval.

## 18. SECURITY
This repository is public: no secrets, service-account keys, IAM detail, private bucket contents, presence data or binding research in Git. **Per-lake species presence is never committed** — it lives only in the private bucket and reaches RTDB through the validated bundle. Writer identity `brain-writer`; its IAM breadth is an open platform item. Some `jobs/lake-brain/` research tools default to developer-machine paths (env-overridable in part); they are tooling, not runtime.

## 19. SESSION CLOSEOUT FORMAT
Every Lake session closes with: gap addressed; bowfisher decision affected; evidence (references, hashes; private items by location only); files changed; tests run with PASS/FAIL/NOT_RUN; score before/after (equal unless an approved scoring change); open gaps; human/field validation needed; confirmation of what was not changed (live systems, schedulers, bindings, validation status, science).
