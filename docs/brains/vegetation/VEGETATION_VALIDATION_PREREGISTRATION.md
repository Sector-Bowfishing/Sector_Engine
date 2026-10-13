# Vegetation Brain — Validation Pre-registration (v1)

**Status:** FROZEN before the adoption-cycle validation runs (committed before any scoring in the cycle that produced this file). Changes after a scoring run must be added as a dated **amendment** at the bottom, never by editing the gates. Research basis: branch `docs/vegetation-brain-research` @ `f6772a1d` (`docs/research/vegetation-brain/`).

Scope: **surface-reaching aquatic vegetation** only (floating-leaved, floating mats, emergent belts, surface-topped canopy). **Submerged vegetation is out of scope for observation** and cannot be validated into an "observed" state by anything in this document.

## 1. Observer candidates (defined before scoring)

| Id | Name | Definition |
|---|---|---|
| **S** | single pass | Nearest clear scene (≥75 % of lake cells seen) to the reference date; cell vote only |
| **A** | accepted pass | Clarity-style pass acceptance: the nearest-to-reference scene that **reads ≥ 50 % of the non-plant lake water** (fallback: best coverage ≥ 25 %, else UNKNOWN). One noisy pixel never makes a cell vegetation: a cell needs `plantFraction ≥ 0.5` of its seen 10 m pixels |
| **P** | persistence | Per-cell **median** over accepted clear scenes within ±21 d of the reference date, requiring **≥ 3 accepted scenes**; `plantFraction_median ≥ 0.5`. With fewer than 3 accepted scenes the cell is evaluated as **A** and carries `persistence: INSUFFICIENT` |
| (excluded) | max / second-highest / votes ≥ 2 of N | Research showed these are weak filters (precision 0.21–0.40); **max composites are forbidden** in V1. They may be run only as a documented negative control |

Plant pixel rule (the unit under test, taken from production `derive_water_surface.py`): `NDVI(B8A,B4) ≥ 0.30` on a pixel that is not cloud/shadow/cirrus/snow/no-data (SCL) and not inside the cloud, haze, structure standoffs. Guards that make a cell **UNKNOWN** rather than "no vegetation": insufficient valid pixels (<50 % of the cell seen), cloud/shadow/haze standoff, dark water with unstable ratio (red and B8A both < 0.01 → pixel excluded, cell UNKNOWN if >50 % excluded), glare (SWIR/B8A pattern or Wind disturbance flag when available), shoreline band (cells within 1 pixel of the polygon edge are `SHORE_ADJACENT` and excluded from presence claims), scene–reference gap > 21 d.

## 2. Metrics (all pre-specified)

1. **Shore-distance matching is mandatory.** Negatives are re-weighted to the positives' distance-to-shore histogram (bins 0/15/30/45/60/90/150/300 m). Unmatched AUC is reported only as a warning, never as a result.
2. Cell metrics at the production 50 m cell: precision, recall, F1, IoU, balanced accuracy, and open-water false-positive rate (flagged cells ÷ verified-open-water cells).
3. **Presence-only truth (FWC points, NAS, EDDMapS)** supports recall only; precision/FPR are never computed from it.
4. **Leave-one-lake-out** for any tuned threshold; report per lake and pooled; confidence intervals by bootstrap over **lakes** (not pixels), 2,000 resamples.
5. Survey–image gap ≤ 7 d for headline numbers; 8–30 d reported separately.
6. Negative controls: lakes with NLA 2017 emergent = floating = 0 at **every** station (set built from the data, not from memory) must show lake-level flagged share ≤ 2 %.

## 3. Ground-truth sets and what each may validate

| Set | May validate | Notes |
|---|---|---|
| Snohomish WA dated polygons (5 lakes) | cell presence P/R/F1/IoU, floating-leaf, LOLO | absence is assumed outside mapped beds |
| FWC LTM points (≤10 fleet lakes) | recall only | presence-only |
| FWC LTM lake PAC/PVI sonar | lake-level rank agreement, high/low discrimination | lake-level volume ≠ pixel presence |
| EPA NLA 2017 phab (fleet-joined lakes) | lake-level class/cover agreement; negative controls | shoreline stations; method fixed in §4 |
| USGS UMR LTRM CSV / UMRS 2020 polygons | system-specific presence recall/agreement | turbid river pools; not pooled with clear lakes |
| UMN Minnesota (when acquired) | recall by lake | not yet in hand |

## 4. NLA × Sentinel-2 protocol (fixed)
- Eligible lakes = fleet lakes whose registry polygon (analysis) contains an NLA 2017 site coordinate **and** have ≥1 NLA station row with a cover code; positives = lakes with mean(emergent, floating) station cover code ≥ 1.0 **or** ≥ 20 % of stations at code ≥ 2; negatives = lakes with all stations 0 for emergent, floating and total macrophyte; the rest are reported as "ambiguous" and not scored as positive or negative. Counts are computed, not assumed.
- Scene: S2 L2A within ±21 d of the NLA visit date (summer 2017); if none in the c1 collection, record `NO_SCENE` (do not substitute another year silently; a labelled 2018 substitute may be reported separately).
- Observer score per lake: **shoreline-belt plant share** = flagged cells ÷ seen cells within the 0–90 m band inside the polygon (cells flagged `SHORE_ADJACENT` excluded).
- Metrics: Spearman between belt share and lake-mean (emergent+floating) cover code; lake-level AUC positives vs negatives; negative-control flagged share.

## 5. Gates (validation ladder)

States: `NOT_VALIDATED → RESEARCH → CALIBRATION → PARTIAL → VALIDATED`. Vegetation **begins `NOT_VALIDATED`**.

| State | Entry condition |
|---|---|
| `RESEARCH` | Observer reproduced from production code and scored once on ≥2 independent truth sets; report committed |
| `CALIBRATION` | Thresholds/acceptance rules fixed on a calibration subset disjoint from the evaluation subset; ≥10 truth lakes |
| `PARTIAL` | Surface presence passes **all** of: (a) cell-level precision ≥ 0.80 and recall ≥ 0.70 pooled and for **each** of ≥ 3 independent truth lakes with ≥ 30 positive cells; (b) open-water FPR ≤ 2 % cell-level; (c) NLA lake-level AUC ≥ 0.80 and Spearman ≥ 0.50 on ≥ 15 eligible lakes spanning ≥ 3 regions; (d) negative-control flagged share ≤ 2 %; (e) lower bootstrap bound of pooled F1 ≥ 0.65. A `PARTIAL` claim applies **only to the regions/lake classes that passed** |
| `VALIDATED` | `PARTIAL` plus: ≥ 25 truth lakes across ≥ 5 regions including ≥ 1 turbid reservoir and ≥ 1 southern hydrilla system; temporal persistence validated; density (if exposed) passes §6; pass acceptance behaviour stable across ≥ 2 seasons; independent review |

## 6. Density gate
Density classes (`SPARSE/MODERATE/DENSE`) are exposed only if, on ≥ 15 lakes with density truth (NLA cover codes, Snohomish density, FWC): weighted kappa ≥ 0.40 **and** within-one-class agreement ≥ 90 %. Otherwise the Brain publishes **presence/coverage evidence only** (`coverageClass: NOT_CALIBRATED`).

## 7. Seasonal gate
Seasonal states (`EMERGING/GROWING/PEAK/DECLINING/DORMANT`) are published for a lake only if a ≥ 4-year back-test (2017–2025 where scenes allow) shows that the state assigned by the climatology (lake-specific, not generic-calendar) agrees with the observed accepted-pass belt share class (leave-one-year-out) with exact agreement ≥ 10 points above the generic "calendar-month" baseline **and** within-one ≥ 85 %; otherwise `seasonalState: UNKNOWN` with reason. "July = peak" is never encoded as truth.

## 8. Things that cannot be validated into existence
Submerged observation; species; underwater density; potential habitat as vegetation. Potential habitat is a separate, always `potentialOnly:true` product with its own (non-observation) checks.

## Amendments
*(none)*
