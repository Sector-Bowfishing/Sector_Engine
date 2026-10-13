# Tonight scenarios — practical regression fixtures

Tests: `jobs/wind-hourly/tests/test_tonight_scenarios.py` (and the unit tests in `test_adoption.py`). All are offline and deterministic. `tonight.simple()` is the customer-simple contract: words only, `None` = **no claim** (never "calm", never "low risk").

Example output (Scenario D, with a DIRECT long-fetch AUDITED bank supplied to `simple()`):
```
wind: SW about 6 mph   tonight: LIGHT   risk: COULD TURN BREEZY   trend: None   bank: DIRECT   fetch: HIGH   confidence: MEDIUM
caveats: modeled forecast; land-referenced · not an over-water measurement
```
| ID | Scenario | Expected | Test |
|---|---|---|---|
| A | 8 mph from SW, ~9 km open fetch, NE bank (faces SW) | DIRECT, fetch MODERATE/HIGH, tonight LIGHT | `test_A_…` |
| B | 8 mph from SW, SW cove | ~60 m cove PROTECTED (short fetch); 400 m side cove CROSS (ripple); 3 km skim CROSS; ESTIMATED borderline cove ≤ PROTECTED-or-CROSS, never more protective than audited | `test_B_…`, `test_estimated_tier_protected_needs_margin` |
| C | 3 mph variable | direction not shown, "light and variable", bank labels UNKNOWN (< 5 mph), no fetch word, no risk | `test_C_…` |
| D | NBM P50 light, P90 breezy | tonight LIGHT + COULD TURN BREEZY, confidence MEDIUM, `ifItBlows` breezy, note says "NOT a maximum" | `test_D_…` |
| D2 | P90 below 10 mph | risk **None** (no statement); output never contains "low risk" or "calm" | `test_D2_…` |
| E | Forecast easing 10→3 mph | trend EASING, tonight not "calm", none of "calm by / lay down / will be calm / dies down" | `test_E_…` |
| F | Forecast rising 4→12 mph | trend None (increase not claimed) but risk flag kept | `test_F_…` |
| G | Strong forecast 16 mph | WINDY; no gust, wave or inch wording | `test_G_…` |
| H | Stale forecast (> 3 h) | confidence LOW + "forecast is stale" caveat | `test_H_…` |
| I | Forecast unavailable | every field None, confidence LOW | `test_I_…` |
| J | Blocked/point-only lakes (AK, identity-risk audited, no polygon) | never get bank words (`exposure_allowed` false) | `test_J_…` |
| K | ESTIMATED bank | "bank exposure is an estimate" caveat; DIRECT/CROSS collapse to EXPOSED; AUDITED keeps DIRECT | `test_K_…` |

## Stress-test findings on the contract
- Simple words suffice; internal Hm0 and percentiles stay out of `simple()`.
- Absence of the risk flag must render as **nothing**; the strong-wind validation shows half of breezy hours are unflagged.
- `wind` range uses the forecast min–max over the evening; it can understate the real range (observed > 10 mph ran 4.6–6 mph above forecast), so the range is labelled forecast and the category is a floor.
- Direction is hidden under 5 mph tonight, and bank words are hidden under 5 mph now.
