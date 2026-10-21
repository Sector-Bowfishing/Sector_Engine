# Engineering status (`engineering-status-v1`) and the Sector Ops read contract (`engineering-status-ops-v1`)

There are two artifacts, with two visibility levels.

| Artifact | Schema | Visibility | Contains |
|---|---|---|---|
| `engineering-status.json` (full report) | `contracts/schemas/engineering-status-v1.schema.json` (1.2.0) | **Internal engineering only. Never sent to a browser.** | Everything, including evidence strings, repository paths, bucket and image names |
| Ops projection | `contracts/schemas/engineering-status-ops-v1.schema.json` (1.0.0) | **Approved for allowlisted Sector Ops users** | Statuses, closed labels, proof results, memory-check statuses, counts and short summaries. No evidence, paths, private resource names, repository identifiers or credentials |

## Producer (implemented and tested)

| Step | Where | What |
|---|---|---|
| 1 | `tools/cortex_status/collect_certification.py` | Runs every Brain's Kit V1 suite. Records per-proof outcomes, mutation counts and the `sourceDigest` of the code it ran against. |
| 2 | `tools/cortex_status/build_engineering_status.py --write` | Builds the full report from committed records plus brain.json, the control manifest and the certification run. Validates against the schema. |
| 3 | `--check` | Fails if the report differs from a fresh build. Because the report carries the current `sourceDigest`, **any code change makes the committed report stale** until steps 1–2 are re-run. A green CI run can never make an old report look current. |
| 4 | `--emit OUT --commit SHA` | Writes a copy stamped with the exact commit (CI uses the PR head SHA on pull requests, `$GITHUB_SHA` on pushes). Exits 1 if the certification run belongs to different code. |
| 5 | `tools/cortex_status/ops_projection.py --report OUT --out P` | Builds the sanitized projection. It **refuses** (exit 1) rather than redacts when any kept field matches a forbidden pattern. Those patterns are the Ops public-bundle scanner's (`gs://`, private bucket names, local paths, key and token shapes) plus repository file paths, branch and repository names, and image digests. Commit subjects are the only normalized field (`brains/x` becomes `x`, other paths become `[path]`). It has **no write capability**. |
| CI | `.github/workflows/python-jobs-tests.yml`, registered-Brains job | On every PR and push commit, with all Brain dependencies installed: runs steps 1, 3, 4 and 5. It also requires the re-collected certification record to equal the committed one byte for byte. Uploads artifact `engineering-status` (full report plus Ops projection, stamped with the PR head or pushed commit, kept 90 days). |

Tests: `tools/architecture/tests/test_engineering_status.py` and `test_ops_projection.py` cover the schema, staleness, separate layers, certification provenance, leak refusal and the absence of any write capability.

## Sector Ops consumer contract (stable; for the Sector Ops read-only consumer)

| Item | Value |
|---|---|
| Schema | `engineering-status-ops-v1`, `schemaVersion` **1.1.0** (`contracts/schemas/engineering-status-ops-v1.schema.json`). Additive minors only; a breaking change becomes `-v2` at a new node |
| Firebase path | Brain RTDB `sector-brain`, node **`/control/engineeringStatusV1`**: exactly one document |
| Access | Ops' existing Firebase Auth plus the `/access/opsUsers/{uid}` allowlist. `/control` is readable by allowlisted users and writable by nobody from Ops. **No rules change.** Ops never writes |
| Writer | Only the Brain Orchestrator control plane (platform-owned `/control`), with `orchestrate.py --publish-engineering-status`. **OFF until decision O-1** |
| Update trigger | Each orchestrator cycle with the flag on re-gates the projection **staged into its own image** at deploy time, and rewrites the node only when the document changed. A new deploy of the orchestrator from `main` brings a new projection |
| Source commit | `generatedFrom.sourceCommit` (40 hex) is the commit the projection describes. `publishedBy.deploymentVersion` is the orchestrator image that published it (`brain-orchestrator@<commit12>`). The gate requires them to agree |
| Code state | `generatedFrom.codeState`: `MAIN_COMMIT` or `UNMERGED_BRANCH`; `generatedFrom.sourceBranch`: the git ref. Only `MAIN_COMMIT` is ever published. **Neither field says what production runs**: per-Brain production state is the `productionActivation` layer, which is never `PASS` from repository evidence |
| Freshness | `generatedFrom.evaluatedAt` (evidence date), `generatedFrom.generatedAt` (emission), `checkedAt` (the publisher's last gate), `generatedFrom.certificationCurrent`, `generatedFrom.verificationCommit` |

**Document states** (top-level `state`):
- `AVAILABLE`: the full document.
- `UNAVAILABLE`: only `schema`, `schemaVersion`, `state`, `reason`, `checkedAt` and optionally `publishedBy`. Reasons include:
  - no projection in this image;
  - projection rejected (schema, leak or missing layer);
  - unmerged code;
  - certification not for this code;
  - commit does not match the deployed commit.

**AVAILABLE payload:**
- `reportId`, `standards` {framework, version, pin}, `statusVocabulary`.
- `generatedFrom` {sourceCommit, sourceDigest, certificationCurrent, evaluatedAt, reportSchemaVersion, codeState, sourceBranch, verificationCommit, generatedAt?, ci?}.
- `brains[8]`, each with:
  - `brainId`, `packageName`, `lifecycle`, `packageStatus`;
  - `statusLayers` (seven, each {status, label});
  - `certification` {status, proofs{P01..P19}, mutationsPassed, mutationsFailed};
  - `memory` {checkId: {branch, production}};
  - `requirements` {BR-id: status};
  - `structuralProblems[]`, `scienceDependencies[]`, `nextWork[]`, `blockers[]`.
- `decisions[]` {id, class, title, brains?} and `recentChanges[]` {commit, summary}.

**Required consumer behaviour:**

| Condition | Show |
|---|---|
| Node absent | "Engineering status not published" (the expected state before O-1) |
| `schema` or major version unknown | "unsupported contract". Never guess fields |
| `state == UNAVAILABLE` | the `reason` and `checkedAt`; show no stale data |
| `certificationCurrent == false` (never published, but handle it) | certification as "not verified for this code" |
| `ci.result` present and not `PASS` | a warning |
| `evaluatedAt` older than 14 days | "stale" label only. Never change a status |

- Render the seven layers **separately**. Never collapse them and never infer PASS.
- Display only; no scores, approvals or controls.

**Before O-1:** nothing is written and the node does not exist. For development, a consumer can use the CI artifact `engineering-status` → `engineering-status-ops.json` of any commit as a fixture. That projection is labelled `UNMERGED_BRANCH` and must be shown as development data, not as published status.

## Readiness for O-1 (what approving it turns on)

1. Merge PR #40 (A-1), then deploy the orchestrator from `main` (A-2). Its staging produces the projection for that commit (`MAIN_COMMIT`).
2. Add `--publish-engineering-status` to the orchestrator's scheduled arguments: a production schedule and argument change (O-1).

No new writer, identity, IAM change or Ops rules change is needed. The node is platform-owned `/control`, written by the existing control-plane writer.

**Verified before approval** (`tools/architecture/tests/test_engineering_status_publication.py`; CI image check):
- the gate refuses every invalid case with an explicit, schema-valid UNAVAILABLE;
- one sanitizer serves producer and publisher;
- the write sits only behind the flag;
- the full report never enters the image;
- a PR image's projection is refused as unmerged.
