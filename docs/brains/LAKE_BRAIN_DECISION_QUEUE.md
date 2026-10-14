# Lake Brain — DECISION_QUEUE (living; long-run score campaign)

Every item that needs Michael (or time, a field result, a licence or an external source) lives here so work never stops on one question. Work continues on every independent path.
Blocker labels: MICHAEL AUTHORIZATION · HUMAN REVIEW · TIME / SEASON · FIELD · EXTERNAL SOURCE · LICENSING · UPSTREAM BRAIN · PREREQUISITE BRANCH.
Last updated 2026-10-14 ~04:45 UTC. Nothing here is applied until decided.

## Queue
| # | Decision / action | Blocker | Why it matters | Recommendation | Unblocks |
|---|---|---|---|---|---|
| 1 | **Consolidated binding review packet** (Section A easy, about 64 rows; Section B flagged, later). Return the CSV export. | HUMAN REVIEW | 5 + 58 accepted = 63 profiled lakes lifts the coverage gate: displayed 3.0 → 5.0 | do Section A only first | coverage, displayed score |
| 2 | Approve running the pre-seed + staged rollout after (1) | MICHAEL AUTHORIZATION | accepted lakes must have history before they publish | approve after review lands | coverage, historyQuality at fleet scale |
| 3 | Rubric proposal A: floodDroughtContext denominator = lakes where a flood pool exists | MICHAEL AUTHORIZATION | rubric measures "has a flood pool" not "knows its flood pool" | **YES, form C** (unknown-because-unpublished stays in the denominator; only not-applicable lakes leave). On the 196: dimension 5.7 → 7.4, uncapped 6.5 → 6.6, displayed unchanged while NOT_VALIDATED (`LAKE_BRAIN_RUBRIC_PROPOSALS.md`) | floodDroughtContext |
| 4 | Rubric proposal B: per-claim validation (provider / deterministic / historical state / rapid) | MICHAEL AUTHORIZATION | one failed Level-3 claim holds the whole Brain at NOT_VALIDATED | **YES, with the MINIMUM rule** across claim families (never average: averaging is a loophole that makes the target look met). With RAPID withheld, a PARTIAL-equivalent state displays 7.3 on the 196 at the ledger clock; VALIDATED is unchanged (needs 12 months) | validation, the 5.0 gate |
| 5 | Rubric proposal C: operatorPlan availability denominator | MICHAEL AUTHORIZATION | pilots score 10 only because they are the best-documented lakes | **NO, in either form.** Excluding unknowns is circular (measures how much Sector ingested, not availability) and would let a best-first 63-lake fleet reach 8.0; counting them moves plan only 4.3 → 4.4 | operatorPlan |
| 6 | Withhold the RAPID flag from publication until H-C passes prospectively | MICHAEL AUTHORIZATION | H-C failed (66.8 % vs 70 %); still published for the pilots | withhold (internal only, no customer exposure today) | a clean PARTIAL path |
| 7 | Route for a revised H-C: pre-register before reading any ledger month, score once on ledger data dated after the commit | MICHAEL AUTHORIZATION | only honest route to re-test RAPID | approve the route; the text is then drafted | validation |
| 8 | Create the monthly ledger scorer schedule (commands prepared, not run) | MICHAEL AUTHORIZATION | first monthly output 2026-11-01 | approve before 2026-11-01 | validation evidence |
| 9 | Ratify critical dimensions and publish `requiredDimensions` / `productionPolicy` (Option A: validation, sourceAuthority, historyQuality, seasonalBaseline, trendQuality) | MICHAEL AUTHORIZATION | Ops cannot evaluate the production policy without it | approve Option A | Ops production view |
| 10 | Role mailbox for `SECTOR_CONTACT` | MICHAEL AUTHORIZATION | NWS asks for a contact before blocking | supply one | fleet-scale provider calls |
| 11 | Coordinate / identity review pack (171 lakes; only the 58 held lakes block candidate bindings: 46 PASS / 12 FLAG) | HUMAN REVIEW | unblocks ~58 more candidate lakes | review the 58 first | coverage beyond 63 |
| 12 | Review of 8 recovered mismatch lakes + 5 needs-review lakes | HUMAN REVIEW | up to 13 more candidates | after (1) | coverage |
| 13 | Definition: a lower-pool level counts as a zone bottom? | MICHAEL AUTHORIZATION | lifts operator-plan lakes 84 → 120 of 196 | decide with proposal C | operatorPlan |
| 14 | Cross-Brain contract additions P1–P3: `datum`, reference pool, `confidence` | MICHAEL AUTHORIZATION / UPSTREAM BRAIN | Depth already asks for datum | approve; Lake implements | Depth, Intelligence |
| 15 | Large-water policy (7 items in `LAKE_REGISTRY_LARGE_WATER_POLICY.md`) | MICHAEL AUTHORIZATION | 16 lakes held with no polygon | decide Great Lakes entries first | geometry coverage |
| 16 | TWDB: ask to clear the `.csv` robots disallow? (adapter gated off, 0 new lakes, history depth for 3) | LICENSING | low value | do not pursue | – |
| 17 | SJRWMD / NH DES / undocumented operator endpoint terms; ResOpsUS licence | LICENSING | a few candidate lakes | defer | – |
| 18 | Apply the GCS lifecycle rules (JSON ready) + predictions retention choice | MICHAEL AUTHORIZATION / TIME | storage growth; scratch proof pending | apply after a full cycle on the new image | cost |
| 19 | Raise lake-brain task timeout to 1800 s (or shard) before the 122+ lake batches | MICHAEL AUTHORIZATION | 196 lakes may exceed 900 s | raise | rollout batch C |
| 20 | Merge `feat/cost-efficient-scheduling` and the Lake branches to main | PREREQUISITE BRANCH / MICHAEL AUTHORIZATION | everything is still on feature branches | when ready | – |
| 21 | Ledger day 90 (2027-01-11) and day 365 (2027-10-13) | TIME / SEASON | PARTIAL / VALIDATED evidence | wait | validation |

## Independent work continuing meanwhile (no decision needed)
Consolidated review packet build; quantitative rubric analysis; control-plane / Ops contract checks after each orchestrator cycle; fingerprint / no-op verification; claim-maturity publication
design; consolidation of Lake branches on the safe lineage; ledger health audit each day.


## Can the target be reached? (quantified — `LAKE_BRAIN_RUBRIC_PROPOSALS.md` §7)
Target: overall >= 8.0 AND every critical dimension >= 7.5.
- Under the CURRENT rubric, 8.0 overall is reachable on evidence in hand only at **VALIDATED** and only with >= 156 lakes (the 25 % coverage rung). The 196-lake table gives 8.045 (six history lakes of margin). 63 or 123 lakes never reach 8.0 in 100 random orderings.
- At PARTIAL the validation dimension is 5.0, so the 7.5 critical floor fails under every proposal and every fleet size. The other four proposed critical dimensions are 8.6–10.0 at 63 / 196 / 427 lakes.
- Validation reaches 7.5 only at 10, which needs 12 months of fleet predictions scored once: earliest = the fleet's first ledger day + 365. No combination of the three rubric proposals moves that date; they only add margin or move the PARTIAL date.
- Therefore the target is **externally blocked by TIME (prospective validation)**, after coverage (HUMAN REVIEW) and the displayed 5.0 step (63 lakes) are done. Everything before that point is independent work and continues.
