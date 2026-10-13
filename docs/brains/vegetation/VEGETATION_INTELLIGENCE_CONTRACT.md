# Vegetation → Sector Intelligence contract (shadow)

Intelligence reads `states/vegetation.forIntelligence`:

```jsonc
{"presence": "PRESENT|NOT_OBSERVED|UNKNOWN", "broadType": "SURFACE_REACHING_MIXED|UNKNOWN", "coverageClass": "NOT_CALIBRATED|SPARSE|MODERATE|DENSE|UNKNOWN",
 "seasonalState": "UNKNOWN|...", "observationAgeDays": 4, "evidenceKind": "SATELLITE_PERSISTENCE", "confidence": "LOW", "stale": false}
plus `limitations[]`, `potentialHabitat` (separate, potentialOnly), `validation.state`, `geometry.tier`.
```

## Separation of concerns
| Question | Owner |
|---|---|
| Is there surface vegetation, where (cells), how old is the look, how sure are we? | **Vegetation** |
| Do the fish we care about use that vegetation this week (habitat VALUE)? | **Biological** (species × season × habitat) |
| Can a bowfisher actually shoot / move through it (SHOOTABILITY / OBSTRUCTION)? | **Intelligence**, from Vegetation coverage/density + Depth + Clarity + conditions |
| What do we tell the user? | **Intelligence** |

Dense vegetation can be excellent fish habitat **and** poor shooting water. Vegetation therefore publishes neither `habitatValue` nor `shootability` nor `obstruction` (test enforces the absence of those keys).

## Rules for consumers
1. Treat `UNKNOWN` as "no information", never as "none". Only `NOT_OBSERVED` means a valid look found nothing, and it is bounded by `observationAgeDays`.
2. `coverageClass: NOT_CALIBRATED` means presence/counts only: do not turn it into a density claim.
3. `potentialHabitat` is evidence about where vegetation *could* exist; weight it below any observation, and word it with the Brain's own language (`Potential vegetation habitat`).
4. `validation.state` < `PARTIAL` ⇒ the strongest permitted wording is "Likely surface vegetation".
5. `seasonalState: UNKNOWN` is the default; do not substitute a calendar guess.
6. `submergedVegetation.observed` is always `false`; Intelligence must not infer observed submerged cover from depth or clarity.

## Versioning
Adding fields is additive; changing a closed vocabulary or a field's meaning bumps `schemaVersion` and requires the consumer's fixture update. No consumer change is made in this phase (Intelligence is not modified).
