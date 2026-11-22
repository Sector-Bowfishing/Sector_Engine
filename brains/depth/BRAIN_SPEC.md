# BRAIN_SPEC - Depth Brain

Canonical specification in the Sector Brain Model v1 shape. Status 2026-10-14. Companion docs live in `docs/brains/depth/` (state contract, evidence policy, datum audit, validation, readiness). This file is the short authoritative summary; it does not restate research.

| Field | Value |
|---|---|
| **Brain ID** | `depth` (platform slot `depth`, snapshot field `depth`) |
| **Lifecycle** | **SHADOW** (registry `status: PROFILED`, `shadow: true`, pilot scope: 5 lakes). Not PRODUCTION; no customer exposure |
| **Mission** | Tell a bowfisher how far the water has moved from its reference pool, and what that does to depth Sector has real evidence for |
| **Bowfishing decision improved** | "Is the flat I fish still shootable tonight?": WHEN to go and WHICH area is better as the lake rises/falls; how confident Sector is |
| **Owns** | reference-pool and datum relationship records; the level shift; effective depth of *known* depth evidence; shallow-zone bounds (survey-verified lakes); dry/flooded bounds; depth-evidence tier, provenance, uncertainty |
| **Does NOT own** | the lake level itself or datum stamping (Lake Brain); fish depth preference (Biological); vegetation; clarity; wind; synthesis (Intelligence). Bathymetry, absolute depth, flats, channels, drop-offs: not a Depth product (GLOBathy and slope-derived depth are forbidden) |
| **Upstream** | Lake Brain `states/lake` (level, datum, observation time, source capability, freshness); engine directory (reference pool, basis, confidence); operator/agency documents (datum, survey pool) via the committed manifest; authoritative contours (derived shares only) |
| **Downstream** | Sector Intelligence (restates, never recomputes: `DEPTH_INTELLIGENCE_CONTRACT.md`); Water Temp / Clarity / Vegetation interface contracts (`DEPTH_CROSS_BRAIN_CONTRACTS.md`); Ops (cached control state) |

## MISSION LOCK (product approval required to change)
Depth = **known depth evidence + current water-level shift + effective shallow-water implications + dry/flooded bounds + confidence/provenance.** Depth is NOT a hydrographic survey, complete bathymetry, a channel mapper, a ledge mapper or a structure finder. A later session may not widen this scope without product approval (the claim `absoluteDepthFlatsChannels` stays NOT_CLAIMED; GLOBathy and slope-derived depth stay forbidden).

## WAIT STATE and wake conditions (2026-10-14)
> **Update 2026-10-14 (long-run campaign):** the wait state was interrupted by a capability campaign (Duke, Reclamation, Cheney, rating-derived shares, score v2 design; `docs/brains/depth/DEPTH_CAMPAIGN_FINDINGS.md`). Wake conditions A (Reclamation) and C (Duke) are largely answered from public data; the remaining Reclamation list is narrowed in `DEPTH_RECLAMATION_DATUM_REQUEST.md`.

Depth is SHADOW, dependency-driven, field-ready. Pilot states are a **point-in-time snapshot** (see `freshness.generatedAt`): with no cron by design they refresh only on a manual pilot-scope run, or by the shared orchestrator once approved. Do nothing while waiting. Resume only on: (A) Reclamation reply, (B) TVA reply, (C) Duke or other datum confirmation, (D) Lake publishes more fleet states, (E) Lake fixes NWPS bindings, (F) field/sonar observations, (G) authorization to deploy the control job, (H) a shared Brain Model/scoring decision on the rubric mismatch, (I) a licensing decision that unlocks contour sources. On a wake: promote confirmed rules through `proposals`, `refresh`, `report --log`, regenerate docs, re-run tests, push. Details: `docs/brains/depth/DEPTH_BRAIN_MODEL_INPUTS.md`.

## Claims (Level 1 / 2 / 3) and claim-level maturity
Machine-readable: `depth_brain/data/claim_levels.json` (published as `claims` in `/brains/depth`).

| Claim | Level | Status |
|---|---|---|
| Current lake level (from Lake) | 1 | PROVIDER_VERIFIED (5 pilots equal operator feeds) |
| Reference pool figure | 1 | PROVIDER_VERIFIED (353 lakes with high/medium pool) |
| Datum relationship | 2 | VERIFIED (counts computed in the registry, e.g. 208 at 2026-10-14), inferred operator system (17 TVA), else UNKNOWN |
| Level shift | 2 | VERIFIED (formula, sign, edges, inputs) |
| Shift uncertainty | 2 | ESTIMATED (research estimates, flagged) |
| Contour shallow-band shares | 2 | VERIFIED (vs exact TWDB tables) |
| Effective dry/shallow bounds | 2 | DESK_VALIDATED on 5 TWDB lakes; WITHHELD for other contour lakes (preregistered validation failed) |
| Depth shares from an operator elevation-area rating / survey table (+ flooded-margin share) | 2 | VERIFIED as a derivation (RATING-ZONE-RULES-1); 91 lakes; shares only, never where; reported share tolerance 0.11 |
| A known flat is DRY/TOO_SHALLOW/SHOOTABLE/GOOD/DEEP | 3 | NOT_VALIDATED (field preregistered, no data) |
| Absolute depth / flats / channels | 3 | NOT_CLAIMED |
A failed Level-3 claim never downgrades Level-1/2 claims (tested).

## Canonical runtime state
`/lakes/{k}/states/depth` (DepthState v1): `kind`, `effectiveDepth{mode, shiftFt, uncertaintyFt, confidence, resolvable, reasons}`, `reference`, `level`, `coverage`, optional `referenceZones`/`effectiveZones`, `limitations`, `freshness`, `provenance{..., inputFingerprint, datumEvidence, licence}`. About 3 KB per lake. Downstream never reads research archives, raw contours, or validation corpora. Contract: `docs/brains/depth/DEPTH_STATE_CONTRACT.md`.

## Reference bases (changed 2026-11-22)
Change note: owner decision, Michael, 2026-11-22 (chat 06:48Z; recorded on Sector_Ops #51, comment 7075545102). (1) A **same-series** reference is allowed for natural lakes and stage-only gauges. (2) The **Great Lakes Low Water Datum (IGLD 1985)** is an allowed reference. Approving a Depth knowledge release that uses them stays with Michael; this change only adds the rules.

`reference.basis` (state: `reference.referencePoolBasis`) is one of `contract.REFERENCE_BASES`:
| Basis | Reference | `shiftFt` means | Datum status |
|---|---|---|---|
| `fullPool` | directory full pool, datum proven compatible with the level | how far the lake is from full pool | SAME_SOURCE / SAME_OPERATOR_SYSTEM / SAME_DATUM / CONVERTED |
| `lowWaterDatum` | Great Lakes Low Water Datum, IGLD 1985 (`research/tools/depth_research/records/great_lakes_lwd.json`: NOAA CO-OPS and CHS, paraphrased) | how far the water is above chart datum: charted depths are deeper by `shiftFt` | SAME_DATUM (IGLD85 level and reference) |
| `seriesMedian` | the level gauge's own median for this day of year: Lake Brain `seasonalBand.p50`, a +/-7-day window (15 days) over the gauge's complete basis years | a **level fact only**: how far the lake is above/below its usual level for this time of year. Never applied to charted or contour depths | SAME_SERIES (one gauge, no datum needed) |

Population. A lake keeps `fullPool` whenever that route is usable; existing datum-verified lakes are unchanged (golden fixtures pinned). The new bases apply only to lakes with a verified direct level binding whose every blocked reason is on the reference side (`REFERENCE_NOT_A_POOL_ELEVATION`, `REFERENCE_POOL_CONFIDENCE_LOW`, `MISSING_REFERENCE_POOL`, `DATUM_UNKNOWN`); level-side failures, known-but-different datums and Duke's scale get no substitute.
- `lowWaterDatum`: the 14 Great Lakes lake ids in the LWD record, when the research level is the NOAA CO-OPS `water_level_IGLD85` series. At run time the Lake reading must itself be stamped IGLD 1985 (`LEVEL_DATUM_NOT_IGLD85` otherwise, including unstamped). **Today none of the 14 has a Lake binding (Lake binds no coops provider), so at run time all 14 are unavailable until Lake has a coops binding whose readings are stamped IGLD85.**
- `seriesMedian`: only where Lake's binding (`jobs/lake-brain/data/bindings.proposed.v1.json` plus Lake's five hand-written pilots) has exactly ONE history source that is the same series as its primary live source with the same offset (usgs: same site and parameter; nwps/hads: same lid, HP; cwms/a2w: same office, CWMS location and parameter). Otherwise blocked `SERIES_HISTORY_NOT_LIVE_SERIES` (lakes Lake does not bind are blocked this way). It also needs at least 10 complete years in the manifest (`SERIES_HISTORY_TOO_SHORT`). Reservoirs whose directory basis is fullPool (stage-only or per-site gauges) are included only while `contract.SERIES_MEDIAN_ALLOW_FULL_POOL_RESERVOIRS` is True (default True pending Michael's answer on Sector_Ops #51; False blocks them `SERIES_MEDIAN_FULL_POOL_RESERVOIR_OFF`). **On the committed release (2026-10-14.6) all 19 lakes that pass are directory full-pool reservoirs and depend on that switch: natural lakes unlock zero today** (they have no Lake binding, or their Lake history is not their live series). At run time: a Lake band with `basisYears` >= 10, `windowDays` 7 and `sampleCount` >= 100 from the primary series (`SERIES_MEDIAN_UNAVAILABLE`, `SERIES_HISTORY_TOO_SHORT`, `SERIES_MEDIAN_WINDOW_MISMATCH`, `SERIES_MEDIAN_TOO_FEW_SAMPLES`, `SERIES_LEVEL_FROM_FALLBACK_SOURCE`).

Both new bases: no cross-check against Lake's `differenceFromNormalPoolFt` (that is from full pool), no relative-scale frame, no reference or effective zones (zones are defined at full pool; manifest `referenceZonesWithheld: REFERENCE_NOT_FULL_POOL`), rollout and `effectiveDepth.confidence` capped at MEDIUM. Sigma: LWD reference 0.25 ft (`high`, component `pool`); median reference 0.25 ft (assumed, component `reference`); datum SAME_SERIES 0. A `fullPool` state keeps its v1 shape; a new-basis state adds `effectiveDepth.referenceBasis`/`referenceFt`, `reference.referenceMeaning` and, for the median, `reference.seriesMedian`. The Depth version is bumped with the next knowledge release.

## Confidence model, refusal policy, freshness
Sigma in quadrature (pool 0.25/1.0/3.0, level 0.1/0.15, datum 0/0.1/0.3 ft); labels HIGH <= 0.5, MEDIUM <= 1.2 ft; `resolvable` = |shift| > 2 sigma. Refuses (UNKNOWN with reason codes, never a number): datum unknown/incompatible/conflicting, no direct level, low-confidence or non-pool reference, implausible shift, stale/future observation, missing Lake state. Level age > 6 h = `evidenceStale`; > 48 h = unavailable.

## Execution model
| Question | Answer |
|---|---|
| What makes Depth change? | A new Lake Brain observation; a reference/datum record; the committed manifest; the Depth version |
| When run? | When the input fingerprint changes (`run.py --plan` -> PUBLISH) |
| When skip? | Fingerprint unchanged -> no work (live-verified) |
| Needs a clock? | **No.** Time-driven invalidity is handled by Lake freshness; no maintenance schedule needed |
| Max acceptable state age | evidenceStale 6 h, unavailable 48 h (of the Lake observation) |
| Fleet recompute? | No: pilot scope, only affected lakes; the manifest is rebuilt offline when evidence changes |
| Input fingerprint | Lake observationTime + elevation + kind + capability, reference pool, datum status, manifest version, Depth version (+ Lake `seasonalBand` and `sourceFallback` for a `seriesMedian` reference) |
Frames: Duke publishes some lakes on a 100-based scale (`reference.relativeScalePoolFt`), the engine accepts either frame and refuses a level that is in neither. Orchestration is PREPARED and gated off (`DEPTH_ORCHESTRATION_ENABLED=1`, set nowhere); not approved for scheduling.

## Score dimensions (research rubric; NOT an official score)
authority, coverage (computed), absolute*, relative*, effective, validation*, provenance, scalability. `*` = rubric mismatch documented in `DEPTH_RUBRIC_MISMATCH_PROPOSAL.md` (rubric unchanged, awaiting Michael). Proposed official design: `depth-brain-score-v2` (unratified; `DEPTH_OFFICIAL_SCORE_DECISION.md`); critical dimensions datumCorrectness, fleetCoverage, derivationValidity, interpretationValidity. Official score: NOT_ESTABLISHED. Production gate (unchanged): overall >= 8.0 and every critical >= 7.5.

## Validation requirements by claim level
L1: source/freshness/units/provenance (done for the pilots). L2: formula/inputs/uncertainty/edge cases/determinism (done; preregistered desk validation for zone bounds on 5 lakes). L3: independent/field/prospective (preregistered thresholds `field_validation_prereg.json`, sha256 pinned; not run).

## Production requirements (all outstanding unless stated)
Lake fleet states live for the target lakes; field validation pass; operator datum confirmations where inferred; control-plane entry live; Ops page; orchestration approved and clean for two cycles; licensing for any contour-derived customer number; Michael decision on score-v1.

## Storage budget
Research directory 1.4 GB (review thresholds 5 GB / 2 GB single dataset not reached); recipe (manifest inputs, ledgers, rebuild pointers) in Git; bulk deleted. `DEPTH_STORAGE_REVIEW.md`.

## Research stop conditions
No open-ended campaigns. A datum question gets two passes (CWMS/API/docs); a third only if it changes a Sector-derived (Level 3) claim. Contours: only what the survey interval supports. No modeled bathymetry, ever. Unknown is an accepted answer.

## Ops summary and customer exposure
Engine-computed summary in `/brains/depth` (fleet counts, research maturity with `official:false`, `scoreStatus`, claims, lifecycle, execution, blockers); control-plane code `SHADOW_BRAINS` excludes Depth from every roll-up. Ops shows nothing yet (catalog `future`; `DEPTH_OPS_FOLLOWUP.md`). **Customer exposure: none** (no API, app, map layer, or Conditions Score input).

## Cost and runtime expectations
Full-fleet analysis 2.7 s including reads; compute 0.02 s; ~43 MB; ~3 KB per lake; no new provider feed; reads only Brain RTDB. Runtime does not depend on large data: the 941 KB manifest is the largest input. Nothing in the Engine request path imports Depth (test).
