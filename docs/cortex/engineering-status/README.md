# Engineering status (`engineering-status-v1`)

Machine-readable engineering status for Sector Ops: structural certification, the Cortex 2.1 standing memory checks, verification runs and open decisions, per Brain.

| File | Role |
|---|---|
| `engineering-status.json` | The report. **Generated; do not edit.** |
| `../../../contracts/schemas/engineering-status-v1.schema.json` | Its schema (validated by the generator and in CI) |
| `inputs/source.json` | Report id, evaluated branch and commit, structural certification per Brain, blockers |
| `inputs/memory-standing-checks.json` | The six standing memory checks per Brain, branch and production columns, with evidence |
| `inputs/verification.json` | What ran, with counts; what did not run says `NOT_RUN` |
| `inputs/decisions.json` | Approvals, decision-required and gated items |

```bash
python3 tools/cortex_status/build_engineering_status.py --write
```

```bash
python3 tools/cortex_status/build_engineering_status.py --check
```

The generator is offline and deterministic (no clock, network or git). It copies what the committed records say. It never runs a check or invents a result. CI (`foundation-verification`) fails if the report is stale or invalid.

## Honesty rules

- **Branch is not production.** Each memory check has a `branch` and a `production` status. Production is graded only from the code at the recorded deployed commit (`7dae7051`, orchestrator image `sha256:cb2e6922`). Otherwise it is `NOT_VERIFIED`. Unit tests never upgrade a production cell.
- A Brain with no package on `main` (Depth, Vegetation) is `BRANCH_ONLY`. Its production cells are `NOT_APPLICABLE` and its structural certification is `FAIL`.
- `NOT_VERIFIED` means the check could not be performed. It is not a pass.

## Proposed read interface for Sector Ops (decision O-1; nothing implemented on the Ops side)

The smallest interface that works without new infrastructure:

1. **Source:** Ops reads `docs/cortex/engineering-status/engineering-status.json` from the Engine repository at a pinned commit, for example the merge commit of the PR that updated it, through the GitHub contents API or a release asset. Read-only, with no Firebase dependency.
2. **Contract:** Ops checks `schema == "engineering-status-v1"` and the major version of `schemaVersion`. An unknown major version shows "engineering status unavailable" and is never guessed.
3. **Fields Ops needs:**
   - `brains[].brainId`
   - `packageStatus`
   - `lifecycle`
   - `structuralCertification.status`
   - `memorySummary.branch` and `memorySummary.production` (counts per status)
   - `blockers[]`, resolved against `decisions[]`
   - `source.evaluatedAt` and `evaluatedCommit` as the as-of stamp
   - `standards` for the Cortex version line
4. **Freshness:** the report states when it was evaluated (`evaluatedAt`), not a live time. Ops should label it "as of `<evaluatedAt>` @ `<evaluatedCommit>`".

Publishing the report anywhere else is a separate, gated decision (PROJECT §7: production writes) and is not done here. That includes the Brain RTDB (`/ops/engineeringStatus`), a bucket object, or anything written by the orchestrator.
