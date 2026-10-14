# Validation Model

Shared *metadata and vocabulary* for validation. The platform defines no validation science; each Brain pre-registers its own gates.

## 1. Validation record (per Brain and per claim)
```jsonc
{ "status": "NOT_VALIDATED",            // closed: NOT_STARTED | NOT_VALIDATED | CALIBRATION | DESK_VALIDATED | VALIDATED | FAILED | WITHHELD
  "ref": "/validation/{brainId}",       // existing node
  "preRegistered": true,                // gate and metric written before outcome data was seen
  "gate": "doc#section",                // where the pass criterion lives
  "evidence": {"n": 0, "window": "…", "truth": "FIELD|PROVIDER|DESK"},
  "lastEvaluatedAt": "…" }
```
`FAILED` is a result, not an absence; `NOT_STARTED` is not `FAILED`. A claim's `maturity` and the Brain's validation `status` are related but distinct: Brain validation summarises the claims that matter for its production policy.

## 2. Rules
1. **Pre-registration.** Gates/thresholds/metrics are fixed before outcome evaluation. Changing a gate after seeing results voids the status (record a new version instead).
2. **Truth hierarchy.** Field/provider truth the model did not train on > desk comparison against independent documents > internal consistency. Only the first can reach `VALIDATED` for a Level-3 claim.
3. **Prospective > retrospective.** A prospective ledger (Lake) is the strongest form; hold-out (H2 sealed until 2027-01-01 for Wind) is next.
4. **No leakage into score.** A validation outcome moves `claim.maturity` and the owner's rubric; the platform never lifts a score because a validation doc exists.
5. **Failing claims degrade gracefully.** A failed Level-3 claim does not disable truthful Level-1/2 fields.
6. **Unknown validation ≠ failed.** Missing validation is `NOT_STARTED`.

## 3. Field validation
Real-world observation comes through one shared envelope (`FIELD_VALIDATION_MODEL.md`) so that each Brain's validation uses the same trip ledger and consent version.

## 4. Where it appears
`/validation/{brainId}` (existing, detail); `control.brains[id].validation{status, ref}` (summary). Model v1 adds only the closed `status` set and the `preRegistered` flag; it migrates no existing validation node.
