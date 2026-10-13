# Wind Brain — what legitimately raises the score

Rubric read from `WIND_STAGE_2_…md` (certification v1) and `WIND_BOWFISHING_SCORE_V1.md` (BWIS v1). **Not modified.**

## A. Certification (now 3.1; raw 31.3)
Earned: dim2 4.3 · dim4 5.0 · dim5 10 · dim9 4 · dim10 8. Remaining: dim1 12, dim2 3.7, dim3 5, dim6 20, dim7 20, dim8 8.

| Target | Raw | What it requires | Can model/desk research deliver it? |
|---|---:|---|---|
| **4** | 40 | Reliability (+8, automatic ≈ 2026-11-07 if uptime holds) → 39.3 | Yes; ≈ 4.0 by waiting. |
| **5** | 50 | 39.3 + ≥ 10.7 more | Only partly: dim2 maxes at +3.7 (needs ≥ 0.85 within 22.5° on **all** hours; now 0.758); dim1/dim3 event conditions need ≥ 15 mph POD ≥ 0.5 at FAR ≤ 0.5 and ≥ 20 kt gust POD ≥ 0.6; no tested source does this. So 5 needs **field** points (dim 6/7). |
| **6** | 60 | Reliability + ≈ 20.7 from dims 6/7 (e.g. dim7 ≥ 55%, dim6 ≥ 50% credit) | **No** — needs bank-pair and surface field data (two-lake network; ≈ 2–4 months after install). Cap 6 lifts only with field truth. |
| **7** | 70 | Reliability + dims 6 and 7 together ≥ 30.7/40 | No (field). 7.0 is the land-only ceiling (over-water cap). |
| **8** | 80 + gates | Over-water reference + dims 6/7 ≥ 70% + **dims 1 and 2 at full credit** + 30 live days + 4 lakes | Not credible on current evidence: dims 1–2 full is blocked by NBM missing windy events. |
| **9–10** | 90+ | All of 8 plus dim 3 and 80%+ field skill | Not credible today. |

Honest ceiling with **no new physical truth**: ≈ 4.3 (reliability + dim2 full, which itself is not reachable).

## B. BWIS v1 (now 5.4; 54.1/100)
| Target | Needs |
|---|---|
| ~5.7 | 30 live days (E2 → +2.6) — automatic |
| ~6 | Model-side only: A4 windy MAE, D1 at long fetch, C2 exact, M4-style transient (C3); the prior session judged "realistically model-only work tops out around 6" |
| 7–8 | B3 (7) + D2 (10) = **17 pts of physical bank-pair truth**, plus a promoted transient model (C3 +5) |
| 9+ | D1 ≥ 0.8 at long fetch = windy-hour forcing accuracy (only an over-water nowcast sensor has shown a lever) |

## C. Does the rubric reward things bowfishing does not need? (documented concern)
1. **Dim 1 and dim 3 event gates are ≥ 15 mph / ≥ 20 kt.** At the 8 METAR stations 15 mph+ nights are ≈ 0.1% of station-hours (13 night-hour events at +1 h in V2; 7–13 per lead). Bowfishing decisions flip at **5–12 mph** over 0.5–5 km of fetch (Stage 3D.2 table; `WIND_FETCH_RESEARCH.md`). A forecast could be excellent at the decision-relevant 5–12 mph band and still score 0 on dim 1/dim 3. Evidence from this campaign: tonight breezy-risk flag from NBM P90 (≥ 10 mph) has POD 0.49, 19× lift (V7), but the rubric has no place for a *probabilistic* flag.
2. **Dim 2 direction is scored over all hours with forecast and observed ≥ 2.6 m/s (5.8 mph).** This includes dawn/afternoon hours bowfishers do not hunt, and weak breezes where direction barely matters for bank choice. On night hours where the *forecast* is ≥ 5 mph the same NBM direction is within 22.5° 0.77–0.81 of the time (≥ 10 mph: 0.92–0.97). Night-weighted or speed-weighted direction would better match the product; an independent review decision, not a research one.
3. **Dim 8 (reliability, 8 pts) and dim 9 (coverage, 4 pts)** are operations, not wind knowledge; BWIS E is smaller (5 pts) and more honest about that.
4. **Dims 6 + 7 = 40 points of the certification require field/over-water physical truth.** That is correct in principle (we should not certify unvalidated exposure), but it means desk science of the kind done in this campaign cannot move the certification score at all. BWIS spreads this more sensibly but still has B3/D2 = 17 points of unreachable-without-hardware.
5. **BWIS D1 favours high-biased forcing** (prior session's own flag) and uses the texture floor, which cannot represent wind shelter: it cannot show a calm tree-lined cove in 15 mph wind.

Net: neither rubric rewards **tonight's trend, direction when it matters, a confidence/risk flag, or fleet coverage of bank exposure**. Those are the bowfishing-relevant advances; they are product value that the score will not register until a rubric review.

## D. Research-supported score (honest)
- Certification: **3.1 → 3.1.** Nothing in this campaign is rubric-earnable without hardware or time.
- BWIS: **5.4 → 5.4** under frozen v1. Shadow sensitivity, not official: re-scoring A3 on night/forecast ≥ 5 mph/lead ≤ 12 h (≈ 0.81 within 22.5°) would give ≈ 6.0 of 7 vs 4.4 now → ≈ +1.6 pts → 5.6.
- What *is* supported: the evidence for five product claims at known accuracy (see `WIND_RESEARCH_SUMMARY.md`).
