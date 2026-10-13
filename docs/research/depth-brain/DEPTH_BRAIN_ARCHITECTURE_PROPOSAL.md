# Depth Brain Architecture Proposal (research only, not a commitment)

Depth Brain does not exist today. This proposes what it should own, what it should refuse to own, and how it should degrade honestly. Evidence numbers are from this campaign's docs; none is production.

## 1. Verdict on "should Sector create a Depth Brain?"

**Yes, but a narrow one.** Two things justify it:

1. **Effective-depth shift** (current level minus reference pool) is bathymetry-independent, validated against the pool table, and already computable for 175 lakes "usable now" (`DEPTH_BRAIN_EFFECTIVE_DEPTH_RESEARCH.md`). It changes bowfishing decisions (a 4 ft flat is 2 ft or dry).
2. **Where real contours exist (about 136 lakes by candidate, verification in `DEPTH_BRAIN_CONTOUR_TRUTH_REPORT.md`), shootable-water maps are possible**, and no other Brain can own them.

What it must not be: a modeled-bathymetry product for the other lakes. GLOBathy and 3DEP slope fail the shallow-flat tests (see GLOBathy evaluation and shallow-zone research). Unknown is the correct output for those lakes.

## 2. Ownership (unchanged boundaries)

| Owner | Owns | Depth Brain relation |
|---|---|---|
| Lake Registry | identity, boundary, IDs | Depth keys on `lakeId`; never edits geometry |
| Lake Brain | current level, trend, pool/flood/drawdown state, operator guides | Depth **reads** level and `differenceFromNormalPoolFt`; never recomputes it |
| **Depth Brain** | reference depth evidence, depth classes, zones, morphology, effective depth, confidence, provenance | this proposal |
| Biological Brain | fish depth preference, seasonal movement | Depth never encodes fish preference |
| Sector Intelligence | joins Depth state with Biological preference | consumes Depth zones and `effectiveDepth` |

## 3. Two layers

**Static layer (per lake, rebuilt rarely):** evidence record. **Dynamic layer (per Lake Brain pass):** effective-depth state derived from the static layer plus the Lake Brain level. Dynamic never mutates static.

### 3.1 Static record `depth/static/{lakeId}`
```
lakeId, evidenceTier, tierReason,
reference: { datumLevelFt, datumName (pool basis), datumConfidence },
absolute:  { available, source, sigmaFt, maxDepthFt?, meanDepthFt? },
relative:  { available, source, shallowShare: {0_3, 3_6, 6_10, gt10}?, flatsAreaAc?, medianShoreTo6ftM? },
morphology:{ flats[], dropoffs[], channels[]  // only Tier A/B },
coarsePrior:{ class: likelyShallow|unknown|likelyDeep, source:"globathy" }  // Tier D only, never scored
provenance: { sources[], survey year, license, builtAt, version },
manualReviewNeeded
```
### 3.2 Dynamic state `depth/state/{lakeId}`
```
levelShiftFt (from Lake Brain, copied with its own timestamp & confidence),
shiftSigmaFt, rangeClass (>=4, 1.5-4, <1.5 ft operating range),
effectiveDepthState: available | shiftOnly | unavailable,
zoneShifts?: re-binned zone shares at current level (Tier A/B only),
exposedOrFloodedAcresEstimate?, staleness, confidence
```

## 4. Output vocabulary (what customers/Intelligence may see)

* `shiftOnly`: "Pool is 2.1 ft below normal. Typical range ±X ft. Shallow flats are shallower/shoreline moved out by ~Y acres." Needs pool confidence ≥ medium. Always a delta, never an absolute depth.
* `zoned` (Tier A/B lakes only): very shallow 0-3 ft, shallow 3-6, transition 6-10, deep >10 at the **reference level**, shifted by the current level, with σ. Round to 1 ft, show bands not feet when σ > 1 ft.
* `unknown`: explicit, with reason. The existing FishIntel client already handles `unmeasured` by dropping the factor and renormalising; Depth Brain keeps that contract.

Never emit: absolute depth on Tier D, per-segment flats from slope, bathymetry from GLOBathy.

## 5. Evidence tiers (proposed, tested)

| Tier | Meaning | Allowed outputs | Fleet today (see `DEPTH_BRAIN_FLEET_COVERAGE.md`) |
|---|---|---|---|
| A | Surveyed bathymetry, ≤2 ft contour interval or dense soundings, datum reconciled | absolute depth, zones, flats, shifted zones | TWDB, MN DNR (fine), USGS, FL FWC (internal), OH, WV etc. where verified |
| B | Published contours at 5-10 ft interval or partial coverage, or binary navigation contour | zones at coarse bands (depth ≤ interval), flats only >interval; σ per contour interval (1.3 ft at 5 ft, 2.8 ft at 10 ft) | many state sets; IENC 9 ft contour |
| C | Validated model for the lake **class** (hypsometry from stage-storage, Landsat drawdown exposure) | lake-level shallow-area share, acres per ft, rank only | CWMS 33 lakes; Landsat on lakes whose level moves |
| D | Unvalidated terrain/modeled inference | coarse prior class only, not scored, not shown as depth | GLOBathy, 3DEP slope |
| U | No defensible evidence | `unknown` | remainder |

Subdivision findings: A and B must be split by **contour interval and coverage** (the 2.8 ft RMSE at 10 ft interval makes a 0-3 ft claim unsound), and C by whether a measured hypsometry exists. Hence the matrix keeps `evidenceTier` plus `absoluteDepthConfidence` and `relativeDepthConfidence` as separate fields.

## 6. Pipeline sketch (for the implementation plan, not built)

1. Static build job (offline, versioned, idempotent): ingest contours → normalise datum/units → verified spatial match to registry polygon → zone rasters/areas → write static record + a small GeoJSON of zones per Tier A/B lake.
2. Dynamic job: after Lake Brain publish, read level, `fullPoolFt`, confidence; compute shift and σ; re-bin zones. No new external fetch, so no new rate-limit surface.
3. Ops: show tier, source, survey year, freshness; a review queue for `manualReviewNeeded` and name-collision matches.
4. Gates before any customer exposure: shadow-only publish, then Ops, then Intelligence consumption behind its own flag.

## 7. Risks

* False precision (largest). Mitigate with bands, σ, tier labels.
* Datum errors (NGVD29 vs NAVD88 median 0.64 ft, up to 5.4 ft). Require reconciled datum for any absolute claim.
* Mismatched lake identity (generic names). Spatial verification mandatory.
* Licensing (FL FWC no-redistribute). Store tier, not geometry, if not licensed.
* Survey age (1960s digitised maps, sedimentation).
