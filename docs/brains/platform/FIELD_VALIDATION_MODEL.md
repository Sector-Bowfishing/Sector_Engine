# Shared Field Validation Model

**One trip envelope, per-Brain blocks. Not four frameworks.** Implementation: `sector_brain_platform/field_validation.py` (`validate_trip`, `BLOCKS`).

## Envelope (required)
| Field | Notes |
|---|---|
| `tripId` | unique |
| `lakeId` | canonical directory id (`"Name|ST"`) |
| `zoneId` | zone/area within the lake |
| `timestamp` | UTC ISO-8601 of the observation |
| `location` | coordinates / context (precision per consent) |
| `observer` | tester identity **or pseudonymous reference**; no real name in the public repo or RTDB `brains` tree |
| `conditionsRef` | reference to the conditions snapshot at the time (not an embedded copy) |
| `consentVersion` | consent/ledger version the observer agreed to |
| `blocks` | map `{brainKey: block}`, ≥ 1 block |

## Per-Brain blocks (registered; fields optional unless the Brain marks them required)
| Block | Fields |
|---|---|
| `wind` | predictedExposure, observedExposure, predictedSurface, observedSurface, providerWindMph, providerGustMph |
| `depth` | predictedEffectiveDepthFt, observedSonarDepthFt, dryOrWet, shootable |
| `biological` | species[], encounters, shootableCount, effortMinutes |
| `vegetation` | surfaceVegetationObserved, coverageClass, vegetationType (only if supported) |
A new Brain registers a block (additive entry in `BLOCKS`) — it does not create its own envelope, ledger or consent flow.

## Value rules
- A field is a real value, **absent**, or an explicit unknown marker `{ "unknown": "UNKNOWN|NOT_ASSESSED|UNAVAILABLE|NOT_OBSERVABLE|WITHHELD" }`.
- `null` is rejected so it can never be read as zero. `0` and `false` are real values (`observedSonarDepthFt: 0` = dry).
- Types are checked (`shootable: 1` is rejected; bool ≠ int).
- Unregistered Brain blocks and unknown fields are rejected, not stored.

## Privacy
Observer references are pseudonymous in anything derived into the Brain RTDB or a repo. Per-lake species presence is not published into the public repo (existing Biological rule). Consent version travels with every trip so a later consent change can exclude affected trips.

## Not in scope
Collection UI/app flows, storage location, and analysis methods — owned by the app/Ops lanes and each Brain's validation plan.
