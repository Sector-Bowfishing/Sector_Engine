# Wind field validation — foundation (schema, bank-pair design, anemometer recommendation)

Wind's score is limited by real-world truth, not by code. This is the smallest collectable design. Code: `sector_wind/brain/field_schema.py` (tested). It extends the Stage 3 protocol (`field_qa.py`, `fieldops.py`, `field.py`, sealed keys, write-once intake) rather than replacing it; v2 drops the four-lake restriction and adds the bowfishing vocabulary.

## 1. Observation record (`sector-wind-field-v2`) — one per bank per visit
`id, lakeId, bankId | zoneId, observedAtUtc, observer, observerConfidence (1 guess–3 sure), observerSawPrediction (bool), wind{source, speedMph, gustMph, directionFromDeg, deviceId, heightM, averagingSec}, bankImpactObserved (DIRECT/CROSS/PROTECTED/UNKNOWN), roughnessObserved (calm … veryRough), boatability (easy/manageable/difficult/unsafe), pairId/pairRole, photoFiles, tags`.
Rules enforced by the validator: measured wind needs device, sensor height and averaging period (height is never assumed); gust only from a measuring device; direction is the FROM bearing; **no model prediction in the record** (predictions are sealed per observation id and joined later); blinding state recorded; nothing is repaired, records are either usable or listed with reasons.
Collection effort: ≈ 2 minutes at the bank (look at the water, call the three buckets, one handheld reading, one photo).

## 2. Paired-bank session (same lake, same time, same wind, different predicted exposure)
1. **Plan** (from the archive at dusk): pick pairs from the lake's banks where the Brain's labels differ — one DIRECT/HIGH FETCH bank and one PROTECTED bank within ≤ 10 km by water, wind ≥ 5 mph forecast so direction is meaningful. Prefer evenings with breezy-risk flag or forecast 8–15 mph (information value is highest when the call matters). Randomise which bank is visited first; label A/B neutrally.
2. **Visit both banks within 60 min** (`PAIR_WINDOW_MIN`); record wind with the same device at both, 2 m, 60 s average.
3. **Record blind**: the observer sees only neutral X/Y bank IDs and coordinates; predictions stay sealed.
4. **Score**: `pair_concordance` — the bank the Brain called more exposed was observed rougher (ties 0.5; model ties and UNKNOWN excluded and counted). Report volume, lakes and wind-direction quadrants; scoring thresholds belong to the canonical scorer (Evidence Addendum v1: ≥ 40 holdout pairs, ≥ 2 lakes, ≥ 3 quadrants).
5. **Also test the vocabulary**: observer's `bankImpactObserved` vs the Brain's label (agreement matrix), and ESTIMATED vs AUDITED lakes separately — this is what can finally earn or refute the ESTIMATED tier.
Why paired: it removes the unknown over-water wind (both banks share it) and tests exactly what the customer is told ("this bank is rougher than that one").

## 3. Anemometer recommendation (no purchase, no assumption of hardware)
**Yes — one trusted over-water (or end-of-fetch shoreline) anemometer would materially improve Wind validation**, and a portable handheld set is enough to start the bank-pair programme.
| Question | Answer |
|---|---|
| Value | Largest single remaining lever: lifts the certification cap 7 (needs a qualifying over-water record), removes the biggest unquantified error (over-water vs land speed, the basis of every bank answer), and the only proven nowcast gain (−16% at +1 h). |
| Measure | 10 m-equivalent (or reported-height) sustained speed (≥ 1-min average), direction FROM, 3-s gust; sensor height and exposure documented. |
| Frequency | 1-min records, continuous, GPS/NTP time; at least 30 days spanning ≥ 3 distinct wind directions and some ≥ 12 mph nights (≥ 10 qualifying nights). |
| Placement | Guntersville (primary geometry lake): at the end of the longest fetch axis on open water (floating platform, or a pier/point shoreline site with unobstructed upwind over water), away from tree line; second site near a protected cove for contrast. Also compare against the nearest land station (HSV/DCU) to quantify the over-water ratio. |
| Portable instead? | Portable (boat-mounted/handheld) is **enough for pair sessions** and a first estimate of the over-water ratio, but it samples only when someone is out; it cannot satisfy the continuous-record requirement or show tonight's evolution. |
| Hardware | Not purchased or specified here; prior planning estimated ≈ $24–39k for the full two-lake network including direct surface-elevation sensors, hosts and permissions (pre-existing `WIND_AUTONOMOUS_VALIDATION_NETWORK.md`, TVA/host questions pending). An anemometer-only deployment is a small fraction of that; obtain quotes. |
| Decision owner | Michael. |

## 4. What this foundation does not do
It does not collect data, buy hardware, change the scorer, or claim any validation. Exposure stays MODELED and ESTIMATED until pairs exist.
