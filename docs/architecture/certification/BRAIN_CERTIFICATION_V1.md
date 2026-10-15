# Brain Certification V1 (`brain-certification-v1`)

**Status:** **APPROVED FOUNDATION** (Michael, 2026-10-14; CERT decisions in `README.md`). Documentation only: nothing has been implemented or changed live.
**Companion standards:** `BRAIN_IDENTITY_AND_LINEAGE_V1.md`, `BRAIN_DATA_CLASSIFICATION_V1.md`, `BRAIN_READ_WRITE_SECURITY_V1.md`, `BRAIN_PATH_OWNERSHIP_V1.md`, `BRAIN_RESEARCH_WORKSPACE_V1.md`, `WIND_CERTIFICATION_ENTRY_CHECKLIST.md`.
**Background evidence:** `docs/architecture/data/` (the read-only inventory and matrices). Where the earlier proposal differs, this standard wins.

## 1. What certification is (and is not)
Architecture certification proves that **one Brain's data is owned, stored, published, secured, versioned and rollback-able the standard way**.

| Certification says | Certification does NOT say |
|---|---|
| The Brain's data has one owner and one canonical home | that the science is right (scientific validation) |
| Its research is in its workspace, with a backup | that field tests passed (field validation) |
| It publishes only through the Publisher, to its own paths, with lineage | how mature its research is |
| Its writes are enforced (rules + IAM), not just conventional | that it is production-ready |
| It can be rolled back reproducibly | that customers may see it (customer promotion) |

A Brain may be `ARCHITECTURE_CERTIFIED_V1` while its lifecycle is still RESEARCH, SHADOW or CALIBRATION, or its claims are NOT_VALIDATED. These axes remain independent; they are defined in `SECTOR_BRAIN_MODEL_V1.md`.

## 2. Strategy
1. One shared standard (this folder).
2. Certify **Wind**.
3. Certify **Fish Brain** (`biological-state`).
4. **STOP.** Run Architecture Audit #1 (§7).
5. If the standard is sound, continue: Lake Brain → Water Temperature → Water Clarity → Depth → Vegetation → Sector Intelligence. The audit may reorder Brains #3 and later, but Sector Intelligence stays last: it should prove that the specialist contracts are clean.
6. Repeat architecture audits as needed. **Fix the shared standard before the next Brain, not during one.**

There is no giant database cleanup. Duplicates and legacy paths are retired Brain by Brain, only through §5 step 12.

## 3. Target architecture (what a certified Brain conforms to)
```
RESEARCH / EVIDENCE          (Brain's workspace + private versioned backup; never in sector-brain)
      ↓
CANONICAL BRAIN RELEASE      (immutable, manifest + hash, provenance)
      ↓
SPECIALIST BRAIN computes a PUBLISH ARTIFACT (schema + lineage + output fingerprint); no production write
      ↓
ORCHESTRATOR PUBLISHER validates: brainId → schema → authorized path family, lifecycle, lineage, release ref,
                                   review/validation status semantics, input/output fingerprints
      ↓
fingerprint unchanged → SKIP          changed → ONE ATOMIC multi-location update
      ↓
sector-brain  ──►  Sector Ops (read) · dependent Brains (read published contracts) · internal consumers
      ↓
customer-serving layers ONLY where separately authorized (unchanged by certification)
```
**The specialist Brain owns domain truth. The Orchestrator Publisher owns the production publishing door.** The Publisher never rewrites scientific meaning. It validates structure and authorization, then publishes exactly the artifact it was given.

**This is the migration target, not the current state.** Today Wind, Fish/Biological, Lake, Water Temperature, Water Clarity, Sector Intelligence and the score/control publisher all write `sector-brain` directly.

## 4. Certification statuses
| Status | Meaning |
|---|---|
| `NOT_STARTED` | no baseline frozen |
| `IN_PROGRESS` | baseline frozen; steps under way |
| `PARTIAL` | some exit evidence (§6) passed; named items open. The Brain stays on its old write path for anything uncovered |
| `BLOCKED` | cannot proceed without an external decision or a dependency (e.g. the Publisher not yet built, or an approval missing). The reason is mandatory |
| `FAILED` | a step showed the standard cannot be met as written. This triggers a shared-standard revision before any further Brain |
| `ARCHITECTURE_CERTIFIED_V1` | all exit evidence A–J present and reviewed by Michael |

Recorded at `/brains/{brainId}/certification` = `{standard: "brain-certification-v1", status, certifiedAt, evidenceRef, reason}` once the Publisher exists. Until then it lives in the certification record in the repo (`docs/architecture/certification/records/{brainId}.md`, created by the Brain's session).

## 5. The 13 steps (same for every Brain)
| # | Step | Output | Changes anything? |
|---|---|---|---|
| 1 | **Freeze baseline** | brainId, display name, lifecycle, current Engine score + score version + score type, current RTDB paths, jobs and schedulers, readers, writers, research locations, private storage, customer exposure, validation status | No |
| 2 | **Inventory local research** | search all of `/Users/mcather/Desktop/Development` plus the Brain's `Sector Research/<brain>` folder. Record files, directories, datasets, sources, results, manifests, releases, validation data, research scripts and duplicates, with byte/dataset/source/release counts and a classification per artifact (`BRAIN_DATA_CLASSIFICATION_V1.md`) | No |
| 3 | **Inventory remote storage** | buckets, releases, manifests (verify hashes), archives, validation stores, snapshots, candidate bundles (read-only) | No |
| 4 | **Inventory database data** | per path: owner, writer, readers, classification, canonical/derived/duplicate/legacy, lifecycle, planned action (`BRAIN_PATH_OWNERSHIP_V1.md` statuses) | No |
| 5 | **Trace actual code** | RTDB readers and writers, Admin SDK/REST use, credential identity *class* per writer, Cloud Run jobs, Cloud Scheduler, local CLIs, Ops readers, Intelligence readers, score and health/control projections. **Code is truth; metadata and `/jobs` declarations are claims to verify** | No |
| 6 | **Define canonical truth** | per dataset: owner, canonical location, accepted version, research vs runtime, rebuildable vs irreplaceable, history and backup requirement | Docs |
| 7 | **Build the publish artifact contract** | schema, lineage, allowed path families, lifecycle, fingerprint rules, validation, material-change semantics | Code (Brain side), no live writes |
| 8 | **Build/verify the Publisher path** | Publisher receives the artifact, validates, SKIPs or atomically publishes, records history, preserves rollback. Shadow first (dry-run diff against current live) | Code; live only with approval |
| 9 | **Enforce security** | specialist cannot write production; Ops cannot write production; Publisher can write only authorized output; cross-domain write denied. Verify **RTDB rules AND IAM/Admin credentials AND the identity actually used** | Rules/IAM only with approval |
| 10 | **Migrate readers** | keep the old path; move readers one at a time to the canonical path; verify; monitor | Reader code |
| 11 | **Score and regression check** | BEFORE and AFTER score under the **same** scoring definition/version; Ops, dependent Brains and Intelligence still work; customer behaviour unchanged; validation and history preserved | No (verification) |
| 12 | **Retire legacy only when safe** | the full retirement procedure (`BRAIN_PATH_OWNERSHIP_V1.md` §5): zero readers, zero writers, rollback preserved, explicit approval | Deletions only with approval |
| 13 | **Certification result** | `ARCHITECTURE_CERTIFIED_V1` / `PARTIAL` / `BLOCKED` / `FAILED` with an explicit reason | Status record |

**Ordering rule:** steps 1–6 are read-only and always complete before any change. Step 12 may be deferred: a Brain can be certified with legacy paths still present if they are classified `LEGACY_READER_PRESENT` or `RETIREMENT_CANDIDATE` and the Brain no longer writes them. Certification does not require deletion.

## 6. Exit evidence (A–J), all required for `ARCHITECTURE_CERTIFIED_V1`
| | Evidence | Pass criterion |
|---|---|---|
| **A** | Identity | brainId, displayName, domain, lifecycle recorded; brainId unchanged |
| **B** | Local research inventory | workspace path, bytes, datasets, sources, releases; **backup status = private versioned copy exists** for everything classified RESEARCH/CANONICAL/OBSERVATION_VALIDATION/HISTORY |
| **C** | Remote storage inventory | buckets, release manifests, verified hashes, archives |
| **D** | RTDB ownership matrix | every path the Brain touches: owner, writer, readers, canonical/duplicate, lifecycle, migration action |
| **E** | Code trace | all readers, writers, schedulers, API paths, credential identity classes; no untraced writer |
| **F** | Security evidence | tested denials: specialist write denied; Ops write denied; cross-domain write denied. Tested success: Publisher authorized write. **Both rules and IAM covered.** (The detailed evidence is private; the repo records only pass/fail) |
| **G** | Publication tests | valid artifact succeeds; same fingerprint SKIPs; invalid schema rejected; cross-domain path rejected; stale input represented correctly; partial publish impossible (or manifest-last proven); rollback verified end to end |
| **H** | Score baseline | before and after, same `scoreType` and `scoreVersion`, and the scope stated; any difference explained by a separately approved scoring change only |
| **I** | Downstream regression | Ops views, dependent Brains, Intelligence (where relevant), and customer path unaffected (demonstrated, e.g. `/conditions` output diff = none) |
| **J** | Final status | the status plus reason, reviewed by Michael |

## 7. Architecture Audit #1 (after Wind + Fish; before Brain #3)
Verify against live reality, not docs:
- the Publisher is the **sole** production writer for the certified Brains; their specialist identities cannot write; Ops cannot write;
- path ownership enforcement works and cross-domain writes fail;
- publication is atomic; fingerprints SKIP unchanged output; rollback works; lineage is complete;
- freshness semantics work (parked Brain ≠ fresh evidence); score semantics are unchanged by the migration;
- local research separation works, the shared folder is used deliberately, and nothing reached into another Brain's private research;
- duplicates are not reappearing, new serving paths are not bloated, Ops read patterns are still efficient, cost has not materially increased;
- customer behaviour did not silently change.

Output: `ARCHITECTURE_AUDIT_1.md` with SOUND / ADJUST (list) / STOP. Any ADJUST is applied to the shared standard before Brain #3.

## 8. Rules that apply during every certification
- **No deletion as part of investigation.** Preserve sources, releases, handoffs, field observations, prospective validation truth, accepted reviews, preregistrations, licence evidence, historical scores, manifests, publication history and irreplaceable local research.
- Scientific and domain truth do not change: moving files or changing the publication path must not move a score.
- No scheduler resumes and no recurring job is created without explicit approval.
- Customer behaviour does not change; the customer path is regression-checked (I).
- Security evidence stays private; the public repo records only outcomes.
- Overall Engine score is **not recomputed** as part of certification (see `BRAIN_IDENTITY_AND_LINEAGE_V1.md` §6).
