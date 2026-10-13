# Depth Maturity Re-evaluation (research rubric; NOT a Brain score)

Two separate things, never mixed:

* **RESEARCH MATURITY** (rubric on `docs/depth-brain-research`: `DEPTH_BRAIN_RUBRIC_PROPOSAL.md`): was **4.3 / 10**. This is a judgment about the state of the evidence, not an Engine score.
* **LIVE BRAIN MATURITY**: Depth Brain has **no official score**. `/scores/depth` does not exist; the platform scoring module is untouched; the registry node carries no `score`. It is a shadow, unregistered-for-customers Brain at readiness `PROFILED` (5 lakes `CALIBRATION`).

## Re-evaluation after the effective-depth implementation (research rubric)

| Dimension (weight) | Was | Now | Why |
|---|---|---|---|
| Source authority (15, critical) | 5 | 5 | unchanged: 103 tier A/B lakes; datum audit adds provenance, not new surveys |
| Coverage (15, critical) | 4 | 3 | honest recount: shift defensible for **92** lakes (research said 265) because datum proof is required; 5 live today. Zones: 94 lakes with reference shares, 0 effective |
| Absolute depth accuracy (10) | 3 | 3 | no absolute depth is published; sigma components are estimates |
| Relative morphology (15, critical) | 3 | 3 | unchanged; no scalable flats method (policy codified) |
| Effective-depth capability (15, critical) | 5 | 6 | engine, contract, sigma propagation, datum rules, live dry run on all 5 pilots, 106 tests; but no event/field validation and zone re-binning withheld |
| Validation (15, critical) | 5 | 5 | arithmetic tested; science not field-validated |
| Confidence / provenance (10) | 5 | 7 | tiers, datum status, licence gate, reasons, fingerprints, contract fixtures implemented in code and tests |
| Fleet scalability (5) | 4 | 4 | the unlock path is data-only, but 233 lakes lack datum evidence and 23 states lack contours |
| **Weighted overall** | 4.3 | **4.5** | 0.15x5 + 0.15x3 + 0.10x3 + 0.15x3 + 0.15x6 + 0.15x5 + 0.10x7 + 0.05x4 |

Gates (overall >= 8.0, every critical >= 7.5): **not met**. The honest headline: the implementation raised effective-depth capability and provenance, while the stricter datum accounting lowered the coverage claim.
