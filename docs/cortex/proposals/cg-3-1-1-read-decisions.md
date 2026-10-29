Standards: Rehtac Cortex 3.1.0 @ 9562274

# CG-3.1-1: disposition of the 15 remaining static-scan findings (each checked against code and the component's contract)

None of them justifies adding a Brain reader declaration. Suppressing them was not done; each is classified, and the fix belongs in the scanner or the contract wording, not in permissions.

| Finding (path:line) | What the code really does | Disposition |
|---|---|---|
| `brains/fish/brain.json:32`, `brains/wind/brain.json:44`, `brains/water-clarity/brain.json:41` `/scores/{brain}` | `score.path` names WHERE THE SCORER writes this Brain's score; the Brain reads nothing | Scanner false positive: classify `score.path` as a scorer reference (SC-04), not a read. No reader added |
| `brains/wind/runtime/.../contract.py:52` `AUTHORITATIVE_SCORE_PATH` | constant naming the Scorer's path for a guard | same |
| `brains/wind/.../artifact.py:181` `/sources/{pid}` | builds a lineage `ref` string for a consumed provider dependency; no RTDB access | Scanner false positive (identifier, not a read) |
| `brains/water-clarity/runtime/run.py:141-142` `/jobs/{job_id}` | URL paths of the Cloud Run and Cloud Scheduler APIs, not RTDB `/jobs` | Scanner false positive (googleapis URL) |
| `brains/wind|water-clarity/brain.json` (`/sources/{id}`), `clarity-publication-v1.json:184,220`, `wind-publication-v1.json:148`, `run.py:333` | these list `/sources/{id}` among the Brain's own LEGACY DIRECT WRITES / publication contract paths (provider source records the Brain fetched) | A WRITE mislabelled as a read. Real gap: `fam.sources` has no verified writer. Engine position: provider source records are authored by the fetching Brain, target writer the Publisher (they are in the publication contract); `/health/sources/{id}` is Orchestrator-owned. Keep `fam.sources` NOT_VERIFIED until an evidence source documents it; do NOT register a Brain reader |
| `data_ownership.json:297,306` `/access/opsUsers`, `/access/privateResearchUsers` | the ownership table NAMES these external-administrator paths in order to refuse every platform write to them | Scanner false positive (a deny list is not a read). Tooling fix: ignore entries under a `deny`/`externalAdmin` key |

Scanner changes this implies (Cortex tooling, CG-3.1-2): treat manifest `score.path` as a reference; ignore identifier strings built into lineage `ref`s and googleapis URLs; understand `legacyDirectWrites`; skip deny lists.
