# Depth local storage review (2026-10-14)

| | Size |
|---|---|
| Starting (before this reset) | 1.4 GB (after the earlier cleanup of 17.6 GB; original 18 GB) |
| Ending | 1.4 GB (no new bulk was downloaded this session; verification used KB-scale GET calls) |
| Reclaimed this session | 0 (nothing rebuildable remained unjustified) |
| Review threshold | 5 GB directory / 2 GB single dataset: **not reached** |

Largest retained directories and why (all rebuildable or evidence; none above 0.5 GB):
* `terrain/` 419 MB - per-lake TWDB area-capacity `table.txt` and pool polygons (91 lakes) read by the preregistered TWDB validation (`twdb_validate.py` refuses to run without them), `twdb_truth.json`, logs. Rebuild: `research/depth-brain/terrain_twdb_fetch.py` from the TWDB survey index.
* `datum3/` 409 MB - Reclamation TSC survey PDFs and RISE/NWPS/Duke evidence: the evidence behind the pending Reclamation/TVA/Duke requests. Candidate for deletion (rebuildable by URL) once those requests are answered and the rules encoded.
* `datum4/` 383 MB - document sweep evidence (USGS WDR pages, FERC notices, CWMS location records): the evidence behind 19 promoted datum pairings and 5 holds.
* `contour/` 82 MB truth pairs + depth grids; `twdb2/` 80 MB TWDB reports (the preregistration's inputs); `adoption/` 47 MB IENC/Hartwell audit data; `contour2/` 10 MB CWMS rating curves (truth for the failed non-TWDB validation); `venv-test` 28 MB (active test env).

Preserved by rule: manifests and retention records (`MANIFEST.jsonl`, `CLEANUP_2026-10-14.json`), preregistrations (hashes in Git), validation truth, licence records, candidate manifest and its 632 KB input snapshots (committed), all handoffs, repos and worktrees.
Recipe, not warehouse: every deleted dataset has its source URL/script in the ledgers or `MANIFEST.jsonl` `rebuild` field.
Next trim (when answered): `datum3/tsc` (384 MB) after the Reclamation reply; `datum4` chunks after the held pairings are resolved.
