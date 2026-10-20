# Fish Capability V2: activation prerequisites

The capability block (`/scores/biological-state/capability`) is attached by the shared scorer only when `fish_capability.publication_gate` passes on the repository record `fish-capability-publication.json`. That requires:
- status ACTIVE;
- `activation.approvedBy`;
- a reviewed decision (APPROVED or REJECTED, plus `reviewer`) for each of the six gate reference cases.

The record reaches production only through a reviewed PR and an approved orchestrator redeploy (the scorer runs from that image).

## Tool (edits the local record only; never approves anything itself)
- `python3 jobs/brain-scores/fish_capability_publication.py status [--read-published | --published-release R]`
  - Read-only readiness. Exit code 3 while blocked.
- `python3 jobs/brain-scores/fish_capability_publication.py record-review --case <id> --decision APPROVED|REJECTED --reviewer "<name>" [--note "..."]`
- `python3 jobs/brain-scores/fish_capability_publication.py activate --approved-by "<name>"`
  - Refused until every gate case has a decision.

Reviewer and approver names must be a named human. Blank names, and names that look automated (Claude, AI, assistant, bot, automated, LLM, GPT, system, rehearsal), are refused. Recording a review never activates anything.

## Order
1. **Reviewer.** Reads the six cases in the private research workspace (not in this repository) and records one decision per case.
2. **PR** with the updated record. Status is still INACTIVE.
3. **Owner.** Runs `activate --approved-by`. This can be in the same PR or a follow-up, and is the explicit production score publication approval.
4. **Merge**, then **approved orchestrator redeploy** with the lineage preflight. The next scorer run attaches the block; `plan_capability_write` writes only `/scores/biological-state/capability`.
5. **Verify.** Ops renders the block only when `authority.status = AUTHORITATIVE_APPROVED` and `authority.publication = ACTIVE`, which the scorer sets only past the gate. Maturity (5.1) is never touched.

Rollback is described in the record (`rollback`).

## Readiness on 2026-10-20 (production GET)
- READY: rubric 2.1.0 approved and frozen; cohorts v2 approved and frozen; evidence present; evidence on the published release 2026-10-17.1; baseline reproduced (TARGET 6.805781 / overall 3.770401).
- BLOCKED:
  - 0 of 6 reference cases decided;
  - owner activation not recorded.
- UNKNOWN until deploy: the image contains the ACTIVE record.
