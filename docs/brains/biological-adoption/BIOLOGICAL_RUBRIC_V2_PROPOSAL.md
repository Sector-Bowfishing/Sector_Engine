# Biological rubric: the bowfisher value test, and `biological-state-score-v2` (PROPOSAL; isolated branch `feat/biological-score-v2`; not wired)

For each v1 dimension: what does a higher value do for a bowfisher?

| v1 dimension (weight) | What a higher value does for a bowfisher | Verdict |
|---|---|---|
| registryCompleteness (10) | Nothing directly: confirms every species row is assessed or explicitly NOT_ASSESSED | hygiene: report, do not score |
| assessedCoverage (15) | Counts saltwater, protected and non-target rows as "coverage"; marking a row NOT_ASSESSED lowers the score | replace with target-species coverage |
| knowledgeDepth (20) | Median over ALL rows; 14 near-empty non-target rows set the median | replace with target-species knowledge |
| evidenceQuality (10) | Mixes maturity labels: partial review can lower it (2.0 to 1.0) | split into evidence strength and human review |
| contradictionsGaps (10) | Documentation hygiene; capped species gain nothing | report, do not score |
| regionalTransfer (5) | Whether the advice fits Southeast lakes | keep, rename regionalApplicability, weight up (v1.1 already consumes it) |
| biologicalStateImpl (15) | Advice for a specific lake right now | keep (stateImplementation) |
| biologicalStateValidation (10) | Proof the advice finds fish | keep (fieldValidation) |
| productionIntegration (5) | The advice reaches the bowfisher | keep, weight up (customerUsefulness) |

## v2 dimensions (weights sum to 100)
targetKnowledge 25 · conditionCoverage 15 · evidenceStrength 10 · humanReview 5 · regionalApplicability 10 · stateImplementation 15 · fieldValidation 10 · customerUsefulness 10. Gates: State NOT_STARTED <= 4.0; no VALIDATED target <= 6.0. Honesty about UNKNOWN is enforced by tests and gates, not points. Non-target species never move the score.

## Species-v2 semantics finding
The arithmetic (an unscored domain counts 0) is a defensible reading of "missing evidence earns nothing". The defects were (1) **unencoded practical knowledge**: profiles had not ingested what the packets and the sweep contain (fixed by this adoption) and (2) a **calibration anchor** that caps a single credible account at 3-4, stricter than the practical standard Michael set. The practical standard is applied in tooling and queued for ratification (D7); the private standard text and the domain weights (enforced by the bundle validator) are unchanged. The food/feeding domain (10%) was not researched by the sweep and stays unknown for most fish, which caps species-v2 at 9.0 until it is studied or reweighted (a v3 question, not changed here).

Results: see BIOLOGICAL_BOWFISHER_KNOWLEDGE_ADOPTION.md (current rubric after encoding 5.2; v2 4.3).
