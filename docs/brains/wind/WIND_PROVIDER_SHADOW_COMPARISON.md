# Provider shadow comparison — Open-Meteo Best Match (HRRR proxy) vs Wind Brain NBM

**Read-only. No customer behavior changed. H2 not read.** Code: `jobs/wind-hourly/research/provider_shadow.py`; full row matrix (4,928 rows: lake, station, init/valid, lead, both providers' direction/speed/category, observation, errors, winner, notes) is kept outside git (`Sector_Research_Data/wind-brain/out/provider/matrix.csv`); aggregates in `data/provider_shadow.json`.

## What is and is not being compared
- **Open-Meteo side = HRRR 10 m wind** from the archived U/V cycles at the same stations. Stage 3D.1 verified by exact-value matching that Best Match for the US is HRRR out to ≈ +46 h (GFS after). It is a *proxy*: the live customer path uses a single 0.01° point request and an `current` value, and may fall back to a different stitched host. The Open-Meteo archive itself cannot return "the forecast as issued" for Best Match, so the real customer feed cannot be replayed historically.
- **Window: CAL+H1 only (inits 2026-05-06 → 2026-10-06), 8 METAR stations, 4 lakes, tonight rows** (init 12Z lead 12/18, init 18Z lead 6/12; valid 00Z/06Z). **The live period (inits ≥ 2026-10-07) is H2 and is not used.** A live side-by-side of the two providers' values would be derived from sealed data, so none was made. Until 2027-01-01 the only live comparison that is allowed is *future* Engine-side logging of both winds (design in the provider decision); its disagreement statistics would be labelled PROVIDER DISAGREEMENT, not accuracy.
- Truth = METAR (land). Rows without an observation (204) are PROVIDER DISAGREEMENT only and are excluded from every accuracy number. **Land truth cannot say which provider is right over open water.**

## Results (n = 4,724 rows with all three values)
| | NBM | Open-Meteo (HRRR proxy) |
|---|---|---|
| Speed bias / MAE (mph) | −0.38 / 2.05 | **+2.01 / 3.03** |
| Tonight category exact | **0.792** | 0.640 |
| Row winner (|error| smaller by > 0.5 mph) | **2,694** | 1,351 (679 ties) |
| Direction within 22.5° (both ≥ 5 mph, obs ≥ 2.6 m/s; n = 316) | **0.782** | 0.703 |
| Circular MAE | **18.3°** | 21.4° |
| Mean absolute disagreement between the two | 2.65 mph | |
| Trend (00Z→06Z, n = 2,324): accuracy / "easing" precision | **0.554 / 0.653** | 0.479 / 0.571 (always-steady baseline 0.417) |

By lake (NBM vs proxy MAE): Guntersville 1.95 vs 2.91, Pickwick 2.00 vs 3.60, Wheeler 2.25 vs 2.77, Wilson 1.77 vs 2.85; direction better for NBM on 3 of 4 lakes (Pickwick: proxy 0.865 vs 0.827 on n = 52). By lead: NBM better at +6/+12/+18 h; category exact 0.705/0.793/0.879 vs 0.553/0.635/0.738.

## The windy-night caveat (important, previously under-stated)
| Observed class | NBM bias / MAE / cat. exact | Proxy bias / MAE / cat. exact | Row winners (NBM/proxy/tie) |
|---|---|---|---|
| < 5 mph (n 3,658) | +0.42 / 1.67 / **0.927** | +2.89 / 3.21 / 0.657 | **2,436** / 745 / 477 |
| 5–10 mph (n 900) | −2.66 / 2.90 / 0.364 | **−0.52 / 2.07 / 0.613** | 222 / **500** / 178 |
| ≥ 10 mph (n 166) | −5.65 / 5.89 / 0.139 | **−3.62 / 4.24 / 0.404** | 36 / **106** / 24 |

- **Conditioned on what actually happened, HRRR beats NBM on every windy night** because it over-forecasts everywhere (it wins the windy tail by being too high on calm nights, where it loses badly). Conditioned on what the *customer is shown*, NBM wins every forecast class (forecast 5–10 mph: bias +0.26 vs +1.14, winners 299 vs 216).
- **Stronger-wind detection (observed ≥ 10 mph, 166 events):** NBM point forecast ≥ 10 mph: POD 0.15 / FAR 0.22. HRRR proxy ≥ 10 mph: **POD 0.43 / FAR 0.68**. NBM P90 ≥ 10 mph (the Brain's risk flag): **POD 0.49 / FAR 0.64**. So the risk flag brings NBM to parity with HRRR's windy-night detection, at the same false-alarm cost, while keeping NBM's calm-night accuracy. Using the NBM *point* forecast alone for windy-night warnings would be a regression from today.
- **Product-gauge implication:** the Huntability wind gate currently reacts to HRRR's higher windy-night speeds. Switching the gauge input to the NBM point value would make windy nights look *calmer* than today. Any customer switch must drive the wind gate from the risk-aware value (P90 / `ifItBlows`), not the NBM mean alone. This is a new gate in the provider decision.
- Direction by observed sector: NBM is weaker than the proxy in wind-from W (0.50 vs 0.67, n = 18) — too few to act on; the larger sectors (S, N, SW) favour NBM.

## Missing / stale behavior and availability
- Missing values in the replay: 0 NBM and 0 proxy rows missing among rows with observations; 204 rows had no METAR (PROVIDER DISAGREEMENT only).
- Freshness: NBM archives with init/valid/lead/retrievedAt and is considered stale after 3 h; Open-Meteo exposes no model init or retrieval time (hidden Best-Match model, silent fallback to a different stitched host), so its staleness cannot be audited.
- Spatial/fleet availability: Open-Meteo is global for all 621 lakes with no work. NBM covers CONUS (≈ 600 lakes) from one grid; Alaska/Hawaii lakes (21) need their NBM domains (untested); fleet sampling code is ready but not wired.

## Verdict (decision input, not a switch)
For the bowfishing outputs that dominate nights — calm vs light, direction, easing — NBM is more accurate on land truth. For stronger winds NBM alone is worse than the current provider's *point* value and only matches it when the P90 risk flag is used. Recommendation stays: move customers to NBM **only with the risk-aware wind value feeding the gauge**, after shadow logging. Over-water accuracy of either provider is unknown.
