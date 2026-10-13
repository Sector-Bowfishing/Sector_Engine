# Wind Brain — source research

**Question asked of every source:** does it materially improve bowfishing usefulness (speed, direction, gust, tonight)? Principle: do not replace a working reliable source because another sounds sophisticated. No provider was bought, called with credentials, or deployed in this campaign; this consolidates the prior bake-offs (Stages 3D.1/3D.2, score acceleration) and adds the bowfishing re-stratification from `WIND_FORECAST_VALIDATION.md`.

## Verdict
**Keep NOAA NBM v5.0 (direct, NODD) as the forecast, RTMA-RU for "now", METAR/MADIS for truth. Stop provider shopping.** The decision that matters is production's, not the Brain's: customers still get Open-Meteo Best Match (HRRR → GFS).

| Source | Role | Evidence | Improves bowfishing usefulness? | Decision |
|---|---|---|---|---|
| **NBM v5.0** (NODD) | Brain forecast | night MAE 0.82–0.84 m/s, bias −0.04…+0.14; best direction of those tested; probabilities (qmd P10/50/90) | Yes (baseline) | **Keep** |
| **HRRR** (via Open-Meteo Best Match) | Production | night MAE 1.38, bias +1.13, direction 0.62 | No: worse speed and direction | Move production off (Michael) |
| **GFS / ICON / ECMWF via Open-Meteo** | not used | look better only in the windy tail because they over-forecast everywhere; 1 km chop correct on calm nights 0.59 vs NBM 0.78 | No | Skip |
| **Open-Meteo `ncep_nbm_conus`** | transport option | numerically the same NBM (mean abs diff 0.067 m/s, direction identical) | Transport/terms only | Option |
| **RTMA-RU** (15-min analysis) | Brain "now" | typed `analysis`; anchoring forecasts to it at +1/+3 h with no on-lake sensor: no gain | "Now" yes; nowcast no | Keep |
| **METAR / AWOS / ASOS** (8 frozen) | truth | land only | Truth, not product | Keep |
| **MADIS mesonet** | possible truth | 33 usable stations near 4 lakes (23 ASOS/AWOS + 10 RAWS), none over water; 110 rejected, mostly citizen | Marginal | Validation breadth only |
| **Station LAMP** | tested | better ordinary MAE/bias and better 1 km chop decision in windy hours (0.55 vs 0.41) but event FAR 0.79 failed its gate; not available at non-MOS points | Possibly for decision | Stopped; an ordinary/decision pre-registration is open |
| **RRFS/REFS** | collector armed | NOAA not yet publishing operational cycles | Unknown | Wait until 2027-01 |
| **WindNinja** | tested | turn ≤ 2°, speed ×0.97–1.03 | No | **Stop** |
| **NBM P90 probability** | not in product | **V7:** P90 ≥ 10 mph tonight flag → P(obs ≥ 10 \| flag) 0.358 vs 0.019; POD 0.49 vs P50's 0.15 | **Yes, no new source** | **Candidate** (re-test on H2) |
| **NDBC / C-MAN / reservoir buoys** | wave truth 2017–25 | used for surface-physics validation | Validation | Keep |
| **Visual Crossing, Meteomatics US1k** | adapters built, untested | need paid keys with historical-forecast access | Expected low | Only if Michael wants |
| **On-lake anemometer** | not installed | only proven nowcast lever (−16% at +1 h); lifts the over-water cap | Yes | Hardware decision |

## What would actually move bowfishing accuracy
1. The problem is the **windy tail**, not model choice. No tested source fixes it without damaging calm-night accuracy.
2. **Use probability, not a new model:** the P90 flag recovers about half of ≥ 10 mph nights that the P50 forecast misses entirely.
3. **Direction is already fine where it matters** (≥ 5 mph at night, within 22.5° 0.77–0.97); no source change needed.
4. **Over-water speed** is the largest unknown and cannot be tested without an instrument (`WIND_FETCH_RESEARCH.md`).
