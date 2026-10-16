# Moved: `jobs/wind-hourly` → `brains/wind/`

**Status: RETIRED (Repository Phase 2, 2026-10-15).** The Wind Brain's permanent home is [`brains/wind/`](../../brains/wind/README.md). Nothing here is code, an entrypoint or a deploy unit; there is no second Wind implementation.

| Was | Now |
|---|---|
| `main.py`, `lakes.json`, `requirements.txt`, `sector_wind/` | `brains/wind/runtime/` (production package; research-only modules moved to `brains/wind/research/tools/sector_wind_research/`) |
| `tests/` | `brains/wind/tests/` (+ research-tool tests in `brains/wind/research/tools/tests/`) |
| `research/`, `check-live.sh` | `brains/wind/research/tools/` |
| `Dockerfile`, `deploy-job.sh`, `.gcloudignore`, `read_service/` | `brains/wind/deploy/` |
| `BRAIN.md`, `SESSION_CLOSEOUT.md` | `brains/wind/docs/` (rules: `brains/wind/BRAIN_OPERATING_CONTRACT.md`) |

The Cloud Run job name `wind-hourly`, its schedule and its deployed image are unchanged (the job name is not a repository path). This pointer retires with the other pointer READMEs in Repository Phase 7.
