# Lake Brain: rubric mismatch proposals, quantified (DRAFT for Michael's decision; nothing adopted)

**Status.** Analysis only. The live rubric (`docs/brains/scoring/lake-brain-score-v1.json`), the scorer (`jobs/brain_platform/sector_brain_platform/scoring.py`), every profile, `/validation/lake-brain` (`NOT_VALIDATED`), every lifecycle and every threshold are unchanged. `/scores/lake-brain` still reads **3.0 / 10, uncapped 6.3** (read live 2026-10-13, `scoreUpdatedAt 2026-10-13T18:58:18Z`). Every figure under a PARTIAL or VALIDATED heading is **hypothetical**: it says what the arithmetic would give if that state were ever legitimately earned, not that it is close. Nothing here claims PARTIAL or VALIDATED.

Written 2026-10-13 by recomputation, not by quoting older documents. Inputs: the committed 196-lake table `jobs/lake-brain/data/bindings.proposed.v1.json`, the research evidence tables on `origin/docs/lake-brain-research` (`plan_flood_evidence.csv`, `verified_bindings_v2.csv`), NID dam links (`nid_links.csv`), the rollout order of `LAKE_BRAIN_STAGED_FLEET_ROLLOUT.md`, and read-only copies of the five published pilot profiles. Script: `jobs/lake-brain/readiness/rubric_proposals.py`; tests: `jobs/lake-brain/readiness/test_rubric_proposals.py`; draft rubric: `docs/brains/scoring/proposed/`.

## 0. The answer in one page

1. **The scorer does not read the rubric JSON.** Weights, rules and gates are hard-coded in `scoring.py` (`dim("floodDroughtContext", 5, ...)`, `vmap`, the gate caps). So the JSON is documentation, and adopting any proposal below is a **scorer change plus new published profile / validation fields**, never a JSON edit. The draft files under `docs/brains/scoring/proposed/` are loaded by nothing; tests prove it (section 10).
2. **P1, floodDroughtContext denominator = lakes where a flood pool exists.** On the 196 lakes the dimension goes **5.7 to 8.1** (UNDETERMINED lakes excluded, "X") or **7.4** (counted, "C"); uncapped **6.5 to 6.7 / 6.6**; displayed unchanged at 5.0 while `NOT_VALIDATED` (the gate binds). Of the 85 lakes without a documented flood level, 47 are NOT_APPLICABLE (the NID purposes list no flood control), 12 are UNDETERMINED (no NID link), and **26 are UNKNOWN because unpublished** (9 of them TVA, whose API publishes no flood-pool bottom); those 26 stay in the denominator. This is a composition fix, it hides no gap, and it adds 0.1 to 0.2 to the underlying score.
3. **P2, per-claim validation** replaces the single fleet-wide word by four claim families (provider display, deterministic derivation, historical state, rapid change) read as "weakest **published** family". For any given family state the arithmetic is **identical to today's rubric** (0 / 5 / 10 on the same 15 points). What it changes is **what can be reached**: with RAPID published and failing its hold-out (H-C), the dimension stays 0 and the 5.0 cap stays on. With RAPID withheld, a PARTIAL-equivalent state (validation 5.0, cap lifted, 196 lakes displayed 7.3) needs only the binding review and the ledger clock, **2027-01-11 at the earliest for the pilots (fleet start + 90 days for a fleet)**, instead of also waiting for a revised H-C. It does **not** move the VALIDATED date, because the historical-state family still needs 12 months of logged predictions.
4. **P3, operatorPlan denominator = lakes where the operator publishes a guide curve or zone.** With UNKNOWN **excluded** ("X") the dimension on the 196 goes **4.3 to 7.0** and a fleet of 63 lakes reaches 8.0 at VALIDATED (7.7 to 8.0) instead of 156; with UNKNOWN **counted** ("C") it goes **4.3 to 4.4**. X turns the dimension into a **capture rate** (how much of what operators publish Sector has ingested), not an availability rate: adding lakes with no known plan can no longer lower it. At the evidence ceiling X is 10.0 by construction. I recommend **no** to X and no to C (section 5).
5. **The key honest answer (section 7).** Under the **current** rubric, overall 8.0 is arithmetically reachable on evidence in hand (documented, or with the TWDB tier-2 data adopted) **only at VALIDATED and only with at least 156 lakes** (the 25 % coverage rung): the 196 table gives **8.045** at VALIDATED (margin: 6 history lakes). A 63-lake fleet gets there only at the evidence CEILING (8.085: every documentable pool documented and the S-B definition accepted), which is not evidence in hand. The critical set `sourceAuthority, historyQuality, seasonalBaseline, trendQuality, validation >= 7.5` is met by the first four on every fleet (lowest 8.6) and by `validation` **only at 10**, which no proposal changes (the dimension takes only 0, 5, 10). So the target is **unreachable before the historical-state family is VALIDATED = 12 months of fleet predictions scored once: first ledger day of the fleet + 365 days.** Pilots-only that is 2027-10-13, but a pilots-only Brain displays at most 3.0 (coverage gate), so the real earliest date is **fleet first ledger day + 365**. No combination of P1, P2, P3 changes this; P1 and P3 only add overall margin (CURRENT 6 lakes, P1+P2+P3-C 14 lakes, X variants 37 lakes), P2 moves the PARTIAL date only.
6. **Do not average claim families.** Reading the dimension as the *mean* of families instead of the minimum lets validation clear 7.5 at "Level 1/2 VALIDATED, historical state only PARTIAL" (8.3), and stacked with the X denominators it shows the **full target met on documented evidence** (section 4.7). That is a floor that no longer tests the weakest claim. Not proposed.
7. **What Michael approves** is a short yes/no list in section 8.

## 1. Method and guarantees

**Production code is reused, not forked.** `score_variant()` calls the unmodified `score_lake()` for the five dimensions no proposal touches (sourceAuthority, historyQuality, seasonalBaseline, trendQuality, coverage) and re-derives only operatorPlan, floodDroughtContext and validation, then combines them with production's own `finish()` (rounding, gates, blockers). With `CURRENT` rules the result equals `score_lake()` on: the five **published** pilot profiles (displayed 3.0, uncapped 6.3), the 196 table, every nested fleet, 427 lakes, and 120 random fleets with random health and directory sizes (the random test found one real rounding-order difference in a first draft, `share * 10` versus `10 * n / d`, now fixed and pinned).

**Fleets.** `5` = today's pilots (Guntersville, Hartwell, Pickwick, Wheeler, Wilson). `63` = 10 % of 621, the coverage gate threshold. `123` = the end of batch C plus one (the "batch B-ish" state). `196` = the accepted-eligible table. `427` = the most permissive research-bound set (68.8 % of 621, coverage 7 points; any rule, including stage-only gauges and post-hoc envelope rules, unmeasured error). 63 and 123 are **nested prefixes of the rollout order of `LAKE_BRAIN_STAGED_FLEET_ROLLOUT.md`** (pilots, then batches A, B, C, D). That order puts the best-documented lakes first (batch B needs at least 15 complete years), so the 63 and 123 figures are optimistic for history; section 7.4 repeats the headline with 100 random orderings. They are illustrations of state, not a prediction of which lakes Michael accepts.

**Evidence levels** (the same for every fleet; they differ only in operatorPlan and floodDroughtContext):

| Level | Plan counts when | Flood known when |
|---|---|---|
| NOW | strict guide curve, or zone with a top **and** a bottom, as documented in the table | operator flood-pool bottom documented in the table |
| KNOWN | NOW plus TWDB conservation + dead-pool pairs (9 lakes, tier 2, evidence in hand, not adopted) | NOW plus TWDB flood levels (4 lakes) |
| CEILING | KNOWN plus the 36 "S-B" lakes (Top of Conservation plus an operator-published lower-pool level; a **definition decision**, not evidence) | every lake where a flood pool exists is documented (generous: includes the 9 TVA lakes whose operator publishes no bottom; the realistic ceiling is 9 lakes lower) |

history, baseline, source and trend are the table's own values at every level (history is the research `historyClass`; the four TVA pilots are SUFFICIENT as in the live profiles; trend assumes every state is OBSERVED, as in the readiness matrix: the 2026-10-13 probe found 194 of 195 sources within 72 h).

**Caveats stated up front.** (a) 104 of the 427 lakes are wave-2 lakes for which **no plan or flood search was run**; they carry no plan or flood credit, and the NID link is missing for 105 lakes, so the 427 rows of P1/P3 are lower bounds for the current rubric and **not interpretable** for the X denominators (an unsearched lake looks like an unknown one). (b) The rollout-order prefixes are best-first. (c) CEILING is an upper bound, never a forecast. (d) Nothing was tuned: every rule was fixed before its numbers were read, and no threshold was changed after a result.

## 2. Today, decomposed (published inputs)

Five pilots: sourceAuthority 10.0, operatorPlan 10.0 (5 of 5), historyQuality 10.0, seasonalBaseline 10.0, trendQuality 10.0, floodDroughtContext **2.0** (1 of 5: Hartwell only), validation **0.0**, coverage **1.0** (0.8 %). Uncapped = (150 + 100 + 150 + 100 + 100 + 10 + 0 + 20) / 100 = **6.3**. Gates: coverage (under 10 %) caps at 3.0, validation caps at 5.0. Displayed **3.0**.

The same arithmetic across the fleet states, current rubric, documented evidence (PARTIAL and VALIDATED hypothetical):

| fleet | profiled | sourceAuth | plan | history | baseline | trend | flood | coverage | NOT_VALIDATED unc / disp | PARTIAL (hyp.) unc / disp | VALIDATED (hyp.) unc / disp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.8% | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 2.0 | 1.0 | 6.3 / 3.0 | 7.0 / 3.0 | 7.8 / 3.0 |
| 63 | 10.1% | 10.0 | 3.7 | 10.0 | 10.0 | 10.0 | 4.9 | 3.0 | 6.2 / 5.0 | 7.0 / 7.0 | 7.7 / 7.7 |
| 123 | 19.8% | 10.0 | 3.7 | 10.0 | 10.0 | 10.0 | 5.9 | 3.0 | 6.3 / 5.0 | 7.0 / 7.0 | 7.8 / 7.8 |
| 196 | 31.6% | 10.0 | 4.3 | 9.2 | 9.5 | 10.0 | 5.7 | 5.0 | 6.5 / 5.0 | 7.3 / 7.3 | 8.0 / 8.0 |

## 3. Proposal P1: floodDroughtContext denominator = lakes where a flood pool exists

### 3.1 Current rule (exact)

`lake-brain-score-v1.json`, `dimensions[5]`:

```json
{"id": "floodDroughtContext", "label": "Flood-pool state known", "weight": 5, "fact": "states[*].floodPoolState != UNKNOWN", "scale": "share x 10"}
```

`scoring.py`: `flood = share_of(lambda s: s.get("floodPoolState") not in (None, "UNKNOWN"), states.values())` over **every published state**.

### 3.2 Proposed rule (exact JSON diff against v1; RFC 6902 subset; alternatives X or C)

P1-X (UNDETERMINED excluded; the literal "a flood pool exists"):

```json
[
 {
  "op": "replace",
  "path": "/dimensions/5/label",
  "value": "Flood-pool state known, where a flood pool exists"
 },
 {
  "op": "replace",
  "path": "/dimensions/5/fact",
  "value": "states[*].floodPoolState != UNKNOWN, over lakes with profiles[*].operatingPools.floodPoolApplicability == EXISTS"
 },
 {
  "op": "add",
  "path": "/dimensions/5/applicability",
  "value": {
   "field": "profiles[*].operatingPools.floodPoolApplicability",
   "EXISTS": "an operator or TWDB flood-pool level is documented, OR the linked NID dam record lists 'Flood Risk Reduction' among its purposes",
   "NOT_APPLICABLE": "an NID dam record with purposes is linked, none of them is flood control, and no flood-pool level is documented",
   "UNDETERMINED": "no NID dam record or no purposes, and no flood-pool level is documented",
   "denominator": "EXISTS only (UNDETERMINED excluded)",
   "EXISTS_but_unpublished": "stays in the denominator as UNKNOWN: a pool that exists but whose level is not published is a real gap, not a non-applicability"
  }
 }
]
```

P1-C differs in three strings (label, fact, and `applicability.denominator`): the label and fact read "where a flood pool exists or cannot be ruled out", the fact's lake set is `floodPoolApplicability in {EXISTS, UNDETERMINED}`, and `applicability.denominator` is "EXISTS and UNDETERMINED (only a positive NOT_APPLICABLE finding is excluded)". Full text in `docs/brains/scoring/proposed/lake-brain-score-v1-to-v2-DRAFT.patch.json`.

Needs (not done): a published profile field `operatingPools.floodPoolApplicability`, set by the profile builder from the binding table (`dam.floodControl`, documented levels) at generation time, and a scorer change that reads it.

### 3.3 Classification rule (precise) and counts

For each lake, at an evidence level:

- **DOCUMENTED**: a flood-pool level is documented at that level (operator Top of Conservation / Bottom of Flood; at KNOWN also a TWDB flood level).
- **EXISTS, UNKNOWN because unpublished** (`EXISTS_UNPUBLISHED`): not documented, and the linked NID dam record lists "Flood Risk Reduction" among its purposes (or TWDB documents a flood level once adopted). A pool exists; its level is not published or not found. **Stays in the denominator** as UNKNOWN.
- **NOT_APPLICABLE**: an NID dam record **with purposes** is linked, none of them is flood control, and nothing is documented.
- **UNDETERMINED**: no NID dam record or no purposes, and nothing is documented. Excluded in X, counted in C.

"A flood pool exists" = DOCUMENTED or EXISTS_UNPUBLISHED. Counts at documented evidence:

| fleet | flood DOCUMENTED | EXISTS_UNPUBLISHED | NOT_APPLICABLE | UNDETERMINED | plan CAPTURED | PUBLISHED_NOT_CAPTURED | OPERATOR_READ_NO_PLAN | UNKNOWN |
|---|---|---|---|---|---|---|---|---|
| 5 | 1 | 3 | 1 | 0 | 5 | 0 | 0 | 0 |
| 63 | 31 | 11 | 18 | 3 | 23 | 12 | 1 | 27 |
| 123 | 72 | 15 | 31 | 5 | 45 | 29 | 4 | 45 |
| 196 | 111 | 26 | 47 | 12 | 84 | 36 | 5 | 71 |
| 427 | 168 | 55 | 102 | 102 | 125 | 55 | 12 | 235 |

On the 196 (NOW): 111 documented, **26 UNKNOWN-because-unpublished** (9 TVA: the TVA RestApi publishes no flood-pool bottom, flag `noOperatorFloodPoolThreshold`; 17 evidence gaps: USACE 7, State 4, Private 2, Local government 2, USBR 1, Public utility 1), **47 NOT_APPLICABLE** (hydropower, supply and recreation reservoirs; 4 of these 47 are Texas lakes whose TWDB flood level contradicts the NID purposes and become DOCUMENTED at KNOWN), **12 UNDETERMINED**. Flood pools exist for 137 lakes (111 + 26), the same 137 as the readiness matrix; at KNOWN 141. Dimension = 111/137 = 8.1 (X) or 111/149 = 7.4 (C). If the 9 TVA lakes were also excluded as "operator publishes none" the value would be 111/128 = 8.7, which rewards an operator's silence; not proposed.

### 3.4 Effect (dimension, uncapped, displayed; documented evidence)

| fleet | proposal | dimension (current -> proposed) | NOT_VALIDATED: uncapped / displayed | PARTIAL (hypothetical): uncapped / displayed | VALIDATED (hypothetical): uncapped / displayed |
|---|---|---|---|---|---|
| 5 | P1-X | floodDroughtContext: 2.0 -> 2.5 | 6.3 -> 6.3 / 3.0 -> 3.0 | 7.0 -> 7.1 / 3.0 -> 3.0 | 7.8 -> 7.8 / 3.0 -> 3.0 |
| 5 | P1-C | floodDroughtContext: 2.0 -> 2.5 | 6.3 -> 6.3 / 3.0 -> 3.0 | 7.0 -> 7.1 / 3.0 -> 3.0 | 7.8 -> 7.8 / 3.0 -> 3.0 |
| 63 | P1-X | floodDroughtContext: 4.9 -> 7.4 | 6.2 -> 6.3 / 5.0 -> 5.0 | 7.0 -> 7.1 / 7.0 -> 7.1 | 7.7 -> 7.8 / 7.7 -> 7.8 |
| 63 | P1-C | floodDroughtContext: 4.9 -> 6.9 | 6.2 -> 6.3 / 5.0 -> 5.0 | 7.0 -> 7.1 / 7.0 -> 7.1 | 7.7 -> 7.8 / 7.7 -> 7.8 |
| 123 | P1-X | floodDroughtContext: 5.9 -> 8.3 | 6.3 -> 6.4 / 5.0 -> 5.0 | 7.0 -> 7.1 / 7.0 -> 7.1 | 7.8 -> 7.9 / 7.8 -> 7.9 |
| 123 | P1-C | floodDroughtContext: 5.9 -> 7.8 | 6.3 -> 6.4 / 5.0 -> 5.0 | 7.0 -> 7.1 / 7.0 -> 7.1 | 7.8 -> 7.9 / 7.8 -> 7.9 |
| 196 | P1-X | floodDroughtContext: 5.7 -> 8.1 | 6.5 -> 6.7 / 5.0 -> 5.0 | 7.3 -> 7.4 / 7.3 -> 7.4 | 8.0 -> 8.2 / 8.0 -> 8.2 |
| 196 | P1-C | floodDroughtContext: 5.7 -> 7.4 | 6.5 -> 6.6 / 5.0 -> 5.0 | 7.3 -> 7.4 / 7.3 -> 7.4 | 8.0 -> 8.1 / 8.0 -> 8.1 |

Reading: the dimension rises by 0.5 (pilots) to 2.4 (196). Because it carries 5 of 100 points the underlying score rises by 0.0 to 0.2, and the **displayed** score does not change under `NOT_VALIDATED` (the gate caps at 5.0 and the coverage gate at 3.0 for the pilots) and moves one-for-one with the underlying score under a hypothetical PARTIAL or VALIDATED. For the pilots 2.0 becomes 2.5 because Wheeler (NID: no flood control) leaves the denominator; the three flood-control TVA pilots stay UNKNOWN-unpublished.

### 3.5 Risks and my reading

- It cannot be gamed by silence: a flood-control reservoir without a published bottom stays penalised. It can be gamed by the NID link: a lake wrongly linked to a non-flood dam leaves the denominator. The 196 links are machine-verified (distance, name, id); beyond the 196 the NID link is missing for 105 of the 427 lakes, which is why X and C diverge there (7.5 versus 5.2). **C is the conservative form** (only a positive "not flood control" finding earns an exclusion) and is the one I would approve if you approve P1. X is the literal wording of the brief and of the product-reset review (111/137).
- It does not change anything Sector publishes; `UNKNOWN` stays a valid output.

## 4. Proposal P2: per-claim validation (claim families) and what happens to the gate

### 4.1 Current rule (exact)

`dimensions[6]`: `{"id": "validation", "label": "Fleet validation", "weight": 15, "fact": "/validation/lake-brain.status", "scale": {"NOT_VALIDATED": 0, "PARTIAL": 5, "VALIDATED": 10}}`; `gates[1]`: `{"id": "validation", "when": "validation NOT_VALIDATED", "cap": 5.0}`. One word for every claim the Brain makes.

### 4.2 Proposed rule

Claim families and which published claims count:

| Family | Level | Claims in it | Counts when |
|---|---|---|---|
| providerDisplay | 1 | current pool elevation, operator guide / normal pool / flood-pool bottom as published, source id, freshness | always (always published) |
| deterministicDerivation | 2 | difference from guide or normal pool, operator zone (IN_ZONE, BELOW_ZONE, ...), 72 h mean rate, trend direction arithmetic | always |
| historicalState | 3 | NORMAL / UNUSUAL / VERY_UNUSUAL against the lake's own history (VERY_UNUSUAL already history-tier gated), trend label stability (H-A, H-B, H-D) | always |
| rapidChange | 3 | RISING_RAPIDLY / FALLING_RAPIDLY and `rapidChangeThresholdFt` (H-C) | **only while published**; a withheld family is not counted and its claims are not shown |

Not counted: species presence (private research, not a Lake level claim), geometry, the Conditions Score.

Per-family maturity, mapped to the **same 0 / 5 / 10 scale** (no new values):

| Family status | Value | Evidence required |
|---|---|---|
| NOT_VALIDATED | 0 | no family-specific acceptance recorded |
| PARTIAL | 5 | binding acceptance recorded (stratified n >= 60, at most 1 error, flagged tier in full, committed review result) **plus** per family: derivation = conformance fixtures and level-meaning review (V13); historicalState = pre-registered hold-out PASS (H-A, H-B, H-D: done retrospectively) and ledger >= 90 days; rapidChange = a pre-registered criterion PASS on ledger data dated after its commit |
| VALIDATED | 10 | PARTIAL **plus** per family: provider display and derivation = continuous freshness record >= 90 days; historicalState and rapidChange = >= 12 months of logged predictions scored once under the pre-registered criteria |

Dimension value = **minimum over counted families** (weakest published claim). Exact JSON diff:

```json
[
 {
  "op": "replace",
  "path": "/dimensions/6/label",
  "value": "Claim validation (weakest published claim family)"
 },
 {
  "op": "replace",
  "path": "/dimensions/6/fact",
  "value": "min over COUNTED claim families of /validation/lake-brain/claims/{family}.status"
 },
 {
  "op": "add",
  "path": "/dimensions/6/families",
  "value": [
   {
    "id": "providerDisplay",
    "level": 1,
    "claims": "current pool elevation, operator guide / normal pool / flood-pool bottom as published, source id, freshness"
   },
   {
    "id": "deterministicDerivation",
    "level": 2,
    "claims": "difference from guide or normal pool, operator zone, 72 h mean rate, trend direction arithmetic"
   },
   {
    "id": "historicalState",
    "level": 3,
    "claims": "NORMAL / UNUSUAL / VERY_UNUSUAL against the lake's own history; trend label stability"
   },
   {
    "id": "rapidChange",
    "level": 3,
    "claims": "RISING_RAPIDLY / FALLING_RAPIDLY flag"
   }
  ]
 },
 {
  "op": "add",
  "path": "/dimensions/6/counted",
  "value": "a family counts while at least one of its claims is published; a family withheld from publication (status WITHHELD) is not counted and its claims are not shown"
 },
 {
  "op": "add",
  "path": "/dimensions/6/aggregate",
  "value": "min"
 },
 {
  "op": "add",
  "path": "/dimensions/6/familyMaturity",
  "value": {
   "NOT_VALIDATED": "no family-specific acceptance evidence recorded",
   "PARTIAL": "binding acceptance recorded (n >= 60, <= 1 error, flagged tier in full); plus per family: derivation = conformance fixtures and level-meaning review; historicalState = pre-registered hold-out PASS and ledger >= 90 days; rapidChange = a pre-registered criterion PASS on ledger data dated after its commit",
   "VALIDATED": "PARTIAL plus per family: provider display and derivation = continuous freshness record >= 90 days; historicalState and rapidChange = >= 12 months of logged predictions scored once under the pre-registered criteria"
  }
 },
 {
  "op": "replace",
  "path": "/gates/1/when",
  "value": "any COUNTED claim family is NOT_VALIDATED"
 }
]
```

Needs (not done): a `claims{family: status}` block in the `/validation/lake-brain` contract (BRAIN_PLATFORM_CONTRACT), a scorer change, and the PARTIAL definition (`LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`) restated per family. The provider-display and derivation VALIDATED evidence (continuous freshness) is my wording for an otherwise undefined cell; it is immaterial to every number below because the historicalState family always binds.

### 4.3 The gate, reinterpreted

Current: while the single word is `NOT_VALIDATED`, the displayed score is capped at 5.0. Proposed: **the cap holds while any counted family is NOT_VALIDATED** (value 0). Therefore:

- **Still capped:** (i) everything until every counted family has reached at least PARTIAL; (ii) indefinitely, while RAPID is published and has not passed a criterion (today: H-C FAIL, preserved); (iii) the coverage gate (under 63 lakes, 3.0) and the health gate (2.0) are untouched.
- **No longer capped:** the cap lifts when the weakest *published* family reaches PARTIAL. Withholding a family trades its claims for the cap, not for a number.

### 4.4 Effect on the score, by claim-family state (196 lakes, documented evidence; hypothetical after S0)

| claim-family state (hypothetical) | families (display/derivation/historical/RAPID; W = withheld) | validation dim (min) | uncapped | displayed | gate fired | NOT PROPOSED: dim if averaged | NOT PROPOSED: displayed if averaged |
|---|---|---|---|---|---|---|---|
| S0 today: nothing recorded | 0/0/0/0 | 0.0 | 6.5 | 5.0 | validation | 0.0 | 5.0 |
| S1 binding accepted; Level 1/2 PARTIAL; historicalState and RAPID not yet | 5/5/0/0 | 0.0 | 6.5 | 5.0 | validation | 2.5 | 5.0 |
| S2 + ledger 90 d: historicalState PARTIAL; RAPID (H-C failed) still published | 5/5/5/0 | 0.0 | 6.5 | 5.0 | validation | 3.8 | 5.0 |
| S3 as S2 with RAPID withheld | 5/5/5/W | 5.0 | 7.3 | 7.3 | none | 5.0 | 7.3 |
| S4 Level 1/2 VALIDATED, historicalState PARTIAL, RAPID withheld | 10/10/5/W | 5.0 | 7.3 | 7.3 | none | 8.3 | 7.8 |
| S5 all counted families VALIDATED, RAPID withheld | 10/10/10/W | 10.0 | 8.0 | 8.0 | none | 10.0 | 8.0 |
| S6 OUT OF SCOPE: Level 1/2 VALIDATED, historicalState AND RAPID withheld | 10/10/W/W | 10.0 | 8.0 | 8.0 | none | 10.0 | 8.0 |

(Families column: provider display / derivation / historical state / RAPID, 0 = NOT_VALIDATED, 5 = PARTIAL, 10 = VALIDATED, W = withheld.) For the same states across fleets:

| fleet | S0 today | S2 RAPID published, H-C failed | S3 RAPID withheld, all PARTIAL | S5 RAPID withheld, all VALIDATED |
|---|---|---|---|---|
| 5 | 6.3 / 3.0 | 6.3 / 3.0 | 7.0 / 3.0 | 7.8 / 3.0 |
| 63 | 6.2 / 5.0 | 6.2 / 5.0 | 7.0 / 7.0 | 7.7 / 7.7 |
| 123 | 6.3 / 5.0 | 6.3 / 5.0 | 7.0 / 7.0 | 7.8 / 7.8 |
| 196 | 6.5 / 5.0 | 6.5 / 5.0 | 7.3 / 7.3 | 8.0 / 8.0 |

The single word cannot express S1 to S4. Under the current definition, S3 and S5 are **not reachable at all while H-C stands failed** (PARTIAL item 2 needs H-A to H-D to all pass; item 3 withholds failing families, which cannot cure a failed item 2). So for each row the honest comparison is: the arithmetic equals the current rubric's PARTIAL or VALIDATED row, but the *state* is reachable only with the claim families and, for S3 to S5, RAPID withheld.

### 4.5 "Withhold RAPID from publication"

Effect, 196 lakes: validation **0.0 to 5.0** (S2 to S3), cap **lifted**, uncapped 6.5 to 7.3, displayed **5.0 to 7.3**. Nothing else moves. It is a publishing decision (Swift: a withhold flag and a new `rulesVersion`; RAPID is today published for the five pilots), not a rubric edit.

Dates: the PARTIAL evidence clock is ledger day 90 = **2027-01-11 for the pilots; first fleet ledger day + 90 for a fleet**. Without withholding, PARTIAL additionally needs a revised, separately pre-registered H-C scored on ledger data dated after its commit (`LAKE_BRAIN_VALIDATION_READINESS.md` 3.3): not before 2027-01-11 for a pooled criterion, about 12 months for a per-lake-share criterion (a per-lake rate at 90 days has a standard error of 1.9 percentage points). VALIDATED is unchanged: **first ledger day + 365** (2027-10-13 pilots-only), because historicalState is counted.

Honesty about the amendment: the readiness document notes that "PARTIAL with RAPID withheld" is an amendment of the PARTIAL definition **made after the H-C result**. It must be recorded as such (what was withheld, why, on what date), it is not a hold-out pass, and it does not rescue H-C. The two routes are a real choice: withhold now (cheap, the flag disappears from the app until it earns its way back) or keep publishing and spend a ledger period on a revised H-C.

### 4.6 What the per-claim reading really buys

Nothing arithmetic. It buys (a) the ability to say, claim by claim, what is verified, which matches the Level 1/2 evidence already in hand (123 independent cross-source pairs, median gap 0.015 ft; 194 of 195 sources fresh at the probe), (b) a PARTIAL that is reachable on its clock if RAPID is withheld, (c) honest labelling of what is not validated instead of one word.

### 4.7 Averaging is a loophole (NOT PROPOSED)

If the dimension were the **mean** of the counted families, "Level 1/2 VALIDATED, historical state PARTIAL" (state S4, reachable at the ledger-day-90 clock) scores validation 8.3 and clears the 7.5 floor with the *weakest* claim only half-validated. Stacked with the X denominators, the full target is met on documented evidence at that state:

| validation rule | fleet | validation dim | uncapped | displayed | all critical >= 7.5 | target met on documented evidence |
|---|---|---|---|---|---|---|
| P2 (min), proposed | 196 | 5.0 | 7.3 | 7.3 | no | no |
| P2 (min), proposed | 427 | 5.0 | 7.3 | 7.3 | no | no |
| P2 averaged | 196 | 8.3 | 7.8 | 7.8 | yes | no |
| P2 averaged | 427 | 8.3 | 7.8 | 7.8 | yes | no |
| ALL (X) averaged | 196 | 8.3 | 8.2 | 8.2 | yes | YES |
| ALL (X) averaged | 427 | 8.3 | 8.4 | 8.4 | yes | YES |
| ALL (C) averaged | 196 | 8.3 | 7.9 | 7.9 | yes | no |
| ALL (C) averaged | 427 | 8.3 | 7.9 | 7.9 | yes | no |

I recommend the explicit answer **no** to any aggregation other than the minimum.

Also out of scope but stated because it is the only route to the validation floor before the 12-month clock: **withholding the historical-state claim as well** (S6) makes Level 1/2 the only counted families, validation 10 and displayed 8.0 on the 196. It removes the product's central claim ("is this lake high, low or normal for this time of year"), so it is a product decision, not a rubric tweak, and I do not propose it.

## 5. Proposal P3: operatorPlan denominator = lakes where the operator publishes a guide curve or zone

### 5.1 Current rule (exact)

`dimensions[1]`: `{"id": "operatorPlan", "label": "Operating guide or zone known", "weight": 10, "fact": "profiles[*].operatingPools.guideCurve.available or operatingZoneSource", "scale": "share x 10"}`. Share of **all profiled lakes**.

### 5.2 Classification and proposed rule

Per lake: **CAPTURED** (strict guide curve, or zone with a top and a bottom, documented); **PUBLISHED_NOT_CAPTURED** (the operator publishes plan-type levels that do not meet the strict rule: an S-B lower-pool level beside Top of Conservation, 36 lakes; a TWDB conservation + dead-pool pair once adopted); **OPERATOR_READ_NO_PLAN** (a verified operator project was read and publishes none: not applicable); **UNKNOWN** (no verified operator record, or no search run).

- **P3-X (UNKNOWN excluded):** denominator = CAPTURED + PUBLISHED_NOT_CAPTURED.
- **P3-C (UNKNOWN counted):** denominator = those plus UNKNOWN; only OPERATOR_READ_NO_PLAN is excluded.

```json
[
 {
  "op": "replace",
  "path": "/dimensions/1/label",
  "value": "Operating guide or zone captured, where the operator publishes one"
 },
 {
  "op": "replace",
  "path": "/dimensions/1/fact",
  "value": "profiles[*].operatingPools.guideCurve.available or operatingZoneSource, over lakes with profiles[*].operatingPools.planPublication in {CAPTURED, PUBLISHED_NOT_CAPTURED}"
 },
 {
  "op": "add",
  "path": "/dimensions/1/publication",
  "value": {
   "field": "profiles[*].operatingPools.planPublication",
   "CAPTURED": "strict guide curve, or a zone with BOTH a top and a bottom, documented",
   "PUBLISHED_NOT_CAPTURED": "the operator publishes plan-type levels (a lower-pool level beside Top of Conservation; a TWDB conservation + dead pool pair) that do not meet the strict rule",
   "OPERATOR_READ_NO_PLAN": "a verified operator project was read and publishes no plan-type level (not applicable)",
   "UNKNOWN": "no verified operator record",
   "denominator": "CAPTURED and PUBLISHED_NOT_CAPTURED (UNKNOWN excluded)"
  }
 }
]
```

(P3-C: label "... where the operator publishes one or is unknown", fact set `{CAPTURED, PUBLISHED_NOT_CAPTURED, UNKNOWN}`; full text in the patch file.) Needs (not done): a profile field `operatingPools.planPublication` and a scorer change.

Counts on the 196 (NOW): CAPTURED **84**, PUBLISHED_NOT_CAPTURED **36**, OPERATOR_READ_NO_PLAN **5**, UNKNOWN **71** (table in section 3.3). X denominator 120 (84/120 = 7.0); C denominator 191 (84/191 = 4.4).

### 5.3 Effect

| fleet | proposal | dimension (current -> proposed) | NOT_VALIDATED: uncapped / displayed | PARTIAL (hypothetical): uncapped / displayed | VALIDATED (hypothetical): uncapped / displayed |
|---|---|---|---|---|---|
| 5 | P3-X | operatorPlan: 10.0 -> 10.0 | 6.3 -> 6.3 / 3.0 -> 3.0 | 7.0 -> 7.0 / 3.0 -> 3.0 | 7.8 -> 7.8 / 3.0 -> 3.0 |
| 5 | P3-C | operatorPlan: 10.0 -> 10.0 | 6.3 -> 6.3 / 3.0 -> 3.0 | 7.0 -> 7.0 / 3.0 -> 3.0 | 7.8 -> 7.8 / 3.0 -> 3.0 |
| 63 | P3-X | operatorPlan: 3.7 -> 6.6 | 6.2 -> 6.5 / 5.0 -> 5.0 | 7.0 -> 7.3 / 7.0 -> 7.3 | 7.7 -> 8.0 / 7.7 -> 8.0 |
| 63 | P3-C | operatorPlan: 3.7 -> 3.7 | 6.2 -> 6.2 / 5.0 -> 5.0 | 7.0 -> 7.0 / 7.0 -> 7.0 | 7.7 -> 7.7 / 7.7 -> 7.7 |
| 123 | P3-X | operatorPlan: 3.7 -> 6.1 | 6.3 -> 6.5 / 5.0 -> 5.0 | 7.0 -> 7.3 / 7.0 -> 7.3 | 7.8 -> 8.0 / 7.8 -> 8.0 |
| 123 | P3-C | operatorPlan: 3.7 -> 3.8 | 6.3 -> 6.3 / 5.0 -> 5.0 | 7.0 -> 7.0 / 7.0 -> 7.0 | 7.8 -> 7.8 / 7.8 -> 7.8 |
| 196 | P3-X | operatorPlan: 4.3 -> 7.0 | 6.5 -> 6.8 / 5.0 -> 5.0 | 7.3 -> 7.6 / 7.3 -> 7.6 | 8.0 -> 8.3 / 8.0 -> 8.3 |
| 196 | P3-C | operatorPlan: 4.3 -> 4.4 | 6.5 -> 6.6 / 5.0 -> 5.0 | 7.3 -> 7.3 / 7.3 -> 7.3 | 8.0 -> 8.1 / 8.0 -> 8.1 |

### 5.4 Why I recommend no

- **X is circular.** "The operator publishes a plan" is known only because Sector found one, so the denominator is the set of lakes Sector already knows about. Adding 30 lakes with no known plan lowers the current rubric and leaves X unchanged (tested). The dimension stops measuring availability and measures ingest completeness; a fleet in which no operator publishes a plan scores UNKNOWN (0 points), and at the ceiling (all published plans captured) X is 10.0 by construction.
- **It changes the reachable target, not the Brain.** On the best-first prefixes, X lets 63 lakes reach 8.0 at VALIDATED; the current rubric needs 156 (section 7.3). Nothing about the lakes changed.
- **C is honest but tiny:** 4.3 to 4.4, because only 5 lakes are excluded. Not worth a schema field.
- The real mover for this dimension is **evidence and one definition**: S-B (36 lakes) would take plan from 84 to 120 captured (4.3 to 6.1, underlying +0.18) and is a separate decision already on Michael's queue; TWDB adds 9. These raise the numerator, which is what the dimension is for.

## 6. Combined (P1 + P2 with RAPID withheld + P3; X and C forms)

| fleet | proposal | dimension (current -> proposed) | NOT_VALIDATED: uncapped / displayed | PARTIAL (hypothetical): uncapped / displayed | VALIDATED (hypothetical): uncapped / displayed |
|---|---|---|---|---|---|
| 5 | ALL (X) | operatorPlan: 10.0 -> 10.0; floodDroughtContext: 2.0 -> 2.5 | 6.3 -> 6.3 / 3.0 -> 3.0 | 7.0 -> 7.1 / 3.0 -> 3.0 | 7.8 -> 7.8 / 3.0 -> 3.0 |
| 5 | ALL (C) | operatorPlan: 10.0 -> 10.0; floodDroughtContext: 2.0 -> 2.5 | 6.3 -> 6.3 / 3.0 -> 3.0 | 7.0 -> 7.1 / 3.0 -> 3.0 | 7.8 -> 7.8 / 3.0 -> 3.0 |
| 63 | ALL (X) | operatorPlan: 3.7 -> 6.6; floodDroughtContext: 4.9 -> 7.4 | 6.2 -> 6.6 / 5.0 -> 5.0 | 7.0 -> 7.4 / 7.0 -> 7.4 | 7.7 -> 8.1 / 7.7 -> 8.1 |
| 63 | ALL (C) | operatorPlan: 3.7 -> 3.7; floodDroughtContext: 4.9 -> 6.9 | 6.2 -> 6.3 / 5.0 -> 5.0 | 7.0 -> 7.1 / 7.0 -> 7.1 | 7.7 -> 7.8 / 7.7 -> 7.8 |
| 123 | ALL (X) | operatorPlan: 3.7 -> 6.1; floodDroughtContext: 5.9 -> 8.3 | 6.3 -> 6.6 / 5.0 -> 5.0 | 7.0 -> 7.4 / 7.0 -> 7.4 | 7.8 -> 8.1 / 7.8 -> 8.1 |
| 123 | ALL (C) | operatorPlan: 3.7 -> 3.8; floodDroughtContext: 5.9 -> 7.8 | 6.3 -> 6.4 / 5.0 -> 5.0 | 7.0 -> 7.1 / 7.0 -> 7.1 | 7.8 -> 7.9 / 7.8 -> 7.9 |
| 196 | ALL (X) | operatorPlan: 4.3 -> 7.0; floodDroughtContext: 5.7 -> 8.1 | 6.5 -> 6.9 / 5.0 -> 5.0 | 7.3 -> 7.7 / 7.3 -> 7.7 | 8.0 -> 8.4 / 8.0 -> 8.4 |
| 196 | ALL (C) | operatorPlan: 4.3 -> 4.4; floodDroughtContext: 5.7 -> 7.4 | 6.5 -> 6.6 / 5.0 -> 5.0 | 7.3 -> 7.4 / 7.3 -> 7.4 | 8.0 -> 8.1 / 8.0 -> 8.1 |

The P2 component changes no number in this table (it appears only through which validation state is reachable). Combined X on the 196 gives 6.9 uncapped under `NOT_VALIDATED` (displayed 5.0) and 8.4 at a hypothetical VALIDATED; combined C gives 6.6 and 8.1.

## 7. The key honest answer: how high can the Lake Brain legitimately score, and when

Target (policy, `SECTOR_OPS_PRODUCTION_POLICY.md`; critical set is my proposal in `LAKE_BRAIN_PRODUCTION_READINESS_MATRIX.md`, option A): **displayed overall >= 8.0 and every critical dimension >= 7.5**, critical = sourceAuthority, historyQuality, seasonalBaseline, trendQuality, validation. No Lake dimension is designated critical today (Ops reads `requiredDimensions[]` only when the Engine publishes it).

### 7.1 Maximum legitimately achievable, VALIDATED (hypothetical) — KNOWN evidence (what is in hand) and CEILING (everything documentable)

63 lakes, KNOWN:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 4.6 | 5.6 | 3.0 | 7.8 (7.840) | 7.8 | no |
| P1-X | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 4.6 | 7.6 | 3.0 | 7.9 (7.940) | 7.9 | no |
| P1-C | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 4.6 | 7.1 | 3.0 | 7.9 (7.915) | 7.9 | no |
| P2+withhold-RAPID | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 4.6 | 5.6 | 3.0 | 7.8 (7.840) | 7.8 | no |
| P3-X | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 7.4 | 5.6 | 3.0 | 8.1 (8.120) | 8.1 | YES |
| P3-C | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 4.7 | 5.6 | 3.0 | 7.8 (7.850) | 7.8 | no |
| ALL (X) | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 7.4 | 7.6 | 3.0 | 8.2 (8.220) | 8.2 | YES |
| ALL (C) | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 4.7 | 7.1 | 3.0 | 7.9 (7.925) | 7.9 | no |

63 lakes, CEILING:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 6.2 | 7.3 | 3.0 | 8.1 (8.085) | 8.1 | YES |
| P1-X | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 6.2 | 10.0 | 3.0 | 8.2 (8.220) | 8.2 | YES |
| P1-C | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 6.2 | 9.4 | 3.0 | 8.2 (8.190) | 8.2 | YES |
| P2+withhold-RAPID | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 6.2 | 7.3 | 3.0 | 8.1 (8.085) | 8.1 | YES |
| P3-X | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 7.3 | 3.0 | 8.5 (8.465) | 8.5 | YES |
| P3-C | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 6.3 | 7.3 | 3.0 | 8.1 (8.095) | 8.1 | YES |
| ALL (X) | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 3.0 | 8.6 (8.600) | 8.6 | YES |
| ALL (C) | 10.0 | 10.0 | 10.0 | 10.0 | 10.0 | 6.3 | 9.4 | 3.0 | 8.2 (8.200) | 8.2 | YES |

196 lakes, KNOWN:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 4.7 | 5.9 | 5.0 | 8.1 (8.095) | 8.1 | YES |
| P1-X | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 4.7 | 8.2 | 5.0 | 8.2 (8.210) | 8.2 | YES |
| P1-C | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 4.7 | 7.5 | 5.0 | 8.2 (8.175) | 8.2 | YES |
| P2+withhold-RAPID | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 4.7 | 5.9 | 5.0 | 8.1 (8.095) | 8.1 | YES |
| P3-X | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 7.5 | 5.9 | 5.0 | 8.4 (8.375) | 8.4 | YES |
| P3-C | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 4.9 | 5.9 | 5.0 | 8.1 (8.115) | 8.1 | YES |
| ALL (X) | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 7.5 | 8.2 | 5.0 | 8.5 (8.490) | 8.5 | YES |
| ALL (C) | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 4.9 | 7.5 | 5.0 | 8.2 (8.195) | 8.2 | YES |

196 lakes, CEILING:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 6.3 | 7.2 | 5.0 | 8.3 (8.320) | 8.3 | YES |
| P1-X | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 6.3 | 10.0 | 5.0 | 8.5 (8.460) | 8.5 | YES |
| P1-C | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 6.3 | 9.2 | 5.0 | 8.4 (8.420) | 8.4 | YES |
| P2+withhold-RAPID | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 6.3 | 7.2 | 5.0 | 8.3 (8.320) | 8.3 | YES |
| P3-X | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 10.0 | 7.2 | 5.0 | 8.7 (8.690) | 8.7 | YES |
| P3-C | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 6.5 | 7.2 | 5.0 | 8.3 (8.340) | 8.3 | YES |
| ALL (X) | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 10.0 | 10.0 | 5.0 | 8.8 (8.830) | 8.8 | YES |
| ALL (C) | 10.0 | 9.2 | 9.5 | 10.0 | 10.0 | 6.5 | 9.2 | 5.0 | 8.4 (8.440) | 8.4 | YES |

427 lakes (most permissive set; plan/flood are lower bounds, section 1), KNOWN:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 3.3 | 4.1 | 7.0 | 8.1 (8.135) | 8.1 | YES |
| P1-X | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 3.3 | 7.7 | 7.0 | 8.3 (8.315) | 8.3 | YES |
| P1-C | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 3.3 | 5.3 | 7.0 | 8.2 (8.195) | 8.2 | YES |
| P2+withhold-RAPID | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 3.3 | 4.1 | 7.0 | 8.1 (8.135) | 8.1 | YES |
| P3-X | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 7.4 | 4.1 | 7.0 | 8.5 (8.545) | 8.5 | YES |
| P3-C | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 3.3 | 4.1 | 7.0 | 8.1 (8.135) | 8.1 | YES |
| ALL (X) | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 7.4 | 7.7 | 7.0 | 8.7 (8.725) | 8.7 | YES |
| ALL (C) | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 3.3 | 5.3 | 7.0 | 8.2 (8.195) | 8.2 | YES |

427 lakes, CEILING:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 4.4 | 5.4 | 7.0 | 8.3 (8.310) | 8.3 | YES |
| P1-X | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 4.4 | 10.0 | 7.0 | 8.5 (8.540) | 8.5 | YES |
| P1-C | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 4.4 | 6.9 | 7.0 | 8.4 (8.385) | 8.4 | YES |
| P2+withhold-RAPID | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 4.4 | 5.4 | 7.0 | 8.3 (8.310) | 8.3 | YES |
| P3-X | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 10.0 | 5.4 | 7.0 | 8.9 (8.870) | 8.9 | YES |
| P3-C | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 4.5 | 5.4 | 7.0 | 8.3 (8.320) | 8.3 | YES |
| ALL (X) | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 10.0 | 10.0 | 7.0 | 9.1 (9.100) | 9.1 | YES |
| ALL (C) | 10.0 | 8.6 | 9.1 | 10.0 | 10.0 | 4.5 | 6.9 | 7.0 | 8.4 (8.395) | 8.4 | YES |

The `P2+withhold-RAPID` row equals CURRENT in every cell, by design (P2 does not change the arithmetic at a given family state). "(rounding)" would mark a displayed 8.0 produced only by rounding an unrounded sum below 8.0; none occurs in these VALIDATED tables (it does occur once in the PARTIAL tables, section 7.2).

### 7.2 PARTIAL (hypothetical): the target fails on the critical floor under every rubric, on every fleet

At PARTIAL the validation dimension is 5.0, below 7.5, whichever rubric is used. Overall can reach 8.0 only where operatorPlan is 10.0 by construction (P3-X or the combined X form at the evidence ceiling: combined X 8.08 on 196 lakes and 8.35 on 427; P3-X alone 8.12 on 427), or by rounding (combined X on 427 lakes at KNOWN evidence is 7.975, displayed 8.0), and the critical floor still fails. The full PARTIAL tables are produced by `rubric_proposals.py --tables` (`maxPA_*`); the 196-lake CEILING table:

| rubric | sourceAuth | history | baseline | trend | validation | plan | flood | coverage | uncapped (unrounded) | displayed | overall>=8.0 and critical>=7.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CURRENT | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 6.3 | 7.2 | 5.0 | 7.6 (7.570) | 7.6 | no |
| P1-X | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 6.3 | 10.0 | 5.0 | 7.7 (7.710) | 7.7 | no |
| P1-C | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 6.3 | 9.2 | 5.0 | 7.7 (7.670) | 7.7 | no |
| P2+withhold-RAPID | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 6.3 | 7.2 | 5.0 | 7.6 (7.570) | 7.6 | no |
| P3-X | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 10.0 | 7.2 | 5.0 | 7.9 (7.940) | 7.9 | no |
| P3-C | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 6.5 | 7.2 | 5.0 | 7.6 (7.590) | 7.6 | no |
| ALL (X) | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 10.0 | 10.0 | 5.0 | 8.1 (8.080) | 8.1 | no |
| ALL (C) | 10.0 | 9.2 | 9.5 | 10.0 | 5.0 | 6.5 | 9.2 | 5.0 | 7.7 (7.690) | 7.7 | no |

### 7.3 Which fleet size is needed (current rubric, VALIDATED)

| rubric | first fleet size >= 8.0, rollout order, documented evidence | same, with TWDB tier-2 adopted | random orders (60): min / median / max | orders that ever reach 8.0 |
|---|---|---|---|---|
| CURRENT | 156 | 156 | 156 / 156 / 156 | 60/60 |
| P1-X | 156 | 64 | 63 / 156 / 156 | 60/60 |
| P1-C | 156 | 68 | 63 / 156 / 156 | 60/60 |
| P3-X | 63 | 63 | 63 / 78 / 156 | 60/60 |
| P3-C | 156 | 156 | 156 / 156 / 156 | 60/60 |
| ALL (X) | 63 | 63 | 63 / 63 / 105 | 60/60 |
| ALL (C) | 156 | 68 | 63 / 156 / 156 | 60/60 |

With the current rubric the first fleet size at which the displayed score reaches 8.0 is **156 = 25 % of 621**, the 5-point coverage rung, in the rollout order and in all 60 random orders. At 63 or 123 lakes the gap to 8.0 is 28.5 or 23.5 weighted points and **floodDroughtContext cannot close it alone** (its room is 25.5 or 20.5 points); operatorPlan or coverage could:

| fleet | evidence | gap to 8.0 (weighted points of 100) | room in operatorPlan | room in floodDroughtContext | room in coverage | dimension that closes the gap alone |
|---|---|---|---|---|---|---|
| 63 | NOW | 28.5 | 63.0 | 25.5 | 140.0 | operatorPlan, coverage |
| 63 | KNOWN | 16.0 | 54.0 | 22.0 | 140.0 | operatorPlan, floodDroughtContext, coverage |
| 123 | NOW | 23.5 | 63.0 | 20.5 | 140.0 | operatorPlan, coverage |
| 196 | NOW | -4.5 | 57.0 | 21.5 | 100.0 | operatorPlan, floodDroughtContext, coverage |

### 7.4 Sensitivity to which lakes are accepted first (100 random orderings, VALIDATED, documented evidence)

| fleet | rubric | operatorPlan min/med/max | floodDroughtContext min/med/max | uncapped at VALIDATED min/med/max |
|---|---|---|---|---|
| 63 | CURRENT | 3.5 / 4.6 / 6.0 | 4.4 / 5.4 / 6.5 | 7.4 / 7.7 / 7.9 |
| 63 | P1-X | 3.5 / 4.6 / 6.0 | 6.5 / 7.7 / 8.6 | 7.5 / 7.8 / 8.0 |
| 63 | P3-X | 5.6 / 7.3 / 8.3 | 4.4 / 5.4 / 6.5 | 7.7 / 7.9 / 8.1 |
| 63 | P3-C | 3.5 / 4.8 / 6.0 | 4.4 / 5.4 / 6.5 | 7.4 / 7.7 / 7.9 |
| 63 | ALL (X) | 5.6 / 7.3 / 8.3 | 6.5 / 7.7 / 8.6 | 7.8 / 8.0 / 8.3 |
| 63 | ALL (C) | 3.5 / 4.8 / 6.0 | 5.9 / 7.0 / 8.1 | 7.5 / 7.8 / 8.0 |
| 123 | CURRENT | 3.7 / 4.4 / 5.1 | 5.0 / 5.6 / 6.1 | 7.5 / 7.6 / 7.8 |
| 123 | P1-X | 3.7 / 4.4 / 5.1 | 7.4 / 7.9 / 8.5 | 7.6 / 7.8 / 7.9 |
| 123 | P3-X | 6.4 / 7.1 / 7.9 | 5.0 / 5.6 / 6.1 | 7.8 / 7.9 / 8.0 |
| 123 | P3-C | 3.8 / 4.5 / 5.2 | 5.0 / 5.6 / 6.1 | 7.5 / 7.7 / 7.8 |
| 123 | ALL (X) | 6.4 / 7.1 / 7.9 | 7.4 / 7.9 / 8.5 | 7.9 / 8.0 / 8.1 |
| 123 | ALL (C) | 3.8 / 4.5 / 5.2 | 6.7 / 7.3 / 8.0 | 7.6 / 7.7 / 7.9 |

In **none** of 100 random 63-lake or 123-lake fleets does the current rubric reach 8.0 (maxima 7.9 and 7.8). The best-first rollout prefixes are therefore at the favourable end for history, and the conclusion stands.

### 7.5 Margin at the first fleet that gets there

| rubric (196 lakes, VALIDATED) | SUFFICIENT lakes that may drop to NONE before displayed < 8.0 (documented evidence) | ... drop to LIMITED | ... drop to NONE (TWDB adopted) | unrounded uncapped (documented) |
|---|---|---|---|---|
| CURRENT | 6 | 12 | 10 | 8.045 |
| P1-X | 16 | 28 | 20 | 8.165 |
| P3-X | 28 | 47 | 33 | 8.315 |
| ALL (X) | 37 | 63 | 41 | 8.435 |
| ALL (C) | 14 | 24 | 18 | 8.140 |

The 196 table reaches 8.0 at VALIDATED by **0.045**: six SUFFICIENT-history lakes dropping to NONE (or one provider outage affecting a handful of lakes) take it under. P1 and P3 buy margin; nothing buys a date.

### 7.6 Is the target reachable, and when

**Yes in arithmetic, no before the validation clock.** The proof in four lines:

1. The four correctness critical dimensions are not the constraint: the lowest of the four, at any evidence level, is 10.0 on 63 lakes, 9.2 on 196 and 8.6 on 427 (test `test_validation_is_the_only_critical_dimension_that_can_fail_and_it_needs_validated`).
2. P1 and P3 do not touch any critical dimension (tested on 63, 196, 427 at all three levels); P2 touches only `validation`.
3. `validation` takes the values 0, 5, 10 (word or minimum over families), so it is >= 7.5 **only at 10**, which requires every counted family VALIDATED. historicalState is counted unless withheld, and its VALIDATED needs >= 12 months of logged fleet predictions scored once. RAPID, if published, additionally needs a passed criterion.
4. Therefore: **earliest date = first ledger day of the fleet + 365 days.** The ledger's day 0 is 2026-10-13 with five pilots, so 2027-10-13 is reachable only for a five-lake Brain, which displays at most 3.0 (underlying 7.8 at a hypothetical VALIDATED). Every week the fleet starts later moves the date a week. Illustration: first fleet ledger day 2026-11-15 gives PARTIAL evidence 2027-02-13 and VALIDATED 2027-11-15.

**What would be required**, in order: (a) the binding review accepted and a fleet of **at least 156 lakes** in production with history pre-seeded (63 is not enough on evidence in hand: 7.7 to 7.8; it reaches 8.1 only at the CEILING); (b) that fleet logged in the ledger for 12 months, scored once under pre-registered criteria, historical-state criteria passing prospectively (H-A margin was one lake retrospectively); (c) RAPID withheld or a revised H-C passed; (d) overall margin: at 196 the documented evidence sits on the line (8.045), so TWDB adoption (+0.05), the S-B definition decision (+0.18) and a larger accepted fleet (the 427-lake set gives 8.085 on documented evidence) are what make it robust, and P1 form C (+0.09) is the only denominator change I would take; (e) the critical set designated and `requiredDimensions[]` published, otherwise Ops will not enforce the dimension rule at all.

**If the target is read as overall >= 8.0 only,** it is reachable at a hypothetical VALIDATED on 156 or more lakes under the current rubric and never at PARTIAL on documented evidence.

## 8. Exactly what Michael approves (one yes or no each; my recommendation is mine, not binding)

| # | Decision | Effect if yes | Recommendation |
|---|---|---|---|
| A1 | **P1 form C**: floodDroughtContext denominator = lakes where a flood pool exists or cannot be ruled out (UNDETERMINED counted; NOT_APPLICABLE excluded) | flood 5.7 to 7.4 on the 196, underlying +0.1; needs profile field + scorer change | **Yes** (conservative form) |
| A1x | **P1 form X** instead: UNDETERMINED also excluded | flood 5.7 to 8.1, underlying +0.2; depends on NID link coverage | No (choose A1 or A1x, not both) |
| A2 | **P2 claim families**, dimension = minimum over counted families, gate "any counted family NOT_VALIDATED", RAPID counted only while published | no arithmetic change; makes PARTIAL reachable per claim; needs `claims{}` in the validation node, scorer change, definition restated per family | **Yes** |
| A3 | **Withhold RAPID** from publication until a revised H-C passes (amends the PARTIAL definition after the H-C result; to be recorded as such; Swift flag and `rulesVersion` bump) | validation 0 to 5 and cap lifted at the 90-day clock (2027-01-11 pilots / fleet start + 90 d); displayed 5.0 to 7.3 on the 196 at that state; no effect on VALIDATED | Your call: **yes** if you want PARTIAL on its clock; **no** if you want to keep RAPID and spend a ledger period on a revised H-C |
| A4 | **P3 form X** (operatorPlan over lakes where the operator publishes a plan, UNKNOWN excluded) | plan 4.3 to 7.0; 63 lakes then reach 8.0; capture-rate metric | **No** |
| A4c | **P3 form C** (UNKNOWN counted, only "operator read, none published" excluded) | plan 4.3 to 4.4 | **No** (not worth a schema field) |
| A5 | **Averaging** claim families instead of the minimum | validation clears 7.5 at PARTIAL for the historical state | **No** (confirm explicitly) |
| A6 | **Critical set** = sourceAuthority, historyQuality, seasonalBaseline, trendQuality, validation, published as `requiredDimensions[]` | makes the 7.5 floor enforceable; changes no score | Yes (prerequisite, not one of the three mismatches) |

If A1, A2 and A3 are approved and A4 is declined: 196 lakes underlying 6.5 to 6.6 under `NOT_VALIDATED` (displayed 5.0 either way), 7.4 at a PARTIAL-equivalent state and 8.1 at a VALIDATED-equivalent state (hypothetical).

## 9. What was not done, and what implementation would need

Not done (by instruction): no change to the live rubric, scorer, profiles, `/validation`, lifecycle, thresholds, Swift or any deploy; no cloud mutation (RTDB `/scores/lake-brain`, `/validation/lake-brain`, `/brains/lake-brain`, the five pilot profiles and `lakeFleet` were read once, read-only, and the pilot copy is `jobs/lake-brain/readiness/data/pilots_live_2026-10-13.json`).

If any of A1 to A3 is approved, implementation (lead, separate branch): (1) profile fields `floodPoolApplicability` (P1), and the claims block of the validation node (P2); (2) a scorer change in `scoring.py` plus a new `scoreVersion`, with the old version's tests kept, the gate text updated and `SCORING.md` restated; (3) the profile builder deriving `floodPoolApplicability` from `dam.floodControl` and the documented levels; (4) a Swift withhold flag for RAPID and a `rulesVersion` bump (A3 only); (5) restating `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md` per family with the amendment labelled; (6) republishing the rubric JSON only with the scorer change, since the JSON is documentation. Until then `docs/brains/scoring/proposed/` is the only place the text lives.

Dependencies and cautions: the scorer reads every profiled lake (the 200-profile cap was already lifted in the base branch); fleet quality figures beyond the 196 depend on the history backfill actually running (only the four TVA pilots and Hartwell have deep history in the Brain today); the 427 set includes post-hoc envelope rules and stage-only gauges whose error rate is unmeasured.

## 10. Reproduction and verification

```
python3 -m pytest jobs/lake-brain/readiness -q          # 83 tests (all in test_rubric_proposals.py)
python3 jobs/lake-brain/readiness/rubric_proposals.py --tables       # every table in this document
python3 jobs/lake-brain/readiness/rubric_proposals.py --write-drafts # regenerate docs/brains/scoring/proposed/*.json
python3 jobs/lake-brain/readiness/rubric_proposals.py --build-facts <bindings> <plan_flood_evidence.csv> <verified_bindings_v2.csv> <nid_links.csv> <rollout_plan.v1.json>
```

Tests prove: (1) **equality with production** `score_lake` under CURRENT rules (published pilots 3.0 / 6.3, the 196 table, nested fleets at all evidence levels and validation words, 120 random fleets with random health and directory size, an empty fleet); (2) **isolation**: no source under `jobs/` or `scripts/` mentions `scoring/proposed`; with every file open, listdir, scandir and glob recorded, `score_lake` and `score_brains.compute` open only `frozen-scores.json` from the scoring directory and list nothing; `compute` output is byte-identical with and without a copy of `proposed/` present; the scorer source contains no JSON loading; the orchestrator image stages only `frozen-scores.json` from `docs/brains/scoring`; (3) the live rubric file is byte-identical to the base-branch version and the draft files equal what the script generates; (4) every headline number above is asserted from committed inputs; (5) the patches apply cleanly, leave weights at 100 and touch only the intended dimension; (6) the module has no network, subprocess-free logic.

The fact table `jobs/lake-brain/readiness/data/rubric_proposals_lake_facts.csv` (427 rows, 35 KB) holds only derived public facts (capability, history class, plan / flood evidence flags, NID link flags, rollout order); it contains no species, presence or clarity data.
