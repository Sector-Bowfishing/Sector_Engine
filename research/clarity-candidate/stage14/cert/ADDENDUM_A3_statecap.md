# Certification addendum A3: the state cap over the whole US core (value-blind)

Recorded 2026-10-01, after the value-blind blind checks and before any certification Secchi, chlorophyll or turbidity
value was read.

**What was seen.** `finalize_wqp.py` capped each state at 15% of the WQP part. With the NLA rows added, Minnesota is
15.7% of the US core. That fails the section 5 check: no state above 15% of the US core. Every other check passes.

**Change.** The cap is applied to the combined US core, as section 5 requires. While any state is above 15% of the US
core, its last-selected WQP row is removed, in the selection order of `finalize_wqp.py`. The original sample is kept as
`wqp_sample_pre_a3.csv`.

**Why it cannot bias the score.** The rule reads only states and the seeded selection order.
