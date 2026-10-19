# Water Clarity Brain — Structural Certification Report V1 (Brain #3)

**Date:** 2026-10-18 · **Branch:** `cert/water-clarity-architecture-v1` (merged with `origin/main` `4ff9bed0`, D4 complete) · **Procedure:** `audit-1/BRAIN_FACTORY_V1.md` + `BRAIN_FACTORY_CHECKLIST_V1.md`, followed in order.
**Status: `WATER_CLARITY_STRUCTURALLY_CERTIFIED_V1_READY_FOR_REVIEW`** — all structural proofs of Factory §8 pass **in SHADOW**. This is **not** `ARCHITECTURE_CERTIFIED_V1`, **not** production-ready, **not** scientific validation and **not** a promotion: lifecycle stays `CALIBRATION`, `cutoverStatus` stays `SHADOW`, the customer number stays `NOT_VALIDATED`, the research score stays 8.0 → 8.0. Nothing was deployed, scheduled, published or written to production.

## 1. Scope
Certification applies to **C1**, the Water Clarity Brain publisher (`brainId` **`water-clarity`**, unchanged), now at `brains/water-clarity/`. C2 (lake-surface / dispatch / hydrology), C3 (ClarityPrecompute), C4 (candidate shadow) and C5 (production Engine clarity) remain separate runtime producers / transitional components; their provenance is the merged D4 record. The raw `brain/water-clarity` branch and the research corpus stay private; the baseline is the public-safe v1.1.0 that was already on main, plus the private catalog overlay mechanism (never exercised with real private data here: tests use a synthetic overlay).

## 2. What was done, by Factory phase
| Phase | Result | Evidence |
|---|---|---|
| 0 Baseline + gap audit | branch brought forward by a normal merge of `origin/main` `4ff9bed0` into the existing certification branch (`691c6ce2`; gap-audit commits kept, nothing recreated); score and architecture baselines recorded | `CLARITY_GAP_AUDIT_V1.md`; §5 |
| 1 Canonical location | `git mv` (history preserved) of `clarity_brain.py`, `run.py`, `brain_platform.py`, `catalog.json` → `brains/water-clarity/runtime/`; tests → `tests/`; deploy files → `deploy/`; `jobs/water-clarity-brain/` = retirement pointer README only; ONE implementation (tree-wide test) | `test_exactly_one_production_clarity_implementation` |
| 2 `brain.json` | validates `brain.schema.json`; lifecycle `CALIBRATION` (== control manifest == artifact lineage); `consumes` = Lake Registry only; `providers` = none; signals none; `authorizedConsumers` = ops, sector-intelligence (both verified readers); `customerIntegrationMode` none; `publisherRequired` SHADOW | `brain.json` |
| 2b Real dependencies | `contracts/INPUTS_V1.json` is the code-derived input truth, pinned by an AST test; Engine `/conditions` and `/lakes` are recorded as **RA-20 ownership debt**, not blessed | §4 |
| 3 Operating contract | 19 sections; says what C1 owns / does not own, inputs, outputs, freshness, fail-closed behaviour, unknown semantics, no customer promise beyond current truth | `BRAIN_OPERATING_CONTRACT.md` |
| 3b Artifact | `runtime/publish_artifact.py` builds ONE `clarity-publication-v1` bundle (3 sections) from the real write set; pure; deterministic; volatile contract `clarity-volatile-v1` | `CLARITY_PUBLISH_ARTIFACT_CONTRACT.md` |
| 3c Lineage | `ConsumptionRecorder` attached to the RTDB client; `consumed` absent when unknown; HTTP/GCS reads never faked | §4 |
| 4 Health / freshness / Publisher shadow | healthV1 renders Clarity generically (zero Clarity code, no Ops change; UNKNOWN stays UNKNOWN); freshness keeps scene / Engine-evaluation / Brain / publication times apart; Publisher registration is data-only (`registry.py`) → `SHADOW_READY`, `live_mutations == 0`, re-publish `SKIP` | tests §6 |
| 5 Direct writes | every write door classified; two C1 RTDB sites pinned (LEGACY / RETIREMENT_CANDIDATE); artifact path writes nothing; GCS writes recorded as platform debt | `CLARITY_DIRECT_WRITE_AUDIT.md` |
| 6 Research / science | research dir = rules + `GAPS.json` only; runtime works with no workspace, HOME or docs (staged-layout test); science golden from the **pre-move tree** matches byte-for-byte | tests |
| 7 Score / gates | 8.0 → 8.0 (block hash identical); architecture NEW 0 | `CLARITY_SCORE_RECONCILIATION.md`; §5 |

## 3. The 21 mandatory proofs (Factory §7) → tests (`brains/water-clarity/tests/test_clarity_certification.py`)
1 location & single implementation · 2 `brain.json` valid, id stable, lifecycle drift hand-gate · 3 ownership in contract + contract derived from registry (`describe_contract.py --check`) · 4 declared dependencies == what the runtime really reads (AST-pinned; RA-20 flagged) · 5 no fabricated signals/providers/edges · 6 artifact valid + deterministic · 7 fingerprint ignores execution identity/run-clock fields; a real change changes it; unchanged republish → SKIP · 8 lineage complete, never fabricated (`knowledgeRelease` NONE, `consumed` absent) · 9 consumption capture works for RTDB reads; HTTP/GCS not faked · 10 healthV1 representable; UNKNOWN honest; no freshness from `lastSuccessfulRun` · 11 Publisher accepts SHADOW and rejects wrong brain/schema/path/lifecycle/freshness · 12 typed deletes only, null ≠ delete, no lake-state delete · 13 every emitted child covered; unmapped paths fail closed · 14 **AST-pinned direct-write set** (== audit table) · 15 the artifact path cannot write (pure builder; dry run touches no database) · 16 no Mac/research/cache paths; staged-layout run with empty HOME and no docs/ · 17 research separate from the package · 18 no private research/agency material in the public package · 19 **science preserved** (golden from the pre-move tree, `catalog.json` identical to main's) · 20 registered-Brain architecture gates, no NEW violations · 21 score BEFORE = AFTER. Plus: engine-miss path (stale carry, error children) is owned and Publisher-valid.

## 4. Dependencies, ownership caveats, lineage
- **Declared (`brain.json`):** Lake Registry (`registry.lakes`, REQUIRED). **Caveat:** C1 reads the lake directory through the **customer Engine `/lakes` endpoint**; no registry contract version is actually read (RA-20).
- **Read but not declarable as an edge:** Engine `/conditions` per lake (RA-20: the customer Engine computes the number; **not a legitimate long-term dependency**, recorded not blessed); C2's GCS outputs (own pipeline); C2 run records and the Engine revision label (operational metadata); catalog + optional private overlay (own model); lake outlines (static).
- **Providers: none** (Sentinel-2 L2A, USGS NWIS, MRMS reach C1 through the Engine and C2; C1 only publishes health records for the sources it owns). **Signals: none. Brains: none.**
- **Lineage:** RTDB reads are recorded (`consumedRtdbReads` in the run report). GCS/HTTP reads have no supported-read model: `consumed` is absent, no fingerprints or state versions were invented (**GCS_HTTP_LINEAGE_PLATFORM_DEBT**, accepted after D4; it did not block any factory gate).
- **healthV1:** `dependencies.declared 1`, `registry:lakes` UNKNOWN ("not observed by the Engine"), `freshness` UNKNOWN, aggregate UNKNOWN — the correct and expected reading until the platform observes the Lake Registry (same shape as Wind).

## 5. Gate results (all offline, local; CI will re-run)
| Gate | Result |
|---|---|
| `brains/water-clarity` pytest | **87 passed** (35 pre-existing + 52 certification) |
| `jobs/brain_platform` | 524 passed (two tests updated for the third registered Brain) |
| `jobs/brain-orchestrator` / `jobs/brain-scores` | 36 / 21 passed |
| `brains/fish` | 285 passed, 2 skipped |
| `brains/wind` | 108 passed; 2 failures are environmental (`shapely` not importable in the scratch venv) and **identical on untouched main** |
| `tools/architecture` | 84 passed (registered-Brain list updated) |
| `verification` / Wind package gates | 17 / 9 passed |
| Sector Intelligence, lake-surface-dispatch, water-temp-tva-archive, lake-brain (bindings, ledger, validation, review) | 33 / 11 / 14 / 13 / 23 / 70 / 24 passed |
| `report.py --legacy --baseline` | KNOWN **20**, NEW **0**, RESOLVED **0** (was KNOWN 21: the `jobs/water-clarity-brain/brain_platform.py` entry retired because the relocated shim has no `docs/` string constant; the `clarity_brain.py` entry carried to `brains/water-clarity/runtime`) |
| `score_baseline.py --check` | OK: water-clarity=8.0/10 |
| `describe_contract.py --check` | matches the Publisher registry |
| Swift | not touched by this branch (no Swift file changed vs main); D4 already verified the Clarity Swift suite |

## 6. Platform changes (Lane B is the only lane allowed to edit shared files); "would Brain #4 reuse it?"
| Change | Generic? |
|---|---|
| `publisher/registry.py`: `clarity_specs()/clarity_bundles()` + `default_registry()`; `publisher/__init__.py` export | data only, same shape as Wind/Fish — **yes** (registration data), validator/planner/path code untouched |
| `tools/architecture/baseline`, `ownership_map.json` | the standard per-Brain move bookkeeping — yes |
| `.github/workflows/python-jobs-tests.yml` | Clarity leaves the legacy list; the `registered-brains` loop picks it up — yes |
| `test_foundation.py`, `test_dependency_declarations.py`, `test_publisher_fish_registration.py` | the registered-Brain lists those tests pin (edited per Brain, as for Fish) |
| nothing else: no change to ownership.py, keys.py, scoring.py, jobs.py, control_manifest.json (confirmed present and consistent) | — |

## 7. Hack budget (target: UNNECESSARY_HACK = 0 → **0**)
| Item | Class |
|---|---|
| `PLATFORM.contract = 'docs/brains/…'` published label (inv 8, carried baseline entry) | TEMPORARY_REPOSITORY_MIGRATION (changing it changes published output; retire at cutover with approval) |
| Per-Brain legacy-path classification kept as data in `publish_artifact.NOT_AUTHORED` (compat.py is Wind-named, D-11) | PLATFORM_GAP |
| Certification suite, `describe_contract.py`, `clarity_support.py` copied from Fish's shape (third copy) | PLATFORM_GAP (D-7b: **extract the parametrised kit now — this was the rule-of-three trigger**) |
| Registration hand-edits (registry, bookkeeping, 3 pinned test lists) | PLATFORM_GAP (D-7) |
| Lifecycle consistency checked by a test, not a generic gate | PLATFORM_GAP (D-9) |
| `run.py` keeps the dormant `job_health()` helper (uncalled, AST-pinned as uncalled); no code was deleted in a structural pass | LEGITIMATE_DOMAIN_SPECIFIC |
| Public catalog carries the PRIVATE REFERENCE (a private store path) — already public on main by the earlier sanitization decision | LEGITIMATE_DOMAIN_SPECIFIC |

## 8. Structural / platform gaps and escalations (none blocks `STRUCTURALLY_CERTIFIED_V1`)
1. **GCS/HTTP supported-read lineage** — recorder covers RTDB only (`GCS_HTTP_LINEAGE_PLATFORM_DEBT`).
2. **GCS write semantics vs Publisher** — C2–C4 write storage outside the RTDB-only path families (`GCS_WRITE_SEMANTICS_PLATFORM_DEBT`); not changed.
3. **RA-20** — `/conditions` and `/lakes` through the customer API; replace with Lake Registry / provider / own-model contracts in the Clarity phase.
4. **Cutover precondition** — the legacy writer replaces the whole `/brains/water-clarity` node, which would erase Publisher-owned `publication`/`certification`; the legacy writer must retire at Publisher production mode (inv 10 enforces).
5. **Orchestrator** — Clarity stays `MANUAL by decision`; the control-manifest `executionTarget` describes C2, not C1, so the Orchestrator cannot run C1 from the registry.
6. **Snapshot projection readers** — Sector Intelligence verified; Ops unverified (retirement gate keeps the full proof).
7. **Evidence freshness for gauge-driven lakes stays UNKNOWN** (`CLARITY-EVI-001`): the Engine payload has no reading time.
8. D-7 / D-7b / D-9 / D-11 platform debt as above; D-12 vocabulary adopted (`STRUCTURALLY_CERTIFIED_V1`).
9. Admin follow-up (not a blocker, not done here): GitHub Support purge request for the previously exposed branches.

## 9. What this certification explicitly does NOT mean
The clarity science is correct or validated; the customer number is usable; production-ready; the Brain cannot write production (the legacy door still exists, classified); rules/IAM write-denial (exit evidence F); the Publisher is live; the Orchestrator can run it; the deployed C2/C3 images were rebuilt from main; the research score reflects architecture. `ARCHITECTURE_CERTIFIED_V1` additionally needs a live Publisher, tested write-denial, reader migration and a rollback exercise.

## 10. Public/private safety
No research corpus, private catalog detail, certification thresholds/populations, agency request material, private bucket contents or raw logs were added (`test_no_private_research_or_agency_material_in_the_public_package…`); the only private identifier in the package is the status-level private **reference** already public on main. The science golden and every test use the synthetic overlay.
