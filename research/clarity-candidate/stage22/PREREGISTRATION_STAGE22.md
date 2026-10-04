# Stage 22 pre-registration — S2C seasonal stability and a sensor-invariant ACOLITE path

Written and frozen before any Stage 22 reflectance, pair outcome or Secchi value is read. `FREEZE_STAGE22.json` holds this file's SHA-256. Candidate definitions made later from derivation data are frozen as `cand22.json`, and their hash is added before any held-out result is read.

**Already known when writing:**
- Every Stage 16–21 result.
- The Stage 22 pair metadata (`pairs22_meta.json`: dates, orbits, cloud, geometry).
- Two tooling checks on one Stage 21 held-out tile, MGRS-10TET 2024-12-15. They reproduced Stage 21's S2A, K0 and K1 values exactly (max |difference| 0.0) and returned its instrumentation fields.
- A synthetic S2A test showing that removing 0.003 of SWIR signal removes the residual-glint subtraction and leaves the aerosol fit unchanged.

## 1. Unchanged and preserved

**Not changed:**
- the C-gbm (not refit);
- the Stage 16 gate;
- the Stage 19 consensus code;
- the frozen ACOLITE K4 path;
- the Stage 20/21 authority-lift bars (never lowered);
- the Stage 16 freeze bars and the true 9/10 targets.

No field reports are used, and no correction is fitted to Secchi.

**Preserved:** Stages 16–21 are kept as they are. Stage 21 K0, K1, K2 and Stage 12 (B) remain named references.

**Instrumentation.** ACOLITE's `acolite_l2r` is loaded with three *recording* lines: the per-tile DSF band order and per-band AOT for each model, the per-tile model, and the selected model. The output-only switches `glint_write_rhog_ref` and `glint_write_rhog_all` are on. Neither changes the computation (verified: identical L2W samples).

**Remote reads.** S2C real-nominal imagery for the winter tandem is read by **windowed requester-pays reads** (lazy SAFE, `/vsis3/`). Bytes are logged in `stage21/aws_bytes.log` under the 95 GB cap. If more data would exceed the cap, the stage stops and reports the amount needed.

## 2. Data, seasons and timing

**Seasons:**
- **winter** = the 29 Oct – 18 Dec 2024 tandem;
- **warm** = 15 Apr – 15 Oct.

| Set | What | Role |
|---|---|---|
| **TD / TH** | Stage 21 real-nominal tandem, Stage 21 split by datatake. S2A from Google Cloud, S2C lazy from AWS. ~30 s apart. | TD derivation; TH held out (winter) |
| **S** | Warm same-day S2C ↔ S2A/B, same UTC date, \|Δt\| ≤ 180 min, both ≤ 20% cloud, restricted to the open-water window 15 Jul – 15 Sep | Held out |
| **T2** | Warm same-track 2-day S2C → S2A: same relative orbit and tile, 48 ± 1 h, both ≤ 20% cloud. 80 pairs per year (2025, 2026), sites in md5("stage22\|site\|year") order. | Split by S2C datatake (lib20.split rule, salt "stage22"): T2D derivation / T2H held out. **Secondary: not "same water".** |
| **FLOOR** | Same-day S2A ↔ S2B at the high-latitude lakes, Jun–Sep, both ≤ 20% cloud. 60 pairs in md5 order. | The measured natural same-day two-sensor floor; descriptive |
| **Secondary context** | Stage 21 F25/F26 and Stage 20 C25/C26/H4 (1–2-day pairs) | Reported only |

**S at sample-size time:** all 84 candidate pairs are at one site, Lake Hazen (81.8°N), with sun elevation 10–30°.

**Ice and snow screen, for S and FLOOR:** a pair is dropped if either scene's disk median TOA B03 > 0.15 or L2W B03 > 0.05.

**Validity:** both scenes need a valid tier-1 or tier-2 sample, as in Stages 20–21.

## 3. Instrumented quantities (every run)

**Disk medians:**
- rhot and rhos per band;
- aot_550;
- rhog_ref (the SWIR glint reference) and rhog per band (the glint subtracted);
- ac_model and ac_aot_550_mean.

**DSF per tile:** the lowest- and second-lowest-AOT bands (b1, b2), the per-band AOT and the model.

**Definitions:**
- **Path switch** between two scenes of a pair: a different selected model, **or** a different modal b1 band across the crop's DSF tiles.
- **Decomposition** for bands B02–B8A: Δrhos (S2C − ref) = Δ(rhos before glint) − Δrhog. The glint pathway is Δrhog; the remainder is the aerosol/path pathway.

## 4. Mechanism tests (derivation data first, then reported on every set)

**Effect sizes:**
1. The median Δp (S2C − S2A) for pairs with and without a path switch.
2. Theil–Sen slopes of Δp on Δrhog_B04 and on Δaot_550.
3. The change in Δp from K0 to each partial correction (below), by season.

**Stratified by:** season, sun elevation (< 25°, 25–40°, ≥ 40°), water brightness (ref B04 tertiles), NIR/SWIR darkness (ref rhot B11 tertiles), optical state (ref hard class) and S2C baseline.

**Verdicts:**
- **Path switching confirmed:** switches occur in ≥ 20% of pairs **and** the switch/no-switch median Δp difference is ≥ 0.02.
- **Partial:** only one of the two holds.

## 5. Candidates (S2C only; runnable live from the S2C scene alone)

| Candidate | Definition |
|---|---|
| A | Raw nominal S2C (K0); no Stage 12 |
| B | Stage 21 K2 (frozen `corr21.json` offsets + B05 band adjustment); reference |
| C1 (glint-invariant) | Remove only the frozen B11/B12 offsets (B11 = 0.00173 + 0.00445·m_C; B12 = 0.0011). The residual-glint reference no longer sees the sensor's dark offset; DSF inputs unchanged. |
| C2 (aerosol-invariant) | Remove only the frozen B08/B8A offsets (0.0004 / 0.0008) |
| C3 | C1 + the B05 band adjustment (1.0332·B05 − 0.0397·(B06 − B04)) |
| D (conditional) | Eligible only as below |

Here m_C is the S2C tile's own clear-pixel B11 median, as in Stage 21.

**D eligibility.** D chooses between two members of {A, C1, C2, C3} by one threshold on one scene-level variable x, computable from the S2C scene alone. x must be one of:
- S2C sun elevation;
- the K0 disk rhog_ref;
- the K0 disk aot_550;
- the S2C tile B11 m_C.

D is eligible only if, on TD ∪ T2D:
- Spearman |ρ(x, Δp(member1) − Δp(member2))| ≥ 0.4; **and**
- D lowers J (below) by ≥ 0.01 against the best single candidate.

The threshold is the derivation median of x. Month-of-year is not allowed.

**Selection, on derivation only:**
- **Objective:** J = max(|median Δp| on TD, |median Δp| on T2D).
- **Constraints:** TD state overlap ≥ 0.95 and TD class jumps ≤ 0.02.
- **Choice:** the candidate in {A, C1, C2, C3, D} with the lowest J. Ties within 0.005 go to the simpler, in the order A < C1 < C2 < C3 < D.
- **Fallback:** if none meets the constraints, the lowest J is chosen and the failure is reported.
- **Freeze:** the selected candidate, **S22**, is frozen in `cand22.json`.

## 6. Decision A — authority lift (Stage 20/21 bars, unchanged)

**Bars:**
- tandem thresholds for TH and S: spectral ≤ 3%, visibility ≤ 0.03, state overlap ≥ 95%, class jumps ≤ 2%;
- pooled |median Δp| ≤ 0.03 over the gating strata.

**Gating:**
- TH gates.
- S gates only with **≥ 15 valid pairs from ≥ 3 sites**. One Arctic lake cannot certify warm-season behaviour.
- The bar needs TH plus at least one warm same-day stratum. **If S cannot gate, the formal bar cannot be met in Stage 22.** That is reported as the blocking condition.

**Reported alongside:** S22 against the measured FLOOR, and T2H / F25 / F26 as secondary, without changing pass or fail.

**Full authority** also needs the Stage 20/21 Secchi checks (harmful ≤ reference + 0.05; severe ≤ 0.02; |bias − reference bias| ≤ 0.05).

## 7. Decision B — Stage 12 retirement (independent of authority)

**Scope:** nominal operational S2C baselines N0511, N0512, N0513 and newer nominal equivalents. Preliminary N9905/N9906 research products are untouched.

**Replacement candidate:** R = S22. If S22 fails, A (raw, zero parameters) is tested as the only fallback.

**Stage 12 is retired from the nominal-S2C lower-authority path if R meets ALL of these.** Secchi rows are every eligible S2C truth row (dev, cert, fresh), validation only.
1. |median signed error|: R ≤ Stage 12 − 0.02.
2. Harmful rate: R ≤ Stage 12.
3. Severe rate: R ≤ Stage 12.
4. Operational: R ≥ Stage 12 − 0.02.
5. ⅔-interval coverage: R ≥ Stage 12 − 0.02.
6. State overlap with S2A/B: R ≥ Stage 12 − 0.03 on TH and on T2H.
7. No new major failure:
   - in each truth pool, |bias_R| ≤ |bias_12| + 0.03 and harmful_R ≤ harmful_12 + 0.05;
   - |median Δp_R| ≤ 0.05 on TH and on T2H.

Retirement does not imply full authority.

## 8. Secchi validation (after `cand22.json` is frozen)

**Paths:** A, Stage 12, Stage 21 K2 and S22, on every eligible S2C truth row, each scene re-run through the instrumented path.

**Reported:**
- the dev, cert and fresh pools separately (previously seen; validation, not blind certification);
- operational, the four class scores, signed bias, harmful, severe, ⅔ coverage and median feet error.

## 9. Consequences

- **If Decision A passes:** the Stage 19 causal consensus re-run (`stage21/dev21.py` pattern) with full-authority S2C, windows 5/10/15, selection as Stage 21 section 7. Compared against Stages 16 and 19.
- **If not:** no re-run. S2C stays at lower authority, and the blocking condition is reported.
- **If Decision B retires Stage 12:** the research engine's nominal-S2C lower-authority path uses R. The shadow candidate is updated with provenance, and the internal Water Clarity surface shows the candidate to internal accounts. Public production is unchanged.

## 10. Provenance kept per S2C result

- satellite, product id, processing baseline, physical pass and acquisition time;
- ACOLITE version and K4 configuration, and the S2C path version (A/B/C1/C2/C3/D, `cand22.json` hash);
- TOA offsets applied;
- DSF and glint diagnostic state;
- raw and corrected reflectance;
- features, visibility and state, and authority.
