# Customer wind provider — decision paper (2026-10-13)

**Recommendation: MOVE customer wind to the Brain's NBM-based source — staged, gated, not executed.** Do not switch anything until Michael approves and the gates below are met. This paper changes nothing.

## The two paths
| | Customer wind today | Wind Brain source |
|---|---|---|
| Source | Open-Meteo `/v1/forecast`, Best Match (no `models=`): HRRR to ≈ +46 h then GFS; raced with a different stitched historical-forecast host as fallback | NOAA NBM v5.0 direct (NODD) + RTMA-RU "now" + METAR evidence, archived by `wind-hourly` |
| Reaches customers | Engine `/conditions` (gauge, gust penalty, 7-night outlook), app cards | Shadow only: Brain RTDB for 4 lakes; not read by the app |

## Comparison (evidence: Stage 3D/3D.1/3D.2 bake-offs and the 2026-10 research; land METAR stations at 4 lakes, 5 months)
| Criterion | Current (HRRR/GFS via Open-Meteo) | Brain (NBM) | Edge |
|---|---|---|---|
| Accuracy, night speed MAE | 1.38 m/s | 0.82–0.84 m/s | Brain |
| Night bias | +1.13 m/s (over-forecasts calm nights) | +0.14 … −0.04 m/s | Brain |
| Direction within 22.5° | 0.62 | 0.72–0.76 all hours; **0.81 / 0.97** at night when forecast 5–10 / ≥ 10 mph | Brain |
| Windy-night speed | HRRR point value is less low-biased on windy nights (−3.6 vs −5.7 mph at observed ≥ 10 mph; detects 43% of ≥ 10 mph hours, FAR 0.68) — but over-forecasts calm nights by +2.9 mph | NBM point value under-forecasts (detects 15%, FAR 0.22); the P90 risk flag restores parity (POD 0.49, FAR 0.64) | **Current for the point value; Brain only with the risk flag** (`WIND_PROVIDER_SHADOW_COMPARISON.md`) |
| Gust | HRRR gust: ≥ 20 kt POD 0.19, FAR 0.93, conditional bias −1.6 m/s | NBM gust: POD 0.04, FAR 0.88, bias −1.9 m/s | Neither is usable; keep gust penalty conservative |
| Tonight usefulness | hourly speed only in the 7-night outlook (no direction, no gust) | tonight block: direction ≥ 5 mph, category, easing, breezy-risk, confidence | Brain |
| Freshness | on request, 30 min cache; the fallback host is a different product | hourly cycle at :05; RTMA 15 min; stale flags and `retrievedAt` | Brain (provenance) |
| Cost | Free tier today; a paid plan or a different route is needed for steady subscription use (terms to be reviewed privately) | NOAA public data, one CONUS decode per cycle already running; fleet sampling adds no GRIB reads (`WIND_FLEET_SAMPLING.md`) | Brain |
| Coverage | global, every lake | CONUS grid for ≈ 600 lakes; Alaska (12) and Hawaii (9) lakes need the NBM AK/HI domains (not tested); 4 lakes live today | Current, until fleet sampling is built |
| Consistency | wind shown ≠ wind used for exposure (different model, time basis, grid) | the same wind drives the card, tonight block and bank exposure | Brain |
| Bank-exposure support | none | native: from-direction + speed feed fetch/CEM; labels and tiers | Brain |
| Confidence | none | stale flags, P90 risk, confidence word | Brain |
| Operational complexity | none (hosted API) | Engine must serve it: new read path, monitoring, fallback; `wind-hourly` is a SHADOW job with < 30 live days of uptime evidence | Current |

## Why move
The accuracy gap (MAE −40%, night bias from +1.1 to ≈ 0, direction +0.10–0.14) is the largest verified improvement available without hardware, it removes the inconsistency between the displayed wind and the exposure model, and it unlocks tonight/bank features for customers. Open-Meteo's own NBM (`ncep_nbm_conus`) is numerically the same product (mean abs diff 0.067 m/s) — a valid *transport* option if Michael prefers a hosted API to serving NBM from the Engine.

## Gates before any switch (all must hold)
1. 30 complete live UTC days of `wind-hourly` ≥ 99% archived, median age ≤ 90 min (earliest ≈ 2026-11-07).
2. Fleet sampling built and run for the lakes being served (otherwise the 617 non-live lakes would regress to "no wind").
3. Automatic fallback to the current provider when the Brain cycle is stale (> 3 h), labelled as the fallback in provenance.
4. Gust penalty and wind gate (`windCurve`, gust excess) re-reviewed: they were tuned on HRRR gusts; NBM gusts are not better and tend lower.
5. A side-by-side shadow period where the Engine logs both winds (no customer change) and Michael reviews disagreements.
6. H2 outcome recorded (sealed until 2027-01-01). The decision does not need H2 to *start* shadowing; customer promotion of any new claim does.
8. **Windy-night handling (new, from the shadow comparison):** the wind gate / gauge must be driven by the risk-aware value (P90 / `ifItBlows` or the flag), not the NBM mean alone, otherwise windy nights would look calmer to customers than they do today.
7. Provider-terms review for whatever remains on Open-Meteo (other fields stay there regardless).

## What would change the recommendation
A materially better source for the windy tail (none found), evidence that NBM degrades outside the Southeast (only 4 lakes, 8 land stations validated), or an unrecoverable Engine operations cost.

## Not decided here
Executing the switch, API changes, or app changes. Keep current customer provider until Michael approves.
