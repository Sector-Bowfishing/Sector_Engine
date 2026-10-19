# Water Clarity — publish-artifact contract (`clarity-publication-v1`)

**Status:** SHADOW. Derived from the Publisher registry (`jobs/brain_platform/sector_brain_platform/publisher/registry.py`: `clarity_specs`, `clarity_bundles`) by `brains/water-clarity/contracts/describe_contract.py --check`; the declaration is `brains/water-clarity/contracts/clarity-publication-v1.json`. Builder: `brains/water-clarity/runtime/publish_artifact.py`. Nothing here is wired into the job's write path; the artifact exists in memory / on local disk only (`run.py --dry-run`).

## One run → one artifact
One Clarity execution builds the multi-path update it would send (`run.py` payload) and re-expresses it as ONE sealed `publish-artifact-v2` bundle `clarity-publication-v1` with three sections, evaluated by the SHADOW Publisher as one atomic plan (`SKIP` or `SHADOW_READY`, or the whole artifact is rejected).

| Section schema | Paths (families) | Notes |
|---|---|---|
| `clarity-lake-state-v1` (`require_freshness`) | `/lakes/{k}/states/waterClarity`, `/lakes/{k}/profiles/waterClarity`, `/lakeFleet/{k}/slots/waterClarity` (+ error children `stale`/`lastError`/`lastErrorAt`), `/lakeFleet/{k}/readiness/waterClarity`, `/lakeFleet/{k}/modelVersions/waterClarity` | no delete family: Clarity never deletes a lake state; scopes `lake-live` / `lake-static` / `fleet-readiness` keep slow parts SKIPping |
| `clarity-registry-v1` | `/brains/water-clarity/{child}` (approved children only), `/validation/water-clarity`, `/health/brains/water-clarity/{status,staleLakeCount}`, `/activity/{event}` (own `-water-clarity-` events) | single delete family `/brains/water-clarity/lastError` (`OPTIONAL_CHILD_CLEARED`); `publication`/`certification` reserved to the Publisher |
| `clarity-source-registry-v1` | `/sources/{id}`, `/health/sources/{id}` for ids Clarity owns (sentinel-2-l2a, usgs-nwis-turbidity, noaa-mrms) | |

Publisher-derived compatibility projections (never Brain-authored): `/snapshots/{k}/latest/waterClarity` (COPY of the lake state) and `/snapshots/{k}/latest/brainVersions/water-clarity` (value of `/brains/water-clarity/version`). Verified reader today: Sector Intelligence (`jobs/sector-intelligence-brain`); Ops reader inventory is NOT yet verified, so the retirement gate keeps the full proof.

## Lineage (truthful; nothing fabricated)
`brainId`, `artifactSchema`, `lifecycle` **CALIBRATION** (== `brain.json` == control manifest), `reviewStatus` **UNREVIEWED**, `validationStatus` **NOT_VALIDATED** (never optimistic), `codeVersion`, `executionId`, `inputFingerprint` (per lake: state type, Engine evaluation time and input sources with observation times, plus the digest of the loaded catalog and the Brain version), `outputFingerprint` (the Publisher's), `generatedAt`, `artifactId` (content address). `knowledgeRelease` / `manifestRef` / `manifestSha256` = **NONE** (Clarity has no canonical versioned release or manifest; the catalog digest is in the input fingerprint). `consumed` is present only when the platform recorder really recorded RTDB reads; **GCS/HTTP reads are not recorded, so it is absent (= unknown), never `[]`** — see the platform-debt item `GCS_HTTP_LINEAGE_PLATFORM_DEBT`.

## Freshness (TIME model)
Four times stay apart: satellite scene observation (`freshness.evidenceObservedAt`, newest scene across lakes; gauge reading times are UNKNOWN in the Engine payload and never substituted); the Engine evaluation the estimate restates (`inputGeneratedAt`); the Brain's generation time (`lineage.generatedAt`); publication (the Publisher's record). `staleAfter` = earliest (Engine evaluation + the existing `staleAfterHours` 26); status `FRESH` / `STALE` (an evaluation older than 26 h at generation) / `UNAVAILABLE` (every lake unavailable) / `UNKNOWN` (no evaluation time at all). The 14-day satellite window stays per lake inside each state. `lastSuccessfulRun` / `lastSuccess` are process history and never enter freshness (tested).

## Determinism and volatility
No clock, no randomness, no I/O in the builder (tested): same updates + same context → byte-identical artifact. Volatile contract `clarity-volatile-v1` (minimal, data): `inputAgeHours`, `satelliteAgeHours`, `nextCheckAt`, `freshUntil`, `lastUpdatedAt`, `lastFetchAt`, `updatedAt`, and the two transitional registry paths `updatedAt` / `lastSuccessfulRun`. The Engine's own evaluation time is deliberately **not** volatile: a new Engine evaluation is a new input, so the next artifact is `SHADOW_READY` rather than `SKIP` (costless in shadow).

## Rejections proven (Publisher)
Wrong brain / wrong bundle / wrong section family; another Brain's slot (`CROSS_DOMAIN_PATH`); `/scores/water-clarity`; Publisher-reserved children (`RESERVED_PATH`); whole-node replacement (`BRAIN_NODE_REPLACEMENT`); Orchestrator-owned `/health/jobs/*`; platform-derived snapshot copies (`PLATFORM_DERIVED_PATH`); production lifecycle without approval; missing freshness on the lake-state section; null `SET`; deleting a lake state. The builder itself fails closed on any path no registration covers.
