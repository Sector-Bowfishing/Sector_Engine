# water-clarity-brain

Publishes production Water Clarity into the Brain RTDB (`sector-brain`) for Sector Ops.
It **reads** production (Engine `/lakes` and `/conditions`, `gs://sector-lake-surface`, Cloud Run status)
and writes only Water Clarity's Brain paths. Design, schemas and paths: `docs/brains/WATER_CLARITY_BRAIN_INTEGRATION.md`;
field mapping: `docs/brains/WATER_CLARITY_BRAIN_MAPPING.md`.

```bash
python3 -m unittest discover -s tests -v          # 35 tests, no network
python3 run.py --dry-run --out /tmp/wcb --lakes "Guntersville|AL"
python3 run.py --lakes "Guntersville|AL"           # publish (gcloud credentials)
python3 run.py                                     # whole directory (~40 min at --engine-concurrency 2)
```

`deploy-job.sh` creates the scheduled Cloud Run job; it has **not** been run.

**Private overlay.** `catalog.json` is public, so it holds status-level facts only.
- Detailed candidate-research results come from a private overlay: `catalog.private.json` beside this file (gitignored), or `CLARITY_PRIVATE_CATALOG=<path|gs://…>`.
- Without the overlay, the Brain publishes status-level facts and reports `catalogDetail: PUBLIC_ONLY`.
- Never commit the overlay.
