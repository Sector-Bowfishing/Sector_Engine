# Lake Brain: validation readiness (every family, with evidence)

**Status of the Lake Brain validation node is unchanged: `/validation/lake-brain` reads `NOT_VALIDATED` (read live 2026-10-13, `modelVersion lake-level-rules-v2`, `holdoutType none`, `sampleCount 0`).** Nothing in this document claims `PARTIAL` or `VALIDATED`, changes lifecycle, or changes the score rubric. It is a ledger of what each validation family has, what it lacks, and the earliest honest date for more evidence.

Written 2026-10-13. Every number below was recounted from a committed file or re-run in this session; the provenance of each is in section 1. The pre-registration (`LAKE_BRAIN_RULES_V2_PREREGISTRATION.md`, committed `4a59715b` before any v2 code) is the only thing that decides pass or fail for H-A to H-D. No threshold was changed, and no rule was tuned on a failed criterion.

## 0. Status vocabulary used here

| Word | Meaning |
|---|---|
| **PASS** | A criterion fixed before the evidence existed was met by the measured number. |
| **FAIL** | The same, but missed. A failed criterion stays failed in this document. |
| **WITHHELD** | The evidence exists or was gathered, but the lakes or the classification are deliberately kept out (held back or not published) until a stated condition is cleared. |
| **WAITING** | A human action or an external answer is the only thing missing. |
| **PROSPECTIVE** | Only future data, collected under rules that are already fixed, can settle it. Calendar time cannot be bought. |

A single family can carry two words (for example, H-A is PASS retrospectively and PROSPECTIVE for its replication).

## 1. What was run in this session (reproduction record)

| Check | Command (worktree `Sector_Engine-fleet-docs`, base `f67b949b`) | Result |
|---|---|---|
| Validation tests | `python -m pytest jobs/lake-brain/validation -q` | 70 passed |
| Ledger tests | `python -m pytest jobs/lake-brain/ledger -q` | 23 passed |
| Review tests | `python -m pytest jobs/lake-brain/review -q` | 24 passed |
| Brain-score tests | `python -m pytest jobs/brain-scores -q` | 8 passed |
| **Hold-out re-run** | the committed `jobs/lake-brain/validation/holdout_v2.py --run 1`, run from a **scratch copy** (the harness refuses to overwrite a committed result; the committed files were not touched), same research data directory | **Reproduced.** 207 lakes with a series, lake-years FULL 462 / STANDARD 147 / PROVISIONAL 226 / NONE 185; H-A PASS, H-B PASS, H-C FAIL, H-D PASS. Every key under `selection`, `lakesWithSeries`, `lakeYearsByTier`, `completeYearsDistribution`, `criteria`, `results`, `sensitivityExcludingSeriesMismatch`, `seriesQa` and `lakes` is equal to the committed JSON, and `holdout_v2_results_lakes.csv` is **byte-identical** (sha256 `9950ca6412392296e5bffc76d20e0acb1aff11f94414c1f1a1e0bee8dc883e6d`). Run time 20 s with numpy 2.5.4. |
| Cross-source agreement | the research `assemble_summary.py` pairing rule re-applied to `Sector_Research_Data/lake-brain/binding/candidates.csv` | **Reproduced** 123 independent pairs, 69 lakes, median gap 0.015 ft, 121 within 0.5 ft, 122 within 2 ft, 1 disagreement (Kerr Reservoir (Buggs Island)\|VA, 29.34 ft, `a2w` against `usgs`). |
| Accepted-fleet sensitivity (NEW, information only) | the same harness functions (`load_records`, `run_lake`, `aggregate`) run on the 188 hold-out lakes that are in the 196-lake accepted-eligible table | see section 5. Not a pre-registered test, no verdict is taken from it. |
| Live reads (read-only) | `GET sector-brain.firebaseio.com/validation/lake-brain`, `/brains/lake-brain`, `/scores/lake-brain`; `gcloud storage ls -r gs://sector-lake-brain/predictions/` | validation `NOT_VALIDATED`; registry `CALIBRATION`, health `HEALTHY`, 5 supported lakes; score 3.0 (uncapped 6.3); **one** ledger object (`2026/10/13/185314Z-740761e4e50a.jsonl`). |

The hold-out reproduces exactly, so the numbers in `holdout_v2_results.json` are used below unchanged. Source files: `jobs/lake-brain/validation/results/holdout_v2_results.json`, `holdout_v2_results_lakes.csv`; narrative `docs/brains/LAKE_BRAIN_RULES_V2_RESULTS.md`.

## 2. One-page scoreboard

| # | Family | Pre-registered / stated threshold | Measured | Status | Next evidence (earliest) |
|---|---|---|---|---|---|
| V1 | Binding acceptance (identity of the level source) | stratified n = 60, at most 1 error (95 % upper bound at most 7.7 %), every row decided; the 57 flagged rows reviewed in full | 0 of 60 reviewed; pack built on the 196 (`LBR-SAMPLE-3d4f12ca7d`, seed 20261013); computer recommendation on the sample 44 PASS / 16 FLAG; no `binding_review_result.json`, no `accepted_batch.json` | **WAITING** (human review) | Michael's one-hour review; any day. |
| V2 | **H-A** band calibration, p10 to p90 | at least 80 % of tested lakes pass **and** pooled coverage in [0.75, 0.85] | 90 of 112 = **80.4 %**; coverage **0.801** | **PASS** (retrospective, by one lake) + **PROSPECTIVE** replication | 2027-01-11 (90 d, pilots only); 2027-10-13 (12 months) |
| V3 | **H-B** tail, p02 to p98, tier FULL | pooled share outside at most 0.06 | **0.0529** (462 lake-years, 102 lakes) | **PASS** + **PROSPECTIVE** | same |
| V4 | **H-C** rapid-change rate | pooled in [0.03, 0.08] **and** at least 70 % of lakes in [0.02, 0.09] | pooled **0.0349** (pass); lakes **66.8 %** = 129 of 193, 136 needed (**fail**) | **FAIL** (preserved verbatim, section 3.3) | A new, separately pre-registered H-C scored on ledger data dated after its commit; see section 3.3. Not before 2027-01-11 even for pooled evidence. |
| V5 | **H-D** trend-label stability | (i) label-change share at most 0.30; (ii) STABLE-inside-3-day-move share at most 0.08 | (i) **0.132**; (ii) **0.0752** | **PASS** (ii by 0.5 percentage points) | same as V2 |
| V6 | Withholding of every failing family (PARTIAL item 3) | each failing family withheld (`INSUFFICIENT_HISTORY` / `UNKNOWN`) | history-tier gate for `VERY_UNUSUAL` is implemented and live; **RAPID is still published** (`RISING_RAPIDLY` / `FALLING_RAPIDLY` can appear) | **NOT MET** | A Swift change and a new `rulesVersion`; needs Michael's decision (section 3.6). |
| V7 | Prospective ledger, at least 90 days | ledger running at least 90 days | started 2026-10-13 18:53:14Z; 1 object, 5 records, 5 pilots; day 0 | **PROSPECTIVE** | **2027-01-11** |
| V8 | First monthly scorer output | `predictions_scores/{YYYY-MM}.json` exists | not yet produced | **WAITING** (calendar) | **2026-11-01** (October, 1 d horizons only; 7 d from 2026-10-20 plus 3 d grace; 30 d from 2026-11-12) |
| V9 | `VALIDATED` prospective result | at least 12 months logged and scored once under a pre-registered rule | day 0 | **PROSPECTIVE** | **2027-10-13** at the earliest, and only if a fleet (not 5 pilots) is logged for 12 months |
| V10 | Cross-source agreement of independent origins | R9 of `binding-review-v1`: within 2 ft | 123 pairs / 69 lakes: median 0.015 ft, 121 within 0.5 ft, **122 within 2 ft**, 1 disagreement. On the 196 table: 77 pairs / 44 lakes, 76 within 2 ft, the same single disagreement | **PASS** (research, rule fixed before counting; not a hold-out) | Grows as fleet fallbacks are logged; no date. |
| V11 | Source freshness | R6: last observation under 72 h (daily feeds under 192 h) | at the 2026-10-13 probe: **194 of 195** within 72 h, median 1.4 h, max 97.5 h (RISE daily, inside its 192 h rule); live pilots `stale: false`, `sourceAgeHours` 0.13 to 1.89 | **PASS at one instant**; continuous freshness **PROSPECTIVE** | Needs a fleet run history; pilot staleness is in `/health` today. |
| V12 | History completeness / reconciliation | recount rule: complete year at least 329 days; composite agrees with the provider | TVA pilots 17 / 18 / 18 / 16 complete years (live profiles: `yearsCovered` 17 for Guntersville); research reconciliation MAE 0.001 to 0.003 ft over 647 days | **PASS** (pilots); **WAITING** for the other 191 (fleet backfill not run) | When the history job runs for the accepted fleet. |
| V13 | Operating-zone / flood-pool semantics | the operator's own levels, correctly read | operator-level checks 0 of 15 contradicted; 10 of 11 within 1 ft and 11 of 11 within 3 ft against an unrelated regulator (TWDB / NWPS); Grand Lake rule curve equal month by month | **PASS** as research evidence; level *meaning* review is **WAITING** (human) | With the binding review (section 3.9). |
| V14 | Series / datum agreement (hold-out data QA) | history series median within 15 ft of the live binding | **14 lakes fail** (e.g. Taneycomo, Shelbyville, Rend), 9 more have no data since 2025 | **WITHHELD** (the 14 are held out of the 196) | When the research history mapping is corrected; no date. |
| V15 | Geometry / coordinate flags | directory point on water | 52 `off_water`, 6 `identity_risk` | **WITHHELD** (58 lakes held out) | Coordinate review. |
| V16 | Provider terms | documented terms | SJRWMD (3 lakes) and NH DES (1 lake) unconfirmed | **WAITING** (4 lakes held out) | Terms confirmation. |
| V17 | Transfer to natural lakes and other classes | at least some tested lakes per class | natural-surface lakes in the hold-out: 1 in H-A, 2 in H-C and H-D | **NOT DEMONSTRATED** (evidence gap, not a failure) | The representative fleet in `LAKE_BRAIN_REPRESENTATIVE_VALIDATION_FLEET.md`. |

Not in scope for validation (and not counted): species presence (private research; `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md` "What does not count"), lake geometry beyond the point flag, the Conditions Score `WaterLevelFactor`.

## 3. The families in detail

### 3.1 V1 Binding acceptance (WAITING)

- Rule (`LAKE_BRAIN_BINDING_REVIEW_PROTOCOL.md` section 4, from the validation strategy): stratified random sample of 60 strict machine-verified rows, accept the batch at most 1 error (exact one-sided 95 % upper bound: 0 errors 4.9 %, 1 error 7.7 %, 2 errors 10.1 %), every row decided; a stratum with any reject goes to full review; the flagged tier is reviewed in full, not sampled.
- Population: 272 strict rows minus 58 coordinate holds, 14 series holds, 4 provider-terms holds = **196 eligible** (`pack_manifest.json` counts: `v2StrictBeforeExclusions 279`, `excluded 7`, `heldBackCoordinateFlags 58`, `heldBackSeriesMismatch 14`, `heldBackProviderTerms 4`, `eligible 196`). That equals the lake set of `jobs/lake-brain/data/bindings.proposed.v1.json` (196 rows, all `MACHINE_VERIFIED`).
- State: the pack exists at `~/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review/` (HTML sample of 60, HTML for the 57 flagged rows, CSVs, manifest). `jobs/lake-brain/data/` holds no `binding_review_result.json` and no `accepted_batch.json`. Review count is zero, so **no binding is REVIEWED beyond the five hand-written pilots** (live `breakdowns.bindingStatus: {REVIEWED: 5}`).
- Caveat that matters: the computer pre-screen gave the sample 44 PASS / 16 FLAG. A flag is not an error; but 16 of 60 flagged rows need real attention from the reviewer, and a reject in a stratum removes that whole stratum from the batch.
- **Next evidence:** Michael completes the HTML and returns the CSV; `ingest_review_result.py` is the only thing that may write the result. Earliest: any day.

### 3.2 V2 and V3, H-A and H-B (PASS, narrow)

Pre-registered text (`LAKE_BRAIN_RULES_V2_PREREGISTRATION.md` section 2): **H-A** tiers STANDARD and FULL (training at least 10 years). A lake-year passes if its p10 to p90 coverage lies within the 5th to 95th percentile of the lake's own leave-one-year-out coverage; a lake passes at 4 of 5 test years. Criterion: at least 80 % of tested lakes pass and pooled coverage in [0.75, 0.85]. **H-B**: tier FULL, pooled share of days outside p02 to p98 at most 0.06 (nominal 0.04).

| Quantity | Result | Verdict |
|---|---|---|
| H-A lakes tested / passed | 112 / 90 = **0.8036** (89 would be 0.795 and fail) | PASS by one lake |
| H-A pooled p10 to p90 coverage | **0.8010** over 560 lake-years | PASS |
| H-A lake-year pass rate (info) | 0.8446 | n/a |
| H-B pooled share outside p02 to p98 | **0.05287** (462 lake-years, 102 lakes, 168,219 days) | PASS |

Where it is weakest (from `LAKE_BRAIN_RULES_V2_RESULTS.md` section 4, unchanged): open-basin storage lakes R4 (pass rate 77 %, coverage 0.754, tail 8.0 %), regulated natural lakes N2 (75 %, 0.746, tail 7.9 %), NWPS-bound lakes (67 %, 0.769). Failing lake-years miss on both sides (40 below, 47 above). The tier gate does real work: 17.5 % of PROVISIONAL (5 to 9 years) lake-days and 8.7 % of STANDARD (10 to 14 years) lake-days fall outside p02 to p98 under the v1 rule, which is why `VERY_UNUSUAL` waits for at least 15 years.

**Prospective replication.** The ledger stores the exact bands used for 1, 7 and 30 day horizons (`horizons[].band`, `bandN`), so realised coverage and tail rate come out of `score_predictions.py` without re-deriving anything. Pilots only so far (5 lakes, all FULL tier): too few for a lake-share criterion. Pooled coverage and tail rate for the pilots can be read from **2027-01-11**. A criterion over lakes needs the accepted fleet in the ledger; the date is fleet start plus 90 days for pooled values and plus 12 months for a per-lake judgement (sampling error of a per-lake rate at 90 days is about 1.9 percentage points at p = 0.035, section 3.3).

### 3.3 V4 H-C rapid-change rate (FAIL, preserved verbatim)

Pre-registered text: *"H-C rapid-change rate (all lakes with a rate baseline, training at least 5 y): pooled share of days with `rate24 > max(p95, 0.25 ft)` in [0.03, 0.08] and at least 70 % of lakes within [0.02, 0.09]."*

Result as recorded in `LAKE_BRAIN_RULES_V2_RESULTS.md` (copied, not paraphrased):

> | **H-C** pooled RAPID rate | in [0.03, 0.08] | **0.0349** (10,606 of 303,707 days, 193 lakes) | pass (part) |
> | **H-C** lakes with a RAPID rate in [0.02, 0.09] | at least 70 % of lakes | **66.8 %** (129 of 193; 136 needed) | **FAIL** |
> | **H-C** overall | both parts | | **FAIL** |
>
> **RAPID (H-C) failed on the lake-share part.** The pooled rate (3.5 %) is inside the band, but only 66.8 % of lakes have a RAPID rate in [2 %, 9 %]. The shortfall is almost entirely on the low side: 59 lakes are below 2 %. Where the seasonal p95 is under 0.25 ft, the floor lifts the threshold above what 5 % of days would produce, so quiet lakes rarely or never show RAPID (regulated natural lakes: 0 of 13 in range; USBR RISE lakes: 36 % in range). The floor is the approved design choice; the criterion measures its cost. It was not re-tuned.

Re-run in this session: identical (129 of 193 = 0.66839; 59 lakes below 0.02, 5 above 0.09; lake-rate quantiles p5/p25/p50/p75/p95 = 0.0010 / 0.0174 / 0.0338 / 0.0488 / 0.0732). Seven more lakes in range would have passed it; no one is allowed to buy those seven now.

By group (hold-out, lakes in range): R1 89 %, R3 85 %, USGS 86 %, TVA 83 % (6 lakes), R2 73 %, NWPS 73 %, A2W 71 %, CWMS 68 %, R4 56 %, RISE 36 %, N2 0 of 13. The failure is the quiet lakes (RISE, N2, R4), not the dynamic ones.

**What prospective evidence could legitimately address it, and when.**

1. **What cannot fix it.** Re-scoring the same hold-out with another threshold, a per-class rate band chosen after seeing the table above, dropping the 59 low lakes, or a floor chosen to put 70 % inside the band. Each of those uses the failed result to design the test. The hold-out is spent for H-C.
2. **Unchanged-rule replication (legitimate, informative, but unlikely to pass).** The ledger records, for every claim, the effective RAPID threshold actually applied (`rapidThresholdFt`, `rateP95`) and the observed 24 h and 72 h change. A prospective scorer can therefore compute each lake's realised RAPID rate under the *shipped* v2 rule (including the `nws:rvd` rate-climatology filter on the four TVA pilots, which the hold-out lacked). That tests whether 66.8 % reproduces out of sample. Because the cause is structural (the 0.25 ft floor on quiet lakes), expect the same shape, not a pass. Its value is a clean second measurement, not a rescue.
3. **A revised H-C (the only route to a pass).** The PARTIAL definition itself says the RAPID family stays withheld "until a revised, separately pre-registered H-C passes" (`LAKE_BRAIN_RULES_V2_RESULTS.md` section 7). Legitimate shape: (a) Michael decides in writing what RAPID is for and which rule or publication scope follows (for example, publish RAPID only where the baseline makes it meaningful, withhold elsewhere); (b) the new criterion, the lakes in scope and the scoring date are committed **before** any ledger month that will be used is read; (c) the rule change gets a new `rulesVersion` (the ledger reports by version and never pools silently); (d) it is scored once, on ledger records whose `generatedAt` is after the commit. The choice of design must not use per-lake or per-class H-C outcomes from the spent hold-out.
4. **Sample size, so nobody over-reads early numbers.** For a lake whose true RAPID rate is 3.5 %, the standard error of its realised rate is 1.9 points at 90 days (n = 90), 1.4 at 180 days, 1.0 at 365 days. A per-lake "in [2 %, 9 %]" decision is therefore near-random at 90 days and usable only after about 12 months. A pooled or per-class rate is usable earlier (17,640 lake-days for 196 lakes at 90 days), but lines are correlated across days and across lakes on one river, so it has no sampling-error interpretation (`LAKE_BRAIN_PREDICTION_LEDGER.md`).
5. **Dates.** Pilots only (5 lakes, FULL tier, no quiet natural lake): pooled rates from **2027-01-11**; per-lake rates from **2027-10-13**. Neither can speak for the 59 quiet lakes, which are not in the ledger. For quiet-lake evidence the accepted fleet must be logged: earliest = fleet start + 90 days (pooled) or + 12 months (per lake). The representative fleet (`LAKE_BRAIN_REPRESENTATIVE_VALIDATION_FLEET.md`) deliberately includes quiet lakes (Keyhole, Bluestone) so that evidence starts early.

### 3.4 V5 H-D trend-label stability (PASS, narrow)

| Part | Threshold | Result |
|---|---|---|
| (i) pooled label-change share of consecutive-day pairs | at most 0.30 | **0.1325** (40,072 of 302,494) |
| (ii) pooled share of STABLE days inside a 3-day move of at least 0.5 ft | at most 0.08 | **0.0752** (16,161 of 214,788) |

Pockets outside the pooled bounds, kept visible: run-of-river R1 (28.9 % label changes, 18.3 % STABLE-in-move), TVA mainstem (38.3 %, 31.8 %; 6 lakes). The TVA hold-out series used NWS RVD daily values at 0.1 ft resolution, the size of the floor; the post-run note in the results document records the `nws:rvd` rate-climatology filter now shipped and states that no verdict was re-run. Margin of (ii) is 0.0048; see section 5 for the accepted-fleet subset, where it is 0.0015.

### 3.5 V6 ... V9 PARTIAL process items

See the checklist in section 4. V7 to V9 are calendar items: ledger day 0 is 2026-10-13 (first object `gs://sector-lake-brain/predictions/2026/10/13/185314Z-740761e4e50a.jsonl`, 6,620 bytes, 5 records, job execution `lake-brain-qz28h`, `rulesVersion lake-level-rules-v2`, `bindingVersion bindings-2026-10-13.1`). Dates: +1 d 2026-10-14; +7 d 2026-10-20; +30 d 2026-11-12; +90 d **2027-01-11**; +180 d 2027-04-11; +365 d **2027-10-13**. Scoring never touches a prediction whose target date has not arrived, and a 3-day grace applies before a missing value is counted missing.

### 3.6 V6 Withholding (NOT MET)

PARTIAL item 3 requires every classification family that fails its criterion to be withheld. Today: `VERY_UNUSUAL` is gated by history tier (this is the one withholding the hold-out supports). RAPID (`trendState` `RISING_RAPIDLY` / `FALLING_RAPIDLY`, `rapidChangeThresholdFt`) is computed and published for all five pilots; live `rapidChangeThresholdFt` values 0.26 (Hartwell) and 0.32 (Guntersville). There is no withhold flag. Implementing one is a Swift change plus a `rulesVersion` bump, and which scope to withhold is a product decision. Listed as a decision for Michael, not done here.

A drafting point to resolve before the definition is adopted: item 2 says H-A to H-D must **all** pass, and item 3 says failing families are withheld. Read together, withholding cannot cure a failed item 2. If Michael wanted "PARTIAL with RAPID withheld", that is an amendment of the definition made after the H-C result, and must be labelled as such; this document does not recommend it. The clean route is a revised H-C (section 3.3, point 3).

### 3.7 V10 Cross-source agreement (PASS, research)

`binding-review-v1` R9: independent verified series of one lake must agree within 2 ft (relays and same-origin series are not independent: A2W and CWMS are both USACE). Recomputed from `candidates.csv`:

| Scope | Independent pairs | Lakes | Median gap | Within 0.5 ft | Within 2 ft | Disagree |
|---|---|---|---|---|---|---|
| All research candidates | 123 | 69 | 0.015 ft | 121 | 122 | 1 (Kerr VA, 29.34 ft, `a2w` vs `usgs`) |
| Lakes in the 196 table | 77 | 44 | 0.010 ft | 75 | 76 | same 1 |

The Kerr VA disagreement is a rejected A2W candidate; the generated binding carries only the USGS series (`live` has one entry). This is a measurement of source agreement; it is not a hold-out and has no pre-registered pass rate other than R9's 2 ft rule. Single-origin lakes (149 of the 196, no corroborating origin in the research table) rely on V1 for identity. The spot-check of 57 rows found 0 adjudicated wrong (95 % upper bound about 5 %, rule of three; adjudication by the research thread, not an external ground truth).

### 3.8 V11 Source freshness (PASS at one instant)

From `bindings.proposed.v1.json` `verification.probe.ageHours` (probe 2026-10-13): 195 lakes with an age; within 3 h 156, within 24 h 171, within 72 h **194**, within 192 h 195; median 1.4 h; by provider median hours a2w 2.1, rise 48.5 (daily feed with a documented lag), cwms 0.6, nwps 1.1, usgs 0.6, tva 0.4. The one lake over 72 h is Waconda Lake KS (RISE, 97.5 h). Live pilots on 2026-10-13: `freshness.stale false`; `sourceAgeHours` 0.13 to 1.89; refresh reason "scheduled: stable lake, 2 h". The registry's `staleLakeCount` is 0. Hartwell's CWMS feed was silent from 2026-10-08 (session closeout) and is currently back on CWMS with the USGS gauge as fallback, which the profile records in `sourceCapability.fallbacks`. A single probe is not a freshness record: continuous freshness needs fleet runs and is PROSPECTIVE.

### 3.9 V13 Operating-zone and flood-pool semantics (PASS as research; meaning review WAITING)

`levelState` compares a value with the operator's own published levels, so correctness is correct binding, correct datum, correct *meaning* of the level. Evidence: 15 operator-level spot checks, 0 failed; `plan_crosscheck.json` 11 pairs, 10 within 1 ft and 11 within 3 ft (the 3.0 ft is Kaw Lake, NWPS 1013 against CWMS 1010); Grand Lake o' the Cherokees CWMS seasonal Top of Conservation equals the GRDA rule curve month by month. Floods: `floodPoolState` is `UNKNOWN` wherever the operator publishes no flood-pool bottom (all four TVA pilots carry flag `noOperatorFloodPoolThreshold`), which is a valid answer. The meaning of each operator level name (for example, that CWMS "Top of Conservation" is the flood-pool bottom) is not yet reviewed lake by lake. It rides on the same human review as V1. Details in `LAKE_BRAIN_OPERATOR_PLAN_FLOOD_EVIDENCE.md`.

### 3.10 V14 to V16 Held-out populations (WITHHELD / WAITING)

The accepted-eligible set excludes: 58 lakes with a flagged directory coordinate (52 `off_water`, 6 `identity_risk`), 14 lakes where the history series differs from the live series by more than 15 ft (Bartlett AZ, Blue Mesa CO, Buffalo Bill WY, Canyon Lake TX, Detroit Lake OR, Glendo WY, Jackson Lake WY, Jordanelle UT, Lake Koocanusa MT, Lake Shelbyville IL, Lake Taneycomo MO, Navajo NM, Pineview UT, Rend Lake IL), and 4 lakes whose provider terms are unconfirmed (Apopka, Griffin, Harris FL via SJRWMD; Lake Winnipesaukee NH via NH DES). None of them is validated or published. The hold-out kept the 14 series-mismatch lakes (pre-registration forbids dropping them); the labelled sensitivity without them leaves the four verdicts unchanged (H-A 0.808 / 0.809, H-B 0.0487, H-C 0.659 FAIL, H-D 0.136 / 0.076).

### 3.11 V17 Natural lakes and class transfer (evidence gap)

The hold-out is a reservoir test. Natural-surface lakes: 1 in H-A, 2 in H-C and H-D. The natural 0.05 ft floor and the all-years (cap 60) basis have almost no hold-out evidence. Among the 196 accepted-eligible lakes with at least 10 complete years there is **no natural lake at all** (109 lakes: R1 8, R2 28, R3 29, R4 37, N2 regulated natural 7). The one machine-verified strict natural deep lake with at least 10 years, Apopka FL (17 years), is held for provider terms. This gap is the reason for the representative fleet document.

## 4. PARTIAL checklist (`LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`, proposal, not adopted)

| # | Requirement | Met? | Evidence |
|---|---|---|---|
| 1 | Binding acceptance by sampling (stratified n at least 60, at most 1 error; flagged tier reviewed in full; recorded in a committed review result file) | **NOT MET** | No review done; no result file (V1). |
| 2 | Pre-registered H-A to H-D **all** pass, on at least 100 lakes, committed before the run | **NOT MET** | H-A, H-B, H-D pass; **H-C FAIL**. The 112-lake H-A and 193-lake H-C/H-D samples are above 100; but see section 5: restricted to the accepted 196, H-A tests 96 lakes, below 100. |
| 3 | Every failing family withheld | **NOT MET** | RAPID is still published (V6). The `VERY_UNUSUAL` history gate is in place. |
| 4 | Ledger running at least 90 days and a first monthly scorer output | **NOT MET** (calendar) | Day 0 = 2026-10-13; 90 days = **2027-01-11**; first scorer output 2026-11-01 (it would show the process works; not evidence of accuracy). |
| Additionally for `VALIDATED` | at least 12 months of logged predictions scored once with pre-registered criteria | **NOT MET** | 2027-10-13 at the earliest, requiring a fleet in the ledger. |

Earliest possible PARTIAL under the proposal as written: the later of (binding review done and accepted), (revised H-C pre-registered, withheld RAPID shipped, and its prospective test passed), and 2027-01-11. The hard lower bound is **2027-01-11**; a realistic date is later because a revised H-C needs fleet evidence (section 3.3). Nothing in this document, the ledger, or the score projections is a PARTIAL claim.

## 5. Sensitivity on the accepted 196 (information only, not pre-registered, no verdict)

Same harness functions, restricted to the 188 of the 196 lakes that have a hold-out series (8 have none: they are the accepted lakes with no history file located):

| Criterion | Value on the 196 subset | Threshold | Read |
|---|---|---|---|
| H-A lakes tested / passed | 96 / 78 = 0.8125; coverage 0.8109 | at least 80 %, [0.75, 0.85] | same side; but only **96** lakes tested, below the "at least 100 lakes" the proposed definition asks |
| H-B tail share | 0.0486 (87 lakes, 141,949 days) | at most 0.06 | same side |
| H-C pooled / lake share | 0.0356; 118 of 175 = **0.674** | [0.03, 0.08]; at least 0.70 | **same failure** |
| H-D (i) / (ii) | 0.1383 / **0.0785** | at most 0.30 / at most 0.08 | same side; (ii) margin is 0.0015 |

The accepted fleet does not change any conclusion; it makes the narrow passes narrower and the H-A sample size marginally short.

## 6. Calendar of next evidence

| Date | What becomes possible | Family |
|---|---|---|
| any day | Michael's binding review; ingestion; `accepted_batch.json` | V1, V13 |
| 2026-10-14 | first 1-day horizon targets arrive (scored after the 3-day grace) | V7 |
| 2026-11-01 | first monthly scorer run (October) | V8 |
| 2026-11-12 | first 30-day horizon targets arrive | V7 |
| 2027-01-11 | ledger day 90; PARTIAL item 4 clock satisfied (pilots) | V7 |
| 2027-04-11 | ledger day 180; per-lake RAPID standard error about 1.4 points | V4 |
| 2027-10-13 | ledger day 365; first date `VALIDATED` could even be considered, only with a fleet logged for all 12 months | V9 |

Fleet start date is not known; every fleet-dependent date is "fleet start + 90 d" or "+ 12 months".

## 7. What was not done, and why

- No `PARTIAL` or `VALIDATED` claim, no change to `/validation/lake-brain`, lifecycle, rubric or thresholds.
- No binding marked REVIEWED, no `accepted_batch.json`, no review result edited.
- No cloud mutation; RTDB and GCS were read only. The hold-out was re-run on a scratch copy; the committed results are byte-identical to the re-run.
- The accepted-fleet subset in section 5 is a labelled sensitivity, never a verdict, and was not used to choose anything.
