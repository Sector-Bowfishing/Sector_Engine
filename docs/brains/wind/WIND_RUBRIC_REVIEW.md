# Wind Certification rubric — review for bowfishing usefulness (documentation only)

Canonical score unchanged: **Certification 3.1 / 10** (rubric v1), **BWIS v1 5.4 / 10**. No rubric text, weight, cap or scorer was edited. This is input for a separate rubric decision.

## Dimension-by-dimension
| # | Dimension (pts) | Improves bowfishing? | Concern |
|---|---|---|---|
| 1 | Speed (12) — night MAE/bias plus **≥ 15 mph event POD ≥ 0.5 & FAR ≤ 0.5** | Partly. MAE/bias matter. | ≥ 15 mph nights are ≈ 0.1% of station-hours (13 in 5 months); the event gate scores 0 for a forecast that is excellent at the 5–12 mph band where bank choice flips. Rewards an extreme case, and no tested source can meet it. |
| 2 | Direction (8) — within 22.5° over **all hours** with speeds ≥ 2.6 m/s | Yes, but mis-weighted. | Includes daytime and 6–8 mph drift. At night with forecast ≥ 5 mph the same forecast scores 0.81–0.97. Night/speed-weighted direction would match use. |
| 3 | Gust (5) — conditional bias plus **≥ 20 kt POD ≥ 0.6** | Marginal. | Gust events are rare and no source forecasts them; bowfishing uses "gusty tonight?" qualitatively. Better asked as a probabilistic risk. |
| 4 | Lead (5) | Yes (tonight skill vs persistence). | Fine. |
| 5 | Fetch method (10) | Yes (bank answer rests on it). | Fine; but ESTIMATED polygon fetch has no route to credit until matched per-bank validation passes. |
| 6 | Exposure field-validated (20) | **Yes — the most bowfishing-relevant item.** | Needs bank-pair truth (hardware/volunteers); correct to keep. |
| 7 | Surface field-validated (20) | Yes (practical roughness). | Needs the same field programme. |
| 8 | Reliability (8) | Operations hygiene. | Not wind knowledge; automatic by ≈ 2026-11-07. |
| 9 | Coverage (4) — 4 lakes + 50 QA'd | Weak. | Coverage that exists as AUDITED tables; ESTIMATED tier (473 lakes) earns nothing and rightly so. |
| 10 | Provenance / Unknown / explanation (8) | Yes (honesty). | Fine. |

## What the rubric does not value but customers do
1. **A probabilistic "could turn breezy" signal** (research: 19× lift, POD 0.49) — no place to score it.
2. **Tonight trend ("easing")** and honest withholding of lay-down/rising.
3. **Direction when it is reliable** and explicit suppression when it is not.
4. **Bank-impact vocabulary at fleet scale**, with tiers (AUDITED / ESTIMATED / POINT_ONLY).
5. **Confidence labels that are ordered** (H2-C1/C2).

## What it rewards that bowfishing mostly does not
≥ 15 mph / ≥ 20 kt event skill, all-hours direction, reliability and coverage counts as points of knowledge.

## Option space (not decided)
A. Keep v1 as the strict certification; add a separate bowfishing-weighted score (BWIS v2) with night/≥ 5 mph direction, probabilistic risk-flag skill (lift/POD at 8–10 mph) and tonight category skill.
B. Revise dims 1–3 to score the 5–12 mph band and a P90 risk flag; keep field dims 6–7 untouched.
C. Leave all as is; accept the score will track field evidence only.
Any change must be pre-registered before looking at H2, versioned (no in-place edit), and the old score kept alongside.

## Score discipline
Cleaner implementation earns no certification points. Likely score movement, in order: reliability (+8 raw, ≈ 2026-11-07), field evidence (dims 6/7), over-water reference (lifts the 7 cap). Nothing in this branch changes the 3.1.
