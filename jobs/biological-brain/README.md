# Moved: `jobs/biological-brain` → `brains/fish/`

**Status: RETIRED (Fish Structural Certification V1).** The Fish Brain's (`brainId: biological-state`) permanent home is [`brains/fish/`](../../brains/fish/README.md). Nothing here is code, an entrypoint or a deploy unit; there is no second Fish implementation.

| Was | Now |
|---|---|
| `*.py` (bundle loader, publisher runner, rules, features, bands, Biological State pilot, Species Intelligence Profile generator, …), `schemas/`, `tools/` | `brains/fish/runtime/` |
| `tests/` | `brains/fish/tests/` |

The in-process executor id `biological-brain` (job record, orchestrator) is not a repository path and is unchanged. The orchestrator image still stages the runtime as `jobs/biological-brain/` (`jobs/brain-orchestrator/deploy-job.sh` copies it from `brains/fish/runtime`), so a deployed image sees the same layout it always has. This pointer retires with the other pointer READMEs in Repository Phase 7.
