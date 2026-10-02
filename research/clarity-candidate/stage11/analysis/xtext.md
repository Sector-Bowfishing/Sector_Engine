@@ answer
**Most of the remaining error comes from the satellite's reflectance, not the Secchi conversion.**
- **The radiometric term is 63% of the champion's error variance** (CI 54–71%).
- **Most of that is unexplained.** Aerosol, glint, adjacency, platform and water type together explain only a fifth of it. The unexplained remainder alone is 50% of all the variance. The unexplained conversion term is next, at 36%.
- **Measured water reflectance shows what the rest is.** Against AERONET-OC, Sen2Cor reads inland and coastal water too bright in every band tested: red ×1.9, blue ×2.2. A fixed brightening matters most in dark water, which fits the clear-water over-read.

**The other five questions:**
- **Atmospheric correction: ACOLITE, by the frozen rule.**
  - It is 25% closer to AERONET-OC than Sen2Cor (CI excludes 0) and no worse on in-situ turbidity.
  - C2RCC and C2X are closer still to AERONET-OC (55% and 50%), but they read inland turbidity 3–5× too low, so they fail the second test.
  - On the champion's own band (red), ACOLITE's gain is small: a bias of +0.25 against +0.28.
- **Sentinel-2C needs harmonisation: YES.**
  - A B05 band-shape shift and a B8A–B12 dark-water offset are present at top of atmosphere, 30 s after 2A.
  - They flip 15.5% of P2's routes on identical water. The red-band champion is unaffected.
- **Routing by water type: NO.**
  - The satellite classifier works (balanced accuracy 0.56), and a pattern exists: C3 for clear water, P1 for algal and mixed.
  - But routing gains only 7.4% over the best single model, below the 10% bar. C3 is never chosen for algal water.
- **A second sensor: NO.**
  - When Landsat agrees with Sentinel-2 the error is 24% lower, but the bar was 25% and the CI touches 0.
  - Fusing the two gains 7%, below the 10% bar.
  - OLCI reaches only 119 offshore stations, too few for the test.
- **Temporal consistency: NOT USEFUL.**
  - Flagged passes are 1.6× worse.
  - But replacing them with their neighbours' median helps only 7% (bar 20%).

@@ aoc_n
**46 Sentinel-2 overpasses** (Erie 10, Okeechobee 10, Palgrunden 10, Chesapeake 9, WaveCIS 7), each within ±60 min of a Level 2.0 record

@@ ls_n
375 station-days in 301 lakes with a valid read within ±1 day

@@ olci_n
119 of the 241 station-days at least 600 m from shore, in 98 lakes, with a valid read within ±1 day

@@ additive
**An exploratory check** (not pre-registered; no verdict uses it). Is the clear-water over-read an additive offset? Subtracting each pixel's own B11 from B04 before the turbidity step gives this:
- **The clear-water bias disappears.** The turbidity bias goes from +0.34 to −0.06 and the Secchi bias from −0.25 to +0.03.
- **The clear-water error barely moves** (0.256 to 0.248).
- **Every murkier class gets worse.** For example, normal water goes from 0.10 to 0.20.

So the clear-water over-read behaves like an offset about B11's size (0.006 in reflectance), but B11 cannot estimate that offset pixel by pixel. That matches what Part B measures directly: Sen2Cor leaves inland water too bright.

@@ b_aeronet_text
**What the measured reflectance shows:**
- **Sen2Cor reads water too bright in every band tested.** The median bias is +0.34 in blue, +0.20 in green, +0.28 in red and +0.29 at 704 nm (×2.2, ×1.6, ×1.9 and ×1.9).
  - Dark water is where a fixed additive error matters most, which is exactly where Part A finds the clear-water over-read.
  - Sen2Cor is a land correction. It does not remove sky light reflected at the water surface, and it leaves 0.0038 in B11, where water is black.
- **ACOLITE removes part of it.** Its B11 falls to 0, and its 704 nm band improves most (bias +0.11 against +0.29).
  - But its red band stays nearly as bright (+0.25), and red is the only band the champion reads.
  - It ran with ACOLITE's default of not modelling reflection at the air–water interface (`dsf_interface_reflectance=False`). That is a plausible cause of the remaining offset, and the first thing to test next.
- **C2RCC and C2X come closest overall** (0.125 and 0.139, against 0.280 for Sen2Cor), and C2RCC's red band is almost unbiased (+0.04). Their valid rate is 98%.
  - C2RCC reads 704 nm too dark (−0.19).
  - It is worst at Lake Okeechobee, the most turbid lake site (0.30).
- **By site:** ACOLITE is best at Okeechobee (0.05) and C2RCC at Erie (0.07). No processor is best everywhere.
- **Criterion (a) (≥ 20% better than Sen2Cor, CI excluding 0) is met by all three:**
  - ACOLITE, 25%;
  - C2X, 50%;
  - C2RCC, 55%.
- **Plausibility:** no processor returns a non-positive ρw in B02–B05 at these sites.

@@ b_repr_text
**Criterion (b), in-situ turbidity, decides it:**
- **ACOLITE is not worse than Sen2Cor.** Its median |e_T| is 0.375 against 0.425 on the 18 stations both answer.
  - It is closer on only 7 of the 18, so the margin is thin.
  - Downstream it also edges Sen2Cor: the champion's formula 0.245 against 0.269, and P1 0.098 against 0.110 (16 answers each).
- **C2RCC and C2X are worse**, at 0.684 and 0.500 against 0.445 on 20 stations.
  - Both read turbidity too low in every class, clear water included (medians ×4.8 and ×3.2 too low).
  - Their neural networks, closest to AERONET-OC at moderate turbidity, read inland red reflectance too dark. The AERONET-OC scatter shows the same thing above ρw ≈ 0.02.
- **Every processor under-reads these murky scenes.** Sen2Cor's median e_T is −0.33, as is ACOLITE's. Only 15 scenes and 20 stations back this test.

**Best path by the frozen rule: ACOLITE.** It is the only processor that meets both (a) and (b). C2RCC and C2X meet (a) by a wider margin but fail (b).

@@ f_text
**Multi-sensor fusion worth pursuing: NO by the frozen rule.**
- **Landsat: a narrow miss on both tests.**
  - When the two sensors agree, the error is 24.1% lower. The bar was 25%, and the CI's upper end sits at 0.000, so it does not exclude 0.
  - The S2+Landsat mean lowers the error by 7.3% (bar 10%), and its CI includes 0.
  - Against in-situ turbidity the fused value is worse than Sentinel-2 alone (0.204 against 0.193), so the fused Secchi gain is not a better turbidity.
  - Landsat on its own is worse than Sentinel-2 (0.205 against 0.191).
- **OLCI: too few stations to test.**
  - Only 119 station-days are far enough from shore for its 300 m pixels, and only 23 of those agree with Sentinel-2. Test (i) needs 30 on each side.
  - One exploratory hint: OLCI's neural-network suspended matter ranks in-situ turbidity better than Sentinel-2's FNU (rank correlation 0.82 against 0.68, n 58). It needs open water, so it cannot serve the bank-side stations bowfishers fish.
- **What it means:** agreement between sensors is a weak confidence signal, not a correction. It is not worth building ahead of the atmospheric-correction work.

@@ g_text
**Temporal consistency: NOT USEFUL by the frozen rule.**
- **The screen finds bad passes.** 10.8% of rows are outliers against their neighbours, and they are 1.6× worse (bar 1.5×).
- **It cannot fix them.** Replacing a flagged value with its neighbours' median helps only 7% (bar 20%). The neighbours mostly share the same error, which suggests a station-level bias that persists from pass to pass rather than pass noise.
- **Refusing flagged passes instead** (exploratory) lowers the overall error by 6% while keeping 89% of rows. That is too small to justify a gate on its own.
- **An early read on half the data looked useful** (37 flagged rows, a 24% reduction). The full data does not bear it out, and the verdict uses the full data.

@@ c2rcc_crash
About half the scenes first crashed SNAP in native code. The crash is in the NetCDF4-CF writer: libnetcdf segfaults while it writes the product's metadata groups (`nc_def_grp`), and whether it happens depends on the scene. Switching glibc off its AVX code paths moved the crash but did not stop it. Every crashed scene was rerun with SNAP's NetCDF4-BEAM writer, which stores the same bands. On a scene that runs under both writers, every sampled value is bit-identical. So these crashes are tooling failures and are not counted against C2RCC's valid-retrieval rate.

@@ path
**What Stage 11 changes about what to build**, in order:

| Step | The Stage 11 finding it rests on | Capabilities it serves | The evidence that would move the score |
|---|---|---|---|
| 1. Score P2's fresh validation exactly as frozen | Nothing here changes P2 | Clear and stained first. Historically P2 already clears the clear-channel PARTIAL bar | The Stage 10 fresh bars, unchanged |
| 2. Harmonise Sentinel-2C before anything that reads B05 or B11 ships | Part C: a B05 band-shape shift and a B8A–B12 dark-water offset at top of atmosphere; 15.5% of P2's routes flip on identical water | Algae (NDCI, P1), and clear and stained through P2's residual test | A correction frozen from the tandem, then route flips on the tandem water below 5% |
| 3. Move the reflectance to ACOLITE, testing its interface-reflectance term first | Part A: the unexplained radiometric term is the largest source (50%). Part B: ACOLITE passes both tests, but its red band is still +0.25 too bright | Clear first, where the error is almost all radiometric; then stained and limited | A pre-registered, lake-held-out rerun of the whole corpus (1,343 scenes) on ACOLITE reflectance, then the same fresh bars |
| 4. One model, not routing, and never C3 in algal water | Part E: routing gains 7.4% (bar 10%), and P1 beats C3 in algal water in every fold | Algae | The algae SUPPORTED bar: PPV ≥ 0.40 and \|median signed\| ≤ 1.0 in algal water |
| 5. Collect the fresh Secchi-grade data | The Stage 10 per-class minima | All six water capabilities | At least 215 fresh observations across warm and cool seasons: clear 40, normal 40, stained 60 in 6 arms, algae 30, sediment 20, limited 25 |

**What 9/10 means under the rubric.** Clear, normal, stained, algae, sediment and badly limited must all reach SUPPORTED on fresh data: 6.0 of 7, which rounds to 9. Bottom-risk stays NOT until a depth layer exists (the pending Navionics track).

**What Stage 11 rules out as near-term levers:**
- C2RCC and C2X for inland turbidity;
- routing by optical water type;
- P1-NIR;
- a second sensor (Landsat or OLCI);
- a temporal-consistency screen;
- the public-depth correction (frozen in Depth Stage 2).

**Cost.** Step 3 needs ACOLITE on 1,343 L1C scenes, roughly 70–90 hours on this Mac or a few hours as a cloud batch job. A cloud job would be a new cloud resource, so it waits for your go-ahead.

@@ line1
Radiometric: the satellite's water reflectance, not the Secchi conversion. 50% of the champion's error variance is retrieval error that aerosol, glint, adjacency, platform and water type do not explain (the conversion residual is next at 36%), and against AERONET-OC Sen2Cor reads water too bright (red ×1.9).

@@ line2
ACOLITE (DSF with residual-glint correction): 25% closer to AERONET-OC than Sen2Cor (CI excludes 0) and not worse on in-situ turbidity. C2RCC and C2X are closer to AERONET-OC (55% and 50%) but read inland turbidity 3–5× too low, so they fail.

@@ line5
NO

@@ line6
Readiness stays 2/10 until fresh evidence exists. Score P2's fresh validation as frozen; harmonise Sentinel-2C; re-freeze the retrieval on ACOLITE reflectance (testing its interface-reflectance term first) with a lake-held-out rerun of all 1,343 scenes; then earn the Stage 10 fresh bars class by class (clear, stained and limited to PARTIAL for 4/10; all six water classes to SUPPORTED for 9/10), which takes at least 215 fresh Secchi-grade observations across warm and cool seasons.
