# Biological Brain: decisions needed from Michael

Nothing below has been applied. Customer behaviour, labels, policy, production and the live Brain RTDB are unchanged. Unrelated implementation is not waiting on these.

## 00. Where things stand (2026-10-14)
Rule set `2026-10-14.1-rules`: 61 rules, 47 usable and active, 11 DRAFT, 3 retired by supersession; 50 frozen identities; 7 predictions; 0 observations. Candidate bundle `2026-10-14.3` passes the 14-point audit (`tools/audit_bundle.py`). Canonical rescore after every change: **published 4.0, implementation-supported 4.6, research potential 4.0 (capped; 4.3 uncapped), research + implementation 4.9, all unchanged by this cycle.** Nothing further can move the score without an approval below, a reviewer, or field data.
**What is waiting on you, in order of leverage:** (1) approve publishing the candidate (4.0 → 4.6); (2) set the knowledgeDepth basis and the unassessed rows (→ up to 4.9); (3) approve a reviewer role; (4) tell me how many testers can log trips at which lakes, and preregister the success criterion (`BIOLOGICAL_VALIDATION_FLEET_DESIGN.md`).

## 0. Corrected numbers
| | Score | |
|---|---:|---|
| **Published (canonical, live)** | **4.0** | my earlier "3.46" omitted the Intelligence-connection dimension (+0.5) |
| **Implementation-supported** | **4.6** | candidate bundle `2026-10-13.1`: Biological State derived `IN_PROGRESS` from verified capability |
| Research potential (proposed species rows) | 4.0 capped (4.3 uncapped) | hidden by the State gate until State exists |
| Research potential + implementation | 4.9 | |

Next steps up: contradictions resolved in the bundle → ≈5.0; State LIVE + partial validation + a regional-transfer fact → ≈6.0 (cap 6.0 until a species is VALIDATED); ≥1 VALIDATED species lifts the 6.0 cap.

## 1. Production-table corrections (`SpeciesDatabase.swift`; customer-facing)
Approve / reject each. Detail, evidence and confidence: `BIOLOGICAL_ADOPTION_RECONCILIATION.md`. **Exact diffs, verified to apply cleanly and not applied:** `proposed/SpeciesDatabase.approve-candidates.patch` (wording for smallmouth/silver/bighead/grass carp, catfish 70/77/80 F, and the one-line `SpawnFactor` sentence that otherwise still says "staging in warm backwaters") and `proposed/SpeciesDatabase.hold-pending-evidence.patch` (longnose, bowfin window, spotted gar). Targeted research this cycle: longnose gar 64-70 F is supported by several agency compilations but no modern southern primary study, and **nothing supports 22/25 C**; bowfin's February start is supported for coastal Louisiana only and **no temperature** change is justified.
| # | Change | My recommendation |
|---|---|---|
| A2 | smallmouth buffalo: drop "submerged vegetation"; use tailrace / creek-mouth / backwater wording | **Approve** (unsupported claim) |
| A3 | silver carp habitat wording → river mouths, tributary approaches, tailwater edges, backwaters when high | **Approve**; also treat TVA silver-carp spawn timing as untested |
| A5 | grass carp habitat → vegetation + tributary mouths from ~60 F (drop ">70 F slow backwaters") | **Approve** |
| A4 | bighead carp wording → same as silver or remove | Approve (low priority) |
| A7 | channel catfish `70/77/80` F | Approve (no customer effect: never headlines) |
| A1 | longnose gar `64/67/77` F | Hold: agency compilations support ~17-21 C and nothing supports 22/25 C, but there is **no modern southern primary source** |
| A6 | bowfin south window Feb-May (temperature unchanged) | Hold: supported for Louisiana only (Davidson 1991 abstract); no other southern timing study |
| A8 | spotted gar `68/75/86` F | Hold: compilations only |

## 2. First LIVE species set
Criteria: bowfishing importance + rule evidence + Intelligence usefulness + presence on the pilot lake (**presence is the Lake Brain's private data; check it before any species goes LIVE on a lake**). **No species is LIVE today; this is the set to take LIVE first once State is approved.**
| Tier | Species | Usable rules (draft) | Note |
|---|---|---:|---|
| **A** | common carp | 11 (0) | richest evidence; summer-night position deliberately UNKNOWN |
| **A** | spotted gar | 7 (1; 3 older versions retired) | night movement outside spring, shallow vegetation, backwaters |
| **A** | silver carp | 8 (1) | flow-driven; spawn untested on TVA pools |
| **A** | longnose gar | 3 (1) | tailwater spring staging only |
| B | alligator gar | 5 (1) | strong flood-spawn evidence; confirm presence first |
| B | grass carp | 7 (1) | good rules; confirm presence before use |
| C | bighead carp | 2 (0) | evidence mostly pooled with silver carp |
| C | smallmouth buffalo | 1 (3) | most rules DRAFT |
| C | bigmouth buffalo | 3 (3) | all direct data northern; spawn temperature unverified |
Recommended first LIVE set: **common carp, spotted gar, silver carp, longnose gar**, subject to presence on the specific lake.

## 3. Previously unassessed species (policy `policyNotAssessed` and the Lake Brain's 12-species presence list are **unchanged**)
Current policy: the 8 below sit outside the Lake Brain's 12 assessed species, so Intelligence guardrails treat them as not assessed (fail closed on the unmerged `feat/intel-guardrails-5a` branch). They have rows in the Biological bundle (some all-zero), which is a separate "knowledge" row, not presence or policy.
| Species | Evidence depth (proposed row) | Bowfishing importance | Recommended action | Score effect | Risk |
|---|---|---|---|---|---|
| Bowfin | thin, one northern harbour (2.0) | production tier 1 | assess later; needs southern telemetry | median only | low |
| Freshwater drum | moderate-thin (3.0) | tier 3 | assess later | median | low |
| Gizzard shad | compilation (2.5) | tier 1 as prey/fish | keep not assessed as a target; value is as a food-web signal | median | low |
| Channel catfish | one thesis (2.0) | tier 1 but not shootable by default | **keep** not assessed (legality varies by state) | median | **legal/conservation** |
| Paddlefish | moderate (3.0) | tier 3, protected | **keep** not assessed | median | **conservation** |
| American shad | thin (2.0) | tier 3, managed gamefish | keep | median | conservation |
| Striped mullet | thin (2.0) | tier 3 | keep (not a reservoir fish) | median | low |
| Tilapia | see §4 | tier 1, AZ/CA/FL/NV/NC/TX only | see §4 | median | taxonomy/product |
Adopting all proposed rows moves the median 1.0 → 2.5 (+0.3 on the brain score once the State gate is lifted). The seven zero rows (gizzard shad, golden/silver/river redhorse, blue sucker, American shad, goldfish) are `ASSESSED` today with empty knowledge: **assess narrowly or mark NOT_ASSESSED**; leaving them understates coverage and the median.

## 4. Tilapia split
Recommendation: **split internally, change nothing customer-facing.** Add a species row `blue_tilapia` (*Oreochromis aureus*) carrying the existing customer label "Tilapia" through `appKeys`; keep `tilapia_unresolved` as a NOT_ASSESSED alias. Evidence supports only blue tilapia: cold-lethal ~8-9.5 C; nests on shallow flats above ~20 C; established in AZ, CA, FL, NV, NC, TX and only reported in AL and GA (so presence on any pilot lake is unconfirmed). Proposed row ≈2.5. TAFS citation verified (Henson, Aday & Rice 2018, 147(2):278-286, doi 10.1002/tafs.10023). Do not score the generic row.

## 5. Biological State on Guntersville
The pilot runs on live inputs (read-only) and is derived `IN_PROGRESS`: 9 species have rules (45 usable, 11 draft, all frozen), 5 predictions logged, 6 of 10 present species evaluable by the presence policy. Today's output is mostly honest UNKNOWNs (it is mid-October, falling stage, moderate clarity, and most rules cover rising-water/spring states). **Recommend:** (1) approve uploading the candidate bundle to the private bucket and publishing the registry change (IN_PROGRESS, no per-lake path); (2) keep per-lake publication (`/lakes/{k}/states/biology`) off until Intelligence has reconciled bands; (3) decide the presence relevance policy (which states count: default established / reported / stocked / inRangeUnconfirmed).

## 6. `knowledgeDepth` weighting
Today: median over all 27 assessed rows = **1.0**, dominated by minor fish. Option: median over the **Lake Brain's 12 assessed species** = **4.0** (4.0 with the proposed rows too). That alone is +0.6 on the score and is a **rubric change, not new evidence**. Recommendation: adopt the 12-species basis (it matches what Intelligence can actually use) **and publish it as scoreVersion v2 with the history re-based**, rather than quietly moving the number. I did not change the rubric.

## 7. Reviewer role
Nothing can reach REVIEWED, so evidenceQuality and the 6.0 cap are frozen. Recommend a minimal process: a second person (not the rule author), ideally one fisheries professional, checks each rule's evidence trace, stream independence and transfer tag, and signs `review:{reviewer,date}` (the validator already requires this for APPROVED); a species becomes REVIEWED when ≥80% of its usable rules are APPROVED. Rough effort: 3-4 hours per species for the four Tier-A species first.

## 8. Real product / policy decisions
1. Which presence states are relevant (§5). 2. Registered presence discrepancies (DISC-001..003; details in the private bundle): keep the shipping app's presence or follow the canonical research state. 3. Whether silver carp spawn-run messaging should appear on TVA pools at all. 4. The VALIDATED success criterion (hit rate vs baseline, minimum independent trips; the code stops at "30 trips is a sample, not a verdict"). 5. How Sector field observations will be collected (schema is ready; app/Ops work is out of scope here). 6. Data partnerships (TWRA/ADCNR/TVA survey data) for the biggest evidence gap, Southeast reservoir night/summer/winter position.
