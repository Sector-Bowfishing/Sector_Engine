# Depth Shift Candidate Fleet (recomputed 2026-10-13)

Source of truth: `jobs/depth-brain/depth_brain/data/candidates.json` (manifest `2026-10-13.1`, built by `python -m depth_brain build-manifest`), flat view `docs/brains/depth/data/depth_candidate_fleet.csv` (621 rows; fields: lake, operator, reference pool/datum/source, level source/provider/capability/datum, history years, datum status and sigma, shift possible, blocked reasons, rollout, depth tier, licence).

The research count of **~265** lakes (and the terrain thread's 339 "delta possible") assumed that a bound level plus a pool figure was enough. This recomputation also requires a **provable datum relationship** (`DEPTH_DATUM_AUDIT.md`), a direct level source, and a pool basis/confidence the engine accepts. Result:

## Funnel (621 directory lakes)

| Gate | Lakes | Notes |
|---|---|---|
| Directory pool is a pool elevation (`fullPool`), confidence high/medium, figure present | 353 | 207 lakes are natural surfaces / not a pool, 268 low-confidence, 13 no figure (overlapping) |
| ... and a verified Lake Brain level binding (research bindings + 5 live reviewed) | 325 | 204 lakes have no verified binding (incl. 10 stage-only) |
| ... and a **defensible datum relationship** | **92** | the 233 that fail: DATUM_UNKNOWN 224, Duke local scale 8, NGVD29/NAVD88 conversion not enabled 1 |

**Shift possible: 92 lakes** (not 265). The remaining ~230 are plausible and become possible as the datum evidence below is obtained; they are not guessed.

| Datum relationship of the 92 | Lakes | Meaning |
|---|---|---|
| SAME_SOURCE | 17 | CWMS level and pool figure share one CWMS location (exact by construction) |
| SAME_DATUM | 59 | both datums stated and equal: 58 A2W/USGS levels vs CWMS location datum (API), 1 reviewed override (Hartwell) |
| SAME_OPERATOR_SYSTEM | 16 | TVA operating-guide pool vs TVA reading; datum not named by TVA (inferred NGVD29), sigma 0.1 ft |

Verified datum count: **76** (SAME_SOURCE + SAME_DATUM). Inferred-system: 16. **Blocked datum: 233 of the 325 plausible lakes.**

## Rollout tiers (Phase 23)

| Tier | Lakes | Rule |
|---|---|---|
| PILOT_VERIFIED | 5 | live reviewed Lake Brain binding and defensible datum: Guntersville, Wheeler, Wilson, Pickwick, Hartwell |
| HIGH_CONFIDENCE | 65 | research-verified (strong) binding, high pool confidence, SAME_SOURCE / SAME_OPERATOR_SYSTEM / SAME_DATUM, >= 10 complete years of history, direct source |
| MEDIUM_CONFIDENCE | 22 | shift possible but labelled bindings (v1.1 envelope/flag), medium pool, or < 10 years |
| BLOCKED | 529 | reasons in the CSV; unknown stays unknown |

Only the 5 pilots can publish today: Lake Brain currently publishes `states/lake` for exactly those 5 lakes (reviewed bindings in `Sources/SectorEngine/LakeBrain/LakeSourceBindings.swift`). The 87 others become live when Lake Brain adopts its fleet bindings (`feat/lake-brain-adoption`, not merged); Depth then needs no change.

## Live shadow dry run (GET-only, 2026-10-13 ~19:00 UTC, nothing written)

| Lake | Depth shift | +/- | Lake Brain difference | datum relation |
|---|---|---|---|---|
| Guntersville | -1.4 ft | 0.3 | -1.4 | TVA system |
| Wheeler | -2.4 ft | 0.3 | -2.4 | TVA system |
| Wilson | -0.9 ft | 0.3 | -0.94 | TVA system |
| Pickwick | -2.9 ft | 0.3 | -2.88 | TVA system |
| Hartwell | -10.6 ft | 0.3 | -10.63 | reviewed override (USGS 00062 vs CWMS NGVD29) |

Agreement with Lake Brain is by construction (same reference), so it validates plumbing, not science.

## What is in the 92

Operators (top): TVA 15, USACE Louisville 9, USACE Little Rock 6, Alabama Power 5, USACE Tulsa 5, Vicksburg 4, Pittsburgh 4, Mobile 3. Range class where history exists: >= 4 ft operating range 64, 1.5 - 4 ft 11, < 1.5 ft 2 (15 have no operating-range statistics yet). 19 of the 92 also have tier A/B contour evidence (e.g. Texoma, Livingston, Fork, Conroe, Tawakoni, Cedar Creek, Summersville, Stonewall Jackson, Alum Creek); their contour zones remain **reference-only** (effective zones withheld until each survey's reference pool is verified).

## How the remaining ~230 unlock (datum evidence needed)

| Group | Lakes | Unlock path |
|---|---|---|
| USBR RISE levels vs USBR project pools | 45 | RISE declares no series datum; needs a Reclamation statement or a same-source series. Not guessable (EGM96 / NGVD29 / NAVD88 / project datums mixed) |
| NWS NWPS levels | 32 | datum tables empty or contradictory; needs a paired CWMS/USGS series per gauge |
| CWMS levels with non-CWMS-location pool figures | 39 | pool is a URL/doc figure with no stated datum; document the datum per project |
| A2W levels (NGVD29) with non-CWMS pool figure | 31 | pool figure datum unstated (USBR pages, "USACE pool inside TVA zone") |
| A2W LOCAL / blank project tag | 22 | LOCAL is ambiguous (Kanopolis = NGVD29, Rathbun ~ NAVD88); resolve per project against a paired USGS gauge, like the Hartwell test |
| USGS 62614 vs pool of unknown datum / 62615 NAVD88 / 00062 | 29 | pair each with a CWMS/operator series (the Hartwell method) |
| Duke (local 100-scale) | 8 | verify `shift = scale - 100` with Duke (API now returns 403) and the full-pond table |
| SRP, SJRWMD, USGS-D, CDEC, others | ~19 | per operator documents |
| NGVD29/NAVD88 conversion | 1 (Toledo Bend) | conversion disabled until its sign/convention is verified both ways (CWMS gives NAVD88 - NGVD29 = -0.32 ft at Hartwell; the research NCAT table gives -0.27) |

The datum rules are code (`depth_brain/datum.py`, `candidates.assess_candidate`) and are tested; every new determination is a data change (a provider/override record with evidence), not a code change.

## Cautions carried in the data

* Hartwell's pool (660 ft) is the **summer** top of conservation; the winter guide is 656 ft. About 4 ft of its shift in winter is the designed drawdown (`DEPTH_HARTWELL_EFFECTIVE_DEPTH.md`: a 4 ft flat is "dry" 30.7% of days against 660 but 24.6% against the operator guide and 8.0% against 656). The state carries Lake Brain's `guideFt` / `differenceFromGuideFt` beside the shift so a reader can see designed vs unusual.
* Pool-confidence `medium` lakes carry sigma >= 1.0 ft (shift rarely `resolvable`).
* Licence gating (`DEPTH_LICENSING_MATRIX.md`): contour-derived numbers are internal-only unless the source terms allow customer derived use; the manifest records the most restrictive source per lake and treats `unknown` as not allowed.
