# Moved: `jobs/sector-intelligence-brain` → `brains/sector-intelligence/`

**Status: RETIRED (Sector Intelligence migration, Cortex architecture completion 2026-10-20).** The Sector Intelligence Brain's (`brainId: sector-intelligence`) permanent home is [`brains/sector-intelligence/`](../../brains/sector-intelligence/README.md). Nothing here is code, an entrypoint or a deploy unit; there is no second Intelligence implementation.

| Was | Now |
|---|---|
| `run.py`, `sector_intelligence_brain.py`, `evaluation.py`, `orchestration.py`, `brain_platform.py`, `catalog.json` | `brains/sector-intelligence/runtime/` |
| `tests/` | `brains/sector-intelligence/tests/` |
| `docs/architecture/certification/sector-intelligence/BRAIN_OPERATING_CONTRACT.md` | `brains/sector-intelligence/BRAIN_OPERATING_CONTRACT.md` |

The in-process executor id `sector-intelligence-brain` (job record, orchestrator) is not a repository path and is unchanged. The orchestrator image still stages the runtime as `jobs/sector-intelligence-brain/` (`jobs/brain-orchestrator/deploy-job.sh` copies it from `brains/sector-intelligence/runtime`), so a deployed image sees the same layout it always has.
