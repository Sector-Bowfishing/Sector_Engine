# Frozen rule register and prediction log: audit (public-safe aggregate)

Audit date 2026-10-14, run against the private stores (`adoption/validation/`). Rule identities, behaviours and hashes are private; this file records counts and integrity results only. Per-rule detail (ruleId, species, behavior, version, frozenAt, evidence streams, region, season, prediction count, observation count, independent trips, status) is in the private `REGISTER_AUDIT.csv`.

## Integrity
| Check | Result |
|---|---|
| Hash chain of the frozen-rule register | verified, 51 entries |
| Every active usable rule matches its frozen hash | **0 mismatches** |
| Retired rules (superseded, never edited) still hash-identical to their frozen entry | **yes (3 of 3)** |
| Prediction log hash chain | verified, 7 entries |
| Any rule changed after freezing | **none**; revisions are new versions |
| Backups of the stores taken before each cycle | yes (`validation_backups/`) |

## Counts
| | |
|---|---|
| Frozen rule identities | 51 (48 active + 3 retired by supersession) |
| Species with frozen rules | 9 |
| Predictions logged | 7 (2 added this cycle with full environment/expected-response/input-version context; the 5 earlier entries predate those optional fields and remain valid) |
| Observations | **0** |
| Independent trips | **0** |
| Species VALIDATED | **0** |
| Validation status of every rule | `NOT_VALIDATED` (literature tier T1 only) |

By species (frozen identities / predictions): common carp 11/1 · silver carp 9/5 · spotted gar 10/5 (3 retired) · alligator gar 5/1 · grass carp 7/0 · longnose gar 3/1 · bigmouth buffalo 3/0 · bighead carp 2/0 · smallmouth buffalo 1/0.

## Revisions this cycle (new frozen identities; old versions untouched)
One silver-carp rule promoted from DRAFT to RECONCILED on a read agency statement (new identity, first freeze). Three spotted-gar rules (night movement restricted to non-spring months; spawn and shallow-vegetation rules gained a directly observed Oklahoma stream) and two bigmouth-buffalo rules (new). The revised v1 rules are retired through `supersededBy`, not edited.

## Caveat on prediction counts
Two predictions (silver carp, spotted gar) restate, with fuller context, predictions logged hours earlier. The evaluator now scores each observation against **one** prior prediction (the latest before it), so near-duplicates cannot double-count a result, and a repeat-suppression rule stops re-runs from adding materially identical entries within 24 h.
