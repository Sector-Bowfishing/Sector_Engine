# Is the research rubric measuring the right thing? (proposal only; the rubric is NOT changed)

> **UPDATE 2026-10-14 (long-run campaign): folded into the full official-score design in `DEPTH_OFFICIAL_SCORE_DECISION.md` (v2). The research rubric was not changed; its out-of-mission dimensions are replaced there by depthShareEvidence and shallowZoneActivation.**

The research rubric (`docs/depth-brain-research`, `DEPTH_BRAIN_RUBRIC_PROPOSAL.md`) was written before the product scope was settled. Product scope now (Michael, 2026-10-14): authoritative depth evidence where available; current water-level shift from a known reference pool; effective current depth for known depth evidence; shallow-zone shifts and dry/flooded bounds; confidence, provenance, uncertainty. **Not** full-lake hydrography, absolute depth for every spot, flats/structure maps. Three dimensions measure something Depth should not do, so they hold the maturity down regardless of how good the product is.

| Rubric dimension (weight) | Today | What it measures | What the product needs | Mismatch |
|---|---|---|---|---|
| Absolute depth accuracy (10) | 3 | foot-level absolute depth error | "known depth + level shift is right" | **Yes.** Depth publishes no absolute depth by design. Closest real capability: effective-depth adjustment error of known contours (TWDB desk validation: dry-share MAE 0.016, bounds coverage 1.0, 5 lakes) |
| Relative morphology (15, critical) | 3 | zones, flats, drop-offs, channels from a scalable method | shallow-zone shifts and dry/flooded bounds where survey-verified | **Yes.** Flats/drop-offs/channels are out of scope and GLOBathy/slope methods are closed. The real capability is shallow-zone bounds on survey-verified lakes (5) |
| Validation (15, critical) | 5 | independent, prospective, field validation of the whole Brain | proportion to the claim: a shift is a Level 2 derivation (formula + inputs + edge cases); interpretation claims need field validation | **Partly.** One dimension mixes "is the arithmetic and its input right?" (validated: 187 tests, live input check vs operator feeds, TWDB desk validation) with "does it match the water a bowfisher sees?" (field, not done) |
| Coverage (15, critical) | 4 | share of lakes with a defensible shift | the same, but weighted by where bowfishers fish and by LIVE state | Partly: counts defensible, not live (5 live) and not demand-weighted |
| Authority (15, critical) | 5 | share of lakes with instrument-survey evidence | surveys where they exist; shift-only is fine elsewhere | Partly: penalises lakes where shift-only is the correct product |
| Effective depth (15, critical), Provenance (10), Scalability (5) | 6 / 8 / 4 | | | match |

## Proposal (needs Michael's approval before any rescoring)
1. Replace **Absolute depth accuracy** with **Known-depth effective adjustment correctness** (error of shifted known contours against exact stage-area tables; evidence: TWDB preregistered validation; extend per survey-verified lake).
2. Replace **Relative morphology** with **Shallow-zone bounds on survey-verified lakes** (count of lakes with verified survey reference pool and passing preregistered validation, weighted by bowfishing relevance).
3. Split **Validation** into **Derivation validity** (formula, inputs, edge cases, provider verification; tests + Level 1 checks) and **Interpretation validity** (field/prospective). Only the second needs field data; the first can be scored today.
4. Make **Coverage** report both defensible and LIVE coverage (live is gated by Lake Brain).
5. Keep critical dimensions: datum correctness, effective-depth correctness, coverage (live), interpretation validity.

Why not change it now: the directive forbids changing definitions to raise a score. Until approved, maturity stays on the old rubric (4.75), and this document records that the old rubric under-reads the product. No indicative rescoring is published.
