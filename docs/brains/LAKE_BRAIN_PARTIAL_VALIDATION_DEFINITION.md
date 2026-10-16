# Lake Brain — proposed definition of `PARTIAL` validation (DOCUMENT ONLY — status unchanged)

`/validation/lake-brain` is `NOT_VALIDATED` and stays so. Starting the prospective prediction ledger, passing a hold-out test, or writing this
document does **not** make the Lake Brain `PARTIAL`. Adopting any definition below is a separate policy decision that Michael must approve explicitly.

## Why a definition is needed
The score rubric reads one fleet-wide value (`NOT_VALIDATED` 0, `PARTIAL` 5, `VALIDATED` 10) and a gate caps the score at 5.0 while it is `NOT_VALIDATED`.
The evidence arrives per dimension (source binding, history, band calibration, trend labels, zone/flood semantics), so a single word needs an explicit rule.

## Proposal (not adopted)
`PARTIAL` requires **all** of:
1. **Binding acceptance.** The machine-verified bindings the Lake Brain publishes were accepted by acceptance sampling (stratified n ≥ 60, ≤ 1 error; the flagged tier reviewed in full), recorded in a committed review result file.
2. **Pre-registered calibration.** The v2 hold-out criteria in `LAKE_BRAIN_RULES_V2_PREREGISTRATION.md` (H-A..H-D) all pass, on ≥ 100 lakes, as committed before the run.
3. **Withholding.** Every classification family that fails its criterion is withheld (`INSUFFICIENT_HISTORY` / `UNKNOWN`) rather than published.
4. **Prospective evidence started.** The prediction ledger has run for ≥ 90 days and its first monthly scorer output exists (this shows the process works; it is not itself the validation).

`VALIDATED` additionally requires a prospective result: ≥ 12 months of logged predictions scored against realised levels with the pre-registered v2 criteria applied once.

## What does not count
The ledger merely existing; a hold-out result without prior pre-registration; counting v1.1 extensions or `R7h` promotions; per-lake private presence or species evidence; any result on lakes whose directory coordinates are flagged (43 identity-risk, 126 off-water) until those are reviewed.

## Status
Proposal only. Lifecycle, validation status and readiness are unchanged by the adoption branch.
