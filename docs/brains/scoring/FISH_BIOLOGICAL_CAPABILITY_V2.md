# Fish Biological Capability V2 (`FISH_BIOLOGICAL_CAPABILITY_V2`)

**Status: APPROVED and FROZEN — rubric `2.1.0` + cohorts `fish-capability-cohorts-v2` (owner, 2026-10-19). Approved baseline: TARGET 6.81 (6.805781), overall Fish 3.77 (3.770401) on release 2026-10-17.1. Displayed as "scenario capability (not field-validated)". The approval covers the rubric and cohorts only: no merge, deployment, Publisher cutover, customer activation or score publication is authorised (§12).**
Rubric: [`fish-biological-capability-v2.json`](fish-biological-capability-v2.json) · Cohorts: [`fish-capability-cohorts-v2.json`](fish-capability-cohorts-v2.json) (v1 kept for history) ·
Evaluator: `brains/fish/runtime/capability_eval.py` · Scorer: `jobs/brain_platform/sector_brain_platform/fish_capability.py` · Local entry point: `brains/fish/runtime/capability_run.py`.

## 1. What it measures, and what it does not

**Question:** *how good is Fish Brain at understanding fish, species by species, as shown by what its runtime actually does?*

It awards points only for **executed runtime behaviour**: an evidence-checked rule that fires under its own conditions, stops under contrasting conditions, moves the species output its way, explains itself, stays UNKNOWN when it should, and covers more or less of the year. Profile text, knowledge scores, paper counts, registry bookkeeping, connectivity and deployment earn nothing.

| Measurement | What it answers | Form | Changed here? |
|---|---|---|---|
| Maturity `biological-state-score-v1` (5.1) | knowledge-evidence completeness + pipeline maturity | number, published | **No.** Reproduced exactly (5.1 / 5.1) |
| Species knowledge `species-v2` | evidence completeness per species (hand-scored domains) | number per species | **No** |
| **Biological capability V2** | demonstrated executable biology per species + two roster aggregates | number per species and per roster | **New (candidate)** |
| Scientific confidence | evidence quality, review, transfer, contradictions, field validation | **statuses only** | new report, never points |
| Production readiness | lifecycle, Publisher cutover, customer path, per-lake state, publication, field validation | **gates only** | new report, never points |

A pass is `SCENARIO_BEHAVIOR_PASSED`, never `FIELD_VALIDATED_ACCURACY`: scenarios are synthetic. Capability says the behaviour exists and is handled safely; it does not say the biology is right on a real lake.

## 2. Architecture (who does what)

```
private knowledge release (hash-verified)          frozen cohorts + rubric (this folder)
            │                                                   │
            ▼                                                   │
Fish runtime: bio_state → movement_outlook → biological_assessment
            ▲                                                   │
Fish Layer 3 evaluator (capability_eval.py): executes scenarios │
            │  evidence: per species × criterion fraction, details, blocker (NO points)
            ▼                                                   ▼
shared platform scorer (fish_capability.py): validate → points → species scores → roster aggregates → backlog → change record
            │
            ▼
result.json (candidate, local) ── future: authoritative publication through the existing Publisher path after approval
```

* **Fish owns biology** (Layer 1 knowledge, Layer 2 evaluation, Layer 3 learning/validation). The evaluator is Layer 3.
* **The shared scorer owns points.** Evidence carrying any score field is rejected (`validate_evidence`).
* **Intelligence owns bowfishing decisions.** The assessment contract `fish-biological-assessment-v1` rejects locations, areas, rankings, opportunity scores and recommendations anywhere in its payload.

## 3. Rubric (owner category weights, unchanged)

| Category | Max | Criteria (weight) |
|---|---:|---|
| Species biology & behavior | 2.5 | BIO-1 executable behaviour (0.75) · BIO-2 breadth over 5 core behaviour families (0.5) · BIO-3 species-specific signature (0.5) · BIO-4 appropriate uncertainty (0.5, abstention × breadth) · BIO-5 behaviour named (0.25) |
| Habitat & depth | 2.0 | HAB-1 habitat preference executes + annual coverage (0.7) · HAB-2 habitat changes with season/conditions (0.3) · HAB-3 `KNOWS_DEPTH_PREFERENCE` (0.5) · HAB-4 `CAN_EVALUATE_SUPPLIED_DEPTH` (0.3) · HAB-5 depth abstention (0.2, abstention × breadth) |
| Environmental responses | 2.0 | ENV-1 temperature (0.6) · ENV-2 water level / hydrology (0.6) · ENV-3 clarity (0.2) · ENV-4 missing, degraded and conflicting inputs (0.6, × environmental breadth) |
| Spawning & seasonality | 2.0 | SPN-1 spawn window executes + spawn-period behaviour (0.6) · SPN-2 temperature trigger discriminates (0.4) · SPN-3 seasonal breadth of known behaviour (0.6) · SPN-4 spawn uncertainty + regional applicability (0.4) |
| Day / night | 1.0 | DN-1 day/night behaviour executes + annual coverage (0.5) · DN-2 behaviour vs catchability evidence (0.25) · DN-3 safe abstention (0.25, abstention × breadth) |
| Knowledge application | 0.5 | APP-1 full runtime on the species' best-supported scenario (0.5; halved if only a spawn state is known) |

Exact award rules per criterion are in the rubric JSON (`award`); `revisionHistory` records 2.0 → 2.1. `points = weight × fraction`; species score = sum (exact to 6 dp, displayed to 1 dp).

**Depth distinctions (owner §9).** `KNOWS_DEPTH_PREFERENCE` = a depth-class habitat rule executes (HAB-3 = 1; a shallow/deep tendency alone = 0.5). `CAN_EVALUATE_SUPPLIED_DEPTH` = given a supplied depth, the runtime says WITHIN / OUTSIDE the preferred class (HAB-4; new in `biological_assessment.depth_tendencies`). `HAS_NO_DEPTH_RULE` = 0 and is reported. No credit depends on an unpublished lake depth dataset.

**Day/night (owner §12).** Night is never assumed. `dayNightAssessment.evidenceKind` classifies the counting evidence of the night rule by study design: BEHAVIORAL (telemetry/tracking), CATCHABILITY (electrofishing/catch/capture/encounter), MIXED, UNCLASSIFIED. Evidence-kind credit (DN-2) needs a non-conflicting claim (DN-1 execution = 1).

## 4. Policies

* **Only usable rules execute.** RECONCILED/APPROVED rules that pass the evidence discipline in `rules.py`; DRAFT and season-gated rules earn nothing and are reported as unused knowledge.
* **Abstention** (BIO-4, HAB-5, DN-3, max 0.95 of 10) is credited only to a species that passes BIO-1, **scaled by executable breadth** (core behaviour families executed / 5). ENV-4 input safety is scaled by executable environmental families / 2. Universal UNKNOWN earns nothing; a one-family species earns at most 0.19.
* **Spawning and seasonality (2.1).** A spawn window alone is not seasonal understanding: SPN-1 gives half for the window and half for knowing what the fish does inside it; SPN-3 counts the seasons (of 4) with known behaviour, excluding the spawn state, at half credit if that behaviour never changes. APP-1 is halved when the only biological output is a spawn state.
* **Annual coverage** (HAB-1, ENV-1..3, DN-1 = half execution, half coverage). Measured by running the runtime for 12 months × every registered condition state; a month without an evidence-backed output is genuinely UNKNOWN for that fish.
* **Normalisation.** A criterion may be NOT_APPLICABLE only via a reviewed `biologicalExemptions` entry (speciesId → criteria + reason); exempt weight leaves the denominator. The list is **empty**: no criterion was found to be biologically inapplicable to a whole species (every fish lives through temperatures, water levels, habitats, a spawning season and day/night). Clarity was not made a core family for this reason and carries only 0.2.
* **Reference cases.** Human-reviewed expectations (`reviewStatus` APPROVED + reviewer) can only **withdraw** credit: a failing approved case zeroes the criterion it checks. PROPOSED cases are executed and reported, never scored. None are approved yet (15 PROPOSED cases for the TARGET species live in the private workspace; 13 of 15 would pass today).
* **Evaluation status.** `ASSESSED` (scored; missing capability = 0) · `NOT_ASSESSED` (policy; explicitly unscored, never 0) · `INSUFFICIENT_EVIDENCE` · `EVALUATION_FAILED` (unscored; the aggregate is INCOMPLETE).
* **Presence.** Biology is evaluated independently of lake presence (every rostered species is treated as relevant for the evaluation). Lake Brain presence policy and the DISC-001..003 decisions are unchanged.
* **Scenario frame.** Region `south`, waterbody `run_of_river` (Sector's product frame); `west` tests regional applicability. A synthetic mid-month temperature climatology drives the standard 48-scenario grid; it is a scenario device, not data.

## 5. Aggregation (`fish-capability-aggregation-v1`)

* Unweighted arithmetic mean of exact species scores over the **complete frozen roster** (no weighting by research volume, ease of study or preference).
* Rosters (`fish-capability-cohorts-v2`, 2026-10-19): **TARGET** 8 species; **ALL_ASSESSED** 26 individually assessable species. **Rule:** only a single biological species is rostered. Rows whose taxonomyStatus is GROUP_* or TAXON_UNRESOLVED are explicitly unscored and listed: `carpsuckers_group` (GROUP_UNRESOLVED, ASSESSED in the registry) is `notIndividuallyAssessable` (INSUFFICIENT_EVIDENCE, backlog RESOLVE_TAXONOMY); `suckers_redhorse_carpsuckers_group` and `tilapia_unresolved` stay NOT_ASSESSED by policy. FIELD_ID_UNRESOLVED (buffalo) and RESOLVED_HYBRIDIZES species are single species and stay in. v1 (27) is kept; the denominator change raises the aggregate (3.63 on v1 vs 3.77 on v2 under rubric 2.1) and is declared in the cohorts file. Membership changes only with a new cohorts version.
* **Overall Fish biological capability = ALL_ASSESSED** (the complete roster, so one strong species cannot hide weak ones); TARGET is shown beside it.
* INCOMPLETE when any rostered species is not ASSESSED or knowledge versions differ: value `null`, bounds shown (unscored at 0 and at 10), all available species kept.
* Reported with every aggregate: eligible / evaluated / completeness, below 5.0, below 7.0, % at 5.0+ and 7.0+, lowest and highest species, lowest score, bottom-quartile mean, median, category averages, rubric / cohorts / aggregation versions.
* **Change record** (`compare`): exact per-species, per-category, per-criterion and aggregate deltas; NOT_COMPARABLE across rubric or cohort versions; history is never edited. Scores can go down.

## 6. Blockers and the research backlog (labels, never points)

Every missed point carries a blocker: `MISSING_KNOWLEDGE`, `THIN_KNOWLEDGE` (species-v2 domain 1-4), `KNOWLEDGE_NOT_IN_RUNTIME` (draft rules, movement-card rule candidates, or domain ≥ 5 with no executable rule), `REVIEW_BLOCKED` (usable rule waiting for a reviewer's season bound / YEAR_ROUND), `CONTRADICTORY_EVIDENCE`, `NEEDS_FIELD_OBSERVATIONS`, `RUNTIME_DEFECT`, `POLICY_BLOCKED`, `DEPENDS_ON_EXECUTABLE_KNOWLEDGE` (abstention). Species-v2 domain scores are used **only** to label blockers.

Backlog order: TARGET roster first → not policy-held → points connectable from existing knowledge (unused research, review-blocked rules, runtime defects) → total gap. Actions: `CONNECT_EXISTING_RESEARCH`, `REVIEW_SEASON_ASSERTIONS`, `RESEARCH`, `RESOLVE_CONTRADICTION`, `POLICY_HOLD` (protected / not a target: visible, nothing commissioned), `MAINTAIN`. SECONDARY and KNOWLEDGE_ONLY species stay listed.

## 7. Contracts

* Evidence `fish-biological-capability-evidence-v2` (private: contains rule ids). Result `fish-biological-capability-result-v2` (`contracts/schemas/fish-capability-result-v2.schema.json`; what Ops would read). Intelligence-facing `fish-biological-assessment-v1` (`brains/fish/contracts/fish-biological-assessment-v1.json`).
* Identity: `evaluationId` = hash of everything material (rubric, cohorts, knowledge release + overlay, evaluator version, code version, frame, results); `evaluatedAt` excluded.

## 8. Running it (developer, Sector Pulse, Mac mini)

```
python3 brains/fish/runtime/capability_run.py --bundle <private release root> --out out/ [--expect-manifest-sha <sha>] [--previous prev/result.json] [--overlay candidate.json] [--reference-cases cases.json] [--maturity score.json]
```
Deterministic, stdlib only, offline: no network, RTDB, credentials, Ollama or LLM. Writes `evidence.json`, `result.json`, `report.md`. Exit 0 complete, 3 incomplete, 2 invalid. `--overlay` evaluates a `HYPOTHETICAL_CANDIDATE` knowledge change (added rules, reviewer season assertions, retirements) without adopting it. Pulse may run it; Pulse never owns the rules or the rubric.

## 9. Development record (honesty notes)

* Not blind pre-registered. Category weights are the owner's (unchanged). Criteria were written after reading the runtime, the rule inventory and the audit.
* Two refinements were made **after the first full run on real data**, both to remove over-credit, with the before/after recorded:
  1. First run: TARGET **7.96**, ALL_ASSESSED **4.48**. One rule earned a whole condition family (bigmouth buffalo, 3 rules, scored 7.9 against common carp's 8.95). Added *annual coverage* to HAB-1, ENV-1..3, DN-1 → TARGET **7.59**, ALL_ASSESSED **4.33**.
  2. BIO-2 ("behaviour changes with conditions") saturated at 3 distinct outputs for every species with rules. Replaced by breadth over the 5 core behaviour families → TARGET **7.42**, ALL_ASSESSED **4.22**.
  Neither change touched category weights; both lowered scores.
* **Rubric 2.1 (owner final review, same day).** The owner found that one spawn rule earned about 4.8 (redhorse). Diagnosis: one phenology rule earned all 2.0 spawning points, plus 0.95 abstention and 0.5 application, with no behaviour beyond the window. All 14 species at full spawning credit got it from one phenology rule. Corrections: abstention × breadth, ENV-4 × environmental breadth, SPN-1 spawn-period behaviour, SPN-3 seasonal breadth, APP-1 spawn-only halved. Result on the live release: TARGET **7.42 → 6.81**; ALL_ASSESSED **4.22 → 3.63** on the same 27, **3.77** on cohorts v2 (26). Redhorse species 4.80 → 2.89. Seven species keep full spawning credit (behaviour inside the window and across all four seasons). No criterion was raised.
* Abstention credit can give a species with one executable rule a floor of about 0.95 + its executed criteria; universal UNKNOWN species score 0.

## 10. Legacy maturity-rubric defects (audit §13, owner §28): investigated, not changed here

`biological-state-score-v1` and its history are untouched. Exact causes in `jobs/brain_platform/sector_brain_platform/scoring.py` (`score_biological`):

| Defect | Cause | Where a fix lives | V2 capability avoids it by |
|---|---|---|---|
| A. median over 27 hides target improvements | `statistics.median` over all assessed `overallRounded` | existing proposal `biological-state-score-v2` (branch `feat/biological-score-v2`, target-scoped; not wired) | per-species scores + mean over frozen rosters; exact deltas |
| B. first VALIDATED species lowers the score | `evidenceQuality = VALIDATED share × 10` replaces the flat 2.0 RESEARCH floor (1/27 → 0.37) | candidate fix prepared separately (monotone ladder), inactive | does not score validation at all (scientific confidence status) |
| C. regionalTransfer hard-coded UNKNOWN | `dim("regionalTransfer", 5, None, …)` | existing proposal `biological-state-score-v1.1` (branch `feat/scorer-regional-transfer`) | SPN-4 tests regional applicability by execution; transfer reported as a status |
| D. null contradiction counts treated as 0 | `int(s.get("contradictionCount") or 0)` | candidate fix prepared separately (null → excluded; all null → UNKNOWN), inactive | contradictions are reported (`UNKNOWN` when not recorded), never scored |
| E. connectivity scored without customer consumption | `productionIntegration` = 10 when the Intelligence dependency is CONNECTED (`consumedByCustomerPath:false`) | existing v2 proposal (`customerUsefulness`) / readiness | readiness is gates only; connectivity earns no capability |

## 11. Owner decisions

**Decided 2026-10-19:** rubric 2.1.0 and cohorts v2 APPROVED (items 1 and 2 below). Open: items 3 and 4.


1. Approve (or change) the criteria, the coverage policy and the abstention policy.
2. Approve cohorts `fish-capability-cohorts-v2` (single-species rule; overall = all individually assessed species, TARGET separate).
3. Review the 15 PROPOSED reference cases (approve / reject). Classified 2026-10-19: 9 SELF_CONSISTENCY (prove only that Fish runs its own rules), 4 ABSTENTION_CHECK, 2 INDEPENDENT_EXPECTATION_NOT_IN_RUNTIME (grass carp and bowfin night). None is backed by APPROVED evidence (0 approved rules, empty review ledger); none was self-approved.
4. Authorise a publication path (e.g. `/scores/biological-state/capability`) through the existing Publisher and scorer; until then nothing is written.

## 12. Frozen baseline and activation gates (owner decision, 2026-10-19)

**Frozen.**
- Weights, criteria, award rules, policies (abstention, coverage, normalisation, reference cases, aggregation) and roster membership are recorded as fingerprints in `fish-biological-capability-v2.json` → `frozen`.
- `sector_brain_platform.fish_capability` refuses any rubric or `fish-capability-cohorts-v2` content that no longer matches them.
- A change needs a new rubric or cohorts version and owner approval, and is never made to raise scores. Results across versions are NOT_COMPARABLE.

**Approved baseline** (`approvedBaseline`):

| Item | Value |
|---|---|
| Evaluation | `fcap-1d7b83b76fd4bfd02627`, code `06557f16`, evaluator 2.1.0 |
| Knowledge release | 2026-10-17.1, manifest `f179ec21…` |
| TARGET | **6.805781** (8 species) |
| Overall Fish (ALL_ASSESSED) | **3.770401** (26 species) |

- Per-species scores, category breakdowns, missing capabilities and the research backlog are in the private baseline `result.json` (sha256 recorded). It is private because the evidence carries rule identifiers.
- Every result shows the baseline.
- Measure improvements with `capability_run.py --previous <approved baseline result.json>`. The change record is marked `againstApprovedBaseline` and gives exact deltas, which can be negative.

**Unchanged and separate:**
- maturity `biological-state-score-v1` 5.1;
- species-v2 knowledge scores;
- scientific confidence (statuses);
- production readiness (gates).

**Not authorised by this approval:**
- PR merges;
- production deployment;
- Publisher cutover;
- customer-facing activation;
- production score publication.

**Activation gates (all required, in order):**
1. **Reference-case review.** A named reviewer marks the 6 non-self-consistency cases APPROVED or REJECTED: CC-REF-02, CC-REF-03, LG-REF-01, BB-REF-01, GC-REF-02 and BF-REF-02. The 9 self-consistency cases may be approved as regression tests.
2. **Merge authorisation for Engine PR #35.** Its own review, separate from this rubric approval.
3. **A publication PR, reviewed separately.** A scorer-job path that writes `capability` inside `/scores/biological-state` through the existing Publisher and gates, nonproduction-tested and approved like any score path. No writer exists today.
4. **Production publication approval.** Explicit owner approval to write the score in production. The Fish Publisher cutover (`SHADOW` today) follows its own cutover order and approval.
5. **Ops.** Merge and deploy Sector_Ops PR #7 only after Engine publishes.
6. **Customer-facing activation.** Separate product decision. Fish has no customer path today, and per-lake Biological State LIVE is decision FISH-PRD-001.
