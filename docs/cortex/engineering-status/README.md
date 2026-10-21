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

## Recommended secure read interface (needs decision O-1; nothing is published today)

**Path:** Brain RTDB (`sector-brain`) node **`/control/engineeringStatusV1`**, holding exactly one `engineering-status-ops-v1` document.

- **Why this path:** Sector Ops is a browser-only SPA on Firebase Hosting. It reads only the Brain RTDB, through its subscription hub with an IndexedDB cache, behind Firebase Auth and the `/access/opsUsers/{uid}` allowlist. `/control` is already readable by allowlisted users and writable by nobody in Ops' rules, so **no rules change** is needed. Ops gets push updates and caching for free.

**Rejected alternatives:**
- **Fetching the private GitHub repository from the browser:** it needs a token in the client.
- **Shipping JSON in the Ops bundle:** Ops' scanner fails any bundled JSON other than the lake directory.
- **A new service or portal:** out of scope.

**Writer (proposed):** an Engine-owned publish step that writes **only** the projection, **only** from `main` after its CI passed (the artifact of the merge commit), with the existing Brain-RTDB writer identity.

This needs, as separate approvals:
1. The production Firebase write itself (PROJECT §7).
2. An ownership entry for `/control/engineeringStatusV1` in `sector_brain_platform.ownership`.
3. If it runs from GitHub Actions, a CI identity able to write. That is an IAM change, for example Workload Identity Federation.

Until then, an operator can download the `engineering-status` artifact of a commit; nothing is pushed automatically.

## Read contract for Sector Ops (consumer requirements)

1. **Subscribe:** read `/control/engineeringStatusV1` with the existing `useBrain`-style hub. Read-only; no write API.
2. **Contract check:**
   - Require `schema == "engineering-status-ops-v1"` and a `schemaVersion` with major `1`.
   - Otherwise show **"Engineering status unavailable (unsupported contract)"**. Never guess fields.
3. **Provenance banner (always visible):**
   - `generatedFrom.sourceCommit` (first 12 characters), `generatedFrom.evaluatedAt`, `standards.version @ standards.pin`.
   - `generatedFrom.ci.result` when present.
4. **Failure states:**

| Condition | Show |
|---|---|
| Node absent | "Engineering status not published" (the expected state until O-1) |
| `certificationCurrent == false` | Certification layers are already `NOT_VERIFIED` in the document. Show them as such and add "certification run is not for this commit" |
| `ci.result` not `PASS` | Warning banner with the counts |
| `evaluatedAt` older than 14 days | "stale" label. Ops computes this as a label only and never changes a status |

5. **Per Brain:**
   - Render the **seven `statusLayers` separately**: canonicalStructure, structuralCertification, scientificValidation, approvedMemoryRelease, operationalReadiness, productionActivation, customerConsumable. **Never** combine them into one flag and never infer PASS.
   - Show `certification.proofs` (P01–P19: PASS / NOT_APPLICABLE / FAIL) and `memory` (six standing checks, branch / production).
   - Show `structuralProblems`, `scienceDependencies`, `nextWork` and `blockers`. Resolve blocker ids against `decisions`.
6. **Ecosystem view:**
   - Counts per layer and status across the eight Brains.
   - `decisions` grouped by `class` (APPROVAL / DECISION_REQUIRED / GATED).
   - `recentChanges` as "latest verified engineering activity".
7. **Mapping to the Brain Progress milestones** (`OPS_BRAIN_PROGRESS_SYNC_V1`):

| Brain Progress milestone | Engineering layer |
|---|---|
| research recorded | `scienceDependencies` |
| knowledge validated | `scientificValidation` |
| capability evaluated | (Brain RTDB, not here) |
| state published | `operationalReadiness` / `productionActivation` |
| operationally available | `productionActivation` |
| customer-consumable | `customerConsumable` |

   The structural layers (`canonicalStructure`, `structuralCertification`) are new and belong to an "Architecture" lane.

8. **No authority:** Ops never derives scores, execution controls or approvals from this document. It is display only.
