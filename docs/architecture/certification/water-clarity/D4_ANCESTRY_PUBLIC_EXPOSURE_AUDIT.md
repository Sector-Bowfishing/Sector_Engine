# D4 ancestry public-exposure audit (PR #26)

**Question:** merging `feat/clarity-algal-warning` @ `03937913` with history makes its whole second-parent history reachable from public `main`. Is every newly reachable object safe for a PUBLIC repository?
**Method:** `git rev-list --objects origin/main..<PR head>` (the PR head at the time of the audit was `b580540d`; the later commit only edits one test line). Every reachable blob was read and scanned deterministically; no values are reproduced here.
**Verdict: `PUBLIC_SAFE`** (classification `INTERNAL_PROPRIETARY` engineering/research of the same class `main` already carries; no secret, credential, customer data, certification threshold, TCEQ or private-catalog material).

## Newly reachable
19 commits (18 branch commits + the merge), all authored by the repository owner; 1,008 objects; 829 blobs; 24.0 MB; 835 paths. No blob over 5 MB.

| Group | Paths | Class |
|---|---|---|
| `docs/data/hydrology/guntersville/**` (replay, pass-pair, rain, zone, stage JSON; `.npz`/`.gz` caches) | 720 (main already holds 327 files under the same directory from Fusion Stages 1–2) | INTERNAL_PROPRIETARY — derived from public USGS/MRMS/NWM inputs for one lake |
| `docs/clarity/**` (stage 3–5 handoffs, pre-registrations, 28 developer-simulator screenshots, DEVELOPMENT-badged) | 44 | INTERNAL_PROPRIETARY — engineering handoffs; screenshots reviewed, no personal data |
| `scripts/hydrology/**` | 22 | INTERNAL_PROPRIETARY — analysis scripts |
| Swift sources/tests, `jobs/lake-surface`, `jobs/clarity-current`, `Package.swift`, `Dockerfile` | ~35 | PUBLIC_SAFE (runtime source, the PR tree) |

## Scan results (patterns over all 829 blobs; binaries checked for key/token/TCEQ markers)
| Check | Result |
|---|---|
| private keys, service-account JSON, Google/AWS/GitHub/Slack tokens, JWT, bearer literals, generic `key=…` secrets | **0** |
| e-mail addresses, phone numbers, private IPs | **0** |
| `TCEQ`, R3.1 certification-bar markers (`ALL_FROZEN_BARS_PASS`, `WEAKEST_CORE_CLASS`, `ACCURACY_CERT`, `FREEZE_STAGE18`), private catalog detail | **0** |
| local filesystem path (`/Users/<name>/…`) | 1 file (`stage3b/validation_spec.json`) — OS user name only; INTERNAL |
| `gs://` bucket identifiers | 6 files: a public product bucket, a public NOAA bucket, and one internal source-staging bucket name in one handoff doc. Names only; no object content, no credentials |
| PDFs / CSV / parquet / logs | 0 |
| customer or user data | none (the only user-flow screenshots are developer-simulator captures) |

## Reasoning and residual risk
- Nothing here is newly *public*: all 835 paths are already reachable on the public `origin/feat/clarity-algal-warning` (and its three ancestor branches) since 2026-09-28/29.
- The merge makes ~24 MB of that history part of `main`'s permanent history. If the owner ever wants these Fusion-stage blobs withdrawn from the public repo, `main` would then keep them reachable; that is a deliberate trade for exact lineage.
- The R3.1/candidate research (the material that was accidentally exposed through `feat/clarity-candidate-shadow` and `campaign/clarity-readiness`) is **not** in this ancestry: `feat/clarity-candidate-shadow` is a descendant of `feat/clarity-algal-warning`, never an ancestor of the PR.

## PR tree recheck
33 paths changed vs `main` (+1 test-line fix): runtime source, tests, job source, deploy scripts, two small runtime region inputs, provenance docs. No `docs/clarity`, no `research/`, no `jobs/clarity-candidate`, no PDF/log/CSV/image, no file over 1 MB; marker scan of the diff: 0 hits.
