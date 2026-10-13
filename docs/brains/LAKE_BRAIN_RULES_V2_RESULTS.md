# Lake Brain rules v2: hold-out results

**Result: 3 of 4 pre-registered criteria passed, 1 failed. H-C (rapid-change rate) FAILED. `/validation/lake-brain` stays `NOT_VALIDATED`. Nothing here is a claim of `PARTIAL`.**

- **Protocol:** `LAKE_BRAIN_RULES_V2_PREREGISTRATION.md` §2, committed (`4a59715b`) before any v2 code or test existed.
- **Harness:** `jobs/lake-brain/validation/holdout_v2.py` (+ `holdout_data.py`), committed (`23e1b211`) **before** the run. The rules it uses are `rules_v2.py`, which passes the same conformance fixture as the Swift rules (`docs/brains/conformance/lake_rules_v2.json`; 64 Python cases, 15 Swift tests) before it was used.
- **Run:** one run, run 1. No harness bug was found, so there was no second run. No rule or threshold was changed after seeing results.
- **Full numbers:** `jobs/lake-brain/validation/results/holdout_v2_results.json` (all criteria, breakdowns, per-lake years, data-QA flags) and `holdout_v2_results_lakes.csv` (one row per lake-year).

## 1. Results against the pre-registered criteria

| Criterion | Pre-registered threshold | Result | Verdict |
|---|---|---|---|
| **H-A** lakes passing (≥ 4 of 5 test years inside the lake's own LOYO 5th–95th coverage range) | ≥ 80 % of tested lakes | **80.4 %** (90 of 112 lakes) | **PASS** (by one lake: 89 would be 79.5 %) |
| **H-A** pooled p10–p90 coverage | in [0.75, 0.85] | **0.801** (nominal 0.80) | **PASS** |
| **H-B** pooled share outside p02–p98, tier FULL | ≤ 0.06 | **0.0529** (462 lake-years, 102 lakes, 168,219 days; nominal 0.04) | **PASS** |
| **H-C** pooled RAPID rate | in [0.03, 0.08] | **0.0349** (10,606 of 303,707 days, 193 lakes) | pass (part) |
| **H-C** lakes with a RAPID rate in [0.02, 0.09] | ≥ 70 % of lakes | **66.8 %** (129 of 193; 136 needed) | **FAIL** |
| **H-C** overall | both parts | | **FAIL** |
| **H-D (i)** pooled share of consecutive-day pairs whose label changes | ≤ 0.30 | **0.132** (40,072 of 302,494) | **PASS** |
| **H-D (ii)** pooled share of STABLE days inside a 3-day move ≥ 0.5 ft | ≤ 0.08 | **0.0752** (16,161 of 214,788) | **PASS** (narrow) |
| **H-B info** (no pass/fail): v1 `VERY_UNUSUAL` reported `UNUSUAL` under v2 | information | PROVISIONAL **17.5 %** of 82,425 lake-days (81 lakes); STANDARD **8.7 %** of 53,481 lake-days (43 lakes) | n/a |

Two of the passes are narrow: H-A by one lake, H-D (ii) by 0.5 percentage points. They are passes as pre-registered and are reported as such, not as comfortable margins.

## 2. The test set

| Step | Lakes |
|---|---|
| Strict bindings (waves w1 + w2-v1, VERIFIED / VERIFIED_CORROBORATED) | 279 |
| minus v1.1-tagged (Clinton Lake\|IL) | −1 |
| minus providers with an undocumented endpoint (nipsco, njwsa, duke, wps-hydro, alliant, srp, cnppid, nppd, utahlake, aep, eccc, mncsg) | −5 |
| minus a directory coordinate with `point_flag` ≠ `ok` (52 off_water, 6 identity_risk; none blank) | −58 |
| **Test set** | **215** |
| minus no history file located (Columbus MS; Douglas, Fort Loudoun, Norris, Watts Bar TN; South Holston VA; Ross WA; Winnebago WI) | −8 |
| **Lakes with a daily series** | **207** |

Lake-years (last 5 complete years of each lake): FULL 462, STANDARD 147, PROVISIONAL 226, NONE 185 (not scored: under 5 training years). H-A tested the 112 lakes that have ≥ 10 training years in all 5 test years (≥ 15 complete years); H-C and H-D used the 193 lakes with ≥ 1 lake-year at ≥ 5 training years; H-B used 102 lakes.

Complete years of the 207 lakes: 6 under 5, 71 with 5–9, 18 with 10–14, 112 with ≥ 15 (`completeYearsDistribution` in the JSON). The 112 meet the "≥ 100 lakes" level in the PARTIAL definition proposal, but that definition also needs binding acceptance, withholding and 90 days of ledger evidence, none of which this run supplies.

## 3. Decisions made before the run (ambiguities in the pre-registration, resolved once and not revisited)

1. **Data location.** The kickoff named `~/Desktop/Sector_Research_Data/lake-brain`; the data is at `~/Desktop/Development/Sector_Research_Data/lake-brain`. Series per lake: the history file named by the research (`binding2/verified_v2_full.csv` `histSeries`), the wave-1 `history_results.json` best series, and the plan-thread composite; the one with the most complete years wins. The 4 TVA pilots use `history/tva_pilots/*_daily.csv`. Values ≤ 1.0 are RISE placeholders and are dropped (as in the v1 harness). Series are rounded to 0.01 ft, the archive precision.
2. **"Strict binding" filter.** v1.1 is detected by the tag in `checks_passed`, not only the lake name (it removes exactly Clinton Lake). "Flagged" is `point_flag != ok` as instructed.
3. **H-A tested lakes.** "≥ 4 of its 5 test years" is read literally: a lake is tested only when all 5 test years have ≥ 10 training years. Pooled coverage is taken over those lakes' test-year days. (All 609 eligible STANDARD+FULL lake-years pooled: 0.804.)
4. **Baseline built exactly like Swift.** Level samples from the basis years only; rate samples from the last 30 years including partial years and across the year boundary; Feb 29 shares Feb 28's index; the grid is rounded to 0.001 ft. The 60-year natural basis applies to levels only.
5. **H-C days.** Only days whose day-of-year has a rate baseline (≥ 20 samples) count; a lake's rate pools its test years with ≥ 5 training years.
6. **H-D labels** use daily data: 24 h = level(t) − level(t−1 d); 72 h = level(t) − level(t−3 d) when that day exists, else the flagged 24 h fallback (515 of 303,707 days). Pairs are consecutive days both inside the test year.
7. **H-D (ii) "inside a 3-day move".** A STABLE day counts when it lies in some window [s, s+3 d] with |level(s+3 d) − level(s)| ≥ 0.5 ft. A trailing-only window would be vacuous (a 72 h move ≥ 0.5 ft can never be labelled STABLE), so a window that contains the day was used.
8. **Units.** All series are treated as feet; the 0.10 / 0.05 / 0.25 ft thresholds are applied as written.
9. **Nominal values are not used as thresholds.** Only the numbers in the pre-registration decide.

## 4. By provider and lake class

Lake class = the directory `poolBasis` (regulated `fullPool` vs `naturalSurface`) and the research `lake_class`. Small groups (n < 5) are noise.

**H-A (lake pass rate / pooled coverage)**

| Group | Lakes | Pass rate | Coverage |
|---|---|---|---|
| a2w | 31 | 77 % | 0.796 |
| cwms | 18 | 94 % | 0.812 |
| nwps | 12 | 67 % | 0.769 |
| rise | 25 | 80 % | 0.799 |
| tva | 4 | 100 % | 0.831 |
| usgs | 18 | 83 % | 0.822 |
| fullPool (regulated) | 111 | 80 % | 0.802 |
| naturalSurface | 1 | n/a | 0.737 |
| R1 run-of-river | 10 | 80 % | 0.816 |
| R2 flow-through | 25 | 80 % | 0.854 |
| R3 dendritic storage | 29 | 86 % | 0.829 |
| R4 open-basin storage | 39 | 77 % | 0.754 |
| N2 regulated natural | 8 | 75 % | 0.746 |

Failing lake-years miss in both directions: 40 below and 47 above their own reference range.

**H-B (share outside p02–p98, FULL)**

| Group | Lakes | Share |
|---|---|---|
| a2w | 29 | 6.1 % |
| cwms | 18 | 4.7 % |
| nwps | 6 | 9.3 % |
| rise | 25 | 5.3 % |
| tva | 4 | 3.1 % |
| usgs | 17 | 4.0 % |
| R1 / R2 / R3 | 8 / 23 / 27 | 3.0 / 2.9 / 3.2 % |
| R4 open-basin storage | 36 | 8.0 % |
| N2 regulated natural | 7 | 7.9 % |

**H-C (pooled RAPID rate / share of lakes within [0.02, 0.09])**

| Group | Lakes | Pooled rate | Lakes in range |
|---|---|---|---|
| a2w | 75 | 3.6 % | 71 % |
| cwms | 40 | 3.6 % | 68 % |
| nwps | 22 | 4.0 % | 73 % |
| rise | 25 | 2.0 % | 36 % |
| tva | 6 | 4.5 % | 83 % |
| usgs | 21 | 4.5 % | 86 % |
| R1 run-of-river | 18 | 4.7 % | 89 % |
| R3 dendritic storage | 54 | 4.4 % | 85 % |
| R2 flow-through | 41 | 3.5 % | 73 % |
| R4 open-basin storage | 63 | 3.1 % | 56 % |
| N2 regulated natural | 13 | 1.0 % | 0 % |

Of the 193 lakes, 59 are below 2 % and 5 are above 9 %.

**H-D (label-change rate / STABLE-in-move rate)**

| Group | Lakes | Label change | STABLE in move |
|---|---|---|---|
| a2w | 75 | 12.6 % | 7.4 % |
| cwms | 40 | 13.0 % | 7.6 % |
| nwps | 22 | 14.0 % | 7.8 % |
| rise | 25 | 8.2 % | 4.1 % |
| tva | 6 | 38.3 % | 31.8 % |
| usgs | 21 | 16.1 % | 8.0 % |
| R1 run-of-river | 18 | 28.9 % | 18.3 % |
| R2 flow-through | 41 | 14.8 % | 9.3 % |
| R3 dendritic storage | 54 | 14.8 % | 9.3 % |
| R4 open-basin storage | 63 | 8.8 % | 4.5 % |
| N2 regulated natural | 13 | 4.4 % | 1.2 % |

## 5. Interpretation

- **Band calibration (H-A, H-B) holds on average, for regulated reservoirs with ≥ 15 years of history.** Pooled coverage is 0.80 and the FULL tail share is 5.3 % against a nominal 4 %. The tail is fatter than nominal, and it is concentrated where the world is not exchangeable year to year: open-basin storage lakes (R4: 8.0 % tail, coverage 0.754, 77 % lake pass rate) and regulated natural lakes (N2: 7.9 %). Those are the lakes with multi-year drought and refill cycles. The H-A pass margin is one lake, so a slightly different test set could flip it.
- **The tier gate is doing real work.** With only 5–9 years, 17.5 % of lake-days fall outside p02–p98, 4 times nominal. v1 would have published those as `VERY_UNUSUAL`. v2 publishes `UNUSUAL` with a provisional flag. At 10–14 years the figure is 8.7 %, still twice nominal, which is why `VERY_UNUSUAL` waits for ≥ 15 years. This is evidence for the gate, not for the 15-year number being tuned.
- **RAPID (H-C) failed on the lake-share part.** The pooled rate (3.5 %) is inside the band, but only 66.8 % of lakes have a RAPID rate in [2 %, 9 %]. The shortfall is almost entirely on the low side: 59 lakes are below 2 %. Where the seasonal p95 is under 0.25 ft, the floor lifts the threshold above what 5 % of days would produce, so quiet lakes rarely or never show RAPID (regulated natural lakes: 0 of 13 in range; USBR RISE lakes: 36 % in range). The floor is the approved design choice; the criterion measures its cost. It was not re-tuned. What the data says is that a fixed 0.25 ft floor and a per-lake 2–9 % rate target cannot both hold on a fleet that includes lakes that barely move.
- **Trend stability (H-D) passes on average and fails in a pocket.** Overall, labels change on 13 % of days and 7.5 % of STABLE days sit inside a ≥ 0.5 ft 3-day move. Run-of-river pools (R1: 18 % of STABLE days inside a move, 29 % label changes) and the TVA mainstem lakes (32 % and 38 %) are well outside the pooled bounds: their levels are managed daily, so a 72 h mean rate against a 0.10 ft/day floor is a poor summary. For TVA, part of the test years come from NWS RVDHUN daily reports recorded to 0.1 ft, the same size as the floor; that may add quantisation flips, but this was not isolated. Nothing here changes the pooled verdict.
- **Natural lakes are not tested.** Only 1 natural-surface lake is in H-A and 2 in H-C and H-D. The natural 0.05 ft floor and the 60-year basis have almost no evidence from this run.

## 6. Data caveats

- **Series/binding mismatch.** For 14 lakes, the median of the history series since 2025 differs by more than 15 ft from the live binding's 30-day median (e.g. Lake Taneycomo is carried by a Table Rock Dam headwater series; Shelbyville and Rend Lake carry tailwater-named CWMS series). This points at the research history mapping, not at the rules, and should be checked there. Nine more lakes have no data since 2025. Per the pre-registration none was dropped. As a labelled sensitivity (information only), removing the 14 gives the same four verdicts: H-A 80.8 % / 0.809, H-B 0.0487, H-C 0.659 (FAIL), H-D 0.136 / 0.076.
- The 8 lakes with no history file located (mostly TVA lakes other than the 4 pilots) have under 5 years anyway.
- Daily values are rounded to 0.01 ft. Production baselines are built from the same 2-decimal archive.

## 7. What this does and does not establish

- It shows the v2 band rules are calibrated on average for regulated reservoirs with long history, using only data that never entered the baselines. It does **not** show the rules are right for any one lake, for natural lakes, or for lakes with under 15 years.
- It is retrospective. Prospective evidence (the prediction ledger) has not started.
- Under the proposed PARTIAL definition (`LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`, not adopted), "all of H-A..H-D pass" is one of four conditions; H-C failed, so that condition is not met, and the definition's own rule would withhold RAPID until a revised, separately pre-registered H-C passes. Lifecycle, readiness vocabulary, the score rubric and `/validation/lake-brain` are unchanged.
