# Current Clarity Stage 23: Operational S2C Authority, Low-Sun Guard and Consensus Recovery

**2026-10-04.** This stage asks whether nominal Sentinel-2C can earn full authority when the sun is at least 25° high, judged against a measured disagreement floor between the two satellites already trusted (S2A and S2B). It then asks whether that would fix the live consensus's evidence-density problem.

**What didn't change:**
- the C-gbm, which was not refit;
- the Stage 16 posterior gate;
- the Stage 19 consensus code;
- the frozen ACOLITE K4 path;
- C3;
- the Stage 22 retirement of Stage 12, which stays retired;
- the Strong definition;
- the Stage 16 freeze bars and the true 9/10 bar.

**What was never used for fitting:** field reports and Secchi truth.

**Method:**
- Pre-registered before any Stage 23 reflectance, consensus score or Secchi value was read: `PREREGISTRATION_STAGE23.md`, SHA-256 `2919833b…`, frozen 16:03 UTC.
- The rules were not changed after any result was seen.

Public production is unchanged.

**The answer: S2C stays at lower authority (outcome B). The cleanest test passes, but the floor, the newest processing baseline and Secchi each fail on their own.**
- **The cleanest test passes.** On the winter tandem (S2A and S2C over the same water about 30 s apart, sun ≥ 25°), C3 is inside the true S2A/S2B tandem floor on every criterion:
  - visibility +0.006;
  - state agreement 100%;
  - class jumps 1.3%.
- **The floor fails its own check.** Same-day S2A/S2B pairs, 146 valid at 101 lakes in all five US regions, disagree systematically by +0.034 in visibility, over the pre-registered 0.03.
  - The disagreement is viewing geometry. On adjacent tracks the two satellites see the water from opposite sides about 10 minutes apart, and differ by 20–28% in the visible bands.
  - In true tandem (same geometry) they agree within 0.5%.
- **N0513 fails.** On fresh N0513 pairs (September–October 2026), C3 reads 0.051 murkier than S2A, while raw S2C is within +0.007.
  - The measured top-of-atmosphere dark-water offset on N0513 is about a third of N0511's.
  - The frozen C3 offsets, derived on N0511, now over-correct the baseline the live product reads.
- **Secchi fails narrowly.** At sun ≥ 25°, C3's bias is −0.062 against the S2A/B reference's −0.010: 0.052 apart against a 0.05 limit. Harmful and severe both pass.
- **No re-run.** As pre-registered, the consensus was not re-run, and the score stays **7/10**.
  - Had S2C been trusted, current-era answers with no earlier full-authority view would fall from 71.3% to 59.1% (5-day window).
  - That is not earned.
- **Diagnostics:**
  - Two-thirds of harmful answers are murky water read as too clear.
  - The leading causes are boundary-state answers, single-scene answers, and confident answers that are wrong.
  - All 22 severe errors are moderate-evidence answers (none Strong); 17 rest on a single scene.

## 1. Data

| Set | What | Processed | Valid | Role |
|---|---|---|---|---|
| **FL23** | Same-day S2A ↔ S2B, ≤ 30 min, both ≤ 20% cloud, sun ≥ 25°, US inland lakes 25–50°N, 2025-03 → 2026-10 | 239 pairs: 66 tandem, 173 adjacent | **146** (after the ice screen 195; 5 scenes produced no water product) at **101 lakes**, all **5 regions**: 42 tandem at 31 lakes, 104 adjacent at 77 lakes | The measured floor |
| **T2N** | Fresh N0513 S2C → S2A, same track, 48 h, Sep–Oct 2026 | 71 | 56 (C3), sun ≥ 25° | N0513 |
| **TH25** | Stage 22's held-out winter tandem, S2C sun ≥ 25°, N0511 | (Stage 22) | 79 | The same-water test |
| **T2H25** | Stage 22's held-out warm 2-day pairs, N0511/N0512 | (Stage 22) | 68 | Warm systematic test |
| **Secchi** | Every eligible S2C truth row | 137 | 129 at ≥ 25°, 8 below | Validation after the sensor decision |

**The floor met its size targets** (≥ 100 valid, ≥ 10 lakes, ≥ 3 regions), so the extension list FL23X was not used. Regions: West 49, Plains 31, Southeast 29, Midwest 21, Northeast 16.

**A tandem inside the data.** In January–February 2026, S2A and S2B flew in tandem: same orbit, about 30 s apart, same viewing geometry. That subset is the exact counterpart of the S2A/S2C tandem.

**Reads:**
- **Scenes were read lazily from the public Google bucket** (only the crop windows), so nothing was billed. Before use, the lazy read was verified to reproduce Stage 22's full downloads exactly: maximum difference 0.0, and identical C1 offsets.
- **7 N0513 tasks were re-run** after a lazy-folder race between parallel workers (two lakes in one satellite scene), which is now fixed. The outputs are deterministic, so no value is affected.
- **5 floor scenes were re-run once and again produced no water product.** They count as invalid pairs, like cloud.
- **No AWS data was used.**

## 2. The measured floor (S2B relative to S2A)

| | Pairs | B02 | B03 | B04 | B05 | Visibility | \|Δvis.\| P90 | State | Jumps | Legacy 3% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Pooled** | 146 | 0.873 | 0.926 | 0.861 | 0.847 | **+0.034** | 0.352 | 93.6% | 8.2% | fail |
| Tandem (same geometry, ~30 s) | 42 | 0.995 | 1.000 | 0.989 | 0.996 | 0.000 | 0.154 | 100% | 0% | **pass** |
| Adjacent (opposite geometry, ~10 min) | 104 | 0.803 | 0.859 | 0.747 | 0.722 | +0.048 | 0.452 | 90.9% | 11.5% | fail |

Band columns are median S2B/S2A reflectance ratios. Per-pair spread, median (P50) and 90th percentile (P90) of |log10 ratio|:

| | B02 P50 / P90 | B03 | B04 | B05 |
|---|---|---|---|---|
| Pooled | 0.074 / 0.542 | 0.042 / 0.427 | 0.088 / 0.660 | 0.097 / 0.620 |
| Tandem | 0.038 / 0.117 | 0.011 / 0.072 | 0.032 / 0.108 | 0.029 / 0.133 |
| Adjacent | 0.107 / 0.677 | 0.070 / 0.528 | 0.139 / 0.713 | 0.166 / 0.715 |

**What this shows:**
- **Two trusted sensors in tandem agree systematically within 0.5%.** They pass even the legacy 3% bar.
  - Their per-pair disagreement (median 1–4%) is ordinary noise.
  - They agree on visibility (0.000) and state (100%).
- **Seen from adjacent tracks, the same water differs by 20–28%.** Visibility differs by +0.048, with heavy tails (P90 0.45).
  - The 10-minute lag puts S2A and S2B on opposite sides of the scene, so one of them consistently sees more sun glint.
  - This is viewing geometry, not sensor calibration.
  - It is also what the live consensus mixes when it combines passes from different tracks.
- **By the pre-registered rule, the floor is not usable.** Its systematic visibility disagreement (+0.034) exceeds 0.03, so the envelope cannot certify S2C (section 8). The geometry effect is a finding in its own right (section 17).

## 3. The pre-registered envelope

| | B02 | B03 | B04 | B05 | Visibility | State | Jumps |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Pooled (primary):** systematic bound E50 | 0.074 | 0.042 | 0.088 | 0.097 | 0.03 (legacy) | ≥ 90.6% | ≤ 10.2% |
| Pooled: spread bound E90 | 0.542 | 0.427 | 0.660 | 0.620 | V90 0.352 | | |
| **Tandem subset (sensitivity):** E50 | 0.038 | 0.011 | 0.032 | 0.029 | 0.03 | ≥ 95% | ≤ 2% |
| Tandem subset: E90 | 0.117 | 0.072 | 0.108 | 0.133 | V90 0.154 | | |

E50 and E90 are in log10.

## 4. S2C (C3) at sun ≥ 25°

| Stratum | Pairs | B02 | B03 | B04 | B05 | Visibility | \|Δvis.\| P90 | State | Jumps | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **TH25** winter, same water (N0511) | 79 | 0.942 | 0.976 | 0.944 | 0.956 | **+0.006** | 0.086 | **100%** | **1.3%** | **pass** (pooled and tandem envelopes) |
| **T2H25** warm 2-day (N0511/N0512) | 68 | 0.941 | 0.956 | 0.935 | 0.975 | **−0.009** | 0.310 | 93.8% | 4.4% | **pass** (systematic) |
| **T2N** warm 2-day (**N0513**) | 56 | **0.793** | 0.890 | 0.891 | 0.908 | **−0.051** | 0.257 | 94.3% | 7.1% | **fail** (B02, B03, visibility) |

Band columns are median S2C/S2A reflectance ratios.

**By baseline:**
- N0511: 109 pairs, visibility 0.000, **pass**;
- N0512: 37 pairs, +0.007, **pass**;
- N0513: 56 pairs, −0.051, **fail**.

**Raw S2C beside it,** for comparison:
- TH25 +0.050;
- T2H25 +0.014;
- T2N **+0.007**.

**Against the stricter tandem envelope,** TH25 still passes every criterion, while T2H25's bands and T2N fail. The legacy 3% bar fails on every S2C stratum, as it did before.

**What this shows:**
- **On the winter tandem,** C3 at ≥ 25° behaves like a trusted sensor: inside the S2A/S2B tandem floor on systematic bias, spread, state and class jumps.
- **On 2-day warm pairs at N0511/N0512,** it is systematically within the floor.
- **On N0513 it is not.** This is the first stage with N0513 data.

## 5. Why N0513 fails (diagnostic)

| Set | Pairs | TOA B08 | B8A | B11 | B12 | C3 B11 offset removed |
|---|---:|---:|---:|---:|---:|---:|
| TH25 N0511 (tandem; pairs with TOA diagnostics) | 94 | +0.0005 | +0.0010 | **+0.0030** | **+0.0016** | 0.0025 |
| T2H25 N0511 (2-day) | 37 | +0.0003 | −0.0001 | +0.0018 | +0.0007 | 0.0025 |
| T2H25 N0512 (2-day) | 42 | +0.0046 | +0.0043 | +0.0053 | +0.0035 | 0.0027 |
| **T2N N0513** (2-day) | 67 | −0.0006 | −0.0002 | **+0.0011** | **+0.0006** | **0.0024** |

The TOA columns are S2C − S2A top-of-atmosphere water reflectance, median over the disk.

**What this suggests:**
- **N0513's S2C dark-water offset looks about a third of N0511's,** yet C3 still removes the full frozen amount. That over-removes the glint reference, so the visible bands keep glint they should lose, and S2C reads murkier.
- **Raw N0513 S2C is already close to S2A in visibility** (+0.007).

**The caveat:** 2-day pairs carry two days of real atmospheric change. N0512's 2-day pairs read high (+0.0053), so this is a strong lead, not a measurement.

**The consequence:** the live shadow runs C3 on N0513 scenes, so its S2C answers (lower authority) are probably too murky by about 0.05 log10. N0513 was not part of the Stage 22 evidence either.

## 6. Low-sun guard

**Pre-registered at exactly 25°:** S2C below 25° can never be full authority or Strong.

**Since no S2C reaches full authority in this stage,** the guard changes no answer today. It is the rule for any later grant.

**Secchi rows below 25° are few** (8 S2C, 149 S2A/B), and both sensors are poor there:
- S2A/B reference: bias −0.211, harmful 32%;
- S2C C3: bias −0.155.

That supports the guard.

## 7. Secchi validation (after the sensor decision was recorded)

| Subset | S2A/B reference | Raw S2C | C3 |
|---|---|---|---|
| **Sun ≥ 25°** | n 2,556; op 0.722; bias −0.010; harmful 13.8%; severe 2.0%; coverage 66% | n 129; op 0.713; **bias +0.009**; harmful 12.4%; severe 1.6%; coverage 64% | n 129; op 0.689; **bias −0.062**; harmful 14.0%; severe 1.6%; coverage 60% |
| Sun < 25° | n 149; op 0.600; bias −0.211; harmful 32.2% | n 8; op 0.606; bias −0.107 | n 8; op 0.656; bias −0.155 |
| Warm | n 2,238; bias −0.017 | n 131; bias +0.005 | n 131; bias −0.064 |
| Winter | n 149; bias +0.041 | n 6; bias −0.085 | n 6; bias −0.190 |
| Dev | n 1,359; bias +0.007 | n 38; bias +0.014 | n 38; bias +0.012 |
| Cert | n 1,300; bias −0.034 | n 54; bias −0.008 | n 54; bias −0.092 |
| Fresh | n 46; bias −0.054 | n 45; bias −0.002 | n 45; bias −0.071 |

"op" is the operational score and "coverage" the ⅔-interval coverage.

**Data gap:** 318 S2A/B reference rows have no scene date, so they are missing from the season split. Every S2C row is dated.

**At sun ≥ 25°, C3 against the reference (sun ≥ 25°):**

| Measure | C3 | Reference | Result |
|---|---|---|---|
| Harmful | 14.0% | 13.8% (limit 18.8%) | pass |
| Severe | 1.6% | — (limit 2%) | pass |
| Signed bias | −0.062 | −0.010 | **fail**: 0.052 apart (limit 0.05) |

**Class scores and feet error at ≥ 25°:**

| Path | Clear | Normal | Stained | Limited | Median feet error |
|---|---:|---:|---:|---:|---:|
| C3 | 0.91 | 0.59 | 0.54 | 0.72 | 1.6 ft |
| Raw S2C | 0.95 | 0.70 | 0.54 | 0.67 | 1.9 ft |
| S2A/B reference | 0.91 | 0.68 | 0.60 | 0.70 | 1.4 ft |

**Raw S2C is again the least biased path against truth,** consistent with section 5.

## 8. Authority decision

| Requirement | Result |
|---|---|
| Floor usable (≥ 100, ≥ 10 lakes, ≥ 3 regions, \|visibility\| ≤ 0.03) | **fail**: 146 / 101 / 5, but visibility +0.034 |
| TH25, every criterion | pass |
| T2H25, systematic | pass |
| T2N, systematic | **fail** |
| Baselines N0511 / N0512 / N0513 | pass / pass / **fail** |
| Secchi ≥ 25°: harmful, severe | pass |
| Secchi ≥ 25°: bias within 0.05 of reference | **fail** (0.052) |

**S2C CONDITIONAL FULL AUTHORITY: NO. Outcome B, lower authority.**

Each of the three failures would block A on its own. The decisive one under the rules is the floor's own visibility check.

**Low-sun S2C stays lower authority.**

## 9. Live causal consensus

**Not run, as pre-registered.** The reference R0 (Stage 22 live development: Stage 19, 5-day causal, C3 for S2C at lower authority) was recomputed by the same patched code. It reproduces Stage 22 to the seventh digit:

| Metric | Value |
|---|---|
| Operational | 0.7102533 |
| Clear | 0.884 |
| Normal | 0.671 |
| Stained | 0.606 |
| Limited | 0.680 |
| Harmful | 11.44% |
| Severe | 1.39% |
| Unknown | 9.9% |
| Strong | 10.9% at 92.9% |

Best live window: **causal, past 5 days** (unchanged).

## 10. Evidence density (independent earlier full-authority views)

Current era = truth date from 21 Jan 2025 (115 events). "Hypothetical" adds S2C at ≥ 25° with a valid C3 sample, which is not earned.

| Window | Current era, now: 0 / 1 / 2 / 3+ | Current era, hypothetical | All 1,582 events, now: 0 views |
|---|---|---|---|
| 5 days | 71.3% / 19.1% / 8.7% / 0.9% | 59.1% / 30.4% / 7.8% / 2.6% | 67.6% (hypothetical 66.8%) |
| 10 days | 59.1% / 21.7% / 15.7% / 3.5% | 48.7% / 26.1% / 13.0% / 12.2% | 52.7% |
| 15 days | 52.2% / 27.0% / 17.4% / 3.5% | 39.1% / 29.6% / 16.5% / 14.8% | 42.0% |

**Answers with at least one recent prior full-authority view (current era, 5 days):** 28.7% now. It would be 40.9% with trustworthy S2C at ≥ 25°.

**Supporting passes:**
- median age 5.0 days;
- contribution S2A 44.7%, S2B 55.3%, S2C 0%.

## 11. Strong evidence

**10.9% of usable answers, at 92.9% accuracy** (156 answers):
- 84% rest on 2 agreeing passes and 16% on 3 or more;
- median supporting-pass age 5.0 days.

| Truth class | Usable | Strong share | Strong accuracy |
|---|---:|---:|---:|
| Clear | 702 | 17.4% | 100% |
| Normal | 337 | 5.0% | 53% |
| Stained | 191 | 3.1% | 50% |
| Limited | 195 | 5.6% | 100% |

**Strong is almost only a clear-water signal.** Where it does appear for normal and stained water, it is a coin toss on very few rows. More legitimate passes, which S2C could have supplied, are the only route to more Strong. The Strong definition was not changed.

## 12. Stained water

| System | Operational | Truth in answer | Harmful | Severe | Unknown | Median \|log10\| feet error | Mean posterior |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stage 16 single scene (Stage 12 retired) | 0.571 | 71.9% | 22.0% | 4.0% | 19.8% | 0.151 | 0.791 |
| **Stage 19 / R0 (live development)** | **0.606** | **74.5%** | **21.1%** | **4.0%** | **15.9%** | **0.142** | **0.798** |
| Stage 23 consensus | not run (outcome B) | | | | | | |

Rows: 227 stained truth rows. R0 against Stage 16: **+0.034 (95% CI +0.007 to +0.064)**, lake bootstrap B = 2000.

The gain comes with fewer Unknowns (19.8% → 15.9%) and no rise in harmful or severe answers. It is not bought by answering less.

## 13. Harmful answers (diagnostic; nothing tuned)

There are 181 harmful answers among 1,425 answered (1,582 rows).

**By direction:**
- **murky water read too clear: 117 (65%);**
- clear water read too murky: 64 (35%).

| Category (non-exclusive) | Harmful | Share of harmful | Harmful rate in the category |
|---|---:|---:|---:|
| **Boundary-state answer** (e.g. Clear-to-Normal) | 125 | 69% | 15.1% of 827 |
| **Single scene only** | 118 | 65% | 12.3% of 962 |
| **High posterior (≥ 0.90) but wrong** | 34 | 19% | 6.5% of 527 |
| Multi-scene disagreement | 32 | 18% | **19.4%** of 165 |
| Tier 2 | 16 | 9% | 8.4% of 191 |
| Stale-prior disagreement | 2 | 1% | 2 of 6 |
| Algae-flagged | 0 | 0% | 0 of 18 |
| Low-sun S2C involved | 0 | 0% | 0 of 1 |
| Stale anchor (≥ 3 days) | 0 | — | none in the corpus (≤ 2 days by construction) |
| Posterior < 0.70 | 0 | — | none (the Stage 16 gate already withholds them) |

**Top causes:**
1. boundary-state answers;
2. single-scene answers;
3. confident answers that are wrong.

**Where the risk concentrates:** multi-scene disagreement has the highest rate. When independent passes disagree, the answer is wrong about one time in five.

## 14. Severe errors (all 22)

**Every one is moderate evidence (none Strong)**, tier 1 except one tier-2 and two tier-3 answers. None involves S2C, and none is algae-flagged.

| Truth | Rows | Answer given | Answer feet | Satellites | Scene age | Posterior | Passes |
|---|---:|---|---|---|---|---|---|
| Stained (2.3–3.0 ft) | 9 | **Clear** (all 9) | 7.7–18.2 ft | S2B 5, S2A 4 | 0–2 d | 0.72–0.98 (6 ≥ 0.93) | 1 (8), 2 (1) |
| Limited (0.7–2.0 ft) | 10 | Clear-to-Normal (8), Clear (2) | 4.5–12.4 ft | S2B 6, S2A 4 | 0–2 d | 0.76–0.95 | 1 (7), 2 (3) |
| Clear (6.0–8.1 ft) | 3 | Stained-to-Limited (3) | 1.9–2.1 ft | S2B 3 | 0–1 d | 0.79–0.92 | 1 (2), 2 (1) |

**The pattern:** 19 of 22 are murky water read as clear, usually from one fresh scene and often with high confidence.

**Diagnostic counterfactuals:**
- **A Strong-only rule** would have removed all 22, but it would also withhold about 89% of answers.
- **Withholding below 0.70** would remove none.

No guard was added.

## 15. Exact feet

**Capability 8/10, unchanged.**
- Feet are shown on 84.8% of rows.
- Median multiplicative error 1.34×.
- Signed bias +0.001 log10.
- ⅔-interval coverage 68%.

**By class:**

| Class | Signed bias | Error | Coverage |
|---|---|---|---|
| Clear | −0.080 (reads murkier) | 1.33× | 67% |
| Normal | +0.035 | 1.28× | 76% |
| Stained | +0.113 (reads clearer) | 1.39× | 68% |
| Limited | +0.150 (reads clearer) | 1.45× | 56% |

**By evidence:**
- Strong 1.36×, coverage 65%;
- moderate 1.34×, coverage 68%.

**The class pattern** is the familiar pull toward the middle: clear water reads murkier, murky water reads clearer. It is the same direction as the harmful answers.

## 16. Adoption

Not applicable. No Stage 23 consensus was produced. The development candidate stays R0 (Stage 19, 5 days, C3 at lower authority).

## 17. What the stage found that matters next

1. **Viewing geometry, not sensor calibration, is the largest disagreement between passes.**
   - Opposite-side views of the same water, 10 minutes apart, differ by 20–28% in the visible bands, with heavy tails.
   - Tandem views agree within 0.5%.
   - Any consensus that mixes tracks is mixing that geometry. A geometry or glint-aware weighting is a better lever than any further sensor correction.
2. **N0513 has moved S2C, and C3 is now probably over-correcting the live S2C.** An N0513-specific check is due: either confirm raw N0513 against the S2A/B floor, or re-derive the offsets on N0513 data, under a fresh pre-registration.
3. **S2C's same-water behaviour at sun ≥ 25° is already trusted-sensor grade at N0511.** The authority question is now about baselines and the floor's definition, not about S2C as an instrument.

## 18. Status of the evidence

**Every truth pool has been seen before;** none is blind.

| Track | Score |
|---|---|
| Development | 7/10 |
| Certified | none |
| Deployed production | 2/10 |

## 19. Internal map

No new candidate results from Stage 23, so the Water Clarity layer and the shadow are unchanged. Internal accounts still see the Stage 22 candidate with its status, observation time and age, evidence, satellite and S2C path; public users are unchanged.

The low-sun guard has no answer to change while S2C is at lower authority.

The likely N0513 over-correction (section 5) affects those internal S2C answers. It is flagged here, not patched, because a path change needs its own pre-registration.

## 20. Files (`research/clarity-candidate/stage23/`)

**Pre-registration and freeze:**
- `PREREGISTRATION_STAGE23.md`;
- `FREEZE_STAGE23.json`.

**Data:**
- `build23_pairs.py` → `pairs23_meta.json`;
- `build23_tasks.py` → `tasks23_{FL23,FL23X,T2N}.json`.

**Processing:**
- `lazy23.py`: the lazy Google Cloud SAFE;
- `run_aco23.py`: the driver. It was amended after the freeze only to give each task its own lazy folder (the race fix in section 1); `FREEZE_STAGE23.json` holds the pre-fix hash;
- `check23_lazy.json`, `check23_offsets.json`: tooling checks;
- `check23_results.py`;
- `res23_FL23/`, `res23_T2N/`.

**Analysis:**
- `anal23.py` → `eval23.json`;
- `secchi23.py` → `secchi23.json`, `secchi23_rows.json`;
- `decide23.py` → `decide23.json`;
- `dev23.py` + `report23_block.py` → `dev23_R0*.json`;
- `_toa23.py`: the report-only N0513 diagnostic.

## 21. Status

MID-LATITUDE S2A/S2B FLOOR SIZE: 146 valid same-day pairs at 101 lakes in 5 regions.
- Of these, 42 are tandem pairs (same geometry, ~30 s apart) at 31 lakes, and 104 adjacent-track pairs (~10 min) at 77 lakes.
- 239 pairs were processed.

LEGACY 3% SPECTRAL BAR PASSED BY S2A/S2B: NO.
- Pooled pairs: B02 0.873, B04 0.861 (S2B/S2A).
- The tandem subset alone passes (all bands within 1.1%).

MEASURED OPERATIONAL SENSOR FLOOR: pooled, median per-pair |log10| disagreement B02 0.074, B03 0.042, B04 0.088, B05 0.097.
- 90th percentile: 0.54 / 0.43 / 0.66 / 0.62.
- Visibility: systematic +0.034, P90 0.35.
- State agreement 93.6%; class jumps 8.2%.
- **Unusable by its own pre-registered check** (systematic visibility +0.034 > 0.03), driven by adjacent-track viewing geometry (+0.048).
- Tandem floor: within 0.5%, visibility 0.000, state 100%.

LOW-SUN S2C GUARD: pre-registered at exactly 25°.
- S2C below 25° can never be full authority or Strong.
- It changes no answer today, because no S2C earned full authority.

S2C ≥25° CROSS-SENSOR EQUIVALENCE: FAIL
- The winter tandem (N0511) passes every criterion, against both the pooled and the tandem envelopes: visibility +0.006, state 100%, jumps 1.3%.
- The warm N0511/N0512 pairs pass (−0.009).
- **N0513 fails** (−0.051; B02 0.79), and the floor itself is unusable.

S2C CONDITIONAL FULL AUTHORITY: NO (outcome B)
- Floor unusable.
- N0513 fails.
- Secchi at ≥ 25°: bias −0.062 against the reference's −0.010 (0.052 > 0.05); harmful and severe pass.

S2C LOW-SUN AUTHORITY: LOWER

BEST LIVE CONSENSUS WINDOW: causal, past 5 days (Stage 19, unchanged; no re-run, because conditional authority failed)

ZERO-PRIOR-VIEW RATE BEFORE / AFTER: current era (115 events), 5 days: 71.3% / 71.3% (unchanged; S2C not lifted).
- All events: 67.6% / 67.6%.
- Hypothetical with trustworthy S2C at ≥ 25°: 59.1% (current era, 5 d), 48.7% (10 d), 39.1% (15 d).
- At least one recent prior view: 28.7% now, against 40.9% hypothetical.

CLEAR SCORE: 0.884

NORMAL SCORE: 0.671

STAINED SCORE: 0.606
- Against the single scene: +0.034, 95% CI +0.007 to +0.064.

LIMITED SCORE: 0.680

OPERATIONAL SCORE: 0.710 (7/10)

HARMFUL RATE: 11.4% (181 of 1,582)

TOP HARMFUL-ERROR CAUSES:
1. Boundary-state answers: 69% of harmful, 15.1% rate.
2. Single-scene answers: 65%, 12.3% rate.
3. Confident (posterior ≥ 0.90) but wrong: 19%, 6.5% rate.

65% of harmful answers are murky water read too clear. Multi-scene disagreement has the highest rate (19.4%).

SEVERE RATE: 1.39% (22)
- All moderate evidence, none Strong.
- 17 rest on a single scene; none involves S2C.
- 19 of 22 are murky water (≤ 3 ft) read as Clear or Clear-to-Normal, often with high posterior.

EXACT-FEET CAPABILITY: 8/10
- Median error 1.34×, bias +0.001, coverage 68%, feet shown on 85% of rows.
- Stained reads +0.11 and limited +0.15 too clear.

STRONG EVIDENCE SHARE / ACCURACY: 10.9% of usable answers / 92.9%.
- Clear 17.4% at 100%; normal 5.0% at 53%; stained 3.1% at 50%; limited 5.6% at 100%.
- 2 supporting passes in 84% of cases; median age 5 days.

STAGE 16 FREEZE BARS PASSED: YES

8/10 DEVELOPMENT CHECKPOINT PASSED: NO
- Operational 0.710 against 0.75.
- Weakest class 0.606 against 0.65.
- Harmful 11.4% against 10%.
- Severe 1.39% against 1.0%.
- Strong 10.9% against 25%.
- Strong accuracy and exact feet pass.

TRUE 9/10 DEVELOPMENT BAR PASSED: NO

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 development (uncertified); certified none; deployed production 2/10

REMAINING TECHNICAL LIMITATIONS:
- **The operational floor is dominated by viewing geometry.** Adjacent-track views of the same water differ by 20–28%, so a floor built from them cannot certify a sensor. The consensus mixes that geometry without modelling it, and a geometry or glint-aware treatment is the open lever.
- **C3 likely over-corrects N0513**, the live S2C baseline (2-day evidence: about a third of the N0511 dark offset, C3 −0.051 against raw +0.007). N0513 needs its own pre-registered check, and the internal S2C answers are probably too murky meanwhile.
- **Raw S2C stays the least biased path against Secchi** (≥ 25°: +0.009 against C3's −0.062), contradicting the S2A-relative evidence on N0511/N0512.
- **Strong is almost only clear water.** Normal 5% and stained 3%, at about 50% accuracy, so evidence density, not the Strong rule, limits coverage.
- **Harmful answers concentrate in boundary states and single scenes.** Severe errors are murky water read clear from one confident scene; only more independent evidence, not a new guard, addresses them without withholding most answers.
- **Stained stays at the 0.60 floor** (0.606), limited at 0.68.
- **No precipitation record** screens the floor pairs (cloud and validity are the proxy).
- **Every truth pool has been seen;** no blind data.

Stop.
Do not promote public production.
