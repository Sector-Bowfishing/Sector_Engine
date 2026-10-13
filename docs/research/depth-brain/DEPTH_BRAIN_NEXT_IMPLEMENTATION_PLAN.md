# Depth Brain Next Implementation Plan (plan only; nothing here is authorised or built)

## Recommended single next step
**Spec and shadow-build the effective-depth shift slice** (no bathymetry needed): a new session designs `depth/state/{lakeId}` for the 265 lakes with a bound live level and a pool reference, adds the TVA/Duke/Santee/USACE datum audit against operator documents, and runs it in shadow (no RTDB customer path, no Intelligence read) beside Lake Brain. In parallel Michael starts the data requests (B-depth-001, B-depth-002).

Why this first: it is the only capability that covers the bowfishing-heavy reservoirs, is validated at 0.27-1.0 ft sigma, and does not wait for contours that do not exist for the Southeast.

## Phases

| Phase | Work | Output | Exit gate |
|---|---|---|---|
| 0 (now) | Michael actions: operator/state data requests; licence review; field-validation plan | emails, permissions | any dataset in hand |
| 1 Shift slice (shadow) | datum audit; define schema; compute shift + sigma + range class from Lake Brain level and `full_pool.csv`; fill 151 missing histories; add acres-per-ft prior (85 % within x2) | shadow state for 265 lakes | shift error <= 0.5 ft p90 on high-confidence pools; sigma calibrated |
| 2 Static zones for tier A/B | productionise contour ingest/match/normalize into an idempotent static builder; verify 24 name-only USGS matches and 37 partial lakes; publish derived zone shares and shore-to-6-ft stats, not raw geometry | static records for 103 (+ verified) lakes | verified spatial match 100 %; datum reconciled; licence cleared |
| 3 Zone re-binning at current level | apply level shift to zones using the contour grid; validate on TWDB lakes against area-capacity at lower pools | `zoneShifts` | MAE <= 0.02 share at lower pool |
| 4 Southeast data | ingest whatever Phase 0 yields (hydroacoustic surveys, TVA, state); extend IENC interior check to the 28 B-binary lakes | tier A/B for SE reservoirs | >= 25 new reservoirs |
| 5 Landsat drawdown pilot | extend the 5-lake test to lakes with 8+ ft level range, calibrated against contours; use only as tier C | satellite exposure bands | Spearman >= 0.8 on held-out lakes; shallow-share bias corrected |
| 6 Intelligence consumption | expose `shiftOnly`, `zoned`, `unknown` to Sector Intelligence behind its own flag; keep Tier D out of scoring | integration spec | Intelligence validation on bowfishing observations |
| 7 Ops/monitoring | tier dashboards, freshness, review queue, drift | Ops pages | rubric gates |

## Do not build
* Modeled bathymetry for non-surveyed lakes (GLOBathy, slope-derived) as a depth layer.
* Per-segment flats from shoreline slope.
* Nationwide satellite hypsometry before the 5-lake pilot is extended and validated.
* Anything that touches Lake Brain, Biological, Clarity, Water Temp or Intelligence code.

## Cost sketch
Phase 1: small (reads existing level + table). Phase 2: offline batch, 4.4 GB working set rebuildable from ledger URLs. 3DEP sampling is rate-limited (about 1 lake/min). No new live API in the Brain cycle.
