# Spatial model: scoring areas of a lake

**Status:** design and validation path only. No production map is built here. Depth and Vegetation Brains do not exist; nothing below is counted as current capability.

## 1. What spatial support exists today
| Input | Best current resolution | Source of truth |
|---|---|---|
| Wind | per-bank effective fetch / Hm0 / exposure class (4 pilot lakes; stored as a gz file, not RTDB; not field-validated). Lake state is one representative point | Wind Brain |
| Water temperature | one lake-wide value (`spatialSupport: lakeWide`) | Water Temp Brain |
| Clarity | lake-level with an 80% range; per-arm fusion exists as unshipped research | Water Clarity Brain |
| Depth | none as a Brain. One binary 9 ft contour on one lake in the iOS app; modeled mean depth proxy for 621 lakes | (Depth Brain does not exist) |
| Vegetation | none as a Brain. Lake-level satellite `grassPct` (566 lakes) and NWI aquatic-bed share are indirect indicators | (Vegetation Brain does not exist) |
| Lake level | per lake | Lake Brain |
| On-device FishIntel | ~200 m shoreline segment + littoral water, Guntersville only | not a Brain |

**Finding:** only Wind (4 lakes) has any bank-scale quantity published by a Brain. A genuine zone ranking cannot exist on today's inputs for any lake; at most a *wind-exposure* ordering of banks on four lakes.

## 2. The zone model

**Unit:** a *zone* is a contiguous stretch of shoreline plus the shootable water in front of it, big enough to fish for an hour and small enough that one wind/depth/vegetation state describes it. The on-device ~200 m segment is a proven unit for one lake; Intelligence should consume zones from whichever Brain owns geometry (Lake Registry / Lake Brain), never define its own. Zones are keyed by `lakeId + zoneId` with the geometry version in provenance.

**Per-zone factor record** (the same record the prototype uses):
`{fid, value, unit, kind, support, ageHours, staleAfterHours, horizonHours, brainConfidence, source@version}`
where `support ∈ {BANK_AREA, LAKE, POINT, NONE}`. A lake-wide input used for a zone decision is capped at MEDIUM confidence (rule R6) and the caveat is printed ("water temperature is lake-level, not specific to this zone").

**Zone inputs**
| Factor | From | Used for |
|---|---|---|
| exposure-adjusted wind / expected chop | Wind (per-bank) | can I see through the surface here tonight; is the bank protected |
| effective depth, shallow share, flats, channel edges | Depth (future) | where shallow-feeding species can be, and shootable |
| vegetation presence, density, broad type, season state | Vegetation (future) | cover/forage for vegetation users, obstruction for the shot |
| clarity | Clarity (lake or arm) | sightline |
| temperature | Water Temp (lake, later shallow-vs-main delta) | species state |
| level trend | Lake Brain | flats gained or lost |
| species response bands | Biological | what each factor means for each fish |

**Algorithm:** identical to the lake-level model. Rate each zone per species with the same rules; rank by (rating, confidence, #FAVORABLE). No spatial smoothing in the first version (smoothing invents agreement between neighbours). Priority *areas* (merging adjacent strong zones) are a presentation step over already-rated zones, not a new score.

## 3. Graceful degradation (the common case for a long time)
| Available | Answer given |
|---|---|
| lake-level inputs only | lake-level rating per species + "which bank" only when Wind exposure exists; otherwise "no zone ranking available" |
| + Wind per-bank | wind-protected banks ranked; other factors listed as lake-level caveats |
| + Depth (modeled) | zone rating possible but confidence ≤ MEDIUM; top class blocked by R9 if Depth brain label is LOW |
| + Vegetation | vegetation-using species get full zone ranking |
| + measured shallow temperature / arm clarity | confidence can reach HIGH |

The system must say which level it is operating at, per lake, in the output.

## 4. Validation path for spatial claims (before any user-facing map)
1. **Offline consistency:** zone ratings must be stable under small input perturbations (rating changes at most one rung for ±1 unit) and monotone in each factor. Property tests exist in the prototype; extend them to real Brain fixtures.
2. **Blind area ranking** (trusted beta testers): before a trip the app records the top and a lower-ranked zone for the same species and night; the tester fishes both for fixed time in random order and records **species-specific sightings in range per effort-hour**, plus a zone-level condition note. Power: roughly 30–80 paired visits per lift claim (see `VALIDATION_STRATEGY`).
3. **Field verification of the inputs themselves:** shallow depth by sounder/lead line at ≥50 points per pilot lake; vegetation by photo transects; wind exposure by a handheld anemometer + wave-height classification at banks. These validate the *Brains*, not Intelligence, and are tracked as upstream blockers.
4. **Do not validate Intelligence on a map nobody can trust.** If Depth or Vegetation is modeled, the zone ranking is labelled UNCONFIRMED and excluded from the validation claim.

## 5. Risks
- The on-device model shows that segment ranks can look decisive while 38% of segments are `habitatUnknown` from depth; the unknown must be surfaced in the output, not hidden by the percentile rank.
- Zone geometry drift between Brains (Wind's NHD polygons vs a future Depth lattice): require a shared geometry version in provenance.
- Edge effects: a zone with strong inputs next to dam or restricted water; keep restricted/legal as a gate with its own source.
