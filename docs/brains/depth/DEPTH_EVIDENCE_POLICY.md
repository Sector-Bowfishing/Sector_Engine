# Depth Evidence Policy (codified research decisions)

Implemented in `jobs/depth-brain/depth_brain/evidence.py`, `zones.py`, `shift.py`; enforced by tests (`tests/test_zones_evidence.py`, `tests/test_state_publish.py`).

## 1. Tiers and precedence

| Tier | Meaning | May produce |
|---|---|---|
| A | authoritative measured/surveyed (fine-interval contours or survey tables, whole lake) | shift, band shares at supported edges, (future) effective zones, mean/max depth where exported |
| B | trusted contour/depth dataset (coarser interval or partial) | shift, band shares at supported edges only |
| C | limited/partial authoritative evidence (binary navigation contour, partial survey, measured hypsometry) | shift; only the statements the evidence itself supports (e.g. "inside the charted 9 ft contour at reference pool") - not yet implemented as a product |
| D | proxy/model context | nothing user-visible; shift-only lakes may list it as `coverage.sourceTier = D` to say "no depth evidence" |
| UNKNOWN | nothing | shift-only if a level exists; otherwise unavailable |

Higher tiers always override lower ones; a lower tier never fills a hole in a higher tier. Research tiers map `A->A, B->B, B-partial->C, B-binary->C, C->C, D->D, U->UNKNOWN`: **partial and binary contours are never promoted to full bathymetry** (tested).

## 2. GLOBathy policy (FINAL)

GLOBathy MUST NOT be used for: canonical absolute depth, point depth, flats, drop-offs, channel location, precise depth zones, ranking lakes by depth, any customer contour layer, effective depth, any scored factor, or overriding measured evidence. These are `FORBIDDEN_MODEL_USES` and `assert_allowed_use()` raises for them (tested for `globathy` and `modeled`).

Evidence for the decision (research branch `docs/depth-brain-research`):
* max depth Spearman 0.42 (n=75, truth) and 0.18 (n=73, vs contour max); within 2x 68% vs 56% for a constant; regresses to the middle (3.6x too deep for lakes < 8 m, 0.51x for > 40 m);
* shallow-share MAE 0.135 vs 0.128 constant; broad-shallow AUC 0.53; recognised 1 of 6 truly shallow lakes;
* its rasters are one power law extruded from the shore (no flats or drop-offs); 89% matched but only 234 of 621 verified (chain reservoirs mismatched).

The one allowed form, a coarse class prior (`likelyShallow` / `unknown` / `likelyDeep`), is **implemented but disabled** (`ENABLE_GLOBATHY_COARSE_PRIOR = False`) because it adds essentially no product value. If a future reviewer enables it: tier D, `scored: false`, class only (no depth, zone, share, polygon or rank), suppressed whenever any A/B/C evidence exists, nothing for suspect/unmatched HydroLAKES matches.

## 3. No slope-derived flats

3DEP shoreline slope predicts **area change per foot of pool** (Spearman 0.77 on CWMS, n=33) and is allowed only as a supporting prior for that. It must not declare a flat: shallow-share predictions did not beat a constant (MAE 0.039 vs 0.041 within 3 ft; per-segment slope adds 0.004 cell AUC over distance to shore). No slope-derived flat/drop-off/channel field exists in the DepthState.

## 4. Contour resolution

Edges resolvable only at multiples of the contour interval, or at any edge when the interval <= 3 ft (measured interpolation RMS: 0.28 ft at 1-2 ft, 1.3 ft at 5 ft, 2.8 ft at 10 ft). A 10 ft survey overstates the shallow share (+0.05 at <= 6 ft). Unresolvable edges are omitted; shifted edges between resolvable ones become bounds.

## 5. Datum rule

A shift exists only for `SAME_SOURCE`, `SAME_DATUM` (both verified from documents or stamped on the data) or `CONVERTED` (explicit conversion supplied). Everything else is UNKNOWN. The candidate builder does not enable NGVD29/NAVD88 conversion in this phase (sign convention of the research conversion table is unverified); affected lakes are listed as `DATUM_CONVERSION_NOT_ENABLED`.
