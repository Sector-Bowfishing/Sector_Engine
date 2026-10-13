# Pilot input verification (Level 1: provider truth) - 2026-10-14

Question: is the level Lake Brain publishes for the five Depth pilots what the operator's own feed says? Why it matters: Depth's shift is only as true as its input. Stop condition: source, freshness, units, sanity confirmed for each pilot. One-off GET-only audit (`research/depth/pilot_input_verification.py`, data `data/pilot_input_verification.json`); the product never does this (Depth consumes Lake; no duplicate retrieval).

| Pilot | Lake Brain level (ft) | Operator feed | Difference | Time check |
|---|---|---|---|---|
| Guntersville | 593.60 | TVA `observed-data-48-hours/GVDA1`: 593.60 (row 10/13/2026 1 PM CDT) | 0.000 | Lake observation 18:00Z = 1 PM CDT |
| Wheeler | 553.60 | TVA `.../WHLA1`: 553.60 (1 PM CDT) | 0.000 | same |
| Wilson | 506.76 | TVA `.../WLSA1`: 506.76 (1 PM CDT) | 0.000 | same |
| Pickwick | 411.12 | TVA `.../PICT1`: 411.12 (4 PM CDT) | 0.000 | row present in the 48 h feed |
| Hartwell | 649.37 | USGS 02187010 parameter 00062 nearest instant: 649.32 | 0.05 | Lake 17:00Z = 13:00 EDT, feed 13:00 EDT |

* Units ft on both sides; levels sane (within 2-11 ft of pool, far below the 80 ft implausibility guard).
* Shift arithmetic: `levelDeltaFromReferenceFt == level - referencePoolFt` to 0.006 ft for all five.
* What this does not show: that the TVA datum is NGVD29 (still inferred; `DEPTH_TVA_DATUM_REQUEST.md`), or that the shift matches what a bowfisher sees on the water (field validation).
* Result: provider display verified; no larger campaign needed.
