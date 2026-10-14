# Matched per-bank validation — AUDITED vs ESTIMATED exposure

Pre-registered in `WIND_VALIDATION_PHASE_PREREG.md §M` (commit `1c3b8fa1`) before any result. Code `jobs/wind-hourly/research/matched_bank_validation.py`; data `data/matched_bank_run1.json`, `data/matched_bank_run2.json`. No forecasts and no H2 involved (geometry only).

## What "matched" means here (unlike the earlier failed comparison)
Every estimate is computed **at the audited bank's own standoff coordinates**, for the **same 16 wind directions**, with the same 9-ray ±12° effective fetch and the same frozen CEM at 12 mph. The earlier G2 test compared independently sampled shoreline cells and different polygons; this one removes bank sampling as a difference.
- **M1 (method match):** the *same NHD polygon* the audited table was built from, 7 lakes (Guntersville, Wheeler, Wilson, Pickwick, Aleknagik, Coventry, Salton Sea): 88,544 bank-direction cells. Isolates raster/ray method (20 m vs 10 m, first-water placement).
- **M2 (source match):** the Lake Brain engine polygon, 73 audited lakes with a polygon: 713,264 cells (≤ 800 banks per lake by deterministic stride). The real ESTIMATED-tier test. Standoff points that are not water in the estimated raster after a 2-cell search (10,928 cells, 1.5%) are **UNKNOWN, never PROTECTED**; four tiny lakes (Andrews DE, Griffith DE, Bowdish RI, Watchaug RI) matched zero cells and so produce no labels at all.
- **M2-C:** M2 with the shipped ESTIMATED policy (PROTECTED must survive 1.5× estimated fetch).

## Two runs, honestly labelled
- **Run 1 (vocabulary v1, as pre-registered):** `false-PROTECTED` (estimate PROTECTED where the audited chop class was ≥ 3 in) = **10.6% (M1) / 10.8% (M2) → FAIL (line ≤ 2%)**. Cause: the v1 vocabulary labelled a lee-facing bank PROTECTED unless chop ≥ 4, so both audited and estimated labels called 3–6 in banks "PROTECTED" whenever the facing said lee. That is a vocabulary defect, found by this test.
- **Run 2 (vocabulary v2, shipped in `exposure.py`):** PROTECTED now requires modelled chop ≤ 2 (< 3 in) even when the bank faces away; ESTIMATED additionally needs the 1.5× margin. **This is a post-hoc safety fix evaluated on the same data. It is not an independent confirmation.**

## Results (run 2; "audited facing" = the audited anchor→standoff bearing used on both sides to isolate fetch)
| Metric | M1 | M2 | Pre-registered line | Verdict |
|---|---|---|---|---|
| 3-class label agreement (median lake) | 0.954 | 0.958 (M2-C 0.921) | M1 ≥ 0.90 · M2 ≥ 0.85 | PASS |
| DIRECT recall / precision | 0.987 / 0.941 | 0.992 / 0.943 | — | |
| CROSS recall / precision | 0.968 / 0.906 | 0.973 / 0.911 | — | |
| PROTECTED recall / precision | 0.934 / 0.981 | 0.940 / 0.985 | — | |
| HIGH FETCH precision / recall | 0.892 / 0.936 | 0.890 / 0.948 | M1 ≥ 0.85 both · M2 recall ≥ 0.80 | PASS |
| Per-direction Spearman of effective fetch (median) | 0.928 | 0.932 | M1 ≥ 0.90 · M2 ≥ 0.80 | PASS |
| Lake dominant-exposure direction within 22.5° | 6/7 (86%) | **58% (40 of 69 lakes)** | M2 ≥ 80% of lakes | **FAIL (M2, M2-C)** |
| False-PROTECTED, audited chop ≥ 3 (pooled) | 1.76% (M2-C 1.26%) | 1.49% (**M2-C 0.98%**) | ≤ 2% | PASS (4 of 65 M2 lakes exceed 2% per-lake, max 2.5% Lake Marion) |
| False-PROTECTED vs audited DIRECT/CROSS labels | 2.36% (C 1.49%) | 1.85% (C 1.02%) | secondary | |
| Median estimated/audited fetch (log ratio) | +0.32 (≈ +38%) | +0.27 (≈ +31%) | — | estimates are *longer* ⇒ safe direction |
| Estimated-facing bearing error (median) / within 45° | 18.7° / 81% | 18.3° / 83% | — | |

**Overall: M1 PASS. M2 and M2-C FAIL as registered**, solely on the lake-level dominant-direction line; every bank-level line passes. Per the pre-registration, **failure keeps the tier ESTIMATED with customer exposure labels withheld.** (The dominant direction is argmax over a nearly flat profile in dendritic reservoirs and differs between polygon sources; it is a lake summary the labels do not use, but the line was registered and is not moved.)

## The number that matters for the real pipeline: estimated facing
Above, both sides used the audited facing. An ESTIMATED lake would use *its own* facing (smoothed-mask gradient). Run 2 also measured that shipped path (estimated facing + conservative margin):
| | M1 | M2 |
|---|---|---|
| 3-class agreement with audited (median) | **0.798** | **0.782** |
| DIRECT recall / precision | 0.766 / 0.697 | 0.771 / 0.694 |
| CROSS recall / precision | 0.681 / 0.592 | 0.665 / 0.565 |
| PROTECTED recall / precision | 0.846 / **0.940** | 0.842 / **0.948** |
| False-PROTECTED (audited chop ≥ 3), pooled | 1.21% | **0.92%** (63 of 65 lakes < 2%; max 2.1%) |
| False-PROTECTED vs audited DIRECT/CROSS (any chop) | 6.9% | 6.1% |
Reading: the estimator is **good at "PROTECTED vs exposed" and poor at "DIRECT vs CROSS"** (the split hinges on a ±45° facing boundary; bearing error median 18°). Collapsing DIRECT+CROSS into EXPOSED gives 88.5% two-class accuracy (M2: 630,629 of 712,560 cells), EXPOSED recall 94.1%, PROTECTED precision 94.8%. Product rule adopted in code: for ESTIMATED geometry customer surfaces may only say **EXPOSED / PROTECTED / HIGH FETCH** (`exposure.public_label`), never DIRECT vs CROSS.

## Conservative rules verified
- UNKNOWN never becomes PROTECTED (unplaceable standoff points → UNKNOWN; sliver banks → UNKNOWN; no margin evaluation → UNKNOWN).
- ESTIMATED is never more protective than the audited rule (property test over facings × chop classes).
- Low/missing geometry confidence never gets labels (`fleet.exposure_allowed`); lake-identity risk and untested AK/HI domains block even audited lakes.

## What is and is not established
- Established: the polygon method reproduces audited fetch ordering (ρ 0.93) and HIGH FETCH (P/R ≈ 0.89/0.95) cell by cell; its error is in the *safe* direction (longer fetch); false-PROTECTED on genuinely exposed cells is ≈ 1%.
- Not established: that the *audited* labels themselves are right (no field truth); that lake dominant direction agrees across polygon sources (it does not); DIRECT vs CROSS on ESTIMATED lakes (withheld).
- Next test of the ESTIMATED tier is physical: the pairs on Hartwell and Toledo Bend in `WIND_BANK_PAIR_FIELD_PACK.md`.
