# Bowfisher knowledge adoption: from movement cards to the Biological Brain (staged, not published)

The freshwater movement sweep found the fish information. This pass **taught it to the Brain** with deterministic tooling (`tools/adopt_cards.py`, `tools/movement_cards.py`, `tools/review_plain.py`), without another research campaign. Nothing here is published, deployed or merged; the canonical Biological score is unchanged (4.6).

## What was done
1. **Encoded 25 movement cards** into the existing species-v2 domains (whole points, provenance kept, general behaviour and regional confidence stored separately). A candidate bundle `2026-10-14.6` is staged locally; it is not uploaded.
2. **Verified sources** (targeted, only for sources that could enter the Brain): 182 source-claims checked by nine parallel readers: READ-FULL 50, READ-ABSTRACT 31, partial/not supported 65 (many support the topic but not the extra detail claimed), unreachable 36.
3. **Processed all 158 rule candidates**: accept as draft rule 49, merge with an existing rule 32, reject for weak evidence 35, reject for no product value 27, review required 15. Of the 49 accepted, 41 became RECONCILED (a counting source was actually read) and 8 stay DRAFT; 37 belong to registered species and 12 to proposed species that are not in the registry (staged separately, never loaded).
4. **Practical source standard** applied to species knowledge: one inspected credible source supports a basic behaviour up to 6, two independent up to 8; anecdotal and unread sources earn nothing; regional confidence never lowers a general behaviour. The private standard document is **not** edited; the amendment is queued (D7).
5. **Target set** (`target_set.py`): 8 targets, 5 secondary, the rest knowledge-only. No row is removed or renamed.
6. **Bowfisher outlook** (`movement_outlook.py`) and **evaluated view v2** for Sector Intelligence; **target readiness** raw counts for a scorer.
7. **Five pilot lakes** evaluated internally (shadow, GET-only inputs, 12 new internal predictions for target/secondary species; nothing customer-facing).
8. **Rubric v2 proposal** on an isolated scorer branch (not wired).

## Species-v2 before and after
| Fish | Role | Species-v2 before | Species-v2 after | Change | Bowfisher Knowledge | Why the remaining gap |
|---|---|---|---|---|---|---|
| Common carp | target | 6.85 | **7.15** | +0.30 | 7.5 | no inspected source behind the claim (-1.2); one inspected source (cap 6) (-0.1); two-source cap (8) (-0.1) |
| Grass carp | target | 5.35 | **6.20** | +0.85 | 6.2 | two-source cap (8) (-0.1) |
| Spotted gar | target | 4.35 | **5.80** | +1.45 | 6.2 | two-source cap (8) (-0.1) |
| Silver carp | target | 4.50 | **5.65** | +1.15 | 6.0 | one inspected source (cap 6) (-0.1) |
| Alligator gar | knowledge only | 5.00 | **5.55** | +0.55 | 6.3 | no inspected source behind the claim (-1.5) |
| Longnose gar | target | 4.55 | **5.25** | +0.70 | 5.7 | no inspected source behind the claim (-0.4); two-source cap (8) (-0.1) |
| American shad | knowledge only | 0.00 | **5.20** | +5.20 | 6.0 | food/feeding domain not researched (10% of species-v2) (-1.0) |
| Northern snakehead | secondary | 1.90 | **5.15** | +3.25 | 6.2 | food/feeding domain not researched (10% of species-v2) (-1.0); no inspected source behind the claim (-0.2) |
| Bowfin | target | 1.30 | **4.75** | +3.45 | 5.8 | food/feeding domain not researched (10% of species-v2) (-1.0); two-source cap (8) (-0.2) |
| Smallmouth buffalo | target | 3.60 | **4.75** | +1.15 | 5.0 | no inspected source behind the claim (-0.4) |
| Bigmouth buffalo | target | 3.25 | **4.55** | +1.30 | 5.9 | no inspected source behind the claim (-1.7); one inspected source (cap 6) (-0.1); two-source cap (8) (-0.1) |
| Freshwater drum | knowledge only | 0.35 | **4.50** | +4.15 | 5.2 | food/feeding domain not researched (10% of species-v2) (-1.0) |
| Paddlefish | knowledge only | 1.60 | **4.30** | +2.70 | 5.2 | food/feeding domain not researched (10% of species-v2) (-1.0); no inspected source behind the claim (-0.2) |
| Shorthead redhorse | knowledge only | 0.20 | **4.00** | +3.80 | 4.9 | food/feeding domain not researched (10% of species-v2) (-1.0) |
| Channel catfish | knowledge only | 0.15 | **3.90** | +3.75 | 4.8 | food/feeding domain not researched (10% of species-v2) (-1.0); no inspected source behind the claim (-0.2); two-source cap (8) (-0.1) |
| Bighead carp | secondary | 3.15 | **3.80** | +0.65 | 4.1 | two-source cap (8) (-0.1) |
| Blue sucker | knowledge only | 0.00 | **3.65** | +3.65 | 4.2 | food/feeding domain not researched (10% of species-v2) (-1.0) |
| Gizzard shad | knowledge only | 0.00 | **3.50** | +3.50 | 5.5 | no inspected source behind the claim (-1.2); food/feeding domain not researched (10% of species-v2) (-1.0) |
| Goldfish | knowledge only | 0.00 | **3.45** | +3.45 | 5.2 | food/feeding domain not researched (10% of species-v2) (-1.0); no inspected source behind the claim (-0.6); one inspected source (cap 6) (-0.1) |
| Black carp | knowledge only | 0.95 | **3.15** | +2.20 | 3.2 | - |
| Shortnose gar | knowledge only | 2.05 | **2.80** | +0.75 | 3.3 | no inspected source behind the claim (-0.2) |
| Silver redhorse | knowledge only | 0.00 | **2.80** | +2.80 | 3.6 | food/feeding domain not researched (10% of species-v2) (-1.0); two-source cap (8) (-0.1) |
| Black buffalo | knowledge only | 0.85 | **2.25** | +1.40 | 3.0 | no inspected source behind the claim (-0.3) |
| Golden redhorse | knowledge only | 0.00 | **2.05** | +2.05 | 3.5 | food/feeding domain not researched (10% of species-v2) (-1.0); no inspected source behind the claim (-0.7) |
| River redhorse | knowledge only | 0.00 | **1.20** | +1.20 | 2.8 | no inspected source behind the claim (-1.2); food/feeding domain not researched (10% of species-v2) (-1.0) |

## Candidate disposition by fish
| Fish | accept as draft | merge | reject weak | reject no value | review required |
|---|---|---|---|---|---|
| Alligator gar | 1 | 4 | 0 | 0 | 1 |
| American shad | 0 | 0 | 0 | 5 | 0 |
| Bighead carp | 1 | 2 | 2 | 0 | 1 |
| Bigmouth buffalo | 3 | 2 | 1 | 0 | 0 |
| Black buffalo | 0 | 0 | 0 | 0 | 3 |
| Black carp | 0 | 0 | 2 | 1 | 1 |
| Blue sucker | 2 | 0 | 0 | 1 | 1 |
| Blue Tilapia | 2 | 0 | 1 | 1 | 1 |
| Bowfin | 4 | 1 | 0 | 0 | 2 |
| Channel catfish | 0 | 0 | 0 | 5 | 0 |
| Common carp | 1 | 5 | 1 | 0 | 0 |
| Freshwater drum | 4 | 0 | 2 | 0 | 0 |
| Gizzard shad | 1 | 0 | 1 | 2 | 1 |
| Golden redhorse | 1 | 0 | 2 | 1 | 0 |
| Goldfish | 3 | 1 | 1 | 0 | 0 |
| Grass carp | 0 | 4 | 2 | 0 | 1 |
| Highfin Carpsucker | 2 | 0 | 0 | 0 | 1 |
| Longnose gar | 1 | 2 | 4 | 0 | 0 |
| Northern snakehead | 4 | 0 | 2 | 0 | 0 |
| Paddlefish | 0 | 0 | 0 | 4 | 0 |
| Quillback | 3 | 0 | 2 | 0 | 0 |
| River Carpsucker | 3 | 0 | 3 | 0 | 0 |
| River redhorse | 0 | 0 | 2 | 1 | 1 |
| Shorthead redhorse | 1 | 0 | 2 | 2 | 0 |
| Shortnose gar | 3 | 0 | 2 | 0 | 0 |
| Silver carp | 1 | 5 | 0 | 1 | 0 |
| Silver redhorse | 1 | 0 | 1 | 2 | 0 |
| Smallmouth buffalo | 2 | 3 | 1 | 0 | 0 |
| Spotted gar | 3 | 3 | 0 | 0 | 1 |
| Spotted Sucker | 2 | 0 | 1 | 1 | 0 |

## Biological score, read-only
| View | Score |
|---|---:|
| Canonical (published) | 4.6 |
| Current rubric after proper knowledge encoding (v1) | 5.2 |
| Current rubric plus regionalTransfer from the published summary (v1.1) | 5.3 |
| Proposed v2, target-scoped | 4.3 |
| v2 if every target rule were human-approved | 4.8 |
| v2 if approved and per-lake state were LIVE | 5.4 |

The encoding legitimately moves the current rubric from 4.6 to about 5.2-5.3. The stricter, target-scoped v2 reads **4.3** because it measures what a bowfisher needs: condition coverage across the target species is only about 2 of 5 families, evidence is mostly one or two sources per rule, nothing is human-reviewed, and nothing is field-validated. Nothing was tuned toward 8.0.

## Remaining production blockers (the real ones)
Human review of the target rules; field validation of a few high-value predictions; condition coverage (clarity, daypart and trend rules are thin); regional evidence (no Southeast counting stream for any rule); per-lake publication and Intelligence consumption (customer contract); upstream presence for bowfin and others (Lake Brain); Michael's decisions in the decision queue.
