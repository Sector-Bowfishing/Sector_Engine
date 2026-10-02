# Addendum B2: correction to Addendum B

Recorded before any certification match was counted toward the sample. No Secchi, chlorophyll or turbidity value has been
fetched or seen.

**Error.** Addendum B read the flag `earthsearch:boa_offset_applied=true` on the 2022 scenes of `sentinel-2-l2a` as "use
ρ = DN × 0.0001 − 0.1". In fact the offset has already been applied to those scenes' DNs. Subtracting it again sent
water negative: the median red over the 2022 disks was −0.069, and the red ≤ 0 gate removed nearly every pixel.

**Correction.** For `sentinel-2-l2a` in both 2017 and 2022, ρ = DN × 0.0001. The 2022 NLA matches, and SYKE's 2022 rows,
are rerun with it. The 2017 conversion was already right (median red 0.027).
