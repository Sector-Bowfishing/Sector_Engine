# Claim Maturity Model

A closed vocabulary describing how far **one claim** has been tested. It is not the Brain's lifecycle (`LIFECYCLE_MODEL.md`) and it is not a score. Not every claim uses every state.

| Maturity | Meaning | Legal at level |
|---|---|---|
| `NOT_ASSESSED` | nobody has looked at this claim yet | 1 2 3 |
| `UNAVAILABLE` | the input/evidence does not currently exist (provider down, no data for this lake) | 1 2 3 |
| `NOT_OBSERVABLE` | the quantity cannot be observed with current means (e.g. submerged vegetation from surface imagery) | 1 2 3 |
| `WITHHELD` | held back on purpose (policy, privacy, unresolved defect) | 1 2 3 |
| `PROVIDER_VERIFIED` | the provider's value was checked against the provider's own documentation/QA | 1 |
| `DETERMINISTIC_VERIFIED` | the derivation was reproduced independently / by test vectors | 2 |
| `DESK_VALIDATED` | checked against independent documents, maps, or published data without new field truth | 2 3 |
| `PROPOSED` | a candidate rule/threshold exists, not yet exercised | 3 |
| `CALIBRATION` | being fitted/tuned/tested on data; results are provisional | 3 |
| `NOT_VALIDATED` | exists and is used internally; has not passed any validation gate | 3 |
| `VALIDATED` | passed its pre-registered validation gate on truth it did not train on | 2 3 |

## Rules
- The set is closed; an unknown string is a defect, not a new state (`test_maturity_vocabulary_is_closed…`).
- `MATURITY_RANK` orders states for minimum-maturity dependency checks. The "no verdict" states rank 0 — **unknown never satisfies a minimum**.
- A claim may move forward or backward (a regression test failing moves `VALIDATED` → `CALIBRATION`); the level never moves.
- `PRODUCTION`, `SHADOW`, `PROFILED`, `RESEARCH` are lifecycle words and are rejected as maturities. `CALIBRATION` is the one shared word; the field name (`claim.maturity` vs `brain.lifecycle`) is what disambiguates it.
- Brain-level summary for Ops: counts per maturity (`model_v1.maturity_summary`), e.g. `{ "VALIDATED": 4, "NOT_VALIDATED": 3, "NOT_OBSERVABLE": 1 }`. Never a single blended number.

## Existing usages (map, do not rewrite)
Vegetation publishes `claimMaturity`; Biological uses `researchMaturity` per species (a *research* axis, kept separate); Lake uses `NOT_VALIDATED` for its prospective ledger. All already use words from this vocabulary or are listed in `BRAIN_MIGRATION_CHECKLIST.md` §3.
