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
**Amendments change definitions, never §5–§7 thresholds. Each cites the evidence that forced it; none was made after seeing a gate-eligible PASS.**

### A1 — 2026-10-14 (after production-code scoring, `notes/06_production_observer_scoring.md`, run on the frozen v1 text)
1. **DARK_WATER (replaces the "red and B8A < 0.01 → pixel excluded, cell UNKNOWN if > 50 % excluded" rule in §1).** As written it blanked 40–58 % of clear-lake cells and made `NOT_OBSERVED` unreachable. New rule: a pixel is a plant pixel only if `NDVI ≥ 0.30` **and** NIR ≥ a floor (provisional 0.03, to be calibrated label-free on open water of negative-control lakes); a cell is `UNKNOWN(DARK_WATER)` only when ≥ 25 % of its pixels cross NDVI 0.30 but fail the floor **and** plant fraction ≥ 0.2 (borderline). Dark water elsewhere is a valid "not plant" look.
2. **Pass acceptance statistic (replaces "reads ≥ 50 % of the non-plant lake water", which is a Clarity turbidity statistic).** Acceptance uses the share of interior cells that are *known* (seen, not hazy/cloudy/shore). Thresholds are unchanged (≥ 50 %; fallback ≥ 25 %, flagged). The production whole-scene SWIR-DN rejection is **not** inherited.
3. **S (single pass) is evaluation-only.** It is never published as presence (`PASS_NOT_ACCEPTED`).
4. **Burst check.** With ≥ 3 accepted scenes, a scene with ≥ 20 plant cells and > 5× the others' median plant-cell count is excluded as an implausible burst (production: one Storm scene gave 39 false cells at coverage 0.03).
5. **Recall population.** Headline recall is **interior-only** (cells not SHORE_ADJACENT); whole-lake recall is reported beside it. Raw prevalence is the headline for precision; shore-matched numbers accompany it. Negatives: strict-none (< 5 % of any mapped class) headline, buffered-none (no label within 2 cells) secondary.
6. **Frame pinned.** Observer cell = 5 × 5 native 10 m pixels (≈ 50 m). Production `daily.py` runs a 36 m frame; results agree within noise on Snohomish, but the observer contract pins 50 m.
7. **Florida / presence-only classes.** At the observer as scored, recall on Florida point truth is < 0.35; presence-only truth never supports a `PARTIAL` claim for that regime.


### A2 — 2026-10-14 (after the seasonal back-test, `notes/08_seasonal_backtest.md`) — STRENGTHENS the seasonal gate
The frozen §7 compares the lake climatology only with the generic calendar rule. The back-test showed that rule is nearly worthless (exact 0.18 pooled), so beating it by 10 points is a low bar: a trivial "always the lake's most common state" guess scored 0.50 pooled and beat the climatology outright at Istokpoga (0.71 vs 0.53) and Sammamish (0.53 vs 0.39). **From A2, the §7 gate must also beat, by the same ≥ 10 exact-agreement points and per lake class, (b) the most-common-state baseline and (c) persistence of the last accepted pass when it is ≤ 30 days old.** This only makes the gate harder. Result on the existing back-test: pooled climatology 0.56 vs most-common-state 0.50 = +6 points ⇒ **the seasonal gate is NOT passed; `seasonalState` stays `UNKNOWN` fleet-wide.** The no-signal rule used in the back-test (climatology max belt share < 5 % ⇒ NOT_TESTABLE) is the back-test author's and is adopted here as: lakes with no measurable surface signal publish `seasonalState: UNKNOWN`, not a state.

### A3 — 2026-10-14 (before evaluating the shipped V1 observer module) — NIR floor calibration protocol
The provisional absolute NIR floor of A1 (0.03) is calibrated **label-free** on open water of lakes with no measurable surface-vegetation signal that are **not** evaluation lakes: Hartwell SC/GA and Leech Lake MN from the seasonal back-test caches (belt share ≈ 0.3 % and ≈ 1 %). Rule, fixed now: `NIR_PLANT_MIN = max(0.03, 99.5th percentile of B8A reflectance over SCL-water pixels ≥ 100 m from the polygon edge, accepted scenes only)`, rounded up to 0.005. No truth label (Snohomish, NLA, FWC, UMN) is used to choose it, and it is then **frozen** for all scoring. The evaluation of `jobs/vegetation-brain/vegetation_brain` (the shipped module, not a replica) follows §1 with A1/A2 and the gates unchanged: Snohomish (cell P/R/F1/IoU, LOLO), NLA 2017 (§4), FWC (recall only), with Snohomish ≥ 30-positive-cell limits making gate (a) NOT_TESTABLE unless more floating-leaf lakes are added. Results from the earlier non-V1 observers (notes 06, 07) are not evidence for the V1 module.
