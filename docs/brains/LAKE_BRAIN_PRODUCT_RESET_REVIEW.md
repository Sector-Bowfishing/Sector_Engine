# Lake Brain — product-reset review (2026-10-13)

Applies Michael's "Universal Product Intelligence Reset": Sector is a bowfishing product, not a research lab. Provider truth first, validation in proportion to
the claim, UNKNOWN is acceptable, simplify. **Nothing here changes a rubric, a threshold, a lifecycle or a validation status.** Items marked PROPOSAL need Michael.

## 1. What Lake Brain tells a bowfisher
"Is this lake high, low or normal for this time of year, is it rising or falling, how fast, and is the data fresh?" — and, for flood-controlled lakes, where the
level sits against the operator's pools. That helps *when to go* and *which lake*; it does not need to reconstruct hydrology.

## 2. Claims by level of truth
| Lake output | Level | Verification that is proportionate | Status |
|---|---|---|---|
| Current pool elevation, operator guide / normal pool, flood-pool bottom as published, source id, freshness | 1 provider/observed | source, freshness, units, datum, sanity; cross-source agreement | Done for the 5 pilots; machine-verified for 196 candidates (123 pairs vs an independent source, median 0.015 ft) |
| Difference from guide / normal pool, operator zone (IN_ZONE, BELOW_ZONE), 72 h mean rate | 2 deterministic | formula, sign, edge cases | Done (rules v2 conformance fixtures, Swift = Python mirror) |
| Historical state (NORMAL / UNUSUAL / VERY_UNUSUAL against the lake's own history) | 3 Sector-derived | pre-registered hold-out | H-A PASS, H-B PASS, H-D PASS (narrow) |
| RAPID change flag | 3 Sector-derived | pre-registered hold-out | **H-C FAIL, preserved**; still published for the pilots |
| Species presence on the Lake profile | 3 | separate evidence rules | not part of the Lake level score |

Consequence: most of what the Lake Brain says is Level 1/2 and is already verified. The validation effort belongs on the two Level-3 claims, and one of them
(RAPID) failed its own test.

## 3. Rubric mismatches (PROPOSALS — rubric `lake-brain-score-v1` unchanged)
1. **validation is one word for the whole Brain** (0 / 5 / 10, NOT_VALIDATED caps the score at 5.0). The Level-1/2 claims are verified; only Level-3 claims are not.
   *Proposal:* report validation per claim family (provider display, deterministic derivation, historical state, rapid change) and let the rubric read the
   weakest *published* family. Combined with withholding RAPID until H-C passes prospectively, PARTIAL becomes reachable for what Sector actually claims.
   The current PARTIAL definition is also internally awkward (item 2 needs all of H-A..H-D to pass, item 3 says failed families are withheld).
2. **floodDroughtContext divides by all lakes.** The score is the share of states with a known flood-pool state, but many lakes have no flood pool to know
   (no flood-control purpose; TVA publishes no flood-pool bottom). On the 196 candidates the ceiling is 137/196 (70 %, dimension 7.0) however good the evidence is.
   *Proposal:* denominator = lakes where a flood pool exists (UNKNOWN is a valid answer elsewhere and must not be penalised). On the same evidence
   111/137 = 81 % (dimension 8.1 vs 5.7); effect on the uncapped score is about +0.1 (weight 5).
3. **coverage is gated on human acceptance of Level-1 provider bindings.** The unlock is a 60-row human sample (plus 57 flagged rows). For a provider-truth
   binding, machine verification with an independent corroborating source is already stronger than a human reading the same numbers. *Proposal (Michael's
   call, he set the review rule):* keep human review for flagged / low-confidence rows and datum questions, but let machine-corroborated rows count as reviewed on a
   smaller sample. Do not do this without his approval.

## 4. Simplifications (recommended)
- **Pause TWDB.** The adapter is built but gated off (`robots.txt` disallows the CSVs) and adds 0 new candidate lakes under current rules. Only value: history depth for 3 lakes. Do not spend more time or ask TWDB unless Michael wants those 3.
- **Drop the per-lake shoreline-slope work from Lake.** Depth owns depth; slope is context for Depth/Vegetation. Keep the note, run nothing.
- **Do not chase plan/flood evidence beyond what operators publish.** The remaining items are low value: ~25 FERC lakes at 1–2 h each, 2 NWPS, ~7 joinable USACE. UNKNOWN is valid.
- **Coordinate review:** 171 lakes is heavy. Review only the 58 that block a candidate binding first (46 PASS / 12 FLAG); the other lakes are not blocked by their pins.
- **Representative validation fleet:** keep the 18-lake design as a *plan*, do not build anything for it until the ledger has results.
- **Cost:** keep the fingerprint-driven, scale-to-zero design; the new baseline writer cuts baseline objects ~86 % and no customer path computes anything.

## 5. Score report
| | Value |
|---|---|
| Starting displayed / underlying | 3.0 / 6.3 |
| Ending displayed / underlying | 3.0 / 6.3 (nothing live changed; the Engine changes are built, not deployed) |
| Dimensions that moved | none |
| Dimensions that did not move | coverage 1.0, floodDroughtContext 2.0, validation 0.0, the other five 10.0 |
| Active caps | coverage 3.0 (5 of 621 profiled, needs 63), validation 5.0 (NOT_VALIDATED) |
| Next legitimate score mover | Michael's binding review → batch B reaches 63 profiled lakes → displayed 5.0 |

## 6. Dimension exhaustion matrix (dimensions below 7.5, plus the one that falls below 7.5 on the accepted fleet)
| Dimension | Score | Product value | Work this session | Result | More desk work? | Real blocker |
|---|---:|---|---|---|---|---|
| coverage | 1.0 | High: a lake outside the 5 pilots shows nothing | 196 machine-verified candidates generated and gated; 8 more lakes recovered from the 14-mismatch set (review required); coverage-recovery ranking; geometry 592/621; pre-seed tool, staged rollout, batch verifier; TWDB adapter (adds none); coordinate pack | No lake can count until reviewed; score unchanged by design | **No** for the score. Everything that does not need a human is built and tested | MICHAEL DECISION (60-row binding review + flagged 57); then IMPLEMENTATION (pre-seed and batches, ~3–4 h of API time) |
| floodDroughtContext | 2.0 | Medium: context for flood-controlled reservoirs | Evidence ranked per operator over the 196; rubric-ceiling analysis; TWDB flood levels found (4 lakes) | Ceiling 7.0 is set by the rubric's denominator, not by missing evidence | **Marginal** (≈25 FERC lakes by hand, 2 NWPS, ~7 USACE): low value, not recommended | MICHAEL DECISION (rubric denominator; whether a lower-pool level counts as a zone bottom, 84 → 120 plan lakes); LICENSING (TWDB) |
| validation | 0.0 | High: trust in the claims | Rules v2 pre-registered and tested once (H-C failure preserved); prospective ledger running and audited; scorer hardened with a no-hindsight rule; readiness doc with dates | NOT_VALIDATED; first scorer output 2026-11-01; ledger day 90 is 2027-01-11 | **No** (a revised H-C pre-registration is drafted as a proposal, not committed as binding until Michael picks the route) | VALIDATION (time: ≥ 90 days for PARTIAL evidence, 12 months for VALIDATED); MICHAEL DECISION (per-claim validation; withhold RAPID) |
| operatorPlan (10.0 today, projected ≤ 6.3 on the 196) | 10.0 | High where an operator publishes a guide curve | Evidence recomputed per operator: 84 of 196 strict (43 %) | Pilots look perfect because they are the best-documented lakes | **No**: known evidence is exhausted at 124/196 | EXTERNAL SOURCE (operators publish no plan for many lakes; UNKNOWN is valid); MICHAEL DECISION (lower-pool definition) |

Dimensions at 10.0 on the pilots (sourceAuthority, historyQuality, seasonalBaseline, trendQuality) hold or nearly hold on the 196: all are Level-1/2 and verified.

## 7. Blocker categories (exact labels)
- MICHAEL DECISION: binding review; critical dimensions and `requiredDimensions`; per-claim validation / withholding RAPID; rubric denominators; role mailbox for `SECTOR_CONTACT`; large-water policy; deploy approval.
- TIME / SEASON: ledger day 90 (2027-01-11), day 365 (2027-10-13), first monthly scorer 2026-11-01, lifecycle observation.
- LICENSING: TWDB `.csv` robots disallow; SJRWMD, NH DES; undocumented operator endpoints; ResOpsUS licence unchecked.
- EXTERNAL SOURCE: NHD intermittent 502/504; no NHD waterbody for Shafer and East Okoboji.
- IMPLEMENTATION: deploy of the built image and orchestrator (blocked by the auto-mode classifier pending Michael); pre-seed and batch rollout after the review.
- VALIDATION: H-C failed; revised H-C must be pre-registered before any ledger month is read.
- PREREQUISITE BRANCH: `feat/cost-efficient-scheduling` unmerged.
- OPS PRESENTATION: Ops does not read `/scores/{id}`; see `LAKE_BRAIN_OPS_VISIBILITY_GAP.md`.
- UPSTREAM BRAIN / FIELD: none for Lake today.

## 8. Local storage
Lake research directory 8.0 GB → 1.0 GB (about 6.6 GB reclaimed, public rebuildable bulk and research venvs; `CLEANUP_RECORD` in `MANIFEST.jsonl`). Largest retained dataset:
the geometry NHD/Overpass query cache (~214 MB), kept because the NHD service is flaky and a rebuild is slow. Below the 5 GB / 2 GB review thresholds. Rebuild manifests
preserved; validation truth (ledger, hold-out results, preregistrations, review packs) preserved.
