# 06. Production surface-grass observer, imported and scored against the pre-registration

Research only. No git repo was written (both Sector worktrees read-only; bytecode writing disabled). Everything is under `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness/` (scripts, `out/` arrays and JSON, `figs/`); new files are logged in `../MANIFEST.jsonl`. Follows notes 04 and 05. Lessons respected: `sentinel-2-c1-l2a` decodes as `DN*1e-4 - 0.1`, `sentinel-2-l2a` is already offset-free (cached windows hold true reflectance, converted back to c1-convention DN before production sees them), and every precision-type number is shore-distance matched.

Pre-registration used (frozen, gates unchanged): `Sector_Engine-vegetation-adoption/docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md`. Production code: `jobs/lake-surface/derive_water_surface.py` (sha256 `eea5395a9bd8ea42717bd7c05b2d51a7268cc53cc3ef8abf82188e4365d055d7`, adoption worktree HEAD `3ed056165f7b`, file last changed in `f0da7fed`). Lineage caveat from `jobs/lake-surface/LINEAGE.md`: this is `main`'s copy, not the live job's `feat/clarity-algal-warning` copy; a diff of the two shows the grass/standoff/gate logic unchanged (the live branch adds NDCI plumbing, `s2_pass(..., ndci=)` and a red-edge read), so the results below describe the live algorithm too.

## 1. Headline

| question | answer |
|---|---|
| Is the production code reproduced by import, not re-implemented? | Yes. `dws.Frame`, `dws.lake_masks`, `dws.to_grid`, `dws._s2_native_fields`, `dws.s2_pass`, `dws.match_tiles` and (end-to-end) `dws.build_clarity` run unchanged; only the COG reader (`_read_s2_native`) and the STAC search (`passes`) are stubbed. |
| Replica (note 05) vs production | Essentially identical. 11 differing grass votes out of 2,119,474 lake-cell x scene comparisons (215 scenes, 12 lakes), 0 differences in seen/unseen, 12 in "turbidity read"; note 05's headline cell numbers reproduce exactly (single 60/51/0, shipped-style 60/5/0, median 60/0/0; FWC surface recall 0.320 / 0.322 / 0.432). Section 5. |
| Snohomish, 60 reachable positive cells (54 Roesiger, 6 Blackmans) | Recall 1.00 for S, A and P. Precision at raw prevalence: **S 0.58, A 0.92, P 0.97** (prereg guards as written; bare production S 0.54, A 0.92, P 1.00). Open-water FPR (flagged / all verified open-water cells): **S 3.2 % (fails the 2 % gate), A 0.4 %, P 0.2 %**, but under the prereg guards only 4-27 % of those cells are even known, so on a known-cells denominator A is 9.8 % and P 3.6 % (bare production and the dark-water fix: A 0.4 % / 0.2 %, P 0.0 %). Whole-lake recall is only **0.51** because 57 of 117 mapped positive cells sit in the 40 m shore band where the observer must refuse. |
| FWC LTM points, recall only (1,127 surface point cells, 7 lakes) | Pooled recall **0.12 (S), 0.12 (A), 0.12 (P)** with UNKNOWN counted as a miss, 0.38 / 0.47 / 0.47 among cells the observer could read; bare production 0.22-0.34. Far below 0.70. The Florida class cannot support a presence claim at this observer. |
| FWC LTM lake-level sonar PAC/PVI (143 lake-years in 52 lakes, 130 with a scene) | Bare production, S, scene gate off (note 05 setting): Spearman **0.43 with PVI, 0.36 with PAC**, AUC high-vs-low PVI **0.78**, PAC **0.66** (note 05: 0.43 / 0.35 / 0.79 / 0.65). Exact production (gate on): rho 0.39 / 0.32. With the prereg guards as written the observer can score only 35-39 lake-years and rho falls to 0.29-0.35. |
| Gates (section 8) | (a) NOT_TESTABLE, (b) S FAIL / A, P provisional PASS on the literal denominator only, (c) NOT_RUN (NLA not in this task), (d) NOT_RUN, (e) NOT_TESTABLE. Entry to `RESEARCH`: condition met by this work (report still to be committed by the repo owner). `CALIBRATION` and above: not reached. |
| What breaks the observer as specified | (1) The prereg DARK_WATER guard (red and B8A both < 0.01 on > 50 % of a cell) marks **40-58 % of all Snohomish lake cells UNKNOWN**: it is clear open water, exactly the "NOT_OBSERVED" evidence the Brain needs. (2) Production's whole-scene SWIR-DN gate rejects 7 of 48 FWC point scenes and 116 of 482 PAC scene-lake-year pairs, the vegetated ones preferentially in the point set, and leaves Cypress with no usable scene at all. (3) The production pass-acceptance test (read >= 50 % of non-plant water) is met by only 11-12 % of Florida scenes (71-78 % are below even the 0.25 fallback), so A and P are mostly UNKNOWN there. (4) P needs >= 3 accepted scenes in +-21 d: true for 3 of 5 Snohomish lakes, 1 of 7 FWC point lakes and none of the PAC lake-years the observer could score. Fixes in section 12. |

## 2. What was run, exactly

### 2.1 Production functions called and stubs

| production symbol | status | note |
|---|---|---|
| `dws.Frame(lake, cell)` and `dws.lake_masks` | **called unchanged** | EPSG:3857 grid, 1 km pad, `lake`, `clarity` (lake eroded 40 m), `dws.UTM` set per lake from the tile CRS. 50 m cell (prereg) is primary; the production daily job's `CLARITY_CELL = 36` m is run as a sensitivity (Snohomish, FWC points). |
| `dws._s2_native_fields(t)` | **called unchanged** (wrapped only to copy out diagnostics from the same arrays) | every 10 m gate: SCL water, 10 m bank/cloud/structure/haze standoffs, 600 m real-cloud standoff, cloud-edge and haze-edge SWIR gates, `NDVI(B8A,B04) >= 0.30` plant pixel, `gfrac`, `hidden`, `near`. |
| `dws.s2_pass(items, frame, measurable, grass_mask)` | **called unchanged** | tile feather blend, `match_tiles`, per-cell `gfrac`, `grass = gfrac >= 0.5 & clarity & isnan(turbidity)`, and the whole-scene "SWIR DN over water" gate that raises `PassRejected`. |
| `dws.to_grid`, `dws.match_tiles`, `dws.PassRejected` | **called unchanged** | |
| `dws.build_clarity` | **called unchanged in `35_e2e.py`** | pass-acceptance walk (newest first, >= 0.5 read, fallback 80 % of best >= 0.25), speck/shadow filters, grass-under-cloud borrow, bed-to-bank strip, `fill_lake`. Output PNG code 3 = grass. |
| `dws._read_s2_native` | **stubbed** | returns the dict production expects (`scl`/`nir08`/`swir16` as 20 m uint16 DN, `red` 10 m, nested windows) rebuilt from cached windows: cached reflectance -> c1-convention DN -> 20 m by taking every second pixel after aligning to the 20 m grid (block-constancy check: 1.000 on every block with data in all 430 B8A/B11 band-scene arrays; all four 20 m phases occur). For the Guntersville pilot the **real** reader and real Earth Search query are used. |
| `dws.passes` (STAC search) | **stubbed only in `35_e2e.py`** | returns the cached candidate passes (no scene cloud-cover filter, because the caches hold scenes chosen by lake clear fraction instead). |
| `daily.py` (GCS store, memory budget, STAC "newest pass") | **not used** | only `dws` is imported. |
| SWIR-DN gate | **one sensitivity switch** | `prod_import.py` can answer the gate's `np.median(list)` with 1000.0 (a numpy proxy), i.e. "gate off", to measure what the gate costs. Every number labelled "gate on" / default is exact production behaviour. |

Production deletes `t["red"]` in place; the stub hands out a copy per call (first harness run crashed on that, see dead ends).

### 2.2 Observers (prereg section 1) as implemented in `score_lib.py`

* **Scene window:** +-21 d of the reference date (prereg `scene-reference gap > 21 d` guard; note 05 used +-45 d). Reference date = survey median date (Snohomish, FWC points) or the median LTM intercept date of the lake-year (PAC). Scenes that production's SWIR-DN gate rejects are dropped (as production does), except in the labelled "gate off" runs.
* **S:** nearest scene with >= 75 % of lake cells seen; cell vote only.
* **A:** nearest scene reading >= 50 % of the non-plant clarity-mask water (`cov`, computed exactly as in `build_clarity`: `read & (clarity & ~flag)` / `clarity & ~flag`); fallback = best coverage >= 0.25 (ties nearest); else UNKNOWN (`PASS_NOT_ACCEPTED`).
* **P:** per cell, median over accepted (cov >= 0.5) scenes within +-21 d of the plant fraction (cells production calls "read" count 0; UNKNOWN cells are skipped), needing >= 3 such scenes **at that cell**; below that the cell falls back to A and carries `persistence: INSUFFICIENT`. If the lake has < 3 accepted scenes the whole lake is A.
* **Cell rule:** `plantFraction >= 0.5` of seen 10 m pixels (production `gfrac`), plant pixel `NDVI(B8A,B4) >= 0.30` unchanged.
* **Modes** (same scenes, three guard sets):
  * `v1` (**primary**, the prereg text): production arrays plus the prereg guards that production lacks: seen share < 0.5 -> UNKNOWN; production `hidden >= 0.5` (cloud/shadow standoff and haze) -> UNKNOWN; dark water (red and B8A < 0.01 on >= 50 % of the cell's seen pixels, pixel excluded from the fraction) -> UNKNOWN; cells within the 40 m shore band (production `clarity` mask; prereg says 1 pixel, ~50 m) -> `SHORE_ADJACENT`. First-hit attribution: shore > no data > cloud/insufficient > haze/standoff > dark.
  * `prod`: bare production (unseen and shore band are the only UNKNOWN).
  * `v1fix`: `v1` but a dark pixel can only be non-plant (it cannot be a plant call) and a dark cell is not refused (recommended change, not the prereg text).
  * GLARE cannot be separated: no Wind flag is available and the contract's SWIR glint limit (0.0215) is within 7 % of production's haze threshold (0.02), so glint falls under HAZE. Reported as an unmeasured guard.
* No threshold was tuned anywhere (production constants only), so leave-one-lake-out is not applicable; per-lake and pooled results are out-of-sample by construction. CIs are bootstrap over lakes (2,000 resamples).

### 2.3 Truth sets and metrics

* **Snohomish WA** (5 lakes): positive cell = floating-leaf polygon share >= 0.5 (note 05 definition; prereg does not fix it); negative = strict-none (< 5 % of any mapped class, 1,331 cells) with "buffered-none" (no label within 2 cells, 837) as a sensitivity. Population = clarity-mask (reachable) cells. Shore matching: pooled positives' distance histogram over 0/15/30/45/60/90/150/300 m (reachable positives fall in 45-60 m: 6, 60-90: 29, 90-150: 22, 150-300: 3); negatives re-weighted to it in two ways, because the prereg fixes the histogram but not the prevalence: "50 % prevalence" (note 04 convention, flatters precision) and "raw prevalence" (same distance shape, total negative weight kept, the conservative reading). UNKNOWN positives count as misses in recall (recall among known cells also given); FPR = flagged / all verified open-water cells (known-only FPR also given).
* **FWC LTM points** (7 lakes, recall only): cells containing >= 1 floating or emergent point; also submersed-only cells and unsurveyed cells (flag rate on the latter is not an FPR).
* **FWC LTM PAC/PVI** (lake-level sonar): lake score = flagged / known clarity cells (also the 40-90 m belt); lake-years refused when no scene / not accepted or < 50 % of clarity cells known. Spearman, AUC PVI >= 20 vs < 5 and PAC >= 50 vs < 20, bootstrap over lakes. Uses note 05's lean caches (<= 2 clear scenes plus a few unclear ones per lake-year).
* NLA 2017 (gates c, d) was not part of this task and was not run.

### 2.4 Commands

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments
H=adoption/prod_harness
for t in snoco fwc; do for c in 50 36; do .venv/bin/python -W ignore $H/10_run_cells.py $t $c; done; done   # production s2_pass on cached scenes
.venv/bin/python -W ignore $H/12_run_pac.py 50                                                              # PAC lake-years (52 lakes)
for m in prod v1 v1fix; do for r in 0 1; do .venv/bin/python -W ignore $H/20_score.py 50 $m $r; .venv/bin/python -W ignore $H/22_score_pac.py 50 $m $r; done; done
for m in prod v1 v1fix; do for r in 0 1; do .venv/bin/python -W ignore $H/20_score.py 36 $m $r; done; done
.venv/bin/python -W ignore $H/25_unknown.py 50 ; .venv/bin/python -W ignore $H/30_replica_diff.py
.venv/bin/python -W ignore $H/35_e2e.py 0 ; .venv/bin/python -W ignore $H/35_e2e.py 7
.venv/bin/python -W ignore $H/40_guntersville_run.py ; .venv/bin/python -W ignore $H/41_guntersville_score.py   # pilot, ~600 MB read
.venv/bin/python $H/23_summarize.py ; .venv/bin/python -W ignore $H/24_extra.py ; .venv/bin/python $H/27_assemble_note.py ; .venv/bin/python $H/50_manifest.py
```
(`score_*.json`, `pac_*.json`, `unknown_50.json`, `replica_vs_production.json`, `e2e_*.json`, `tables*.md` are in `out/`; figures in `figs/`.)

## 3. Snohomish polygons, cell level (5 lakes, 60 reachable positive cells)

Primary configuration: prereg guards as written (`v1`), 50 m cell, production scene gate on, +-21 d. Scene gaps are 1-7 d (headline gap class, <= 7 d) for every lake; no 8-30 d scene is used.

**Snohomish, PRIMARY: v1 guards as written, 50 m cell, production scene gate ON, +-21 d** (`score_50_v1_rej0.json`, negatives = nstrict)

| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 60 | 43 | 0 | 0.583 | 0.946 | 0.448 | 0.619 | 1.000 | 1.000 | 0.972 | 0.946 | 0.916 | 0.032 | 0.121 | 0.000 | 0.66-1.00 (n=1858) |
| A | 60 | 5 | 0 | 0.923 | 0.992 | 0.852 | 0.920 | 1.000 | 1.000 | 0.996 | 0.992 | 0.945 | 0.004 | 0.098 | 0.000 | 1.00-1.00 (n=1858) |
| P | 60 | 2 | 0 | 0.968 | 0.997 | 0.937 | 0.968 | 1.000 | 1.000 | 0.998 | 0.997 | 0.980 | 0.002 | 0.036 | 0.000 | 1.00-1.00 (n=1858) |

Per lake (`score_50_v1_rej0.json`): positives reachable (outside 40 m shore band) / whole-lake, TP, FP, P raw, P matched, R reachable, R whole-lake, FPR raw, scene (gap d, cov).

| lake | obs | pos reach / whole | TP | FP | P raw | P matched | R reach | R whole-lake | FPR raw | scene used |
|---|---|---|---|---|---|---|---|---|---|---|
| Serene | S | 0 / 7 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | SINGLE gap 1d cov 0.04 |
| Serene | A | 0 / 7 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | NONE gap Noned |
| Serene | P | 0 / 7 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | PERSISTENCE gap Noned, n_acc 0, INSUFFICIENT |
| Blackmans | S | 6 / 17 | 6 | 0 | 1.000 | 1.000 | 1.000 | 0.353 | 0.000 | SINGLE gap 4d cov 0.41 |
| Blackmans | A | 6 / 17 | 6 | 0 | 1.000 | 1.000 | 1.000 | 0.353 | 0.000 | ACCEPTED gap 7d cov 0.58 |
| Blackmans | P | 6 / 17 | 6 | 0 | 1.000 | 1.000 | 1.000 | 0.353 | 0.000 | PERSISTENCE gap 7d, n_acc 3, MEDIAN_OF_ACCEPTED |
| Storm | S | 0 / 0 | 0 | 39 | 0.000 | 0.000 | n/a | 0.000 | 0.257 | SINGLE gap 1d cov 0.03 |
| Storm | A | 0 / 0 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | ACCEPTED gap 2d cov 0.76 |
| Storm | P | 0 / 0 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | PERSISTENCE gap 2d, n_acc 4, MEDIAN_OF_ACCEPTED |
| Roesiger | S | 54 / 88 | 54 | 3 | 0.947 | 0.995 | 1.000 | 0.614 | 0.004 | SINGLE gap 1d cov 0.50 |
| Roesiger | A | 54 / 88 | 54 | 5 | 0.915 | 0.991 | 1.000 | 0.614 | 0.006 | ACCEPTED gap 6d cov 0.55 |
| Roesiger | P | 54 / 88 | 54 | 2 | 0.964 | 0.997 | 1.000 | 0.614 | 0.003 | PERSISTENCE gap 6d, n_acc 6, MEDIAN_OF_ACCEPTED |
| Bosworth | S | 0 / 5 | 0 | 1 | 0.000 | 0.000 | n/a | 0.000 | 0.004 | SINGLE gap 1d cov 0.50 |
| Bosworth | A | 0 / 5 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | ACCEPTED gap 6d cov 0.51 |
| Bosworth | P | 0 / 5 | 0 | 0 | n/a | n/a | n/a | 0.000 | 0.000 | PERSISTENCE gap 6d, n_acc 2, INSUFFICIENT |

Figure `figs/snoco_Roesiger_Storm_SAP.png` (truth | S | A | P | A bare production, Roesiger above, Storm below) shows both the Storm burst failure of S and the dark-water guard blanking the open water.

Reading the table: recall is 1.00 (60 of 60) for every observer and every guard set; what differs is false positives. S fails on **one** scene, Storm 2023-08-18 (39 false cells, pass coverage 0.03: haze or thin cloud the SCL missed; the scene shows 100 % of lake cells "seen" and passes the 75 % clear test), exactly the burst failure note 05 found. A rejects that scene (cov 0.03) and also has no accepted pass at Serene (cov 0.04 in the +-21 d window), so Serene is UNKNOWN. P (3-6 accepted scenes at Blackmans, Storm, Roesiger; Serene and Bosworth have < 3 and fall back to A) removes the remaining false cells in the bare-production run; under `v1` 2 false cells remain at Roesiger because only 114 of its 906 reachable cells have >= 3 *known* accepted scenes (the dark-water and haze guards leave the rest UNKNOWN) and the others fall back to A.

**Bare production (no prereg-only guards):**

**Snohomish, bare production (no prereg-only guards), 50 m** (`score_50_prod_rej0.json`, negatives = nstrict)

| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 60 | 51 | 0 | 0.541 | 0.936 | 0.401 | 0.573 | 1.000 | 1.000 | 0.967 | 0.936 | 0.966 | 0.038 | 0.038 | 0.000 | 0.65-0.99 (n=1858) |
| A | 60 | 5 | 0 | 0.923 | 0.991 | 0.839 | 0.912 | 1.000 | 1.000 | 0.996 | 0.991 | 0.995 | 0.004 | 0.004 | 0.000 | 1.00-1.00 (n=1858) |
| P | 60 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.00-1.00 (n=1858) |

**Dark-water fix:**

**Snohomish, v1 with dark-water fix, 50 m** (`score_50_v1fix_rej0.json`, negatives = nstrict)

| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 60 | 41 | 0 | 0.594 | 0.950 | 0.467 | 0.637 | 1.000 | 1.000 | 0.974 | 0.950 | 0.973 | 0.031 | 0.034 | 0.000 | 0.66-1.00 (n=1858) |
| A | 60 | 2 | 0 | 0.968 | 0.998 | 0.954 | 0.976 | 1.000 | 1.000 | 0.999 | 0.998 | 0.999 | 0.002 | 0.002 | 0.000 | 1.00-1.00 (n=1858) |
| P | 60 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.00-1.00 (n=1858) |

**Production scene gate off (no Snohomish scene is rejected, so identical):**

**Snohomish, v1, production scene gate OFF (sensitivity)** (`score_50_v1_rej1.json`, negatives = nstrict)

| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 60 | 43 | 0 | 0.583 | 0.946 | 0.448 | 0.619 | 1.000 | 1.000 | 0.972 | 0.946 | 0.916 | 0.032 | 0.121 | 0.000 | 0.66-1.00 (n=1858) |
| A | 60 | 5 | 0 | 0.923 | 0.992 | 0.852 | 0.920 | 1.000 | 1.000 | 0.996 | 0.992 | 0.945 | 0.004 | 0.098 | 0.000 | 1.00-1.00 (n=1858) |
| P | 60 | 2 | 0 | 0.968 | 0.997 | 0.937 | 0.968 | 1.000 | 1.000 | 0.998 | 0.997 | 0.980 | 0.002 | 0.036 | 0.000 | 1.00-1.00 (n=1858) |

**Production daily 36 m frame (the frame `daily.py` really uses):**

**Snohomish, v1, production daily 36 m frame** (`score_36_v1_rej0.json`, negatives = nstrict)

| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 118 | 95 | 0 | 0.554 | 0.939 | 0.412 | 0.583 | 1.000 | 1.000 | 0.968 | 0.939 | 0.902 | 0.036 | 0.140 | 0.000 | 0.36-1.00 (n=1978) |
| A | 116 | 6 | 2 | 0.951 | 0.995 | 0.902 | 0.941 | 0.983 | 1.000 | 0.989 | 0.978 | 0.957 | 0.002 | 0.057 | 0.017 | 0.82-1.00 (n=1858) |
| P | 116 | 8 | 2 | 0.935 | 0.993 | 0.862 | 0.918 | 0.983 | 1.000 | 0.988 | 0.976 | 0.943 | 0.003 | 0.074 | 0.017 | 0.81-1.00 (n=1858) |

**Buffered-none negatives:**

**Snohomish, v1, buffered-none negatives (no label within 2 cells)** (`score_50_v1_rej0.json`, negatives = nbuf)

| obs | TP | FP | FN(all) | P raw | **P matched (50% prev.)** | P matched (raw prev.) | F1 matched (raw prev.) | R (UNKNOWN=miss) | R (known only) | F1 matched | IoU matched | BalAcc matched | FPR raw (all open-water cells) | FPR raw (known) | pos UNKNOWN | F1m lake-bootstrap 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 60 | 26 | 0 | 0.698 | 0.900 | 0.399 | 0.571 | 1.000 | 1.000 | 0.947 | 0.900 | 0.877 | 0.031 | 0.120 | 0.000 | 0.47-1.00 (n=1858) |
| A | 60 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.00-1.00 (n=1858) |
| P | 60 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.00-1.00 (n=1858) |

Points to take from the sensitivity runs: results do not depend on the frame (A recall drops from 1.00 to 0.98 at 36 m because 2 Serene cells fall in a refused scene, precision 0.95); the production gate never fires on these clear PNW lakes; buffered-none negatives give A and P zero false cells (all A/P false cells touch a mapped polygon, i.e. they may be unmapped bed edge, not open water); the shore-matched precision at 50 % prevalence is far higher than at raw prevalence (A 0.99 vs 0.85) because with 4.3 % prevalence a handful of false cells matter.

**Whole-lake recall.** 57 of the 117 mapped floating-leaf cells (49 %) lie inside the 40 m shore band (Roesiger 34 of 88, Blackmans 11 of 17); the observer must call them SHORE_ADJACENT, so whole-lake recall is **0.51** at 50 m and 0.46 at 36 m for S, A and P alike. The reachable-cell recall of 1.00 is therefore not "the lake's recall". If the PARTIAL recall gate is read on whole-lake truth, it fails by construction; the prereg should say which population it means.

## 4. FWC LTM points, recall only (7 lakes, 1,127 surface point cells at 50 m)

Recall is presence-only evidence; precision and FPR are not computed. "Unsurveyed cells flagged" is a flag rate on cells > 3 cells from any recorded point, not an FPR.

**FWC points, PRIMARY v1, 50 m** (`score_50_v1_rej0.json`)

| lake (survey) | obs | scene (gap d) | point cells (surface, reachable) | recall (UNKNOWN=miss) | recall (known only) | UNKNOWN share of point cells | submersed-only cells flagged | unsurveyed cells flagged (not an FPR) |
|---|---|---|---|---|---|---|---|---|
| Orange (2022-09-06) | S | SINGLE 2022-09-05 (1) | 141 | 0.128 | 0.462 | 0.723 | 0.032 | 0.018 |
| Orange (2022-09-06) | A | ACCEPTED 2022-09-05 (1) | 141 | 0.128 | 0.462 | 0.723 | 0.032 | 0.018 |
| Orange (2022-09-06) | P | PERSISTENCE  (1) | 141 | 0.128 | 0.462 | 0.723 | 0.032 | 0.018 |
| Griffin (2019-08-29) | S | SINGLE 2019-08-27 (2) | 276 | 0.098 | 0.370 | 0.736 | 0.000 | 0.008 |
| Griffin (2019-08-29) | A | FALLBACK 2019-08-27 (2) | 276 | 0.098 | 0.370 | 0.736 | 0.000 | 0.008 |
| Griffin (2019-08-29) | P | PERSISTENCE  (None) | 276 | 0.098 | 0.370 | 0.736 | 0.000 | 0.008 |
| Apopka (2021-08-18) | S | SINGLE 2021-08-21 (3) | 141 | 0.390 | 0.410 | 0.050 | 0.032 | 0.003 |
| Apopka (2021-08-18) | A | ACCEPTED 2021-08-21 (3) | 141 | 0.390 | 0.410 | 0.050 | 0.032 | 0.003 |
| Apopka (2021-08-18) | P | PERSISTENCE  (3) | 141 | 0.390 | 0.410 | 0.050 | 0.032 | 0.003 |
| Harris (2018-06-18) | S | NONE  (None) | 111 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Harris (2018-06-18) | A | FALLBACK 2018-06-18 (0) | 111 | 0.000 | 0.000 | 0.937 | 0.001 | 0.001 |
| Harris (2018-06-18) | P | PERSISTENCE  (None) | 111 | 0.000 | 0.000 | 0.937 | 0.001 | 0.001 |
| Panasoffkee (2022-05-10) | S | SINGLE 2022-05-28 (18) | 222 | 0.032 | 0.087 | 0.640 | 0.000 | 0.008 |
| Panasoffkee (2022-05-10) | A | NONE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Panasoffkee (2022-05-10) | P | PERSISTENCE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Yale (2023-07-27) | S | SINGLE 2023-08-11 (15) | 74 | 0.432 | 0.865 | 0.500 | 0.003 | 0.000 |
| Yale (2023-07-27) | A | ACCEPTED 2023-08-11 (15) | 74 | 0.432 | 0.865 | 0.500 | 0.003 | 0.000 |
| Yale (2023-07-27) | P | PERSISTENCE  (15) | 74 | 0.432 | 0.865 | 0.500 | 0.003 | 0.000 |
| Cypress (2022-06-29) | S | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | A | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | P | PERSISTENCE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |

Pooled (cell-weighted) recall on surface point cells:

| obs | recall (UNKNOWN=miss) | recall (known only) | gap <= 7 d | gap 8-21 d | submersed-only cells flagged |
|---|---|---|---|---|---|
| S | 139/1127 = 0.123 | 139/363 = 0.383 | 100/558 = 0.179 | 39/296 = 0.132 | 98/9974 = 0.010 |
| A | 132/1127 = 0.117 | 132/283 = 0.466 | 100/669 = 0.149 | 32/74 = 0.432 | 101/9974 = 0.010 |
| P | 132/1127 = 0.117 | 132/283 = 0.466 | 73/282 = 0.259 | 32/74 = 0.432 | 101/9974 = 0.010 |

**Bare production:**

**FWC points, bare production, 50 m** (`score_50_prod_rej0.json`)

| lake (survey) | obs | scene (gap d) | point cells (surface, reachable) | recall (UNKNOWN=miss) | recall (known only) | UNKNOWN share of point cells | submersed-only cells flagged | unsurveyed cells flagged (not an FPR) |
|---|---|---|---|---|---|---|---|---|
| Orange (2022-09-06) | S | SINGLE 2022-09-05 (1) | 141 | 0.262 | 0.500 | 0.475 | 0.111 | 0.019 |
| Orange (2022-09-06) | A | ACCEPTED 2022-09-05 (1) | 141 | 0.262 | 0.500 | 0.475 | 0.111 | 0.019 |
| Orange (2022-09-06) | P | PERSISTENCE  (1) | 141 | 0.262 | 0.500 | 0.475 | 0.111 | 0.019 |
| Griffin (2019-08-29) | S | SINGLE 2019-08-27 (2) | 276 | 0.373 | 0.479 | 0.221 | 0.014 | 0.006 |
| Griffin (2019-08-29) | A | FALLBACK 2019-08-27 (2) | 276 | 0.373 | 0.479 | 0.221 | 0.014 | 0.006 |
| Griffin (2019-08-29) | P | PERSISTENCE  (None) | 276 | 0.373 | 0.479 | 0.221 | 0.014 | 0.006 |
| Apopka (2021-08-18) | S | SINGLE 2021-08-21 (3) | 141 | 0.397 | 0.397 | 0.000 | 0.032 | 0.003 |
| Apopka (2021-08-18) | A | ACCEPTED 2021-08-21 (3) | 141 | 0.397 | 0.397 | 0.000 | 0.032 | 0.003 |
| Apopka (2021-08-18) | P | PERSISTENCE  (3) | 141 | 0.397 | 0.397 | 0.000 | 0.032 | 0.003 |
| Harris (2018-06-18) | S | NONE  (None) | 111 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Harris (2018-06-18) | A | FALLBACK 2018-06-18 (0) | 111 | 0.180 | 0.303 | 0.405 | 0.018 | 0.001 |
| Harris (2018-06-18) | P | PERSISTENCE  (None) | 111 | 0.180 | 0.303 | 0.405 | 0.018 | 0.001 |
| Panasoffkee (2022-05-10) | S | SINGLE 2022-05-28 (18) | 222 | 0.059 | 0.062 | 0.059 | 0.006 | 0.006 |
| Panasoffkee (2022-05-10) | A | NONE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Panasoffkee (2022-05-10) | P | PERSISTENCE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Yale (2023-07-27) | S | SINGLE 2023-08-11 (15) | 74 | 0.459 | 0.507 | 0.095 | 0.005 | 0.000 |
| Yale (2023-07-27) | A | ACCEPTED 2023-08-11 (15) | 74 | 0.459 | 0.507 | 0.095 | 0.005 | 0.000 |
| Yale (2023-07-27) | P | PERSISTENCE  (15) | 74 | 0.459 | 0.507 | 0.095 | 0.005 | 0.000 |
| Cypress (2022-06-29) | S | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | A | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | P | PERSISTENCE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |

Pooled (cell-weighted) recall on surface point cells:

| obs | recall (UNKNOWN=miss) | recall (known only) | gap <= 7 d | gap 8-21 d | submersed-only cells flagged |
|---|---|---|---|---|---|
| S | 243/1127 = 0.216 | 243/706 = 0.344 | 196/558 = 0.351 | 47/296 = 0.159 | 188/9974 = 0.019 |
| A | 250/1127 = 0.222 | 250/563 = 0.444 | 216/669 = 0.323 | 34/74 = 0.459 | 224/9974 = 0.022 |
| P | 250/1127 = 0.222 | 250/563 = 0.444 | 93/282 = 0.330 | 34/74 = 0.459 | 224/9974 = 0.022 |

**Dark-water fix:**

**FWC points, v1 with dark fix** (`score_50_v1fix_rej0.json`)

| lake (survey) | obs | scene (gap d) | point cells (surface, reachable) | recall (UNKNOWN=miss) | recall (known only) | UNKNOWN share of point cells | submersed-only cells flagged | unsurveyed cells flagged (not an FPR) |
|---|---|---|---|---|---|---|---|---|
| Orange (2022-09-06) | S | SINGLE 2022-09-05 (1) | 141 | 0.128 | 0.462 | 0.723 | 0.032 | 0.018 |
| Orange (2022-09-06) | A | ACCEPTED 2022-09-05 (1) | 141 | 0.128 | 0.462 | 0.723 | 0.032 | 0.018 |
| Orange (2022-09-06) | P | PERSISTENCE  (1) | 141 | 0.128 | 0.462 | 0.723 | 0.032 | 0.018 |
| Griffin (2019-08-29) | S | SINGLE 2019-08-27 (2) | 276 | 0.098 | 0.370 | 0.736 | 0.000 | 0.008 |
| Griffin (2019-08-29) | A | FALLBACK 2019-08-27 (2) | 276 | 0.098 | 0.370 | 0.736 | 0.000 | 0.008 |
| Griffin (2019-08-29) | P | PERSISTENCE  (None) | 276 | 0.098 | 0.370 | 0.736 | 0.000 | 0.008 |
| Apopka (2021-08-18) | S | SINGLE 2021-08-21 (3) | 141 | 0.390 | 0.410 | 0.050 | 0.032 | 0.003 |
| Apopka (2021-08-18) | A | ACCEPTED 2021-08-21 (3) | 141 | 0.390 | 0.410 | 0.050 | 0.032 | 0.003 |
| Apopka (2021-08-18) | P | PERSISTENCE  (3) | 141 | 0.390 | 0.410 | 0.050 | 0.032 | 0.003 |
| Harris (2018-06-18) | S | NONE  (None) | 111 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Harris (2018-06-18) | A | FALLBACK 2018-06-18 (0) | 111 | 0.000 | 0.000 | 0.937 | 0.001 | 0.001 |
| Harris (2018-06-18) | P | PERSISTENCE  (None) | 111 | 0.000 | 0.000 | 0.937 | 0.001 | 0.001 |
| Panasoffkee (2022-05-10) | S | SINGLE 2022-05-28 (18) | 222 | 0.032 | 0.087 | 0.640 | 0.000 | 0.008 |
| Panasoffkee (2022-05-10) | A | NONE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Panasoffkee (2022-05-10) | P | PERSISTENCE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Yale (2023-07-27) | S | SINGLE 2023-08-11 (15) | 74 | 0.419 | 0.721 | 0.419 | 0.003 | 0.000 |
| Yale (2023-07-27) | A | ACCEPTED 2023-08-11 (15) | 74 | 0.419 | 0.721 | 0.419 | 0.003 | 0.000 |
| Yale (2023-07-27) | P | PERSISTENCE  (15) | 74 | 0.419 | 0.721 | 0.419 | 0.003 | 0.000 |
| Cypress (2022-06-29) | S | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | A | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | P | PERSISTENCE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |

Pooled (cell-weighted) recall on surface point cells:

| obs | recall (UNKNOWN=miss) | recall (known only) | gap <= 7 d | gap 8-21 d | submersed-only cells flagged |
|---|---|---|---|---|---|
| S | 138/1127 = 0.122 | 138/369 = 0.374 | 100/558 = 0.179 | 38/296 = 0.128 | 97/9974 = 0.010 |
| A | 131/1127 = 0.116 | 131/289 = 0.453 | 100/669 = 0.149 | 31/74 = 0.419 | 100/9974 = 0.010 |
| P | 131/1127 = 0.116 | 131/289 = 0.453 | 73/282 = 0.259 | 31/74 = 0.419 | 100/9974 = 0.010 |

**Bare production with the production scene gate off (what the gate costs):**

**FWC points, bare production, production scene gate OFF (sensitivity)** (`score_50_prod_rej1.json`)

| lake (survey) | obs | scene (gap d) | point cells (surface, reachable) | recall (UNKNOWN=miss) | recall (known only) | UNKNOWN share of point cells | submersed-only cells flagged | unsurveyed cells flagged (not an FPR) |
|---|---|---|---|---|---|---|---|---|
| Orange (2022-09-06) | S | SINGLE 2022-09-05 (1) | 141 | 0.262 | 0.500 | 0.475 | 0.111 | 0.019 |
| Orange (2022-09-06) | A | ACCEPTED 2022-09-05 (1) | 141 | 0.262 | 0.500 | 0.475 | 0.111 | 0.019 |
| Orange (2022-09-06) | P | PERSISTENCE  (1) | 141 | 0.262 | 0.500 | 0.475 | 0.111 | 0.019 |
| Griffin (2019-08-29) | S | SINGLE 2019-08-27 (2) | 276 | 0.373 | 0.479 | 0.221 | 0.014 | 0.006 |
| Griffin (2019-08-29) | A | FALLBACK 2019-08-27 (2) | 276 | 0.373 | 0.479 | 0.221 | 0.014 | 0.006 |
| Griffin (2019-08-29) | P | PERSISTENCE  (None) | 276 | 0.373 | 0.479 | 0.221 | 0.014 | 0.006 |
| Apopka (2021-08-18) | S | SINGLE 2021-08-21 (3) | 141 | 0.397 | 0.397 | 0.000 | 0.032 | 0.003 |
| Apopka (2021-08-18) | A | ACCEPTED 2021-08-21 (3) | 141 | 0.397 | 0.397 | 0.000 | 0.032 | 0.003 |
| Apopka (2021-08-18) | P | PERSISTENCE  (3) | 141 | 0.397 | 0.397 | 0.000 | 0.032 | 0.003 |
| Harris (2018-06-18) | S | SINGLE 2018-06-23 (5) | 111 | 0.351 | 0.406 | 0.135 | 0.026 | 0.001 |
| Harris (2018-06-18) | A | FALLBACK 2018-06-18 (0) | 111 | 0.180 | 0.303 | 0.405 | 0.018 | 0.001 |
| Harris (2018-06-18) | P | PERSISTENCE  (None) | 111 | 0.180 | 0.303 | 0.405 | 0.018 | 0.001 |
| Panasoffkee (2022-05-10) | S | SINGLE 2022-05-28 (18) | 222 | 0.059 | 0.062 | 0.059 | 0.006 | 0.006 |
| Panasoffkee (2022-05-10) | A | NONE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Panasoffkee (2022-05-10) | P | PERSISTENCE  (None) | 222 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Yale (2023-07-27) | S | SINGLE 2023-08-11 (15) | 74 | 0.459 | 0.507 | 0.095 | 0.005 | 0.000 |
| Yale (2023-07-27) | A | ACCEPTED 2023-08-11 (15) | 74 | 0.459 | 0.507 | 0.095 | 0.005 | 0.000 |
| Yale (2023-07-27) | P | PERSISTENCE  (15) | 74 | 0.459 | 0.507 | 0.095 | 0.005 | 0.000 |
| Cypress (2022-06-29) | S | SINGLE 2022-06-17 (12) | 162 | 0.593 | 0.696 | 0.148 | 0.012 | 0.500 |
| Cypress (2022-06-29) | A | NONE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| Cypress (2022-06-29) | P | PERSISTENCE  (None) | 162 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |

Pooled (cell-weighted) recall on surface point cells:

| obs | recall (UNKNOWN=miss) | recall (known only) | gap <= 7 d | gap 8-21 d | submersed-only cells flagged |
|---|---|---|---|---|---|
| S | 378/1127 = 0.335 | 378/940 = 0.402 | 235/669 = 0.351 | 143/458 = 0.312 | 258/9974 = 0.026 |
| A | 250/1127 = 0.222 | 250/563 = 0.444 | 216/669 = 0.323 | 34/74 = 0.459 | 224/9974 = 0.022 |
| P | 250/1127 = 0.222 | 250/563 = 0.444 | 93/282 = 0.330 | 34/74 = 0.459 | 224/9974 = 0.022 |

Observations: (i) recall in Florida is 0.12-0.34 before and after every guard variant; the best case (bare production, gate off, S) is 0.335, half the 0.70 bar; (ii) the guards turn most of the missing recall into UNKNOWN (known-only recall 0.38-0.47) rather than into correct "no vegetation" calls, so an honest Brain would publish "could not look" for most Florida point cells; (iii) Harris (gate rejects 2 of 8 scenes; the others are cloudy) and Cypress (gate rejects 6 of 14 scenes, every summer scene) end with NO_SCENE for S; Panasoffkee's only usable scene is 18 d from the survey (S recall 0.03, A none); (iv) submersed-only cells are flagged at 1-3 %, i.e. the observer does not see submerged plants, as intended; (v) gap <= 7 d vs 8-21 d is reported in the pooled tables above (A at 8-21 d is 0.43 only because it is one lake, Yale).

## 5. Replica (note 05) vs production

Per-scene cell comparison of `cell_lib.py` outputs (note 05's `out/cell_*.npz`) with the imported production `s2_pass` on the same cached windows and the same 50 m frame (frames identical, 12 lakes):

`{"scenes": 215, "cells": 2119474, "vote_diff": 11, "gfrac_diff": 299, "nan_diff": 0, "read_diff": 12, "scenes_with_any_diff": 10, "maxabs": 0.10602837800979614}`

i.e. 11 grass votes differ in 2,119,474 lake-cell x scene pairs; all 11 are in two 2022 FWC lakes (Orange 8, Cypress 3) whose caches hold the offset-free collection (most likely the reflectance -> DN -> reflectance round trip and the 20 m grid phase of the cached window moving a few cells across the 0.30 / 0.5 thresholds; not isolated; max |gfrac| difference 0.106); Snohomish (c1 collection) is bit-identical (0 differences in 118 scenes). Re-running note 05's own metric code on production arrays:

| method (Snohomish, +-45 d, grass-eligible cells, TP/FP/FN) | note 05 original | production arrays |
|---|---|---|
| single, closest clear date | 60/51/0 P 0.541 F1 0.702 | 60/51/0 P 0.541 F1 0.702 |
| SHIPPED-style pass (cov>=0.5) | 60/5/0 P 0.923 F1 0.96 | 60/5/0 P 0.923 F1 0.960 |
| median g' >= 0.5 | 60/0/0 P 1.0 F1 1.0 | 60/0/0 P 1.000 F1 1.000 |
| max g' >= 0.5 (negative control) | 60/228/0 P 0.208 F1 0.345 | 60/228/0 P 0.208 F1 0.345 |

FWC surface recall with note 05's methods: original single 0.320 / shipped-style 0.322 / median 0.432; production arrays 0.320 / 0.322 / 0.432; with the production SWIR-DN gate applied (rejected scenes removed) 0.324 / 0.338 / 0.449. PAC lake-level (note 05: rho 0.43 / 0.35, AUC 0.79 / 0.65, 130 lake-years): production arrays, S, gate off, 130 lake-years, rho 0.43 / 0.36, AUC 0.78 / 0.66.

**Conclusion of the difference check:** the replica was faithful for everything it replicated. What the replica could not show, and production adds, is (a) the **whole-scene SWIR-DN gate** (`PassRejected`), (b) the production `hidden`/`near` plumbing, and (c) in `build_clarity`, the borrow and bed-to-bank steps. Windows are shared (lake bbox + ~200 m, not production's 1 km pad), so standoff distances at the window edge are truncated in both; tile blending is exercised only by the Guntersville pilot (one pass with two T16SED granules, 2025-10-10).

### End-to-end `build_clarity` (production walk, 36 m frame, Snohomish)

`until` = survey date (production takes the newest accepted pass up to `until`):

| lake | pass used | open-water read | grass % of lake (of which bed-to-bank strip) | whole-lake truth+ / TP / FP | P, R whole lake | clarity-40 m truth+ / TP / FP | P, R clarity-40 m |
|---|---|---|---|---|---|---|---|
| Serene | none: `no clear Sentinel-2 pass in the window` | | | | | | |
| Blackmans | 2023-07-31 | 57.8% | 31.5% (24.3%) | 41 / 41 / 1 | 0.976, 1.0 | 9 / 9 / 0 | 1.0, 1.0 |
| Storm | 2023-08-15 | 75.7% | 0.0% (0.0%) | 0 / 0 / 0 | 0.0, 0.0 | 0 / 0 / 0 | 0.0, 0.0 |
| Roesiger | 2021-07-11 | 59.5% | 12.5% (5.8%) | 179 / 179 / 2 | 0.989, 1.0 | 107 / 107 / 2 | 0.982, 1.0 |
| Bosworth | 2023-07-31 | 47.8% | 13.7% (12.0%) | 10 / 10 / 7 | 0.588, 1.0 | 0 / 0 / 3 | 0.0, 0.0 |


`until` = survey date + 7 d:

| lake | pass used | open-water read | grass % of lake (of which bed-to-bank strip) | whole-lake truth+ / TP / FP | P, R whole lake | clarity-40 m truth+ / TP / FP | P, R clarity-40 m |
|---|---|---|---|---|---|---|---|
| Serene | none: `no clear Sentinel-2 pass in the window` | | | | | | |
| Blackmans | 2023-07-31 | 57.8% | 31.5% (24.3%) | 41 / 41 / 1 | 0.976, 1.0 | 9 / 9 / 0 | 1.0, 1.0 |
| Storm | 2023-08-15 | 75.7% | 0.0% (0.0%) | 0 / 0 / 0 | 0.0, 0.0 | 0 / 0 / 0 | 0.0, 0.0 |
| Roesiger | 2021-07-24 | 54.0% | 17.1% (9.5%) | 179 / 179 / 69 | 0.722, 1.0 | 107 / 107 / 17 | 0.863, 1.0 |
| Bosworth | 2023-08-03 | 45.4% | 29.5% (24.7%) | 10 / 10 / 32 | 0.238, 1.0 | 0 / 0 / 18 | 0.0, 0.0 |


Whole-lake numbers here include the "bed run to the bank" strip (6-25 % of lake area) and grass-under-cloud borrow: a proximity rule, not an observation. They show the production A-walk is sensitive to which side of a surface it lands on (Roesiger 2021-07-11 gives whole-lake precision 0.99; 2021-07-24 gives 0.72), and Serene never gets a pass at >= 0.25 coverage.

## 6. Unknown / refusal accounting

Share of **all lake cells** (incl. the shore band) by outcome for the selected single scene (S) and accepted pass (A); first-hit attribution.

### SWIR-DN scene gate (dws.s2_pass: median SWIR DN over SCL water must be 900-1500)

| dataset | scenes within +-21 d | rejected by gate | lakes with >=1 rejected | plant-flag share of clarity cells, gate-rejected scenes (median) | same, accepted scenes (median) |
|---|---|---|---|---|---|
| snoco | 60 | 0 | 0 / 5 | nan | 0.086 |
| fwc_points | 48 | 7 | 3 / 7 | 0.097 | 0.011 |
| fwc_pac (scene x lake-year pairs) | 482 | 116 | 42 / 51 | 0.009 | 0.010 |

### UNKNOWN / refusal accounting, prereg guards as written: share of ALL lake cells (incl. shore band), selected scene (S) and accepted pass (A)

| dataset | obs | SHORE_ADJACENT | NO_DATA_OFF_SWATH | CLOUD_SHADOW_STANDOFF | HAZE_OR_CLOUD_EDGE_STANDOFF | DARK_WATER | NO_SCENE | PASS_NOT_ACCEPTED | CLEAR | FLAG | UNKNOWN total | lakes w/o scene |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| snoco (5 units) | S | 30.3% | 0.0% | 0.0% | 5.8% | 40.4% | 0.0% | 0.0% | 15.5% | 7.9% | 76.5% | 0 |
| snoco (5 units) | A | 30.3% | 0.0% | 0.0% | 0.2% | 57.9% | 0.0% | 4.0% | 2.7% | 5.0% | 92.3% | 1 |
| fwc_points (7 units) | S | 3.7% | 1.9% | 2.7% | 14.1% | 2.1% | 27.5% | 0.0% | 46.9% | 1.1% | 52.0% | 2 |
| fwc_points (7 units) | A | 3.7% | 1.9% | 10.4% | 20.8% | 2.1% | 0.0% | 8.1% | 52.0% | 1.0% | 47.0% | 2 |
| fwc_pac (143 units) | S | 4.8% | 0.9% | 7.4% | 32.1% | 3.0% | 19.4% | 0.0% | 27.7% | 4.6% | 67.7% | 29 |
| fwc_pac (143 units) | A | 4.8% | 2.5% | 6.1% | 21.8% | 3.3% | 0.0% | 26.0% | 31.9% | 3.5% | 64.6% | 60 |

### UNKNOWN / refusal accounting, bare production: share of ALL lake cells (incl. shore band), selected scene (S) and accepted pass (A)

| dataset | obs | SHORE_ADJACENT | NO_DATA_OFF_SWATH | CLOUD_SHADOW_STANDOFF | HAZE_OR_CLOUD_EDGE_STANDOFF | DARK_WATER | NO_SCENE | PASS_NOT_ACCEPTED | CLEAR | FLAG | UNKNOWN total | lakes w/o scene |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| snoco (5 units) | S | 30.3% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 61.4% | 8.3% | 30.3% | 0 |
| snoco (5 units) | A | 30.3% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 4.0% | 60.9% | 4.8% | 34.3% | 1 |
| fwc_points (7 units) | S | 3.7% | 1.9% | 2.3% | 0.0% | 0.0% | 27.5% | 0.0% | 62.9% | 1.7% | 35.4% | 2 |
| fwc_points (7 units) | A | 3.7% | 1.9% | 9.4% | 0.0% | 0.0% | 0.0% | 8.1% | 75.1% | 1.7% | 23.1% | 2 |
| fwc_pac (143 units) | S | 4.8% | 0.9% | 6.5% | 0.0% | 0.0% | 19.4% | 0.0% | 62.4% | 6.1% | 31.6% | 29 |
| fwc_pac (143 units) | A | 4.8% | 2.4% | 5.4% | 0.0% | 0.0% | 0.0% | 25.6% | 57.2% | 4.5% | 38.2% | 59 |

### UNKNOWN / refusal accounting, v1 with dark-water fix: share of ALL lake cells (incl. shore band), selected scene (S) and accepted pass (A)

| dataset | obs | SHORE_ADJACENT | NO_DATA_OFF_SWATH | CLOUD_SHADOW_STANDOFF | HAZE_OR_CLOUD_EDGE_STANDOFF | DARK_WATER | NO_SCENE | PASS_NOT_ACCEPTED | CLEAR | FLAG | UNKNOWN total | lakes w/o scene |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| snoco (5 units) | S | 30.3% | 0.0% | 0.0% | 5.8% | 0.0% | 0.0% | 0.0% | 56.4% | 7.5% | 36.1% | 0 |
| snoco (5 units) | A | 30.3% | 0.0% | 0.0% | 0.2% | 0.0% | 0.0% | 4.0% | 60.8% | 4.7% | 34.5% | 1 |
| fwc_points (7 units) | S | 3.7% | 1.9% | 2.7% | 14.1% | 0.0% | 27.5% | 0.0% | 49.0% | 1.1% | 49.9% | 2 |
| fwc_points (7 units) | A | 3.7% | 1.9% | 10.4% | 20.8% | 0.0% | 0.0% | 8.1% | 54.1% | 1.0% | 44.9% | 2 |
| fwc_pac (143 units) | S | 4.8% | 0.9% | 7.4% | 32.1% | 0.0% | 19.4% | 0.0% | 30.7% | 4.6% | 64.7% | 29 |
| fwc_pac (143 units) | A | 4.8% | 2.5% | 6.1% | 21.8% | 0.0% | 0.0% | 26.0% | 35.3% | 3.5% | 61.2% | 60 |

### Non-exclusive guard hit frequency, clarity-mask cells, all scenes within +-21 d (bare production flags + prereg-only guards)

| dataset | cloud/shadow/insufficient (seen<50%) | no data | hidden (cloud edge/600 m standoff/haze) | of which near real cloud | dark-water (>=50% of seen px) | glint-like SWIR>0.0215 (>=50%) |
|---|---|---|---|---|---|---|
| snoco | 14.0% | 0.0% | 20.8% | 15.4% | 44.9% | 8.2% |
| fwc_points | 38.4% | 4.1% | 66.5% | 60.6% | 1.0% | 15.2% |
| fwc_pac | 34.4% | 6.5% | 65.4% | 58.1% | 4.1% | 19.7% |

### Pass acceptance (coverage of non-plant water) per dataset, scenes within +-21 d, bare production

| dataset | scenes | cov >= 0.50 | 0.25 <= cov < 0.50 | cov < 0.25 | median cov |
|---|---|---|---|---|---|
| snoco | 60 | 25% | 27% | 48% | 0.30 |
| fwc_points | 48 | 12% | 17% | 71% | 0.00 |
| fwc_pac (scene x lake-year) | 482 | 11% | 11% | 78% | 0.01 |


Highlights: the shore band alone is 30 % of Snohomish lake cells (3.7-4.8 % in the larger Florida lakes). Under `v1` the DARK_WATER guard turns 40 % (S) to 58 % (A) of Snohomish cells UNKNOWN and fires on 45 % of all clarity-cell x scene observations, versus 1-4 % in Florida; the HAZE/standoff guard (production `hidden`) hits 65-67 % of Florida cell-scene observations (60 % of them near a real cloud) and holds 14 % (FWC points, S) to 32 % (PAC, S) of cells UNKNOWN in the selected scene. Cloud/shadow proper (seen < 50 %) is 2-7 % of the selected scene and 34-38 % of all Florida observations. NO_SCENE affects 2 of 7 FWC point lakes (S and A) and 29 (S) / 60 (A) of 143 PAC lake-years. GLARE: not separable (section 2.2).

## 7. FWC LTM lake-level sonar PAC / PVI (143 lake-years, 52 lakes with a cache; Okeechobee excluded)

Observer S/A/P lake score vs sonar PVI and PAC. A "refused" lake-year is one where the observer returned no scene, or fewer than 50 % of the clarity cells were known. P is INSUFFICIENT in **every** lake-year (the lean caches hold <= 2 clear scenes per lake-year, so no lake-year has 3 accepted scenes): **P = A on this set; persistence is not testable here**.

**Primary (`v1`, gate on):**

**PAC/PVI, PRIMARY v1, 50 m** (`pac_50_v1_rej0.json`)

| obs | lake-years scored (lakes) | refused lake-years | Spearman vs PVI [95% lake-bootstrap] | Spearman vs PAC [95%] | AUC PVI>=20 vs <5 (n) [95%] | AUC PAC>=50 vs <20 (n) [95%] | per-lake-mean rho PVI | belt (40-90 m) rho PVI | rho PVI gap<=7 d (n) | rho PVI gap 8-21 d (n) |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 35 (22) | 108 {'TOO_FEW_KNOWN_CELLS': 79, 'NO_SCENE/NOT_ACCEPTED': 29} | 0.29 [-0.16, 0.62] | 0.24 [-0.24, 0.59] | 0.70 (7/13) [0.33, 0.97] | 0.59 (10/16) [0.31, 0.88] | 0.32 | 0.12 | -0.02 (22) | 0.76 (13) |
| A | 39 (21) | 104 {'TOO_FEW_KNOWN_CELLS': 44, 'NO_SCENE/NOT_ACCEPTED': 60} | 0.35 [-0.02, 0.67] | 0.24 [-0.19, 0.66] | 0.85 (7/16) [0.55, 1.00] | 0.62 (12/20) [0.34, 0.92] | 0.36 | 0.15 | 0.15 (23) | 0.68 (16) |
| P | 39 (21) | 104 {'TOO_FEW_KNOWN_CELLS': 104} | 0.35 [-0.02, 0.67] | 0.24 [-0.19, 0.66] | 0.85 (7/16) [0.55, 1.00] | 0.62 (12/20) [0.34, 0.92] | 0.36 | 0.15 | 0.12 (20) | 0.74 (10) |

**Bare production, gate on (exact production behaviour, no prereg-only guards):**

**PAC/PVI, bare production** (`pac_50_prod_rej0.json`)

| obs | lake-years scored (lakes) | refused lake-years | Spearman vs PVI [95% lake-bootstrap] | Spearman vs PAC [95%] | AUC PVI>=20 vs <5 (n) [95%] | AUC PAC>=50 vs <20 (n) [95%] | per-lake-mean rho PVI | belt (40-90 m) rho PVI | rho PVI gap<=7 d (n) | rho PVI gap 8-21 d (n) |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 114 (47) | 29 {'NO_SCENE/NOT_ACCEPTED': 29} | 0.39 [0.11, 0.65] | 0.32 [0.05, 0.58] | 0.74 (23/39) [0.49, 0.92] | 0.64 (37/44) [0.44, 0.84] | 0.40 | 0.30 | 0.32 (74) | 0.53 (40) |
| A | 82 (36) | 61 {'TOO_FEW_KNOWN_CELLS': 2, 'NO_SCENE/NOT_ACCEPTED': 59} | 0.41 [0.08, 0.69] | 0.39 [0.07, 0.68] | 0.75 (15/35) [0.49, 0.95] | 0.65 (23/39) [0.42, 0.88] | 0.44 | 0.33 | 0.28 (43) | 0.57 (39) |
| P | 82 (36) | 61 {'TOO_FEW_KNOWN_CELLS': 61} | 0.41 [0.08, 0.69] | 0.39 [0.07, 0.68] | 0.75 (15/35) [0.49, 0.95] | 0.65 (23/39) [0.42, 0.88] | 0.44 | 0.33 | 0.10 (26) | 0.28 (17) |

**Bare production, gate off (note 05's setting):**

**PAC/PVI, bare production, gate OFF (sensitivity)** (`pac_50_prod_rej1.json`)

| obs | lake-years scored (lakes) | refused lake-years | Spearman vs PVI [95% lake-bootstrap] | Spearman vs PAC [95%] | AUC PVI>=20 vs <5 (n) [95%] | AUC PAC>=50 vs <20 (n) [95%] | per-lake-mean rho PVI | belt (40-90 m) rho PVI | rho PVI gap<=7 d (n) | rho PVI gap 8-21 d (n) |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 130 (51) | 13 {'NO_SCENE/NOT_ACCEPTED': 13} | 0.43 [0.16, 0.66] | 0.36 [0.10, 0.59] | 0.78 (27/44) [0.54, 0.93] | 0.66 (43/51) [0.46, 0.83] | 0.42 | 0.35 | 0.38 (93) | 0.57 (37) |
| A | 82 (36) | 61 {'NO_SCENE/NOT_ACCEPTED': 59, 'TOO_FEW_KNOWN_CELLS': 2} | 0.41 [0.08, 0.69] | 0.39 [0.07, 0.68] | 0.75 (15/35) [0.49, 0.95] | 0.65 (23/39) [0.42, 0.88] | 0.44 | 0.33 | 0.28 (43) | 0.57 (39) |
| P | 82 (36) | 61 {'TOO_FEW_KNOWN_CELLS': 61} | 0.41 [0.08, 0.69] | 0.39 [0.07, 0.68] | 0.75 (15/35) [0.49, 0.95] | 0.65 (23/39) [0.42, 0.88] | 0.44 | 0.33 | 0.10 (26) | 0.28 (17) |

**`v1` with the dark-water fix:**

**PAC/PVI, v1 with dark fix** (`pac_50_v1fix_rej0.json`)

| obs | lake-years scored (lakes) | refused lake-years | Spearman vs PVI [95% lake-bootstrap] | Spearman vs PAC [95%] | AUC PVI>=20 vs <5 (n) [95%] | AUC PAC>=50 vs <20 (n) [95%] | per-lake-mean rho PVI | belt (40-90 m) rho PVI | rho PVI gap<=7 d (n) | rho PVI gap 8-21 d (n) |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 47 (29) | 96 {'TOO_FEW_KNOWN_CELLS': 67, 'NO_SCENE/NOT_ACCEPTED': 29} | 0.15 [-0.20, 0.47] | 0.08 [-0.28, 0.43] | 0.61 (11/14) [0.31, 0.86] | 0.47 (15/18) [0.22, 0.76] | 0.15 | 0.02 | -0.09 (29) | 0.51 (18) |
| A | 54 (28) | 89 {'TOO_FEW_KNOWN_CELLS': 29, 'NO_SCENE/NOT_ACCEPTED': 60} | 0.20 [-0.10, 0.49] | 0.11 [-0.21, 0.45] | 0.69 (10/19) [0.39, 0.92] | 0.50 (17/24) [0.26, 0.78] | 0.20 | 0.09 | 0.10 (30) | 0.43 (24) |
| P | 54 (28) | 89 {'TOO_FEW_KNOWN_CELLS': 89} | 0.20 [-0.10, 0.49] | 0.11 [-0.21, 0.45] | 0.69 (10/19) [0.39, 0.92] | 0.50 (17/24) [0.26, 0.78] | 0.20 | 0.09 | 0.01 (26) | 0.23 (17) |

Reading: the lake-level agreement is moderate and it is carried by the production pixel rule, not by the guards. Gate on or off barely moves rho (0.39 vs 0.43), but the prereg guards cut the scorable lake-years from 114-130 to 35-39 (they refuse 79 lake-years (S) for "< 50 % of cells known"; the HAZE/standoff guard alone holds 32 % of the selected-scene cells UNKNOWN), and rho falls to 0.29-0.35 with a bootstrap interval that includes zero. The dark fix does not rescue it (rho 0.15-0.20, n 47-54): the remaining refusals are the HAZE/standoff and the cloud guards, so the scored lake-years are a selected subset (which kind was not examined). Gap strata are noisy (rho 0.32-0.38 at <= 7 d, 0.53-0.57 at 8-21 d, bare production). None of this is a gate (the prereg's lake-level gate is NLA, not sonar); against that gate's thresholds (AUC >= 0.80, Spearman >= 0.50) the sonar numbers would not pass, but sonar PAC/PVI measure canopy volume that includes submerged plants, which this observer cannot see by design.

## 8. Gate-by-gate, prereg section 5

Primary configuration unless stated. "Provisional" = computed but the evidence base is too thin to carry a claim.

| gate | requirement | result here | verdict |
|---|---|---|---|
| **(a)** cell precision >= 0.80 and recall >= 0.70, pooled and for **each** of >= 3 independent truth lakes with >= 30 positive cells | data needed: 3 lakes x >= 30 positive cells | Only **Roesiger** (54 reachable positive cells; 88 whole-lake) has >= 30; Blackmans has 6 (17 whole-lake); Serene, Storm, Bosworth have 0 reachable. At 36 m: Roesiger 107, Blackmans 9 reachable (41 whole-lake), still 1-2 lakes. Pooled (60 positives, one lake dominates): A precision 0.92 raw / 0.85 shore-matched-raw-prevalence, recall 1.00; P 0.97 / 0.94, 1.00; S 0.58 / 0.45, 1.00. FWC points: recall 0.12-0.34 (recall criterion would fail in that class). Whole-lake recall 0.51. | **NOT_TESTABLE** (not relaxed). Informational: S fails precision; A, P pass in the single testable lake; Florida recall fails; whole-lake recall fails if that is the intended population. |
| **(b)** open-water FPR <= 2 % (cell level) | flagged / verified open-water cells | S **3.2 %** (1331 strict-none cells; 43 false cells, 39 of them in the Storm burst); A **0.4 %**; P **0.2 %**. Bare production S 3.8 %, A 0.4 %, P 0.0 %. Known-only FPR under `v1` is S 12 %, A 9.8 %, P 3.6 %, because 73-96 % of the verified open-water cells are UNKNOWN (dark-water guard) and the denominator shrinks to ~50 cells for A and P; under bare production (S 3.8 %, A 0.4 %, P 0.0 %) and the dark fix (S 3.4 %, A 0.2 %, P 0.0 %) known-only is within a hair of all-cells. Open-water truth exists only for 5 small clear lakes with assumed absence; none is turbid or Florida. | **S FAIL. A, P: provisional PASS** on the literal all-cells denominator and with bare production / dark fix; **FAIL on a known-cells denominator under `v1` as written** (the verdict depends on the guard design); evidence is 5 small clear PNW lakes only |
| **(c)** NLA lake-level AUC >= 0.80 and Spearman >= 0.50 on >= 15 eligible lakes in >= 3 regions | NLA 2017 x S2 (+-21 d) | not run in this task (out of scope). Sonar PAC/PVI, for information only: rho 0.29-0.43, AUC 0.70-0.85 (n 35-130 lake-years), not NLA. | **NOT_RUN** |
| **(d)** negative-control lakes flagged share <= 2 % | NLA all-zero lakes | not run. For information only: unsurveyed (not verified-empty) FWC cells are flagged at 0.0-1.8 % per lake (S, v1). | **NOT_RUN** |
| **(e)** lower bootstrap bound of pooled F1 >= 0.65 | bootstrap over lakes, 2,000 resamples | computed over 5 lakes of which 2 carry positives (resamples with no positive lake have no F1 and are skipped; 1,858 of 2,000 are defined): lower bound S 0.66, A 1.00, P 1.00 (shore-matched, 50 % prevalence; at raw prevalence the pooled F1 is S 0.62, A 0.92, P 0.97). An interval from 2 effective lakes is not an estimate of population performance. | **NOT_TESTABLE** |

**State.** `RESEARCH` entry ("observer reproduced from production code and scored once on >= 2 independent truth sets; report committed"): reproduction by import: done; scored on three independent truth sets: done (Snohomish cells, FWC points recall, FWC sonar lake-level); "report committed": this note lives in the research data folder, not in the repo (no repo write allowed here), so the commit step belongs to the repo owner. `CALIBRATION` (thresholds fixed on a disjoint calibration subset, >= 10 truth lakes): not reached; nothing was tuned, and there is no calibration/evaluation split. `PARTIAL` and `VALIDATED`: not reached. If a `PARTIAL` claim were ever made on these data it could cover at most **clear-water floating-leaf beds in Pacific Northwest lakes** and nothing in Florida.

## 9. Guntersville pilot (UNVALIDATED, no ground truth; sanity check only)

Lake Guntersville AL, **central/lower reach only** (production polygon `Guntersville|AL` clipped to lon -86.30..-86.00, lat 34.40..34.66; the whole 266 km2 lake would need > 2 GB of windowed reads). Because the polygon is clipped, the cut lines behave like shore (SHORE_ADJACENT) and plants beyond the cut are not seen. This pilot uses the **real** production reader and the real Earth Search query (`sentinel-2-c1-l2a`, tile T16SED, 1 Apr to 31 Oct 2025, scene cloud <= 30 %), 50 m frame, no cache of raw scenes (about 0.6 GB transferred, new arrays `out/cells50_guntersville_central.npz`). Nothing here says what is on the water: no survey was compared.

Lake Guntersville central/lower reach (clipped polygon, 71402 lake cells, 61893 clarity cells), Sentinel-2 C1 L2A, passes with scene cloud <= 30 %: 40 passes, 37 read, 3 rejected by the production SWIR-DN gate.

**mode v1**: scene-level (every pass; clear = lake cells seen; cov = pass-acceptance coverage; flagged % = flagged / known clarity cells; unknown % = share of clarity cells UNKNOWN)

| date | gate | clear | cov | accepted | flagged % of known | flagged % of clarity cells | UNKNOWN % | haze/cloud-edge | dark | cloud/shadow |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-04-08 | ok | 0.94 | 0.01 | n | 4.8 | 0.6 | 88 | 82 | 0 | 6 |
| 2025-04-08 | ok | 0.90 | 0.43 | n | 1.1 | 0.5 | 52 | 41 | 0 | 11 |
| 2025-04-13 | ok | 1.00 | 0.75 | Y | 2.1 | 1.8 | 12 | 12 | 0 | 0 |
| 2025-04-15 | ok | 0.99 | 0.15 | n | 6.2 | 1.7 | 72 | 72 | 0 | 1 |
| 2025-04-16 | ok | 1.00 | 0.46 | n | 3.3 | 2.0 | 39 | 39 | 0 | 0 |
| 2025-04-28 | ok | 1.00 | 0.20 | n | 9.0 | 3.6 | 61 | 60 | 0 | 0 |
| 2025-04-28 | ok | 1.00 | 0.81 | Y | 4.4 | 4.0 | 9 | 9 | 0 | 0 |
| 2025-05-06 | ok | 0.98 | 0.48 | n | 4.5 | 2.8 | 39 | 37 | 0 | 2 |
| 2025-06-02 | ok | 1.00 | 0.53 | Y | 6.6 | 5.0 | 24 | 24 | 0 | 0 |
| 2025-06-22 | ok | 0.98 | 0.72 | Y | 8.2 | 6.7 | 19 | 17 | 0 | 1 |
| 2025-07-02 | ok | 0.98 | 0.72 | Y | 8.6 | 6.6 | 23 | 19 | 2 | 2 |
| 2025-07-04 | ok | 0.82 | 0.47 | n | 7.6 | 4.0 | 47 | 28 | 0 | 19 |
| 2025-07-07 | ok | 0.94 | 0.76 | Y | 5.8 | 4.8 | 18 | 12 | 0 | 6 |
| 2025-07-12 | ok | 0.83 | 0.05 | n | 33.8 | 3.5 | 90 | 72 | 0 | 17 |
| 2025-07-15 | ok | 0.76 | 0.12 | n | 14.3 | 2.1 | 86 | 60 | 0 | 26 |
| 2025-07-24 | ok | 0.48 | 0.03 | n | 45.5 | 2.4 | 95 | 41 | 0 | 54 |
| 2025-08-16 | ok | 1.00 | 0.89 | Y | 12.8 | 12.6 | 1 | 1 | 0 | 0 |
| 2025-08-19 | ok | 0.97 | 0.60 | Y | 14.6 | 10.3 | 30 | 28 | 0 | 2 |
| 2025-08-29 | ok | 1.00 | 0.34 | n | 25.8 | 13.1 | 49 | 48 | 1 | 0 |
| 2025-08-31 | ok | 1.00 | 0.88 | Y | 13.4 | 13.2 | 2 | 2 | 0 | 0 |
| 2025-09-08 | ok | 0.79 | 0.04 | n | 51.1 | 6.9 | 87 | 64 | 0 | 22 |
| 2025-09-10 | ok | 1.00 | 0.89 | Y | 13.2 | 13.1 | 1 | 1 | 0 | 0 |
| 2025-09-13 | ok | 0.98 | 0.72 | Y | 14.3 | 11.6 | 19 | 17 | 0 | 1 |
| 2025-09-15 | ok | 1.00 | 0.86 | Y | 13.0 | 12.6 | 3 | 3 | 0 | 0 |
| 2025-09-15 | ok | 1.00 | 0.89 | Y | 12.9 | 12.8 | 1 | 1 | 0 | 0 |
| 2025-09-18 | ok | 1.00 | 0.85 | Y | 13.6 | 12.8 | 6 | 6 | 0 | 0 |
| 2025-09-20 | ok | 1.00 | 0.86 | Y | 12.6 | 12.3 | 2 | 2 | 0 | 0 |
| 2025-09-28 | ok | 1.00 | 0.81 | Y | 14.3 | 12.8 | 11 | 10 | 0 | 0 |
| 2025-10-03 | ok | 0.92 | 0.73 | Y | 11.1 | 8.8 | 21 | 12 | 1 | 8 |
| 2025-10-10 | ok | 1.00 | 0.88 | Y | 28.4 | 10.0 | 65 | 0 | 2 | 63 |
| 2025-10-12 | ok | 1.00 | 0.92 | Y | 14.8 | 13.8 | 6 | 0 | 6 | 0 |
| 2025-10-13 | ok | 1.00 | 0.92 | Y | 15.0 | 14.1 | 6 | 0 | 6 | 0 |
| 2025-10-15 | ok | 1.00 | 0.92 | Y | 14.6 | 13.6 | 7 | 0 | 7 | 0 |
| 2025-10-15 | ok | 1.00 | 0.91 | Y | 14.6 | 13.3 | 9 | 0 | 9 | 0 |
| 2025-10-20 | ok | 1.00 | 0.91 | Y | 13.9 | 12.4 | 10 | 0 | 10 | 0 |
| 2025-10-23 | ok | 1.00 | 0.89 | Y | 11.8 | 11.4 | 3 | 1 | 2 | 0 |
| 2025-10-25 | ok | 0.95 | 0.56 | Y | 11.0 | 7.0 | 36 | 29 | 0 | 7 |

**mode v1**: observers by month (reference = 15th, window +-21 d, production gate ON)

| month | candidate passes in window | gate-rejected | accepted (cov>=0.5) | S: scene gap, flagged % known, UNKNOWN % | A: scene gap/kind, flagged % known, UNKNOWN % | P: n accepted / status, flagged % known, UNKNOWN % |
|---|---|---|---|---|---|---|
| 2025-04 | 8 | 0 | 2 | gap 0d, 6.2%, 72% | 2d ACCEPTED, 2.1%, 12% | 2 / INSUFFICIENT, 2.1%, 12% |
| 2025-05 | 6 | 2 | 2 | gap 9d, 4.5%, 39% | 17d ACCEPTED, 4.4%, 9% | 2 / INSUFFICIENT, 4.4%, 9% |
| 2025-06 | 6 | 2 | 3 | gap 7d, 8.2%, 19% | 7d ACCEPTED, 8.2%, 19% | 3 / MEDIAN_OF_ACCEPTED, 8.1%, 19% |
| 2025-07 | 7 | 1 | 2 | gap 0d, 14.3%, 86% | 8d ACCEPTED, 5.8%, 18% | 2 / INSUFFICIENT, 5.8%, 18% |
| 2025-08 | 4 | 0 | 3 | gap 1d, 12.8%, 1% | 1d ACCEPTED, 12.8%, 1% | 3 / MEDIAN_OF_ACCEPTED, 12.9%, 1% |
| 2025-09 | 11 | 0 | 9 | gap 0d, 13.0%, 3% | 0d ACCEPTED, 13.0%, 3% | 9 / MEDIAN_OF_ACCEPTED, 13.2%, 0% |
| 2025-10 | 10 | 0 | 10 | gap 0d, 14.6%, 7% | 0d ACCEPTED, 14.6%, 7% | 10 / MEDIAN_OF_ACCEPTED, 13.7%, 1% |

**mode prod**: scene-level (every pass; clear = lake cells seen; cov = pass-acceptance coverage; flagged % = flagged / known clarity cells; unknown % = share of clarity cells UNKNOWN)

| date | gate | clear | cov | accepted | flagged % of known | flagged % of clarity cells | UNKNOWN % | haze/cloud-edge | dark | cloud/shadow |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-04-08 | ok | 0.94 | 0.01 | n | 0.8 | 0.7 | 4 | 0 | 0 | 4 |
| 2025-04-08 | ok | 0.90 | 0.43 | n | 0.7 | 0.7 | 9 | 0 | 0 | 9 |
| 2025-04-13 | ok | 1.00 | 0.75 | Y | 1.9 | 1.9 | 0 | 0 | 0 | 0 |
| 2025-04-15 | ok | 0.99 | 0.15 | n | 1.9 | 1.9 | 0 | 0 | 0 | 0 |
| 2025-04-16 | ok | 1.00 | 0.46 | n | 2.1 | 2.1 | 0 | 0 | 0 | 0 |
| 2025-04-28 | ok | 1.00 | 0.20 | n | 4.0 | 3.9 | 0 | 0 | 0 | 0 |
| 2025-04-28 | ok | 1.00 | 0.81 | Y | 4.1 | 4.1 | 0 | 0 | 0 | 0 |
| 2025-05-06 | ok | 0.98 | 0.49 | n | 3.3 | 3.3 | 1 | 0 | 0 | 1 |
| 2025-06-02 | ok | 1.00 | 0.53 | Y | 5.4 | 5.4 | 0 | 0 | 0 | 0 |
| 2025-06-22 | ok | 0.98 | 0.73 | Y | 7.8 | 7.7 | 1 | 0 | 0 | 1 |
| 2025-07-02 | ok | 0.98 | 0.73 | Y | 8.0 | 7.9 | 2 | 0 | 0 | 2 |
| 2025-07-04 | ok | 0.82 | 0.48 | n | 6.8 | 5.6 | 17 | 0 | 0 | 17 |
| 2025-07-07 | ok | 0.94 | 0.77 | Y | 6.6 | 6.3 | 5 | 0 | 0 | 5 |
| 2025-07-12 | ok | 0.83 | 0.05 | n | 7.6 | 6.5 | 15 | 0 | 0 | 15 |
| 2025-07-15 | ok | 0.76 | 0.13 | n | 7.3 | 5.6 | 23 | 0 | 0 | 23 |
| 2025-07-24 | ok | 0.48 | 0.03 | n | 9.0 | 4.5 | 50 | 0 | 0 | 50 |
| 2025-08-16 | ok | 1.00 | 0.89 | Y | 12.7 | 12.7 | 0 | 0 | 0 | 0 |
| 2025-08-19 | ok | 0.97 | 0.61 | Y | 12.6 | 12.4 | 2 | 0 | 0 | 2 |
| 2025-08-29 | ok | 1.00 | 0.34 | n | 13.4 | 13.4 | 0 | 0 | 0 | 0 |
| 2025-08-31 | ok | 1.00 | 0.88 | Y | 13.5 | 13.5 | 0 | 0 | 0 | 0 |
| 2025-09-08 | ok | 0.79 | 0.04 | n | 13.7 | 10.8 | 21 | 0 | 0 | 21 |
| 2025-09-10 | ok | 1.00 | 0.89 | Y | 13.3 | 13.3 | 0 | 0 | 0 | 0 |
| 2025-09-13 | ok | 0.98 | 0.73 | Y | 13.1 | 13.0 | 1 | 0 | 0 | 1 |
| 2025-09-15 | ok | 1.00 | 0.87 | Y | 13.4 | 13.4 | 0 | 0 | 0 | 0 |
| 2025-09-15 | ok | 1.00 | 0.89 | Y | 13.2 | 13.2 | 0 | 0 | 0 | 0 |
| 2025-09-18 | ok | 1.00 | 0.85 | Y | 13.1 | 13.1 | 0 | 0 | 0 | 0 |
| 2025-09-20 | ok | 1.00 | 0.87 | Y | 13.3 | 13.3 | 0 | 0 | 0 | 0 |
| 2025-09-28 | ok | 1.00 | 0.82 | Y | 13.1 | 13.1 | 0 | 0 | 0 | 0 |
| 2025-10-03 | ok | 0.92 | 0.75 | Y | 12.0 | 11.2 | 7 | 0 | 0 | 7 |
| 2025-10-10 | ok | 1.00 | 0.91 | Y | 13.1 | 13.1 | 0 | 0 | 0 | 0 |
| 2025-10-12 | ok | 1.00 | 0.92 | Y | 13.6 | 13.6 | 0 | 0 | 0 | 0 |
| 2025-10-13 | ok | 1.00 | 0.92 | Y | 14.1 | 14.1 | 0 | 0 | 0 | 0 |
| 2025-10-15 | ok | 1.00 | 0.92 | Y | 13.5 | 13.5 | 0 | 0 | 0 | 0 |
| 2025-10-15 | ok | 1.00 | 0.91 | Y | 13.2 | 13.2 | 0 | 0 | 0 | 0 |
| 2025-10-20 | ok | 1.00 | 0.91 | Y | 12.5 | 12.5 | 0 | 0 | 0 | 0 |
| 2025-10-23 | ok | 1.00 | 0.89 | Y | 11.8 | 11.8 | 0 | 0 | 0 | 0 |
| 2025-10-25 | ok | 0.95 | 0.57 | Y | 10.2 | 9.6 | 6 | 0 | 0 | 6 |

**mode prod**: observers by month (reference = 15th, window +-21 d, production gate ON)

| month | candidate passes in window | gate-rejected | accepted (cov>=0.5) | S: scene gap, flagged % known, UNKNOWN % | A: scene gap/kind, flagged % known, UNKNOWN % | P: n accepted / status, flagged % known, UNKNOWN % |
|---|---|---|---|---|---|---|
| 2025-04 | 8 | 0 | 2 | gap 0d, 1.9%, 0% | 2d ACCEPTED, 1.9%, 0% | 2 / INSUFFICIENT, 1.9%, 0% |
| 2025-05 | 6 | 2 | 2 | gap 9d, 3.3%, 1% | 17d ACCEPTED, 4.1%, 0% | 2 / INSUFFICIENT, 4.1%, 0% |
| 2025-06 | 6 | 2 | 3 | gap 7d, 7.8%, 1% | 7d ACCEPTED, 7.8%, 1% | 3 / MEDIAN_OF_ACCEPTED, 7.6%, 1% |
| 2025-07 | 7 | 1 | 2 | gap 0d, 7.3%, 23% | 8d ACCEPTED, 6.6%, 5% | 2 / INSUFFICIENT, 6.6%, 5% |
| 2025-08 | 4 | 0 | 3 | gap 1d, 12.7%, 0% | 1d ACCEPTED, 12.7%, 0% | 3 / MEDIAN_OF_ACCEPTED, 12.8%, 0% |
| 2025-09 | 11 | 0 | 9 | gap 0d, 13.4%, 0% | 0d ACCEPTED, 13.4%, 0% | 9 / MEDIAN_OF_ACCEPTED, 13.3%, 0% |
| 2025-10 | 10 | 0 | 10 | gap 0d, 13.5%, 0% | 0d ACCEPTED, 13.5%, 0% | 10 / MEDIAN_OF_ACCEPTED, 13.2%, 0% |


**What the observer outputs (unvalidated).** Of 40 candidate passes, 3 are rejected whole by production's SWIR-DN gate (2025-05-21, 05-31, 07-05; SWIR DN over water 2716-3536) and 37 are read; 36 of the 37 are >= 75 % clear and 25 reach the 0.50 pass-acceptance coverage. Observer A (reference = the 15th of each month, +-21 d), flagged share of known clarity cells: April 2.1 %, May 4.4 %, June 8.2 %, July 5.8 % (bare production 6.6 %), August 12.8 %, September 13.0 %, October 14.6 %; the 37 individual passes in bare-production mode (flagged / known cells) run 0.7-4.1 % in April, 3.3 % on 6 May, 5-8 % in June, 7-9 % in July and a plateau of 12.6-14.1 % from 16 August to 23 October (10.2 % on the partly cloudy 25 October pass). P is INSUFFICIENT in April, May and July (fewer than 3 accepted scenes in the window) and falls back to A; it is a 3-10 scene median in June and from August on and agrees with A to within 1 point. This is a rising-then-plateau shape of the *flagged* share, which is what an observer that sees only surface-reaching canopy should output on a reservoir with milfoil/hydrilla mats; whether it is true is not tested here.

**Refusal rates.** Under the prereg guards the median pass has 19 % of clarity cells UNKNOWN (bare production: 0.2 %); the UNKNOWN share is dominated by HAZE/standoff in April-July (up to 82 % of cells on a hazy April pass, 60 % on 2025-07-15) and by DARK_WATER mainly in October (6-10 % of cells, low sun) and by cloud/shadow on 2025-07-24 (54 %) and 2025-10-10 (63 %). Pass acceptance fails (cov < 0.5) on 12 of 37 passes (cov 0.01-0.48), all April-September, among them clear scenes (e.g. 2025-04-08 and 2025-04-15, 94-99 % seen, cov 0.01 and 0.15). A single-scene S would have picked a pass that is 72-86 % UNKNOWN in April and July.

**Bias to flag:** under `v1` the flagged share *of known cells* is inflated on hazy passes (2025-07-12: 33.8 % of known vs 7.6 % bare production; 2025-09-08: 51 % vs 13.7 %; 2025-07-24: 45 % vs 9.0 %). The HAZE guard removes bright non-plant water but leaves plants (plants are not `haze_px`), so refusing cells asymmetrically biases the ratio. A lake score must be reported with its UNKNOWN share, or computed over a fixed cell set. Tile blending was exercised once (2025-10-10, two granules, offset x1.028 on 14,596 shared cells). Nothing in this section is a validation.

## 10. Dead ends and things that went wrong

* First run of the harness crashed: production's `s2_pass` does `del t["red"]` on the tile dict, so a tile cannot be reused (stub now hands out copies); also `pass_record` needs `properties.datetime` in the stubbed items.
* A first scoring run silently lost scenes because production raises `PassRejected` on the SWIR-DN gate (median SWIR DN over SCL water 900-1500). Initially read as a conversion bug (offset-free 2022 caches get +1000 DN); the rejected scenes include c1-collection Yale 2023 scenes (SWIR DN 1541-1796), so it is a real property of the gate on vegetated or bright-bottom lakes, not an artifact of the conversion. Sensitivity switch added (section 2.1).
* The prereg guards as written were first scored as the primary result and gave a nonsense picture (whole lakes UNKNOWN). That is a finding about the guard (DARK_WATER), kept as primary; the `v1fix` variant exists only to show the effect.
* The PAC persistence observer is not testable: the lean caches hold <= 2 clear scenes per lake-year. Re-extraction of 3+ scenes per lake-year (note 05's script with a higher scene cap, ~1.5 GB) would fix it.
* FWC BioVolume ImageServers: still dead (note 05); not retried.
* No NLA run (scope). TVA/Wisconsin/UMN truth not touched.
* The whole-lake Guntersville read was not attempted (> 2 GB).

## 11. Limitations

1. **Snohomish cannot carry the gates:** 60 reachable positive cells, 54 in one lake, absence assumed outside mapped beds, 5 small clear lakes, 2 survey years. Bootstrap over 5 lakes (2 with positives) is not an interval.
2. **Cached windows** are the lake bbox + ~200 m (production pads 1 km), so cloud/structure/haze standoffs are truncated at the window edge for both replica and production-in-harness; tile blending is not exercised on the truth sets (single tile per scene).
3. **DN reconstruction:** cached float reflectance -> DN -> production decode gives the same reflectance to ~1e-4 (11 vote differences in 2.1 M); 20 m bands are recovered by sub-sampling the nearest-upsampled 10 m cache after aligning to the 20 m grid (block-constancy check: 1.000 on every block with data).
4. **Truth definitions are mine** (floating-leaf share >= 0.5; strict-none negatives; surface = floating or emergent points). FWC is presence-only and sampled toward the vegetated littoral zone; point cells are 1-pixel points in 44 m cells, so a cell can hold a point and still be < 50 % plant.
5. **UNKNOWN handling is a choice:** recall is reported with UNKNOWN counted as a miss (primary) and among known cells; FPR with all and with known open-water cells.
6. **Shore band:** the production `clarity` mask is 40 m, the prereg says "1 pixel"; with a 50 m cell these differ little, with 36 m they are the same.
7. **PAC/PVI:** lake-level sonar volume mixes submerged and surface vegetation; lake-years are clustered (52 lakes); lake-year survey date is the median LTM intercept date, not the sonar date.
8. **Gap strata:** Snohomish headline numbers all have gaps <= 7 d; FWC pooled recall is split <= 7 d vs 8-21 d, but the 8-21 d bucket for A is a single lake.
9. **Guntersville** is clipped, has no truth, one tile, and is a sanity run.

## 12. Concrete fixes recommended for the V1 observer

1. **Rewrite the DARK_WATER guard.** Do not refuse a cell because it is dark; veto *plant calls* on pixels whose ratio is unstable (red and B8A < 0.01) and keep the cell known (`v1fix`: A precision 0.97, FPR 0.2 %, UNKNOWN share of Snohomish lake cells drops from 92 % to 35 %). As written it blanks 45 % of PNW cell-scene observations and makes the "NOT_OBSERVED" state unreachable for clear dark lakes.
2. **Do not inherit the whole-scene SWIR-DN gate for vegetation.** It rejects a pass because the median SWIR over SCL "water" is high, which happens on vegetated, bright-bottom or hazy lakes: 7 of 48 FWC point scenes (median plant-flag share 9.7 % vs 1.1 % for accepted scenes), 116 of 482 PAC scene-lake-year pairs, all summer scenes at Cypress. Replace with a per-pixel/per-cell guard or compute the median over open-water pixels (SCL water, NDVI < 0.10).
3. **Separate CLOUD, SHADOW, HAZE and BRIGHT-WATER refusals.** Production `hidden` bundles 600 m real-cloud standoff, cloud-edge SWIR and haze; it marks 65 % of Florida observations and, with SWIR > 0.02 non-plant water, probably turbid/algal water. Keep the cloud standoff, make the haze test relative (SWIR vs lake median) and report them as distinct refusals.
4. **Define pass acceptance for vegetation, not clarity.** `cov >= 0.5` of *turbidity-readable non-plant water* is met by only 11-12 % of Florida scenes (71-78 % are below 0.25; median cov 0.00-0.01) and Serene (clear scene, cov 0.04) for reasons unrelated to plant visibility. Use the share of cells that are *known* (seen, not hazy, not shore) as the acceptance statistic, and keep the burst-failure test (Storm: 39 false cells at cov 0.03) as a separate "implausible plant share" check.
5. **Never expose S.** One scene produced 39 false cells at Storm; S fails the FPR gate (3.2 %) while A and P pass. If S is kept as `SATELLITE_SINGLE_PASS`, give it the same acceptance floor as A.
6. **Make P reachable.** >= 3 accepted scenes in +-21 d occur for 3 of 5 Snohomish lakes, 1 of 7 FWC point lakes and none of the PAC lake-years the observer could score (the caches hold <= 2 clear scenes, so the last is partly a data limit). Either widen the window (+-45 d, as in note 05, median gave 0 false cells) or state that P will be INSUFFICIENT for most lakes and design A to be the usual evidence.
7. **Shore band policy.** 30 % of Snohomish lake cells are SHORE_ADJACENT and 49-54 % of mapped floating-leaf cells sit there, so whole-lake recall is 0.46-0.51 for every observer. State that claims are interior-only, or test a 1-pixel band against polygon registration; never present the production bed-to-bank strip (up to 24 % of lake area) as an observation.
8. **Pick one frame.** Prereg says 50 m; production `daily.py` runs 36 m. Results agree within noise here but cell counts and shore band differ; pin the frame in the observer contract.
9. **GLARE.** Specify a separate glint test (SWIR vs B8A pattern or a Wind flag); the contract's 0.0215 limit is not separable from the 0.02 haze threshold.
10. **Truth definitions for the next scoring round:** declare the recall population (interior vs whole lake), the prevalence used for shore matching (raw preferred), and the negative class (strict vs buffered) before scoring; add >= 2 more floating-leaf lakes with >= 30 interior positive cells (e.g. UMN Minnesota, other counties' polygon surveys) before any `PARTIAL` claim; extract >= 3 scenes per PAC lake-year to test P; run NLA 2017 for gates c and d.
11. **Florida:** at this observer the Florida class (floating + emergent, presence-only truth) is below 0.35 recall even with no guards; do not publish PRESENT/NOT_OBSERVED for it, only the evidence class and refusals.
