# Wind Brain — H2 holdout pre-registration (frozen 2026-10-13, before H2 is read)

H2 = NBM v5.0 cycles with init 2026-10-07 00Z → 2026-12-31 23Z, scored against METAR at the 8 frozen stations (4 lakes). Sealed until **2027-01-01 00:00 UTC** by the earlier campaigns and by code (`brain/contract.py: H2_SEALED_UNTIL`). The criteria below were derived from the CAL+H1 research (`docs/wind-research/WIND_FORECAST_VALIDATION.md`) and are **frozen**: they cannot be edited after any H2 row is read. A change needs a new file `WIND_H2_PREREG_v2.md` and a new freeze, and v1's outcome stays on record. `WIND_H2_PREREG.freeze.json` stores the SHA-256 of this file; a test fails if it changes.

## Run rules
1. **One shot.** The runner (`sector_wind/h2.py`) writes a ledger entry on its first execution that reads H2 and refuses every later run. If it fails, the failure is recorded; criteria are not tuned.
2. **Release gate.** The runner refuses before 2027-01-01 00:00 UTC, and refuses unless every init hour through 2026-12-31 23Z that exists in the archive is included (the window is whatever the archive actually holds; missing cycles are counted and reported, not imputed).
3. **Same definitions as the product.** Categories, confidence labels and the breezy-risk flag are computed by the same functions the Brain uses (`brain/tonight.py`), never re-implemented for the test.
4. **Rows.** Night = valid hour 01–08 UTC. Tonight rows = init 12Z with lead 12/18 or init 18Z with lead 6/12 (valid 00Z/06Z). Observation = METAR within 10 min of the hour. Calm direction = METAR speed < 2.6 m/s excluded from direction scoring. Speeds in mph; 1 mph = 0.44704 m/s.
5. **INSUFFICIENT is not PASS.** A test below its minimum count is reported INSUFFICIENT and the related product claim stays withheld.

## Tests and thresholds
| ID | Claim guarded | Rows | PASS rule | Min count |
|---|---|---|---|---|
| H2-D1 | direction when forecast 5–10 mph | night, lead ≤ 12 h, forecast 5–10 mph, observed ≥ 2.6 m/s | within 22.5° ≥ **0.75** | 500 |
| H2-D2 | direction when forecast ≥ 10 mph | same, forecast ≥ 10 mph | within 22.5° ≥ **0.85** | 100 |
| H2-S1 | tonight speed category (calm <5 / light 5–10 / breezy 10–15 / windy ≥ 15) | tonight rows | exact ≥ **0.65** AND within-one ≥ **0.95** AND exact > always-modal-category baseline | 1000 |
| H2-S2 | strong-wind underforecast is real and conservative handling is warranted (descriptive, not a claim) | tonight rows with observed ≥ 10 mph | report mean signed bias (forecast − observed); expectation negative | 30 events |
| H2-T1 | "easing overnight" | all pairs valid 00Z→06Z from 12Z/18Z inits | three-class accuracy ≥ always-steady baseline + **0.05** AND precision of forecast "easing" ≥ **0.55** | 1000 pairs, 100 forecast-easing |
| H2-T2 | lay-down (guard against adding the claim) | obs ≥ 8 mph at 00Z and ≤ 5 mph at 06Z | claim allowed only if POD ≥ **0.40** AND FAR ≤ **0.50** (expected to fail; the product does not make the claim either way) | 50 events |
| H2-T3 | rising (guard) | pairs | claim allowed only if recall ≥ **0.40** AND precision ≥ **0.55** | 50 observed rises |
| H2-B1 | "could turn breezy" flag (NBM P90 sustained ≥ 10 mph at any tonight hour) | tonight rows | P(observed ≥ 10 mph \| flag) ≥ **3×** P(observed ≥ 10 mph \| no flag) AND POD ≥ **0.40** | 30 observed events and 50 flagged rows |
| H2-C1 | HIGH confidence means the direction is dependable | rows labelled HIGH by the product rule, observed ≥ 2.6 m/s | direction within 22.5° ≥ **0.75** | 300 |
| H2-C2 | confidence is ordered | HIGH vs not-HIGH rows (observed ≥ 3 mph both) | direction error > 45° rate of HIGH ≤ **0.5×** the rate of not-HIGH | 200 each |

Confidence rule frozen here (implemented in `tonight.py`): HIGH = tonight mean forecast ≥ 5 mph and no breezy-risk flag; MEDIUM = mean 3–5 mph, or breezy-risk flag; LOW = mean < 3 mph or forecast unavailable/stale.

## Honest-reporting commitments
- Each test is reported PASS / FAIL / INSUFFICIENT with its numbers and counts. Failures are written to `WIND_H2_RESULT.md` and are not re-run.
- A passing H2 does not promote the Wind Brain, change the Certification score, or change customer wind; the canonical scorer and Michael decide separately.
- Fleet/bank exposure and fetch are **not** tested here (no independent truth); they remain MODELED/ESTIMATED.
