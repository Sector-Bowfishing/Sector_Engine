# Wind Brain — fetch / exposure: the simple scalable calculation

## Decision
**Keep the frozen method: effective fetch = mean of 9 rays at 3° spacing across ±12° of the wind-FROM bearing, ray-marched over a water mask to the first land (islands are land); exposure from the Candidate's own CEM at the forecast speed.** It is already simple, cheap and mirrored in Swift. This campaign added an **independent polygon-only reimplementation** to test whether fetch can be produced for lakes without a hand-built NHD raster pipeline.

## Why fetch matters (numbers from the frozen physics, 6 h steady wind)
| Wind | 100 m cove | 500 m | 1 km | 2 km | 5 km | 10 km |
|---|---|---|---|---|---|---|
| 5 mph | LOW | LOW | MODERATE | MODERATE | MODERATE | MODERATE |
| 8 mph | LOW | MODERATE | MODERATE | MODERATE | MODERATE | **HIGH** |
| 12 mph | LOW | MODERATE | MODERATE | MODERATE | **HIGH** | HIGH |
| 18 mph | MODERATE | MODERATE | MODERATE | **HIGH** | HIGH | HIGH |
| 25 mph | MODERATE | MODERATE | **HIGH** | HIGH | HIGH | HIGH |
(LOW < 1 in, MODERATE 1–6 in, HIGH ≥ 6 in significant wave height.) 10 mph over 100 m is not 10 mph over 5 km: this is the whole value of fetch. Output classes already match the requested LOW / MODERATE / HIGH.

## Independent polygon calculation (new this campaign)
`research/wind-brain/polygon_fetch.py`: rasterize the lake polygon (≥ 20 m cells, ≤ 3,000 px), sample ≤ 400 shoreline cells, cast 5 rays across ±12° in each of 16 directions up to 30 km. Cost: ≈ 4 s per lake (single core, unoptimised); all 599 engine polygons in ≈ 40 min on a laptop, 595 succeed (4 fail on geometry type/validity: Waiau, Shafer, Devils, Buckeye).

### G2 (pre-registered) vs frozen NHD tables — **FAIL as registered**
Median per-lake Spearman ρ of the 16-direction median fetch profile = **0.56** (line ≥ 0.85); only 13% of lakes ≥ 0.85; dominant exposure direction within 45° on **51%** (line 80%). Post-hoc, labelled exploratory (`compare_posthoc.py`):
- using the 90th-percentile bank fetch: median ρ 0.65, 31% ≥ 0.85;
- **magnitude agrees**: median log ratio of mean p90 fetch −0.06 (≈ 6% lower) on 53 open lakes; the four dev lakes match within 5% (e.g. Guntersville 1329 vs 1291 m);
- **no rotation, mirror or reversed-convention error**: ρ peaks at shift 0.
- Why rank agreement is low: dendritic reservoirs have almost flat 16-direction profiles (fetch varies little by direction at the median bank), so rank correlation measures noise; and the two pipelines use different polygons (engine/OSM-derived vs NHD-HR), 5 vs 9 rays and different bank sampling.
**Conclusion:** the polygon method reproduces *how much* open water exists but is **not shown to reproduce the same direction ranking** as the audited tables. Treat polygon fetch for new lakes as an **estimate-tier (PROFILED-lite)**, not equal to the QA'd 74. A fair re-test needs per-bank matching on a shared polygon (see blockers).

## Duration
The frozen rule uses 6 h steady for classification. Memory/duration (M3/M4) concept PASSED on buoys for transients (MAE −23%), but SWAN says τ = 6 h is too sticky for reservoir basins (waves die in ≈ 1 h); the fetch-scaled M4 is not promoted. For tonight, **duration should be a speed history, not a wave model** (`WIND_TONIGHT_MODEL.md`).

## What not to build
CFD, per-point wind fields (WindNinja: turn ≤ 2°, speed ×0.97–1.03 → STOP), wave-height claims to the inch (CEM is a fetch-limited estimate; chop *class* is the output).

## Over-water vs land (open)
Standard guidance (not validated here): wind over open water exceeds nearby land-station wind (ratio typically > 1, larger for long fetch and stable stratification) and the 10 m neutral conversion used for CEM. Sector has **no over-water anemometer**, so this is the largest unquantified error in the bank answer, and the reason certification is capped at 7. One anemometer at one lake would also give the only proven nowcast gain (−16% at +1 h).
