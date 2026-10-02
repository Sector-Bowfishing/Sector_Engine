@@ answer
**The new reflectance improves the clarity estimate wherever it can read the water. It reads only three stations in
four, and it does not fix the red band.**
- **The configuration.** ACOLITE with the FFSS sky-dome interface correction (K4), surface pressure from each lake's
  elevation, and S2C harmonised at the water-reflectance level.
- **The gain.** C3 refitted on this reflectance is the best model, and no simpler one is equivalent: held-out error **×1.47**,
  against **×1.66** for today's production on the same 1,206 rows at 792 lakes.
  - **The reflectance itself buys most of it.** The same C3 on Sen2Cor scores ×1.58 on those rows (difference −0.031,
    CI −0.045 to −0.016).
  - **Clear water is where it shows:** ×1.56 against ×1.97, and a median error of −3.3 ft against −5.2 ft for production.
    Routing adds nothing (0.8%).
- **What it does not fix:**
  - **Coverage.** ACOLITE gives a valid disk at only **76%** of stations. Sen2Cor has one at all of them.
  - **The red band.** No interface option cut the red bias enough (K4 +0.22 against +0.25). The two that cut it to +0.15
    lost too many retrievals.
  - **Turbidity.** It is not better overall: better in clear water, worse in murky water.
  - **Sentinel-2C.** It is only partly harmonised, and the engine's class still flips on 11% of identical S2A/S2C pixels.
- **Capability, historical and strict:**
  - exact feet **0/10**;
  - clarity class **1/10** (clear and sediment PARTIAL).
  - **Stained and limited water are the weakest classes on every input tested** (recall 0.2–0.3).
- **The blind certification set** was built without reading a single Secchi value: 289 observations, 272 lakes, 39
  states. It is **not ready**: short of 400 observations, of stained, sediment and limited water, and of the cool season.

@@ corpus_line
**1,631 station-days** (1,015 lakes) through the new reflectance: 1,343 L1C scenes and 1,504 crops, of which 1,478 ran and 100 used the angle-grid fallback. Guntersville is kept apart (45 rows).

@@ p3_text
**Retrieval rate (R1).**

{{T:p3_r1}}

- **ACOLITE loses a quarter of the stations, evenly across classes.** Of the 379 stations without a valid disk:
  - **289** have every disk pixel flagged by ACOLITE's water mask;
  - **64** keep fewer than 5 valid pixels;
  - **24** crops produced no output, because the aerosol fit failed;
  - **2** scenes have no L1C.
- **Which flag.** The flag type was not recorded per station. At the one station inspected it was the
  negative-reflectance flag.
- **Sen2Cor production answers everywhere,** because every corpus row was selected on a valid Sen2Cor read.
- **Unknown in Part 5 is these stations.**

**Turbidity from each path's red band (R2)**, as median |e_T| (bias), with the paired difference:

{{T:p3_r2}}

- **Reflectance improved: NO by the frozen rule.** On same-day rows ACOLITE is +0.013 (CI includes 0); within ±1 day it
  is worse, +0.041 (CI excludes 0).
- **The pattern matters more than the total:**
  - **Clear water:** ACOLITE removes most of Sen2Cor's over-read (bias +0.18 against +0.38; error 0.26 against 0.39).
  - **Stained, limited, algal and mixed water:** ACOLITE reads turbidity lower than Sen2Cor (bias −0.21 to −0.33).
  - **Why this matters:** Sen2Cor's extra brightness was partly cancelling the turbid-water under-read that every
    processor shares.
- **Across the corpus ACOLITE's water reflectance is 17–33% darker than Sen2Cor's.** Blue is ×0.67, green ×0.83, red
  ×0.70 and 704 nm ×0.76. That fits Sen2Cor's AERONET-OC over-read.

**The Part A split (R3), through the frozen champion:**

{{T:p3_r3}}

The frozen champion was fitted on Sen2Cor, so on ACOLITE it is worse (0.219 against 0.177). That is why Part 4 refits
every empirical form.

**By platform (R4):**

{{T:p3_r4}}

@@ p4_text
**All candidates, held out by whole lakes** (1,206 rows at 792 lakes with a valid ACOLITE disk, Guntersville excluded):

{{T:p4_models}}

**Equivalence to the best, C3** (the lake-bootstrap CI's upper bound must be ≤ +0.010):

{{T:p4_equiv}}

**Routing**, judged against the engine:

{{T:p4_routing}}

**The engine is C3, refitted on ACOLITE reflectance: one model, no routing.**
- **It is the best model,** and no simpler model is statistically equivalent. N2 comes closest, at +0.0095 with an upper
  bound of +0.024.
- **It passes the C3 guard in algal water:** 0.189, against 0.184 for N2, the best other model there (the bar is +0.01).
  So C3 is not an unconditional algal fallback.
- **Routing gains 0.8%** (CI includes 0), well short of the 10% bar, so the improved input does not need a router.
- **P1 and P2 score well on the rows they answer,** but answer only 75–76% of them, below the 90% needed for a single
  engine.

**Where the gain comes from** (exploratory, not pre-registered):

{{T:p4_attrib}}

On identical rows and folds, the reflectance change alone lowers C3's error by 0.031 log (16%).

**Per class, held out, against production on the same rows:**

{{T:p4_perclass}}

- **Better** in clear water (×1.56 against ×1.97; the under-read shrinks from −5.2 to −3.3 ft), limited, algal and mixed
  water.
- **About the same** in normal and stained water.
- **Worse in sediment water** (×1.37 against ×1.27), consistent with ACOLITE's darker red.
- **Guntersville** (42 historical agency rows at 10 station groups, never used for selection): ×1.34 against ×1.72. This
  is historical only. Michael's survey remains the acceptance test.

**Platform** (condition b, held-out signed error of one platform minus the others):

{{T:p4_platform}}

S2C reads 0.10 log low, but on 31 rows the CI includes 0, so condition (b) passes.

**Condition (a) fails.** On identical tandem water, the engine's class flips on 11.2% of pixels (bar 5%). The median
change is only 0.16 ft:

{{T:p2_engine}}

- **Harmonisation barely moves the class flips** (12.1% raw).
- **They most likely come from pixel-level scatter near the class boundaries** and near C3's NDCI = 0 branch switch,
  not from the S2C band bias, since harmonisation leaves them almost unchanged.
- **The tandem test is per pixel at 20 m,** while production reads a 60 m disk of about 28 pixels. So this flip rate probably
  overstates what a user would see. That was not tested, and the frozen rule still applies.

**S2A/B/C PLATFORM-INVARIANT ENOUGH FOR CLARITY: NO.**

@@ p5_text
**What a user would get**, with exact feet shown only for classes the inner folds authorise:

{{T:p5_shares}}

- **Which classes get feet.** The inner folds authorised limited water in every fold and stained water in three.
  Normal was authorised once, and clear never; clear's predicted rows miss the ×1.41 and ±1.5 ft bars.
- **So most answers are a class, not a number:** 61% of rows get only a class, and 24% are Unknown.

**The two historical capability scores** (lake-held-out, Stage 10 bars; **not product readiness**):

{{T:p5_caps}}

- **EXACT-FEET CAPABILITY: 0/10.**
  - Feet are published too rarely: under 50% coverage in every class.
  - Where they are published for true clear water, it is because the model called it stained or limited. Those answers
    are badly wrong (−4.4 ft).
- **CLARITY-CLASS CAPABILITY: 1/10.**
  - **Clear is PARTIAL.** Precision is 0.80, but recall is 0.58 once the 23% Unknown counts as a miss. On retrieved
    rows alone it is 0.75.
  - **Sediment is PARTIAL:** no bright-sediment station is called clear.
  - **Stained and limited fail on recall** (0.23 and 0.24).

**The same rubric on other inputs** (exploratory; answered rows, and Unknown where noted):

{{T:p5_explore}}

- **Coverage is one limit.** With a disk at every station, C3 on ACOLITE would clear the clear-class SUPPORTED bar
  (recall 0.75, precision 0.80).
- **Stained and limited water are the real capability gap.** They sit at recall 0.17–0.32 on every input, whether
  Sen2Cor or ACOLITE, champion or C3.

@@ p6_text
**The protocol** was written and hashed before any site or visit file was fetched (`cert/CERT_PROTOCOL_STAGE12.md`,
15:04:45Z).
- **Sources:**
  - **US core:** EPA National Lakes Assessment 2022 and 2017, from EPA's own files. Neither is in the 2018–2026 WQP pull
    used for development.
  - **Cool-season stress test:** Finland's SYKE Vesla open data.
- **Eligibility and matching:**
  - lakes within 5 km of any development station are excluded, as is Guntersville;
  - NLA visits duplicated in the WQP pull are dropped;
  - each visit needs a production-gated Sentinel-2 pass within ±1 day;
  - at most 3 observations per lake;
  - every date is ≤ 2025-12-31, so the set is disjoint from P2's fresh holdout.
- **Blindness.**
  - Only site, visit and event-key tables were fetched.
  - No NLA Secchi file was downloaded.
  - SYKE queries never selected the value field.
  - `cert/blind_sample.csv` (sha256 `111cff44…`) lists IDs, dates and satellite items only.

**Blind checks:**

{{T:p6_checks}}

**BLIND EXTERNAL CERTIFICATION SET READY WITHOUT USER SURVEY: NO.**
- **What passes:** geography and lake count. There are 272 lakes in 39 states plus Finland, with no state above 10%.
- **What fails:**
  - **Total:** 289 matched observations against the 400 bar.
  - **Match rate.** Only 11% of NLA visits have a clear pass within a day that survives the production gates, and 2017 is
    thin before Sentinel-2B.
  - **Cool season:** 4% (NLA samples only in summer, and Finnish October and November are cloudy).
  - **Expected stained, sediment and limited counts.**
- **What would complete it,** in order of independence:
  - SYKE extended from 400 lakes to all 3,705 with eligible events (cool season and humic stained water, but out of
    domain);
  - a request to TVA or USACE districts for their cool-season reservoir records;
  - a pre-registered, sealed tier of WQP records that were downloaded in Stage 1 but never analysed. That is your call,
    because those values already sit on this Mac.

@@ path
**Product readiness stays 2/10.** Under the Stage 10 rule only fresh evidence moves a capability.

| Step | The Stage 12 finding it rests on | What it would move |
|---|---|---|
| 1. Recover the 24% of lost retrievals | ACOLITE gives a valid disk at 76% of stations. Its water mask flags whole disks at 289 stations and most of the disk at 64 more, and the aerosol fit fails on 24 crops | Clear to SUPPORTED on the class rubric. On retrieved rows its recall is already 0.75 |
| 2. Give the class decision an uncertainty band at the 3 and 6 ft boundaries, and re-test S2A/S2C on disk-averaged pixels | 11% of pixels flip class on identical water, with a median change of only 0.16 ft | Platform invariance |
| 3. Find a signal for stained and limited water | Recall 0.17–0.32 on every input and model; routing and refits do not help | Stained and limited, the capabilities that separate 4/10 from 9/10 |
| 4. Complete the blind set | 289 observations; stained, sediment, limited and cool season short | Certification without anyone surveying |
| 5. Certify once, on the blind set and on P2's fresh data | The Stage 10 bars, unchanged | Readiness |

- **Step 1 options, to pre-register:** ACOLITE mask variants, or a hybrid. The hybrid uses ACOLITE where it reads the
  water, and C3 on Sen2Cor elsewhere, flagged as lower authority. C3 on Sen2Cor is ×1.58 against production's ×1.68 on
  every row.
- **What 9/10 needs:** clear, normal, stained, algae, sediment and limited all SUPPORTED on fresh data. Bottom-risk stays
  NOT until a depth layer exists (the Navionics track).

@@ l1
ACOLITE 20260421.0 (DSF, residual-glint correction, the FFSS sky-dome interface correction after AC; candidate K4) with surface pressure from each lake's USGS elevation, 20 m, and Sentinel-2C harmonised at the water-reflectance level (V-ρw)

@@ l2
NO

@@ l3
PARTIAL

@@ l4
NO

@@ l5
C3 refitted on ACOLITE reflectance (two red-band branches split on NDCI > 0), a single model with no routing: held-out ×1.47 (median |log| 0.169) against ×1.66 for today's production on the same rows, but only at the 76% of stations where ACOLITE retrieves water

@@ l6
×1.56 (median |log| 0.192), median −3.3 ft, class accuracy 0.75 (n 574; production ×1.97, −5.2 ft)

@@ l7
×1.27 (0.104), median +0.3 ft, class accuracy 0.64 (n 286; production ×1.31, +0.2 ft)

@@ l8
×1.38 (0.140), median +0.9 ft, class accuracy 0.29 (n 173; production ×1.40, +0.9 ft)

@@ l9
×1.81 (0.257), median +1.0 ft, class accuracy 0.32 (n 173; production ×1.98, +1.3 ft)

@@ l10
×1.51 (0.178), median +1.0 ft (n 94, in-situ algal; production ×1.57, +1.2 ft)

@@ l11
×1.37 (0.136), median +0.6 ft (n 64, in-situ sediment; production ×1.27, −0.0 ft, so worse than production)

@@ l12
0/10 (historical lake-held-out; feet are authorised for 15% of rows, and no class reaches 50% published coverage)

@@ l13
1/10 (historical; clear and sediment PARTIAL; 24% Unknown; stained and limited recall 0.23–0.24)

@@ l14
NO

@@ l15
Readiness stays 2/10. First recover ACOLITE's 24% lost retrievals (pre-registered mask variants or a Sen2Cor-C3 fallback). Add a class-boundary uncertainty band so S2A/S2C scatter stops flipping classes. Find a signal for stained and limited water, the weakest classes on every input. Complete the blind set (≥ 400 observations, stained and cool-season water) from SYKE's full lake list plus agency records or a sealed never-analysed WQP tier. Then certify once, on that set and on P2's fresh data, against the Stage 10 bars.
