# Lake Brain: coverage recovery plan beyond the 196 eligible candidates

Status: planning only. Every count was recomputed on 2026-10-13 from the repository tables and the cached research data by
`jobs/lake-brain/bindings/coverage_recovery_plan.py`; no number is carried over from an older document. Every score below is a
**PROJECTION ONLY, conditional on human review** of the lakes in the tranche. Nothing here is REVIEWED, nothing promotes a lifecycle, nothing edits the rubric.

## 1. Read this first

1. **The 196 are the only lakes that are ready for review today.** Of the other 425 directory lakes, 231 have research bindings that are held and 194 have no source.
2. **After the 196, coverage barely moves the score, and padding it hurts.** The rubric `lake-brain-score-v1`, run unmodified, gives 6.5 uncapped at 196 lakes (31.6%). The next coverage-ladder step is 50% (311 lakes) and is worth +2 ladder points (+0.4 of 10); the quality shares of later tranches are lower, so the uncapped score peaks at **6.8** (361 to 380 lakes) and falls to **6.3** if every remaining recoverable lake is added, including the poor matches.
3. **The displayed score is held at 5.0 by the validation gate in every tranche** (`/validation/lake-brain` is NOT_VALIDATED). Coverage cannot lift it; a validation run can. The PARTIAL and VALIDATED columns below are what-ifs, not claims.
4. **Highest value for least effort:** R1 (Task A, 8 lakes, human review only) and R3 (52 strict-evidence lakes whose only blocker is an off-water pin, 34 of them bowfishing tier A). Together +60 lakes, mostly operator-pool sources.
5. **One new adapter/permission unlocking many lakes barely exists.** Duke is the largest single operator (8 lakes, 7 tier A) but only 1 of them has no other blocker; CO-OPS is 14 lakes but each also needs the post-hoc decision and 13 also have no polygon.

## 2. Recomputed counts

The 621 directory lakes partition exactly: **196 eligible + 231 research-bound but held + 194 unbound = 621**.

| Category (priority order mismatch > terms > adapter > coordinate > other evidence gap > no source) | Lakes |
|---|---|
| Eligible candidate (bindings.proposed.v1.json) | 196 |
| History/live mismatch (Task A) | 14 |
| Provider terms: St. Johns River WMD / NH DES | 12 |
| Provider terms: other undocumented operator endpoint | 23 |
| Provider not on the allow-list / no adapter | 34 |
| Coordinate: off water | 66 |
| Coordinate: identity risk | 7 |
| Other evidence gap (post-hoc v1.1 / R7h, flagged, stage-only) | 75 |
| No source (unbound) | 194 |
| **Total** | **621** |

The generator's own primary-reason split of the 231 held (`excluded.json`) is: post-hoc 130, coordinate-flag 58, flagged 19, history-live-mismatch 14, undocumented-provider 9, flagged-wave1 1.

A lake can carry several blockers, so the table above is a partition and the next one counts every blocker (lakes may appear in more than one row):

| Blocker | Lakes |
|---|---|
| post-hoc (wave w2-v1.1, VERIFIED_ENVELOPE R7h, v1.1 tag) | 130 |
| coordinate: off water | 126 |
| coordinate: identity risk | 43 |
| coordinate: no polygon | 22 |
| flagged (VERIFIED_FLAG, drawdown / weak level class) | 73 |
| no source: live candidate failed review rules | 116 |
| no source: no public level data found | 70 |
| no source: known but stale / portal-only / pending | 8 |
| terms: other undocumented endpoint | 23 |
| terms: SJRWMD / NH DES | 12 |
| no adapter / provider not allowed | 34 |
| stage-only | 10 |
| mismatch 14: FIXED / NEEDS HUMAN REVIEW / NO DEFENSIBLE MATCH | 8 / 5 / 1 |

Coordinate flags over the **whole directory** (the 43 identity-risk, 126 off-water and 22 no-polygon lakes) split as follows. Most of them are unbound lakes, so a pin repair alone recovers few:

| Flag | Eligible | Held (research-bound) | Unbound |
|---|---|---|---|
| ok | 196 | 136 | 98 |
| off water (126) | 0 | 72 | 54 |
| identity risk (43) | 0 | 9 | 34 |
| no polygon (22) | 0 | 14 | 8 |

Provider groups (all lakes carrying the blocker, and how many have no other blocker):

| Blocker | Provider: lakes (no other blocker) |
|---|---|
| terms SJRWMD / NH DES | sjrwmd 6 (3), nhdes 6 (1) |
| terms undocumented | duke 8 (1), srp 4 (0), cnppid 2 (0), nipsco, eccc, mncsg, nppd, njwsa (1), utahlake, aep, wps-hydro (1), alliant: 1 each |
| adapter / allow-list | coops 14 (0), usgs-d 12 (0), usbr-pnhm 4 (0), cdec 2 (0), cwms-nwdp 1 (0), nwrfc 1 (0) |

Unbound lakes by the research's own class: live candidate failed the review rules 119, no public level data found 70, source exists but not live / stale 3, portal / PDF / login only 2 (plus 3 whose wave-1 reason was "pending", folded into "known source": 8 in the blocker table).

The most common blocker combinations (the full list is in `coverage_recovery_plan.json`, `counts.blockerSignatures`): unbound-failed-review alone 57; off-water alone 52; off-water plus unbound-failed-review 40; flagged plus post-hoc 40; unbound-no-data alone 36; post-hoc alone 15; adapter plus post-hoc 13; adapter plus no polygon plus post-hoc 13; flagged alone 13; mismatch-FIXED alone 8.

## 3. Ranking method

Each recovery opportunity pulls a named set of blockers; the lakes it recovers "on its own" are those whose **every** blocker is in that set. Opportunities are ranked lexicographically, in the order the task gave:

1. **Confidence** (H, M, L). H: the evidence is binding-review-v1 VERIFIED and the blocker is not evidence. M: partly evidenced, or the rule was written after the failures (v1.1 / R7h). L: evidence or permission is absent, or a wrong match is possible.
2. **Effort** (S, M, L). S: a decision or data edit by the lead. M: a script, a pin repair or one adapter. L: a new provider adapter plus review plus an outside party.
3. **Bowfishing value.** The directory has **no popularity or species-presence field**. The proxy is the research heuristic in `binding2/profile_unbound.py`, applied to all 621 lakes: size class (0 to 4) + state bowfishing prevalence (1 to 3) + regulated pool (+1) + warm-water lake (+1); tier A is 8 or more, B is 6 or 7. It encodes judgement, not data (it only ordered scouting effort); here it orders opportunities by their number of tier-A lakes and never gates anything. It reproduces the research's 274 stored values exactly (unit-tested).
4. **Lakes recovered** on its own.
5. **Reuse**: the most lakes behind one provider or operator.

An opportunity that recovers no lake on its own is ranked last (R5). Confidence and effort are judgement fields set in `OPPORTUNITIES` with the reason beside them; if you disagree with one, change it there and rerun.

## 4. Ranked recovery opportunities

| Rank | Id | Opportunity | Lakes alone | Tier A / B / C | Conf | Effort | Reuse |
|---|---|---|---|---|---|---|---|
| 1 | R1 | Mismatch-14 FIXED lakes (Task A) | 8 | 3 / 5 / 0 | H | S | 6 |
| 2 | R3 | Coordinate: off-water pins whose evidence is strict (only blocker) | 52 | 34 / 15 / 3 | H | M | 22 |
| 3 | R8 | Post-hoc v1.1 / R7h rows with no other blocker | 15 | 9 / 4 / 2 | M | S | 8 |
| 4 | R2 | Mismatch-14 NEEDS-REVIEW lakes (Canyon, Detroit, Jackson, Rend, Taneycomo) | 5 | 3 / 2 / 0 | M | S | 3 |
| 5 | R9 | New provider adapters on the post-hoc rows (CO-OPS, USGS-d, CDEC, USBR PN, NWRFC, CWMS-NWDP) | 28 | 14 / 10 / 4 | M | L | 8 |
| 6 | R10 | Flagged single-origin rows (drawdown / weak level class) | 68 | 26 / 32 / 10 | L | M | 27 |
| 7 | R4 | Coordinate: identity-risk lakes whose evidence is strict (only blocker) | 6 | 3 / 2 / 1 | L | M | 2 |
| 8 | R6 | Provider terms: St. Johns River WMD and NH DES | 4 | 3 / 1 / 0 | L | M | 3 |
| 9 | R12 | Unbound lakes with a known but stale / portal-only / pending source | 5 | 1 / 3 / 1 | L | M | 1 |
| 10 | R11 | Stage-only lakes | 22 | 14 / 6 / 2 | L | L | 13 |
| 11 | R13 | Unbound lakes whose live candidate failed the review rules | 57 | 3 / 26 / 28 | L | L | 6 |
| 12 | R7 | Provider terms: other undocumented operator endpoints (Duke, SRP, CNPPID, ...) | 3 | 1 / 2 / 0 | L | L | 1 |
| 13 | R14 | Unbound lakes with no public level data found | 36 | 0 / 12 / 24 | L | L | 10 |
| 14 | R5 | Coordinate: no polygon, strict evidence, only blocker | 0 | 0 / 0 / 0 | M | M | 0 |

"Lakes alone" counts only lakes whose entire blocker set is inside the opportunity. Lakes that need two opportunities (for example off-water plus post-hoc, 3 lakes; adapter plus no polygon plus post-hoc, 13) join the later of the two in the cumulative table below, so the cumulative additions differ from the "alone" column.

## 5. What each tranche is waiting for

| Id | Blocker type | Exact human / terms / decision required |
|---|---|---|
| R1 | HUMAN REVIEW | Michael reviews the 8 newly recovered MACHINE_VERIFIED candidates in `jobs/lake-brain/data/bindings.proposed.v1.recovered.json` (Blue Mesa, Buffalo Bill with its RISE 152 to 146 correction, Glendo, Jordanelle, Koocanusa, Navajo, Pineview, Shelbyville). Then remove the accepted ids from `held_lakes.SERIES_MISMATCH` and `build_bindings_table.HISTORY_LIVE_MISMATCH` and regenerate with `--include-recovered`. See `LAKE_BRAIN_MISMATCH14_DISPOSITION.md`. |
| R3 | HUMAN REVIEW + GEOMETRY | A pin repair to the lake polygon for 52 lakes (a polygon exists for every off-water lake; confidence HIGH for 32 and MEDIUM for 20) by the geometry / coordinates thread, then Michael's sign-off of the repaired coordinates. The binding evidence does not change. Changing a directory coordinate touches the customer directory, so it is a lead action. |
| R8 | DECISION | Whether the 15 binding-review-v1.1 / R7h promotions (rules written after wave-1 failures; the R7h error rate was never measured) may enter review as a separate, clearly labelled list. This is a decision about the rule's standing, not new evidence. |
| R2 | HUMAN REVIEW / DECISION | Canyon and Jackson: accept that the Access2Water tsid is the CDA series name, or log A2W for 20 days. Detroit: accept a day-key-aligned comparison as a new pre-registered criteria version. Taneycomo: supply the FERC P-2221 operating range. Rend: decide on the unexplained 0.55 ft series offset. |
| R9 | DECISION + CODE | The R8 decision AND a Swift adapter per provider. CO-OPS is 14 rows (13 of them also have no polygon), USGS daily-value rows 12, USBR PN 4, CDEC 2, NWRFC 1, CWMS-NWDP 1 (the last is a CWMS office label and probably needs only an allow-list entry, not an adapter). |
| R10 | EXTERNAL SOURCE | An independent second source per lake to corroborate the flagged single-origin row, or Michael's waiver of the R7 "flag" class. 68 lakes alone; 27 USGS, 12 RISE, 10 NWPS, 9 A2W, 8 CWMS, 2 TWDB. |
| R4 | HUMAN REVIEW | A per-lake identity decision for 6 lakes (Buckhorn Lake KY, Eagle Lake MS, Hiwassee Lake NC, Lake Tschida ND, Swanson Reservoir NE, East Lynn Lake WV): is the directory pin the lake the gauge belongs to? |
| R6 | TERMS | Written confirmation of acceptable use of the SJRWMD and NH DES public endpoints (or a supported feed), then one adapter per provider. 4 lakes alone (SJRWMD 3, NH DES 1), 12 with the post-hoc decision. |
| R12 | EXTERNAL SOURCE | Per lake: a live feed for the stale source, a machine-readable endpoint for the portal-only source, or the pending corroboration / operator full-pool figure. |
| R11 | EXTERNAL SOURCE | A documented gauge datum (USGS site altitude or an operator datum record) that turns stage into elevation. Never a fitted offset. |
| R13 | EXTERNAL SOURCE | A different candidate series per lake, or a decision on which failed review rule is waivable. Each failure was a real check (datum, freshness, identity, plausibility); recovering these would be padding with poor matches. |
| R7 | TERMS | Operator permission and an adapter per endpoint: Duke (8 lakes, 7 tier A, 1 with no other blocker), SRP 4, CNPPID 2, and 9 single-lake operators. Each needs its own agreement; reuse is low except Duke. |
| R14 | EXTERNAL SOURCE | A new public data source or a state / local gauge; the research logged per-lake dead ends (no gauge, discontinued, proxy only). |
| R5 | EXTERNAL SOURCE | A polygon source accepted by the geometry contract for the 22 no-polygon lakes (14 research-bound, 8 unbound); all 22 need another lever as well, so none is recovered alone. |

## 6. Coverage-ladder effect on the unmodified rubric (PROJECTION ONLY)

Method: the production evaluator `sector_brain_platform.scoring.score_lake` (rubric `lake-brain-score-v1`, unmodified) is run on synthetic facts with exactly round(share x N) profiles satisfying each predicate, the method of the research scorer (`research_score.py`). The per-lake quality inputs are, for the 196 eligible and the 8 FIXED lakes, the generated table's own fields (capability, `historyClass`, strict plan and flood evidence); for the other held lakes the research classification (re-implemented here and checked: it reproduces the research tier T1 exactly, 273 lakes, plan 0.44, flood 0.575, history 0.934, baseline 0.989). Unbound lakes get **no** plan, flood or history credit (unknown stays unknown), so the late tranches are a floor, not an estimate. `obs` is 1.0 for every profiled lake (each publishes an observed level).

The first row reproduces the published state (5 reviewed pilot lakes: displayed 3.0 by the coverage gate, uncapped 4.3).

| Cumulative step (ranked order) | Added | Profiled | Coverage | Ladder pts | plan | flood | hist | Uncapped | Displayed (NOT_VALIDATED) | PARTIAL what-if | VALIDATED what-if |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Today: 5 reviewed pilot lakes | 5 | 5 | 0.8% | 1 | 1.0 | 0.2 | 0.2 | 4.3 | 3.0 | 3.0 | 3.0 |
| T0 all 196 eligible reviewed | 196 | 196 | 31.6% | 5 | 0.429 | 0.566 | 0.898 | 6.5 | 5.0 | 7.2 | 8.0 |
| + R1 Mismatch-14 FIXED | 8 | 204 | 32.9% | 5 | 0.426 | 0.578 | 0.902 | 6.5 | 5.0 | 7.2 | 8.0 |
| + R3 off-water pins | 52 | 256 | 41.2% | 5 | 0.438 | 0.586 | 0.91 | 6.5 | 5.0 | 7.3 | 8.1 |
| + R8 post-hoc, no other blocker | 18 | 274 | 44.1% | 5 | 0.409 | 0.547 | 0.916 | 6.5 | 5.0 | 7.3 | 8.0 |
| + R2 Mismatch-14 NEEDS-REVIEW | 5 | 279 | 44.9% | 5 | 0.409 | 0.552 | 0.918 | 6.5 | 5.0 | 7.3 | 8.0 |
| + R9 new adapters on post-hoc rows | 15 | 294 | 47.3% | 5 | 0.388 | 0.524 | 0.918 | 6.5 | 5.0 | 7.2 | 8.0 |
| + R10 flagged single-origin rows | 67 | 361 | 58.1% | 7 | 0.335 | 0.457 | 0.909 | **6.8** | 5.0 | 7.5 | 8.3 |
| + R4 identity-risk lakes | 7 | 368 | 59.3% | 7 | 0.34 | 0.457 | 0.908 | 6.8 | 5.0 | 7.5 | 8.3 |
| + R6 SJRWMD / NH DES | 12 | 380 | 61.2% | 7 | 0.329 | 0.442 | 0.911 | 6.8 | 5.0 | 7.5 | 8.3 |
| + R12 known-source unbound | 7 | 387 | 62.3% | 7 | 0.323 | 0.434 | 0.894 | 6.7 | 5.0 | 7.5 | 8.2 |
| + R11 stage-only | 10 | 397 | 63.9% | 7 | 0.315 | 0.423 | 0.874 | 6.6 | 5.0 | 7.4 | 8.1 |
| + R13 unbound, failed review rules | 115 | 512 | 82.4% | 9 | 0.244 | 0.328 | 0.678 | 6.4 | 5.0 | 7.2 | 7.9 |
| + R7 other undocumented endpoints | 22 | 534 | 86.0% | 9 | 0.234 | 0.315 | 0.663 | 6.4 | 5.0 | 7.1 | 7.9 |
| + R14 unbound, no data | 64 | 598 | 96.3% | 10 | 0.209 | 0.281 | 0.592 | 6.4 | 5.0 | 7.1 | 7.9 |
| + R5 no polygon | 22 | 620 | 99.8% | 10 | 0.202 | 0.271 | 0.594 | 6.3 | 5.0 | 7.1 | 7.8 |

Reading it:

* **Coverage gate.** The 3.0 cap lifts at 10% (63 profiled lakes). The 196 are well past it.
* **Ladder.** 5 points from 25% (156 lakes) to 49.9% (310); 7 points from 50% (311); 9 from 75% (466); 10 from 90% (559). Between 196 and 310 lakes the ladder does not move, so R1, R3, R8, R2 and R9 add lakes (and bowfishing coverage) but no ladder points. The first ladder gain is inside R10, once the cumulative profile passes 311.
* **Quality dilution.** Plan evidence falls from 0.43 to 0.20 and flood-pool evidence from 0.57 to 0.27 as weaker lakes are added, which is why the uncapped score tops out at 6.8 and ends at 6.3. Adding a lake with no operator plan or history costs more in the quality dimensions than the ladder gives back.
* **Validation, not coverage, is the displayed-score blocker after 196 lakes.** The displayed value is 5.0 in every row. This plan does not claim PARTIAL or VALIDATED.
* The bowfishing view is different from the score view: R3 and R8 are the tranches with the most tier-A lakes per unit of effort even though they add no ladder points.

## 7. Recommended order and what not to do

1. Review the 196 and R1's 8 now; they are strict binding-review-v1 rows.
2. Start R3 (pin repair) in parallel: it is the largest high-confidence block and needs no new source.
3. Take the R8 / R2 decisions as one sitting: R8 is a rule-standing decision, R2 five single-gap lakes.
4. Do not start R9, R7, R6 adapters before the R8 decision and the terms answers; each is code plus an outside party for 4 to 28 lakes.
5. Do not recover R13 or R14 lakes by relaxing a rule. Both lower the uncapped score and the 119 "failed review rules" lakes failed real checks.

## 8. Limits

* Confidence, effort and the bowfishing proxy are judgement fields, stated above and editable in the script; the recovery sets and counts are not judgement.
* The projection treats a tranche as reviewed in full; in practice some lakes in each tranche will fail review, and a lake that fails is simply not added.
* Research-quality inputs for the non-table lakes are the research evidence (plan and flood columns exist only for lakes the plan thread verified); lakes that entered in wave 2 receive no plan or flood credit unless verified.
* No account is taken of lakes that could be re-bound to a better source than the one the research chose.

## 9. Reproduce

```
python3 jobs/lake-brain/bindings/coverage_recovery_plan.py [--check]   # writes jobs/lake-brain/data/coverage_recovery_plan.json
python3 -m pytest jobs/lake-brain/bindings -q                           # 66 tests, 20 of them for this plan
```

Inputs and their sha256 are recorded in the output. It needs the research checkout and `Sector_Research_Data/lake-brain` (the same inputs as `build_bindings_table.py`) plus the committed tables.
