# Sector Intelligence Brain publisher

Publishes the `sector-intelligence` registry, its upstream-brain dependency status, its validation status and per-lake input availability to the Brain RTDB (`sector-brain`). It **evaluates nothing** and never calls `/conditions`.

Contract: `docs/brains/SECTOR_INTELLIGENCE_BRAIN_INTEGRATION.md`.

```
python run.py --plan                 # is a publish warranted? (GET only)
python run.py --dry-run --out out/   # build everything from live reads, write out/updates.json, no writes
python run.py --write                # one atomic multi-path update
python -m unittest discover -s tests
```

- **Python:** stdlib only.
- **Credentials:** the gcloud CLI token on a developer machine, or the metadata server on Cloud Run.
- **Scheduling:** none. Scheduling belongs to the future Sector Brain Orchestrator (see `orchestration.py`).
- **`brain_platform.py`:** a verbatim copy of the Water Clarity / Biological platform module. Lift it into a shared module when the Brain platform is unified.
