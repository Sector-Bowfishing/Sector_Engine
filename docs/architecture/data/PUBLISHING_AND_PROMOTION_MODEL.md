# Publishing and Promotion Model

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


**Status:** PROPOSED. Integrates with the existing Orchestrator material-change model (`orchestration.py:decide_brain`, `fingerprint.py`) and the platform score publisher (`publication.py:guard_scores`). **No new scheduler, queue or service.**

## 1. Promotion: research ≠ canonical knowledge ≠ published runtime state

Promotion is a change of **plane**, not a flag edited in place. Existing vocabularies are mapped, not replaced.

| Stage | Plane / where it physically is | Existing vocabulary that expresses it | Who moves it forward | Production effect |
|---|---|---|---|---|
| **DISCOVERED** | research store (packet, card, lead) | `READ_STATUS = LEAD-NOT-OPENED / SNIPPET-ONLY` | research session (agent or human) | none |
| **SUPPORTED** | research store, source read | `READ_STATUS = READ-FULL / READ-ABSTRACT`; card verification | research session | none |
| **CANDIDATE** | authoring dir (private repo) | rule `status = DRAFT`; `adopt_cards` `ACCEPT_AS_DRAFT_RULE` / `MERGE_WITH_EXISTING_RULE` | adoption session | none |
| **RECONCILED** | authoring dir | rule `status = RECONCILED` (`rules.py` — already "usable" in shadow builds) | adoption session (author) | none (shadow builds only) |
| **REVIEWED** | review ledger entry | review `DECISIONS = ACCEPT` → rule re-issued `APPROVED`; `REJECT`; `NEEDS_MORE_EVIDENCE` | **non-author reviewer** (Michael / external); agent identities refused (exists) | none |
| **RELEASED** | immutable release bundle, `latest.json` points at it | `researchVersion`/`releaseId`, manifest sha256 | **Michael** (pointer move; Biological Decision #1) | becomes eligible to publish |
| **PUBLISHED** | `sector-brain` runtime artifact with `lineage.knowledgeRelease = releaseId` | `publication.publishId` | Brain publisher via Orchestrator RUN decision or manual `--write` | **live** |
| *VALIDATED* (orthogonal) | claim maturity in the release | `CLAIM_MATURITY_MODEL` `VALIDATED` (pre-registered gate on unseen truth) | validator + review | changes displayed confidence, not stage |

Rules:
1. **Only RELEASED knowledge can be PUBLISHED.** A builder refuses an unreleased bundle in `--write` mode (Biological `load_bundle` already refuses bad hashes; add: refuse anything not reachable from `latest.json` unless `--shadow-release <id>` and the output is written to a dry-run store).
2. **What counts as usable at publish time is a Brain policy recorded in the release**, e.g. Biological today publishes RECONCILED rules with `review: UNREVIEWED` visible in the profile. That is allowed *because it is labelled*; the profile's `reviewState` must say so. Moving the bar to APPROVED-only is a Brain decision, not an architecture change.
3. **Observation Brains (Wind, Water Temp, Clarity)** promote *models*, not facts: their "release" is a code commit + config, promoted by the existing lifecycle (SHADOW → CALIBRATION → PRODUCTION_READY) and deploy lineage rules. Their runtime state is published every run from providers. The same lineage block applies (`knowledgeRelease = modelVersion@commit`).
4. **Nothing is deleted on promotion.** Rejected claims stay in the research store with their disposition.

## 2. The generic publish lifecycle (one platform function: `publish()`)
```
canonical state (release + current inputs)
  ↓ VALIDATE        schema, maxBytes, UNKNOWN rules, ownership of every target path, release reachable from latest.json
  ↓ BUILD           deterministic derived artifact(s)
  ↓ FINGERPRINT     outputFingerprint = sha256(canonical JSON of material output, volatile fields stripped)
  ↓ COMPARE         vs /brains/{id}/publication.outputFingerprint
       ├─ equal  → SKIP (write nothing; optionally heartbeat per existing 6 h rule)
       └─ differ → PUBLISH
  ↓ PUBLISH         one multi-location PATCH containing artifacts + lineage + /brains/{id}/publication (manifest-last rule, §4)
  ↓ RECORD          append publish manifest to gs://sector-brain-history/{brainId}/publishes/{publishId}.json
  ↓ NOTIFY          Orchestrator sees the new outputFingerprint on its next evaluation → existing consumer input-fingerprint
                    logic decides whether downstream Brains (e.g. Intelligence) RUN. No new event system.
```
**Integration with the Orchestrator:** today `orchestration.py:184-196` derives a Brain's output fingerprint from the Brain's own value (only Intelligence publishes one) or a hash of manifest `materialFields`, else UNKNOWN (and UNKNOWN never cascades). `publication.outputFingerprint` becomes that Brain's own value for **every** Brain, which turns material-change cascades from UNKNOWN into real CHANGED/UNCHANGED decisions without changing the decision function.

## 3. Lineage (mandatory — D14)

### 3.1 `lineage` block on every published artifact (schema `brain-lineage-v1`)
```jsonc
"lineage": {
  "schema": "brain-lineage-v1",
  "brainId": "biological-state",
  "artifactSchema": "biological-species-profile-v1",
  "knowledgeRelease": "2026-10-14.4",                   // release id | modelVersion@commit for observation Brains | "NONE"
  "knowledgeManifestSha256": "sha256:efbd1a9f…",        // release manifest hash | "NONE"
  "codeCommit": "f6cec529",                             // the publisher's own commit (NOT the orchestrator's) 
  "inputFingerprint": "sha256:…",                       // over upstream outputFingerprints actually read
  "outputFingerprint": "sha256:…",                      // over this artifact's material content
  "publishId": "biological-state:20261015T031200Z:3fa91c0e",
  "generatedAt": "2026-10-15T03:12:00Z"
}
```
For per-lake states the existing `provenance{brainVersion, modelVersion, processingVersion, generatedAt, sources[]}` stays; `lineage` adds only the fields it lacks (`knowledgeRelease`, `codeCommit`, `inputFingerprint`, `outputFingerprint`, `publishId`). To keep 621-lake states small, per-lake states may carry only `publishId` + `outputFingerprint`; the rest is in the Brain's `publication` manifest.

**Fixes this requires** (found in the audit): Biological and Intelligence run in-process in the orchestrator and inherit `brain-orchestrator@<commit>` — each Brain must stamp its *own* code commit (build-time constant). Wind's deploy label hard-codes `main@`. Score blocks carry no commit or input fingerprint.

### 3.2 `publication` manifest (latest in RTDB, full history in GCS)
`/brains/{brainId}/publication`:
```jsonc
{ "publishId": "biological-state:20261015T031200Z:3fa91c0e",
  "previousPublishId": "biological-state:20261014T220000Z:9b1d22aa",
  "status": "COMPLETE",                          // COMPLETE | PARTIAL (chunked publishes only, §4)
  "publishedAt": "2026-10-15T03:12:00Z", "publishedBy": "<publisher identity class>", "trigger": "ORCHESTRATOR_RUN|MANUAL",
  "knowledgeRelease": "2026-10-14.4", "knowledgeManifestSha256": "sha256:…",
  "codeCommit": "f6cec529", "inputFingerprint": "sha256:…", "outputFingerprint": "sha256:…",
  "paths": {"count": 31, "bytes": 1084211}, "removed": [] }
```
`gs://sector-brain-history/{brainId}/publishes/{publishId}.json` additionally lists every path written with its own fingerprint (so a reader can say *which species* changed).

### 3.3 Answering the questions
- **Why did Common Carp change yesterday?** Find the two publishes that bracket "yesterday" in history; compare `/speciesProfiles/common_carp` per-path fingerprints → if different, compare `knowledgeRelease` (knowledge change: diff the two release manifests file-by-file; the changed rule/claim files and the review ledger lines say why) or `codeCommit` (builder change) or `inputFingerprint` (upstream change).
- **What knowledge revision produced this?** `lineage.knowledgeRelease` on the artifact.
- **Can we recreate the prior version?** Yes for knowledge Brains: rebuild from the prior release with the prior `codeCommit`'s builder and check `outputFingerprint` matches the old manifest. For observation Brains: no (inputs were live); prior *model* is reproducible, prior *state* is not, and need not be.

## 4. Transaction and partial-publish safety (D-recommendation)
RTDB multi-location PATCH is atomic (all paths or none). Recommended model, simplest first:

1. **Single PATCH per publish whenever the payload is ≤ 2 MB.** This covers every Brain except Clarity once duplicates are removed: Biological ≈1.2 MB with profiles, Intelligence ≈1 MB, Water Temp ≈1.1 MB, Wind < 1 MB, Lake (pilots) small. The `publication` manifest goes in the same PATCH → summary and detail can never disagree.
2. **Chunked publishes (> 2 MB — Clarity today: ≈3.4 MB of states + profiles for 621 lakes, plus snapshot copies)** use **manifest-last**:
   - write `/brains/{id}/publication/status = "PARTIAL"` with the new `publishId` *first*;
   - write chunks; every per-lake artifact carries `lineage.publishId`;
   - write the final `publication` (status `COMPLETE`, fingerprints) *last*;
   - a failed chunk stops the run (no "continue after failure" — Clarity must change) and leaves status `PARTIAL`;
   - consumers treat a lake whose `publishId` ≠ `publication.publishId` while status is `PARTIAL` as "previous publish" (consistent per lake, which is the contract's unit).
3. **No double-buffering / pointer swap in RTDB.** An A/B pointer (`/speciesProfiles@v/{n}` + `current`) would double storage and force every reader to dereference; the problem it solves (cross-path consistency) is solved by rule 1 for everything that matters. Revisit only if a Brain's payload legitimately exceeds ~5 MB.
4. **Score/control publisher:** scores + score mirror cleanup + control in one PATCH (≈ 0.25 MB). Pruning activity is a separate, idempotent step.
5. **Wind:** state + fleet slot + registry in one PATCH per run (< 1 MB); today's ≥ 6 PATCHes are the main live partial-publish risk.

## 5. Shadow / review outputs
There is one production RTDB and no dev Engine RTDB. SHADOW-lifecycle Brains may publish to their production paths **only** with `lifecycle: SHADOW` on the registry and `customerPublication: false` (Ops is internal; customers never read RTDB). A *candidate release* that is not yet RELEASED is never written to `sector-brain`; it is built into a `DryRunStore` and diffed (`--shadow-release <id> --dry-run --diff`) — the output diff (per-path fingerprints vs current publication) is the review artifact.
