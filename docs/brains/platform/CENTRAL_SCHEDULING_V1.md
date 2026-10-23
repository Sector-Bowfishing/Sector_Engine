# Central Brain scheduling V1 (2026-10-23)

Owner directive (2026-10-23): all eight Brains are controlled by ONE orchestrator, and recurring Brain execution stays **PAUSED** until the owner
explicitly authorizes it. Rehtac Cortex 2.7.0: PL-15 (one scheduling authority), PL-16 (fail-closed execution control), PL-17 (duplicate
protection and limits), PL-18 (no reactivation by deployment), BR-21 (execution declaration).

## The one authority

`brain-orchestrator` (Cloud Run job, hourly Cloud Scheduler trigger `50 * * * *`, **PAUSED**) is the only component that starts Brain work
automatically. Each cycle it evaluates all eight Brains and starts only those that are due. Their freshness, dependencies, inputs, retry state and
limits decide; a cycle can evaluate everything and start nothing.

| Brain | Trigger (BR-21) | Executed as | Refresh |
|---|---|---|---|
| Wind | TIME 1.5 h | Cloud Run job `wind-hourly`, started by the orchestrator (its own `wind-hourly` scheduler is **deprecated, PAUSED**) | hourly provider forecast/observation archive |
| Lake | TIME 26 h | Cloud Run job `lake-brain` (`--scope pilots`), started by the orchestrator (`lake-brain-ledger-daily` scheduler is **deprecated, PAUSED**) | daily prospective ledger |
| Water Temp | TIME 6 h | `water-temp-brain` (5 pilot lakes) | sensor + model |
| Water Clarity | TIME 26 h | `water-clarity-brain` (2 pilot lakes); satellite pipeline stays PAUSED | C1 publisher |
| Fish | EVENT | in-process | when its inputs change (own plan check) |
| Intelligence | EVENT | in-process | when a dependency materially changes |
| Depth | SHADOW 24 h | shadow lane in the orchestrator | candidate release; approved path abstains |
| Vegetation | SHADOW 168 h | shadow lane in the orchestrator | candidate release; no live feed |

The six Brain-input pipeline schedulers (`water-temp-tva-archive`, `lake-surface-dispatch`, `lake-surface-daily`, `hydrology-hourly`,
`clarity-current-hourly`, `clarity-candidate-shadow`) stay PAUSED. Their deploy scripts no longer create, update or resume schedulers.

## Global execution control

`/control/executionControlV1` (`brain-execution-control-v1`, Cortex family `fam.control-execution-control`, writer: the owner CLI):

```json
{"schema": "brain-execution-control-v1", "state": "PAUSED",
 "brains": {"wind": {"enabled": false, "limits": {"maxRunsPerDay": 24, "maxRetries": 2, "maxConcurrency": 1, "maxCostPerDay": 1.0}}},
 "limits": {"maxStartsPerCycle": 2}, "approvalRef": null, "changedBy": "...", "changedAt": "...", "reason": "..."}
```

**Fail closed:** an absent, unreadable, wrong-schema or invalid document is PAUSED, and so is ENABLED without an `approvalRef`.

**While PAUSED:**
- no worker starts;
- no Brain plan check runs (plan checks can call providers);
- no shadow lane runs.

The orchestrator still evaluates, and still publishes control, health and engineering status. Every Brain then shows `internalOperation: PAUSED`, never ACTIVE.

**While ENABLED,** these limits hold:
- only Brains with `enabled: true` may start;
- at most `maxStartsPerCycle` workers start per cycle, so there is no catch-up burst after a long pause and missed cycles are never replayed;
- `maxRunsPerDay` and `maxCostPerDay` (ledger estimate) apply per Brain;
- single-flight per Brain (running execution or lock);
- no overlapping orchestrator cycles: a cycle that sees another running execution starts nothing;
- bounded retries (`retry_gate`).

**Admin runs:**
- Form: `orchestrate.py --run-now <brain> --scope <scope> --requested-by <name> --admin-reason "<why>"`.
- Explicit and recorded: `admin {requestedBy, reason}` goes into the execution ledger.
- Allowed while PAUSED, and starts only that Brain.
- Never changes the control or any schedule.

**Deployments:** `jobs/brain-orchestrator/deploy-job.sh` creates or updates the trigger definition, then **always pauses it** and fails if it is not PAUSED. No deploy script creates or resumes any other scheduler.

## Owner-approved activation procedure (the only one)

1. **Decide scope and budget.** Choose which Brains to enable and record an approval reference. A pilot start is `water-temp,water-clarity`; add Brains later one at a time.
2. **Enable the control** (owner, own gcloud identity):
   ```
   python3 tools/ops/execution_control.py enable --changed-by <owner> --approval-ref <ref> --reason "<why>" \
       --brains water-temp,water-clarity --confirm "RESUME RECURRING BRAIN EXECUTION"
   ```
3. **Resume the central trigger.** `resume-orchestrator.sh` checks that the control is ENABLED with this ref, that the schedule audit passes, that no deprecated scheduler is enabled and that no cycle is running, then runs a dry cycle in Cloud Run and resumes:
   ```
   OWNER_APPROVAL_REF=<ref> bash tools/ops/resume-orchestrator.sh
   ```
4. **Verify the pilot.** Over the next cycles:
   - `/control/engineeringStatusV1` shows only the enabled Brains ACTIVE;
   - `/control/orchestratorV1/executions` records the starts;
   - `check_preproduction_schedules.py` passes.
5. **Expand.** Use `execution_control.py brain --brain <id> --enable-brain` (one Brain at a time), and verify each Brain's first execution.

**Stop at any time:**
```
gcloud scheduler jobs pause brain-orchestrator --location us-central1
python3 tools/ops/execution_control.py pause --changed-by <owner> --reason "<why>"
```

## Expected operating cost when enabled

Estimates use measured run durations and Cloud Run us-central1 list prices, before the free tier.

| Component | Basis | ≈ USD / month |
|---|---|---|
| orchestrator | 720 cycles × ~40–90 s × (1 vCPU, 0.5 GiB) | 0.6–1.2 |
| Wind | ≤ 24 runs/day × ~4 min × (1 vCPU, 2 GiB) | ~4 (former `wind-hourly` cap $5) |
| Lake | 1 run/day × ~2 min × (1 vCPU, 1 GiB) | < 0.1 |
| Water Temp | ≤ 4 runs/day × ~90 s × (1 vCPU, 1 GiB) | ~0.2 |
| Water Clarity | ≤ 1 run/day × ~100 s × (1 vCPU, 2 GiB) | < 0.1 |
| Fish, Intelligence, shadow lanes | inside the orchestrator | negligible |
| **All eight enabled** | | **≈ 5–6** |
| Pilot only (Water Temp + Clarity) | | ≈ 1–1.5 |

## While paused: remaining (non-execution) costs

Pausing stops execution charges only. These persist:
- Artifact Registry image storage
- Cloud Storage buckets (research archives, Brain archives, Lake ledger, Wind store)
- RTDB storage and download bandwidth (Sector Ops reads)
- Cloud Logging retention
- Cloud Scheduler jobs, which bill per job (including paused ones) beyond the free allowance
- customer-serving services (`sector-engine`, `conditions`, purchase/notification functions; not Brain execution)
