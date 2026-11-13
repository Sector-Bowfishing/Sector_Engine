# Proposal for Cortex: the first CUSTOMER-lane family, `fam.customer-lake-level` (Engine gap CG-3.1-8)

**Status:** ready to apply in a Cortex maintenance session (Sector_Ops #47 item 5, 2026-11-02). It was written from the Engine and nothing under Cortex was changed.
- Cortex IO-06: "Only an approved customer release can register a CUSTOMER-lane family." So this is applied together with the owner's customer release for Lake level, not before it.
- Engine side: design note `docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md` §6.
  - Engine reader: PR #85, list #89.
  - Publisher planner: `publisher_live/customer_lake_level.py` (this PR).

## 1. Registry entry for `projects/sector/shared/data/firebase-data-contracts.json` → `families`
It is written in the existing record shape. Field values use the registry's current vocabulary, except `lane: CUSTOMER`, which is the first of its kind.
```json
{
 "id": "fam.customer-lake-level",
 "pattern": "/customer/lakes/{lakeKey}/level",
 "domain": "domain-output",
 "scope": "per-lake",
 "status": "CANONICAL",
 "writer": "platform.publisher-live",
 "targetWriter": "platform.publisher-live",
 "readers": ["service.customer-engine"],
 "schemaRef": "sector-customer-lake-level-v1 (Engine docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md §6)",
 "freshness": "freshUntil in the record; the Engine re-checks it on every request",
 "freshnessModel": {"kind": "WRITE_TIME", "currentSource": "the record's own freshUntil (copied from the Lake publication)", "writeTimeFields": ["freshUntil", "writtenAt"]},
 "retention": "latest only; overwritten by each Lake publication; UNKNOWN written over a lake that stops passing",
 "classification": "INTERNAL",
 "label": "PLANNED",
 "evidencePaths": ["/customer/lakes/{k}/level"],
 "evidence": [{"source": "engine-pr", "section": "#85 §6; customer_lake_level.py"}],
 "notes": "First CUSTOMER-lane family (IO-06). A minimal copy of Lake level and trend for owner-approved lakes only. A nearby-gauge proxy is trend only (lake.md LC-06). No internal field (zone, percentile, provenance, binding) is copied.",
 "lane": "CUSTOMER"
}
```
- **`classification: INTERNAL`** is about sensitivity, not lane. The values come from public agency gauges, and the app never reads the database; only the customer Engine does, server side. `PRIVATE` and `RESTRICTED` do not apply.
- **`label: PLANNED`** becomes `VERIFIED_IMPLEMENTATION` once the Publisher wiring merges, and `PRODUCTION_OBSERVATION` after the first real write is read back.

## 2. Supporting changes in the same Cortex release
1. **`roots`:** add `"/customer"`. Without it, `data-check` reports the root as unknown.
2. **`accessRules`:** add a rule. Clients have no read and no write. The customer Engine reads with its service identity, which client rules do not govern, and the read grant is an IAM change approved on its own.
   ```json
   {"id": "ar.customer-lake-level", "path": "/customer/lakes/{lakeKey}/level", "read": "NONE", "write": "NONE", "state": "PLANNED", "label": "PLANNED",
    "notes": "Server-side read by service.customer-engine only; the Publisher writes with its own identity. No client grant."}
   ```
   `"read": "NONE"` and `state: PLANNED` are new values in this list. If the release prefers the existing vocabulary only, leave the rule out and keep the default deny.
3. **`DATA_CONTRACTS.md`:** the generated table gets the row. Regenerate it from the JSON; do not hand-edit it.
4. **`operations.md` IO-06:** change "no CUSTOMER-lane family existed on 2026-10-22" to name `fam.customer-lake-level` as the first, registered with the Lake level customer release.
5. **`data-check`:** resolve paths that the Engine builds through a declared helper, here `LakeLevelOutputAPI.copyPath(_:)` and the Publisher's `customer_lake_level.copy_path`. Today the interpolated path is invisible to the check, which is the second half of CG-3.1-8.
6. **A test** in `tools/tests/test_publication_ownership.py`, or wherever the lane checks sit:
   - a customer-class component (`service.customer-engine`) reading `fam.customer-lake-level` is allowed;
   - reading `fam.lake-states` is still `INTERNAL_TO_CUSTOMER`.

## 3. What this does not do
- It does not register any other Brain's customer path. Each follows the same pattern with its own family and an approved release.
- It does not grant IAM, write data, or change Lake's INTERNAL families.
