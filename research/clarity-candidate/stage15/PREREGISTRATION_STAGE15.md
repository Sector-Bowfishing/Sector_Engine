# Stage 15 pre-registration: final product semantics and the re-score

Written 2026-10-01, before any development quantity for the new semantics was computed. The development rows were last
evaluated in Stage 14. Only these were checked:
- that the engine files match their Stage 14 hashes;
- the count of development and certification rows by platform and tier.

This file's sha256 goes into `FREEZE_STAGE15.json`.

**What the re-score is.** The Stage 14 certification set was unsealed and scored in Stage 14. Its findings motivated
this stage, so re-scoring it is **not a blind certification**:
- every parameter below is derived from development rows only;
- the readiness decision (section 8) requires the development rows to pass as well.

## 1. The engine (unchanged)

These Stage 14 files are used unchanged and their hashes are re-checked:
- `engine/engine14.py`, `frozen_engine.json`, `frozen_gbm.pkl`;
- C-gbm, ACOLITE K4, lake-elevation pressure, the tiers, S2C V-ρw, the 60 m disk and the two-thirds interval.

Stage 15 adds a display and authority layer only. The numeric prediction p is never changed.

## 2. Clear-to-Normal

- **The band.** The Stage 14 method, at b = 6 ft: a logistic P(y ≥ b | d) on development lake-held-out predictions with
  |d| ≤ 0.30 (tiers 1–2). Its edges sit where P = 1/3 and 2/3. Each edge is at least 0.05 from b, and the band contains
  b.
- **Fitting.** Nested inside training folds for development evaluation; pooled for production.
- **States.** p inside the band gives **Clear-to-Normal**. Where two bands overlap, the nearer boundary wins (Stage 14
  rule). The Normal-to-Stained and Stained-to-Limited bands are unchanged from Stage 14.
- **Adoption.** Clear-to-Normal is adopted only if, on development rows (nested), both hold:
  - the class-balanced operational score (section 6) rises;
  - the full-authority wrong-answer rate falls.

## 3. The very-clear floor (display only)

- **Trigger T** ∈ {10, 12, 15} ft. The lowest candidate at which development rows predicted ≥ T (tiers 1–2,
  lake-held-out) have median |log error| > 0.15. That is the point where exact feet stop meeting the Stage 12 clear
  SUPPORTED error bar. If no candidate exceeds it, there is no floor.
- **Displayed bound D** ∈ {8, 10, 12, 15}, with D ≤ T. The largest candidate with P(truth ≥ D | p ≥ T) ≥ 2/3, the same
  2:1 standard as the bands.
- **The display.** When p ≥ T, the answer is the Clear state with "**D+ ft**" (at least D ft). Exact feet and the interval
  are withheld; p is unchanged. Tier-3 Clear answers follow the same rule.
- **Fitting.** T and D are chosen on development rows pooled lake-held-out, and checked nested.

## 4. Algal water (authority only)

**The existing detection:** NDCI = (B05 − B04)/(B05 + B04) on the answering reflectance, the Stage 10/11 satellite
algal flag.
- **Moderate:** 0.03 < NDCI ≤ 0.10.
- **Strong:** NDCI > 0.10. On the Mishra & Mishra (2012) relation, NDCI 0.03 is about 17 µg/L chlorophyll and 0.10
  about 25.

**The rule, per level, from the development decision precision of the states issued to flagged rows:**

| Development precision | Behaviour |
|---|---|
| ≥ 0.75 | **Modifier.** State kept at full authority; feet shown as "~X ft"; "Algal water detected — elevated uncertainty" |
| 0.60 – 0.75 | **Softened.** A single-class state is replaced by the boundary state nearer to p (Clear → Clear-to-Normal if adopted, otherwise kept); lower authority; feet "~X ft"; the modifier |
| < 0.60 | **Withheld.** No class: "~X ft visibility · Algal water detected — elevated uncertainty"; state Unknown / Low Authority (algal) |

Under "Withheld", the "~X ft" figure shows only if feet in algal-flagged development water meet the PARTIAL feet bars:
median |log| ≤ 0.20 and |median signed| ≤ 1.5 ft.

## 5. Sentinel-2C (authority only, temporary)

- **The rule.** Every Sentinel-2C answer at tiers 1–2 keeps its state but is marked **lower authority**, and its exact
  feet and interval are withheld. Tier-3 S2C answers are already lower authority; their feet are withheld too.
- **No recalibration.** No bias correction is applied.
- **When it lifts.** At least 60 independent S2C certification rows with |median signed log| ≤ 0.05 and decision quality
  within 0.05 of S2A/S2B.
- **The cost**, reported as:
  - the share of rows affected, in the certification set and in 2025-dated rows;
  - the S2C rows' development and certification performance.

## 6. The operational rubric (frozen here, before the re-score)

**The question it answers:** would this output help a bowfisher make the right visibility decision, without pretending
to know more than the satellite supports?

**Each row gets one outcome and a score:**

| Outcome | Condition | Score |
|---|---|---:|
| Correct single state | Full authority; a single class equal to the truth | 1.0 |
| Correct boundary state | Full authority; a boundary state containing the truth | 0.9 |
| Correct very-clear floor | "D+ ft" and truth ≥ D | 1.0 |
| Floor, clear but below D | "D+ ft" and 6 ≤ truth < D | 0.75 |
| Correct lower-authority answer | Tier 3, S2C or algal-softened; the answer contains the truth | 0.75 |
| Wrong lower-authority answer | Flagged, but does not contain the truth | 0.25 |
| Appropriate Unknown | Nothing to say, or the withheld answer would have been wrong | 0.5 |
| Unknown that withheld a right answer | | 0.25 |
| **Harmful wrong answer** | Full authority, does not contain the truth (including a floor with truth < 6 ft) | 0.0 |

- **Severe:** a harmful answer whose classes are ≥ 2 classes from the truth.
- **The withheld answer:**
  - for tier-3 Unknown, the state C3-Sen2Cor's own bands would have issued;
  - for algal-withheld rows, the state before withholding;
  - with no reading at all, nothing (appropriate).
- **The score.** OPERATIONAL BOWFISHING CLARITY CAPABILITY = round(10 × the mean, over the four true classes, of each
  class's mean row score).
- **Also reported:** the overall mean, the harmful rate and the severe rate.

## 7. The other rubrics, kept for comparison

- **Exact feet** (Stage 12, as coded): floor answers count as feet withheld. The same score is also reported with the
  floor treated as a bound.
- **Original hard class:** the hard class of p, unchanged.
- **Boundary-aware product** (Stage 14 section 8):
  - Clear-to-Normal and the floor count as states;
  - S2C and algal lower-authority answers count as not answered at ACOLITE authority.

## 8. Readiness to freeze and move on

**CURRENT CLARITY READY TO FREEZE AND MOVE TO WATER TEMP: YES** only if all of these hold on **both** the development
rows (nested) and the certification re-score:
1. The engine is unchanged.
2. Operational capability ≥ 7/10.
3. Every true class has a mean operational score ≥ 0.60.
4. The harmful rate is ≤ 15%, and the severe rate ≤ 2%.

Otherwise NO.

**What a YES does and does not mean.** It ends development. It does not move product readiness: the Stage 10 rule still
applies, and production is unchanged.

## 9. The re-score

- **The rows.** The Stage 14 certification rows, ACOLITE samples and truth are used unchanged (hashes re-checked). No
  redraw.
- **The breakdowns:**
  - exact feet, hard classes and states;
  - Clear-to-Normal, the floor and the algal behaviour;
  - S2A, S2B and S2C;
  - warm and cool season;
  - tiers 1, 2 and 3.
- **Apart from the verdicts.** SYKE is reported apart.
