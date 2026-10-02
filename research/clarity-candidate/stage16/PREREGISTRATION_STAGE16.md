# Stage 16 pre-registration: the reliability gate, tier-2 authority and the fresh holdout

**Timing.** Written 2026-10-01:
- before any development quantity for the gate or the tier-2 options was computed;
- before any fresh value was fetched or read.

**What has been read so far** (value-blind; dates and sites only, from the Stage 1 pull's blind index):
- 1,448 site-days dated 2026-04-01 or later and 38 dated January–March 2026, at sites in no earlier file;
- 89% of them are in Wisconsin.

**Freezing.** This file's sha256 goes into `FREEZE_STAGE16.json`. The Stage 14/15 certification set is not used for
anything.

## 1. Unchanged

The following are all used exactly as they are (hashes re-checked):
- the Stage 14 engine: C-gbm, ACOLITE K4, the tiers, S2C V-ρw, the 60 m disk, exact feet and the two-thirds interval;
- the Stage 15 tier-3 rule: Clear only, lower authority;
- the S2C lower-authority rule;
- the algal modifier (NDCI > 0.03 → "~X ft" plus the warning);
- the Stage 15 operational rubric weights.

## 2. The single-state reliability gate (replaces fixed bands as the state rule)

**Posterior model.** For each boundary b ∈ {6, 3, 2} ft, a logistic P(y ≥ b | p) = σ(α_b + β_b (p − b)) is fitted on
development lake-held-out predictions. All rows of the calibration population are used. The three probabilities are
made monotone (P₆ ≤ P₃ ≤ P₂), and the class posteriors follow:

| Class | Posterior |
|---|---|
| Clear | π = P₆ |
| Normal | π = P₃ − P₆ |
| Stained | π = P₂ − P₃ |
| Limited | π = 1 − P₂ |

**The rule,** with thresholds τ₁ (single state) and τ₂ (boundary pair):
1. If the largest π_c ≥ τ₁, the answer is that single state.
2. Otherwise the adjacent pair with the largest combined π is taken (Clear-to-Normal, Normal-to-Stained or
   Stained-to-Limited). If that sum ≥ τ₂, the answer is the boundary state.
3. Otherwise the answer is **Unknown / Low Authority**, with the pair recorded as the withheld answer.

**Consistency.** The issued state must contain the hard class of p. If it does not, it is widened to the adjacent pair
that contains both; if no such pair exists, the answer is Unknown.

**Thresholds** come from the grid τ₁ ∈ {0.60, 0.65, …, 0.90} and τ₂ ∈ {0.70, 0.75, …, 0.95}, with τ₂ ≥ τ₁. They are
chosen jointly with the tier-2 option (section 3), on development rows with nested posteriors (fitted on the inner folds
of the training lakes, applied to the held-out fold):
- **Primary:** the highest class-balanced operational score, subject to development harmful ≤ 12% (a margin under the
  15% bar), severe ≤ 1.5%, and every core class ≥ 0.60.
- **If none qualifies:** the highest score with harmful ≤ 15% and severe ≤ 2%.
- **If still none:** the lowest harmful rate.
- **Ties** (score within 0.005): the lower harmful rate wins.

The production posteriors are fitted on all development lake-held-out predictions.

## 3. Tier-2 authority (development rows only)

| Option | Tier-2 answers |
|---|---|
| T2-A | Full authority, tier-1 posteriors |
| T2-B | Full authority, posteriors calibrated on tier-2 rows only (wider, so more pairs and more Unknown) |
| T2-C | Lower authority (tier-1 posteriors, all tier-2 answers flagged) |
| T2-D | Boundary states only (tier-2 posteriors, no single states; the pair threshold τ₂ applies, else Unknown) |

The option is selected jointly with the thresholds by the section 2 criterion. Coverage is not a criterion.

## 4. The fresh holdout (the P2 fresh pool)

**Sources.**
- **Primary.** WQP "Depth, Secchi disk depth" at lake, reservoir and impoundment sites, dated 2026-01-01 to 2026-09-28,
  fetched fresh on 2026-10-01. The Stage 1 download and build code is reused unchanged, except for the start date.
- **What it covers.** Agency Secchi dated 2026 (January–March), and the P2 national fresh draw (2026-04-01 onward).
- **Not used:** Sector field reports, and Michael's Guntersville survey.

**Exclusions.**
- the site appears in any earlier development or certification file: the Stage 14 `dev_footprint.json` site ids, plus
  every Stage 14 draw and sample site;
- the site is in the Guntersville box;
- the record is censored (bottom visible), which the Stage 1 build rules apply.

**Lake independence.** A lake is a single-linkage 5 km cluster.
- **Primary:** sites in no earlier file, which is the Stage 10 P2 definition.
- **Strict subset:** lakes more than 5 km from every development station and every Stage 12–14 certification site.
  Reported separately.

**Sampling and matching.**
- At most one site-day per site-month.
- **Prescreen:** an item within ±1 day with `eo:cloud_cover` ≤ 20% (the A2 rule).
- **Match:** `extract_cert.py --max-dt 1`, the production gates, ≥ 5 valid pixels, the best pass.
- **Per lake:** at most 3, in seeded order (seed 20261001, the P2 seed).
- **No state cap.** The pool cannot afford one. The Wisconsin share is reported, with a breakdown without Wisconsin.
- **ACOLITE:** `run_cert_aco_a1.py`, the frozen K4 path (EPQS elevation).

**Classes and labels.**
- Secchi classes at 6 / 3 / 2 ft.
- Water type by the Stage 11 `insitu_type` rule: same-day turbidity from the fresh pull, and chlorophyll fetched at
  unsealing for fresh sites only.
- Truth is the median of the site-day's readings, kept if 0.05–25 m.

**Minimum counts.** Below any of these, the verdict is INSUFFICIENT, and the minima are never lowered:

| Group | Minimum | Role |
|---|---:|---|
| Clear | 40 | Core |
| Normal | 40 | Core |
| Stained | 60 | Core |
| Limited | 25 | Core |
| Scored rows overall | 200 | Core |
| Algae | 30 | Reported only, not a readiness gate |
| Sediment | 20 | Reported only, not a readiness gate |

**Unsealing.** Fresh Secchi values are read once, after the gate, the tier-2 rule and this protocol are frozen and the
fresh sample is hashed.

## 5. Scores

**A. Exact feet.** The Stage 12 rubric as coded. Feet are published only at full authority with "exact" or "approx"
display.

**B. Operational visibility decision.** The Stage 15 rubric unchanged, with these outcomes:
- correct single state;
- correct boundary state;
- correct or wrong lower-authority answer;
- appropriate Unknown, or one that withheld a right answer;
- harmful (full-authority wrong);
- severe (harmful by ≥ 2 classes).

The score is round(10 × the class-balanced mean).

**C. Sector Intelligence suitability.** Each answer gets one evidence level:

| Evidence level | Condition | Bar (truth in the answer) |
|---|---|---|
| **Strong** | Full authority, tier 1, not S2C, no algal flag, issued posterior ≥ 0.90 | ≥ 0.90 |
| **Moderate** | Any other full-authority answer | ≥ 0.80 |
| **Weak** | Any lower-authority answer (tier 3, S2C, tier 2 if lowered) | ≥ 0.65 |
| **Unavailable** | Unknown | — |

A level with n < 30 is INSUFFICIENT and counts as not met.
- **SAFE FOR SECTOR INTELLIGENCE: YES** if strong, moderate and weak all meet their bars.
- **PARTIAL** if strong and moderate meet theirs.
- **NO** otherwise.

## 6. Success bars (the Stage 15 freeze rules, unchanged)

**READY TO FREEZE CLARITY AND START WATER TEMPERATURE: YES** only if, on the fresh holdout, all of these hold:
1. every core minimum is met;
2. operational capability ≥ 7/10;
3. every core class ≥ 0.60;
4. harmful ≤ 15%;
5. severe ≤ 2%.

The same must also hold on development (nested).

**Stretch target (a true 9/10 product), reported only:**
- operational ≥ 9/10 (class-balanced ≥ 0.85);
- every core class ≥ 0.80;
- harmful ≤ 5%;
- severe ≤ 0.5%;
- strong evidence ≥ 50% of answers.
