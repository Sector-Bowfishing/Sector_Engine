# CG-3.1-15 option (a): Water Clarity's health family moves to the Orchestrator

Owner decision 2026-11-04 (Sector_Ops #50): **option (a)**. Water Clarity's health family moves to the Orchestrator through a Cortex change and an Engine PR. Cortex is read-only from the Engine, so this file is the proposal for a Cortex maintenance session. The Engine side is the draft PR on `feat/clarity-health-orchestrator-2026-11-04`.

## Proposed Cortex change (3.1.2, registry only)

Add four families to `projects/sector/shared/data/firebase-data-contracts.json`, immediately after `fam.health-sources`. Then reseal the registry and re-render `DATA_CONTRACTS.md`.

| id | pattern | scope | status | writer | targetWriter |
|---|---|---|---|---|---|
| `fam.health-brains-water-clarity` | `/health/brains/water-clarity` | per-brain | CANONICAL | `platform.orchestrator` | null |
| `fam.health-sources-sentinel-2-l2a` | `/health/sources/sentinel-2-l2a` | global | CANONICAL | `platform.orchestrator` | null |
| `fam.health-sources-usgs-nwis-turbidity` | `/health/sources/usgs-nwis-turbidity` | global | CANONICAL | `platform.orchestrator` | null |
| `fam.health-sources-noaa-mrms` | `/health/sources/noaa-mrms` | global | CANONICAL | `platform.orchestrator` | null |

The other columns (domain `health-control-jobs`, readers, freshness model, classification INTERNAL, lane INTERNAL) are copied from `fam.health-brains` and `fam.health-sources`.
- Notes: "Moved from @owning-brain to the Orchestrator at Water Clarity's CENTRAL cutover (owner decision 2026-11-04, option a). Derived by the Orchestrator health mirror from the published `/brains/water-clarity/status` (sources: `/sources/{id}`); written at child level."
- observedAt: 2026-11-04.

### Rule the maintenance session should state
- **Per-Brain move:** a Brain's health family moves to the Orchestrator only at that Brain's approved CENTRAL cutover, and only through literal per-Brain rows like these. The generic `{brainId}` / `{sourceId}` families keep `@owning-brain` (current) and `platform.orchestrator` (target).
- **Matching:** a literal path segment is more specific than a `{placeholder}` at the same depth. Any Cortex tool that matches paths to families (`cortex_data.py` / `data-check`) must resolve `/health/sources/noaa-mrms` to the literal row, not to `fam.health-sources`. The Engine applies this in `data_ownership._families`.
- **Validation:** `validate` should accept these rows. They are not Brain-written, so no Publisher target applies.

### Checked against a scratch copy (Cortex itself untouched)
- **Proposed rows:** applied to a scratch extract of Cortex `d5c8380`. Every Engine CI suite passed with that copy as `CORTEX_HOME`, including the mirror-equality test, the ownership audit and Swift/Python ownership conformance.
- **Pinned Cortex:** against it unchanged, only the mirror test fails (by design), until Cortex 3.1.2 lands and the Engine re-syncs.

## Engine side (draft PR)
- **`ownership.path_allowed`:**
  - For `brain-platform`, it allows a `/health/brains/{id}/{child}` or `/health/sources/{id}` path only when the registry's **current** writer for it is `platform.orchestrator`.
  - It refuses that path, and the whole `/health/brains/{id}` node, to every Brain.
  - Today that is Water Clarity's health and its three sources. Every other Brain is unchanged.
- **Swift:** `BrainContract.pathAllowed` mirrors the rule with a literal list. A test pins that list to the registry rows, and shared conformance cases keep both languages equal.
- **Mirror and tests:** the `data_ownership.json` mirror carries the four rows. The tests that assumed Clarity writes its own health are updated: Clarity has no database write site (X14).
- **Live effect:** none until the Orchestrator is redeployed (no deploy authorised). After that, `health_mirror.stage` writes Clarity's derived health on a cycle that publishes Clarity. All Brain execution is still PAUSED.
