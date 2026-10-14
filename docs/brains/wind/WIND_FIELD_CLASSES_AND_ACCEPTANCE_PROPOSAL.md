# Wind field classes and acceptance lines — PROPOSAL for Michael (status PROPOSED_NOT_FROZEN)

Question behind every line: **would a bowfisher trust this enough to choose a bank?** Not derived from academic convention. Nothing here is frozen until you approve; once approved, freeze the classes and lines (with a sha) BEFORE the first observation is scored. The frozen pair lines in `WIND_BANK_VALIDATION_V2_PREREG.md` (concordance >= 0.80 with lower bound >= 0.65, false-PROTECTED <= 10%, tester agreement >= 0.80, >= 40 pairs) are untouched; these lines cover the new one-tap, non-paired observations and add the dangerous-miss guard.

## Practical classes (what a bowfisher can tell from the boat in seconds)
| Question | Class | Meaning on the water |
|---|---|---|
| Is the wind reaching this bank? | PROTECTED | Water along the bank is glassy to lightly rippled while open water upwind is textured; the wind is blocked by land |
| | PARTIAL | Wind reaches part of the stretch or comes and goes; some chop but not driving onto the bank |
| | EXPOSED | The wind and chop hit this bank head-on; waves or chop pushing onto the shore |
| | UNKNOWN | Not sure (never forced) |
| Water surface here | CALM | Little surface disturbance; easy shooting |
| | MODERATE | Shootable, but noticeable chop |
| | ROUGH | Shooting and boat control significantly degraded |
| | UNKNOWN | Not sure |
Mapping to the frozen field schema v2 (`quick_observation.to_v2`): PARTIAL = CROSS; CALM -> calm, MODERATE -> choppy, ROUGH -> rough; boat control and confidence are DERIVED and flagged. ESTIMATED-geometry lakes only make EXPOSED / PROTECTED calls, so a model CROSS call there is counted as EXPOSED (a PARTIAL observation is then within-one).

## Observation (target under 15 s)
`docs/brains/wind/field_tools/quick_observation.html` (offline, no accounts): three taps (exposure, surface, "did you see a Sector prediction first?"), your initials, and a bank/zone or GPS. Lake, time and trip id are automatic; wind speed/direction/notes optional. Any bowfisher can submit many banks in one night. The prediction is regenerated from the archive at the observation time and kept separate.

## Proposed acceptance lines
| Item | Proposed line | Why a bowfisher would care |
|---|---|---|
| Volume | >= 60 observations, >= 8 independent nights, >= 2 lakes (Guntersville, then Hartwell), >= 3 wind quadrants, >= 15 observations with wind >= 8 mph | Banks on one night share weather: nights, not banks, are the independence unit |
| Bank exposure exact (3-class) | >= 0.60 | Right more often than not on a three-way call |
| Bank exposure within one class | >= 0.90 | Almost never wrong by two steps |
| **Dangerous miss (PROTECTED called, EXPOSED observed)** | **<= 5% of PROTECTED calls AND one-sided 95% upper bound <= 15%; needs >= 20 PROTECTED calls** | The mistake that wrecks a night; the bound stops a lucky handful from passing |
| Surface exact | >= 0.60 | |
| Surface within one class | >= 0.90 | |
| **Dangerous miss (CALM called, ROUGH observed)** | **<= 3% of CALM calls AND upper bound <= 12%; needs >= 20 CALM calls** | "Calm" must not turn out rough |
| UNKNOWN share | reported, <= 35% expected; UNKNOWN is never scored right or wrong | Honest refusal is allowed but too much means little help |
Implemented and tested in `sector_wind/brain/field_acceptance.py` (small-sample guard included). Not lowered to pass: if Guntersville misses a line the claim stays withheld.

## What each outcome does (no activation without your approval)
- Exposure passes, surface does not: prepared fallback = BANK_ONLY (PROTECTED / PARTIAL / EXPOSED words, surface withheld).
- Strong-event evidence stays short: prepared NORMAL OPERATING ENVELOPE (sustained 5-12 mph, forecast <= 6 h old); outside it the card says "Use caution" instead of a bank call. `customer_output.py`, tested, not imported by anything.
