# Sector Intelligence Brain publisher

Publishes the `sector-intelligence` registry, its upstream-brain dependency status, its validation status and per-lake input availability to the Brain RTDB (`sector-brain`). For the five pilot lakes (`evaluation.py` `PILOT_LAKES`) it also publishes a **pilot normalized evaluation** (`intelligence-eval-v1`, `evaluationStatus: EVALUATED_PILOT`) that restates real specialist Brain states with provenance. It produces **no rating, score or recommendation**, no customer consumes it, and it never calls `/conditions`; the customer path is the Engine Conditions Score.

Contract: `docs/brains/SECTOR_INTELLIGENCE_BRAIN_INTEGRATION.md` (read its "Current state on main" note first). Operating contract: `docs/architecture/certification/sector-intelligence/BRAIN_OPERATING_CONTRACT.md`.

```
python run.py --plan                 # is a publish warranted? (GET only)
python run.py --dry-run --out out/   # build everything from live reads, write out/updates.json, no writes
python run.py --write                # one atomic multi-path update
python -m pytest -q                  # what CI runs (33 tests); `python -m unittest discover -s tests` misses the pytest-only test
```

- **Python:** stdlib only.
- **Credentials:** the gcloud CLI token on a developer machine, or the metadata server on Cloud Run.
- **Scheduling:** no scheduler of its own. The Brain Orchestrator runs it in-process (`control_manifest.json` `sector-intelligence`, `executionTarget.kind: in-process`), FINGERPRINT-triggered; the Brain is PARKED.
- **`brain_platform.py`:** a shim that resolves the shared `jobs/brain_platform/sector_brain_platform` package (a deployed job carries a vendored copy). Nothing brain-specific lives in it.
