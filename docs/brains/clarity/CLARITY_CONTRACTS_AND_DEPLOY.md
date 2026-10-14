# Clarity — contracts, schedules, deploy and rollback (prepared, nothing activated)

Measured 2026-10-13. Nothing here changes a live schedule, deploys, or touches customer behaviour.

## 1. Schedule inventory and recommended state

| Job | Cadence | Purpose | Provider calls | Observed runtime | Changes state? | No-op guard | Recommendation |
|---|---|---|---|---|---|---|---|
| `lake-surface-dispatch` (scheduler ENABLED) | daily 03:00 CT | STAC metadata query per lake; start heavy job for lakes with a newer usable pass | ~621 STAC queries, no imagery | 100–170 s, 1 vCPU / 512 Mi | decides work only | yes (compares published `latest.json`) | **KEEP** (this *is* the input-driven model) |
| `lake-surface-daily` (scheduler PAUSED; started by dispatch) | on dispatch | Sentinel-2 → clarity field per lake | Sentinel-2 COG reads | 52–75 min, 8 tasks × 4 vCPU × 16 Gi (299 lakes on 2026-10-13) | yes | own "up to date" check + dispatch | **INPUT_DRIVEN** — keep scheduler paused; never re-enable its own cron |
| `clarity-current-hourly` (PAUSED) | hourly (paused) | Guntersville current-regions precompute (Stage 5) | none heavy | 75–160 s | n/a while paused | none | **PAUSE** until decision D4 lands the code on `main`; then INPUT_DRIVEN |
| `clarity-candidate-shadow` (PAUSED) | daily (paused) | private R3.x shadow | private | — | n/a | — | **PAUSE** (research; resume only under a shadow plan) |
| `hydrology-hourly` (PAUSED) | hourly (paused) | catchment rain/discharge for the Guntersville state loader | MRMS, USGS | — | n/a | none | **PAUSE** (nothing customer-visible reads it) |
| `water-clarity-brain` (**not deployed**) | manual | restate production clarity into the Brain | 621 `/conditions` | ≈ 40 min at concurrency 2 | yes | **fingerprint (added)** | **INPUT_DRIVEN**: run ≤ 1×/day after `lake-surface-dispatch` completes; no-op ≈ 1 KB/lake |

Changes recommended (all need authorization): deploy `water-clarity-brain` with a 04:30 CT scheduler once D2 is approved;
no change to any currently running schedule.

## 2. Ops summary contract (`/brains/water-clarity`, existing + proposed)
Existing: lifecycle, readiness counts, state-type / model / satellite / platform / rainfall breakdowns, stale count, health,
`lakeSurfaceRun`. **Proposed additions (not built; Ops owner):** `lastUsableScenePerLake` (pilots), `nextExpectedUpdate`
(next dispatch), `noopRatio`, `sceneFreshnessBuckets` (≤3 d / ≤14 d / older / none), `claimMaturity`
(`{L1: …, L2: …, L3: CANDIDATE_NOT_DEPLOYED}`), `blockers[]`.

## 3. Intelligence contract
May consume: `stateType, kind, readiness, clarityFt (+low/high only when present), trend, satellite.{status,date,ageHours},
freshness.{stale,evidenceStale,freshUntil}, provenance.qualityFlags, engine.model, inputFingerprint`.
Rules: `RAINFALL_MODELED` / `FALLBACK_NEUTRAL` / `UNAVAILABLE` are **non-observational**; `satellite.status≠FRESH` is not
"current"; never request raw imagery or Clarity scoring. Wiring to customer recommendations: **not authorized**.

## 4. Customer-safe contract (prepared, not activated)
```jsonc
{ "asOf": "…ISO…", "ageHours": 3.2,                    // age of the answer, always shown
  "visibilityFt": 4.0, "rangeFt": null,               // range only when validated
  "basis": "ESTIMATE_FROM_RAIN" | "GAUGE_READING" | "SATELLITE_OBSERVATION" | "NONE",
  "confidence": "LOW" | "MEDIUM" | "HIGH",
  "limitations": ["code", …],                         // codes, localised by the client
  "lakeScope": "SINGLE_POINT" | "LAKE_MEDIAN" | "MAP_AVAILABLE" }
```
Distinguishes current observation vs inference, age, confidence, limitations. `basis=NONE` must render "unknown".

## 5. Deploy plan (requires Michael's go; not run)
1. `jobs/water-clarity-brain/deploy-job.sh` (creates SA, Cloud Run job, 04:30 CT scheduler). Set `CLARITY_PRIVATE_CATALOG`
   to the private overlay object (read access for the job SA only).
2. First run: `python3 run.py --lakes "<5 pilots>"` from the Mac; verify `/lakes/{k}/states/waterClarity.inputFingerprint`.
3. Second run, unchanged inputs: expect `report.noop == lakes`, `rtdbBytes` ≪ first run.
4. Fleet run; confirm `/health/brains/water-clarity.status = HEALTHY`.
5. Wire scheduler to run after `lake-surface-dispatch`.

## 6. Rollback plan
- **Pause scheduler:** `gcloud scheduler jobs pause water-clarity-brain --location us-central1` (state stops updating; consumers see `freshness.stale=true` after 26 h — honest).
- **Revert publisher:** redeploy the previous image tag; fingerprint is additive, old readers ignore `inputFingerprint`/`checkedAt`.
- **Force rewrite:** `python3 run.py --force` rewrites every lake regardless of fingerprint.
- **Remove Brain paths:** delete `/lakes/*/states/waterClarity`, `/lakes/*/profiles/waterClarity`, `/lakeFleet/*/slots/waterClarity`, `/brains/water-clarity` (writer-owned; customer paths untouched — the Brain only *reads* production).
- Customer behaviour is unaffected by any of the above (the Brain mirrors `/conditions`; no client reads it).
