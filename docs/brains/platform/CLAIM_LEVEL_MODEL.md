# Claim Level Model

Claim **level** says what kind of claim a statement is. It is fixed when the claim is defined and never changes because the claim was tested.

| Level | Name | Meaning | Examples (illustrative) |
|---|---|---|---|
| **1** | PROVIDER / OBSERVED | A value a provider or sensor reported, or a human observed, carried through unchanged (units/format aside) | USGS gage height; an NWS wind forecast value; an agency vegetation survey record; a sonar depth reading in a field trip |
| **2** | DETERMINISTIC DERIVATION | A value computed from Level-1 inputs by a fixed, documented, reproducible rule with no fitted/predictive component | rate of rise from two gage readings; geometry tier of a polygon; days since last observation; an effective depth = level − datum offset |
| **3** | SECTOR-DERIVED / PREDICTIVE | A value that depends on a model, calibration, inference or prediction Sector authored | predicted wind exposure of a bank; species response to conditions; a surface-vegetation-presence probability; a bite-window recommendation |

## Rules
1. **Level ≠ maturity.** A Level-3 claim is Level 3 when it is `NOT_VALIDATED`, still Level 3 in `CALIBRATION`, and still Level 3 when `VALIDATED`. Validation never promotes a claim to a "lower" level or makes it provider truth.
2. **A claim has exactly one level.** If a statement mixes (a Level-1 reading plus a Level-3 adjustment) split it into two claims; the combined one is Level 3.
3. **A failing Level-3 claim never disables a truthful Level-1/2 field** (Vegetation V1 already works this way).
4. **Customer exposure follows the level × maturity pair**, never the level alone: Level 1 may be shown with provenance; Level 3 needs at least the maturity its consumer declares (`dependencies.minClaimMaturity`), otherwise it is shown as unvalidated or withheld.
5. **Levels are declared, not inferred.** The Brain Spec carries the claim table; the platform validates it (`model_v1.validate_claim`).

## Record shape
```jsonc
{ "id": "species-response", "level": 3, "maturity": "NOT_VALIDATED", "owner": "biological-state", "evidence": "ref?", "limits": "…" }
```
`level` is an integer 1–3 (booleans rejected). `maturity` must be legal at that level (`MATURITY_BY_LEVEL`): a provider reading is never "CALIBRATION"; a predictive claim is never "PROVIDER_VERIFIED".

## Tests
`test_claim_level_is_independent_of_validation_maturity`, `test_maturity_must_make_sense_at_its_level`.
