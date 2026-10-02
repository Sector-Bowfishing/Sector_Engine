@@ answer
**The frozen engine certifies at the level development predicted. That level is not yet good enough to pass.**

- **The engine.** C-gbm, Stage 13's best exact-feet model, frozen as a single continuous engine. One prediction gives
  exact feet, a two-thirds interval (−37% / +51%) and a product state. The boundary bands sit where the odds across
  3 ft and 2 ft fall below 2:1.
- **O2 lost** the pre-registered comparison: it is worse on decision quality by 0.037, CI excludes 0.
- **The blind test.** The sealed WQP tier and the NLA rows give **825 US observations at 675 lakes in 46 states**, never
  used in any fit or selection.
- **Decision quality matched development:** decision-balanced accuracy 0.726 against 0.724, and the interval covered
  65% of truths against a two-thirds target.

| Rubric | Blind certification | Development |
|---|---|---|
| Exact feet | 7/10 | 8/10 |
| Original hard class (kept for comparison) | 4/10 | 5/10 |
| Boundary-aware product | 4/10 | 5/10 |

- **Boundary states rescue stained water as a decision.** True stained water gets a right answer 69% of the time
  (precision 0.74), against 33% hard recall.
- **The certification does not pass** (2.0 of 6 points). Clear feet, stained, limited and sediment are PARTIAL; normal
  and algae are NO.
  - **Normal fails** because a plain "Normal" answer is right only 41% of the time. Most of those errors are clear water
    read low.
  - **Algae fails** because in algal water the engine is no better than always answering the same state.
- **Two failures appear only on independent water:**
  - Sentinel-2C reads 0.19 log low (n 23);
  - cool-season clear water reads 0.15 log low.
- **The clear-water bias is a deep-water tail** (section 5), not a constant or proportional error.
- **Tier 3** is reduced to a lower-authority "Clear", right 78% of the time on certification.
- **Readiness.** Production is unchanged, so readiness stays 2/10 as deployed. The certified candidate would be 4/10 if
  deployed.

@@ cert_class_text
- **How the columns are counted.**
  - Original hard recall counts every row, with Unknown and tier-3 answers as misses.
  - Decision recall and precision count rows answered at ACOLITE authority. The share answered sits beside them.
- **Clear holds up.** Decision recall is 0.81 and precision 0.87; "Clear" answers are right 87% of the time, as in
  development.
- **Stained is the class the boundary states were built for.** 89% of stained water is answered, and 69% of those
  answers include stained. Only 43% of them are a single class, because the retrieval cannot resolve 2–3 ft.
- **Limited is right 88% of the time when named,** but its recall (0.73) is just under the 0.75 bar.
- **Normal is the weak class.** Its decision precision is 0.56. Of 127 plain "Normal" answers, 52 were actually clear
  and 23 stained or limited.
- **Feet are good where the water is not very clear:** ×1.28–1.48, with median signed −0.0 to +0.6 ft for normal,
  stained and limited. Clear reads −2.3 ft.

@@ cert_text
**BLIND CERTIFICATION PASSED: NO.** Every class met its minimum, so every verdict is a real one, not INSUFFICIENT:

| Class | n | Minimum |
|---|---:|---:|
| Clear | 393 | 40 |
| Normal | 177 | 40 |
| Stained | 99 | 60 |
| Algal | 124 | 30 |
| Sediment | 38 | 20 |
| Limited | 156 | 25 |

**The six lines:**
- **CLEAR FEET: PARTIAL.** The median is −2.3 ft against the ±1.5 ft SUPPORTED bar. On certification the tail is the
  same shape as in development:
  - 6–13 ft reads about −1 ft;
  - 13–20 ft reads −3.9 ft;
  - ≥ 20 ft reads −9.3 ft.
- **NORMAL: NO.** Decision recall 0.66, precision 0.56 (the PARTIAL bar is 0.60).
- **STAINED: PARTIAL.** 0.69 / 0.74. Recall is short of the 0.75 SUPPORTED bar.
- **LIMITED: PARTIAL.** 0.73 / 0.88.
- **ALGAL: NO.** In algal water, decision accuracy is 0.72. Always answering one fixed state would score 0.74, because
  algal water here is mostly stained or limited.
- **SEDIMENT: PARTIAL.** No bright sediment (turbidity ≥ 20, n 18) was called Clear, but accuracy is 0.85 against a
  constant 0.88.

**Tier 3 on certification.** 116 US rows reached tier 3:
- "Clear" was issued 59 times and was right 78% of the time (0.89 in development), still above the 0.75 bar. Its feet:
  ×1.52, +1.3 ft.
- The other 57 rows became Unknown / Low Authority.
- The tier-3 rows were 58% clear water, so the precision-first rule cost little.

**Coverage.**
- 73% tier 1, 13% tier 2, 14% tier 3.
- 24 of 1,574 scored rows had no ACOLITE result (no L1C, or ACOLITE produced no L2W); they fell to tier 3 as designed.
- Feet were published for 93% of US rows.

@@ breakdown_text
**What holds:**
- **NLA and WQP agree:** decision-balanced 0.77 and 0.72.
- **Independence does not change the result.** The strict-independence subset (lakes with no Stage 1–4 site within
  5 km) scores 0.71 against 0.73 for the rest.
- **The two-thirds interval** covers 61–73% of truths in every region.
- **Sentinel-2A and 2B agree:** 0.72 and 0.74.

**What breaks:**
- **Sentinel-2C.** 33 rows, only 23 of them at ACOLITE authority, all from 2025. They read 0.19 log low (×0.65); clear
  water reads 0.23 log low, and interval coverage is 30%.
  - Stage 13 found the class invariant on the 12 tandem pairs. That held on identical water, but not on these independent
    S2C scenes.
  - The sample is small and partly cool-season, so this is a warning rather than a measurement. It is a new failure.
- **Cool-season clear water.** It reads 0.15 log low, and only 55% of it is called Clear (warm season: 86%).
- **Tier-2 limited water.** The relaxed mask recovers rows, but limited decision recall there is 0.45.

@@ syke_text
**SYKE is out of domain and stays out:** humic Finnish lakes score decision-balanced 0.59 and product 1/10. Clear water
reads −2.7 ft there. That fits the cool-season and dissolved-colour findings. It does not count toward any verdict.

@@ readiness_text
**CURRENT CLARITY PRODUCT READINESS: 2/10 as deployed.**
- **Why it doesn't move.** The Stage 10 rule scores the product as it runs, and production was not changed.
- **The candidate, as if deployed: 4/10.** It is scored on the blind certification with the boundary-aware product
  rubric:
  - clear SUPPORTED;
  - stained, limited and sediment PARTIAL;
  - normal, algae and bottom-risk NOT.
- **Against production.** Production was not run on the certification set, so there is no head-to-head certified
  comparison. The nearest comparison: Stage 12 measured production on development data at ×1.97 and −5.2 ft in clear
  water, against the candidate's certified ×1.39 and −2.3 ft.
- **What it would take.** Shipping it is a product decision, and readiness moves only with deployment.

@@ remaining
1. **Michael's ship decision.** The candidate (4/10 certified) against production (2/10). Ship it shadowed in the
   engine first; production stays unchanged until then.
2. **Clear water read low.** It drives both CLEAR FEET PARTIAL and NORMAL NO: 52 of 127 "Normal" answers were clear
   water. This needs a product rule, not a new model. Examples:
   - a "Clear-to-Normal" boundary state, which the specification does not have yet;
   - showing exact feet above about 12 ft as a floor ("12+ ft").
3. **Sentinel-2C on independent water.** S2C reads 0.19 log low (n 23). It needs more S2C tandem pairs and S2C
   certification rows before S2C answers can be trusted. Until then they could be marked lower authority. This is a new
   failure, so it is a legitimate reason to reopen harmonisation.
4. **Cool-season clear water** (−0.15 log), and **algal water**, where the engine is no better than a constant answer:
   the algae state or warning needs its own semantics.
5. **Fresh evidence:** Michael's Guntersville survey as the acceptance test, and P2. Under the Stage 10 rule, only these
   move readiness past the certified level.
6. **Bottom-risk** needs a depth layer.

@@ l1
C-gbm single continuous engine (the Stage 13 seven-feature constrained boosting, fitted once on 1,206 development rows) on ACOLITE K4 with lake-elevation pressure, S2C V-ρw and the 60 m disk. Tier 2 is the M3 relaxed mask. Tier 3 is Sen2Cor-C3, Clear only. Boundary states come from frozen 2:1-odds bands: Normal-to-Stained 2.63–3.80 ft, Stained-to-Limited 1.70–2.38 ft. Exact feet are shown for every class with a two-thirds interval (−37% / +51%).

@@ l2
8/10 (development, lake-held-out); 7/10 on blind certification

@@ l3
5/10 (development); 4/10 on blind certification (kept for comparison, not declared passed)

@@ l4
5/10 historical (clear SUPPORTED; normal, stained, limited, algae and sediment PARTIAL); 4/10 on blind certification

@@ l5
825 scored US-core observations at 675 lakes in 46 states (NLA 155, sealed WQP tier 670; 19.9% October–April), plus 749 SYKE (Finland) reported apart. 1,574 of 1,585 drawn observations were scored

@@ l6
NO (2.0 of 6 points: clear feet, stained, limited and sediment PARTIAL; normal and algae NO)

@@ l7
PARTIAL (×1.39, median −2.3 ft; about −1 ft at 6–13 ft, −3.9 ft at 13–20 ft, −9.3 ft at 20 ft or more)

@@ l8
NO (decision recall 0.66, precision 0.56; a plain "Normal" answer is right 41% of the time, mostly because clear water is read low)

@@ l9
PARTIAL (decision recall 0.69, precision 0.74, against 0.33 hard recall)

@@ l10
PARTIAL (decision recall 0.73, precision 0.88)

@@ l11
NO (decision accuracy 0.72 in algal water, against 0.74 for the best constant answer)

@@ l12
PARTIAL (no bright sediment called Clear; decision accuracy 0.85 against a constant 0.88)

@@ l13
Clear only, at lower authority with lower-confidence feet, when Sen2Cor-C3 reads ≥ 6 ft (precision 0.89 in development, 0.78 on certification, n 59). Every other tier-3 reading is Unknown / Low Authority

@@ l14
2/10 as deployed (production unchanged); the certified candidate would score 4/10 if deployed

@@ l15
(1) Michael's decision whether to ship the certified candidate, shadowed first; (2) a product rule for clear water read low in deep and cool-season water, which drives both CLEAR FEET PARTIAL and NORMAL NO; (3) Sentinel-2C on independent water reads 0.19 log low (n 23), which needs more S2C tandem and certification data; (4) algal-water semantics, since the engine is no better than a constant answer there; (5) fresh evidence: the Guntersville survey acceptance test and P2; (6) bottom-risk needs depth
