# Wind Brain — cross-Brain opportunities (documentation only; no other Brain modified)

Wind provides the **wind/exposure state**; each owner keeps its science.

| Brain | Wind output | What the owner could do | Evidence/readiness |
|---|---|---|---|
| **Clarity** | per-bank effective fetch and exposure class for the last N hours at the forecast speed history; "hours above 8/12 mph over fetch ≥ 1 km" | Clarity owns resuspension: wind hitting a shallow flat with long fetch → higher resuspension risk. Needs depth/bed type (Depth Brain) which Wind must not own. | Geometry/hours exist; relationship not validated (Clarity decides) |
| **Depth** | wind-FROM and fetch per bank | Depth owns "shallow flat"; combine to flag exposed flats. Also water-level changes alter fetch (full-pool polygon is static) | Needs Depth water-level/bathymetry contract |
| **Vegetation** | same exposure class per bank | Sheltered coves hold weed; exposed banks scour. Vegetation could use `PROTECTED` persistence | Hypothesis only |
| **Sector Intelligence** | tonight block: from-direction (compass), strength class, breezy-risk flag, trend, per-bank exposure at mean and P90 speed, confidence word | Rank banks and write "start here" guidance (the research-only `rank_banks_for_wind` and `nearby_alternatives` logic belongs there per the ownership matrix); apply thresholds in one place (≈ 11 wind threshold sets exist today) | Validation in `WIND_FORECAST_VALIDATION.md`; contract fields below |
| **Water Temp** | none | Wind-driven mixing affects surface temperature; owner decides | Not researched |
| **Lake Brain** | none | Supply polygon + confidence (already does); fetch generator should consume it | Done in this campaign read-only |

## Suggested additive fields (proposal, not applied)
`tonight{ fromCardinal, strengthClass, breezyRisk:bool, trend, confidence, validFrom/To }`, `exposure.byBank[]{classMean, classP90, label:DIRECT|CROSS|PROTECTED, highFetch:bool}` in the per-bank storage object, `profile.tier: AUDITED|ESTIMATED|POINT_ONLY`. Unknown stays null, never "calm".

## Boundaries kept
Wind does not say a bank is "good", does not model clarity, depth or species, and does not turn exposure into a fishing score.
