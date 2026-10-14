# Bowfisher Wind Readiness (read-only; NOT the canonical score)

**Would I use this before choosing which side of the lake to bowfish? PARTIALLY**

Trust the wind (speed, direction, gust display) and the shoreline geometry; treat bank calls as advisory until validated. Not yet done: Forecast reliability (prospective); Bank exposure (protected / partial / exposed).

| Layer | Capability | Claim level | Maturity | Note |
|---:|---|---:|---|---|
| 1 | Provider wind speed | 1 | VERIFIED |  |
| 1 | Provider wind direction | 1 | VERIFIED |  |
| 1 | Provider gust (display) | 1 | VERIFIED | forecast runs low in strong wind; display only |
| 2 | Forecast reliability (prospective) | 2 | IN_PROGRESS | 6/30 prospective days |
| 3 | Fetch / direction relative to bank | 2 | VALIDATED |  |
| 3 | Bank exposure (protected / partial / exposed) | 3 | CALIBRATION | v2 rules frozen; field truth pending |
| 4 | Surface / chop (calm / moderate / rough) | 3 | NOT_VALIDATED | classes defined; field truth pending |
| 5 | Tonight recommendation | 3 | CALIBRATION | internal only |
| 5 | Confidence and refusal (UNKNOWN works) | 2 | VERIFIED | UNKNOWN for point-only / below-resolution / light wind / boundary banks |

Canonical score: {'displayed': 3.3, 'raw': 3.29, 'v2SimulationNonOfficial': 4.42}
Reliability: {'validDays': 6, 'target': 30, 'projectedGate': '2026-11-07'}
