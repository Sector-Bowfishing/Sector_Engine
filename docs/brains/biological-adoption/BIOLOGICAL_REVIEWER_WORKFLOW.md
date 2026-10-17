# Biological rule review: the exact workflow

**Purpose:** let a human decide which machine rules are acceptable evidence summaries, without the author promoting its own work. Review changes what is called APPROVED/REVIEWED. It does **not** make anything VALIDATED, and it does **not** change the score by itself; a published `REVIEWED` share raises `evidenceQuality` only when species maturity is actually promoted and published.

## 1. What needs human review
Every RECONCILED rule that should become APPROVED. DRAFT rules are excluded by construction. Priority order: the four internal focus species (common carp, spotted gar, silver carp, longnose gar), then the rest.

## 2. What the reviewer is shown
`tools/review.py packet RULES_DIR OUT.md --species …` writes one **private** packet (it contains rule text and evidence notes). Per rule: the statement, feature/habitat/spawn definition, months/regions/waterbody, confidence, Southeast transfer tag, number of independent streams, and each evidence item with source packet/number, read status, study type, region, sample, whether it counts, and any documented conflicts; plus the checklist and a decision line. The first packet (30 rules, four focus species) is generated; it is long only because it is complete (≈1 minute per rule).

## 3. What counts as acceptance (all six)
1. Every cited source exists and says what the evidence note says.
2. Independent streams are really independent (one cohort reported twice is one stream).
3. The statement claims no more than the evidence (direction, season, region, species, life stage).
4. The Southeast transfer tag is fair (PARTIAL/UNTESTED unless a Southeast stream counts).
5. Confidence is not above what the evidence supports (one stream = LOW).
6. Limitations and conflicts are stated; unknown is left unknown.
Decisions: **ACCEPT**, **REJECT**, or **NEEDS_MORE_EVIDENCE** (legacy spelling `CHANGES` is still read; the author makes it as a new version and it is reviewed again).

## 4. Who may review
* **EXTERNAL**: a fisheries professional who did not author the rules (preferred, and the only kind that should support a species being called independently reviewed).
* **OWNER**: Michael, as an initial reviewer if no external reviewer exists. Recorded as `OWNER` so the distinction is never lost.
* Never the author (the tool refuses the Claude author identities) and never an automated process.

## 5. What happens to an accepted rule (versioned and frozen)
`tools/review.py apply RULES_DIR DECISIONS.json OUT_DIR`:
* writes a **new** rules directory; the original rule is never edited;
* each ACCEPT is re-issued as `ruleVersion + 1`, status `APPROVED`, with `review{reviewer, reviewerRole, date, supersedes}`; the old version is retired through `supersededBy`;
* REJECT/NEEDS_MORE_EVIDENCE leave rules as they are and are recorded in `review_ledger.jsonl` (decision, reviewer, role, date, note, hash of the rule reviewed);
* the rules version is bumped (`…+review.YYYYMMDD-rules`);
* each new APPROVED version must then be **frozen in the register** before a prediction may use it (the prediction log refuses an unfrozen hash);
* predictions already logged keep referencing the older frozen version; nothing is rewritten.

## 6. From APPROVED rules to a REVIEWED species
A species is eligible for `researchMaturity = REVIEWED` when **at least 80% of its usable rules are APPROVED** by a reviewer who did not author them. Promotion is then a separate recorded decision made by Michael on a new `researchVersion` of the private species profile. The published response bands become `APPROVED`/tier `REVIEWED` only when every contributing rule is APPROVED. The score effect (evidenceQuality: REVIEWED share × 7, ceiling 7.0 even if every species were reviewed) is computed by the canonical scorer afterwards; nothing here sets it.

## 7. Concise path if Michael reviews first
1. Open the packet for one species (start with common carp: 11 rules).
2. Tick the checklist per rule and mark ACCEPT/REJECT/NEEDS_MORE_EVIDENCE; write one line for anything not accepted.
3. Hand back the decisions as JSON (a spreadsheet works; the author converts it). Nothing else is needed.
