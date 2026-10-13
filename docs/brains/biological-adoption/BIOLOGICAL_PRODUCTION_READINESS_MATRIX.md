# Biological Brain: production readiness matrix

**Policy (Sector production):** overall Brain score ≥ **8.0 / 10** AND every required/critical dimension ≥ **7.5 / 10**. Engine has **not published** which dimensions are critical (Ops evaluates the critical rule only when Engine names them); the "critical?" column below is **my recommendation for Michael to ratify**, not a published designation.

**Scores:** published **4.0** · implementation-supported **4.6** · research potential + implementation **4.9** (canonical `score_biological`; dimension values below are the published ones unless stated). Rubric `biological-state-score-v1` is unchanged. Hard gates: Biological State NOT_STARTED ≤ 4.0 (lifted by IN_PROGRESS); **no VALIDATED species ≤ 6.0** (binding for everything below).

| Dimension (weight) | Now → impl-supported | Critical? (recommend) | Floor | Evidence now | Current blocker | Next action | Time / human dependency | Ceiling without field validation |
|---|---|---|---|---|---|---|---|---|
| registryCompleteness (10) | 10 → 10 | no | n/a | 27 + 2 = 29 species | none | none | none | 10 |
| assessedCoverage (15) | 9.3 → 9.3 | no | n/a | 27 of 29 assessed | 2 NOT_ASSESSED rows (tilapia generic, grouped suckers) | assess narrowly (blue tilapia) or accept | Michael decision | 10 |
| **knowledgeDepth (20)** | 1.0 → 1.0 | **yes** | 7.5 | median species-v2 = 1.0 over 27 rows (4.0 over the 12 Lake-Brain species) | median driven by 18 minor rows; principal species 3.0-7.0 | adopt proposed rows (median 2.5); see `BIOLOGICAL_KNOWLEDGE_DEPTH_BASIS.md`; more Southeast evidence for principal species | Michael (basis, rows); data partnerships | **≈4.5 (12-species basis) or ≈2.5-3 (27)**: one-study accounts cap at 3-4 per rubric; 7-8 needs multi-source southern evidence for every species |
| **evidenceQuality (10)** | 2.0 → 2.0 | **yes** | 7.5 | all RESEARCH | no REVIEWED/VALIDATED species; no reviewer role | reviewer role; review Tier-A species | Michael + a fisheries reviewer (~3-4 h/species) | **7.0 (all REVIEWED)**: below the 7.5 floor; **only VALIDATED share ≥75% clears it** |
| contradictionsGaps (10) | 6.6 → 6.6 | no | n/a | mean capped contradiction load 0.34 | open contradictions inside profiles (grass carp 16, silver 12, buffalo 8 each …) | resolve in the private bundle with sourced decisions (new `researchVersion`) | research + Michael sign-off | 10 |
| **regionalTransfer (5)** | UNKNOWN (0) | **yes** | 7.5 | per-rule `transferability` exists (every principal rule PARTIAL or UNTESTED) | scorer reads "not published" (hard-coded UNKNOWN) | **ENGINE CONTRACT**: publish a region-transfer fact the scorer may read (platform change; not made here) | Engine/platform + Michael (rubric consequence) | cannot be scored today; honest value for the Southeast is LOW |
| **biologicalStateImpl (15)** | 0 → **4** (IN_PROGRESS) | **yes** | 7.5 | pilot state derived IN_PROGRESS; Hartwell dry run OK | not published; per-lake publication not approved; no live use | publish registry; Intelligence reconciliation; approve per-lake publication → LIVE (8) | Michael approval; Intelligence session | **8 (LIVE)**; 10 needs VALIDATED |
| **biologicalStateValidation (10)** | 0 → 0 | **yes** | 7.5 | 51 frozen identities, 7 predictions, **0 observations** | no field observations; no preregistered criterion | preregister the success criterion; start structured observation | testers, elapsed seasons, Michael (criterion) | 5 (PARTIAL needs real partial validation); **10 requires VALIDATED** |
| productionIntegration (5) | 10 → 10 | yes | 7.5 | Intelligence dependency CONNECTED | none today (but Intelligence consumes no species band) | keep CONNECTED when the band contract is wired | Intelligence reconciliation | 10 |

## What the numbers say
* **Maximum score reachable without field validation: 6.0** (the speciesValidation gate), and in practice ≈ 6.0 only after State LIVE, partial validation and a published regional-transfer fact.
* **Four critical dimensions cannot reach 7.5 without field validation:** evidenceQuality (7.0 ceiling), biologicalStateValidation (5 ceiling), regionalTransfer (unscorable), knowledgeDepth (≈4.5 ceiling). Production readiness for Biological is therefore primarily a **field-validation and elapsed-time** problem, not a coding problem.
* Realistic sequence: publish candidate (4.6) → adopt rows + resolve contradictions (≈5.0) → LIVE + partial validation + regional transfer (≈6.0, gate-capped) → first VALIDATED species lifts the 6.0 gate → broad validation for ≥8.0.

## Gate requirements
| Gate | Cap | What exactly moves it |
|---|---|---|
| biologicalState (NOT_STARTED) | 4.0 | the published registry must report `biologicalState.status` ≥ IN_PROGRESS. Derived by `capability.assess` from valid rules + frozen register + a verifying pilot state. **Requires publishing the candidate bundle (Michael)** |
| speciesValidation (no VALIDATED species) | 6.0 | ≥1 species at `researchMaturity = VALIDATED`. Requires field-validation evidence meeting a preregistered criterion, after independent review; no promotion path exists in code and none will be added by this campaign |
