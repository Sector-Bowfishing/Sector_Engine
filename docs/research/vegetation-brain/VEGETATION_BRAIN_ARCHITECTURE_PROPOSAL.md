# Vegetation Brain — Architecture Proposal

**RESEARCH ONLY. A NEW, PROPOSED Brain. Nothing here is registered, deployed, scored or customer-visible.** The platform slot `vegetation` is already reserved (`BRAIN_PLATFORM_CONTRACT.md` §2; `BrainPlatform.swift:34`), so no platform change is a prerequisite.

## 1. The question the Brain answers
> Where is the aquatic vegetation, what broad kind is it, how dense is it, and how is it changing — and how sure are we?

Everything else (fish use, depth, clarity, lake level, the recommendation) belongs to other Brains.

## 2. Ownership boundary

| Owns | Does NOT own (consumes by reference only) |
|---|---|
| Vegetation presence, extent, density, broad class (submerged / emergent / floating / flooded-terrestrial), seasonal state, change, confidence, provenance | Fish preference for vegetation → Biological Brain |
| "Potential vegetation zone" as a *labelled model product* | Depth → Depth Brain (future) |
| Evidence tier per cell and per lake | Water clarity / Secchi → Water Clarity Brain (never invented here) |
| Refusals ("cannot see") | Pool level / anomaly → Lake Brain |
| | Final recommendation → Sector Intelligence |

## 3. Classes (v1 proposal)

| Class | Meaning | Primary evidence | Observed by Sentinel-2? |
|---|---|---|---|
| `EMERGENT` | rooted plants standing above the water (cattail, bulrush, phragmites, cutgrass, maidencane) | NDVI/red-edge/SWIR-low, S1 double-bounce, NAIP, NWI PEM | Yes, best class (≈91 % point accuracy in one 4-lake study) |
| `FLOATING` with flag `leaved` or `freeMat` | lily/lotus/pads vs hyacinth/lettuce/salvinia/duckweed; also topped-out SAV mats are reported as `surfaceTopped` SUBMERGED, see below | NDVI + FAI + red-edge | Yes (≈78 % for leaved; 79–95 % mats) |
| `SUBMERGED` with `surfaceTopped:true/false` | plants below the surface; *topped-out* canopy (hydrilla/milfoil) is surface-visible; non-topped is bottom-reflectance only | `surfaceTopped` = NIR-visible; else bottom reflectance + survey | Only topped-out, plus shallow-clear (≈59 % point accuracy in a clear-lake study) |
| `FLOODED_TERRESTRIAL` | terrestrial grass/shrub/timber currently inundated | pool anomaly × shoreline slope × land cover × SAR | Indirect (needs Lake/Depth state) |
| `NONE_SIGNIFICANT` | observed clear of cover (needs a valid observation) | SCL water + low indices | Yes, with clear scene |
| `UNKNOWN` | cannot see (cloud, ice, turbid, deep, glare) | — | **First-class outcome, never interpolated** |

Species identification is **out of scope**. Multispectral satellites cannot reliably separate species (EWM could not be separated from other SAV without hyperspectral). Species appear only in survey-derived evidence as free text, never as a satellite claim.

**Density** (4 classes, `scheme` tag stored with every value): `NONE`, `SCATTERED`, `MODERATE`, `DENSE`. Proposed cover cutoffs (≈2/15/45 % PAC-like, expert estimate) are anchored to the SFWMD 1/10/40/80 % legend and the FWC ~50 % managed-lake level; they are **[E] estimates to be calibrated** against NLA cover codes (0, <10, 10–40, 40–75, >75 %) and FWC data. Density applies to the *accessible-water area* (≈0–8 ft), not whole-lake PAC, which is diluted by deep water.

## 4. Evidence tiers (every output carries one)

| Tier | Meaning | May drive a customer layer? |
|---|---|---|
| `OBSERVED_SATELLITE` | dated Sentinel-2/Landsat/S1 classification, surface-reaching classes | Yes, with date + age |
| `OBSERVED_SURVEY` | agency/NLA/point-intercept record, with survey date | Yes, labelled as survey |
| `PRIOR_MAPPED` | NWI/NLCD polygon | Only as "historic mapped wetland", never as current |
| `SEASONAL_EXPECTATION` | model of typical state for this week | Only as "typically …" wording + confidence |
| `POTENTIAL_HABITAT` | SAV-capable zone = depth × clarity × substrate × region (modelled) | Only as "could grow here", never as "grass here" |
| `UNAVAILABLE` | refusal with reason code | Shown as "no reading" |

This mirrors Sector's existing doctrine (iOS `CLAUDE.md:265`: unread segments are refused, not given a lake mean) and Clarity's source-code vocabulary (observed / estimated / unreadable).

## 5. Data model (proposed, not implemented)

Per lake `vegetation` state under the platform slot:
```
schemaVersion, lakeId, computedAt, brainVersion, readiness(enum), confidence
summary: { coverFractionByClass{emergent,floating,submerged,floodedTerrestrial}, densityMix, ageDaysOfNewestObservation, trend(30/90d), seasonalExpectation{classProbabilities,reason,regime}, levelContext{poolAnomalyFt, source:"lake-brain"} }
cells[]: { id(~50 m grid or littoral segment), class, density, surfaceTopped, tier, observedAt, sourceId, confidence, reason }
refusals[]: { cellIds|region, reasonCode: CLOUD|ICE|TURBID|DEEP|GLINT|TOO_NARROW|NO_POLYGON|BLOOM_AMBIGUOUS }
provenance[]: { sourceId, product, acquiredOn, license, method, validationRef }
```
- **Grid choice:** ~50 m cells (5×5 S2 pixels) hold sub-pixel fractions rather than hard 10 m labels; matches Clarity's per-cell evidence raster pattern and is a compact payload. Segment-based output (iOS littoral segments) is a derived view.
- **Cloud gaps:** reuse the Clarity pattern (borrow from passes within N days, flagged `BORROWED`) for surface-reaching classes; use the seasonal prior only as a labelled expectation.
- **Bloom ambiguity:** cyanobacteria and floating plants share high NIR/FAI; ambiguous cells get `BLOOM_AMBIGUOUS` unless persistence/phenology resolves them (no study validated a discriminator).

## 6. Pipelines (proposal)
1. **Surface-reaching observer** (daily/weekly): Sentinel-2 L2A via STAC → water/plant mask → NDVI, NDAVI, FAI, red-edge ratio, SWIR gate → class + density fraction per cell; per-season 90th-percentile composites for cloud-robust peak state.
2. **Flooded-terrestrial/emergent complement**: Sentinel-1 water frequency + JRC seasonality + NWI PFO/PSS + Lake Brain pool anomaly.
3. **Potential-SAV model**: depth bands (Depth Brain) × clarity class (Clarity Brain) × region/species-group priors → `POTENTIAL_HABITAT`, never `OBSERVED`.
4. **Seasonal expectation**: GDD-based phenology (Water Temp Brain) × lake amplitude (history) × management/regime flag; Bayesian blend with last clear observation.
5. **Survey ingestion**: FWC/NLA/MN/WI/TVA/TPWD records → `OBSERVED_SURVEY` and calibration targets.

## 7. Readiness enum (proposed)
`DISCOVERED → GEOMETRY_READY → PRIOR_ONLY → OBSERVER_UNVALIDATED → OBSERVER_VALIDATED_REGION → VALIDATED`, mirroring the Lake Brain readiness pattern; a lake without validation stays at most `OBSERVER_UNVALIDATED` and its confidence is capped.

## 8. Anti-requirements (explicit)
- No species labels from satellite.
- No "submerged vegetation here" from NDVI alone.
- No invented clarity; clarity is an input, with its own confidence.
- No lake-mean fill for unread cells.
- No fish-behaviour logic.
- No customer layer change, no iOS/Android work, no Intelligence/Biological/Clarity/Ops modification in this campaign.

## 9. Reuse from existing Sector assets
| Asset | Reuse |
|---|---|
| Clarity `derive_water_surface.py` plant-spectrum gate (NDVI ≥ 0.30, FAI, SWIR, haze rejection) | Algorithm precedent for surface-reaching classes; fork the idea, do not couple code |
| Clarity cloud borrowing (`GRASS_BORROW_DAYS=10`) | Cloud-gap pattern |
| Clarity evidence raster/cell encoding | Cell schema precedent |
| Brain platform contract (schema gate, health vocab, readiness) | Publishing |
| Lake polygons (599) + GSW/NHD matches | Water mask |
| `lake_geometry_flags.csv` | Geometry quality routing |
