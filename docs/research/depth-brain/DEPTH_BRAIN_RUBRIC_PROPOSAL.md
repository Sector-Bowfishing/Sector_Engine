# Depth Brain Rubric Proposal (RESEARCH ONLY - not official)

Depth Brain does not exist, so there is no official rubric. This is a candidate for Michael to adopt, amend or reject. Philosophy matches Lake Brain: **production-ready needs overall >= 8.0 and every critical dimension >= 7.5**. Scores are evidence-weighted judgments, not computed by any production function.

## Dimensions

| # | Dimension | Weight | Critical | What it measures |
|---|---|---|---|---|
| 1 | Source authority | 15 | yes | share of served lakes whose depth evidence is an instrument survey / authoritative table, weighted by bowfishing importance |
| 2 | Coverage | 15 | yes | share of fleet (weighted by user demand) with a usable Depth output of a tier worth showing |
| 3 | Absolute depth accuracy | 10 | no | measured foot-level error where absolute depth is claimed |
| 4 | Relative morphology accuracy | 15 | yes | zones, flats, drop-offs, shore-to-depth distances validated against surveys |
| 5 | Effective-depth capability | 15 | yes | level-adjusted depth/shift with datum and uncertainty handled and validated |
| 6 | Validation | 15 | yes | independent truth, held-out testing, prospective and field checks |
| 7 | Confidence and provenance | 10 | no | tier, sigma, source, year, licence, unknown-handling carried in the data |
| 8 | Fleet scalability | 5 | no | repeatable pipeline per state/source, cost, upkeep |

## Scale (applies to each dimension; 0-10)

| Score | Meaning |
|---|---|
| 0 | nothing exists |
| 1 | idea only; assets inventoried |
| 2 | one lake or anecdotal; no validation |
| 3 | evidence exists for a minority of lakes or one method with weak/negative tests; limits unknown |
| 4 | evidence for ~15-30 % of fleet; methods tested on small n; main failure modes known |
| 5 | half the capability proven for a meaningful subset; validation against real truth on tens of lakes; gaps explicit |
| 6 | broad subset (~40-60 % of demand) proven; error bars calibrated; pipeline sketched and partly exercised |
| 7 | most demand covered at an honest tier; independent held-out validation passed; pipeline run end-to-end in shadow |
| 8 | production-ready for the stated tiers: >= 70 % of demand covered, gates passed, monitoring, unknown handled |
| 9 | prospective field validation passed across regions; drift monitoring; operator-reviewed datums |
| 10 | complete and routinely re-validated; essentially no remaining blocker |

Dimension-specific anchors:

* **Authority**: 4 = A/B on ~15 % of fleet; 7 = A/B or authoritative table on >= 60 % of demand-weighted lakes; 9 = all served lakes have instrument-survey evidence.
* **Coverage**: 4 = A/B 17 % plus shift 43 %; 8 = zone-capable or shift-capable for >= 80 % of demand-weighted lakes at tier B or better.
* **Absolute accuracy**: 5 = sigma known and validated on A lakes; 8 = p90 error <= 1.5 ft on validated A/B lakes across >= 5 regions.
* **Relative morphology**: 5 = zones validated on tier A with CIs; 8 = a scalable predictor for non-surveyed lakes beats a constant by validated margin, or surveys cover demand.
* **Effective depth**: 5 = shift defined with uncertainty for hundreds of lakes; 8 = shift validated against measured events, datum audited per operator, zone re-binning validated at two pool levels.
* **Validation**: 5 = real truth on tens of lakes, honest negative results; 8 = prospective pre-registered test plus bowfishing field check.
* **Provenance**: 5 = ledger and schema designed; 8 = every served value carries tier, sigma, source, year, licence.
* **Scalability**: 4 = per-source scripts exist, 23 states have no source; 8 = automated, monitored refresh and coverage in all demand states.

## Gates

* Overall (weighted) >= 8.0.
* Every critical dimension (1, 2, 4, 5, 6) >= 7.5.
* Any customer-visible foot-level depth needs tier A and dimension 3 >= 7.
* No Tier D or U lake may feed a scored factor.
