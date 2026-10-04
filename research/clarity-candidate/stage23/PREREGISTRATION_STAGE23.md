# Stage 23 pre-registration — operational S2C authority, low-sun guard, consensus recovery

Written and frozen before any Stage 23 reflectance, pair outcome, consensus score or Secchi value is read. `FREEZE_STAGE23.json` holds this file's SHA-256 and the hashes of the pair metadata and run lists below.

## 0. Already known when writing

**From earlier stages:** every Stage 16–22 result, including Stage 22's held-out S2C (C3) numbers.
- **By sun elevation:** visibility +0.005 at 25–40° and −0.004 at ≥ 40° (held out), against +0.076 below 25°.
- **On the full winter tandem (TH, all sun):** band ratios B02 0.942, B03 0.980, B04 0.940, B05 0.943; visibility +0.007; state agreement 100%; class jumps 1.1%.
- **On T2H:** visibility −0.009, state agreement 93.8%, class jumps 4.4%.
- **On Secchi, all S2C rows:** C3 bias −0.067 against the S2A/B reference −0.016. On warm-season rows, raw S2C was +0.007 and C3 −0.063.

**Stage 23 metadata only:** `pairs23_meta.json` and the run lists `tasks23_{FL23,FL23X,T2N}.json`.
- dates, orbits, cloud, geometry and sun elevation;
- no reflectance.

**Two tooling checks, on Stage 22 scenes outside every Stage 23 set:**
- `check23_lazy.json`: the lazy Google Cloud read reproduces the Stage 22 full-download ACOLITE samples with maximum difference 0.0, on one S2A and one S2B scene.
- `check23_offsets.json`: the lazily read C1 offsets reproduce Stage 22's exactly, on two S2C scenes.

These Stage 22 values are known. The rules below are chosen on principle, and section 4 states why. They were not chosen to make S2C pass.

## 1. Unchanged and preserved

**Not changed:**
- the C-gbm (not refit);
- the Stage 16 posterior gate;
- the Stage 19 consensus code;
- the frozen ACOLITE K4 path and the instrumented runner (`stage22/aco22_one.py`);
- C3 (the frozen Stage 21 B11/B12 offsets, then the B05 band adjustment);
- the Stage 22 retirement of Stage 12;
- the Strong definition (posterior ≥ 0.90, ≥ 2 agreeing independent full-authority passes, no disjoint state);
- the Stage 16 freeze bars and the true 9/10 bar.

**Not done:** Stage 12 is not restored. Nothing is fitted to field reports or Secchi. No new general S2C correction is attempted.

**Lower authority stays** for every S2C scene unless section 8 grants a change.

## 2. Data

**Floor FL23 (`tasks23_FL23.json`, 239 pairs, 146 lakes, 5 regions).** Same UTC day S2A ↔ S2B pairs at Stage 20 inland-lake sites (`L:`, 25–50°N), 2025-01-01 to 2026-10-03. Each pair:
- is ≤ 30 minutes apart;
- has both scenes ≤ 20% tile cloud;
- has both scenes at sun elevation ≥ 25°.

**Physical-pass deduplication:**
- one observation per (lake, UTC date): the S2A and S2B items with the lowest combined cloud;
- a physical pass is (platform, UTC date, relative orbit), so each observation is two different physical passes.

**Two subtypes:**
- **tandem:** same relative orbit, the Jan–Feb 2026 S2A/S2B tandem, about 30 s apart, same viewing geometry. All 66 are included.
- **adjacent:** neighbouring tracks, about 10 minutes apart, different viewing angles. 173 are taken in md5("stage23|floor|site|date") order, at most 3 per lake.

**Regions** (by state):
- Northeast;
- Southeast;
- Midwest;
- Plains;
- West.

**Precipitation-front screen.** It is approximated by the cloud limits and the per-scene validity below. No weather record is used, and that is stated as a limitation.

**Extension rule (once).** If FL23 yields fewer than 100 valid pairs, fewer than 10 lakes or fewer than 3 regions, the 118 pairs of `tasks23_FL23X.json` (the next adjacent candidates, same order) are processed. If the floor is still short, the attainable sample is reported, and the stage stops before any S2C evaluation.

**T2N (`tasks23_T2N.json`, 71 pairs, 69 lakes).** Fresh nominal **N0513** S2C → S2A pairs:
- same relative orbit and tile, S2A 48 ± 1 h later;
- both ≤ 20% cloud, S2C sun ≥ 25°;
- 2026-08-01 to 2026-10-03, one per (lake, S2C pass);
- S2C runs K0 and C1, so C3 = C1 + the B05 adjustment.

**From Stage 22, unchanged:**
- **TH:** the winter real-nominal tandem, N0511, held out from C3's selection;
- **T2H:** warm 2-day S2C → S2A pairs, N0511 and N0512, held out.

**Validity.** Both scenes need a valid tier-1/2 sample (`lib20.pick`).

**Ice and snow screen,** for FL23 and T2N, as Stage 22: drop a pair if either scene's disk TOA B03 > 0.15 or L2W B03 > 0.05.

**Sun.** S2C pairs count only if the S2C scene's sun elevation is ≥ 25° (90° minus the crop's solar zenith). Floor pairs are ≥ 25° by construction.

**Processing.** Every scene goes through the identical frozen, instrumented ACOLITE path, read lazily from Google Cloud (verified identical). FL23 and T2N use the same scene and gate code as Stage 22 (`stage20/lib20.scene`).

## 3. Floor quantities (both sensors through the identical path; S2B relative to S2A)

**Per valid pair:**
- d_b = log10(S2B/S2A) for B02, B03, B04, B05 (both > 0.001);
- Δp (visibility, log10);
- state overlap (the two states share a class);
- class jump (hard classes ≥ 2 apart);
- the posterior difference.

**Reported** for all valid pairs (pooled, primary) and per subtype:
- the median signed d_b, Δp and their IQRs;
- the distribution of |d_b| and |Δp| (P50, P90, P95);
- state overlap, class-jump rate and posterior difference.

**The legacy 3% bar,** |median d_b| ≤ log10(1.03) = 0.0128 for all four bands, is reported unchanged for the floor itself.

**Floor usable:** ≥ 100 valid pairs, ≥ 10 lakes, ≥ 3 regions, and |median Δp| ≤ 0.03 (two trusted sensors must agree systematically on visibility).

## 4. The operational equivalence envelope (frozen here, before S2C is scored against it)

**From the pooled valid FL23 pairs, per band b:**
- **E50_b** = the median of |d_b| (the typical disagreement between two trusted sensors on one pair);
- **E90_b** = the 90th percentile of |d_b|.

**Also:**
- V90 = the 90th percentile of |Δp|;
- O = the floor's state overlap;
- J = the floor's class-jump rate.

**Why these:**
- **Pooled floor, not the tandem subset.** The question is whether S2C behaves like a trusted sensor *in operation*, and the live consensus combines passes from different days and viewing geometries. The pooled floor measures the disagreement those operations already accept between two certified sensors. The tandem subset is the geometry-matched comparison; it is reported beside it as a sensitivity and does not gate.
- **The systematic bound is the median.** A systematic S2C offset, unlike pair noise, does not average out in consensus. So the bound on S2C's *median signed* offset is the floor's *typical* (median) disagreement, not its 90th or 95th percentile.
- **The 90th percentile bounds the spread.** It is applied only to same-water pairs.
- **Visibility keeps the legacy limit, 0.03 log10.** It is a visibility bar, never lowered or raised.
- **State and class jumps** use the form Stage 20's code already applies to its floor: overlap ≥ min(0.95, O − 0.03), jumps ≤ J + 0.02.

## 5. Low-sun guard

**Rule:** S2C with sun elevation < 25° can never receive full authority. The threshold is exactly 25° and is not tuned.

**What low-sun S2C keeps:**
- its existing lower-authority semantics (Stage 16 product with S2C lower authority, C3 path);
- never Strong;
- never counted as a full-authority prior view.

## 6. Conditional full authority (C3 nominal S2C, sun ≥ 25°)

**Gating strata (each needs ≥ 15 valid pairs):**

| Stratum | What | Criteria |
|---|---|---|
| TH25 | Winter tandem, same water (~30 s), S2C sun ≥ 25° | **All** of: \|median d_b\| ≤ E50_b and P90 of \|d_b\| ≤ E90_b for each band; \|median Δp\| ≤ 0.03 and P90 of \|Δp\| ≤ V90; state overlap ≥ min(0.95, O − 0.03); class jumps ≤ J + 0.02 |
| T2H25 | Warm 2-day, N0511/N0512 | Systematic only (spread is inflated by 2 days of real change): \|median d_b\| ≤ E50_b each band; \|median Δp\| ≤ 0.03 |
| T2N | Warm 2-day, N0513 (fresh) | As T2H25 |

**Stable across processing baselines.** Each must have ≥ 15 valid pairs at sun ≥ 25°, |median Δp| ≤ 0.03 and |median d_b| ≤ E50_b:
- N0511 (TH25 plus T2H25's N0511 pairs);
- N0512 (T2H25's N0512 pairs);
- N0513 (T2N).

**Reported, not gating:**
- the legacy 3% result for every stratum;
- the tandem-subset envelope against TH25.

## 7. Secchi validation (only after section 6 is evaluated and recorded)

**Rows:** every eligible S2C truth row (Stage 22's re-runs: raw = K0; C3 = C1 + B05 adjustment).

**Reported separately for:**
- sun ≥ 25° and < 25°;
- warm (Apr–Oct) and winter (Nov–Mar);
- the dev, cert and fresh pools, all previously seen.

**For the ≥ 25° subset, for C3, raw S2C and the S2A/B reference:**
- operational and the four class scores;
- signed bias, harmful, severe;
- ⅔-interval coverage and median feet error.

**Reference** = S2A/B truth rows with sun ≥ 25° (matched to the subset's condition).

**Checks entering section 8, C3 ≥ 25° against the reference ≥ 25° (the Stage 20–22 full-authority checks):**
- harmful ≤ reference + 0.05;
- severe ≤ 0.02;
- |bias − reference bias| ≤ 0.05.

Stage 12 is historical only.

## 8. Authority decision

| Outcome | Condition |
|---|---|
| **B — LOWER** | The floor is unusable (section 3), or any TH25 criterion fails |
| **C — PARTIAL** | TH25 passes, but T2H25 or T2N fails, a baseline is not evidenced or fails, or a section 7 check fails |
| **A — CONDITIONAL FULL AUTHORITY** | Everything in sections 3, 6 and 7 passes |

Under A, S2C/C3 is full authority only when all of these hold:
- sun ≥ 25°;
- a supported nominal baseline (N0511, N0512, N0513, or a later nominal equivalent);
- all normal quality gates pass.

Low-sun S2C stays lower authority (section 5). A is not forced; B and C are reported as they fall.

## 9. Live causal consensus (only under A)

**`dev23.py`** = `stage19/dev19.py` executed verbatim with the `stage21/dev21.py` pattern of asserted patches, changed only in these respects:
- **(a) Samples.** S2C anchors and prior passes are predicted from their C3 samples (`stage22/res22_truth` C1, plus the re-run `_res_syke` row) with the B05 adjustment. An S2C scene without a valid C3 sample is dropped. Fold models are trained exactly as in Stage 19.
- **(b) Authority.** S2C scenes with sun ≥ 25° are full-authority platforms: consensus, agreement count, prior state, guard and diagnostics. S2C scenes with sun < 25° are excluded from full-authority use exactly as Stage 19 excluded all S2C (S-off).
- **(c) Anchors' Stage 16 product.**
  - S2C anchors at ≥ 25°: re-issued at full authority from the C3 prediction (fold posteriors, as `dev21` base20).
  - S2C anchors at < 25°: the C3 lower-authority product (`product16` with platform sentinel-2c).
- **(d) Windows:** 5, 10 and 15 days, all primary. Selection is Stage 19's rule:
  1. candidates pass the Stage 16 bars;
  2. best = the highest operational score;
  3. choose the smallest window whose operational and stained lake-bootstrap CIs against the best both include 0.
- **(e) No future scene.** The age ≥ 0 assertion is kept.

**Reference R0 (Stage 22 live development).** The same code with every S2C scene at lower authority and S2C anchors on the C3 lower-authority product, 5-day window. Its reproduction of the Stage 22 figure (operational 0.7103) is reported. Any difference is explained, never adjusted.

## 10–15. Reporting (under A for the consensus parts; the diagnostics in all cases)

**Evidence density.** Before (R0, S2A/B only) and after (S2A/B plus S2C ≥ 25° with a valid C3 sample), for all events and 2025–26 events (truth date ≥ 2025-01-21):
- the share with 0, 1, 2 and ≥ 3 independent prior full-authority views, per window;
- the share of current-era answers with ≥ 1 recent prior full-authority view;
- the median age of supporting passes;
- the number of passes supporting Strong;
- S2A/S2B/S2C contribution shares.

Without A, the "after" counts are reported as hypothetical availability (counts only, no scoring).

**Strong:**
- share and accuracy;
- median number of supporting passes and median age;
- share by class.

**Stained:** Stage 16 single scene, R0 and Stage 23, each with:
- operational and truth-in-answer;
- harmful, severe and Unknown share;
- median |log10| feet error and mean posterior.

Plus a lake-bootstrap of the Stage 23 stained score against Stage 16 (B = 2000, seed 23, 95% CI).

**Harmful taxonomy (diagnostic only; no rule is tuned on it).** For every harmful row of R0, and of Stage 23 if run. Categories are non-exclusive:
1. too murky (the truth class is clearer than every class in the answer);
2. too clear (the truth class is murkier than every class in the answer);
3. boundary state (the answer is a two-class state);
4. stale anchor (|truth date − scene date| ≥ 3 days);
5. stale-prior disagreement (a used prior pass ≥ 3 days old whose own state is disjoint from the anchor's);
6. low-sun S2C involved (the anchor or a used scene is S2C below 25°);
7. algae-flagged (the product's algal modifier is set);
8. tier 2;
9. single scene only (no consensus, or one scene used);
10. multi-scene disagreement (consensus with a disjoint state, or fewer agreeing scenes than used);
11. high posterior but wrong (posterior ≥ 0.90);
12. low evidence, arguably Unknown (posterior < 0.70).

For each category: its count, its share of harmful rows and its harmful rate within its own population. The top 2–3 causes are by count, with the rate shown.

**Severe audit.** Every severe row, with:
- truth and answer;
- scene age and satellite;
- authority and evidence level;
- algal state and posterior;
- the number of independent passes, and whether S2C participated;
- whether a Strong-only rule or an Unknown-below-0.70 rule would have removed it (diagnostic, not adopted).

**Exact feet:**
- median multiplicative error (10^median |log10 error|);
- signed bias;
- ⅔-interval coverage and feet availability;
- each by class and by evidence level;
- the Stage 13 capability score.

## 16. Adoption of a new live consensus (only under A)

Stage 23 replaces R0 as the development candidate only if **all** of these hold:
- the Stage 16 freeze bars pass;
- operational improves by ≥ 0.02 over R0, with the lake-bootstrap 95% CI lower bound > 0;
- stained does not regress (Δ ≥ −0.01);
- harmful does not materially worsen (Δ ≤ +0.01);
- severe does not materially worsen (Δ ≤ +0.002);
- Strong truth-in-answer ≥ 0.90;
- no future scene is used;
- exact-feet capability stays ≥ 8/10.

Otherwise it is not adopted.

Under A without adoption, S2C ≥ 25° is still recorded as conditionally full authority (an evidence rule). The development candidate stays R0.

## 17. Development 8/10 checkpoint (frozen)

**All of:**
- operational ≥ 0.75;
- weakest class ≥ 0.65;
- harmful ≤ 10%;
- severe ≤ 1.0%;
- Strong share ≥ 25% of usable answers;
- Strong accuracy ≥ 90%;
- exact-feet capability ≥ 8/10.

**Why these:** the brief's suggested rubric, kept as given. Each bar sits between the Stage 16 freeze bars (7/10) and the true 9/10 bar, so it is a real step and not tuned to any result.

## 18. True 9/10 (unchanged)

**All of:**
- operational ≥ 0.85;
- weakest class ≥ 0.80;
- harmful ≤ 5%;
- severe ≤ 0.5%;
- Strong share ≥ 50%;
- Strong truth-in-answer ≥ 90%.

## 19. Internal map

**If a new candidate results** (adoption, or A for single-scene S2C answers), it appears on the normal Sector Mapbox Water Clarity layer for master accounts, with:
- Candidate status;
- observation time and age;
- evidence and satellite;
- the S2C path.

A low-sun S2C answer says so in the detail card only.

**Public users are unchanged.**

## 20. Status of the evidence

**Every truth pool has been seen before.** Stage 23 is development research. A development score is not certified and not deployed, and no reused pool is called blind.
