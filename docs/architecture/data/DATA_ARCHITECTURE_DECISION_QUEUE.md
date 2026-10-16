# Data Architecture Decision Queue

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


Each item: **RECOMMENDED** / ALTERNATIVE / WHY NOT. Michael decides; nothing is implemented until approved. IDs `DA-n` avoid colliding with Brain decision queues (Biological D1–D17, Lake, Wind D7–D9…).

| ID | Question (campaign D#) | RECOMMENDED | ALTERNATIVE | WHY NOT the alternative |
|---|---|---|---|---|
| DA-1 | Role of `sector-brain` (D1) | Production serving + control DB (internal: Ops, Brains, Intelligence). Compact, derived, lineage-stamped, bounded. | Keep it general-purpose (research + serving + history) | Research/workflow data is already leaking into Ops reads; history in RTDB inflates every whole-node read; no rollback story |
| DA-2 | Raw/private research (D2) | Private git `Sector_Research` + versioned private bucket `sector-research-private`; **back up now** | Git LFS / Firestore / public research branches | quotas & binaries / no diffs + new DB / public repo |
| DA-3 | Canonical knowledge (D3) | Per-Brain immutable release bundles in private versioned GCS, `latest.json` pointer, authored from the private repo (Biological pattern) | Firestore; RTDB; public repo | Firestore: new DB, weak history/diff. RTDB: no immutability, read-shape cost. Public repo: licensing/presence/privacy |
| DA-4 | Compiled runtime outputs (D4) | `sector-brain`, deterministic from a release, `lineage` + `publication` | Serve profiles from GCS via signed URLs | Ops would need bucket credentials; second serving mechanism |
| DA-5 | Profile path (D5) | **`/speciesProfiles/{speciesId}`** | `/species/{id}/profile` (implemented on branch) | ×10 growth of a wholesale-read collection; identity and big derived artifact mixed |
| DA-6 | Owner of `/species` (D6) | Biological (identity + knowledge summary); Policy owns `policy` child | Neutral "Species Registry" service | an extra owner with no science; Biological already curates identity/taxonomy |
| DA-7 | Environment classification (D7) | One id; `environments` + `environmentsAssessed` + `intelligenceScope` on identity; `/speciesIndexes/{env}`; knowledge tagged by environment; Biological owns all environments | `/species/freshwater`, `/species/saltwater` trees; separate Marine Brain | duplicates identity for multi-environment species; splits ownership of one species |
| DA-8 | `/sources` (D8) | Data-feed registry + health only; one owner per id; literature only in release + profile `evidenceSummary` | Put literature sources in `/sources` | mixes feed health with research; exposes workflow |
| DA-9 | `/validation` (D9) | Summaries only; raw observations/ledgers append-only in buckets | Keep raw observations in RTDB | overwrite risk; read-shape cost; irreplaceable data next to derived data |
| DA-10 | Ops writes (D10) | `/opsPreferences/{uid}` + create-only uid-bound `/requests/{control,review,research}` | Let Ops write decisions directly into Brain nodes | second source of truth; bypasses validators |
| DA-11 | Review submission (D11) | `/requests/review` → owning Brain review tool → review ledger in next release; reviewer = auth uid; agents refused | Reviews stored in RTDB as the canonical ledger | ledger must be in the release so the build is reproducible offline |
| DA-12 | Research requests (D12) | `/requests/research` → research queue → research store; Engine writes outcome | Generic single queue for all request kinds | different consumers, schemas and authority; one queue blurs them |
| DA-13 | Promotion (D13) | DISCOVERED → SUPPORTED → CANDIDATE → RECONCILED → REVIEWED → RELEASED → PUBLISHED, by plane; mapped onto existing vocabularies; VALIDATED orthogonal | New stored stage enum on every claim | duplicates existing `READ_STATUS`/rule status/review vocab (five already exist) |
| DA-14 | Lineage (D14) | `brain-lineage-v1` on every artifact; `publication` manifest; append-only history bucket | Rely on activity feed + Cloud Logging | capped at 80/30 d; cannot reproduce; already insufficient |
| DA-15 | Partial-publish safety | Single PATCH ≤ 2 MB incl. manifest; manifest-last for larger (Clarity); stop on first failed chunk | A/B pointer double-buffer in RTDB | doubles storage, forces dereference in every reader, solves a problem rule 1 already solves |
| DA-16 | Environments | Keep one Engine RTDB; non-prod = `DryRunStore`/read-through; no env var may enable writes; tests refuse real URLs | Create an Engine dev RTDB | costs ongoing sync/drift; dry-run + diff already covers review; revisit when a second writer team exists |
| DA-17 | Writer identity scope | Single bounded publisher identity; specialist identities read-only (see `BRAIN_READ_WRITE_SECURITY_V1.md`); options assessed privately | Rely on code conventions | conventions are not enforcement |
| DA-18 | `/schemaVersion` gate | Populate `/schemaVersion` once so the existing gate works | Delete the gate | the gate is cheap protection against old writers after a schema change |
| DA-19 | `/snapshots` | Retire after readers move to `/lakes/{k}/states` | Keep as a convenience view | 3.4 MB byte-identical duplicate with a misleading `generatedAt` |
| DA-20 | `/control/fleet` vs `/lakeFleet` | Keep `/lakeFleet`, add platform `rollup` child, retire `/control/fleet` | Keep both | two whole-fleet listeners with overlapping data |
| DA-21 | Depth canonical data in public repo | Move to a private release bundle unless Michael confirms it is publishable | Leave in repo | public by default; inconsistent with other Brains |
| DA-22 | Profiles published before review | Allowed only with explicit `reviewState: UNREVIEWED` labelling (today's Biological practice) | APPROVED-only | that is a Biological product decision (its D-queue), not an architecture rule |
| DA-23 | `/requests` retention | 90 days in RTDB, then archived to history bucket | Keep forever in RTDB | unbounded growth |
| DA-24 | App species catalogs | App teams map catalogs to Engine `speciesId` via a Biological-published id map; no second registry | Leave independent | duplicate identity with different ids (C7) |

## Decided by this document unless Michael objects (low risk, reversible)
Naming conventions (architecture §11), UNKNOWN serialization (§12), activity key format, `maxBytes`/`readPattern` declarations, history bucket name.

## D18 — leave alone (working well)
The two write clients; Ops read-only + allowlist rules; Biological release pattern; Lake prediction ledger; Orchestrator V1 content-aware writes + capped ledgers; per-lake slot layout; `/lakeFleet`; apps via Engine HTTP; injected-transport tests; existing ids and paths not listed for retirement.
