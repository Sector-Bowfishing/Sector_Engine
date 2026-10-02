# Certification addendum A2: a stricter prescreen and a second draw (value-blind)

Recorded 2026-10-01, before any certification Secchi, chlorophyll or turbidity value was read. The only inputs to this
decision are the extractor's own value-blind outputs: n_valid, item and scene cloud for the 553 events extracted so far.

**What was seen.**
- **The yield is low.** Only 59 of those 553 events (11%) matched with ≥ 5 valid pixels. At that rate, the first draw
  gives about 330 WQP observations, against the protocol's cap of 900.
- **Scene cloud predicts the match.** Events whose best item has `eo:cloud_cover` ≤ 20% matched 31–32% of the time.
  Above 20%, the rate was 1–5%.
- **The cost.** Each extracted event costs about 300 MB of COG reads, and the link is saturated.

**Change.**
1. **Stricter prescreen.** Every event not yet extracted is prescreened again and goes to the extractor only if an item
   within ±1 day has `eo:cloud_cover` ≤ 20%. Events already extracted are kept as they are.
2. **A second draw.** 7,000 more site-days, taken in the frozen seeded order of section 4 (seed 20261015):
   - it continues past the first draw;
   - per-lake (≤ 6) and site-month limits are counted across both draws, and the 15% state cap applies within the draw;
   - it is prescreened at ≤ 20% and extracted in the same way.
3. **Unchanged.** The final-sample rule (≤ 3 per lake, October–April first; ≤ 15% per state; ≤ 900) and every other rule.

**Why it cannot bias the score.** Cloud cover and the draw order are independent of the Secchi values, which stay
sealed.
