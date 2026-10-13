# Blind expert ranking: the cheapest real validation step

**Question:** when an experienced bowfisher ranks areas of a lake before a trip, and then fishes them for equal time, does the ranking predict shootable fish per effort-hour?
**Why it matters to a bowfisher product:** it produces the first real outcome data Sector has ever had. Any later ranking (wind exposure now, the full synthesis later) can be scored against it without running new trips.
**What result changes the product:** it tells us whether area ranking is worth building before Depth/Vegetation exist, and gives the real base rate and dispersion that the power numbers need (`validation/power_sim.py` currently assumes them).
**Stop condition:** 20 paired visits on the pilot lakes, or one season, whichever is first. Then re-run the power calculation with the measured numbers and stop.
**Level of validation:** this is field truth for a Sector-derived claim, so it is worth the effort; nothing else in this document is.

## Protocol (one evening, one lake)
1. Before the trip, the expert lists 4–8 named areas and ranks them 1..N for one target species, with a confidence (low/med/high). Written down before fishing; the model's output is not shown (it does not exist for zones yet).
2. A coin flip (or the app) picks two areas, one ranked in the top half and one in the bottom half, and the order to fish them.
3. Fish each for the same fixed time (default 45 min of actively looking, not travel).
4. Log per area: species seen in range, count, shots, effort minutes, plus observed wind or chop class, clarity, vegetation, depth cue. Counts are **sightings in range per effort hour**, not fish landed.
5. One line per area in `research/intelligence/validation/blind_ranking_log_TEMPLATE.csv`. No outcome data exists yet; the template is empty on purpose.

## Analysis (pre-registered here)
Primary: in paired visits, higher-ranked area has more sightings per effort hour (one-sided sign test; paired log-ratio of (count+0.5)/hours as sensitivity). Report null results. Include same-rank negative controls when possible. Do not tune any rule on these trips and then claim they validate it; hold out by lake or season.

## What it does not do
It does not validate Intelligence, does not support a PARTIAL claim until the pre-registered paired size is reached on a Sector ranking, and does not replace field checks of Depth, Vegetation or Wind exposure, which belong to those Brains.
