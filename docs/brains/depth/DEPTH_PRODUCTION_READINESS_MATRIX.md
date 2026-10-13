# Depth Production Readiness Matrix (2026-10-13)

Verdict: **NOT production-ready, by design.** Depth is a shadow/internal foundation. Nothing is deployed, scheduled, registered with the orchestrator, written to the live Brain RTDB, or customer-visible. Statuses: PASS / PARTIAL / FAIL / WAITING (needs an external input) / NOT_REQUIRED.

| # | Area | Status | Evidence / gap |
|---|---|---|---|
| 1 | Brain contract | **PARTIAL** | `DEPTH_STATE_CONTRACT.md` + code + 7 golden fixtures + platform conformance (writer ownership, key rules, vocabularies). Not ratified; slot `depth` reserved in the platform contract; `jobs.py` manifest/orchestrator registration not added |
| 2 | Reference pool | **PARTIAL** | directory `fullPoolFt/poolBasis/poolConfidence`: 353 lakes usable; 207 not pool elevations, 268 low-confidence, 13 absent. Seasonal pools (Hartwell 660 summer / 656 winter) are carried only as Lake Brain `guideFt` context |
| 3 | Datum confidence | **PARTIAL** | rules in code + `DEPTH_DATUM_AUDIT.md`: 76 verified (SAME_SOURCE / SAME_DATUM), 16 inferred-system (TVA), 233 of 325 plausible lakes blocked; conversions disabled; TVA/Santee/Duke operator statements unverified; Duke local scale not enabled |
| 4 | Current level | **PARTIAL** | consumed from Lake Brain `states/lake` only (read). Live for 5 reviewed pilots; the other 87 await Lake Brain fleet-binding adoption (`feat/lake-brain-adoption`, unmerged). TVA states publish `datum: null` |
| 5 | Effective depth (shift) | **PARTIAL** | engine + 106 tests + live GET-only dry run on all 5 pilots (agrees with Lake Brain differences by construction); no field/event validation |
| 6 | Authoritative contours | **PARTIAL** | 103 tier A/B lakes in the manifest as reference shares; ingest/match pipeline exists only as research scripts; not productionised; no Southeast contours |
| 7 | Shallow zones | **PARTIAL** | reference shares at supported edges (94 lakes); `effectiveZones` implemented and tested but withheld for every lake (survey reference pool unverified) |
| 8 | Fleet coverage | **FAIL** | shift defensible for 92 of 621 (5 live); zones reference-only for 94; the rest unknown. Expected to rise as datum evidence arrives |
| 9 | Validation | **PARTIAL** | arithmetic + research evidence validation (CWMS 33, TWDB 63, Landsat 5, Hartwell pilot); `/validation/depth` = NOT_VALIDATED |
| 10 | Field truth | **WAITING** | `DEPTH_FIELD_VALIDATION_PLAN.md` (5-10 lakes); needs bowfishers / beta testers and sonar |
| 11 | Confidence | **PASS** | sigma components in quadrature, HIGH/MEDIUM/LOW labels, `resolvable`, reasons; components flagged as estimates (so: PASS for mechanics, not for calibration) |
| 12 | Provenance | **PASS** | reference source, datum assessment, level source/version, tier, research tier, fingerprint, quality flags, limitations |
| 13 | Licensing | **PARTIAL** | `DEPTH_LICENSING_MATRIX.md` (37 sources) and a manifest gate (most restrictive source wins, unknown = not allowed). 44 of 103 tier A/B lakes blocked for customer-derived use; FL internal-only; IENC "non-public" flag unresolved |
| 14 | Freshness | **PASS** | FINGERPRINT plan(); `evidenceStale` at 6 h, refusal at 48 h, future-dated observations refused; stale Lake input flagged |
| 15 | Cost | **PASS** | no new external feed; reads <= 92 Lake Brain nodes per run; computation is arithmetic; offline builder uses public APIs (CWMS locations, 94 GETs) |
| 16 | Orchestration | **FAIL** (not started) | no job, scheduler, image, deploy script, `/jobs` manifest entry or orchestrator registry; deliberately out of scope |
| 17 | Intelligence contract | **PARTIAL** | `DEPTH_INTELLIGENCE_CONTRACT.md` + fixtures + a reference consumer test; the Intelligence branch is untouched and has not adopted it |
| 18 | Water Temp contract | **PARTIAL** | interface documented (`DEPTH_CROSS_BRAIN_CONTRACTS.md`); no consumer; Water Temp branch untouched |
| 19 | Clarity contract | **PARTIAL** | same; no modeled depth permitted into Clarity |
| 20 | Vegetation contract | **PARTIAL** | same |
| 21 | Biological contract | **NOT_REQUIRED** | Biological owns preferences; no Depth interface needed beyond Intelligence |
| 22 | Rollback | **PASS** | nothing live to roll back: dry-run default, live writes need `--yes-write-shadow`; paths are depth-owned and deletable (`null` patch); no schema or shared-field change; branch unmerged |

Customer behavior: **unchanged** (no iOS/Android/Ops/API/RTDB/scheduler change; no live write performed).

## Biggest gating items for any promotion
1. Datum evidence for the ~230 plausible-but-blocked lakes and operator confirmation for TVA/Santee/Duke (2, 3, 8).
2. Field validation of effective depth (10).
3. Lake Brain adoption of fleet bindings so the 87 non-pilot lakes have a live level (4, 8).
4. Southeast bathymetry request package answered (6, 7) - `DEPTH_SOURCE_REQUEST_PACKAGE.md`.
5. A Michael decision to register, schedule and expose Depth (1, 16).
