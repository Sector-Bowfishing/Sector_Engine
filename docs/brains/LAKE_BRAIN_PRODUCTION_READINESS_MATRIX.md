# Lake Brain: production-readiness matrix (policy: Brain score at least 8.0 and every critical dimension at least 7.5)

**All "projected" figures here are PROJECTIONS, not scores.** They run the real, unmodified rubric code over hypothetical facts. Nothing was published, no profile was changed, no rubric or gate was edited, and `/scores/lake-brain` still reads **3.0 / 10**. Lifecycle naming (`CALIBRATION`, `BETA`, `PRODUCTION`) is a separate axis and is not touched.

Written 2026-10-13. Read live (read-only) the same day: `/scores/lake-brain` (`value 3.0`, `uncapped 6.3`, `scoreUpdatedAt 2026-10-13T18:58:18Z`, `lake-brain-score-v1`), `/validation/lake-brain` (`NOT_VALIDATED`), `/brains/lake-brain` (`status CALIBRATION`, `health HEALTHY`, `supportedLakeCount 5`).

## 1. The policy, and what is and is not published

Source: `/Users/mcather/Desktop/Development/Web/Sector-Ops/docs/SECTOR_OPS_PRODUCTION_POLICY.md` (read only). A PRODUCTION Brain's canonical score must be at least **8.0 / 10**; every Engine-designated required or critical dimension must be at least **7.5 / 10**. Ops evaluates the dimension rule **only when the Engine publishes `requiredDimensions[]`**. Checked live: `/control/overview` has no `productionPolicy` and no `requiredDimensions` (keys: `brains, engine, fleet, jobs, schemaVersion, sources, updatedAt, version, workNext`). So **no Lake Brain dimension is designated critical today.** The designation in section 3 is a **PROPOSAL** for Michael, made so the readiness can be read against something.

Naming trap noticed while reading: `/control/overview.brains["lake-brain"].activeModel.status` is `PRODUCTION` (the model line), while `brains["lake-brain"].status` is `CALIBRATION` (the Brain). The Ops guardrail reads the Brain's status. They are different fields and must not be conflated.

## 2. How the score is built (so the arithmetic below can be checked)

`jobs/brain_platform/sector_brain_platform/scoring.py::score_lake`, rubric `docs/brains/scoring/lake-brain-score-v1.json`. Each dimension is rounded to one decimal; uncapped = sum(value x weight) / 100, rounded to one decimal; displayed = min(uncapped, lowest fired gate cap).

| Dimension | Weight | Fact (share of profiled lakes unless stated) | Scale |
|---|---|---|---|
| sourceAuthority | 15 | level source is `DIRECT_OPERATOR_POOL` or `DIRECT_LAKE_GAUGE` | share x 10 |
| operatorPlan | 10 | `guideCurve.available` or an `operatingZoneSource` | share x 10 |
| historyQuality | 15 | `baselineStatus == SUFFICIENT` (at least 5 complete years) | share x 10 |
| seasonalBaseline | 10 | `baselineStatus` in SUFFICIENT, LIMITED | share x 10 |
| trendQuality | 10 | state `kind` is observed (share of published states) | share x 10 |
| floodDroughtContext | 5 | `floodPoolState` is not `UNKNOWN` (share of published states) | share x 10 |
| validation | 15 | `/validation/lake-brain.status` | NOT_VALIDATED **0**, PARTIAL **5**, VALIDATED **10** |
| coverage | 20 | profiled lakes / 621 directory lakes | ladder: under 5 % 1 pt; 5 % 2; 10 % 3; 25 % **5**; 50 % **7**; 75 % **9**; 90 % **10** |

Gates (cap, never add): profiled share under 10 % caps at **3.0**; `NOT_VALIDATED` caps at **5.0**; brain health FAILED or UNKNOWN caps at 2.0. Weights sum to 100.

Two consequences that drive everything below:
- **`validation` PARTIAL scores 5.0 on its dimension. A 7.5 floor on that dimension is met only by VALIDATED (10).** If validation is designated critical, PARTIAL can never be enough for PRODUCTION.
- **The ladder jumps 5, 7, 9, 10.** A coverage value of 7.5 or more needs the 75 % rung (9 points): 466 of 621 lakes.

A scorer limit to know about (code, not rubric; not changed here): `jobs/brain-scores/score_brains.py::fetch_facts` reads at most 200 profiles and states (`sorted(profiled)[:200]`), and `score_lake` takes `n = len(profiles)`. With the 196-lake fleet this is harmless. At 200 or more profiled lakes the coverage evidence would read "200 of 621" (32.2 %, still 5 points), every quality share would be measured on the first 200 lake keys only, and the 50 % rung (311 lakes) could not be reached at all until the cap is lifted. Flag for the lead before any fleet beyond 200 is accepted.

## 3. The matrix

"Now" is the live published figure over **5 profiled pilot lakes**. "196" is the projection if the 196-lake accepted-eligible table (`jobs/lake-brain/data/bindings.proposed.v1.json`) were accepted and all lakes ran, with `NOT_VALIDATED`. "PARTIAL" and "VALIDATED" change only the validation dimension (and lift the 5.0 gate). Method for "196": per lake, `sourceCapability.level` from the table; plan = `guideCurve` role present or both `zoneTop` and `zoneBottom` (84 lakes); flood = `floodPoolBottom` role present (111 lakes); history = research `historyClass` with the four TVA pilots set SUFFICIENT as in the live profiles (180 SUFFICIENT, 6 LIMITED, 10 NONE); every state OBSERVED (the 2026-10-13 probe found 194 of 195 sources within 72 h). Script: `jobs/lake-brain/readiness/project_scores.py` (tests `test_readiness.py`: the what-if arithmetic equals `score_lake` on the real table).

| Dimension | Weight | Criticality (PROPOSAL) | Floor | Now (5 lakes) | 196 lakes | 196 + PARTIAL | 196 + VALIDATED | Gap to 7.5 (196) | Gap to 8.0 (196) |
|---|---|---|---|---|---|---|---|---|---|
| sourceAuthority | 15 | **critical** | 7.5 | 10.0 (5/5) | **10.0** (196/196) | 10.0 | 10.0 | none | none |
| historyQuality | 15 | **critical** | 7.5 | 10.0 (5/5) | **9.2** (180/196) | 9.2 | 9.2 | none | none |
| seasonalBaseline | 10 | **critical** | 7.5 | 10.0 | **9.5** (186/196) | 9.5 | 9.5 | none | none |
| trendQuality | 10 | **critical** | 7.5 | 10.0 (5/5) | **10.0** (assumes 196/196 observed) | 10.0 | 10.0 | none | none |
| validation | 15 | **critical** | 7.5 | 0.0 | 0.0 | 5.0 | **10.0** | 7.5 (NOT), 2.5 (PARTIAL), none (VALIDATED) | 8.0, 3.0, none |
| operatorPlan | 10 | weighted, not critical | (7.5 if made critical) | 10.0 (5/5) | **4.3** (84/196) | 4.3 | 4.3 | **3.2** (need 147 lakes, have 84) | **3.7** (need 157) |
| floodDroughtContext | 5 | weighted, not critical | (7.5 if made critical) | 2.0 (1/5) | **5.7** (111/196) | 5.7 | 5.7 | **1.8** (need 147, have 111) | **2.3** (need 157) |
| coverage | 20 | weighted, not critical | (7.5 if made critical) | 1.0 (5/621 = 0.8 %) | **5.0** (196/621 = 31.6 %, rung 25 %) | 5.0 | 5.0 | **2.5** (needs the 75 % rung: 466 lakes) | **3.0** |
| **Overall, uncapped** | 100 | | 8.0 | 6.3 | **6.5** | **7.3** | **8.0** (8.045) | | |
| **Overall, displayed** | | | 8.0 | **3.0** (coverage gate 3.0, validation gate 5.0) | **5.0** (validation gate) | **7.3** | **8.0** | | |

Arithmetic, 196 lakes (dimension values are the rounded ones the rubric sums):

- NOT_VALIDATED: 15x10.0 + 10x4.3 + 15x9.2 + 10x9.5 + 10x10.0 + 5x5.7 + 15x0 + 20x5 = 150 + 43 + 138 + 95 + 100 + 28.5 + 0 + 100 = 654.5, so uncapped 6.5 (6.545); gate cap 5.0, displayed **5.0**.
- PARTIAL: validation 5 adds 15x5 = 75, so 729.5, uncapped **7.3** (7.295); the 5.0 gate no longer applies; displayed **7.3**. Below 8.0.
- VALIDATED: validation 10 adds 150, so 804.5, uncapped **8.0** (8.045 rounds to 8.0); displayed **8.0**. At the floor, not above it.

Margin of the VALIDATED case, found by re-running the arithmetic with lakes removed: the displayed value falls to **7.9** if **13** SUFFICIENT-history lakes drop to LIMITED or NONE, or **19** plan lakes lose their plan, or **19** states are not observed, or **38** flood-known states become UNKNOWN. That is a thin margin: one provider outage affecting 19 lakes at the moment of scoring would take it under.

Sensitivities (all NOT_VALIDATED gates aside):

| Variation (196 lakes) | PARTIAL | VALIDATED | Note |
|---|---|---|---|
| History rule of 10 complete years instead of 5 (rubric change, not permitted here; 109 of 196 have at least 10 years, 94 have at least 15) | 6.8 | 7.5 | historyQuality falls to 5.6 and would no longer clear 7.5 |
| Tier-2 evidence adopted (TWDB conservation / dead pool for Conroe, Fork, Livingston, Tawakoni; zone for 5 more Texas lakes): plan 93, flood 115 | 7.3 | 8.1 | plan 4.7, flood 5.9 |
| Definition decision: a documented Top of Conservation plus a lower-pool level (Top of Inactive, Bottom of Power) counts as a zone: plan 120 (84 + 36) | 7.5 | 8.2 | NOT evidence; a rubric-semantics call (section 5) |
| All of the above plus every NID flood-control lake documented (flood 137), history 190, baseline 196 (ceiling case) | 7.7 | 8.4 | operatorPlan 6.1, floodDroughtContext 7.0 |

Reading the table:
1. **PARTIAL cannot reach 8.0 on any fleet this evidence supports.** Even the ceiling case is 7.7. Production at 8.0 needs VALIDATED (earliest 2027-10-13, and only with a fleet logged for all twelve months, `LAKE_BRAIN_VALIDATION_READINESS.md`).
2. **VALIDATED reaches 8.0 on the 196 only barely** (8.045). Raising the underlying shares (plan, flood, coverage) buys margin; nothing else does.
3. **Under my proposed designation (section 4), the five critical dimensions all clear 7.5 on the 196 except validation.** The one dimension that blocks the critical test is validation; the other three dimensions that are weak are weighted but not critical.

## 4. The proposed critical designation (PROPOSAL for Michael; not published, not enforced)

| Option | Critical set | Consequence |
|---|---|---|
| **A (recommended)** | validation, sourceAuthority, historyQuality, seasonalBaseline, trendQuality: the dimensions that say whether what the Brain publishes is right | On the 196 fleet all except validation clear 7.5 already. PRODUCTION then reduces to VALIDATED plus overall at least 8.0 plus the three completeness dimensions carrying their weight. |
| B (strict) | all eight dimensions | **Not achievable**, see section 5: floodDroughtContext and coverage cannot reach 7.5 on the 196 fleet under the unmodified rubric, operatorPlan cannot on known evidence. Lake Brain could never be PRODUCTION. |
| C (scoped) | A plus coverage, with a declared scope ("PRODUCTION for the accepted fleet") | Needs a rubric or policy change (a coverage denominator that is not 621). Not available under the unmodified rubric. A decision for Michael; this document does not make it. |

Why operatorPlan, floodDroughtContext and coverage are the "not critical" group in option A: `UNKNOWN` is a legitimate output of this Brain. A low share says how much of the fleet has documented operator levels, a flood pool, or a bound source. It does not say what is published is wrong. Hiding that behind a critical floor would push the Brain to invent plan or flood values. The score still carries them at 35 of 100 points.

## 5. Which dimensions can never reach 7.5, and what real evidence would move them

### 5.1 floodDroughtContext (weight 5): cannot reach 7.5 on the 196 fleet, even with perfect evidence

A flood-pool state is possible only where the operator publishes a flood-pool bottom, which requires the lake to have flood-control storage. NID purposes of the 196: flood control **127**, not flood control 53 (47 + 6 with evidence but not NID-flagged), unknown 16. Documented today: 111. Every lake with a flood-control purpose could at most be documented: 127 + 6 + 4 (flood evidence without an NID flag) = **137 / 196 = 69.9 %, 7.0**. The 7.5 floor needs 147. So the dimension is **capped below 7.5 by the fleet's composition** (TVA mainstem and other run-of-river pools, hydropower-only dams, regulated natural lakes), not by missing work. Of the 26 flood-control lakes still undocumented, 9 are TVA (the TVA API publishes no flood-pool bottom; `UNKNOWN` is the right answer there).
- Real evidence that moves it, in order: USACE flood-pool levels for the 7 undocumented USACE flood-control lakes (Clarks Hill / Thurmond, Eufaula / W.F. George, Jordan NC, Kerr NC and VA, Lewis and Clark, Seminole); TWDB for Conroe, Fork, Livingston, Tawakoni (flood 115); NWPS normal threshold for Herrington and Oconee (tier 3, flood 117). Ceiling with all of them and the 26: 137.
- What cannot move it: a different pool definition, treating `UNKNOWN` as known, or dropping lakes without a flood pool from the denominator (a rubric change, not allowed).
- Or change the fleet: adding flood-control reservoirs raises the share; adding natural lakes lowers it.

### 5.2 coverage (weight 20): cannot reach 7.5 on any bindable set found so far

7.5 needs 75 %: **466 of 621 lakes** with a reviewed source. What exists: strict machine-verified **272**; accepted-eligible **196** (31.6 %, 5 points); the permissive labelled sets: 389 core with v1.1 and `R7h` (62.6 %), **427** research-bound lakes under any rule (68.8 %, 7 points). Even the most permissive set found by the research is 39 lakes short of 466. 149 directory lakes still had no candidate source at all after wave 2 (`no-candidate`; 171 after wave 1). So coverage cannot reach 7.5 on current evidence under any rule, and cannot be reached with strict rules. The next rung that is reachable is **7 points at 50 % = 311 lakes**, which needs 115 more reviewed lakes than the 196 (the 76 held-back strict lakes become eligible when their holds clear: 196 + 76 = 272, 43.8 %, still 5 points; the 311 rung needs about 39 more beyond the entire strict set).
- Real evidence that moves it: new, independently verified source bindings for lakes now unbound (state and regional operators: Duke, Dominion, Alabama Power gauges beyond CWMS, state water agencies, USGS lake gauges not yet found) and resolved holds (58 coordinates, 14 series, 4 provider terms). The scorer 200-profile cap (section 2) must be lifted before 311 can show.

### 5.3 operatorPlan (weight 10): below 7.5 on every known source; not structurally impossible

7.5 needs 147 of 196 lakes with a guide curve or a documented zone (top and bottom); documented today 84. Known additions: TWDB tier 2 adds 4 lakes with neither plan nor flood and supplies a zone-shaped pair (conservation pool, dead pool) for 5 lakes that have a flood level only (93). A **definition decision** (36 lakes have an operator-published Top of Conservation plus a lower-pool level such as Top of Inactive or Bottom of Power but no strict zone bottom) would take it to 120-124. Everything known tops out at **124 / 196 = 63.3 % = 6.3**. Reaching 147 needs 23 more lakes from sources not found yet. Where nothing machine-readable exists: 20 USBR lakes (RISE has no rule-curve parameter), 25 non-federal hydropower lakes (FERC licence curves exist only as PDFs and settlement agreements), most state and local lakes. This is real work, not a ceiling: each source in `LAKE_BRAIN_OPERATOR_PLAN_FLOOD_EVIDENCE.md` is ranked by lakes unlocked.

### 5.4 validation (weight 15): reachable only by VALIDATED

0 now, 5 at PARTIAL, 10 at VALIDATED. The 7.5 floor is met only at 10. Earliest dates and what blocks each are in `LAKE_BRAIN_VALIDATION_READINESS.md`.

### 5.5 The dimensions that are already fine, and what could break them

- **sourceAuthority 10.0** holds by construction (the generated table admits only operator pools and own gauges); it breaks only if a proxy gauge is ever bound as primary.
- **historyQuality 9.2** depends on the research history counts (180 of 196 at five or more complete years). It is also the dimension most exposed to a stricter history rule: at ten years it would be 5.6. The v2 tier ladder already uses 10 and 15 years for publishing `VERY_UNUSUAL`, so a rubric-v2 that follows is plausible. If so, 87 lakes (196 minus 109) sit below the new line.
- **trendQuality 10.0** assumes every published state is OBSERVED at scoring time; it is a share of published states, so a lake that is UNAVAILABLE reduces it.

## 6. Next actions, in order of leverage

| # | Action | Dimension it moves | Owner / blocker |
|---|---|---|---|
| 1 | Binding review (60-row sample, 57 flagged rows) and `accepted_batch.json` | coverage 1.0 to 5.0; removes the 3.0 coverage gate; makes every other 196-lake figure real | Michael (HUMAN REVIEW) |
| 2 | Lift the 200-profile read cap in `score_brains.py` before more than 200 lakes are profiled | coverage evidence honest above 200 | lead (code, not rubric) |
| 3 | Run the history backfill for the accepted fleet (176 SUFFICIENT in research, only the 4 TVA pilots and Hartwell are in the Brain today) | historyQuality, seasonalBaseline | lead; engineering |
| 4 | Resolve the 14 series holds, 58 coordinate holds and 4 provider-terms holds | coverage (+76 strict lakes: 272, 43.8 %) | research / TERMS |
| 5 | Adopt documented plan and flood evidence per `LAKE_BRAIN_OPERATOR_PLAN_FLOOD_EVIDENCE.md` (TWDB first, then CWMS gaps) | operatorPlan, floodDroughtContext | engineering; sources already in hand |
| 6 | Pre-register a revised H-C and, if wanted, withhold RAPID (decision) | validation (PARTIAL route) | Michael (DECISION) |
| 7 | Fleet in the ledger for 12 months, scored once | validation 10 | TIME, earliest 2027-10-13 |
| 8 | Designate critical dimensions and publish `requiredDimensions[]` and `productionPolicy` from the Engine (Ops already reads them when they appear) | policy visibility | Michael (DECISION) / lead |

## 7. Verdict in one paragraph

On the 196 accepted fleet, `NOT_VALIDATED` displays 5.0, PARTIAL would display 7.3, VALIDATED would display 8.0 (8.045, on the floor). The critical dimensions that describe correctness (source, history, baseline, trend) clear 7.5 comfortably; validation clears it only at VALIDATED. Three weighted dimensions stay far from 7.5: coverage (5.0, capped by evidence at 5 to 7), operatorPlan (4.3, ceiling 6.3 on known evidence), floodDroughtContext (5.7, structural ceiling 7.0). They can be left out of the critical set honestly; they cannot be made to pass by the score as written. Production readiness for Lake Brain is a validation-and-evidence problem measured in months, not a score arithmetic problem.
