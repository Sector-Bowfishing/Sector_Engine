# Current Clarity: P2 Pre-registration and Guntersville Survey Plan

**Stage 10 · 2026-09-29 · Guntersville (AL)**

This stage:
1. Froze the four benchmarks.
2. Added the "Measured with a Secchi disk" answer to the master field report.
3. Pre-registered and hashed P2, the physics-routed hybrid, and a separate SWIR-residual experiment, before any fresh data existed.
4. Ran both once on the historical corpus as a development check.
5. Built a survey plan from the frozen models' disagreements.

Nothing was deployed except the master iOS build with the new answer (§1).

---

## The short version

**P2 is pre-registered.**
- Frozen at **2026-09-29 18:08:57 UTC**, manifest sha256 **`374d4cd36c8a195daf577d4a680aa099a161fafd0e9af316253d380a1fdd96d4`**.
- 18 files are pinned, including the exact code that will score the fresh data.
- Nothing has changed since; `verify_freeze.py` confirms it.

**Fresh validation data touched: none.**
- No Sector field report, no 2026 agency value and no fresh national draw was read.
- The 7 agency records Stage 8 fetched (dates seen, values never read) are excluded anyway.

**The routing rule, from sensor physics.**
- Water leaves essentially no light at 1610 nm, so each pixel's own B11 is its image residual.
- P1 is trusted only if removing that residual would move its answer by no more than 20%: the half-width of the stained class.
- Otherwise C3 answers, if it is inside its own validated domain. Otherwise P2 refuses.
- No Secchi value enters the rule.

**Development check: NOT PROMISING (by the pre-registered definition).** It is not certification either way.
- **The criterion P2 misses:** stained 2–3 ft water reads **+0.87 ft**, against P1's +0.11. The rule routes 11 of the 18 stained observations to C3, because in those arms B11 is a quarter to a half of the 704 signal. The criterion required P2 to stay within 0.5 ft of P1.
- **Otherwise P2 is the strongest model measured so far (historically):**
  - 8 of 9 gates pass on both schemes; only the clear channel fails, at −1.87 ft;
  - it is the first model to pass the 4-class accuracy gate (0.55 against a 0.51 bar);
  - Spearman 0.56, monotone, channel/arm AUC 0.92.
  - None of that raises readiness.
- **Nothing was retuned.**

**The SWIR experiment (P1S): fails its own criteria, as predicted.**
- **Clear channel:** −2.7 ft.
- **Stained water:** 0.6 ft worse than P1.

**A new risk: the routing depends on the satellite.**
- **Sentinel-2C passes:** B11 over water is higher and B05 lower, so P2 sends nearly the whole lake to C3 (99%). C3 also reads the lake about 2 ft clearer.
- **2A/2B passes:** P1 answers 16–48% of the lake.
- **Evidence:** 5 passes, so this is suggestive, not conclusive. The survey plan spans both groups.

**Survey plan: 42 targets in three lake sections.**
- **Formats:** a GPX, a KML, a CSV and a printable boat card that carries no model numbers.
- **Pass calendar:** Sentinel-2 passes Guntersville nearly every other day.

**Readiness remains 2/10.**
- Only fresh held-out evidence can move a capability.
- §12 gives the exact bar for each move: 2 → 4 → 6 → 8.

---

## 1. "Measured with a Secchi disk": implementation and tests

**What changed** (master beta, iOS `feat/clarity-production`, uncommitted):

**Model.** `TripClarityNote.measuredWithSecchiDisk: Bool?`
- It is optional, a lightweight migration.
- Old notes read nil, meaning unknown.

**Rule** (`FieldSurvey.secchiDisk`):
- **Yes is kept only for a daylight report with its exact depth.**
- A Yes under lights, or without feet, is stored as unanswered. It is never upgraded into a measurement.
- No is kept as given.

**The report sheet**, under *More (optional)*:
- A **Secchi disk** row: Not sure / Yes / No.
- It is enabled only when lights are off and exact feet are entered. It resets if either condition goes away.
- Its caption says what Yes means: a white disk or plate on a measured line, in daylight, at the depth where it disappears.

**Provenance and export.**
- `method` stays `userReportedDayVisibility`; `source` stays `fieldReport`. It is never relabelled `instrumentMeasured`.
- The export schema is now `sector-field-clarity-report-v2` (v1 plus this field). The new column is in both the JSON and the CSV.
- **The shared payload is unchanged.** A test checks that no disk answer, depth or feet appears in it.
- Daylight and under-lights reports stay separate throughout.

**Tests:**
- New `SecchiDiskFieldTests`, all pass:
  - the daylight-and-feet rule;
  - persistence;
  - the JSON and CSV column;
  - no leak into the shared payload;
  - the method never relabelled;
  - old notes exporting unknown.
- Current Clarity classes: 30 pass.
- **Full iOS suite: 752 tests, 0 failures** (2 skipped).

**Master build on your iPhone:** 4.1.0 (28), Release, development-signed. Installed with devicectl at 13:28 CDT, launched and running. The binary contains the v2 schema and the new caption.

**Rollback caveat (as in Stage 9).** Export your reports before reinstalling an older TestFlight build.

---

## 2. Frozen benchmarks

| Model | Frozen as | Check |
|---|---|---|
| Champion | secchi-power-v1 on production turbidity | formula in `frozen/models.py` |
| C3 | fitted **once** on all 715 historical clean rows; domain from its training inputs | `frozen/c3_frozen.json`; Stage 7 outputs regenerate byte-identically |
| C6 | Stage 8 `c6_model.json`, unchanged | Stage 8 outputs regenerate byte-identically |
| P1 | Stage 9 block, byte-identical | block sha256 `ed0dcfe9…`; Stage 9 pre-registration `4cc30221…` unchanged |

**Unchanged in P1:** no constant, no guard, and no empirical constant for the clear channel.

**Preserved from Stage 9:**
- stained water about unbiased;
- strong on algal and stained water;
- bright-sediment failures corrected;
- the clear channel badly under-read.

**C3 and C6 remain benchmarks.**

---

## 3. The exact P2 pre-registration, and the proof it came first

- **The full text:** `stage10/PREREGISTRATION_P2.md` (sha256 `c2c6e142…`).
- **The code** that implements it verbatim, and the code that will score it:

| File | sha256 (first 12) |
|---|---|
| `PREREGISTRATION_P2.md` | `c2c6e14269e6` |
| `frozen/p2.py` (routing) | `6ffeb12ed076` |
| `frozen/p1.py` (P1, byte-identical block) | `da26e4ee9a73` |
| `frozen/models.py` (champion, C3, C6, P1S) | `dc81e23542ff` |
| `frozen/metrics.py` (Stage 7 `evaluate` and Stage 8 `gates`, verbatim) | `7565d0c23d46` |
| `frozen/regions.py` (arm / main-stem lookup) | `6a65c2e6973c` |
| `frozen/build_observations.py` (fresh-data intake) | `8361cf0f8eed` |
| `frozen/fresh_eval.py` (the fresh verdict) | `e3f094b24e79` |
| `frozen/c3_frozen.json`, `c6_model.json` | `08665fe0afe8`, `206720531a4f` |
| `stage6/extract.py` (the read-out, unchanged) | `2ac2d7865123` |
| the engine's `derive_water_surface.py` at `0393791`, plus the arm grid (3 files) | pinned |
| `stage8/g2026_secchi.csv` (the exclusion list) | `4051da984cea` |

**Freeze record.** `FREEZE.json`: frozen at **2026-09-29T18:08:57Z**, manifest (canonical) sha256 `374d4cd3…`.
- `verify_freeze.py` re-checks every file before any fresh run.
- It passed after the development check and after the survey work.

**Disclosed in the pre-registration (§0):**
- **What the designer had seen:** Stage 9's class-level inputs (B05 and B11 by class) and P1's errors.
- **A pipeline dry run.** Run after `p2.py` was written, to test that the code runs. Its console line included the rounded historical readiness each system would score. No frozen file was changed after it.

**A stronger timestamp.** These hashes are self-attested. Pushing the pre-registration to GitHub before your first survey trip would give an independent timestamp. I have not pushed anything; say if you want it.

---

## 4. The exact optical routing rule

**Residual estimate.** r = max(ρ(B11), 0), taken from the same valid pixels as the reading.

| Residual source | At 704 nm compared with B11 |
|---|---|
| Sun glint | flat: equal |
| Sky glint | larger at 704 |
| Adjacency | comparable or larger at 704 (aerosol scattering is about 3× stronger there) |
| Aerosol-correction error | larger at 704 |

So B11 is roughly equal to the 704 residual for sun glint, and a lower bound for the other sources. It needs no Secchi value.

**Sensitivity.** S = |Z_P1(ρ − r) / Z_P1(ρ) − 1|, with r removed from all four bands.
- If P1 refuses after the removal, S = ∞.
- The threshold is **S ≤ 0.20**: the stained class's half-width relative to its centre (0.5 ft / 2.5 ft). It was set by the product, not fitted.

**Decision tree** (`frozen/p2.py`):

| P1 outcome | Route |
|---|---|
| Answers, S ≤ 0.20 | **P1**, authority ≤ Moderate, provenance "physical (P1)" |
| Answers, S > 0.20 or ∞, or no B11 | residual-limited → C3 check |
| Refuses: B05 < 0.003 only (below the noise floor) | → C3 check |
| Refuses: R7, an inconsistent inversion | → C3 check |
| Refuses: sun, other reflectance, band ratios, NDCI > 0.20, scum/vegetation, output range | **REFUSE** |
| C3 check: inside its domain, output in 0.5–20 ft | **C3**, authority ≤ Low, provenance "empirical (C3)", reason kept |
| C3 check fails | **REFUSE** |

**Valid range.** P1 answers and B11 is present; B11 ≤ 0.0215 already holds (the production gate).

**Rejected alternatives, and why:**
- **A scene-level open-water B11 floor:** it cannot be computed for the historical rows. Deferred.
- **A detection ratio B05/B11 ≥ 3:** it measures detection, not accuracy. And I knew from Stage 9 that it happens to split the arms (≈ 4) from the channel (≈ 1.8).

## 5. Domain and refusal logic

- **P1's guards are unchanged** (R1–R8).
- **C3's validated domain** is the 1st–99th percentile of its training inputs:
  - log10 R(B04): [−2.775, −1.107] when NDCI ≤ 0; [−2.359, −0.996] when NDCI > 0;
  - NDCI: [−0.461, +0.361];
  - output: 0.5–20 ft.
- **Outside any domain → refuse. Nothing is clamped.**
- **The algal warning** (NDCI > 0.03) is layered on top and caps any path at Low.
- **Vegetation and bottom-risk** are evaluation labels only, never routing inputs.
- **Expected failure modes (pre-registered):**
  1. Adjacency-heavy arms routed away from a correct P1.
  2. Sky glint larger at 704 than B11, so P1 is kept where it is still murky.
  3. The C3 path inheriting C3's clear bias in stained and algal water.
  4. Refusals concentrating in dense algae, so low coverage under 2 ft.

## 6. The separate SWIR-residual experiment (P1S)

**What it is.** P1 on ρ − ρ(B11), with every guard. No scale factor, and nothing fitted.

**Pre-registered criteria:**

| # | Criterion |
|---|---|
| (i) | Clear channel ≥ −1.5 ft **and** at least 1.5 ft closer to zero than P1 |
| (ii) | Stained \|bias\| ≤ 1.0 ft **and** no more than 0.5 ft worse than P1 |
| (iii) | Dark algal water \|bias\| ≤ 1.0 ft |
| (iv) | Coverage ≥ 80%; arms and channel reported separately |
| (v) | The nine gates |

**It is not part of P2.** A pass would only nominate it for a fresh test and a future pre-registration.

---

## 7. Development-only historical comparison

> **These are the same historical rows every earlier stage inspected. They are a development
> diagnostic, not certification, and they do not count toward product readiness.** The frozen rule
> was not changed after seeing them.

### 7.1 Where P2 sends the water (72 clean Guntersville rows)

| Truth class | → P1 | → C3 | Refused | Median S | Median B05/B11 |
|---|---:|---:|---:|---:|---:|
| Clear ≥ 6 ft | 0 | 22 | 1 | 0.56 | 2.3 |
| Normal 3–6 ft | 3 | 25 | 2 | 0.41 | 2.6 |
| Stained 2–3 ft | **7** | **11** | 0 | **0.27** | 3.5 |
| Limited < 2 ft | 0 | 1 | 0 | — | — |

**Totals:**
- **Guntersville:** P1 10, C3 59, refused 3.
- **National clean (643):** P1 129, C3 396, refused 118.
- **Fresh national (412):** P1 58, C3 304, refused 50.

**Against the pre-registered predictions:**
- **Right:** the clear channel went to C3, as did very clear water; bright sediment stayed on P1 (TENR-417, 2018-03-06: S = 0.08, 1.7 ft against 2.7 observed).
- **Partly right:** the stained arms. The median S of 0.27 sits just above the bar, so 11 of 18 went to C3.
- **Wrong in size:** predicted +1.5 ft for P2 on stained water; it is **+0.87**. Seven stained rows stay on P1: six arm readings and the bright-sediment channel row, with B05/B11 between 3.7 and 10.4.

### 7.2 All five systems on the same rows (69 rows P2 answers)

C3 and C6 use their held-out predictions (leave-one-year-out shown; leave-one-station-out in `dev_results.json`, within 0.1 ft for P2).

| Metric (69 rows) | Champion | C3 | C6 | P1 | **P2** |
|---|---:|---:|---:|---:|---:|
| Spearman | −0.11 | 0.40 | 0.39 | 0.51 | **0.56** |
| Median signed (ft) | −0.78 | +0.14 | +0.17 | −1.48 | **−0.28** |
| MAE | 2.44 | 1.86 | 1.82 | 2.28 | **1.66** |
| Median absolute | 2.19 | 1.58 | 1.18 | 1.74 | **1.27** |
| Station-balanced median signed | +0.10 | +0.47 | +0.48 | −0.66 | **+0.27** |
| AUC, channel against arm | 0.343 | 0.826 | 0.838 | 0.888 | **0.918** |
| 4-class accuracy (constant 0.41) | 0.30 | 0.49 | 0.46 | 0.32 | **0.55** |
| Monotone | no | yes | yes | no | **yes** |
| **Stained 2–3 ft** (n 18) | +2.02 | +1.69 | +1.23 | **+0.11** | **+0.87** |
| **Clear channel** (n 20) | −4.04 | **−1.87** | −2.42 | −4.43 | **−1.87** |
| Algal arms | +1.21 | +1.37 | +0.72 | −0.26 | **+0.38** |
| Sediment turbid | −1.75 | +0.16 | +0.60 | −1.80 | **−0.18** |

**Where P2 lands:**
- **Stained water:** between P1 and C3.
- **Clear channel:** equal to C3, and 2.6 ft better than P1.
- **Normal water:** −0.05 ft.

**4-class results for P2:**

| Class | Recall | Precision |
|---|---:|---:|
| Clear | 12 of 22 | 0.63 |
| Normal | 20 of 28 | 0.50 |
| Stained | 6 of 18 | 0.67 |

For comparison, P1's clear recall was 1 of 22.

**The nine gates (P2, both schemes):**

| # | Gate | Result |
|---|---|---|
| 1 | Spearman ≥ 0.5 | pass |
| 2 | Monotone | pass |
| 3 | Station-balanced bias | pass |
| 4 | Stained ≤ +1.0 ft | pass |
| 5 | Clear channel ≥ −1.5 ft | **fail** (−1.87) |
| 6 | AUC ≥ 0.8 | pass |
| 7 | 4-class ≥ constant + 0.10 | pass |
| 8 | Beats the champion | pass |
| 9 | National | pass: median absolute error 2.08 against the champion's 2.25; Alabama MAE 1.12 against 1.46 |

**National non-regression, fresh set (362 paired):**
- **Spearman:** P2 0.575, the best of the five.
- **Stained, n 45:** P2 +0.32; C3 +0.99; C6 +1.33; champion +0.90.
- **Clear:** P2 −3.82.

### 7.3 Every stained observation

| Date | Station | Observed | P1 | **P2** | Route | S | B05/B11 | C3 |
|---|---|---:|---:|---:|---|---:|---:|---:|
| 2017-09-07 | Browns Creek | 2.30 | 2.69 | **2.69** | P1 | 0.09 | 8.2 | 4.55 |
| 2018-03-06 | TENR-417 (channel) | 2.71 | 1.71 | **1.71** | P1 | 0.08 | 10.4 | 3.06 |
| 2018-05-15 | GUNM-8 | 2.82 | 1.95 | **3.07** | C3 | 0.32 | 2.5 | 3.07 |
| 2018-09-11 | Browns Creek | 2.95 | 2.67 | **2.67** | P1 | 0.20 | 3.7 | 4.57 |
| 2019-10-22 | Browns Creek | 2.30 | 2.30 | **2.30** | P1 | 0.11 | 6.2 | 4.15 |
| 2022-06-14 | GUNM-8 | 2.85 | 1.91 | **2.58** | C3 | 0.60 | 1.7 | 2.58 |
| 2022-09-29 | GUNM-10 | 2.43 | 2.00 | **2.79** | C3 | 0.25 | 3.5 | 2.79 |
| 2022-09-29 | GUNM-7 | 2.17 | 2.62 | **3.75** | C3 | 0.43 | 2.5 | 3.75 |
| 2022-09-29 | GUNM-8 | 2.50 | 2.41 | **3.66** | C3 | 0.30 | 3.1 | 3.66 |
| 2022-09-29 | GUNM-9 | 2.53 | 2.53 | **3.45** | C3 | 0.46 | 2.3 | 3.45 |
| 2023-06-28 | South Sauty Creek | 2.62 | 2.84 | **4.22** | C3 | 0.49 | 2.1 | 4.22 |
| 2025-10-15 | GUNM-10 | 2.49 | 2.45 | **2.45** | P1 | 0.06 | 10.1 | 4.25 |
| 2025-10-15 | GUNM-7 | 2.76 | 3.29 | **5.30** | C3 | 0.39 | 2.7 | 5.30 |
| 2025-10-15 | GUNM-7B | 2.25 | 2.93 | **6.46** | C3 | ∞ | 0.9 | 6.46 |
| 2025-10-15 | GUNM-8 | 2.23 | 2.64 | **5.51** | C3 | ∞ | 4.2 | 5.51 |
| 2025-10-15 | GUNM-9 | 2.62 | 3.45 | **3.45** | P1 | 0.20 | 4.3 | 5.51 |
| 2025-10-15 | TENR-350 (channel) | 2.85 | 4.86 | **8.09** | C3 | 0.31 | 3.6 | 8.09 |
| 2025-10-16 | GUNM-4 | 2.20 | 3.36 | **3.36** | P1 | 0.17 | 4.9 | 7.49 |

**The worst P2 failures are the C3 fallback in algal water (Oct 15 2025).**
- Where P1 becomes residual-limited, C3 reads **5.3–8.1 ft** in 2.2–2.9 ft water.
- The algal warning would flag three of them (GUNM-7, GUNM-7B and GUNM-8) and cap them at Low. It cannot give the right number.

### 7.4 Water-type subsets (clean rows, paired)

| Water type | n | Routes (P1 / C3 / refused) | Champion | C3 | C6 | P1 | **P2** |
|---|---:|---|---:|---:|---:|---:|---:|
| Dark algal water | 28 | 8 / 20 / 0 | +1.21 | +1.37 | +0.72 | −0.26 | **+0.38** |
| Stained arms | 17 | 6 / 11 / 0 | +1.99 | +1.76 | +1.22 | +0.22 | **+0.92** |
| Sediment-muddy | 6 | 1 / 5 / 0 | −1.75 | +0.16 | +0.60 | −1.80 | **−0.18** |
| Very clear channel | 21 | 0 / 20 / 1 | −4.04 | −1.87 | −2.42 | −4.43 | **−1.87** |
| Normal 3–6 ft | 30 | 3 / 25 / 2 | −0.61 | +0.16 | +0.11 | −1.48 | **−0.05** |
| Algae/sediment tug-of-war | 11 | 2 / 9 / 0 | +1.91 | +1.76 | +1.22 | −0.04 | **+1.17** |

### 7.5 The pre-registered PROMISING test

| # | Criterion | P2 | Result |
|---|---|---|---|
| 1 | Stained ≤ +1.0 **and** within 0.5 ft of P1 | +0.87 against P1 +0.11 (a 0.76 ft gap) | **fail** |
| 2 | Dark algal \|bias\| ≤ 1.0 | +0.38 | pass |
| 3 | Clear channel ≥ C3 − 0.5 | −1.87 against C3 −1.87 | pass |
| 4 | Normal \|bias\| ≤ 1.0 | −0.05 | pass |
| 5 | Coverage ≥ 80% (clean, stained) | 96%, 100% | pass |

**→ NOT PROMISING.**
- It misses one criterion by 0.26 ft beyond the tolerance.
- **It did not "obviously fail":** it is the best historical model on most measures. But the pre-registered purpose was to keep P1's stained result, and it does not.
- Per the rule, **P2 stays frozen as written and goes to fresh validation unchanged.** Only fresh data can say whether the routing gave away real accuracy in the arms, or removed a fragile one.

### 7.6 The SWIR experiment (P1S)

| Criterion | P1S | P1 (same rows) | Result |
|---|---:|---:|---|
| (i) Clear channel ≥ −1.5 ft, ≥ 1.5 ft closer than P1 | −2.74 | −4.60 | **fail** (1.86 ft closer, but still below −1.5) |
| (ii) Stained \|bias\| ≤ 1.0 ft, ≤ 0.5 ft worse than P1 | +0.63 | 0.00 | **fail** (0.63 ft worse) |
| (iii) Dark algal \|bias\| ≤ 1.0 ft | +0.22 | — | pass |
| (iv) Coverage (clean, stained) | 82%, 89% | — | pass (arms +0.17; all channel rows −1.47) |
| (v) Nine gates | fails 2, 5, 7 | — | **fail** |

**→ P1S fails its development criteria.**
- This is as predicted: a flat SWIR subtraction helps the channel but pushes the arms clearer.
- It stays out of P2.

### 7.7 What this says about P1's arm result (for the fresh test)

- **In most stained arms, the scene's own residual is 25–50% of the 704 signal** (median B05/B11 3.5).
- **P1 is nonetheless unbiased there.** The pre-registered physical explanation: two opposing biases cancelling.
  - the residual reads murky;
  - chlorophyll absorption at 704 reads clear.
- If that is right, P1's arm accuracy will not survive a different chlorophyll-to-residual balance.
- **The two pre-registered diagnostics test this on fresh data** (P1's error against NDCI, and against B05/B11, in arms).

---

## 8. Fresh held-out validation plan (the only source of a verdict)

**What counts as fresh:**
1. **Sector field reports** with `observedAt` ≥ 2026-09-29T18:08:57Z.
2. **Agency Secchi** on Guntersville dated 2026 or later, never fetched before the freeze. That includes ADEM's and TVA's **2026 warm season** once published. The 7 Stage 8 records are excluded by organisation, site and date.
3. **A fresh national draw** for gate 9, following the Stage 8 protocol: seed 20261001, WQP dated 2026-04-01 or later, sites in no earlier file.

**The frozen pipeline:**
1. `build_observations.py`: exports and agency CSVs → observations.
2. `stage6/extract.py --max-dt 1`: the production gates and the 60 m disk. It takes the best pass per observation (≥ 5 valid pixels) and dedupes to one row per site-cell, scene-day and tier.
3. `fresh_eval.py`, which produces:
   - the nine gates, P2's coverage precondition and the minimum-sample checks;
   - the SWIR-experiment criteria;
   - the fresh algal-warning PPV;
   - the capability verdicts for each system.

**Truth tiers:**

| Tier | Source | Use |
|---|---|---|
| Secchi-grade | agency Secchi, and field reports with **Secchi disk = Yes** (which implies daylight and exact feet) | the gates and capabilities |
| Visual (daylight, exact feet, no disk) | field | scored separately |
| Band-only daylight | field | scored separately |
| Night under lights | field | scored separately |

The last three are never pooled with Secchi-grade.

**Labels:**
- **Arm, main stem:** the engine's arm grid.
- **Algal:** NDCI > 0.03 or chlorophyll ≥ 15.
- **Sediment:** NDCI ≤ 0, and (turbidity ≥ 8 NTU or a muddy/brown colour note).
- **Warm season:** May–September.
- **Vegetation** ("vegetation here" = Yes, or the NDVI/FAI share) and **bottom-risk** ("bottom visible" = Yes, or disk ≥ half the depth) are excluded from the headline.

**Rules:**
- **One run per declared batch.** Results can never change P2.
- **A successor (P3)** needs its own pre-registration, and data collected after its own freeze.
- **Not pre-registered, and reported as such:** results split by satellite (2A/2B against 2C) will be shown as a diagnostic, because of the platform finding (§9.3).

## 9. Minimum coverage and the survey plan

### 9.1 Minimum Secchi-grade coverage (clean rows) before any class is judged

| Class | Observations | Scene-days | Arms | Realistic source |
|---|---:|---:|---:|---|
| Clear channel (≥ 6 ft) | 20 | 5 | — | survey (G07, G09, G10, G22, G24–G26, G38–G42), agency |
| Normal 3–6 ft | 25 | 5 | — | survey, anywhere |
| Stained 2–3 ft | 30 | 5 | 4 | survey (the 8 stained stations and 6 disagreement targets), ADEM 2026 |
| Badly limited < 2 ft | 10 | 3 | — | the 4 "possibly under 2 ft" targets, and after runoff |
| **Warm-season arms (May–Sep)** | 20 | 4 | 4 | **cannot be met this fall.** ADEM/TVA 2026 warm season when published, or the summer 2027 survey |
| Algal (NDCI > 0.03 or chlorophyll ≥ 15) | 20 | 4 | — | the 4 algal targets, and arms in bloom |
| Sediment-driven | 12 | 3 events | — | the "after rain only" targets |

**Below a minimum:** that class is **INSUFFICIENT**, with no verdict and no score change.

**The P2 verdict** needs:
- the clear, normal and stained minima;
- ≥ 80% coverage;
- all nine gates, with gate 9 on the fresh national set.

**What the survey has to deliver.** One lake section per trip is 12–19 targets. That means at least 5–6 trips on different pass days for the core classes, and more for water under 2 ft and for sediment.

### 9.2 The Guntersville Clarity Survey plan (master only)

**How the targets were chosen.** They come from the frozen models' disagreements on the five latest usable passes (Sep 13, 15, 17, 20, 28): about 21,000 blocks of roughly 90 m.

**Selection rules:**
- A block must be read on ≥ 3 passes, and its category must hold on ≥ 2.
- Every target is ≥ 60 m from shore, ≥ 1.5 km from any other target, and ≥ 1 km from either dam.
- No truth was used; targets were fixed before any survey. `targets_boat.csv` sha256 `ed470af8…`.

| Category | Targets | IDs | What it tests |
|---|---:|---|---|
| Known stained arms (agency stations) | 8 | G03 G05 G08 G11 G16 G18 G21 G30 | P1's arm result, at stations with a history |
| **P1 says stained, C3 says normal/clear** | 6 | G27 G31 G32 G33 G34 G36 | whether P1's "stained" is real where C3 disagrees |
| **C3 says clear, P1 says murky** | 5 | G24 G25 G26 G38 G39 | the clear-channel failure, directly |
| Active algal warning | 4 | G12 G13 G15 G28 | the warning's PPV and algal-water visibility |
| Possibly under 2 ft | 4 | G01 G02 G04 G37 | the thinnest class |
| Clear main channel (agency stations) | 4 | G22 G40 G41 G42 | continuity with TVA/ADEM TENR stations |
| Clear main channel (open water) | 3 | G07 G09 G10 | the clear class, far from adjacency |
| After rain only (runoff) | 4 | G14 G23 G29 G35 | sediment-driven water, within 48 h of ≥ 1 in of rain |
| Controls (models give the same class) | 4 | G06 G17 G19 G20 | agreement locations, for contrast |

**Deliverables** (`stage10/survey/`):
- `GUNTERSVILLE_CLARITY_SURVEY_BOAT_CARD.pdf`: protocol, pass calendar and targets by section. **No model numbers, so readings are not anchored.**
- `guntersville_clarity_targets.gpx` and `.kml`: waypoints G01–G42, for any chart plotter or maps app.
- `targets_boat.csv`: with a tap-to-navigate Apple Maps link per target.
- `targets_map.png`: the overview map.
- `targets_analyst.csv`: the model readings behind each target. For analysis only; keep it off the boat.

**Pass days, Oct 2026:**

| Satellite | Dates |
|---|---|
| S2A | Oct 7, 20, 27 |
| S2B | Sep 30; Oct 3, 10, 13, 20, 23, 30 |
| S2C | Oct 5, 8, 15, 18, 25, 28 |

November is on the boat card.

**Timing.** The pass is at about 11:35–11:45 CDT. Survey between 10:00 and 14:00 on a mostly clear day.

**Platform mix.** Plan at least 2 trips on S2C days and at least 3 on S2A/S2B days, because the routing behaves differently between them (§9.3).

**Protocol at each target:**
1. Use a white disk on a line marked in feet, on the shaded side of the boat, without sunglasses. Take the average of where it disappears and where it reappears.
2. In the app: lights OFF, exact feet, **Secchi disk: Yes**.
3. Record the depth from sonar, bottom visible, vegetation, water colour, and a photo.
4. Don't open the clarity layer first.
5. Export after each trip.

### 9.3 A new risk found while building the plan (reported, not acted on)

| Pass | Satellite | Median B11 | Median B05 | P2 → P1 | Lake-median C3 |
|---|---|---:|---:|---:|---:|
| Sep 13 | S2B | 0.0049 | 0.0182 | 45% | 4.1 ft |
| Sep 15 | S2C | 0.0062 | 0.0138 | 0.2% | 5.8 ft |
| Sep 17 | S2A | 0.0033 | 0.0134 | 48% | 5.4 ft |
| Sep 20 | S2B | 0.0070 | 0.0214 | 16% | 3.9 ft |
| Sep 28 | S2C | 0.0076 | 0.0149 | 1% | 6.0 ft |

**Whatever the cause, both the routing and the red-band number depend on the pass.**
- **On the two S2C passes:** B11 is higher and B05 lower, so P2 sends nearly everything to C3. C3 also reads the lake about 2 ft clearer.
- **Possible causes:** an inter-sensor radiometric difference, a processing difference, or haze on those days.
- **Evidence:** 5 passes; this is not settled.

**Relevance beyond P2.** The champion is also a red-band model, so this could affect the production number too. It deserves its own cross-platform check (same-day S2B/S2C pairs over stable water) once Current Clarity's validation is under way. It is flagged here and out of scope for this task.

---

## 10. Readiness gates (unchanged)

- **The nine gates** are unchanged (Stage 7/8, verbatim in `frozen/metrics.py`).
- **Stained water is first-class** (gate 4).
- **P2's added precondition:** coverage ≥ 80% of clean rows and of stained rows.
- **Readiness rubric:** unchanged. Seven capabilities; SUPPORTED 1, PARTIAL 0.5, NOT 0; out of 7 scaled to 10 and rounded.
- **The score is for the product as it runs:** today, the champion plus the algal warning. A candidate's fresh evidence is reported "as if deployed", and moves the score only once that candidate is deployed.

## 11. Current Clarity product readiness: 2/10 (unchanged)

| Capability | Today | Why unchanged |
|---|---|---|
| Clear channel | NOT | no fresh evidence |
| Normal 3–6 ft | PARTIAL | no fresh evidence |
| Stained 2–3 ft | NOT | no fresh evidence |
| Algae-affected | PARTIAL | the warning is live; there is no fresh PPV yet |
| Sediment-muddy | PARTIAL | no fresh evidence |
| Badly limited < 2 ft | NOT | no fresh evidence |
| Bottom-risk / shallow clear | NOT | needs a depth input (out of scope) |

**Score: 1.5 / 7 → 2.1 → 2/10.**

It is not raised for any of these:
- P2's historical showing;
- the architecture;
- the survey system;
- the Secchi field.

## 12. What would actually move the score (fresh, Secchi-grade, clean data)

These are the bars coded in `frozen/fresh_eval.py`. A class below its §9.1 minimum stays where it is.

| Capability | NOT → PARTIAL | PARTIAL → SUPPORTED |
|---|---|---|
| **Clear channel** (main stem, ≥ 6 ft) | minimum met (20 / 5 scene-days); median signed ≥ −2.5 ft; clear recall ≥ 0.40; clear precision ≥ 0.60 | n ≥ 40 on ≥ 8 scene-days; median signed in [−1.5, +1.5]; recall ≥ 0.60; precision ≥ 0.75; refusals ≤ 30% |
| **Normal 3–6 ft** (PARTIAL today; downgraded if these fail) | \|median signed\| ≤ 1.5; normal recall ≥ 0.50 | n ≥ 40 on ≥ 8 scene-days; \|median signed\| ≤ 1.0; recall and precision ≥ 0.60; monotone calibration |
| **Stained 2–3 ft** | minimum met (30 / 5 scene-days / 4 arms); \|median signed\| ≤ 1.0; stained recall and precision ≥ 0.40 | n ≥ 60 on ≥ 10 scene-days in ≥ 6 arms, warm **and** cool season; \|median signed\| ≤ 0.75; recall and precision ≥ 0.60 |
| **Algae-affected** (PARTIAL today) | fresh warning PPV ≥ 0.25 (≥ 20 flagged) | n ≥ 30 algal on ≥ 5 scene-days; PPV ≥ 0.40; \|median signed\| ≤ 1.0 in algal water; class accuracy ≥ constant + 0.10 there |
| **Sediment-muddy** (PARTIAL today) | \|median signed\| ≤ 2.0; bright-sediment-as-clear ≤ 15% | n ≥ 20 on ≥ 4 scene-days; \|median signed\| ≤ 1.0; bright-sediment-as-clear ≤ 5% |
| **Badly limited < 2 ft** | minimum met (10 / 3 scene-days); ≤ 10% called ≥ 4 ft; ≥ 60% called < 3 ft **or refused** (an honest refusal counts) | n ≥ 25 on ≥ 5 scene-days; recall ≥ 0.60; precision ≥ 0.50; median signed ≤ +0.75 |
| **Bottom-risk / shallow clear** | needs a depth input: a bottom-risk flag on ≥ 60% of bottom-visible reports, ≤ 30% false flags (n ≥ 15). **Cannot move in this track.** | ≥ 80% flagged, ≤ 15% false flags (n ≥ 30) |

**The path, without moving the goalposts:**

| Target | What it takes | Score |
|---|---|---|
| **4/10** | Clear, stained and limited each reach PARTIAL (the others hold) | 3.0 / 7 = 4.3 |
| **6/10** | Additionally, normal, algae and sediment reach SUPPORTED | 4.5 / 7 = 6.4 |
| **8/10** | Additionally, stained and clear reach SUPPORTED | 5.5 / 7 = 7.9 → 8 |
| **9/10** | Additionally, limited reaches SUPPORTED | 6.0 / 7 = 8.6 → 9 |

Beyond that needs bottom-risk, and so a depth layer.

**Earning 4/10 needs a deployed system that meets these bars.** Historically:
- P2 already clears the clear-channel PARTIAL bar (median −1.87 ≥ −2.5; recall 0.55; precision 0.63);
- and the stained PARTIAL bar (+0.87 ≤ 1.0; recall 0.33, **just below 0.40**).

Whether it does on fresh data is exactly what the survey will show.

## 13. Exact next step once the survey data arrives

1. **Before the first trip:**
   - Decide whether to push `PREREGISTRATION_P2.md` and `frozen_manifest.json` to GitHub for an independent timestamp.
   - Load the GPX.
   - Print or save the boat card.
2. **After each trip:**
   - Export the field reports (Layers → Basemaps → Beta → Field clarity reports → Prepare export → Share) and AirDrop both files to the Mac.
   - Nothing is analysed yet.
3. **When the §9.1 minima look reachable** (a count, not a look at outcomes):
   - Declare the batch (its date range).
   - Fetch WQP Guntersville Secchi, chlorophyll and turbidity, plus the fresh national draw.
   - Then run, in order:
     1. `python stage10/verify_freeze.py`, which must print "all unchanged";
     2. `python stage10/frozen/build_observations.py --reports <exports…> --agency <wqp_secchi.csv> --stations <wqp_stations.csv> --chl … --turb … --out fresh_obs.csv`;
     3. `python stage6/extract.py fresh_obs.csv fresh_readouts.csv --max-dt 1`;
     4. `python stage10/frozen/fresh_eval.py fresh_obs.csv fresh_readouts.csv --national <fresh_national_readouts.csv> --out verdict_batch1.json`.
4. **Report exactly what `fresh_eval.py` says:**
   - P2 READY / NOT READY / INSUFFICIENT DATA;
   - the capability verdicts;
   - the readiness of the product as it runs;
   - the SWIR experiment;
   - the two arm diagnostics.
   - No re-analysis, no retuning.
5. **If P2 is READY,** propose a master-beta deployment separately, for approval. If not, any P3 is pre-registered first and tested only on data collected after its own freeze.

**Kept out of this task:** the vegetation map, a water-temperature redesign, the Wheeler/Wilson/Pickwick rollout, Sector Intelligence integration and bathymetry. Vegetation and bottom-risk stay as contamination labels.

**Not deployed:** P1, P2, C3, C6 or P1S. The only change that left this Mac is the master iOS build with the Secchi-disk answer.

---

## Files (session scratchpad `stage10/`)

- **Pre-registration and freeze:** `PREREGISTRATION_P2.md`, `frozen_manifest.json`, `FREEZE.json`, `verify_freeze.py`.
- **`frozen/`:** `p1.py`, `p2.py`, `models.py`, `metrics.py`, `regions.py`, `build_observations.py`, `fresh_eval.py`, `build_frozen.py`, `c3_frozen.json`, `c6_model.json`.
- **Development check:** `dev_check.py` → `dev_results.json`.
- **Pipeline dry run:** `dryrun/`.
- **Survey:** `survey_map.py`, `survey_targets.py`, and `survey/`:
  - `blocks_<date>.csv` for 5 passes;
  - `targets_analyst.csv`, `targets_boat.csv`, `targets.json`;
  - `guntersville_clarity_targets.gpx` / `.kml`;
  - `targets_map.png`;
  - `pass_calendar.json`;
  - `BOAT_CARD.md`, `GUNTERSVILLE_CLARITY_SURVEY_BOAT_CARD.pdf`.
- **iOS** (`~/Desktop/Development/iOS/Sector-mapbox`, uncommitted):
  - `PersonalTrip.swift`, `ClarityReports.swift` and `CurrentClarityViews.swift` (the Secchi-disk answer);
  - `SectorTests/CurrentClarityTests.swift`.

---

P2 PREREGISTERED

P2 HISTORICAL DEVELOPMENT CHECK: NOT PROMISING

FRESH VALIDATION DATA TOUCHED: NO

CURRENT CLARITY PRODUCT READINESS REMAINS: 2/10
