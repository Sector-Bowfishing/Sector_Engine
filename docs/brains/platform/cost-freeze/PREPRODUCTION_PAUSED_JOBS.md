# Pre-Production Paused Jobs (restore register)

Paused **2026-10-14 ≈ 05:12Z** by the Brain Platform lane under the cost freeze. Nothing was deleted: every scheduler job, Cloud Run job, image, bucket and ledger still exists. Pre-change configs are in `snapshots/` (taken 05:11Z). Restoring any job is **one command**. **Do not restore without the gate in §3** (Model v1 policy).

## 1. Register
| Job | Previously | Schedule / tz | Target | Last image / revision | Reason paused | Reactivation condition |
|---|---|---|---|---|---|---|
| `brain-orchestrator` | ENABLED | `50 * * * *` UTC | Cloud Run job `brain-orchestrator` | gen 8, commit `5fd727effa4a`, sha256:23ceb4d9… | no Brain is customer-production; hourly cycle also started `lake-brain` (8.4/day) and `water-temp-brain` (4.7/day) and rewrote ~620 control paths per cycle | an approved activation proposal for a Brain approaching PRODUCTION_READY (`SECTOR_BRAIN_MODEL_V1.md` §Activation gate); for development run it manually |
| `water-temp-tva-archive` | ENABLED | `20 * * * *` UTC | `water-temp-tva-archive` | gen 2, sha256:f2e45516… | advances no defined readiness gate; Lake Brain falls back to a flagged 24 h trend | Water Temp/Lake owner names a gate that needs TVA discharge history (cascade/tailwater feature) or Michael chooses to buy the history (queue C-3) |
| `lake-surface-dispatch` | ENABLED | `0 3 * * *` America/Chicago | `lake-surface-dispatch` → `lake-surface-daily` | dispatch gen 2 `0d7e932f5d0e` | Clarity/Vegetation are not customer-production; heavy job 8×4 vCPU×16 Gi ≈ $3.4–4.8 per run | Clarity readiness test or Vegetation pilot with a named scene window; run manually first |
| `lake-surface-daily` | PAUSED (already) | `0 3 * * *` Chicago | | gen n/a (see snapshots) | unchanged | only via dispatch, manually |
| `hydrology-hourly` | PAUSED (already) | `15 * * * *` UTC | | | unchanged; **do not reactivate for future Biological use** | an approved activation proposal |
| `clarity-current-hourly` | PAUSED (already) | `40 * * * *` UTC | | | unchanged | active Clarity prospective-validation requirement proven with current evidence |
| `clarity-candidate-shadow` | PAUSED (already) | `0 7 * * *` Chicago | | | unchanged | as above |

## 2. Restore commands (one each)
```bash
gcloud scheduler jobs resume brain-orchestrator       --location us-central1
gcloud scheduler jobs resume water-temp-tva-archive   --location us-central1
gcloud scheduler jobs resume lake-surface-dispatch    --location us-central1
```
Schedule, target and OAuth settings were not edited, so `resume` restores the exact previous behaviour. If a scheduler job was ever recreated, its original definition is `snapshots/scheduler-<name>.json`.
**Verify after restoring:** `gcloud scheduler jobs describe <name> --location us-central1 --format='value(state,schedule,scheduleTime)'`.

## 3. Reactivation gate (required — "turn my hourly job back on" is not enough)
Record before resuming:
```
Brain:
Readiness gate it advances:
Why recurring execution is necessary:
Expected monthly cost:
Expected duration:
Stop condition / date:
Cheaper alternatives considered:
```
Append the filled form to this file under "Reactivations" and to the Brain's HANDOFF_INDEX.

## 4. Temporary validation jobs that stay enabled (not paused)
| Job | Gate | Cost | Stop condition | Pause command |
|---|---|---|---|---|
| `wind-hourly` (`5 * * * *` UTC) | Wind live-reliability gate, 30 valid live days (5 of 30; ≈ 2026-11-07) + timed provider archive | ≈ $4.1/mo | gate satisfied (≈ 2026-11-08) → re-decide; or campaign ends | `gcloud scheduler jobs pause wind-hourly --location us-central1` |
| `lake-brain-ledger-daily` (`0 12 * * *` UTC, **new 2026-10-14**) | Lake prospective prediction ledger (90 d for PARTIAL, 12 mo for VALIDATED) | ≈ $0.08/mo | Michael's decision on the Lake validation campaign, or 12-month scoring complete | `gcloud scheduler jobs pause lake-brain-ledger-daily --location us-central1` |

## 5. Reactivations
_None._
