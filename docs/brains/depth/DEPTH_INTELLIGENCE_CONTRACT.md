# Depth -> Sector Intelligence Contract (proposal; do not edit the Intelligence branch yet)

**Rule: Depth publishes environmental depth state. Intelligence restates and combines it. Intelligence never performs lake-level arithmetic, never infers a datum, never converts a shift into an absolute depth.**

Source of truth: `docs/brains/depth/DEPTH_STATE_CONTRACT.md`; executable fixtures `jobs/depth-brain/tests/fixtures/*.json` (golden, deterministic, drift-tested). The Intelligence research already expects a `DepthZoneState` and expects Depth to calculate effective depth; this document is Depth's side of that contract.

## 1. What Intelligence may read

| Depth field | Meaning | Intelligence may |
|---|---|---|
| `kind` | `observed` or `unavailable` | treat `unavailable` as **missing evidence** (drop the factor and renormalise, the existing FishIntel `unmeasured` rule) |
| `effectiveDepth.mode` | `shiftOnly` / `zoned` / `unknown` | restate; `unknown` is never "0" and never "normal" |
| `effectiveDepth.shiftFt`, `uncertaintyFt`, `confidence`, `resolvable` | level-driven change of every reference depth | say "about 1.4 ft lower than normal pool"; gate on `resolvable` before saying any depth "changed" |
| `coverage.sourceTier`, `contourCoverage`, `contourIntervalFt` | how much real depth evidence exists | limit claims to the tier: shift statements for D/UNKNOWN; band shares only for A/B/C |
| `referenceZones.share*` | share of the surveyed surface in a band at the reference pool | restate as a share of surveyed water, with `support` |
| `effectiveZones.shares.*.{lo,hi}` | bounds on the same shares at the current shift | restate as a range; never collapse to a midpoint and call it measured |
| `freshness.evidenceStale`, `limitations` | input age / caveats | carry caveats to the reasoning text |

## 2. What Intelligence may NOT do

* Compute `level - pool` itself, or use Lake Brain's level plus its own reference.
* Convert a shift into an absolute depth of any spot ("this flat is 2.6 ft deep") unless a Depth state carries a contour reference depth for that spot (not available today).
* Use `coverage.sourceTier` D or UNKNOWN as depth evidence, or any modeled bathymetry (GLOBathy) for anything.
* Claim flats, channels or drop-offs from Depth (none published).
* Fill an absent field. Absent = unknown.

## 3. Join with Biological

Biological supplies preferred depth bands and seasonal movement. Intelligence matches a **band** to a **Depth statement of the same kind**:
* Shift-only lakes: express as a delta against a lake's normal conditions ("the lake is 2 ft lower than normal, which exposes water that is normally 0-2 ft deep"). Do not claim the preferred band is or is not present.
* Contour lakes: compare the preferred band with `referenceZones` / `effectiveZones` ranges; require `resolvable` and `confidence != LOW` for a positive claim.
* Evidence classes should propagate: `levelDelta` (shift) and `contour` (zones) must remain distinguishable in the Intelligence evidence layer.

## 4. Fixtures (consumer contract tests)

| Fixture | Case | Required consumer behaviour |
|---|---|---|
| `shift_only_observed` | tier UNKNOWN, shift -1.4 +/-0.3 ft HIGH | restate shift + uncertainty; no depth claim |
| `shift_only_rising` | shift +1.2 | rising: flooded margin not quantified |
| `unavailable_datum_unknown` | datum unknown, blocked | missing evidence; no number |
| `unavailable_no_level` | Lake Brain state absent | missing evidence |
| `tier_d_no_depth_evidence` | no measured depth | shift only; "no depth evidence" in caveats |
| `contour_zones_reference_unverified` | tier A zones, survey reference unverified | restate reference shares; **no effective zones** |
| `contour_zones_effective` | tier A zones with verified reference, bounds | restate ranges only |

`tests/test_contract_fixtures.py` includes a reference `restate()` consumer proving the rules are implementable in a few lines.

## 5. Versioning

Additive fields do not bump `schemaVersion`. Changing the meaning of `shiftFt`, its sign, or the closed vocabularies bumps `stateSchema` (`...-v2`) and requires the golden fixtures to be regenerated deliberately (`UPDATE_FIXTURES=1`) and reviewed.
