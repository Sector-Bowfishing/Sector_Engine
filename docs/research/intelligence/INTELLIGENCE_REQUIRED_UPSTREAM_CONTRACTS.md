# Required upstream contracts: what Intelligence needs from each Brain

**Status:** proposal from the Intelligence side. No Brain is modified by this research. Each Brain owns its own science, schema and approval; these are the *consumer requirements* and the current gap. Common to all: every state carries `provenance` (brain@version, model version, generatedAt, sources), `freshness` (`staleAfterHours`, `stale`), a `kind` from the platform vocabulary, a spatial `support`, and a `confidence` label with a stated basis. Unknown is a value, not an omission.

## 0. Common record Intelligence reads (the "Factor")
```
{ factorId, lakeId, zoneId?, value, unit, kind (measured|observed|modeled|forecast|proxy|none),
  support (BANK_AREA|LAKE|POINT|NONE), geometryVersion?, generatedAt, ageHours, staleAfterHours,
  horizonHours?, confidence (HIGH|MEDIUM|LOW|UNKNOWN) + confidenceBasis, source: "brainId@version/model" }
```
The prototype's `Factor` is exactly this. Where a Brain does not yet publish a field, the row below says what Intelligence does in the meantime (always: UNKNOWN or an explicitly flagged interim).

## 1. Lake Brain
| Need | Today | Gap / ask | Until then |
|---|---|---|---|
| level state, trend, guide difference, flood-pool state | published for 5 pilot lakes (research: 273 lakes bindable under strict rules) | scheduling (stale on all pilots), coverage | level is UNKNOWN beyond pilots; the Engine's own level factor remains the customer path |
| species presence + confidence per lake | 5 pilots | fleet presence; presence confidence semantics | no species list ⇒ no species-first answer |
| level change → flats gained/lost | trend only | optional `areaChangePerFt` (best-validated fleet-wide capability per Depth audit) | none |
| zone geometry / registry | Lake Registry owns identity; shoreline segments exist only in the iOS app | one geometry owner and a versioned zone lattice | no zone answers |

## 2. Water Temp Brain
| Need | Today | Ask |
|---|---|---|
| `currentTempF`, kind, age, `spatialSupport` | published, CALIBRATION, lake-wide; 32 measured / 589 modeled (2026-10-12) | schedule the job (unscheduled ⇒ stale) |
| forecast per night | ≈4-day daily model | publish forecast skill vs persistence (not yet validated) |
| calibrated interval | none | planned 80% residual interval per lake class; Intelligence maps it to confidence |
| shallow-vs-main delta, `depthM` | `depthM` always unknown | shallow product is Water Temp's declared future; Depth supplies the depth interface |

## 3. Water Clarity Brain
| Need | Today | Ask |
|---|---|---|
| visibility feet + range | production `secchi-power-v1` / `rain-decay-v0`; Brain mirrors it; R3.1 certified but undeployed (8.0 research) | approval/deployment is Michael's; Intelligence then reads `clarityFt`, `lowFt/highFt`, `confidence` |
| per-arm / per-zone | lake-level; arm fusion research weak | publish `support` honestly; arm clarity only when validated |
| rain-event future state | none | say "unknown after rain" rather than persist |
| vegetation indicator | satellite `grassPct` lake share | keep as indirect indicator, *not* a vegetation state (Vegetation Brain owns that) |

## 4. Wind Brain
| Need | Today | Ask |
|---|---|---|
| sustained/gust/direction hourly to ≈24 h | published for 4 pilot lakes at CALIBRATION | scale beyond 4 lakes; schedule exists (hourly) |
| per-bank exposure (`effectiveFetchM`, Hm0, exposure class, `firm|boundary|unknown`) | in storage (`brain/wind/latest/{lk}.json.gz`), "never RTDB", not field-validated | a documented read path for Intelligence (storage ref in state is present); field validation of exposure and surface |
| forecast skill statements | certification 3.1; windy-hour POD 0.0 for ≥15 mph | publish skill by category so Intelligence can cap claims; do not let Intelligence quote "will build to 20 mph" |
| uncertainty | none numeric | map `firm|boundary` to HIGH/MEDIUM, `unknown` to UNKNOWN (in the prototype) |

## 5. Biological Brain
| Need | Today | Ask |
|---|---|---|
| **per-species response bands** over temp, depth, vegetation, wind exposure, clarity, level trend, by season/state | species knowledge scores (median ≈1.0/10); rules for common carp only; per-lake state NOT_STARTED | the central dependency: publish bands + evidence tier + regional transfer tags (see `SPECIES_MODEL` §2) |
| night-shallow behaviour | unresolved | yes/no/unknown per species-season |
| spawn table reconciliation | three conflicting tables | one reconciled table |
| target relevance | n/a | policy-owned list of bowfishing targets per state |

## 6. Depth Brain (does not exist; interface proposed, not counted as capability)
Intelligence needs depth only as **effective depth in the zone tonight**, and a trustworthy statement of how it is known. Intelligence must not do level arithmetic.
```
DepthZoneState {
  lakeId, zoneId, geometryVersion,
  reference:   { datum, poolElevationFt, source },                    // e.g. full pool; Lake Brain owns the datum choice
  atReference: { meanFt, p10Ft, p90Ft, shallowShare{ "<0.6m": f, "<1.2m": f, "<2.0m": f }, flatShare, nearestChannelEdgeM },
  effective:   { meanFt, p10Ft, p90Ft, shallowShare{...}, levelUsed:{ valueFt, asOf, source:"lake-brain@v" }, deltaFromReferenceFt },
  morphology:  flat | slope | channelEdge | hole | unknown,
  kind:        measured(survey) | modeled | proxy | unknown,  method, surveyYear,
  confidence:  HIGH | MEDIUM | LOW | UNKNOWN  + basis ("sounded 2019, ±0.3 ft" | "modeled, x1.5-x2.4 uncertainty"),
  support:     BANK_AREA | LAKE, provenance, freshness (static; survey age instead of staleAfter)
}
```
What it enables: shallow zones, flats, channel edges, effective depth as water rises or falls. Confidence rules: surveyed = HIGH; modeled/derived = ≤MEDIUM with an explicit uncertainty factor; absent = UNKNOWN (never a default depth). Interim: no depth ⇒ the deciding factor is UNKNOWN for every depth-using species ⇒ at most `WORTH_A_LOOK` (rules R1/R4). Today's only measured depth is one binary 9 ft contour in the iOS app for one lake; modeled mean-depth proxies exist for 621 lakes with 41 unknown, mean depth only, not a distribution, so they cannot support zones.

## 7. Vegetation Brain (does not exist; interface proposed, not counted as capability)
```
VegetationZoneState {
  lakeId, zoneId, geometryVersion,
  presence:    none | sparse | moderate | dense | unknown,   coverShare:{ value, lo, hi },
  broadType:   submerged | emergent | floating | filamentous_algal | flooded_terrestrial | unknown,
  obstruction: open | partial | mat,                         // shootability, distinct from habitat value
  seasonalState: dormant | emerging | peak | senescent | unknown, phenologyBasis, lastObservedAt,
  kind:        observed(sensor/date) | modeled | proxy | unknown,
  confidence + basis, support, provenance, freshness ( staleAfter in days; vegetation is slow, so 'stale' is weeks not hours )
}
```
Habitat value vs obstruction are the same pixels read two ways; Biological's species band decides which matters (a carp feeder wants cover, a shooter dislikes a mat). Flooded vegetation depends on level: Vegetation may reference Lake Brain level, but the combination into "flooded grass" is a Vegetation-owned fact. Interim: lake-level `grassPct` and NWI aquatic-bed share are shown as *indirect indicators*, never as a zone vegetation state.

## 8. Items with no Brain owner
- **Weather/sky/moon/fog/warnings** (see `TONIGHT_MODEL` §5): adapter with provenance.
- **Policy/legal** (species legality, restricted water): a gate source with versions (decision D5).
- **Lake geometry / zones**: Lake Registry or Lake Brain.

## 9. What Intelligence promises in return
Consumes published states only; never writes or "improves" a Brain value; passes `source@version` to the output; prints UNKNOWN wherever a contract field is absent; reports which Brain limited the answer (so the upstream blocker queue is visible product-side).

## 10. Contract-priority order (value to the bowfisher per unit of upstream effort)
1. Biological response bands for 3–5 principal species (unlocks species-first).
2. Scheduling of Lake and Water Temp jobs (removes STALE on all pilots).
3. Wind per-bank exposure read path for pilot lakes + field validation.
4. A Brain-level `confidence` label with basis on every state.
5. Clarity R3.1 decision.
6. Depth zone interface and a first pilot lake (research is just beginning).
7. Vegetation zone interface.
