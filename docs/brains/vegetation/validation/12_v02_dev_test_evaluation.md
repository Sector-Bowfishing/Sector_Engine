# 12. Observer v0.2 (SHIPPED module) - DEV tuning and one-shot TEST evaluation (pre-registration + A1-A4)

Offline, cache-only, read-only on every git repo. Subject: `Sector_Engine-vegetation-adoption/jobs/vegetation-brain/vegetation_brain/observer.py` at HEAD `c341eb09` (sha256 `b8fa09a1f254addf84b1c482ed63bc88ce1dc37a3b2b0643b47b6c425da38ca0`), imported unchanged (`sys.dont_write_bytecode`, no `__pycache__` created in the repo, `git status` clean). Everything lives under `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/v2_eval/` (`scripts/`, `out/`); new files are logged (bytes, sha256) in `../../MANIFEST.jsonl`. Gates are the section 5 gates of `VEGETATION_VALIDATION_PREREGISTRATION.md`, unchanged; the procedure is amendment A4 verbatim. **New Sentinel-2 network bytes: 0** (a socket guard, `install_guard()` = v1's `net_guard`, is installed in every process; any connection would have raised).

## 1. Headline (read first)

| question | answer |
|---|---|
| Chosen pair | **haze_swir 0.10, haze_standoff_px 0**, frozen `2026-10-13T16:41:44` in `out/chosen_params.frozen.json` before the TEST run (`test_raw.pkl` written 16:42). All 20 grid settings passed both DEV constraints, so selection reduced to "max DEV F1 (0.979), tie-break fewer UNKNOWN, larger haze_swir, smaller standoff". **The chosen setting effectively switches the haze guard off** (HAZE refusal share 0.000 on every TEST set). The defaults (0.02, 10) scored dev recall 0/24. |
| Does the DEV tuning have any power? | **No.** DEV positives: 24 interior cells, 23 of them in one lake (Roesiger). DEV negative control: 2 of 3 dev NLA negatives scored, both at <= 0.25 % at every setting. The two constraints never bound; the grid cannot tell a safe setting from an unsafe one. The test of the choice is therefore TEST only, and TEST (below) shows the unsafe case (Keystone Lake, 11.3 %). |
| Gates, TEST, observers A and P | (a) **NOT_TESTABLE** (the three TEST Snohomish lakes hold **0** interior positive cells); (b) **PASS (literal)**: 0 of 203 known open-water cells (FPR 0.0 %, 95 % upper bound about 1.5 %); (c) **FAIL**: 22 TEST lakes, 9 regions, AUC 0.72 (0.37-1.00), Spearman 0.22 / 0.24 (-0.30..0.62); (d) **FAIL**: Keystone Lake OK 11.3 % flagged (3 of 4 scored negatives <= 2 %, mean 3.2 %, Lake Buchanan TX unscored because both scenes are BLOOM_AMBIGUOUS); (e) **NOT_TESTABLE** (no interior positive to compute F1). **No gate is PASSED; (b) is a weak literal pass.** State unchanged: `NOT_VALIDATED` / RESEARCH. |
| Observer S (evaluation only) | S is still unreachable on small lakes: 0 of 5 Snohomish lakes (no cell ever known), reachable on only 15 of 25 TEST NLA lakes. (b) NOT_TESTABLE; (c) FAIL (n 15, AUC 0.69, Spearman 0.02); (d) FAIL. |
| FWC LTM points (recall only; 1,205 cells) | recall (UNKNOWN = miss) S 0.110, A 0.111, **P 0.138** (95 % CI over lakes 0.047-0.228); interior 0.21; among known cells 0.32. Not a gate (presence-only, A1.7). V1 was 0.007. |
| NLA 2018-2019 secondary (labelled, 24 TEST lakes) | A: AUC 0.81 (0.50-1.00), Spearman 0.10: gate (c) FAIL; gate (d) 4/4 scored <= 1.0 % (PASS on this secondary only, not a gate substitute). |
| UMN / SFWMD / UMR | UMN points (4 MN lakes, substitute years except tier E): pooled surface-strict recall **4-14 %**. SFWMD (substitute years 2018/19 vs polygons 2015/16): precision 0.90-1.00, recall Okeechobee 0.12-0.21, Toho 0.62-0.73, **Kissimmee 0.00 (all 10 cached scenes BLOOM_AMBIGUOUS)**. **UMR Pool 5: NOT_RUN** (no scene cache). |
| New defect, descriptive | `BLOOM_AMBIGUOUS` is largely a cloud/haze/smoke detector, and it is now the biggest refusal: **36 % of NLA cell-scenes, 45 % of FWC**. 30 of 47 NLA lakes have at least one ambiguous scene. Among scenes with <= 1 % lake cloud it fires in 3-13 %; with > 5 % cloud in 31-65 %. |
| vs V1 (note 11) | Reachability is repaired (Snohomish accepted-pass lakes 0/5 -> 5/5; NLA lakes with an accepted pass 29 -> 38 of 47; P-reachable NLA 2 -> 12), recall is no longer zero (DEV Roesiger 23/23, tuned), but **every lake-level gate fails exactly as in V1** (c FAIL, d FAIL with the same lake, Keystone ~12 % -> 11.3 %). |

## 2. Method (what was done, in order; nothing deviated)

1. **Split and declarations written first** (`out/nla_split.csv`, `out/protocol_declared.json`, 16:39:44). NLA lakeId is the registry `lakeId` (e.g. `Allatoona|GA`, from `registry/lakes.v1.json` by lakeKey); `sha256(lakeId).digest()[0]` even = DEV, odd = TEST. Eligible = the 48 lakes of `nla_lake_classes.csv` with stations (Lake Mead is skipped as in notes 07/11 and falls in TEST). DEV 22 lakes run (5 POS / 3 NEG / 14 AMB), TEST 26 (25 run; 10 POS / 5 NEG / 11 AMB). Snohomish: DEV Roesiger + Serene, TEST Bosworth + Blackmans + Storm.
2. **Interpretive choices declared before any scoring** (A4 leaves them open): DEV F1 is the pooled raw-prevalence interior F1 against strict-none negatives with UNKNOWN positives counted as misses; constraint 1 is FP/(FP+TN) on known strict-none cells <= 2 %; constraint 2 is **each** scored dev-NLA negative (observer A, >= 10 read belt cells) <= 2 % (the literal per-lake reading used for gate (d) in note 11; the mean is also tabulated); a constraint with no evidence (no known cells / no scored negative) is **inadmissible**, not vacuously met (the vacuous reading would have chosen the same pair); ties to 1e-9. No admissible setting would have meant "keep (0.02, 10)", not the least-bad setting.
3. **Adapter.** `scripts/v2lib.py` reuses `v1lib` (cached reflectance to raw DN to `observer.reflectance`, lake masks, distance transform, NLA mosaic) and calls `observer.scene_fields(..., haze_swir=, haze_standoff_px=)`. **`nir_floor` is never passed**; the module computes the adaptive floor and `BLOOM_AMBIGUOUS` itself. `v2jobs.py` holds the Snohomish/FWC/NLA workers (all scene arrays read once, settings looped). The Snohomish/FWC/NLA truth, belt, scoring and bootstrap code is the v1/`n5_score` code (`v2metrics.py`, `t5_metrics.py`).
4. **DEV grid** (`t2_grid.py`, `t3_choose.py`): 5 haze_swir x 4 standoff, observer A, DEV sets only. Chosen pair written with timestamp. Then **TEST run once** (`t4_test.py`, S/A/P, the frozen pair only; also covers every NLA lake so the descriptive all-lakes statistics come from the same pass; gate verdicts use only odd-hash lakes). No re-tuning and no second pair was ever run on TEST (not even the defaults).
5. **Supplementary TEST sets** from existing note-09/10 caches (`t4b_umn_sfwmd.py`): UMN points, SFWMD polygons. **Descriptive** (`t6_seasonal_desc.py`, `t6b_nla_cloud.py`): every cached scene of Hartwell, Leech Lake and Guntersville, and the 218 NLA 2017 in-window scenes.

## 3. DEV grid (observer A; DEV sets only)

Full table (`out/grid_dev_table_full.md`; interior positives 24 = Roesiger 23 + Serene 1; strict-none negatives; Snohomish DEV in-window scenes 26; dev NLA negatives Lake Hickory NC, Sherman Reservoir NE, Monroe Lake IN):

| haze_swir | standoff px | TP/FN | FP | F1 | open-water FPR (FP/known) | UNKNOWN interior share | acc/in-win scenes | dev NLA negatives' belt share (Hickory, Sherman, Monroe) | C1 | C2 | admissible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.02 | 0 | 23/1 | 0 | 0.979 | 0/353 | 0.077 | 21/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.02 | 2 | 20/4 | 0 | 0.909 | 0/312 | 0.212 | 20/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.02 | 5 | 9/15 | 0 | 0.545 | 0/225 | 0.459 | 9/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| **0.02** | **10 (default)** | **0/24** | 0 | **0.000** | 0/190 | 0.581 | 0/26 | 0.0027, 0.0000, unscored | Y | Y | yes |
| 0.03 | 0 | 23/1 | 0 | 0.979 | 0/373 | 0.033 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.03 | 2 | 20/4 | 0 | 0.909 | 0/358 | 0.093 | 21/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.03 | 5 | 15/9 | 0 | 0.769 | 0/291 | 0.285 | 17/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.03 | 10 | 0/24 | 0 | 0.000 | 0/217 | 0.494 | 5/26 | 0.0026, 0.0000, unscored | Y | Y | yes |
| 0.04 | 0 | 23/1 | 0 | 0.979 | 0/376 | 0.026 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.04 | 2 | 23/1 | 0 | 0.979 | 0/373 | 0.035 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.04 | 5 | 23/1 | 0 | 0.979 | 0/332 | 0.141 | 21/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.04 | 10 | 23/1 | 0 | 0.979 | 0/225 | 0.386 | 9/26 | 0.0026, 0.0000, unscored | Y | Y | yes |
| 0.06 | 0 | 23/1 | 0 | 0.979 | 0/379 | 0.020 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.06 | 2 | 23/1 | 0 | 0.979 | 0/378 | 0.022 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.06 | 5 | 23/1 | 0 | 0.979 | 0/363 | 0.064 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.06 | 10 | 23/1 | 0 | 0.979 | 0/302 | 0.212 | 15/26 | 0.0026, 0.0000, unscored | Y | Y | yes |
| **0.10** | **0** | 23/1 | 0 | **0.979** | 0/379 | **0.020** | 23/26 | 0.0025, 0.0000, unscored | Y | Y | **chosen** |
| 0.10 | 2 | 23/1 | 0 | 0.979 | 0/379 | 0.020 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.10 | 5 | 23/1 | 0 | 0.979 | 0/378 | 0.024 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |
| 0.10 | 10 | 23/1 | 0 | 0.979 | 0/349 | 0.106 | 22/26 | 0.0025, 0.0000, unscored | Y | Y | yes |

Reading: the one miss (Serene's single interior positive) is constant; F1 is 0.979 from 12 settings; the constraints are non-binding (FPR 0 everywhere, dev negatives at 0.25 %); the selection therefore walked down the tie-break list to the setting with the largest SWIR cut-off and no standoff. This is the A4 rule operating correctly on a dev set that cannot discriminate, not evidence that the haze guard is useless or safe. Note also that the **default (0.02, 10)** reproduces the V1 failure on the dev lakes (0 of 24, 0 of 26 scenes accepted) despite the new adaptive floor.

**Chosen pair (frozen): haze_swir = 0.10, haze_standoff_px = 0, written 2026-10-13T16:41:44** (`out/chosen_params.frozen.json`, `verdict: ADMISSIBLE_SETTING_CHOSEN`).

## 4. TEST results (frozen pair; scored once)

### 4.1 Snohomish (Bosworth, Blackmans, Storm), interior population, strict-none negatives

Survey-image gaps of the observed scenes are 1-4 d (inside the headline limit of 7 d). **There are no interior positives in the three TEST lakes** (whole-lake positives 2 + 8 + 0 = 10, all in the shore ring that A1.5 excludes from the headline), so precision, recall, F1 and the bootstrap are undefined and gates (a) and (e) cannot be evaluated.

| obs | TP | FP | interior pos | whole-lake pos | TP whole-lake | recall interior | recall whole-lake | open-water cells | known | FPR all | FPR known | neg UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 0 | 0 | 0 | 10 | 0 | n/a | 0.000 | 203 | **0** | 0.000 | n/a | 1.000 |
| A | 0 | 0 | 0 | 10 | 0 | n/a | 0.000 | 203 | 203 | 0.000 | **0 / 203** | 0.000 |
| P | 0 | 0 | 0 | 10 | 0 | n/a | 0.000 | 203 | 203 | 0.000 | **0 / 203** | 0.000 |

Buffered-none negatives (81 cells): FP 0 for A and P. Per lake A/P: Bosworth NOT_OBSERVED (10 accepted scenes), Storm NOT_OBSERVED (7), Blackmans PRESENT with 3 plant cells (10 accepted; the 3 cells fall outside the strict-none set, so no false positive is counted). All three lakes reach persistence (P) and an accepted pass; S is `NONE` on every lake.

For context only (DEV lakes under the frozen pair; **tuned-on, not evidence**): Roesiger 23/23, Serene 0/1; pooled interior recall 0.958, precision 1.000, F1 0.979, whole-lake recall 0.561, FPR 0/381. ALL five lakes: interior recall 0.958 versus **whole-lake recall 0.451** (interior vs whole-lake recall differ by a factor of two because 27 of 51 positives lie in the excluded shore ring).

### 4.2 FWC LTM points (recall only)

| obs | point-cells | recall (UNKNOWN = miss) | interior recall | known-only recall | 95 % CI (lakes) | per lake |
|---|---|---|---|---|---|---|
| S | 1,205 | 0.110 | 0.168 | 0.290 | 0.042-0.174 | Orange 0.157, Griffin 0.164, Apopka 0.260, Harris 0, Panasoffkee 0.034, Yale 0.189, Cypress 0 |
| A | 1,205 | 0.111 | 0.170 | 0.309 | 0.038-0.178 | Orange 0.157, Griffin 0.176, Apopka 0.260, Harris 0, Panasoffkee 0.017, Yale 0.189, Cypress 0 |
| P | 1,205 | **0.138** | 0.210 | 0.318 | 0.047-0.228 | Orange 0.320, Griffin 0.201, Apopka 0.252, Harris 0, Panasoffkee 0.017, Yale 0.189, Cypress 0 |

Still far below 0.70; presence-only truth cannot support PARTIAL (A1.7). Reachability: 5 of 7 lakes with an accepted pass, 3 P-reachable; 29 % of in-window scenes reach 50 % known-interior coverage.

### 4.3 NLA 2017 (section 4 protocol), TEST = odd-hash lakes (25 run of 26)

Belt = interior cells with centre 10-90 m from the edge; lake scored if >= 10 read belt cells; 25 of 25 run lakes have an in-window scene (zero NO_SCENE); 21 have an accepted pass, 7 are P-reachable, 1 is fallback-only (Burnsville Lake WV); presence P: 17 PRESENT / 5 NOT_OBSERVED / 3 UNKNOWN.

| set | obs | lakes scored | pos/neg/amb | regions | AUC (95 % CI over lakes) | Spearman (95 % CI) | gate (c) | negatives scored / in set | each <= 2 % | neg mean / max | gate (d) each | gate (d) mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TEST primary | S | 15 | 6/3/6 | 7 | 0.69 (0.20-1.00) | 0.02 (-0.64..0.58) | **FAIL** | 3/5 | 2 | 0.040 / 0.113 | **FAIL** | FAIL |
| TEST primary | **A** | 22 | 8/4/10 | 9 | 0.72 (0.37-1.00) | 0.22 (-0.30..0.62) | **FAIL** | 4/5 | 3 | 0.032 / 0.113 | **FAIL** | FAIL |
| TEST primary | **P** | 22 | 8/4/10 | 9 | 0.72 (0.38-1.00) | 0.24 (-0.26..0.63) | **FAIL** | 4/5 | 3 | 0.032 / 0.113 | **FAIL** | FAIL |
| TEST secondary (2018+2019, mean) | S | 16 | 6/3/7 | 8 | 0.75 (0.33-1.00) | -0.11 (-0.64..0.50) | FAIL | 3/5 | 3 | 0.004 / 0.010 | PASS | PASS |
| TEST secondary | A | 24 | 9/4/11 | 9 | 0.81 (0.50-1.00) | 0.10 (-0.37..0.55) | FAIL | 4/5 | 4 | 0.003 / 0.010 | PASS | PASS |
| TEST secondary | P | 24 | 9/4/11 | 9 | 0.78 (0.50-1.00) | 0.13 (-0.33..0.58) | FAIL | 4/5 | 4 | 0.003 / 0.010 | PASS | PASS |

TEST negatives (primary, A = P): **Keystone Lake OK 0.113** (6,197 read belt cells), Lake Jocassee SC 0.006, Pomme de Terre Lake MO 0.008, Willard Bay Reservoir UT 0.000, **Lake Buchanan TX unscored** (both in-window scenes BLOOM_AMBIGUOUS, 0 read cells). The 11.3 % at Keystone is the same false-flag mechanism V1 had (12.0 %): its only accepted scene (2017-08-03) has an adaptive floor of 0.071 (below the 0.10 ambiguity cap, so it is read) and flags 701 of 6,197 belt cells; the cause (turbid water, flooded vegetation, or something else) was not investigated here. The median belt share is 0.092 for positives against 0.007 for negatives, so there is rank signal, but the Spearman against the station cover code is 0.22-0.24.

Descriptive pools (not gate evidence; DEV lakes were tuned on): DEV primary A: 17 scored, AUC 0.75, Spearman 0.07; ALL lakes (mixed) primary A: 39 scored (11/6/22), AUC 0.74 (0.48-0.97), Spearman 0.20 (-0.13..0.52), negatives mean 2.1 %, 5 of 6 scored <= 2 %.

### 4.4 UMN points (recall only) and SFWMD polygons (supplementary; substitute years)

Neither can carry a headline: UMN is mostly 2008-2016 surveys scored against 2017-2019 scenes (tiers F/N/A) and SFWMD polygons are 2015/2016 against 2018/2019 scenes (gap >= 2.5 years; section 2 metric 5 excludes them from headline numbers).

UMN `surface_strict` points, pooled over lakes (Minnetonka, Mille Lacs, Winnibigoshish, Gull; recall = PLANT cell / points, shore-ring and UNKNOWN count as misses):

| tier | obs S / A / P recall | points x scene-year (S) | PLANT (A) | read interior (A) |
|---|---|---|---|---|
| E exact year (survey >= 2017) | 0.044 / 0.044 / 0.044 | 90 | 4 | 56 |
| A adjacent year after an S2-era survey | 0.078 / 0.078 / 0.067 | 90 | 7 | 49 |
| N near substitute (survey 2014-2016) | 0.142 / 0.111 / 0.127 | 592 | 66 | 183 |
| F far substitute (<= 2013) | 0.069 / 0.069 / 0.038 | 291 | 20 | 97 |

Per lake: Winnibigoshish 0 of 10 flagged (9 of 10 points read in the interior); Mille Lacs 1-14 % depending on tier; Minnetonka 4-24 %; Gull has no interior points (all 15 in the shore ring). Winnibigoshish and Mille Lacs read most of their interior points and still flag almost none, so for UMN the limit is plant detection (taxa classed `surface_strict` are pondweeds etc. that need not form NDVI >= 0.3 canopies), not UNKNOWN.

SFWMD littoral polygons (positives = FLOAT + CATTAIL + HERB >= 0.5 of the cell, negatives = open-water class >= 0.9, interior; observer A; P identical because no lake reaches 3 accepted scenes):

| lake | scene yr | accepted/in-window | interior pos | recall (UNK = miss) | precision raw | open-water FPR (known) |
|---|---|---|---|---|---|---|
| Okeechobee | 2018 | 2/5 | 25,784 | 0.122 | 0.897 | 0.005 |
| Okeechobee | 2019 | 2/5 | 25,784 | 0.205 | 0.934 | 0.005 |
| Kissimmee | 2018 / 2019 | 0/5, 0/5 | 9,633 | **0.000** | n/a | no known cells |
| Tohopekaliga | 2018 | 1/2 | 9,182 | 0.732 | 0.998 | 0.001 |
| Tohopekaliga | 2019 | 2/4 | 9,182 | 0.620 | 0.987 | 0.004 |
| pooled | 2018 / 2019 | | 44,599 | **0.22 / 0.25** (0.28 / 0.31 without Kissimmee) | 0.96 / 0.96 | 0.0045 / 0.0051 |

Single pass S on Okeechobee 2018 has FPR 0.041 (evaluation-only). If these cells were admitted as truth lakes for gate (a), the gate would still FAIL on recall (pooled 0.22-0.25, only Toho above 0.70 at one date); precision would pass. This is reported only as a labelled supplementary result. **All 10 cached Kissimmee scenes are BLOOM_AMBIGUOUS** (adaptive floor 0.21-0.35, whole lake UNKNOWN): the guard blanks an entire shallow macrophyte/turbid lake.

**UMR Pool 5: NOT_RUN.** Note 09 fetched its 2017/2018 scenes live from the STAC API and kept no scene cache, so no scene exists offline; per instruction no download was attempted.

### 4.5 Refusals by guard (share of eligible cell-scenes over every in-window scene; "known" = cells with a plant/no-plant call)

| set | cell-scenes | known | CLOUD | SHADOW | HAZE | DARK_WATER | SHORE_ADJACENT | INSUFF. VALID PX | ICE/SNOW | **BLOOM_AMBIGUOUS** | GLARE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Snohomish TEST (3) | 4,520 | 0.530 | 0.123 | 0.022 | 0.000 | 0.007 | 0.316 | 0.000 | 0.000 | 0.000 | 0 |
| Snohomish DEV (2) | 7,780 | 0.636 | 0.062 | 0.003 | 0.000 | 0.007 | 0.290 | 0.000 | 0.000 | 0.000 | 0 |
| FWC (7) | 813,843 | 0.325 | 0.151 | 0.009 | 0.000 | 0.001 | 0.036 | 0.031 | 0.000 | **0.446** | 0 |
| NLA 2017 TEST | 1,222,091 | 0.344 | 0.115 | 0.017 | 0.000 | 0.001 | 0.147 | 0.096 | 0.001 | **0.279** | 0 |
| NLA 2017 ALL 47 | 2,562,830 | 0.292 | 0.140 | 0.015 | 0.000 | 0.000 | 0.117 | 0.074 | 0.001 | **0.361** | 0 |
| NLA 2018+19 TEST | 3,624,346 | 0.315 | 0.081 | 0.005 | 0.000 | 0.000 | 0.146 | 0.094 | 0.000 | **0.359** | 0 |

HAZE is 0 because the frozen pair disables it (compare V1: 43.7 % / 30.8 % / 23.7 %); its work has moved to BLOOM_AMBIGUOUS. GLARE is never set (needs a Wind flag), unexercised.

### 4.6 Reachability

| set | lakes | accepted pass (>= 50 %) | P-reachable (>= 3) | fallback-only (25-50 %) | burst exclusions (lakes / scenes) | in-window scenes | share scenes >= 50 % / >= 25 % |
|---|---|---|---|---|---|---|---|
| Snohomish TEST | 3 | **3** | **3** | 0 | 0 / 0 | 34 | 0.79 / 0.82 |
| Snohomish DEV | 2 | 2 | 2 | 0 | 0 / 0 | 26 | 0.89 / 0.89 |
| FWC | 7 | 5 | 3 | 0 | 0 / 0 | 48 | 0.29 / 0.31 |
| NLA 2017 TEST | 25 | 21 | **7** | 1 | 1 / 5 | 117 | 0.42 / 0.50 |
| NLA 2017 ALL | 47 | 38 | 12 | 1 | 1 / 5 | 218 | 0.39 / 0.45 |
| NLA 2018+19 TEST (scene-years) | 50 | 44 | 25 | 2 | 3 / 4 | 293 | 0.44 / 0.51 |

The 5 burst exclusions on the NLA primary are all at **Bitter Lake SD** (NLA cover 0, 5 of 10 accepted scenes dropped): the burst rule is still unstable when the other scenes' median plant count is 0-1 (V1 finding unfixed; no harm to the score since the lake reads 0.000).

## 5. Gate verdicts (section 5, thresholds unchanged)

| gate | S (evaluation only) | A | P |
|---|---|---|---|
| (a) precision >= 0.80 and recall >= 0.70, pooled and in each of >= 3 truth lakes with >= 30 positive cells | NOT_TESTABLE | **NOT_TESTABLE** (0 interior positives in the TEST lakes; no TEST lake has 30; supplementary SFWMD, not admissible as headline, would FAIL on recall) | **NOT_TESTABLE** (same) |
| (b) open-water FPR <= 2 % | NOT_TESTABLE (no known cell) | **PASS (literal)**: 0/203 known cells (3 lakes, 0 plant cells in 2 of them); supplementary SFWMD FPR 0.1-0.5 % | **PASS (literal)** (same) |
| (c) NLA AUC >= 0.80 and Spearman >= 0.50, >= 15 lakes, >= 3 regions | FAIL (15 lakes, 7 regions: AUC 0.69, rho 0.02) | **FAIL** (22 lakes, 9 regions: AUC 0.72, rho 0.22) | **FAIL** (AUC 0.72, rho 0.24) |
| (d) each negative control <= 2 % | FAIL | **FAIL** (Keystone 11.3 %; 3 of 4 scored; Buchanan unscored) | **FAIL** (same) |
| (e) lower bootstrap bound of pooled F1 >= 0.65 | NOT_TESTABLE | **NOT_TESTABLE** (F1 undefined, no interior positive; lake bootstrap over 3 lakes empty) | **NOT_TESTABLE** |

Validation state: **unchanged, `NOT_VALIDATED` (RESEARCH reached by notes 06-07/11; CALIBRATION not reached on the strength of this run)**. Per A4 the gate (c) caveat applies: it fails on TEST and is reported as a failure of the V1 design to be validated against shoreline NLA plots (162 of 467 stations 10-90 m from the edge, 191 within 10 m) with co-located truth listed as a blocker, **not** as a pass of anything. The secondary gate (d) pass (4/4 at <= 1 %) comes from capped, cloud-filtered 2018/2019 scenes and is not a substitute (V1 had the same pattern).

## 6. Comparison with V1 (note 11, frozen V1 at floor 0.13, different populations noted)

| quantity | V1 module (note 11) | v0.2 on TEST (this note) | v0.2 on the V1 populations, descriptive (includes tuned-on DEV lakes) |
|---|---|---|---|
| Snohomish lakes with an accepted pass | 0 of 5 | 3 of 3 TEST (5 of 5 all) | 5 of 5 |
| Snohomish interior recall A / P | 0.00 (0/24) | **n/a (0 interior positives in TEST)** | 0.958 (23/24, Roesiger; tuned) |
| Snohomish whole-lake recall | 0.00 | 0.00 (0/10) | 0.451 |
| Snohomish open-water FPR (known) | 0 / 264 known, 55 % unknown | 0 / 203, 0 % unknown | 0 / 582 |
| Dominant Snohomish refusals | HAZE 43.7 %, SHORE_ADJACENT 30.0 %, CLOUD 8.5 % | SHORE_ADJACENT 31.6 % (structural), CLOUD 12.3 %, HAZE 0 | SHORE_ADJACENT 29-32 %, CLOUD 6-12 % |
| FWC recall P (UNK = miss) | 0.007 | 0.138 (A 0.111, S 0.110) | same |
| NLA lakes with accepted pass / P-reachable | 29 / 47, 2 | 21 / 25, 7 | 38 / 47, 12 |
| NLA lakes scored (A) | 32 (7/6/19) | 22 (8/4/10) | 39 (11/6/22) |
| NLA AUC, A (P) | 0.77 (0.77) | 0.72 (0.72) | 0.74 (0.74) |
| NLA Spearman, A (P) | 0.13 (0.11) | 0.22 (0.24) | 0.20 (0.23) |
| NLA negative mean / worst | 2.1 % / 12.0 % (Keystone) | 3.2 % / 11.3 % (Keystone) | 2.1 % / 11.3 % |
| gate (c) / (d) | FAIL / FAIL | FAIL / FAIL | FAIL / FAIL |
| top refusals (NLA) | CLOUD 32.6 %, HAZE 23.7 % | BLOOM_AMBIGUOUS 27.9 %, CLOUD 11.5 % | BLOOM_AMBIGUOUS 36.1 %, CLOUD 14.0 % |

What changed: the HAZE blanking that made V1 unusable is gone (by the tuned pair), and recall can now be nonzero. What did not: the lake-level NLA rank signal, the Keystone false flags, and the structural gate (a)/(e) untestability. A new blanket refusal (BLOOM_AMBIGUOUS) has taken HAZE's place.

## 7. Descriptive sanity (step 3; not gate evidence; frozen pair)

### 7.1 BLOOM_AMBIGUOUS behaviour on the Leech / Hartwell / Guntersville window caches (all cached scenes)

| lake | scenes | share with floor = 0.03 | median floor | p90 | p99 | max | BLOOM_AMBIGUOUS share |
|---|---|---|---|---|---|---|---|
| Hartwell SC/GA | 322 | 0.52 | 0.030 | 0.149 | 0.209 | 0.297 | **0.205** |
| Leech Lake MN | 320 | 0.37 | 0.049 | 0.162 | 0.266 | 0.459 | **0.256** |
| Guntersville AL | 301 | 0.37 | 0.037 | 0.305 | 0.808 | 1.026 | **0.239** |

Does it behave sensibly? Mostly as a cloud/haze/smoke flag, not a bloom flag. Ambiguity share by lake cloud fraction (SCL 3/8/9/10 share of lake pixels):

| set | scenes | cloud <= 1 % (n, ambiguous) | 1-5 % | > 5 % | cloud <= 1 % and snow-free |
|---|---|---|---|---|---|
| NLA 2017 in-window | 218 | 50, 3 (0.06) | 17, 4 (0.24) | 151, 47 (0.31) | 50, 3 (0.06) |
| Hartwell | 322 | 183, 5 (0.03) | 33, 3 (0.09) | 106, 58 (0.55) | 183, 5 (0.03) |
| Leech | 320 | 182, 19 (0.10) | 33, 8 (0.24) | 105, 55 (0.52) | 160, 6 (0.04) |
| Guntersville | 301 | 222, 28 (0.13) | 30, 12 (0.40) | 49, 32 (0.65) | 221, 28 (0.13) |

* **Hartwell (clear reservoir, A3's "no-signal" lake):** the guard is quiet in clear scenes (3 %), loud in cloudy ones; the monthly median floor is 0.030 except May-July (0.06-0.065). Reasonable.
* **Leech:** 40 of 320 scenes have SCL snow/ice in the lake and 22 of those are ambiguous (winter/spring median floors 0.07-0.16); clear snow-free scenes 4 %. Reasonable; the A3 ice-shoulder tail is now confined to individual scenes instead of poisoning a global floor.
* **Guntersville (growing-season vegetated reservoir):** 13 % of **clear** scenes are ambiguous and the May-June median floors are **0.205 and 0.272** (monthly ambiguity 18 of 24 in May, 13 of 24 in June). The open-water tail used by the guard (SCL water, NDVI < 0.10) is evidently contaminated by bright shallow/turbid water or submerged canopy in exactly the months the observer matters; the same behaviour blanked all of Kissimmee (floors 0.21-0.35 on 10 of 10 scenes) and 2 of 5 Okeechobee scenes in each of 2018 and 2019. This is a defect for vegetated shallow systems, not a Hartwell-style pass.
* Waldo Lake OR (an exceptionally clear lake) has a median floor of 0.24 in its two in-window scenes (2017 wildfire smoke is a candidate cause, not verified), another sign the statistic responds to haze/smoke.

### 7.2 Distribution of the adaptive floor

| set | scenes | share at the 0.03 minimum | median | p90 | p99 | max | BLOOM_AMBIGUOUS share |
|---|---|---|---|---|---|---|---|
| NLA 2017 in-window (47 lakes) | 218 | 0.46 | 0.0375 | 0.148 | 0.682 | 0.990 | 0.248 |
| NLA 2018/19 scenes | 598 | 0.30 | 0.0725 | 0.176 | 0.509 | 0.820 | 0.390 |
| Snohomish (5) | 118 | 0.92 | 0.030 | 0.030 | 0.090 | 0.098 | 0.000 |
| FWC (7) | 97 | 0.30 | 0.093 | 0.169 | 0.249 | 0.274 | 0.454 |

The floor sits at the 0.03 minimum for small clear lakes (Snohomish: also because their open-water area >= 100 m from the edge is under 1,000 pixels in some lakes), rises to 0.05-0.10 on turbid and Florida lakes, and goes to 0.5-1.0 on scenes where cloud is labelled water. 30 of 47 NLA lakes have at least one ambiguous 2017 in-window scene (54 of 218 scenes); per-lake shares are in `out/tables_v02.md` (all-ambiguous lakes: Buchanan TX, Griffin FL, Walker Lake NV).

## 8. Limits

* **TEST Snohomish has no interior positives**: gates (a) and (e) are structurally NOT_TESTABLE, so the one cell-level recall/precision question of the pre-registration remains unanswered on independent data. Only (b) is informative there, and it rests on 203 open-water cells of three small lakes (two of them with no plant cell at all).
* The DEV tuning set is effectively one lake (Roesiger 23 of 24 positives) plus two scored negatives; the chosen pair is the output of a rule with no discriminating power on that set (section 3). A different, equally valid tie-break would pick any of 12 identical-F1 settings. The pair was frozen as the rule dictates; it is not endorsed as a good parameter.
* The (0.10, 0) pair turns HAZE off: results here say nothing about the haze guard's value on hazy scenes, and gate (d) at Keystone suggests the guard-off setting is exposed on turbid reservoirs (not demonstrated causal; V1 with HAZE on had the same 12 %).
* Gate (d) uses the literal "each negative <= 2 %" reading; the mean reading gives the same FAIL (3.2 %). Only 4 of 5 TEST negatives are scoreable and Buchanan is unscored because it is fully BLOOM_AMBIGUOUS, so the pass/fail is based on very few lakes.
* The NLA station truth is shoreline-based and not co-located with the interior-only belt (A4 caveat). The rank signal exists (median belt share 0.092 vs 0.007) but Spearman 0.2 with CI spanning 0 is not a gate-grade statistic at n = 22.
* SFWMD/UMN scenes are substitute years and the polygons/taxon classes are generalised; they are not headline evidence. The SFWMD truth file `VEG_KCOL_2015.geojson` was compressed to `.gz` by another process during this session; the first UMN/SFWMD run (16:44) therefore skipped Kissimmee, and the stage was re-run (16:46) reading `.gz`; nothing else changed (same frozen pair, same caches).
* NLA scene windows: the module window is +-21 d on cached dates; secondary years hold at most 6 dates/year; Lake Mead (TEST) not run; 2017 cached dates only. Collections: NLA tiles are `sentinel-2-l2a` (offset-free), seasonal caches carry their own tag, Snohomish/FWC/UMN-SFWMD caches are treated as c1 (offset -0.1), as in note 11.
* Lake masks for Snohomish/FWC come from county/FWC polygons (differ from the note-04 stack mask by 7-12 % of pixels); NLA/UMN/SFWMD from registry analysis polygons.
* Local cache bytes read were not measured per file this run; the Sentinel-2 network bytes were 0 by construction (guard).

## 9. Recommendations for the next iteration (ranked; NOT applied; each needs an amendment, a dev set with power, and a fresh TEST)

1. **Build a dev/test pair that can discriminate before tuning anything further.** Gates (a)/(e) need >= 3 independent lakes with >= 30 interior positives in TEST, and a DEV negative control with a turbid reservoir in it. Today DEV has 1 effective positive lake and 2 scoreable negatives, and TEST has 0 interior positives. Candidates: SFWMD/UMN/UMR polygons with same-year scenes, additional dated floating-leaf polygon sets, or counting a shore ring that the cell definition does not blank.
2. **Redesign BLOOM_AMBIGUOUS** (the most damaging new behaviour: 36 % of NLA and 45 % of FWC cell-scenes, whole-lake blanking at Kissimmee and Buchanan, 13 % of clear Guntersville scenes). Exclude pixels near cloud/cirrus from the tail, use a robust statistic (median/MAD or a lower quantile), require spatial structure, make it a per-cell guard, and keep the 0.10 cap for true bloom. Re-measure on Guntersville May-June, where the clear-scene floor is 0.2-0.27.
3. **Fix the turbid-reservoir false flags** (gate d; Keystone 11.3 % unchanged from V1 12.0 %, not shore-driven). Needs a diagnosis of the 2017-08-03 scene (floor 0.071, 701 of 6,197 belt cells flagged), then a bloom/turbidity test that is not the open-water NIR tail (red-edge or FAI-type contrast).
4. **Re-think the haze guard rather than tune it.** The grid shows a smooth monotone trade (default 0 of 24 recall vs 23 of 24 with guard off) with no false positive in 379 dev cells either way; a cluster/area-based or cloud-adjacency rule, calibrated label-free on open-water lakes, is the V1 recommendation still outstanding. Report (b) separately for guard-on and guard-off settings on hazy scenes.
5. **Co-located truth for gate (c).** Spearman 0.2 (0.1-0.24 across V1 configurations and v0.2) with CIs spanning 0 says the shoreline-plot statistic cannot reach 0.5 with an interior belt; this is a blocker, not a tuning problem.
6. **S definition** (still unreachable on small lakes: 0 of 5 Snohomish, 15 of 25 NLA TEST): measure the 75 % test on interior cells, as recommended in note 11.
7. **Burst rule**: use `max(median, 3)`; Bitter Lake lost 5 of 10 accepted scenes with no vegetation present.
8. **Plant detection on UMN-class taxa and Florida points** (recall 0.04-0.14, mostly among read cells): characterise which of the `surface_strict` taxa produce NDVI >= 0.30 canopies at 10 m before treating this as an observer failure.
9. **Report fallback-only lakes as such** (1 TEST lake) and keep `SATELLITE_ACCEPTED_PASS` for >= 50 % passes only (V1 recommendation 4, unchanged).

## 10. Reproduction

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/v2_eval/scripts
PY=../../../.venv/bin/python        # rasterio/shapely/scipy; numpy-only venv: ../../../../.testvenv/bin/python for the observer alone
$PY t1_split.py                      # split + declared interpretations (before any scoring)
$PY t2_grid.py && $PY t3_choose.py   # DEV grid -> out/grid_dev*.{json,md}, out/chosen_params.frozen.json (writes the file)
$PY t4_test.py                       # TEST once, frozen pair (reads chosen_params.frozen.json, asserts it exists)
$PY t4b_umn_sfwmd.py                 # UMN / SFWMD supplementary (existing caches only)
$PY t6_seasonal_desc.py && $PY t6b_nla_cloud.py   # descriptive
$PY t5_metrics.py                    # all tables -> out/tables_v02.md, out/metrics_v02.json
```
Do not re-run `t3_choose.py` casually: it rewrites the frozen file with a new timestamp. The observer is imported from `Sector_Engine-vegetation-adoption/jobs/vegetation-brain` and never modified; the adapter reuses `v1_eval/scripts/v1lib.py` and `nla/scripts/n5_score.py` read-only.
