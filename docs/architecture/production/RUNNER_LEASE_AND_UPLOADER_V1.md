# Runner lease and artifact uploader, V1 (DRAFT; Sector_Ops #46, #47, #50)

**Status:** draft code, off by default. Nothing is deployed, no IAM is granted and no lease exists anywhere.

**Purpose.** The owner wants Sector Pulse, the runner on the owner's Mac mini, to run the Brains, with the cloud jobs as a fallback that stays **OFF** until the owner turns it on. These two pieces let a second runner exist without breaking the single-scheduler rule (Cortex PL-15) or making a double publish possible.

## 1. The lease (`jobs/brain_platform/sector_brain_platform/runner_lease.py`)
- **Storage.** There is one object per Brain, `exports/runners/leases/{brainId}.json` (`sector-runner-lease-v1`), in the private artifact store. It is written by compare-and-swap (generation match), the same mechanism as the Publisher's apply lock.
- **Granting.** Only the **Orchestrator** grants or hands over a lease (`grant`), wherever the Orchestrator runs.
  - A fresh lease of another runner is never taken.
  - An expired lease goes to a different runner only when **failover is enabled** for that Brain in the reviewed `runner-policy.json`.
- **Renewing.** Only the **holder** renews, as a heartbeat (`renew`), and only while the lease is unexpired. An expired lease must be granted again, so a runner that lost its lease stops before it seals.
- **Policy.** `runner-policy.json` is reviewed in git: `defaultPrimary: cloud`, no per-Brain primaries, **failover off**. Making Pulse primary for a Brain, or enabling failover, is an owner decision with an `approvalRef`.
- **Orchestrator gate** (`--runner-leases` or `RUNNER_LEASES=on`, default off). Before starting a Brain's Cloud Run job, `cloud_may_start`:
  - refuses while another runner holds a fresh lease;
  - refuses whenever the policy primary is not the cloud and failover is off.

  A missing store or policy fails closed, so it never means a surprise cloud run.
- **Runs outside Cloud Run** leave a create-only `exports/runners/{holder}/executions/{brainId}/{executionId}.json`. With the flag on, the publication stage reconciles those runs exactly like Cloud Run executions.

## 2. The uploader (`tools/runner/runner.py upload`)
Pulse calls it through its Engine bridge, from a commit-pinned Engine snapshot. For a locally sealed artifact (for example `run.py --dry-run --out DIR` → `DIR/artifact.json`), it does the following:
1. checks that the lineage is present (Brain, execution, schema, generation time);
2. requires this runner to hold a fresh lease for the Brain (exit 3 otherwise);
3. stores the artifact create-only under `artifacts/{brainId}/` with the Brain's own `ArtifactWriter`, the call Cloud Run jobs make. An identical re-upload is a no-op, and a different artifact under the same id is an error;
4. reads it back by digest and canonical form (exit 5 on mismatch);
5. creates the runner execution record.

It never writes a database and never starts anything. `runner.py renew` is the heartbeat; `show` and `grant` (Orchestrator only) are for operations.

## 3. What this does not do yet
- **Identity.** The access split (Pulse may create only `artifacts/{brainId}/` and its own execution records, and renew leases) is enforced in code (`runner_view`), not yet by IAM. A per-holder IAM condition is part of the Pulse activation plan.
- **Lease history.** The Orchestrator does not yet record its grants in its publication ledger, so `held_for_cycle` has no production caller. That wiring comes with Pulse activation.
- **Pulse side.** Calling `renew` / `upload` from Pulse's pipeline is the matching Sector-Pulse PR.
