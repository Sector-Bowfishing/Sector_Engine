@@ answer
**Limited water is largely fixed. Stained water is not, and it looks like a resolution limit rather than a missing
signal.**
- **The multicomponent models.** Red, red-edge, green/red, blue/green and brightness together cut the exact-feet error
  from ×1.47 (C3) to ×1.36–1.38.
- **Limited water.** Recall rises from 0.32 to 0.54–0.65, and every CI excludes 0.
- **Stained water (2–3 ft)** stays at 0.21–0.38 recall on every model. The two diagnostics say why:
  - the class is only a factor of 1.5 wide, narrower than the best retrieval's error spread;
  - an unbiased retrieval with that spread would recall stained only 33%;
  - even perfect in-situ turbidity and chlorophyll reach only 48%.
- **Low visibility is mostly particles.** In stained and limited water, in-situ turbidity explains 28–30% of the variance
  (most of what in-situ data explain). Dissolved organic carbon adds 8%, and chlorophyll about 0. Sentinel-2's blue/green colour feature adds
  nothing there.
- **No pre-registered candidate is a Stage 13 success.** All fail the stained bars (recall ≥ 0.45, precision ≥ 0.40).
- **BEST, by the frozen fallback rule, is O2:** the linear multicomponent model with class cut-points learned on held-out
  lakes. Its balanced accuracy is 0.568 against 0.501 (CI excludes 0).
  - It generalises across regions (0.92–0.93 of its lake-held-out stained and limited recall).
  - Its class never flips on identical S2A/S2C 60 m disks once ±12% boundary bands are used.
  - **Its cost:** normal recall falls from 0.64 to 0.41.
- **Coverage reaches 100%** in three labelled tiers:
  - 76% ACOLITE default;
  - 12% relaxed mask (as good as tier 1);
  - 12% Sen2Cor fallback (lower authority; poor in murky water).
- **The blind set is still not ready.** Expanding SYKE fills the total and the cool season, but not the US stained,
  sediment and limited counts.

@@ deviations
- **CERT-3 (the extraction budget).** It covers all 687 prescreened cool-season SYKE events and 1,500 seeded warm ones.
  Readiness could not change either way, because the US core carries the per-class check.
- **The QAA-switch clamps a negative spectral slope η to 0** rather than refusing. The pre-registration did not say.
- **O2's feet** are C-lin's continuous prediction (O2 is a class model). The Stage 12 exact-feet rule is applied to
  O2's predicted class.
- **The footprint Δft rule** uses the Stage 12 definition: the median over pairs of each pair's median. The mean over
  pairs is also shown, in the file.
- **"Not materially worse" (coverage)** is judged two ways, and both pass. One compares the union with tier 1 counting
  Unknown as a miss, as registered. The other compares it with tier 1's own rows, which is stricter.
- **No absorbance-at-440 nm results** exist at the corpus sites. The CDOM mechanism uses true colour and DOC/TOC instead.
- **A flaw in one pre-registered rule, disclosed below.** The attenuation verdict tests recall only.

@@ mech_text
- **Particles dominate low visibility.**
  - In stained and limited water, turbidity explains most of what in-situ data can explain: 0.30 of 0.31 held-out R²
    (stained and limited rows among the 509 matched), and 0.28 of 0.36 where DOC exists.
  - Dissolved carbon adds 0.08. True colour, on only 38 stained or limited rows, adds nothing measurable.
  - Across all water, dissolved colour does matter (0.21–0.29 of R²). That is mainly what separates clear lakes from
    coloured ones.
- **The satellite sees the particles, not the colour, in murky water.** Within stained and limited rows, the particle
  features carry 0.19 and green/red 0.09. The blue/green colour feature carries 0.00.
- **Stained water is a resolution problem.**
  - **The class is narrow.** 2–3 ft is a factor of 1.5 (0.176 in log10).
  - **The retrieval is wider.** The best held-out retrieval (C-gbm) has an interquartile error of −0.14 to +0.12.
  - **The arithmetic.** Blur the true values with that error, and even an unbiased estimator recalls stained only 33%,
    normal 51%, limited 76% and clear 86%.
  - **Even perfect knowledge falls short.** Known in-situ turbidity and chlorophyll recall stained only 48%.
  - **So** no satellite feature can be expected to lift stained recall past about 0.4–0.5 while the classes stay this
    narrow.
- **Limited water was a model-form problem.** C3's single red-band form flattens in bright, murky water. The
  multicomponent features (740/665, green/red, brightness) keep the gradient, and limited recall doubles.

@@ models_text
- **Limited water: fixed by the multicomponent models.**
  - Recall is 0.54 (C-lin), 0.57 (C-gbm), 0.64 (O1) and 0.65 (O2), against 0.32 for A. Every gain's CI excludes 0.
  - Precision is 0.57–0.70.
- **Stained water: not fixed.** No model's stained recall gain has a CI above 0. O2 gets closest, at +0.08 (−0.03 to +0.19).
- **Feet: the best in the series.** C-gbm reaches ×1.36 and C-lin ×1.38, against ×1.47 for A. Ordinal κ rises from 0.66
  to 0.75–0.77.
- **No candidate is a SUCCESS.**
  - Criterion 1 (stained recall ≥ 0.45) fails for all.
  - C-gbm passes 2 and 4, and fails 1 and 3.
  - O2 fails all four. Its stained gain's CI includes 0 (criteria 1 and 3), its limited precision is 0.57 against the
    0.60 bar (criterion 2), and it trades normal recall for stained (criterion 4).
- **BEST is O2, by the frozen fallback rule:**
  - the highest balanced accuracy (0.568), beating A by +0.067 with the CI excluding 0;
  - it holds up region-held-out (stained ratio 0.92, limited 0.93);
  - C-gbm is statistically indistinguishable (0.566), keeps normal recall at 0.64, and gives the best feet.
- **The ordinal models do not beat regression-then-threshold.** Their class skill equals C-lin's, except where O2's
  learned cut-points move the 3 ft and 2 ft boundaries to 3.78 and 2.12 ft. That simply buys stained recall with normal
  recall.

@@ switch_text
**RED/NIR TURBIDITY SWITCH USEFUL: NO.**
- **It barely activates.** The red band exceeds the switch threshold (ρ665 > 0.05) at 2.4% of stations.
- **Where it does, it helps nowhere.** Stained error worsens by 12%, limited is unchanged, and sediment worsens by 37%.
  Stained and limited recall do not rise.
- **Red-band saturation is not what limits these waters** in this corpus. They are rarely bright enough.

@@ qaa_text
**DIRECT ATTENUATION MODEL USEFUL: YES by the frozen rule, but not in substance.**
- **The rule was flawed:** it tested stained + limited recall and nothing else.
- **B-pure passes it by calling murky water limited far too often.** Limited recall is 0.71, but precision is 0.26.
- **On every other measure it is worse than A:**
  - stained recall 0.11;
  - balanced accuracy 0.43 against 0.50 (CI excludes 0);
  - exact-feet error ×1.81 against ×1.47.
- **Calibrating it (B-cal) does not help.** Its Secchi estimate barely correlates with the truth once refitted.
- **Why the physics fails.** The inversion took the 740 nm reference on 39% of rows. There, assuming a(740) ≈ a_w
  inflates backscatter and attenuation in turbid inland water.
- **The QAA Kd(492) is still a useful input,** as one of C-gbm's seven features.

@@ cdom_text
**CDOM/ABSORPTION SIGNAL USEFUL: NO.**
- **Removing the blue/green feature lowers nothing.** Stained recall even rises slightly (+0.05 in C-lin, +0.04 in O1),
  and neither change is significant.
- **The feature carries information only between clear and coloured lakes** (0.13 of R² over all rows), not inside
  stained or limited water (0.00).
- **The in-situ data agree:** dissolved carbon is a minor factor in low visibility, next to particles.

@@ coverage_text
**The relaxed masks recover real water.**
- **Variant M3** ignores the negative-reflectance flag (with positive visible medians) and the SWIR non-water flag where
  NDWI > 0.
- **What it recovers.** 191 of the 353 lost stations, whose error is the same as tier 1's (A: 0.173 against 0.169).
  Class skill on those rows is good: balanced accuracy 0.60, stained 0.47 recall.
- **The two flags in the default mask** that dropped good water are the SWIR non-water flag (158 stations) and the
  negative-reflectance flag (32).

**Coverage recovered, with authority stated:**
- tier 1: 76.2% (ACOLITE, default mask);
- tier 2: 12.1% (ACOLITE, relaxed mask; equal authority on this evidence);
- tier 3: 11.7% (C3 on Sen2Cor; **lower authority**);
- **total 100%,** or **88.3% at ACOLITE authority** (just under the 90% bar without the fallback).

**Tier 3 is honest but weak.** On its rows, stained recall is 0.13 and limited 0.11 (balanced 0.36). The fallback should
show a class with a low-confidence marker, not exact feet. The union is not materially worse (balanced accuracy 0.547,
against 0.568 on tier 1's own rows).

@@ footprint_text
**S2A/B/C PLATFORM-INVARIANT AT PRODUCT FOOTPRINT: YES** (for BEST, with bands).
- **O2 never flips class** on identical S2A/S2C 60 m disks once the ±12% boundary bands are applied, over 10 scored pairs
  (Volta and Nasser have no valid disk). The median change is 0.13 ft.
- **Without bands it flips on 3.8%,** against C3's 8.2% (11% per pixel in Stage 12).
- **The cost.** A quarter of corpus predictions fall inside a band. Those would be shown as a boundary state, for
  example "normal-to-stained", not a single class.
- **What changed from Stage 12.** Stage 12's 11% flips were per pixel. At the real footprint, and with a model that uses
  several bands rather than C3's NDCI branch switch, the S2C difference no longer changes the class.

@@ caps_text
- **EXACT-FEET CAPABILITY: 7/10** (5.0 of 7), up from 0/10.
  - The multicomponent feet are good enough (×1.28–1.41 in every class but limited) that the inner folds authorise exact feet for
    almost every predicted class. Feet are shown for 95% of rows.
  - **SUPPORTED:** normal (+0.4 ft), stained (+0.6 ft), algae and sediment.
  - **PARTIAL:**
    - clear, a −2.3 ft median (the ±1.5 ft SUPPORTED bar is missed; deep clear water is still under-read);
    - limited, a median |log| of 0.201 against the 0.20 bar (×1.59).
- **CLARITY-CLASS CAPABILITY: 4/10** (2.5 of 7), up from 1/10.
  - **SUPPORTED:** clear (recall 0.80, precision 0.83) and algae (accuracy 0.55 against a constant 0.37).
  - **PARTIAL:** sediment.
  - **Not met:** normal, stained and limited miss the 0.60 recall/precision bars. O2 lowered normal recall to buy
    stained recall.
- **The two scores diverge because they measure different things.** Feet are judged on typical error, and classes on
  hitting a narrow band. That is the resolution finding again.

@@ cert_text
**BLIND CERTIFICATION SET READY: NO.** The expansion fixed five of the six Stage 12 checks. The sixth is structural.
- **What the full SYKE pool added.** The 3,705 eligible Finnish lakes yielded 2,187 extracted events and 625 new matches.
  The set grows from 289 to **914 observations at 821 lakes** (NLA 165, SYKE 749).
- **Cool-season water now passes:** 19.5% October–April across 163 lakes, against the 15% bar. Every cool-season row is
  Finnish, and most are October. The US core has none.
- **What still fails** is the expected class mix of the US core, the part that represents Sector's water:
  - stained 24 against a minimum of 60;
  - sediment 13 against 20;
  - limited 23 against 25.
- **SYKE cannot fill those counts.** Finnish lakes are humic, rarely turbid, and do not stand in for US reservoirs.
- **To close the gap needs new US data.** One route is a TVA or USACE records request for reservoir Secchi. The other is
  your approval to open the sealed WQP tier, which was downloaded in Stage 1 but never analysed.
- **The set was built value-blind.** It holds ids, dates and scene items only, and no Secchi value was read.
  `blind_sample13.csv` is hashed in the freeze file (sha256 `bcb18659…`, 21:59Z).

@@ gunt_text
- **C-lin and O2 improve Guntersville** (42 historical rows at 10 station groups): ×1.28 and −0.5 ft, against C3's ×1.34
  and −0.7 ft. O2 recalls 4 of the 7 stained rows, against C3's 1.
- **C-gbm does worse there** (×1.43). It may fit national patterns that Guntersville's arms do not follow.
- **This is historical only.** Michael's survey remains the independent acceptance test.

@@ blockers
**Product readiness stays 2/10** (the Stage 10 rule: fresh evidence only).

**What is left:**
1. **The class definition limits stained recall.** 2–3 ft is narrower than any satellite retrieval can resolve, and
   narrower even than in-situ turbidity and chlorophyll can. There are three honest paths:
   - accept a boundary state ("normal-to-stained") as a supported answer;
   - widen or merge the stained class for Sector Intelligence;
   - require a much more precise retrieval, which nothing tested here provides.
2. **Normal recall (0.41–0.64) trades against stained recall.** One cut-point set cannot maximise both.
3. **Tier-3 coverage is weak.** The Sen2Cor fallback misclassifies murky water, so 12% of stations need either another
   ACOLITE recovery path or a class-only low-confidence answer.
4. **Clear water is still under-read by about 2–3 ft** in deep lakes. That blocks clear-feet SUPPORTED.
5. **No blind US certification set exists without new data.** US stained, sediment, limited and cool-season counts need
   either a TVA/USACE records request or your approval of a sealed, never-analysed WQP tier.
6. **Fresh evidence** (P2's fresh data and the certification) is still the only thing that moves readiness.
7. **Bottom-risk** needs a depth layer (the Navionics track).

@@ l1
Resolution, not a missing signal. Stained water (2–3 ft) is a band only a factor of 1.5 wide, narrower than the best retrieval error (×1.36; interquartile −0.14 to +0.12 log), so even an unbiased estimator recalls it only ~33% (perfect in-situ turbidity and chlorophyll reach 48%). Low visibility is mostly particles (in stained and limited water, in-situ turbidity explains 28–30% of the variance, most of what in-situ data explain; DOC 8%; chlorophyll ~0). Limited water was failing because C3's single red-band form flattens in murky water, which the multicomponent features fix.

@@ l2
NO

@@ l3
NO

@@ l4
YES (by the frozen rule only: the QAA-switch model buys limited recall by over-calling limited water, precision 0.26, and is worse than C3 on balanced accuracy and feet)

@@ l5
O2: the linear multicomponent model (red, NDCI, blue/green, green/red, 740/665, brightness) with class cut-points learned on held-out lakes (6.0 / 3.78 / 2.12 ft). It is BEST by the fallback rule, not a pre-registered SUCCESS (stained bars unmet). Balanced accuracy 0.568 against 0.501 for C3; C-gbm is equivalent and keeps normal recall.

@@ l6
0.80 / 0.83 (O2 on all 1,582 rows, tiers 1–3; 0.84 / 0.83 on the 1,206 ACOLITE-valid rows; C3 0.73 / 0.80)

@@ l7
0.42 / 0.44 (0.41 / 0.46 on ACOLITE-valid rows; C3 0.62 / 0.40). O2 buys stained recall with normal recall; C-gbm keeps normal at 0.64 / 0.47

@@ l8
0.37 / 0.34 (0.38 / 0.36 on ACOLITE-valid rows; C3 0.28 / 0.28). The gain is not significant, and it is below the 0.45 / 0.40 bar

@@ l9
0.60 / 0.55 (0.65 / 0.57 on ACOLITE-valid rows; C3 0.28 / 0.77). Recall gain +0.32, CI excludes 0

@@ l10
100% in three tiers: 76.2% ACOLITE default mask + 12.1% ACOLITE relaxed mask (88.3% at ACOLITE authority) + 11.7% Sen2Cor-C3 fallback at lower authority

@@ l11
YES

@@ l12
NO

@@ l13
4/10 (historical; clear and algae SUPPORTED, sediment PARTIAL; normal, stained and limited below the 0.60 bars)

@@ l14
7/10 (historical; normal, stained, algae and sediment SUPPORTED; clear and limited PARTIAL; feet published for 95% of rows)

@@ l15
(1) the stained class (2–3 ft) is narrower than any retrieval's error, and than in-situ turbidity can resolve: it needs a boundary-state answer ("normal-to-stained") or a wider class, not a new signal; (2) normal and stained recall trade off through one set of cut-points; (3) the Sen2Cor fallback (tier 3, 12% of stations) misreads murky water; (4) deep clear water is under-read by about 2.3 ft; (5) the blind US set lacks stained, sediment and limited water (expected 24/13/23 against 60/20/25), which needs TVA/USACE records or your approval of the sealed WQP tier; (6) fresh evidence: readiness stays 2/10 until P2 and certification run; (7) bottom-risk needs depth data
