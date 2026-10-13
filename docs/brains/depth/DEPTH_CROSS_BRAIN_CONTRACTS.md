# Depth Cross-Brain Contracts (interface documents only; no other Brain's branch is touched)

Principle: Depth owns depth. Each consumer owns its own science. A consumer reads `states/depth` (shadow, internal) and restates it; it never recomputes level arithmetic and never uses Tier D/UNKNOWN as depth. Absent = unknown.

## 1. Water Temp (Depth -> Water Temp)

Water Temp currently uses a modeled mean depth (`depth_proxy_candidates.csv` on its research branch: 335 HydroLAKES `Depth_avg`, 245 NID storage/area, 41 unknown; every row flagged MODELED with x1.5 - x2.4 error notes).

| Depth supplies | When | Notes |
|---|---|---|
| `referenceZones` shallow shares (`shareUnder3Ft`, `shareUnder6Ft`) | tier A/B contour lakes only | replaces the shallow-fraction proxy for those lakes; gives the thermally responsive share |
| mean depth where measured | tier A only, and only when the contour record exports it (future field `meanDepthFt`, not published today) | research: contour mean depth beats HydroLAKES (modeled overestimates by 1.4x, n=17) |
| `effectiveDepth.shiftFt` + `acresPerFt` prior | shift lakes | drawdown-adjusted volume proxy: dV ~ A * shift. **Defensible only as a first-order proxy**; Water Temp must carry the uncertainty and must not call it measured volume |
| max depth where authoritative | tier A only | never from GLOBathy; GLOBathy Dmax has no skill for lakes < 8 m (3.6x too deep) or > 40 m (0.51x) |

Do not: feed modeled Dmax into stratification; treat a shift as a depth. Water Temp's active branch is unchanged.

## 2. Water Clarity (Depth -> Clarity)

| Depth supplies | Use | Guardrail |
|---|---|---|
| `shareUnder3Ft`/`shareUnder6Ft` (tier A/B/C) | shallow resuspension mask denominator; optical-bottom-risk share; wind-fetch x shallow exposure | contour evidence only; **no modeled depth enters Clarity** (Clarity 8.0 truth must not be contaminated) |
| `effectiveDepth.shiftFt` | lower pool exposes/relocates shallow margins; a drawdown can raise turbidity | shift only changes *interpretation*; Clarity keeps `grassPct` and satellite truth |
| `coverage.sourceTier` | consumers can ignore anything below A/B | D/UNKNOWN = no input |

## 3. Vegetation (Depth -> Vegetation)

Vegetation needs effective depth, depth class, shallow share, and inundation status.
* `effectiveDepth` (shift), `referenceZones` shares (A/B/C), and `floodedMarginUnquantified` / dry share (from `effectiveZones`) give inundation context: newly exposed margin (`dry`) vs flooded margin.
* Depth does not publish plant state, light-limited depth limits, or "littoral" classes. Vegetation derives those from its own optics plus Depth's depth statements.
* A bound (`lo`,`hi`), not a point, is the unit of exchange for effective zones.

## 4. Biological (Biological -> Intelligence <- Depth)

Biological supplies species depth preferences and seasonal movement (e.g. spawning 1.2 - 6.1 m). Depth supplies environmental depth. Neither imports the other; **Sector Intelligence matches them** (see `DEPTH_INTELLIGENCE_CONTRACT.md`). Depth contains no fish behaviour; Biological contains no lake-level arithmetic.

## 5. Lake Brain (Lake -> Depth)

Depth **reads** `states/lake`: `currentElevationFt`, `unit`, `datum`, `observationTime`, `sourceCapability`, `kind`, `differenceFromNormalPoolFt` (cross-check only), `freshness.stale`. Depth never reads raw level feeds, never writes any Lake Brain path (ownership enforced), and flags (`lakeBrainDeltaDisagrees`) when its shift and Lake Brain's own difference disagree by > 0.15 ft at the same reference.
Requested of Lake Brain (non-blocking): stamp `datum` on every state (TVA states publish `datum: null` today - Guntersville live read, 2026-10-13), and publish the reference pool's datum with `normalPoolRef`.

## 6. Customer surfaces

None. iOS/Android/Ops are unchanged. The FishIntel client already treats unmeasured depth by dropping the factor and renormalising; a future adoption should reuse that exact behaviour for `kind: unavailable`.
