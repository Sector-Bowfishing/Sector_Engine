# Scoring contract audit V1 (read-only; 2026-10-23)

Question: do the scoring contracts measure real bowfishing capability, coverage, prediction quality and validation, or research
volume and engineering completion; and are engineering and scientific scores separated? No rubric, score or approval file was changed.

Classes: CAP = BOWFISHING_CAPABILITY, COV = COVERAGE, PRED = PREDICTION_QUALITY, VAL = VALIDATION, ENG = ENGINEERING_COMPLETION, VOL = RESEARCH_VOLUME.
"Data/pkg" = can the dimension move by downloading data or packaging a release alone (no new accuracy evidence)?

## 1. Contracts, dimensions, classification

All paths under `docs/brains/scoring/` unless stated. Weights are of 100.

| Contract | Dimension (weight) | Class | Data/pkg |
|---|---|---|---|
| `lake-brain-score-v1.json` | sourceAuthority (15) | COV (data quality of level source) | binding review only |
| | operatorPlan (10) | COV | YES: a guide curve/zone file fills it |
| | historyQuality (15), seasonalBaseline (10) | COV | YES: history backfill is pure download |
| | trendQuality (10), floodDroughtContext (5) | ENG (observed-vs-proxy, fetch success of one feed) | YES: a retry fix flips it; no freshness test |
| | validation (15) | VAL (status enum 0/5/10) | status decision, not a measure |
| | coverage (20) | COV (ladder, 5/621 = 0.8%) | needs published bindings |
| `sector-intelligence-score-v1.json` | specialistConnectivity (20), dependencyHandling (10), runtime (5) | ENG | YES (wiring, bookkeeping, a cron entry) |
| | normalizedEvaluations (20), lakeCoverage (10) | COV (same fact counted twice, 30) | evaluations run |
| | provenance (10) | ENG (field presence) | YES |
| | validation (15) | VAL (enum) | no |
| | synthesisQuality (10) | PRED, always UNKNOWN | cannot move |
| `biological-state-score-v1.json` | registryCompleteness (10) | ENG (everything assessed OR labelled NOT_ASSESSED) | YES: a label scores full |
| | assessedCoverage (15), knowledgeDepth (20) | VOL (species count, species-v2 knowledge score) | YES: more literature/rules |
| | evidenceQuality (10) | VOL (REVIEWED/VALIDATED label) | review label |
| | contradictionsGaps (10) | VOL | YES (min(count,5)) |
| | regionalTransfer (5) | COV, UNKNOWN forever | cannot move |
| | biologicalStateImpl (15), biologicalStateValidation (10) | ENG / VAL (registry status enums) | declared, not measured |
| | productionIntegration (5) | ENG | YES |
| `fish-biological-capability-v2.json` (2.1.0, frozen) | all 6 categories (10 pts) | CAP, but SCENARIO capability only (synthetic grid, self-declared "not field-validated"); no PRED | YES: a candidate bundle with more usable rules raises BIO/HAB/ENV/SPN/DN/APP and annual coverage |
| `wind-specialist-capability-v2.json` | WI1-4 (25), SI1-2 (10), EA1 (10), GI1-2 (10), TI3 (6) | PRED (WI, SI, EA1, TI3); GI1-2 ENG (fetch QA, canonical cases) | no (needs observations) |
| | GI3, SI3, EA2, EA3, TI1-2, UM1-2 (39 pts) | CAP on SYNTHETIC wind (MODEL_CAPABILITY) | YES: code/scenario work |
| `frozen-scores.json` wind (cert v1, 3.3) | Wind speed 12, Direction 8, Gust 5, Lead 5 | PRED | live days only |
| | Exposure(field) 20, Surface(field) 20 | VAL (0 now) | no (needs bank-pair truth) |
| | Fetch 10, Freshness 8, Coverage 4, Provenance 8 | ENG / COV | Freshness grows with calendar days |
| `frozen-scores.json` water-temp 3.0, clarity 8.0 | single typed number + blockers | water-temp: VAL gate (protected truth n per lake); clarity: research PRED, NOT_DEPLOYED | no rubric in repo (private) |
| `engine-score-v1.json` | specialistBrainMaturity (25), scientificValidation (15), lakeCoverage (10) | mean of scientific scores, VAL, COV | inherit |
| | integrationCompleteness (20), runtimeReliability (10), productionConsistency (10), platformHealth (10) | ENG | YES (5/6 to 6/6 conformance moved 7.0 to 7.2) |
| `beta-readiness-v1.json` | blockers/warnings on readiness, staleness, validation | ENG gates + VAL; no accuracy fact | n/a, separate and never averaged (good) |
| Depth/Vegetation (`maturity.py`, `maturity_inputs.json`) | 8 dims, 6 are typed judgment scores; coverage computed | RESEARCH only, `official: false`; cert specs state "no official score" | judgment dims need cited change evidence |

## 2. Defects

D1. Water temperature 3.0 and clarity 8.0 are typed constants (`frozen-scores.json:4-25`, `scoring.py:217 frozen_score`). A lower temperature RMSE, a
new independent sensor comparison (`tools/research/discovery.py:551-577`) or more validated lakes cannot change the number unless the
Level-4 sufficiency gate (n >= 25 casts on 4 lakes) passes. Clarity 8.0 is a NOT_DEPLOYED research candidate yet counts at full weight in the
Engine mean (`frozen-scores.json:19-22`).

D2. Lake dimension values for the campaign are typed, not computed: `/Sector Research/lake-brain/.../build_candidate.py:26`
(`dims = {"coverage": (20, 1.0), ...}`), surfaced as `run_adapter.py:229` ("dimension values typed in the builder, not computed"). Water-temp
candidate score is the constant `3.0` whenever `score_baseline.py --check` passes (`run_adapter.py:252`), whatever the candidate contains.

D3. Cap masks all improvement: Lake coverage gate cap 3.0 while profiled < 10% (`lake-brain-score-v1.json:68-73`; `scoring.py:104-107`). The
candidate builder records uncapped 6.3 would display as 3.0 ("Research cannot legitimately move any dimension", `build_candidate.py:82`).
Sector Intelligence is capped 1.0/2.0/5.0 by gates (`sector-intelligence-score-v1.json:67-82`), Biological at 4.0/6.0
(`biological-state-score-v1.json:80-91`), Wind V1 at 6.0/7.0 (non-binding now). Real improvements below the cap are invisible.

D4. Lake quality dimensions are shares over PROFILED lakes (`scoring.py:75-89`), coverage is a ladder. Profiling more lakes on weaker
sources lowers `sourceAuthority`/`historyQuality` while raising `coverage`; no dimension rewards fresh independent level data
("more lakes with a fresh independent level source" cannot move anything; `tools/research/discovery.py:624` computes
`lakesWithFreshLevel` but "no rubric dimension recomputed" at `:625`). `floodDroughtContext` and `trendQuality` swing with one feed
failing (Hartwell CWMS) on 5 profiled lakes: reliability noise inside a scientific score.

D5. Fish capability (`FISH_BIOLOGICAL_CAPABILITY_V2.md:11,63`): a rule earns credit if "usable" (a binary evidence discipline); evidence strength
is not graded, so a literature-weak rule and a field-validated rule score the same. Annual coverage = months with any output
(`fish-biological-capability-v2.json` ENV-1, HAB-1, DN-1, SPN-3). BIO-3 rewards a UNIQUE output signature, not a correct one. Abstention
criteria (BIO-4, HAB-5, DN-3, ENV-4) pay for correct UNKNOWN. Net: a release that adds rules raises the score with zero field outcomes;
the approved note admits "synthetic scenarios prove behaviour, not accuracy". No higher species-rule evidence strength, no field hit rate.

D6. Biological-state score rewards knowledge volume and bookkeeping: assessedCoverage 15, knowledgeDepth 20 (species-v2 median), registry
bookkeeping 10 (`scoring.py:115-160`; a NOT_ASSESSED label earns 10), productionIntegration 5. `regionalTransfer` (5) is permanently UNKNOWN
(`scoring.py:158`), so max reachable is 9.5; Intelligence `synthesisQuality` (10) is permanently UNKNOWN (`scoring.py:204`), max 9.0.
Prediction quality (does it pick the right fish/lake) is not a dimension of any computed Brain rubric.

D7. Intelligence double-counts coverage (normalizedEvaluations 20 + lakeCoverage 10, `scoring.py:198,202`) and 35 of 100 points are wiring/bookkeeping.
Its only quality-of-recommendation items are `validation` (enum) and the UNKNOWN synthesisQuality.

D8. Wind V2: 39 of 100 points are MODEL_CAPABILITY on synthetic wind (`wind-specialist-capability-v2.json:101-247`); status note says NOT
blind pre-registered (line 6). Wind V1 (3.3) `Lead time` scores 10/10 while speed/gust POD score 0 (`frozen-scores.json:58-64,37-57`).

D9. Documentation drift: `SCORING.md` frozen table still lists Wind 3.1 FROZEN while `frozen-scores.json:26-31` is 3.3 COMPUTED; every Brain's
`brain.json` types its number `ENGINE_READINESS_SCORE` (fish, lake, intelligence, clarity, temp, wind) although SCORING.md says it is a maturity/evidence score.

D10. `Validation` dimensions in Lake, Intelligence, Engine are enums set by a status node, with no tie to measured hold-out performance
(`lake-brain-score-v1.json:50-58`).

## 3. Separation of engineering and scientific scores

| Layer | State |
|---|---|
| Data nodes | Separate nodes: `/scores/{brain}` (maturity), `/scores/engine`, `/control/beta`, `/control/engineeringStatusV1`. GOOD |
| Engineering status 1.2.0 (`engineering-status.json` engineScore) | Labelled `ENGINEERING_SCORE`, "not a scientific capability score"; seven status layers incl. `scientificValidation` rendered separately, no scientific number in the Ops projection. GOOD |
| Engine score itself (`engine-score-v1.json`) | MIXED: 50 of 100 weight comes from scientific inputs (specialist mean 25, scientificValidation 15, lakeCoverage 10), 50 from engineering. It is labelled engineering but moves with science, and moved 7.0 to 7.2 with engineering-only work. Its `keepSeparate` list (line 83) contains the very Brain scores it averages |
| Brain scores | MIXED: Lake, Intelligence, Biological include engineering dims (health, schedule, wiring, provenance fields, registry labels, `productionIntegration`) |
| Mixed-semantics inputs to the Engine mean | wind = cert of candidate pipeline (not production), clarity = undeployed research candidate, temp = frozen ladder; fish contributes biological-state-score-v1 (5.1), not Capability V2 |
| Campaign report (`tools/research/campaign.py`) | MIXED: `Candidate score` column (`:729`) lists heterogeneous values (wind V2 capability, fish TARGET capability, depth/veg research maturity with judgment dims, clarity 8.0, temp constant 3.0) with no rubric id, scale or class; closeout files it under "Blockers" (`:602`); `scoreImpact` is a hand-typed prose string per track (`discovery.py:574,625,674,712,756,771`), not computed deltas. `authoritativeUnchanged` (`:74,511`) protects files only |

## 4. Recommended corrections

| # | Action | Class |
|---|---|---|
| R1 | Campaign report: replace the single `Candidate score` with `{rubricId, scale, class (CAP/COV/PRED/VAL/ENG/VOL), measured|typed|recorded, baseline, candidate}`; mark typed constants (lake, water-temp) as `TYPED_NOT_COMPUTED` and never print them as a candidate result (`run_adapter.py:229,252`, `campaign.py:704-729`) | SAFE_NOW |
| R2 | Report measured metric deltas next to the score: temp pooled RMSE (`discovery.py:551`), lakes with fresh independent level (`:624`), species rules with evidence strength, validated-case count; state "score movable: yes/no and why (cap, gate, typed)" | SAFE_NOW |
| R3 | Report `scoreImpact` as structured data (dimension id, can-move, blocking gate) generated from the rubric JSON, not prose; add a `CAPPED_BY` field when an uncapped value exceeds the gate (Lake 6.3 vs 3.0) | SAFE_NOW |
| R4 | Closeout: move candidate score out of "Blockers" into its own line labelled non-authoritative, with the class | SAFE_NOW |
| R5 | Fix doc drift: SCORING.md Wind row (3.1 to 3.3 COMPUTED), explain `ENGINE_READINESS_SCORE` type; document in SCORING.md which dimensions are ENG vs scientific (this table) | SAFE_NOW |
| R6 | Document that Engine score is "engineering-labelled but 50% scientific-derived"; show both halves separately in Ops text | SAFE_NOW (docs); score split is R9 |
| R7 | Add a measured prediction-quality dimension (hold-out skill, e.g. temp RMSE vs protected truth, lake level prediction ledger scorer, outcome hit rate) to Lake, Temp, Intelligence, Fish; make evidence strength gradable in Fish | NEEDS_OWNER_APPROVAL (new rubric version; results NOT_COMPARABLE) |
| R8 | Remove or re-weight bookkeeping/volume dims (Biological registryCompleteness, Intelligence dependencyHandling and double coverage, Lake history/baseline as downloads) | NEEDS_OWNER_APPROVAL |
| R9 | Split Engine score into an Engineering score (ENG dims only) and a Scientific composite; exclude NOT_DEPLOYED/candidate scores (clarity 8.0) from the specialist mean | NEEDS_OWNER_APPROVAL |
| R10 | Revisit caps so sub-cap improvement is visible (display uncapped beside capped; or step caps), and make Lake quality shares fleet-weighted so wider profiling is not penalised | NEEDS_OWNER_APPROVAL |
| R11 | Replace permanently-UNKNOWN dims (regionalTransfer, synthesisQuality) with measurable ones or drop them from the 100 | NEEDS_OWNER_APPROVAL |
| R12 | Give Water Temperature and Clarity in-repo, computed rubrics (RMSE/bias vs protected truth, deployed vs candidate) instead of typed constants | NEEDS_OWNER_APPROVAL |

## Summary of findings (15 lines)

1. No computed Brain rubric contains a measured prediction-quality dimension; PRED exists only in Wind (V1/V2) and the frozen temp ladder.
2. Water Temp 3.0 and Clarity 8.0 are typed constants; RMSE improvement cannot move them (`frozen-scores.json:4-25`).
3. Clarity 8.0 (NOT_DEPLOYED research candidate) counts at full weight in the Engine specialist mean.
4. Lake campaign dimension values and the temp "candidate score" are typed (`build_candidate.py:26`, `run_adapter.py:229,252`).
5. Lake coverage cap 3.0 (5/621 profiled) hides any sub-cap gain; uncapped 6.3 shows 3.0.
6. Lake history/baseline/operatorPlan (35 pts) can move by download alone; no freshness or independence-of-source dimension.
7. Fish Capability V2 is scenario capability: more usable rules raise it with zero field outcomes; evidence strength is binary.
8. Biological-state score rewards species counts, knowledge depth, registry labels (volume and bookkeeping); regionalTransfer is permanently UNKNOWN.
9. Intelligence: 35 of 100 points are wiring/bookkeeping, coverage counted twice, synthesisQuality permanently UNKNOWN (max 9.0).
10. Wind V2: 39 of 100 points are synthetic-wind MODEL_CAPABILITY; not blind pre-registered.
11. Engine score is labelled ENGINEERING_SCORE but 50 of 100 weight derives from scientific scores; 7.0 to 7.2 came from engineering only.
12. Data nodes, beta readiness and the Ops projection are cleanly separated; the Ops projection carries no scientific number.
13. Campaign report mixes heterogeneous candidate scores in one column, with hand-typed `scoreImpact` prose and the score under "Blockers".
14. SAFE_NOW: R1-R6 (campaign-side reporting and docs). NEEDS_OWNER_APPROVAL: R7-R12 (rubric/score meaning).
15. Nothing was changed except this file.
