# Depth Brain Source Ledger

Machine-readable ledgers (append-only JSONL, same conventions as Lake Brain research) live in `docs/research/depth-brain/ledger/`:

| file | thread | records |
|---|---|---|
| `contour.jsonl` | contour | {'source': 24, 'finding': 9} |
| `globathy.jsonl` | globathy | {'source': 223} |
| `lead.jsonl` | lead | {'source': 1} |
| `sources.jsonl` | sources | {'source': 40} |
| `terrain.jsonl` | terrain | {'source': 9, 'finding': 11, 'blocker': 3, 'action': 2, 'dataset': 2} |

Record kinds: `source` (id `S-depth-*`, `S-globathy-*`, `S-depth-L*`), `finding`, `blocker`, `action`, `dataset`. Every source record carries URL, access date 2026-10-13, reachability (only endpoints actually fetched are marked reachable), licence, authority 1-7 and an ACCEPTED/LEAD/REJECTED/DEAD_END decision with reason.

Raw data inventory (outside git): `~/Desktop/Development/Sector_Research_Data/depth-brain/MANIFEST.jsonl`.

Licence flags that bind implementation: Florida FWC contours are internal-only (do not redistribute); TWDB maps carry a not-for-navigation/fishing disclaimer; MI, MN, IN, MT, WV, NJ, TN contours have no explicit licence (publish derived metrics only until reviewed); GLOBathy is CC0; USACE/USGS/3DEP are US-federal public.
