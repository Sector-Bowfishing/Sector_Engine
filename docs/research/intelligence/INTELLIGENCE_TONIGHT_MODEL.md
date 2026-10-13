# Tonight model: practical temporal synthesis

**Rule that governs everything here:** Intelligence may not know the future better than its specialists do. A factor is usable at a time checkpoint only if its Brain publishes a value for that time (rule R7). Otherwise the factor is UNKNOWN at that checkpoint. No quiet persistence.

## 1. What each specialist can actually say about tonight
| Brain | Time structure it publishes | Horizon | Skill statement on record | Implication |
|---|---|---|---|---|
| Wind | `hourly[]` (≤24 entries), `transitions[]` crossings of 5/10/15/20 mph, `trend` steady/rising/easing | ≈24 h | candidate NBM: speed MAE 2.19 mph; night MAE 1.88; direction within 22.5° only 75.8% (gate 85% failed); **15 mph events: POD 0.0** (production HRRR proxy 0.108); H2 hold-out sealed to 2027-01-01 | use wind in categories (calm <5, light 5–10, breezy 10–15, windy ≥15); do not claim a windy night is coming with confidence; a "lays down" claim needs the Brain's own `trend` and is capped MEDIUM |
| Water Temp | daily model `forecast[]`; `trend24hF` | ≈4 days | LOLO RMSE 3.40 °F; no forecast-vs-persistence validation; no diurnal curve | one value per night; constant across checkpoints; kind MODELED unless a fresh sensor anchors it |
| Water Clarity | current state; Engine rain-decay for future nights | no true forecast | R3.1 candidate is research-certified, undeployed; production `rain-decay-v0` is uncalibrated | clarity tonight = current state, labelled "current"; if rain is forecast inside the window the future clarity is UNKNOWN, not "unchanged" |
| Lake Brain | current level, trend, guide difference | none (operator plan context only) | | level trend now; no forecast level (flats gained/lost tonight is unknown) |
| Biological | seasonal state (calendar/temperature-driven) | n/a | state model not started | species state at the night's temperature, label its basis |
| Depth / Vegetation (future) | static fields; effective depth moves with level; vegetation seasonal | n/a | | enter as static-with-age; effective depth must reference the level actually used |
| Weather / sky / moon (no Brain today) | hourly Open-Meteo, astronomy | days | | **ownership gap**, see §5 |

## 2. Checkpoints
`NOW`, `SUNSET`, `DUSK` (astronomical dusk: shooting realistically begins), `MIDNIGHT`, `PRE-DAWN`. Production's window is astro-dusk to sunrise (`ConditionsInputBuilder`), and `nights[]` repeats it for 6 nights. Reuse those definitions; do not invent a new window.

At each checkpoint: build factor records with `leadHours = checkpoint − now`, apply R7, rate each species (rules R1–R9). Result: a short strip per species, e.g.
`NOW poor (wind) → DUSK worth a look → MIDNIGHT start here → PRE-DAWN worth a look`.

## 3. Derived statements (each is a function of the strip, never free text)
- **Best window:** the longest contiguous run of checkpoints at the maximum rating (min rating `WORTH_A_LOOK`). Its edges are quoted at the resolution of the coarsest *time-varying* deciding factor (wind: hourly; others: night) ("from about 9 pm", never "9:12").
- **Improving / steady / worsening:** compare first and last checkpoints with all deciding factors known (`trend()`; UNKNOWN when fewer than 2). The *driver* is the factor whose state changed, quoted with its source: "improving: wind lays down [wind@brain-1.0, hourly]".
- **Current vs tonight:** NOW is a measured/analysis-based statement; later checkpoints are forecast statements. They are displayed differently (confidence for forecast checkpoints is capped MEDIUM by R6 `lead_h>0`).
- **Multi-night (nights +1…+6):** only the factors that have a forecast (wind to ≈24 h; temperature to ≈4 d). Nights beyond a Brain's horizon rate on fewer factors, so the rating is `UNRANKED` or capped; production currently fills them by persistence (audit §5.3).

## 4. What the current code does and what changes
| Today (Engine `nights[]`) | Research recommendation |
|---|---|
| flat −10 confidence per night, cap −50 | confidence follows the weakest *available* factor at that lead; horizon-limited factors become UNKNOWN |
| level/stage/discharge/gust/pressure/humidity/fog spread silently persisted | persisted values are labelled `HELD` and are ineligible to raise confidence or the top class |
| a nearby turbidity gage freezes clarity for all nights | clarity held-current, with future rain flagged as unknown-direction |
| no trend field | strip + trend with driver |
| tonight == headline gauge (parity test exists) | keep the parity property in tests |

## 5. Ownership gap: weather, sky, moon, fog, warnings
No Brain owns precipitation, cloud, fog spread, moon geometry or NWS warnings; production computes them inside `/conditions` (Open-Meteo, in-process astronomy, NWS alerts). They decide gates (storm, warning, fog, rain) and the darkness/moon factor. Recommendation: treat them as a documented **Intelligence input adapter with provenance** (source, issuedAt, horizon), not as science Intelligence owns silently, until a Weather/Sky component exists. Gate thresholds (what rain/fog ends a night) remain Intelligence's *impact* decisions and must be versioned.

## 6. Test plan
- Property: removing a factor's forecast beyond its horizon never raises any checkpoint rating (R7+R1).
- Property: persistence-labelled factors never increase confidence.
- Golden: `tonight == nights[0] == headline` parity retained across the migration.
- Field: record, per checkpoint, observed sightings per effort-hour; evaluate "best window" against realized windows only on trips whose effort spanned multiple checkpoints (`VALIDATION_STRATEGY` §4).

## 7. Limits
No hourly water temperature or clarity forecast exists, so within-night "improving" can only come from wind, weather, moon/dark and (later) level. That is fine: those are the factors that actually change within a night.
