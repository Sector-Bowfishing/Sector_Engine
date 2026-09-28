# Clarity Fusion Stage 3B: hand-off

Prepared 2026-09-28 in `Sector_Engine-fusion`. Validation only: **production is unchanged**, and nothing was built or rendered. The Water Clarity map, `/conditions`, Huntability, Priority Zones, Fish Attraction and every visibility number are exactly as before.

## Recommendation: `DO NOT PROCEED`

On three untouched years (2021, 2023, 2024), **no arm class and no challenger passes the preregistered gate.**

- **Two of the Stage 3A signals replicate as hypotheses:**

  | Signal | Class | Murkier beyond noise, condition vs control | Positive in |
  |---|---|---|---|
  | Relative NWM flow (≥ 3× its own baseline) | large arms | 48% vs 15% | all three years |
  | Relative NWM flow | medium arms | 50% vs 11% | all three years |
  | Cold-season storms | large arms | 34% vs 13% | all three years |

- **Neither turns into a prediction that beats "keep the last satellite reading"** with enough independent storms behind it:
  - The best candidate, relative flow in medium arms, passes six of the eight criteria. It fails on sample: only 9 independent storms (15 required), one of which carries 34% of the observations. And its error improvement over persistence has an interval that crosses zero.
  - Cold-season storms make *some* large-arm zones murkier, but the typical storm-window zone is not: the median anomaly is +0.003 log10. So the season challenger is worse than persistence.
- **Head → mouth progression does not replicate:** 53% of events, p = 0.18, and the years disagree.
- **The heads of many arms stay unobservable.** Six heads were never measurable in three years; Town Creek's was measurable on 1.9% of passes.

---

## 1. Preregistration

- **What:** `CLARITY_STAGE_3B_PREREGISTRATION.md`, written and hashed at 2026-09-28T16:01:57Z **before any pre-2025 data was requested**. Hashes are in `CLARITY_STAGE_3B_PREREGISTRATION.sha256`; the document is `7f4eeb18…28de`.
- **Frozen:** the evaluation code (`stage3b_eval.py`, `89476718…52f4`), the discovery-only constants (`constants.json`, `50e9afbc…b735`), Stage 3A's zones, the production Sentinel pipeline and the input scripts.
- **Verified before the run:** the evaluation code and constants were byte-identical to their frozen hashes when `evaluate` ran (checked immediately before it).
- **Deviations and operational notes:**
  1. **2022 is not a validation year.** Earth Search's C1 collection has 6 usable 2022 passes, so §2.5 (≥ 40 read passes) reports it separately with 2020. It was applied through the preregistered `--years` / `--separate` arguments; the code is unchanged. The gate's "≥ 3 qualifying years" therefore needed all three remaining years. The older `sentinel-2-l2a` collection covers 2022, but it is a different processing baseline, and using it would change the frozen pipeline.
  2. **GDAL HTTP timeouts and retries** were set for the satellite reads, after the first readers hung on stalled S3 connections. This is operational only: no gate or rule changed.
  3. **No analysis deviation.** No rule, threshold, window, constant or line of evaluation code changed after the freeze.

## 2. Historical data completeness

| | 2020 (Nov–Dec, separate) | 2021 | 2022 (separate) | 2023 | 2024 |
|---|---|---|---|---|---|
| Sentinel-2 C1 candidates (a tile at or under 40% cloud) | 19 | 72 | **6** | 91 | 88 |
| Read (production gates) | 18 | 64 | 6 | 75 | 75 |
| Rejected by the production SWIR check (haze/glint) | 1 | 8 | 0 | 16 | 13 |
| Daily MRMS Pass 2 days present | 90.7% (from 2020-10-07) | 99.5% | 99.7% | 100% | 99.7% |
| Year counts toward the gate (§2.5) | no | **yes** | no | **yes** | **yes** |

- **Hourly MRMS for the day before each pass:** 6,325 hours read, 22 missing (those days stay daily).
- **NWM analysis at 16Z:** 1,547 days, with each file's version:

  | Version | From | To |
  |---|---|---|
  | v2.0 | start | 2021-04-19 |
  | v2.1 | 2021-04-20 | 2022-06-27 (plus a one-day v2.2 on 2022-06-01) |
  | v2.2 | 2022-06-28 | 2023-09-18 |
  | v3.0 | 2023-09-19 | end |

  A flow ratio is formed only within one version.
- **USGS 03572900 and 03572690:** complete for 2020-10 → 2025-01 (South Sauty has gaps in 2023).
- **Wind:** preserved, not used. IEM ASOS for Scottsboro (4A6), Gadsden (GAD) and Huntsville (HSV), 2020-10 → 2024-12, 203k observations, plus the 2025–2026 file from Stage 3A.

## 3. Independent events, 2021 / 2023 / 2024

- **Storm days:** 144 lake-wide (≥ 1.0 in on any drainage), forming **88 independent storms** (episodes, ≤ 3 days apart merged). By year: 28 / 28 / 32. By season: cold 39, warm 49.
- **Measurable storm-window observations** (lag 0–3 days, with a baseline and a previous observation):

  | Class | Observations | Cold season | Independent storms behind them |
  |---|---|---|---|
  | large | 174 | 174 | 13 |
  | medium | 94 | 91 | 13 |
  | small | 12 | 11 | 8 |
  | main stem | 5 | 5 | 5 |

- **So:** of 88 storms, a large arm was measurably read in the storm window after only 13. That is the first ceiling on everything below.
- **Warm season: untestable.** 225 warm storm-window observations exist, but only **4** have a dry baseline. In these wet summers a dry week rarely precedes a pass within 45 days, and warm passes are rejected by the SWIR check more often. The warm contrast is reported but carries no weight.

## 4. Cold vs warm season (H1)

Murkier-beyond-noise share, cold-season storm window vs cold-season dry weeks. 95% intervals by cluster bootstrap (condition by storm, control by pass date).

| Class | Condition (obs, storms) | Condition share | Control share | Difference (95%) | By year 2021 / 2023 / 2024 | H1 |
|---|---|---|---|---|---|---|
| **large** | 174 (13) | 0.345 | 0.130 | **+0.21 (0.02, 0.46)** | +0.63 / +0.16 / +0.21 | **pass** |
| medium | 91 (12) | 0.220 | 0.108 | +0.11 (−0.09, 0.34) | 2021 too few / +0.11 / −0.01 | fail |
| small | 11 (7) | 0.091 | 0.139 | −0.05 (−0.22, 0.22) | too few | fail |
| main stem | 5 (5) | 0.20 | 0.00 | +0.20 (0.0, 0.6) | too few | fail (sample) |
| warm contrast, any class | 0–3 | | | untestable (§3) | | |

**Stage 3A's post-hoc season finding holds for large arms as a shift in the share of murkier zones.** It does not show a typical-magnitude shift (§7), and it does not hold for medium or small arms.

## 5. Relative NWM flow (H2): `modeledNWM`, same reach and version only

Condition: model flow ≥ 3× its own median on the zone's dry-baseline pass days. Control: below 1.5×.

| Class | Condition (obs, storms) | Condition share | Control share | Difference (95%) | By year 2021 / 2023 / 2024 | H2 |
|---|---|---|---|---|---|---|
| **large** | 162 (12) | 0.481 | 0.153 | **+0.33 (0.18, 0.47)** | +0.47 / +0.24 / +0.36 | **pass** |
| **medium** | 68 (9) | 0.500 | 0.105 | **+0.39 (0.19, 0.53)** | +0.62 / +0.32 / +0.38 | **pass** |
| small | 4 (2) | 0.75 | 0.18 | +0.57 (−0.24, 0.88) | too few | fail (sample) |

**This is the most robust signal Sector has found.** When a creek's modeled flow rises well above its own recent dry-weather level, that creek's arm is 3–5× more likely than usual to read murkier beyond noise, in every untouched year. It is a statement about the model's *relative* change, never its cfs.

## 6. Zone / head-to-mouth (H3, secondary)

- **Qualifying events** (cold-season storm window, same pass and arm, ≥ 3 measurable zones): **47**. Of those, 27 have the head measured.
- **Result:** the head is stronger than the rest (ρ < 0) in **53%**, sign test **p = 0.18**. By year: 100% (5 events), 55% (33), 22% (9). **Not supported.**
- **Head coverage (item 11):**
  - 106 cold-season storm events had any measurable zone in a large or medium arm; 46 of them (43%) had a measurable head, and 44 had both head and mouth.
  - **Heads never measurable in 2021/2023/2024:** Crow, Dry Creek (into Roseberry), Jagger, Long Island, Nichols, Polecat.
  - **Heads almost never measurable:**

    | Arm | Head measurable on |
    |---|---|
    | Mud | 0.5% of passes |
    | Town Creek (Jackson) | 0.9% |
    | Town Creek (Marshall) | 1.9% |
    | Slaton | 2.8% |
    | Coon | 3.3% |
    | Aspel | 4.7% |

  - **In those heads, on an average pass:**
    - 44–74% of the water is unreadable (the bank and structure standoffs, or Sen2Cor not calling it water);
    - 19–45% is under cloud;
    - up to 29% is grass.
  - **Insufficient head observations alone don't explain the failure.** Where heads are read (27 events), the ordering is still inconsistent. But for most large arms the head question cannot be asked at all with the production read.

## 7. Baselines vs challengers (out of sample; δ frozen from discovery)

On each challenger's own condition units:

| Class × challenger | Obs (storms) | MAE log10: persistence / reversion / challenger | Challenger − persistence (95%) | Direction accuracy: persistence / challenger | Peirce skill (95%) | Median anomaly (95%) |
|---|---|---|---|---|---|---|
| season × large | 174 (13) | 0.241 / 0.247 / 0.266 | +0.025 (−0.042, +0.072) | 48% / 47% | 0.09 (−0.11, 0.31) | +0.003 (−0.13, 0.19) |
| **flow × large** | 162 (12) | 0.262 / 0.266 / **0.244** | −0.018 (−0.072, +0.038) | 49% / 50% | 0.17 (−0.01, 0.36) | +0.12 (−0.04, 0.19) |
| season × medium | 91 (12) | 0.157 / 0.158 / 0.171 | +0.014 (−0.036, +0.040) | 62% / 58% | 0.22 (−0.04, 0.54) | −0.05 (−0.11, 0.04) |
| **flow × medium** | 68 (9) | 0.168 / 0.191 / **0.146** | −0.022 (−0.084, +0.016) | 57% / **68%** | **0.30 (0.08, 0.52)** | **+0.12 (0.04, 0.21)** |
| season × small | 11 (7) | 0.173 / 0.142 / 0.495 | +0.32 (+0.10, +0.46) | 73% / 18% | n/a | −0.07 |
| flow × small | 4 (2) | 0.132 / 0.264 / 0.264 | | | | +0.31 |
| season × main stem | 5 (5) | 0.148 / 0.195 / 0.195 (δ = 0, so it is persistence) | | | | −0.07 |

Over **all** of a class's observations, no challenger is worse than persistence by more than 0.005 (G8), except season × small.

**Calibration by confidence.** Persistence error falls as the previous observation's coverage rises:

| Class | Previous coverage 30–50% | 50–75% | ≥ 75% |
|---|---|---|---|
| large | 0.182 | 0.145 | 0.134 |
| medium | 0.136 | 0.131 | 0.126 |

The observation-quality ordering is meaningful.

**By lag (large, error):** 0.31 at 0–1 d, 0.25 at 2–3 d, 0.27 at 4–6 d, 0.18 at 7–10 d. Errors are highest right after storms, as expected.

## 8. Year-by-year holdouts (condition units, challenger − persistence MAE)

| Class × challenger | 2021 | 2023 | 2024 |
|---|---|---|---|
| season × large | −0.105 (4 storms) | **+0.070** (5) | −0.034 (4) |
| flow × large | −0.084 (3) | +0.018 (4) | −0.028 (5) |
| season × medium | too few (2 storms) | +0.041 (5) | −0.076 (5) |
| flow × medium | −0.156 (3) | +0.013 (3) | −0.034 (3) |

**2023 is the year that fails every challenger.** It has the most condition observations (116 large, 89 flow), and in it persistence beats every challenger.

## 9. Evidence gate (per class × challenger)

| | G1 independence | G2 hypothesis | G3 effect > noise | G4 beats persistence | G5 direction | G6 beats reversion | G7 quality | G8 no harm | Decision |
|---|---|---|---|---|---|---|---|---|---|
| season × large | ✗ (13 storms; largest 26%) | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | insufficient evidence |
| flow × large | ✗ (12 storms) | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | insufficient evidence |
| season × medium | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | insufficient evidence |
| **flow × medium** | ✗ (**9 storms; largest 34%**) | ✓ | ✓ | ✗ (interval crosses 0) | ✓ | ✓ | ✓ | ✓ | insufficient evidence |
| season × small | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | insufficient evidence |
| flow × small | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | insufficient evidence |
| season × main stem | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | insufficient evidence |

- **Combined challenger:** not evaluated. The preregistration allows it only where both season and flow are supported.
- **Within-arm structure (H3):** not supported.
- **Supported arm classes: none.**
- **Stated per class**, as asked:
  - relative-flow runoff signal in large and medium arms: replicated as a hypothesis, unsupported as a prediction (sample);
  - cold-season response in large arms: replicated as a hypothesis, unsupported as a prediction (magnitude);
  - small arms, the main stem and head-to-mouth structure: unsupported.

## 10. Secondary: the Stage 2 per-arm state on untouched years

`ClarityReplay` (hourly rain, reconstructed fill distances) on 2,456 pairs across the three years:
- **"Murkier" held** 16.9% of the time, against a 10.2% base rate.
- **Direction skill:** Peirce **0.14 (0.004, 0.28)**. By year: 0.19 (−0.06, 0.40), **−0.02 (−0.22, 0.19)**, 0.29 (0.04, 0.50).
- **The authority ladder is clearly ordered out of sample.** The next pass matched the scene 78% of the time at high authority, 65% moderate, 61% low, 55% none. In discovery it was 81 / 75 / 77 / 67.

The Stage 2 state's *authority* — how much to trust the scene after rain and flow — carries real information. Its *direction* is weak and year-dependent.

## 11. Is another sensor necessary for the creek heads? (feasibility only)

- **Width is not the limit.** Large-arm heads are 130–1,000 m wide mid-channel (Town Creek Marshall 178 m, Crow 132 m), which leaves 11–104 Sentinel-2 pixels across.
- **The production shore rules are.** On clear winter passes (`head_gate_diagnostic.py`, discovery passes only), Town Creek's head loses most of its water to the **100 m structure standoff**: bare winter fields and leafless riparian land read as bright non-vegetated land. 54% of pixels survive the bank rule, 8–9% the structure rule.
- **A relaxed rule** (bank 0 m, structure 30 m, cell minimum 10%) recovers ten times the head water there. But the shore's adjacency bias across arms and passes runs **from −0.26 to +0.70 log10**, larger than the effects being tested. It cannot be adopted without per-pixel validation against in-situ turbidity.
- **Some heads fail before any shore rule.**
  - Crow Creek: Sen2Cor calls only 5–31% of its head pixels water.
  - Mud Creek: the grass/FAI limits remove the head.
  - No Sentinel-2 rule recovers these.
- **Answer.** For heads like Town Creek's, a *validated* winter-aware structure rule on Sentinel-2 might suffice. For narrow or vegetated heads like Crow, Mud and Long Island, a finer sensor or ground truth is needed:
  - PlanetScope (3 m, near-daily, commercial) is the only realistic satellite option; Landsat (30 m) is worse than Sentinel-2.
  - Sector users' own visibility reports in those heads, with time, place and photo, are the natural ground truth. They would validate a relaxed rule and fill in where no satellite can see. They need enough reports per arm per storm to matter, and they must be kept as `userReported`, never merged with satellite values.

## 12. What would change the answer

1. **More independent storms per class.** The gate needs ≥ 15 storms with measurable condition observations; three years gave 9–13, at about 3–5 a year. That means more years:
   - **Fill 2022** from a C1-equivalent source (ESA's CDSE reprocessing), preregistered as a pipeline source change.
   - **Go back before October 2020**, which needs a rain source other than MRMS Pass 2 (Stage IV, or MRMS Pass 1), also preregistered.
2. **A preregistered test of the relative-flow challenger alone.** It is the one candidate close to the gate, and it would be tested on those added years.
3. **A validated winter structure rule**, so large-arm heads enter the data at all, checked against user or in-situ reports.

---

## Files

- `docs/clarity/CLARITY_STAGE_3B_PREREGISTRATION.md` and `.sha256`: frozen before any historical data.
- `docs/clarity/CLARITY_FUSION_STAGE_3B_STATUS.md`: the interim status, superseded by this hand-off.
- **Data** (`docs/data/hydrology/guntersville/stage3b/`):
  - `results.json`: the full evaluation output;
  - `constants.json` and `validation_spec.json`;
  - `pass_candidates_hist.json`, `passes/` (per pass, per arm) and `zone_history_hist.json.gz`;
  - `anchors/` (238 files);
  - `rain_daily_hist.json.gz`, `rain_pass_hours_hist.json.gz`, `nwm_daily16z_hist.json.gz` (with versions), `usgs_iv_hist.json.gz`;
  - `replay_hist.json`, `head_gate_diag.json`, `zone_widths.json`;
  - `wind_asos_4A6_GAD_HSV_2020-2024.csv.gz`.
- **Scripts:**
  - `stage3b_eval.py` (frozen), `pass_candidates.py`, `nwm_history.py` (records versions);
  - `head_gate_diagnostic.py`, `head_widths.py` (feasibility).
- The 238 per-cell pass files (about 35 MB) stay out of git. `pass_history.py --cells` on `pass_candidates_hist.json` rebuilds them in 3–4 hours.

**STOP. Validation complete; no production implementation.**
