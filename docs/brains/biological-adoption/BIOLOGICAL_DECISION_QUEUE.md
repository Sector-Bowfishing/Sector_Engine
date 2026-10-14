# Biological decision queue (nothing here is applied; each item names who decides)

Status as of 2026-10-14. Canonical score **4.6**. Everything below is queued; none of it blocks other work.

## D1. Scorer ratification: `regionalTransfer` from `transferSummary` (Michael / platform owner)
* Change is built and tested in an isolated lineage: branch `feat/scorer-regional-transfer` (from origin/main, 41 platform tests pass). Rubric `biological-state-score-v1.1`: (TRANSFERS + 0.5 × PARTIAL) / usable rules × 10; UNKNOWN when the summary is absent or malformed, so a Brain that publishes none still scores as v1.
* Effect on Biological (0 TRANSFERS, 28 PARTIAL, 20 UNTESTED of 48): dimension 2.9, score 4.6 → **4.7**. Risk: the 0.5 weight for PARTIAL is a judgement call; at 0 it would be 0.0 and the dimension would score *below* "UNKNOWN is free". Not deployed; not merged; no score written.
* Also needs the next private bundle (D4) because the live registry predates `transferSummary`.

## D2. Proposed species knowledge rows (Michael)
Existing evidence only (no new literature). Tier RESEARCH. Effect is on `knowledgeDepth` (median over assessed species).
Current → proposed overall (rounded half-up; exact in brackets):

| Species | Current | Proposed |
|---|---:|---|
| american_shad | 0.0 | 2.0 (2.15) |
| black_buffalo | 1.0 | 1.0 (1.05) |
| black_carp | 1.0 | 2.0 (1.95) |
| blue_sucker | 0.0 | 2.0 (1.85) |
| bowfin | 1.5 | 2.0 (1.85) |
| carpsuckers_group | 0.0 | 2.0 (1.85) |
| channel_catfish | 0.0 | 2.0 (2.1) |
| freshwater_drum | 0.5 | 3.0 (2.8) |
| gizzard_shad | 0.0 | 2.5 (2.3) |
| golden_redhorse | 0.0 | 2.0 (2.0) |
| goldfish | 0.0 | 2.5 (2.4) |
| grass_carp | 5.5 | 5.5 (5.25) |
| northern_snakehead | 2.0 | 2.5 (2.6) |
| paddlefish | 1.5 | 3.0 (2.75) |
| river_redhorse | 0.0 | 2.0 (1.95) |
| shorthead_redhorse | 0.0 | 2.5 (2.65) |
| silver_redhorse | 0.0 | 2.5 (2.5) |
| striped_mullet | 0.0 | 2.0 (1.85) |

* Current effect: median 1.0. Proposed: median 2.5 (+1.5 on a 20-weight dimension, about +0.3 score). Evidence: unchanged packets, no species gains a VALIDATED/REVIEWED claim. Risk: low scores on thin evidence could be read as authority; they stay RESEARCH, and no species becomes customer-visible.
* Not applied. Swift `SpeciesDatabase` patches remain unapplied.

## D3. Reviewer package (external or owner; not the author)
* One package: rules for common carp first, then spotted gar, silver carp, longnose gar (30 rules) plus a blank answer sheet. Decisions: ACCEPT / REJECT / NEEDS_MORE_EVIDENCE (legacy `CHANGES` still read). Private files under the research store `adoption/review/` (`REVIEW_PACKAGE_2026-10-14.md`, `REVIEW_ANSWER_SHEET_2026-10-14.json`).
* Score effect: **none or slightly negative until rubric D5**; review is justified by trust, not points.

## D4. Next private bundle (Michael)
Carries `transferSummary`, `responseBands` unchanged, and D2 rows if approved. Staged only by the private driver; publication needs approval.

## D5. Rubric mismatch: `evidenceQuality` penalises partial review (platform owner)
With the 4 focus species REVIEWED the dimension falls 2.0 → 1.0 (REVIEWED share × 7 over 27 assessed species is below the flat 2 for "RESEARCH present"). Proposed: floor at 2 while any species is REVIEWED. See BIOLOGICAL_RUBRIC_MISMATCH_PROPOSAL.md.

## D6. `biologicalStateImpl` LIVE (Michael + upstream)
IN_PROGRESS = 4, LIVE = 8 (+0.6). Needs per-lake publication, which is OFF and depends on upstream truth and Intelligence reconciliation. Not planned.

## Score scenarios (scorer v1.1 where it applies; GET-only on live facts; nothing written)

| Scenario | Score | knowledgeDepth | evidenceQuality | regionalTransfer |
|---|---:|---:|---:|---:|
| A published (v1, no transfer) | 4.6 | 1.0 | 2.0 | None |
| B + regionalTransfer v1.1 (needs scorer ratification) | 4.7 | 1.0 | 2.0 | 2.9 |
| C B + proposed species rows adopted | 5.0 | 2.5 | 2.0 | 2.9 |
| D B + 4 focus species REVIEWED (needs reviewers) | 4.6 | 1.0 | 1.0 | 2.9 |
| E B + C + D | 4.9 | 2.5 | 1.0 | 2.9 |

**Ceiling without field data is about 5.0.** Reaching 8.0 needs VALIDATED species (field trips, first confirmatory comparison realistically spring 2027), Southeast evidence streams, and LIVE state. No desk work remains that moves the score honestly.

## Queue additions (2026-10-14, bowfisher knowledge adoption)
* **D7. Practical species-v2 source standard** (Michael): one inspected credible source up to 6, two independent up to 8; amend the private SPECIES_SCORING_STANDARD anchors. Applied in tooling only until ratified.
* **D8. Next private bundle 2026-10-14.6** (Michael): species knowledge, 77 usable rules (41 RECONCILED from the sweep, 29 of them on registered species), target set and readiness facts, movement summaries. Publishing it moves the canonical score from 4.6 to about 5.2-5.3 on the current rubric.
* **D9. Scorer v1.1 / v2** (platform owner): v1.1 consumes transferSummary; v2 is the target-scoped rubric (reads 4.3 today).
* **D10. Target set v1** (Michael): 8 targets, 5 secondary, rest knowledge-only.
* **D11. Registry splits**: quillback, river carpsucker, blue tilapia (see BIOLOGICAL_REGISTRY_SPLIT_PROPOSAL.md).
* **D12. Reviewer queue**: plain-English package of 77 usable rules (private) plus 15 REVIEW_REQUIRED candidates; includes three flagged rules: the month-agnostic common-carp rising-stage rule (the sweep says spring and early summer), retire the DRAFT alligator-gar night rule (telemetry shows no day/night difference), retire the DRAFT bigmouth spawn range (better-sourced range exists).
* **D13. Upstream**: presence for bowfin and the other non-policy-12 target fish (Lake Brain) so they can be evaluated on a lake.
