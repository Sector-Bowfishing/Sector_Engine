# Moved: `jobs/water-clarity-brain` → `brains/water-clarity/`

**Status: RETIRED (Water Clarity Structural Certification V1).** The Water Clarity Brain's (`brainId: water-clarity`) permanent home is [`brains/water-clarity/`](../../brains/water-clarity/README.md). Nothing here is code, an entrypoint or a deploy unit; there is no second Clarity implementation.

| Was | Now |
|---|---|
| `clarity_brain.py`, `run.py`, `brain_platform.py`, `catalog.json` | `brains/water-clarity/runtime/` |
| `tests/` | `brains/water-clarity/tests/` |
| `deploy-job.sh`, `Dockerfile` | `brains/water-clarity/deploy/` |

The Cloud Run job id `water-clarity-brain` (job manifest, never deployed) is not a repository path and is unchanged. This pointer retires with the other pointer READMEs in Repository Phase 7.
