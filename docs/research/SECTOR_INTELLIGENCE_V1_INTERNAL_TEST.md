# Sector Intelligence V1 — internal app-test package (2026-10-26)

INTERNAL ONLY. Nothing here is customer-facing, approved science, or a production schedule. Cloud Brain execution stays PAUSED until the owner authorizes the activation steps below.

## What the package is

| Part | Where | What it gives the test |
|---|---|---|
| Eight Brain charters | `brains/*/research/CHARTER.json` | each Brain's bowfishing purpose, what it can and must not predict, what it needs from other Brains, pre-declared fit-for-purpose targets, abstain conditions |
| Internal conditions assessment | `tools/research/integration.py` | per factor: value, age, freshness limit, status (FRESH / STALE / MISSING / ABSTAIN), uncertainty, capability class; a seasonal calm-night prior; field-compared species notes with the probability that a temperature-gated rule applies; **no combined score, no recommendation** |
| Capability measurement | `tools/research/bowfishing_capability.py` | computed `bowfishing-capability-v1` per Brain, current vs candidate, UNMEASURED where evidence does not exist; separate from engineering, certification, customer-readiness and authoritative scores |
| Repeatable scenarios | `tools/research/scenarios/v1_internal.json` (+ CI test) | fresh data, stale data, strong-wind night, cold / warm / borderline water, missing Brain, Depth/Vegetation ABSTAIN |
| Outcome recorder | `tools/research/outcomes.py` | append-only field results tied to the assessment that was shown; `evaluate` reports counts and errors only and feeds the next research campaign |
| Autonomous research loop | `tools/research/campaign.py loop` | keeps researching: queued agent tasks are executed, ingested, turned into follow-up tasks or exact blockers |

## What each Brain contributes to the test

The classification (VALIDATED_FOR_INTERNAL_TEST / EXPERIMENTAL / ABSTAIN) is kept per lake in the private pilot readiness record (`PILOT_V1_READINESS.json`); the rules are the same everywhere: a capability is VALIDATED only with an independent validation record; observations and models are EXPERIMENTAL and shown with source and age; Depth and Vegetation ABSTAIN; no Brain's unresolved gap blocks another.

## Activation requirements (none executed)

1. Declare the used-but-undeclared Brain dependencies in `brain.json` (`integration_contract_gaps.json` lists them; a contract change for the owner's review).
2. Reconcile deployed images that predate the release-verification and pilot changes.
3. The internal app computes data age itself from timestamps (node `stale` flags are write-time).
4. Owner approval reference; then `execution_control.py enable ... --dry-run`, then `resume-orchestrator.sh` (it refuses unless every precondition holds).
5. Run the scenarios against the live states, then record real outcomes with `outcomes.py` and let the next campaign test the Brains against them.

## Not part of V1 (isolated, not blocking)

Depth and Vegetation outputs; strong-wind-night forecasts; shoreline exposure; any fishing recommendation; any rule contradicted by the field comparison.
