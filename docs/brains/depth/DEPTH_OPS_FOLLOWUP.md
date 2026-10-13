# Ops follow-up: Depth is an active SHADOW Brain, not a future bathymetry product

For the Sector Ops repo (`/Users/mcather/Desktop/Development/Web/Sector-Ops`, audited at `main` @ `12b59f7`). **Ops was not edited.** Companion: `DEPTH_OPS_VISIBILITY_GAP.md`.

## 0. What the Engine publishes now (live, verified by read-back 2026-10-14)
`/brains/depth` (status PROFILED, health HEALTHY, `shadow: true`, `scope: pilots`, `stalenessModel: FINGERPRINT`, `dependsOn: [lake-brain]`, `scoreStatus: NOT_ESTABLISHED`, no `score`, `research {maturity 4.65, official false}`, `fleet {...}`, `breakdowns`, `lakeDependency`, `orchestration`, `fieldValidation`, `primaryBlocker`, `statusBasis`, `blockers[]`, `contractVersion`), `/validation/depth` (NOT_VALIDATED), `/health/brains/depth`, and for the **5 pilot lakes only** `/lakes/{k}/states/depth`, `/snapshots/{k}/latest/depth`, `/lakeFleet/{k}/readiness|slots|modelVersions/depth`. All numbers are computed by the Engine from the candidate manifest and research-maturity inputs (never typed).

`/control/overview.brains.depth` is **not live yet**: the control builder code that adds it (`jobs/brain_platform/.../control.py`, `SHADOW_BRAINS`) is committed on `feat/depth-brain-foundation` but the scoring/control job has not been redeployed from it. Run against the live database in dry-run it produces the correct entry and changes no roll-up (worst health, conformance count, dependency completeness, work-next, per-lake stale/issue figures are identical with and without Depth). Redeploy of the control job is a separate approval.

There is no `officialScore` field: RTDB cannot store null, so an unscored Brain is represented by the **absence** of `score` plus `scoreStatus: "NOT_ESTABLISHED"`. Ops must render that explicitly ("Official score: Not yet established"), never "0" or "--".

## 1. Exact Ops changes
1. `src/lib/brainCatalog.ts`: set Depth `future: false` and add `shadow: true`; replace the copy. Current (wrong): *question* "What does the underwater structure look like?" ; *outputs* Bathymetry, Depth contours, Shallow flats, Channels, Ledges, Structural zones. New:
   - **question:** "How far has the water moved from its reference pool, and what does that do to depth we have real evidence for?"
   - **outputs:** Level shift (+/- uncertainty), Reference pool and datum, Evidence tier and coverage, Effective depth where a measured reference depth exists, Shallow-zone bounds (dry / shallow shares) where survey-verified, Provenance and licence status.
   - Remove: Bathymetry, Channels, Ledges, Structural zones. Depth never produces them, and GLOBathy / slope-derived depth is forbidden.
2. `src/pages/BrainPage.tsx`: do not return `<FutureBrain>` for Depth. Render the normal Brain page with a **SHADOW** badge ("internal, not scored, not customer-visible").
3. `src/types/brain.ts` (`ControlBrain`, and the registry entry if the page reads `/brains/depth` directly): add optional `shadow`, `scoreStatus`, `research{maturity, official, rubricVersion, criticalBelowThreshold[]}`, `fleet{...}`, `lakeDependency{liveLakeStates, defensibleShiftLakes, awaitingLakeBrain}`, `orchestration{status}`, `fieldValidation{status}`, `primaryBlocker`, `contractVersion`, `breakdowns`.
4. Overview `BrainCard`: for `shadow` Brains show **"Not scored"** (from `scoreStatus`), show `research.maturity` only as "Research maturity 4.65 / 10 (not a score)", and exclude shadow Brains from any average, ranking, "weakest/strongest", Engine-score and production-policy displays. `policyWarnings` is already safe (it only fires for lifecycle `PRODUCTION`).
5. Brain page content (all from Engine fields): Fleet funnel (pilots / high / medium / blocked of `totalLakes`), datum counts, primary blockers (`blockers[]`), validation state, Lake dependency, orchestration status, field-validation status, contract version, tier A/B contour lakes and licensed share.
6. Per-lake view: render `states/depth.effectiveDepth` as "Water is X ft below/above reference pool (+/- Y), confidence" and the `limitations`; when `kind: unavailable`, show `reasons[]` verbatim. Do not display it as a depth.
7. Registry list/Overview: Depth appears as "Shadow" (not "Coming", not dimmed).
8. Optional: show `fleet.readinessBySlot.depth` (CALIBRATION 5) in the fleet card. Do **not** add per-lake "blocked" displays for Depth (none are written by design).

## 2. Scope text to use everywhere
Depth Brain reports (1) the current water-level shift from a known reference pool, (2) effective current depth for known depth evidence, (3) shallow-zone shifts and dry/flooded bounds where survey-verified, with (4) confidence, provenance and uncertainty. It is not bathymetry, a navigation product, a flats/structure map or a score.

## 3. Cost safety (verified)
* Ops reads cached RTDB nodes only (`brainPaths.ts`: `/brains`, `/control/overview`, `/lakeFleet`, ...). It has no call into Depth; Depth has no HTTP entry point and nothing in the Engine request path imports it (test `test_ops_read_path_has_no_depth_compute_entry_point`).
* Building or reading the control summary makes no network call (test `test_building_and_reading_the_control_summary_makes_no_network_call`).
* Depth updates only when Engine truth changes: `run.py --plan` returns SKIP ("inputs unchanged") against the live database right after the write, and PUBLISH only when a Lake observation, reference/datum record, manifest or Depth version changes. No page view, no Ops open, and no fixed timer triggers it.
