# Depth vs Sector Brain Model v1: conformity pass (one pass; no research restarted)

Spec: `jobs/depth-brain/BRAIN_SPEC.md`. Claim levels: `depth_brain/data/claim_levels.json`.

| Model requirement | Depth | Gap / action |
|---|---|---|
| Brain improves a real bowfishing decision (sec 1) | PASS | "is the flat still shootable tonight / how far has the water moved" |
| Standard claim model L1/L2/L3 (2) | PASS | classified; machine-readable and published |
| Validation scaled to claim (3) | PASS | L1 provider check done; L2 tests + preregistered desk validation; L3 field preregistered, not run; an L3 failure cannot downgrade L1/L2 (tested) |
| Claim-level maturity (4) | PASS | `claims` in `/brains/depth` and the control summary |
| Owns / does not own / upstream / downstream (5) | PASS | BRAIN_SPEC |
| Canonical small runtime state (6, 7) | PASS | ~3 KB per lake; no research artifact is a runtime input (largest runtime input: 941 KB manifest) |
| Research question requirement (8), escalation ladder (9) | PASS | two datum passes, third only for an L3 claim; closed topics stay closed (GLOBathy) |
| UNKNOWN is a feature (10) | PASS | refusals carry reason codes; non-defensible lakes stay UNKNOWN (423) |
| Score -> work -> rescore (11), no score chasing (12) | PASS | `report --log` with anti-gaming check; thresholds/rubric untouched |
| Rubric audit (13) | DONE | `DEPTH_RUBRIC_MISMATCH_PROPOSAL.md` (absolute, relative, validation); not applied |
| Dimension exhaustion matrix (14) | DONE | `DEPTH_DIMENSION_EXHAUSTION_MATRIX.md` |
| Standard lifecycle (15) | PASS | `lifecycle: SHADOW`; no custom lifecycle |
| Production gate (16) | unchanged | 8.0 overall + every critical >= 7.5 |
| Research score vs official score (17) | PASS | research maturity 4.75 with `official:false`; official NOT_ESTABLISHED; score-v1 unratified; five distinct notions kept apart |
| Provider truth first (18), no duplication (19) | PASS | consumes Lake state only; no raw level fetch in the product |
| Execution model (20-24) | PASS | dependency-driven, fingerprint-first, no clock, per-lake no-op (BRAIN_SPEC) |
| Customer requests are not compute triggers (25) | PASS | tested: no Depth entry point in the Engine request path; control summary makes no network call |
| Storage as architecture (27-29) | PASS | 1.4 GB; recipe in Git; `DEPTH_STORAGE_REVIEW.md` |
| Field validation shared (30) | DOCUMENTED | compatibility needs below; no Depth-only framework built beyond the preregistered tooling |
| BRAIN_SPEC (31) | DONE | `jobs/depth-brain/BRAIN_SPEC.md` |
| Score artifact ownership (36) | PASS | Depth publishes no score; the shared orchestrator's stale-score guard is untouched |
| Ops model (37, 38) | PARTIAL | Engine fields live; control entry and Ops page pending (`DEPTH_OPS_FOLLOWUP.md`) |
| Runtime performance (40) | PASS | no unexpectedly large runtime inputs; no slow recomputation |

## What a shared field-validation trip needs from Depth (compatibility only)
One trip record (trip id, lake, UTC time, GPS, observer) should let Depth be scored without a second form: for each named flat - **observed depth (ft) and method**, **DRY/wet state**, **operator pool elevation at that hour**, and a photo. Depth supplies, from the state generated at that time: `predictedDepthFt`, `sigmaFt`, `inputFingerprint`. Class bins (DRY/TOO_SHALLOW/SHOOTABLE/GOOD/DEEP) are measurement bins, kept separate from Biological's species outcomes (encounters/shootable counts) so the same trip can score Wind (exposure/surface), Biological (encounters) and Vegetation (surface vegetation present, rough density) without conflict. The current Depth record sheet (`DEPTH_FIELD_VALIDATION_PACKETS.md` section 4) is a subset of that shape.

## Cross-Brain findings for owners (not acted on)
* **Lake:** publishes `datum: null` for TVA states (requested interface approved: `DEPTH_LAKE_DATUM_DEPENDENCY.md`); 193 defensible Depth lakes await live states.
* **Ops:** catalog marks Depth `future` with out-of-scope copy (`DEPTH_OPS_FOLLOWUP.md`).
* **Platform:** `control.py` previously excluded unknown Brains from the control plane; shadow Brains are now handled generically via `SHADOW_BRAINS` (Depth only today) - a future Brain should declare shadow status in its registry rather than needing a code edit (platform direction, sec 35).

## Observation (2026-10-14): two freshness authorities
Depth marks a level `evidenceStale` at 6 h (`LEVEL_FRESH_HOURS`), independent of Lake Brain's own `freshness.stale`. Live example: Hartwell's USGS-sourced observation was 6.0 h old, so Depth set readiness DEGRADED while Lake still treated the state as fresh (Lake knows each source's cadence; Depth does not). Not changed here (no threshold tuning to make a flag disappear). Proposal for Michael/Lake: make Lake's `freshness.stale` the staleness authority and keep Depth's age window only as a hard upper bound (48 h refusal); that removes a duplicate rule and follows "consume Lake, do not duplicate it". Needs evidence of Lake's per-source cadence before adopting.
