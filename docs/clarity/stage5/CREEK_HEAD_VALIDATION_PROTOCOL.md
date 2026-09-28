# Creek-head validation protocol (beta)

Clarity Fusion Stage 5, item 17. For master accounts using the Current Clarity beta on Guntersville.

**The goal is evidence, not a conclusion.** Stages 3A and 3B found no replicated, out-of-sample effect of runoff on creek-head clarity. The heads are also the water the satellite reads least: Town Creek's head is measurable on 2.7% of passes. What's missing is repeated ground truth at the same places, before and after rain that happens anyway.

## Where

| Site | Region id | Why |
|---|---|---|
| Town Creek head | `town-creek-marshall` | USGS 03572690 / 03572900 gauged; the largest runoff signal; the main head the satellite can't read |
| South Sauty head | `south-sauty-creek` | Gauged; grass beds at its mouth (no supported number there, Stage 5) |
| Browns Creek head | `browns-creek` | Ungauged: modeled NWM flow only |
| A heavily vegetated head | pick one where the map shows grass (grey on Water Clarity, green on Vegetation) | A report is the only clarity evidence a bed can have |
| An open-water control | a main-stem stretch the satellite read directly (level B/D on the tap card) | The satellite can be checked against a report only here |

## How

1. Open Water Clarity and turn on **Clarity run** (Beta section).
2. Moving up the arm, tap the band at each look: **one tap per ~250 m, and at the head itself.** Keep "Under bowfishing lights" true at night.
3. At the head and at the control, also open the tap card and **Report clarity** with the depth and a photo.
   - The photo stays on the phone.
   - Turn on **Share with Sector** only if you want the zone and hour to leave the phone.
4. Log the same heads **again on the next trip** whatever the weather. A pair needs no storm.
5. When rain happens anyway, log the heads on the first trip after it and again once they have cleared. **Do not go out because of a storm.** The protocol takes rain as it comes.

## What each report already records

Captured automatically, on the phone only:
- the band as an interval (0–1, 1–2, 2–4, 4–6, 6+ ft; never a midpoint);
- the method (night under lights / day, kept apart; never converted to Secchi);
- the time, and the precise position (the map's 5 m fix);
- the region, zone and cell.

The evidence level and hydrologic state at that moment are **not** stored on the report. They can be rebuilt afterwards from the region, the time and the hourly record.

Nothing else is needed from the bowfisher.

## What it can validate, and when

| Question | Needs | Earliest honest look |
|---|---|---|
| Report freshness (12 h if stable, 3 h if unknown) | ≥ 10 repeated same-head pairs 3–24 h apart, some across a rain | after ~10 trips |
| Spatial repeatability (does one cell speak for its zone?) | ≥ 3 looks per zone, same night | after ~5 runs |
| Sentinel shoreline challenger (the relaxed-shore mask) | Reports at the control and near-shore cells, within 72 h of a direct scene | when ≥ 20 such matches exist |
| Night visibility vs Secchi | Paired night/day looks at the control, same day | only when ≥ 30 pairs exist; no fitting before that |

**Rules for reading the log:**
- No thresholds are tuned on fewer than the counts above.
- Every analysis is written down before it is run, as with the confidence tiers (`CONFIDENCE_TIERS_PREREGISTRATION.md`).
- A head with no reports stays unknown.

## Exporting

The reports are the trip store's `TripClarityNote` rows (owner, lake, region, zone, cell, interval, method, time, position, depth, notes). **There is no export yet**: analysing the precise, private reports needs one (a gap, not built in Stage 5). Shared reports (`clarityReports/*`, zone and hour only) are readable by masters in the database.
