# Sector — unified eight-Brain research campaign & development cleanup — Session Record (sanitized)

```text
Standards: Rehtac Cortex 2.3.0 @ 8955840 (mission pin); hygiene also checked with Cortex 2.4.0 @ 054131f (research-check, worktree-check), pack sector/engine
Date: 2026-10-22 · Public repository: this record holds aggregate outcomes only; research content stays in the private research workspace.
```

**Nothing in production was changed:**
- no Firebase writes;
- no deploys or schedule changes;
- no score, rubric or release-pointer changes;
- no knowledge promotion.

The Engine changes are PR #49 only: Lake research tools read the canonical research workspace, and one architecture-debt entry was resolved.

## Storage and worktree cleanup

**Research consolidation:**
- The legacy research hierarchy (3.6 GB) was consolidated into the nine canonical research folders. Each was first backed up to the private research bucket and verified (checksums-only dry-run with 0 differences; object counts equal). The legacy hierarchy is removed.
- Every folder now has a `README.md`, a `manifest.json` with DEV-05 retention classes, and a closeout record. Cortex `--closeout` checks report 0 findings.

**Worktrees:**
- 77 git worktrees were retired with `git worktree remove` (no force, no `rm`). Every branch was kept. Six branches that exist only locally are preserved as verified git bundles in the private backup.
- 16 remain: 2 main checkouts, 10 active, 2 KEEP_UNIQUE (bundled), 2 KEEP_DIRTY (preserved).

**Local data removed only after verified recoverability (DEV-07):**
- **Duplicate Wind staging:** 1.4 GB.
- **Legacy Wind caches:** 2.4 GB, backed up first.
- **Git-ignored Water Clarity stage data:** 53 GB. Recoverability was proven:
  - the archive tier A SHA-256 matches its recorded value;
  - 38,167 of 38,167 recorded per-file hashes match;
  - the rest is public, re-fetchable data or rebuildable environments.
- **Build caches** inside retired worktrees: about 46 GB.
- **Total disk recovered:** about 103 GB.

**Production Mac dependency:** none. `research-check --repo` flags one file in a deployed runtime path, and it is a guard regex that *rejects* Mac paths. All other hits are research tools.

## Research outcomes

All candidates were scored with the existing rubrics and are not official. Each candidate is packaged in its private workspace with claims, sources, validation, applicability, failure cases, hashes and reviewer requirements.

| Brain | Baseline | Candidate | Note |
|---|---|---|---|
| Fish | capability v2: 8 targets 6.81 / 26 assessed 3.77 | 7.24 / 6.15 | 47 new rules, mostly LOW confidence. The rubric measures behaviour coverage, not evidence strength. Reference case BB-REF-01 regresses (owner decision) |
| Wind | certification 3.3; capability v2 6.7; BWIS 5.4 | unchanged | Remaining points need the sealed holdout (2027-01-01) or field observations |
| Water Clarity | research certification 8.0 | unchanged | Calibrated range and confidence documented. The production rain-decay model showed no skill nationally |
| Lake | 3.0 (uncapped 6.2) | unchanged | Interim prospective ledger read (rates only, as pre-registered); cluster-robust hold-out re-analysis |
| Water Temperature | 3.0 | unchanged | Independent per-lake reproduction (12,515 lake-days). Pre-registered interval candidate passed; bias correction failed |
| Depth | no official score (research 5.05) | unchanged | Level-sensitivity derivation on 107 rated lakes; field and datum gates remain |
| Vegetation | no official score (research 2.84) | unchanged | Fresh independent truth prepared but **not** evaluated (single-use holdout = owner decision) |
| Sector Intelligence | 4.8 | unchanged | Candidate recommendation contract and reference implementation. Exhaustive tests prove missing data never raises a rating |

**Field validation:** protocols and empty prediction ledgers are prepared for every Brain. No observations were invented, and no validation is marked complete.

## Owner decisions

- **Knowledge and validation:** release approvals (M-3, G-1); V-1; CLARITY-PRO-001; Fish D-1 to D-3; spending the vegetation holdout; field-campaign starts.
- **Research branches:** pushing or keeping the bundled local-only research branches. The repository is public, so they stay bundled until decided.
- **Duplicates:** removing intentional duplicates (deletion gated).
