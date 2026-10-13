# 11. Evaluation of the SHIPPED V1 vegetation observer module (frozen pre-registration + A1-A3)

Offline. Subject: `Sector_Engine-vegetation-adoption/jobs/vegetation-brain/vegetation_brain/observer.py` (imported, not re-implemented; no repo file was edited or committed; `sys.dont_write_bytecode` set). Everything is under `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/v1_eval/` (`scripts/`, `out/`); new files are logged with bytes and sha256 in `../../MANIFEST.jsonl`. Gates are those of `VEGETATION_VALIDATION_PREREGISTRATION.md` section 5 unchanged. Nothing was tuned: the NIR floor was calibrated label-free and frozen before any scoring (file `out/calibration.frozen.json`, written 2026-10-13 16:19:39, before the first scoring run).

## 1. Headline (read first)

| question | answer |
|---|---|
| A3 NIR floor | Pooled P99.5 of B8A over SCL-water >= 100 m from the edge in accepted scenes of Hartwell + Leech Lake = **0.1272**, so `NIR_PLANT_MIN = 0.13` (A3 rule, rounded up to 0.005). Hartwell alone: P99.5 0.0277 (floor would be 0.03); Leech alone 0.1497. The rule as written is dominated by Leech Lake spring/ice-shoulder and bloom/turbid-water scenes. The 0.13 floor is frozen and used for every verdict below. A 0.03 run (the module default) is shown as a labelled sensitivity only. |
| Does the shipped module pass anything? | **No gate is PASSED.** (a) NOT_TESTABLE per A3 (no lake has >= 30 interior positive cells; pooled recall would be 0.00 anyway); (b) literal PASS (0 false cells in 584 open-water cells) but 55 % of those cells are UNKNOWN and 0 of 5 Snohomish lakes has an accepted pass; (c) **FAIL** (AUC 0.77, Spearman 0.11, n = 32 lakes, 9 regions); (d) **FAIL** (6 of 8 negatives scored; 5 of 6 are <= 2 %, Keystone Lake OK is 12.0 %; mean 2.1 %; 2 negatives UNKNOWN); (e) **FAIL** by computation (no true positive recovered, F1 = 0) and statistically untestable (24 interior positives, 2 lakes). |
| Snohomish (5 lakes, A1.5 interior-only) | **Zero accepted passes on all 5 lakes** (60 in-window scenes, 0 reach 50 % known-interior coverage). Observer P/A/S: TP 0 of 24 interior positives (recall 0.00), FP 0, precision undefined, F1 0. Dominant refusal: `HAZE` (43.7 % of eligible cell-scenes), then `SHORE_ADJACENT` 30.0 %, `CLOUD` 8.5 %, `DARK_WATER` 0.1 %. |
| FWC LTM points (7 lakes, 1,205 surface-point cells) | Recall (UNKNOWN = miss) **P 0.007, A 0.005, S 0.000** (known-only P 0.138). Gate gives no credit (presence-only; A1.7 already says Florida cannot support PARTIAL). |
| NLA 2017 (48 eligible lakes, 47 run; Lake Mead skipped as in note 07) | 29 of 47 lakes have an accepted pass, **2 are P-reachable (>= 3 accepted)**, 5 more are scored from the 25-50 % fallback pass only; 32 lakes scored (7 pos / 6 neg / 19 amb). Observer P (= A): AUC 0.77 (95 % CI 0.46-1.00), Spearman 0.11 (-0.24..0.47). Observer S is reachable on only 6 lakes (no positive) because the 75 %-seen test counts the shore ring as unseen. |
| Did A1 fix the defects it named? | **Dark-water blanking: yes** (`DARK_WATER` is 0.1 % of eligible cell-scenes, was 40-58 % of cells). **Whole-scene SWIR gate: removed, but replaced by a pixel-level HAZE rule (SWIR > 0.02 on non-plant water, 100 m Chebyshev standoff, no minimum count) that is now the largest refusal and blocks passes more than the old gate did on the Snohomish lakes: not fixed in effect.** **Acceptance statistic: replaced correctly (known-interior share), but with HAZE on only 0 % (Snohomish), 21 % (NLA) and 21 % (FWC) of in-window scenes reach 50 %;** with the HAZE guard monkeypatched off (diagnostic) that becomes 83 %, 50 % and 60 %. |
| Network | **0 bytes** of Sentinel-2 downloaded (cap was 1 GB). The adapter has no reader; a socket guard (`net_guard()`) makes any connection raise. Local cache bytes read are listed in section 10. |

## 2. Method and adapter

* **Subject imported** with `sys.path.insert(0, .../jobs/vegetation-brain)`; `observer.reflectance`, `scene_fields`, `to_cells`, `Scene`, `select_scenes`, `observe(mode='S'|'A'|'P')`, `presence` are called as shipped. `observer.NIR_PLANT_MIN` is set by monkeypatch in the adapter process only (`v1lib.freeze_floor`).
* **Adapter** (`scripts/v1lib.py`): cached true-reflectance windows are converted back to raw DN in the convention of the originating collection (`refl_to_dn`) and then passed through `observer.reflectance(dn, collection)`, so the module owns the c1 (-0.1 offset) / l2a (offset-free) convention. NLA caches already hold raw DN plus a collection tag (used directly; 2017 is `sentinel-2-l2a`). Seasonal caches carry `src` (c1 / l2a). Snohomish/FWC caches hold float reflectance with no collection tag and are treated as c1 convention (round trip is exact to 1e-4). 20 m bands are already nearest-repeated to 10 m in every cache (block-constancy verified by note 06). The lake mask is the polygon rasterised on the 10 m scene grid with the pixel-centre rule: registry `geometry.v1.analysis` polygons for NLA (cached in `adoption/nla/data/geom/`), county polygons (`data/snoco_layer15.geojson`) for Snohomish, FWC LTM lake polygons for the FWC lakes, `adoption/seasonal/geom/` for the calibration lakes and Guntersville. Multi-tile NLA dates are mosaicked on a per-lake union canvas (first tile wins where SCL = 0).
* **Cells** are the module's own 5 x 5 pixel blocks from the window origin (so cell edges differ from the web-mercator frame of notes 06/07; ground size is 50 m, not ~36 m; absolute cell counts are therefore not comparable with note 06).
* **Truth.** Snohomish: positive = floating-leaf share >= 0.5 of the cell (note 05/06 convention), negative = strict-none (< 5 % of any mapped class; headline) or buffered-none (no label within 2 cells), restricted to interior cells; distance histogram bins 0/15/30/45/60/90/150/300 m from the 10 m EDT at the cell centre; matched precision is shown beside raw-prevalence precision (A1.5). FWC: cells containing >= 1 floating or emergent point. NLA: eligible set, positive/negative/ambiguous classes and Spearman/AUC/bootstrap-over-lakes code reused unchanged from the earlier NLA harness (`adoption/nla/scripts/n5_score.py`); belt = interior cells with centre distance in (10, 90] m, share = PLANT cells / read cells (UNKNOWN excluded), lake scored if >= 10 read belt cells. Reference date = first NLA visit date; scene window = module's +-21 d.
* **Gate d reading.** The prereg text says each negative-control lake must show a lake-level flagged share <= 2 %. The earlier NLA note used the mean over negatives. Both are shown; the verdict row uses the literal per-lake reading, and the mean reading is also FAIL for the frozen config.
* **Configurations.** `frozen` (NIR floor 0.13) is the only one that carries gate verdicts. `prov` (floor 0.03, the shipped default) is a labelled sensitivity. `*_nohaze` sets `contract.HAZE_SWIR = 1e9` (monkeypatch, in-process) to quantify what the haze guard does; it is a DIAGNOSTIC for the recommendations in section 8, no value was chosen from it, and it carries no gate verdict.

## 3. Step 1: NIR floor calibration (A3), done and frozen before scoring

Rule (A3): `NIR_PLANT_MIN = max(0.03, P99.5 of B8A reflectance over SCL-water pixels >= 100 m from the polygon edge, accepted scenes only)`, rounded up to 0.005. Accepted = the shipped module's pass acceptance (known-interior coverage >= 0.5) evaluated at the provisional floor 0.03. Scenes: all cached dates 2017-2025 of Hartwell (322 scenes, 168 accepted) and Leech Lake (320 scenes, 177 accepted); 42,582,093 pixels; no truth label used.

| lake | accepted / scenes | pixels | median B8A | P99 | P99.5 |
|---|---|---|---|---|---|
| Hartwell SC/GA | 168 / 322 | 21,859,429 | 0.0052 | 0.0244 | 0.0277 |
| Leech Lake MN | 177 / 320 | 20,722,664 | 0.0068 | 0.1276 | 0.1497 |
| **pooled** | 345 / 642 | 42,582,093 | | 0.096 | **0.1272** |

**Result: `NIR_PLANT_MIN = 0.13`** (frozen: `out/calibration.frozen.json`). Variant (observer-`seen` pixels only): P99.5 0.1235, which would also round to 0.125.

Why it is high (post-hoc diagnosis, does not alter the frozen value; `out/calibration_diag.txt`): per-scene P99.5 exceeds 0.10 in 17 % of Leech accepted scenes (1 % of Hartwell), concentrated in March-April (ice-edge / floe pixels labelled SCL water; month medians 0.09 and 0.04) and in a handful of late-spring/summer scenes whose cause was not verified (bloom, turbid water or thin haze are candidates). Cuts of the same two calibration lakes (never an evaluation lake; `out/calibration_alt_cuts_NOT_USED.json`): Jun-Sep both lakes P99.5 0.068, Jun-Sep Leech 0.074, Jun-Sep Hartwell 0.032. So even in summer a turbid or bloom lake sits well above Hartwell, which says an absolute NIR floor of any single value is a poor instrument: the floor that kills rounding noise at Hartwell (0.03) costs real plants (aquatic canopy NIR is plausibly in the 0.05-0.15 range; not measured here) when it is raised to the Leech tail.

Cost of 0.13 vs 0.03, same scenes, HAZE off: FWC recall (P) 0.154 vs 0.259; Snohomish interior recall (P, A) 0.83 / 0.67 vs 0.96 / 0.96.

## 4. Step 2a: Snohomish WA polygons (5 lakes, cell level, interior population)

Frozen config (floor 0.13), strict-none negatives, 50 m cells, reference = survey date, scenes +-21 d (60 in-window scenes; gaps 1-21 d). Interior positives: **24** (Roesiger 23, Serene 1; whole-lake positives 51; interior open-water negatives 584).

| obs | TP | FP | FN (interior) | P raw | R interior (UNK = miss) | F1 raw | IoU | FPR (all open-water cells) | FPR (known only) | open-water cells UNKNOWN | R whole-lake |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 0 | 0 | 24 | n/a | 0.000 | n/a | 0.000 | 0.000 | n/a | 1.000 | 0.000 |
| A | 0 | 0 | 24 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.000 | 0.548 | 0.000 |
| P | 0 | 0 | 24 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.000 | 0.548 | 0.000 |

Per lake (all observers the same here): Serene NONE (no scene >= 25 %); Blackmans NONE; Storm, Roesiger, Bosworth hold only a 25-50 % **fallback** pass, `persistence: INSUFFICIENT`, presence UNKNOWN. **No lake has an accepted pass.** Bootstrap over lakes is degenerate (TP = 0 in every resample): F1 = 0 point estimate, lower bound 0.

Open-water FPR is 0 flagged of 584 cells, but only 45 % of those cells (264) are known under A/P and none under S, so that number is not evidence of a low false-positive rate.

Sensitivity and diagnostics (not gate evidence; same scenes and truth):

| config | obs | TP | FP | FN | P raw | R interior | F1 raw | R whole-lake | open-water cells UNKNOWN | accepted scenes / in-window (5 lakes) |
|---|---|---|---|---|---|---|---|---|---|---|
| prov (floor 0.03) | A, P | 0 | 0 | 24 | n/a | 0.000 | n/a | 0.000 | 0.524 | 1 / 60 |
| frozen + HAZE off | A | 16 | 0 | 8 | 1.000 | 0.667 | 0.800 | 0.314 | 0.000 | 50 / 60 |
| frozen + HAZE off | P | 20 | 0 | 4 | 1.000 | 0.833 | 0.909 | 0.392 | 0.000 | 50 / 60 |
| prov (0.03) + HAZE off | A, P | 23 | 0 | 1 | 1.000 | 0.958 | 0.979 | 0.451 | 0.003 / 0.000 | 50 / 60 |

HAZE off removes the whole problem on these clear PNW lakes, with no false cell in 584; this is the same precision picture notes 04-06 found, and it says the plant rule and the A1 dark-water rule are sound while the haze rule is the blocker. Because only 24 interior positives exist (and Roesiger alone carries 23), this is a feasibility signal, not a gate result.

Note on S: `observer.observe(mode='S')` requires >= 75 % of ELIGIBLE cells non-UNKNOWN, and the SHORE_ADJACENT ring is UNKNOWN by construction (30 % of eligible cells on these lakes), so S is structurally unreachable on small lakes (0 of 5 here, 6 of 47 on NLA).

## 5. Step 2b: FWC LTM points (recall only)

Same lakes and survey dates as note 06 (Orange, Griffin, Apopka, Harris, Panasoffkee, Yale, Cypress), scenes +-21 d of the survey date, 1,205 cells with a floating or emergent point (790 of them interior).

| config | obs | recall (UNK = miss) | recall interior-only | recall among known cells | bootstrap CI (lakes) |
|---|---|---|---|---|---|
| frozen 0.13 | S | 0.000 | 0.000 | 0.000 | 0.000-0.000 |
| frozen 0.13 | A | 0.005 | 0.008 | 0.158 | 0.000-0.014 |
| frozen 0.13 | P | 0.007 | 0.011 | 0.138 | 0.000-0.022 |
| prov 0.03 | P | 0.045 | 0.068 | 0.470 | 0.002-0.104 |
| frozen + HAZE off (diag.) | P | 0.154 | 0.235 | 0.270 | 0.074-0.283 |
| prov 0.03 + HAZE off (diag.) | P | 0.259 | 0.395 | 0.437 | 0.141-0.390 |

Lake-level (frozen, P): Orange PRESENT (persistence), Griffin PRESENT (persistence), Apopka PRESENT, Yale PRESENT, Harris UNKNOWN, Panasoffkee UNKNOWN (no scene >= 25 %), Cypress UNKNOWN. Every configuration is far below 0.70 and, with presence-only truth, none can support PARTIAL (A1.7). Note 06 non-V1 numbers were 0.12 (S/A/P, UNKNOWN = miss) and 0.38-0.47 among readable cells.

## 6. Step 2c/2d: NLA 2017 (section 4 protocol) and the 2018-2019 secondary

Eligible set 48 lakes (15 positive / 8 negative / 25 ambiguous, from `nla_lake_classes.csv`); 47 run (Lake Mead skipped as too large, as in note 07). Scenes: cached S2 L2A windows within +-21 d of the 2017 visit (all `sentinel-2-l2a`; zero NO_SCENE). Secondary: 2018 and 2019 anniversary windows, <= 6 nearest dates per year, tile cloud < 50 %; labelled separately and averaged over the two years per lake as in note 07.

**Frozen config, gate view** (`out/metrics_nla_frozen.json`, per-lake CSVs `out/nla_lakelevel_frozen_*.csv`):

| set / obs | lakes scored | pos / neg / amb | regions | AUC (95 % CI) | Spearman (95 % CI) | negative-control share, mean | max | negatives <= 2 % | gate c | gate d (each lake) |
|---|---|---|---|---|---|---|---|---|---|---|
| primary S | 6 | 0 / 2 / 4 | 3 | n/a | -0.31 | 0.000 | 0.000 | 2 / 2 scored | NOT_TESTABLE | PASS (2 lakes only) |
| **primary A** | 32 | 7 / 6 / 19 | 9 | 0.77 (0.47-1.00) | 0.13 (-0.22..0.46) | 0.021 | 0.120 | 5 / 6 scored (of 8) | **FAIL** | **FAIL** |
| **primary P** | 32 | 7 / 6 / 19 | 9 | 0.77 (0.46-1.00) | 0.11 (-0.24..0.47) | 0.021 | 0.120 | 5 / 6 scored (of 8) | **FAIL** | **FAIL** |
| secondary S | 8 | 0 / 1 / 7 | 5 | n/a | 0.38 | 0.000 | 0.000 | 1 / 1 | NOT_TESTABLE | n/a |
| secondary A | 34 | 10 / 6 / 18 | 9 | 0.73 (0.49-0.94) | 0.08 (-0.28..0.43) | 0.003 | 0.014 | 6 / 6 scored | FAIL | PASS |
| secondary P | 34 | 10 / 6 / 18 | 9 | 0.73 (0.50-0.93) | 0.14 (-0.22..0.47) | 0.003 | 0.014 | 6 / 6 scored | FAIL | PASS |

Reading. Gate (c) is testable (32 lakes, 9 regions) and fails on both legs; the AUC point estimate is close to the earlier observers' 0.8 but its interval reaches 0.46, and Spearman 0.11 is 0.4 below the gate. Gate (d): the negatives that survive are mostly lakes where the observer made no call at all or scored on very few read cells (Sherman 14, Willard Bay 26 belt cells read; Buchanan and Monroe UNKNOWN). The one negative with a large belt sample, **Keystone Lake OK, is 12.0 % flagged** (3,381 read belt cells; 12.1 % at 30-60 m and 11.9 % at 60-90 m, i.e. not a shore-proximity effect; cause not investigated here, a bloom or turbid-water spectrum is a candidate and `BLOOM_AMBIGUOUS` is declared in the contract but not implemented). **Distance structure:** the module's own `interior` rule removes every cell touching the polygon edge, so no cell has a centre closer than ~30 m and the "10-30 m" bin is empty; the false-flag share is the same at 30-60 m and 60-90 m (negatives 5.6 % / 5.7 %; positives 9.1 % / 7.2 %).

Secondary years are labelled separately and are not mixed into the primary. Their gate-(d) PASS is not an improvement in the module: the capped (<= 6 dates/year) cloud-filtered scenes give fewer, cleaner reads and the same Spearman failure.

**Diagnostic configurations** (labelled; same lakes):

| config | obs | scored | AUC | Spearman | neg mean | negatives <= 2 % | gate c | gate d (each) |
|---|---|---|---|---|---|---|---|---|
| prov 0.03 | P | 32 | 0.76 | 0.06 | 0.023 | 5 / 6 | FAIL | FAIL |
| frozen + HAZE off | P | 43 | 0.61 | 0.12 | 0.017 | 6 / 8 | FAIL | FAIL |
| prov 0.03 + HAZE off | P | 43 | 0.75 | 0.23 | 0.019 | 6 / 8 | FAIL | FAIL |

Removing the haze guard roughly raises the scored lakes from 32 to 43, accepted-pass lakes from 29 to 41 and P-reachable lakes from 2 to 18, but it does **not** produce a passing lake-level signal: gate (c) still fails (best Spearman 0.23) and gate (d) still fails on a per-lake basis. So the NLA failure is not mainly a coverage problem.

### Per-lake table (frozen floor, primary 2017, observer P)

Sorted by NLA class then mean(emergent, floating) cover code. `kind` is the module's evidence kind; "(fallback)" means only a 25-50 % coverage pass existed. `belt read` = belt cells with a plant/no-plant call.

| lake | st | cls | mean_ef | scenes | acc | kind | belt read | belt share | presence |
|---|---|---|---|---|---|---|---|---|---|
| Grand Lake | LA | AMB | 0.95 | 7 | 1 | SATELLITE_ACCEPTED_PASS | 188 | 0.011 | NOT_OBSERVED |
| Whitefish Lake | MT | AMB | 0.38 | 4 | 1 | SATELLITE_ACCEPTED_PASS | 180 | 0.000 | NOT_OBSERVED |
| Skiatook Lake | OK | AMB | 0.25 | 6 | 1 | SATELLITE_ACCEPTED_PASS | 1413 | 0.000 | PRESENT |
| Harlan County Lake | NE | AMB | 0.19 | 5 | 1 | SATELLITE_ACCEPTED_PASS | 172 | 0.971 | PRESENT |
| Lake Wawasee | IN | AMB | 0.17 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Allatoona | GA | AMB | 0.15 | 4 | 0 | SATELLITE_ACCEPTED_PASS(fallback) | 1668 | 0.219 | PRESENT |
| Keuka Lake | NY | AMB | 0.15 | 2 | 1 | SATELLITE_ACCEPTED_PASS | 997 | 0.039 | PRESENT |
| Waldo Lake | OR | AMB | 0.12 | 2 | 1 | SATELLITE_ACCEPTED_PASS | 104 | 0.000 | NOT_OBSERVED |
| Beltzville Lake | PA | AMB | 0.10 | 6 | 1 | SATELLITE_ACCEPTED_PASS | 229 | 0.061 | PRESENT |
| Burnsville Lake | WV | AMB | 0.10 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Lake Winnisquam | NH | AMB | 0.10 | 3 | 2 | SATELLITE_ACCEPTED_PASS | 406 | 0.005 | NOT_OBSERVED |
| Raystown Lake | PA | AMB | 0.10 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Enemy Swim Lake | SD | AMB | 0.08 | 8 | 2 | SATELLITE_ACCEPTED_PASS | 23 | 0.000 | NOT_OBSERVED |
| Folsom | CA | AMB | 0.05 | 4 | 0 | SATELLITE_ACCEPTED_PASS(fallback) | 49 | 0.082 | PRESENT |
| Rye Patch Reservoir | NV | AMB | 0.05 | 2 | 1 | SATELLITE_ACCEPTED_PASS | 360 | 0.025 | PRESENT |
| Bitter Lake | SD | AMB | 0.00 | 15 | 5 | SATELLITE_PERSISTENCE | 1005 | 0.000 | NOT_OBSERVED |
| Canton Lake | OK | AMB | 0.00 | 4 | 1 | SATELLITE_ACCEPTED_PASS | 17 | 0.824 | PRESENT |
| Fish Lake | UT | AMB | 0.00 | 4 | 1 | SATELLITE_ACCEPTED_PASS | 184 | 0.000 | NOT_OBSERVED |
| Heron Lake | NM | AMB | 0.00 | 3 | 0 | SATELLITE_ACCEPTED_PASS(fallback) | 330 | 0.167 | PRESENT |
| Lake Tschida | ND | AMB | 0.00 | 7 | 1 | SATELLITE_ACCEPTED_PASS | 443 | 0.212 | PRESENT |
| Lake Zoar | CT | AMB | 0.00 | 9 | 1 | SATELLITE_ACCEPTED_PASS | 361 | 0.000 | NOT_OBSERVED |
| Philpott Lake | VA | AMB | 0.00 | 6 | 0 | NONE | 0 | n/a | UNKNOWN |
| Skaneateles Lake | NY | AMB | 0.00 | 4 | 0 | NONE | 0 | n/a | UNKNOWN |
| Smithville Lake | MO | AMB | 0.00 | 8 | 2 | SATELLITE_ACCEPTED_PASS | 1265 | 0.317 | PRESENT |
| Walker Lake | NV | AMB | 0.00 | 2 | 1 | SATELLITE_ACCEPTED_PASS | 5 | n/a | PRESENT |
| Keystone Lake | OK | NEG | 0.00 | 8 | 1 | SATELLITE_ACCEPTED_PASS | 3381 | 0.120 | PRESENT |
| Lake Buchanan | TX | NEG | 0.00 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Lake Hickory | NC | NEG | 0.00 | 6 | 1 | SATELLITE_ACCEPTED_PASS | 1118 | 0.003 | PRESENT |
| Lake Jocassee | SC | NEG | 0.00 | 3 | 1 | SATELLITE_ACCEPTED_PASS | 1294 | 0.000 | NOT_OBSERVED |
| Monroe Lake | IN | NEG | 0.00 | 3 | 0 | NONE | 0 | n/a | UNKNOWN |
| Pomme de Terre Lake | MO | NEG | 0.00 | 8 | 1 | SATELLITE_ACCEPTED_PASS | 1446 | 0.003 | PRESENT |
| Sherman Reservoir | NE | NEG | 0.00 | 9 | 1 | SATELLITE_ACCEPTED_PASS | 14 | 0.000 | NOT_OBSERVED |
| Willard Bay Reservoir | UT | NEG | 0.00 | 4 | 2 | SATELLITE_ACCEPTED_PASS | 26 | 0.000 | NOT_OBSERVED |
| Piney Run Lake | MD | POS | 1.56 | 9 | 2 | SATELLITE_ACCEPTED_PASS | 96 | 0.062 | PRESENT |
| Griffin | FL | POS | 1.50 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Concord Pond | DE | POS | 1.17 | 6 | 0 | SATELLITE_ACCEPTED_PASS(fallback) | 14 | 0.000 | UNKNOWN |
| Arkabutla Lake | MS | POS | 0.85 | 3 | 0 | SATELLITE_ACCEPTED_PASS(fallback) | 508 | 0.065 | PRESENT |
| Box Butte Reservoir | NE | POS | 0.75 | 2 | 1 | SATELLITE_ACCEPTED_PASS | 82 | 0.549 | PRESENT |
| Saguaro | AZ | POS | 0.75 | 9 | 2 | SATELLITE_ACCEPTED_PASS | 1 | n/a | NOT_OBSERVED |
| Records Pond | DE | POS | 0.70 | 5 | 0 | NONE | 0 | n/a | UNKNOWN |
| Wilson Lake | KS | POS | 0.65 | 3 | 1 | SATELLITE_ACCEPTED_PASS | 1080 | 0.001 | NOT_OBSERVED |
| Lake Washington | MS | POS | 0.50 | 4 | 3 | SATELLITE_PERSISTENCE | 163 | 0.147 | PRESENT |
| Lake Habeeb (Rocky Gap) | MD | POS | 0.39 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Nickajack Lake | TN | POS | 0.35 | 4 | 2 | SATELLITE_ACCEPTED_PASS | 884 | 0.131 | PRESENT |
| Eagle Creek Reservoir | IN | POS | 0.30 | 1 | 0 | NONE | 0 | n/a | UNKNOWN |
| Tippecanoe Lake | IN | POS | 0.30 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |
| Hamilton | AR | POS | 0.25 | 2 | 0 | NONE | 0 | n/a | UNKNOWN |

## 7. Step 3: guards, reachability, bursts, gate verdicts, comparison

### 7.1 Per-guard UNKNOWN shares (frozen floor; share of eligible cell-scenes, pooled over every in-window scene; "known" = cells with a plant / no-plant call)

| set | known | HAZE | CLOUD | SHORE_ADJACENT | SHADOW | INSUFFICIENT_VALID_PIXELS | DARK_WATER | ICE_OR_SNOW | cell-scenes |
|---|---|---|---|---|---|---|---|---|---|
| Snohomish (5 lakes) | 0.168 | **0.437** | 0.085 | 0.300 | 0.010 | 0 | 0.001 | 0 | 12,300 |
| FWC points (7 lakes) | 0.284 | **0.308** | 0.321 | 0.036 | 0.016 | 0.035 | 0.001 | 0 | 813,843 |
| NLA 2017 primary (47 lakes) | 0.214 | 0.237 | **0.326** | 0.117 | 0.026 | 0.077 | 0.001 | 0.002 | 2,562,830 |
| DIAG. Snohomish, HAZE off | 0.587 | 0 | 0.085 | 0.300 | 0.010 | 0 | 0.018 | 0 | |
| DIAG. NLA primary, HAZE off | 0.450 | 0 | 0.326 | 0.117 | 0.025 | 0.077 | 0.002 | 0.002 | |

Observation level (observer P, NLA primary, eligible-cell weighted): `PASS_NOT_ACCEPTED` 0.218, HAZE 0.146, SHORE_ADJACENT 0.081, CLOUD 0.054, SHADOW 0.018, DARK_WATER 0.001; lake presence PRESENT 20, NOT_OBSERVED 13, UNKNOWN 14 of 47. `GLARE` is never set (reserved for a Wind flag that the harness does not have), so glare is an untested guard.

### 7.2 Reachability

| set | lakes | with >= 1 scene in window | with an accepted (>= 50 %) pass | P-reachable (>= 3 accepted) | burst exclusions | share of in-window scenes accepted (>= 50 % / >= 25 %) |
|---|---|---|---|---|---|---|
| Snohomish | 5 | 5 | **0** | **0** | 0 | 0.00 / 0.35 |
| FWC points | 7 | 7 | 4 | 2 | 0 | 0.21 / 0.38 |
| NLA 2017 | 47 (48 eligible) | 47 | 29 | **2** | 1 lake (Bitter Lake SD: 3 of 5 accepted scenes dropped) | 0.21 / 0.34 |

P is therefore the shipped observer in name only: it degrades to A (`persistence: INSUFFICIENT`) on 45 of 47 NLA lakes and 5 of 5 Snohomish lakes. The Bitter Lake burst drop (a lake with NLA cover 0) removed three of five accepted scenes because the rule compares against a median of 0 or 1 plant cells; it did no harm here but shows that the 5x-median rule is unstable when the other scenes are near empty.

### 7.3 Gates of section 5 (frozen floor 0.13)

| gate | threshold | V1 module result | verdict |
|---|---|---|---|
| (a) cell precision >= 0.80 and recall >= 0.70, pooled and for each of >= 3 truth lakes with >= 30 positive cells | | 0 lakes with >= 30 interior positives (Roesiger 23, Serene 1); pooled P undefined, R 0.00 | **NOT_TESTABLE** (A3: Snohomish limits make (a) untestable); the pooled clause alone would FAIL |
| (b) open-water FPR <= 2 % cell level | | 0 / 584 flagged (0.0 %); but 54.8 % of those cells UNKNOWN, 2 of 5 lakes have no observation, no lake has an accepted pass | **PASS (literal), weak**; not demonstrated for any accepted-pass lake |
| (c) NLA lake AUC >= 0.80 and Spearman >= 0.50 on >= 15 lakes, >= 3 regions | | n = 32, 9 regions, AUC 0.77 (0.46-1.00), Spearman 0.11 | **FAIL** |
| (d) negative-control flagged share <= 2 % | | per lake: 5 of 6 scored <= 2 %, Keystone 12.0 %; mean 2.1 %; 2 of 8 negatives UNKNOWN | **FAIL** |
| (e) lower bootstrap bound of pooled F1 >= 0.65 | | F1 = 0 (no TP); bootstrap over 5 lakes (2 with positives) degenerate | **FAIL** by computation; statistically NOT_TESTABLE |

Validation state implied: unchanged, `NOT_VALIDATED`/RESEARCH. Entry to RESEARCH (observer reproduced from production code and scored on >= 2 independent truth sets) is met by this run and notes 06-07; CALIBRATION and above are not reached.

### 7.4 Comparison with the non-V1 observers (notes 06 and 07)

| quantity | note 06/07 non-V1 (prereg-v1 guards as written) | V1 module, frozen 0.13 | V1, floor 0.03 (labelled) | V1 frozen + HAZE off (diag.) | V1 0.03 + HAZE off (diag.) |
|---|---|---|---|---|---|
| Snohomish recall, P (UNK = miss) | 1.00 on 60 reachable (40 m) cells | **0.00** (24 interior) | 0.00 | 0.83 | 0.96 |
| Snohomish precision raw, P | 0.97 | undefined (0 flagged) | undefined | 1.00 | 1.00 |
| Snohomish open-water FPR, P (S) | 0.2 % (S 3.2 %) | 0.0 % of 584; 55 % UNKNOWN | 0.0 % | 0.0 % | 0.0 % |
| Snohomish lakes with accepted pass | 3 of 5 | **0 of 5** | 1 of 5 | 5 of 5 | 5 of 5 |
| FWC points recall (UNK = miss), P | 0.12 | **0.007** | 0.045 | 0.154 | 0.259 |
| NLA lakes scored (A/P) | 26 (7 pos / 4 neg) | 32 (7 / 6) | 32 | 43 (12 / 8) | 43 |
| NLA AUC, A (P) | 0.82 (0.50-1.00) | 0.77 (0.77) | 0.76 | 0.61 (0.61) | 0.75 (0.75) |
| NLA Spearman, A (P) | 0.31 | 0.13 (0.11) | 0.07 | 0.13 (0.12) | 0.21 (0.23) |
| NLA negative-control mean share, A | 9.0 % (2 of 4 > 2 %) | 2.1 % (1 of 6 > 2 %) | 2.3 % | 1.9 % (2 of 8 > 2 %) | 2.1 % (2 of 8 > 2 %) |
| NLA gate (c) / (d) | FAIL / FAIL | FAIL / FAIL | FAIL / FAIL | FAIL / FAIL | FAIL / FAIL |

Honest reading: the V1 module reduces the NLA negative-control share (9.0 % mean to 2.1 %, one lake still at 12 %) mostly because it declines to call (interior-only belt starting ~30 m, haze blanking, fallback-only lakes), not because the false-flag mechanism was demonstrated away: the one negative with a large sample is still 12 %. It buys that with a collapse in reachability on the lakes where the earlier observers worked (Snohomish recall 1.00 to 0.00 at the frozen config). The Snohomish and FWC numbers of notes 06 are not comparable cell for cell (different frame, 40 m reachable population vs interior population); the direction is not in doubt.

### 7.5 Did A1 fix the defects it identified?

1. **Dark-water blanking: fixed.** `DARK_WATER` is 0.1 % of eligible cell-scenes on all three sets (0.2 % on NLA with HAZE off); the old rule blanked 40-58 % of Snohomish cells. Open water now yields valid NO_PLANT looks. (The price is that plants with NIR below the floor become silent NO_PLANT; see 3 and 8.)
2. **Whole-scene SWIR rejection: not inherited, but the defect it represented moved to pixel level and got worse on small lakes.** The new HAZE guard marks any non-plant SCL-water pixel with SWIR > 0.02 (B11 over water has p95 0.03-0.05 even in clear scenes: 6-25 % of Roesiger's water pixels exceed 0.02 in non-hazy scenes) and then blocks a 100 m Chebyshev neighbourhood around it, with no minimum cluster size and no tie to cloud. It is the largest refusal on Snohomish (43.7 %) and a top-two refusal on FWC and NLA. Switching it off in-process raises accepted Snohomish scenes from 0 to 50 of 60.
3. **Acceptance statistic: changed correctly, and now irrelevant as written.** The known-interior share is a sensible statistic, but its denominator is limited by HAZE and CLOUD, so acceptance (>= 0.5) is met by 0 % / 21 % / 21 % of scenes (Snohomish / NLA / FWC), and P reachability is 0 / 2 / 2 lakes. With HAZE off the same statistic accepts 83 % / 50 % / 60 %.

New defects found by this run: (i) the A3 calibration rule yields 0.13 and costs recall (FWC P 0.007 vs 0.045 at 0.03, same scenes); (ii) S is structurally unreachable on small lakes (shore ring counted as unseen in the 75 % rule); (iii) `interior` removes all edge-touching cells so the first usable cell centre is ~30 m in and the "10-30 m" belt is empty; (iv) the burst rule is unstable when the comparison median is 0-1; (v) acceptance falls back to a 25-50 % pass labelled `SATELLITE_ACCEPTED_PASS` (flag `low_coverage_fallback` set), and 5 of the 32 scored NLA lakes are scored on such a pass.

## 8. Step 5: recommendations, ranked by expected effect on the failing gates (NOT done in this run; nothing here was tuned on an evaluation lake)

Any change below needs a new amendment (definitions only, thresholds of sections 5-7 untouched), an independent calibration set, and a re-run of this evaluation on fresh or held-out lakes.

1. **Replace the per-pixel HAZE standoff** (largest effect; gates a, b, e and reachability). Evidence: HAZE is 43.7 % / 30.8 % / 23.7 % of eligible cell-scenes; HAZE-off diagnostic moves Snohomish accepted scenes 0 to 50 of 60, NLA P-reachable lakes 2 to 18, Snohomish interior recall 0.00 to 0.83-0.96 with 0 FP in 584 cells. Options (to be calibrated label-free on open-water lakes such as the A3 pair): require a connected patch or a minimum count (not one pixel), take SWIR from a spatial median or an area share, drop the 100 m Chebyshev growth or tie it to cloud adjacency, and take the 20 m B11 noise level into account (a clear Roesiger scene has p95 0.03). Note the concept itself, not only V1's 100 m growth, is the issue: production's own `hidden` indicator (haze pixels offshore plus a 400 m / SWIR > 0.010 haze edge) also left only 4-27 % of Snohomish cells known under the prereg guards in note 06; production never noticed because its pass acceptance counts turbidity-read cells and ignores hidden cells, whereas V1 acceptance now inherits the blanking.
2. **Fix the NIR floor protocol** (gates a, e, FWC recall). The A3 rule is contaminated by ice-edge and turbid-water scenes of one calibration lake. A new amendment could restrict calibration to snow/ice-free months, exclude scenes with SCL snow/cirrus in the lake, and add more than two lakes, or replace the absolute floor by a rule that does not depend on lake turbidity (for example require NDVI >= 0.30 plus a minimum NIR - SWIR contrast, or a per-scene dark-water level). Evidence: floor 0.13 vs 0.03, same scenes: FWC P recall 0.154 vs 0.259 (HAZE off). Jun-Sep cuts of the calibration lakes alone give 0.032-0.074.
3. **Do not widen the shore band; examine bloom/turbid water instead** (gate d). The false flags in Keystone are as high at 60-90 m as at 30-60 m (11.9 % at 60-90 m vs 12.1 % at 30-60 m), and there is no usable 10-30 m bin, so shore width is not what drives them. Implement the declared-but-unused `BLOOM_AMBIGUOUS` check (for example red-edge/NDCI or FAI-type contrast, the production live branch has NDCI plumbing) and test it on negatives not used here.
4. **Acceptance and fallback handling** (reachability). Report fallback-only lakes as such everywhere (they currently carry `SATELLITE_ACCEPTED_PASS`); consider that P needs 3 accepted scenes in +-21 d while S2 revisit gives about 8 in 42 d and cloud + HAZE leave 0-2: after item 1 recheck P reachability (18 of 47 with HAZE off) before any change to the window or the 3-scene rule.
5. **S definition.** Use interior (not eligible) cells in the 75 % seen test, otherwise S, the evaluation baseline, cannot be computed on small lakes.
6. **Burst rule.** Use `max(median, 3)` or a robust ratio so a near-empty reference set does not trigger (Bitter Lake dropped 3 of 5 accepted scenes).
7. **Truth for gate (c).** NLA station cover (shore plots of ~10-15 m, 12.6 m median from the polygon edge) cannot be co-located with an interior-only cell belt; Spearman 0.1-0.2 across five configurations suggests the gate is not reachable by any observer with this covariate. Add co-located truth (UMN, UMR, FWC polygon, more floating-leaf lakes) before spending effort here.

## 9. Step 4: Guntersville 2025 sanity (UNVALIDATED)

The central-reach pilot rasters of note 06 are not cached (only derived arrays), so the 2025 scenes of the **seasonal back-test cache for Guntersville AL** were used instead: a 5 x 5 km upper-reach window (`windows.json`: lon -85.94..-85.885, lat 34.746..34.791), 37 scenes, 2,091 interior cells. This is a different part of the lake from the pilot, no truth exists, and the window is a vegetated flat. Observer P, four reference dates (`out/guntersville_2025.json`):

| config | 2025-06-15 | 2025-07-15 | 2025-08-15 | 2025-09-15 |
|---|---|---|---|---|
| frozen 0.13 | UNKNOWN (no scene >= 25 %) | PRESENT, fallback pass, plant 555 / read 689 of 2,091 interior | PRESENT, fallback, 696 / 814 | PRESENT, fallback, 667 / 782 |
| prov 0.03 | PRESENT fallback 514 / 651 | PRESENT, 1 accepted, 932 / 1,106 | PRESENT, persistence (4 accepted), 1,353 / 1,622 | PRESENT, persistence (4), 1,456 / 1,710 |
| frozen + HAZE off | PRESENT, persistence (3), 580 / 2,091 | 1,076 / 2,085 | 1,225 / 2,091 | 1,266 / 2,091 |

Frozen: HAZE 41-44 % of eligible cells, SHORE_ADJACENT 32 %. Plant cells are 79-86 % of the cells the module could read when the haze guard is on (it leaves only 689-1,710 of 2,091 interior cells readable) and 28-82 % of the interior when it is off; the window is a shallow vegetated reach, so a high share is plausible, but with no truth this is a smoke test only: the module runs, produces PRESENT, never produces NOT_OBSERVED here, and its persistence output depends entirely on the haze guard (3-4 accepted scenes with it off, 0-4 with it on).

## 10. Byte accounting

* **New Sentinel-2 network bytes: 0** (cap 1 GB). The adapter has no network reader; `net_guard()` replaces `socket.connect`, `create_connection` and `getaddrinfo` with an exception in every scoring process, so any attempt would have failed loudly. No STAC query, no registry fetch (polygons were already cached).
* Local cache bytes read (disk, no network): seasonal caches Hartwell 231 MB, Leech Lake 236 MB, Guntersville 241 MB; `experiments/out/s2cache` Snohomish + FWC files (1.0 GB total; each run reads the ones listed in the lake stacks, +-45 d of survey); NLA `s2cache_nla` (4.9 GB directory; only the +-21 d windows of the 47 lakes are read, per configuration, four configurations).
* New files written: scripts (`scripts/*.py`), `out/*.json|pkl|csv|log|md`; see `MANIFEST.jsonl` entries with kind `v1_eval`. No file inside any git repo was created or changed.

## 11. Limits

* Snohomish truth is small: 51 whole-lake and 24 interior positive cells, 23 of the 24 in one lake; per-lake gates and the bootstrap over lakes are underpowered or degenerate. This run cannot say what V1 would score with the haze guard fixed; the diagnostics are indications only.
* The cell grid is the module's 10 m-aligned block grid, not the web-mercator 50 m frame of notes 06-07; positives counted differently (51 whole-lake vs 117), so absolute counts do not compare.
* FWC and Snohomish lake masks come from the county/FWC polygons, not the canonical registry analysis geometry (those lakes are not in the registry or were not fetched); the NLA lakes use the registry analysis polygons. My Snohomish mask differs from the note-04 stack mask by 7-12 % of pixels (edge pixels).
* Acceptance during calibration was decided at the provisional floor 0.03; a literal reading of A3 would need an iteration, but the 0.13 vs 0.1235 (observer-seen) check shows the result is stable.
* Snohomish/FWC reflectance caches have no collection tag; treated as the c1 convention (round trip is exact). Collection mix on NLA secondary was taken from the per-file tag.
* `GLARE` (needs a Wind flag) and `BLOOM_AMBIGUOUS` are not exercised. Burst check and persistence were exercised on few lakes (burst: 1 lake; persistence: 2 NLA lakes at the frozen config).
* The NLA positive class is defined from shoreline stations; with the interior-only belt it compares different locations, so gate (c) failing may partly reflect the truth, not the observer.
* No accuracy claim is made for Guntersville.

## 12. Reproduction

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/v1_eval/scripts
PY=../../../.venv/bin/python
$PY s1_calibrate.py            # writes out/calibration.json (copy kept as out/calibration.frozen.json); then s1b_cal_diag.py, s1c_cal_alt.py (post-hoc, not used)
for t in frozen prov frozen_nohaze prov_nohaze; do
  $PY s2_snoco_fwc.py $t; $PY s3_metrics_snoco_fwc.py $t
  $PY s4_nla.py $t both;  $PY s5_nla_metrics.py $t
done
$PY s6_gunt.py; $PY s7_compile.py        # tables in out/tables.md
```
`frozen` = floor from `out/calibration.json` (0.13) and carries the verdicts; `prov` = 0.03; `_nohaze` sets `contract.HAZE_SWIR = 1e9` in the scoring process only (diagnostic). The repository code is imported from `Sector_Engine-vegetation-adoption/jobs/vegetation-brain` and never modified.
