# Wind Brain — what bank is the wind hitting?

## 1. The convention (get this right once)
- **Wind direction is the bearing the wind blows FROM** (270° = west wind). The app asserts this in tests (`WindFieldGrid.swift`: `fromDeg`, arrows fly toward `fromDeg+180`).
- **Fetch is measured the opposite way: look INTO the wind** — from the bank toward `fromDeg` — over open water to the first land (shore or island). The water the wind crossed before it reached the bank builds the chop.
- A bank **faces** the bearing from the bank toward its adjacent water. A bank on the NE shore of a lake **faces SW**.
- Therefore: **wind FROM the SW hits the shore that is located at the NE end and faces SW.** That is the downwind shore: the longest water run ends there. The shore at the SW end faces NE, has land immediately upwind, and is the protected one.
- Wording trap: "northeast-facing shore" is ambiguous in English (location NE vs facing NE). Product and code should say **"NE shore" (location)** or **"faces SW" (orientation)** and never "NE-facing" for the downwind shore of a SW wind.
- Verified by **G1 unit tests: 7/7 PASS** (`research/wind-brain/polygon_fetch.py test`): on a 10 km × 2 km lake, wind FROM W gives the east bank 10.0 km and the west bank 40 m; wind FROM E reverses it; crosswind from N gives ≈ the 2 km width; wind FROM SW on a square lake gives the NE corner 8.5 km and the SW corner 20 m; an island blocks the centre-line (5.4 km) but not the flank (10 km). Independent check against the **frozen NHD tables**: the best agreement of 16-direction fetch profiles over 72 lakes is at **zero shift** (median ρ 0.65 at 0°, ≤ 0.46 at any other rotation and 0.03 when mirrored), so the shipped tables use the same convention.

## 2. What already exists (do not rebuild)
For the 4 live lakes (+70 tables) the Brain code (`sector_wind/bowfishing.py`) already computes, per bank: effective 9-ray fetch (±12°), CEM wave height, a **PROTECTED / LOW / MODERATE / HIGH / EXTREME** rank, best/worst banks for a wind, **nearby alternatives** within 2/5/10 km, a plain-language reason ("sheltered: land within 250 m on every upwind ray"), and `firm`/`boundary` confidence. Findings from the prior engine report (15 mph SW, Guntersville): 8.4% High, 32% Protected; **72–78% of banks change rank between SW and NE wind** — the per-bank answer is the product value, a lake-wide "it's windy" hides it. It is research-only and not published.

## 3. Proposed simple vocabulary (DIRECT / CROSS / PROTECTED / HIGH FETCH)
Relative angle α = angle between wind-FROM bearing and the bank's facing bearing.

| Label | Rule | Meaning for a bowfisher |
|---|---|---|
| **DIRECT** | α ≤ 45° and exposure ≥ MODERATE | wind is blowing straight onto this bank across open water |
| **CROSS** | 45° < α ≤ 90° | wind skims along the bank; chop arrives at an angle, boat drifts along shore |
| **PROTECTED** | α > 90° (wind comes over land) **or** exposure = LOW | lee of land; the best place to start |
| **HIGH FETCH** (tag) | frozen-CEM chop ≥ 6 in at the forecast speed (≈ ≥ 5 km at 12 mph, ≥ 2 km at 18 mph) | long open-water run behind the wind: the worst-case bank |

Fetch × speed → exposure (frozen CEM, 6 h steady; `G6`): at **8 mph** LOW below ~250 m, MODERATE to 5 km, HIGH only at ≥ ~10 km; at **12 mph** LOW < 250 m, HIGH ≥ ~5 km; at **18 mph** HIGH ≥ ~2 km; at **25 mph** HIGH ≥ ~1 km and nothing under 100 m is LOW. This matches the Stage 3D.2 table (coves 100 m Protected→Ripple at 12 mph; 5 km mainstem Light→Moderate at 10 mph).

### G5 test (pre-registered) — **PASS on 64 of 71 lakes (90%; line ≥ 80%)**
For each frozen-table bank, wind at 12 mph from 8 directions: **LEE banks (α > 90°) are HIGH exposure 0.3% of the time (median across lakes; line ≤ 5%)** and median effective fetch DIRECT/LEE is **15× (median; line ≥ 5×)**. The 7 failing lakes are the largest open water, e.g. (Salton Sea 8.0% of LEE banks HIGH, Maurepas 7.2%, Sevier 6.8%, Flathead 6.4%, Oneida 6.0%, Mille Lacs 5.7%): at 12+ km fetch even 30 m standoff from the "lee" shore leaves a long run at a shallow angle. **Informational AUC (DIRECT flag predicts HIGH): median 0.70 (< 0.75).** Meaning: the orientation label alone is not a good predictor of high exposure; a bank facing the wind in a 300 m cove is DIRECT but not HIGH. **The label must be combined with fetch; fetch carries the signal.** Orientation's own job is "protected by land upwind" and "which way to look".

## 4. Lake-level answers to the bowfisher's questions
| Question | Computation | Status |
|---|---|---|
| Which side of the lake is protected tonight? | banks with lowest effective fetch in the wind direction, grouped by shore sector (use the 16-direction median/p90 profile) | geometry exists for 74 lakes (frozen) and 544 polygon-estimated |
| Will this bank get hammered? | bank rank (CEM) at forecast speed, with `firm`/`boundary` confidence | exists for 4 lakes, computable for 70 more |
| Is this cove sheltered? | effective fetch < 250 m on all 9 rays, or α > 90° | exists |
| Long open fetch hitting this shoreline? | HIGH FETCH tag | exists |
| Where should I start looking? | nearest PROTECTED/LOW bank cluster to the ramp or user, from `nearby_alternatives` logic | exists (research) |

## 5. Limits that must be shown to users (not hidden)
- Exposure is **modelled** (fetch + wind speed + duration), **never field-validated** (B3/D2 = 0). It should be labelled as a model estimate.
- The wind speed is **one lake-wide land-referenced forecast**; over-water speed is unvalidated (likely higher).
- The surface physics has a **texture floor** that ignores local wind shelter (trees, bluffs): a calm, tree-lined cove in 15 mph wind can still read "Light chop" (prior engine report's largest product gap).
- Banks narrower than the raster (9.5% of Wheeler, 8.8% of Wilson) are **Unknown**, never Protected.

## 6. Result
Bank-impact concepts are well supported geometrically (G1 7/7, G5 90%), the convention is verified against the shipped tables, and the engine already ranks banks. The research-supported advance is **vocabulary + fleet coverage**, not new physics (`WIND_FLEET_SCALING.md`).
