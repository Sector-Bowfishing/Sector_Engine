# lake-level-crosscheck (collector, Mac mini / Sector Pulse)

Logs the pool level the Engine shows for a lake next to an independent operator gauge. This is how a lake moves from "unverified" to validated under the owner's Lake bar.

- **Lake Barkley|KY:**
  - **Engine source:** NWPS `KYDK2`, the Kentucky Lake pool (`WaterLevelService.reservoirs`).
  - **Independent gauge:** USACE CWMS LRN `BAHK2-BARKLEY.Elev-Pool.Inst.1Hour.0.dcp-rev`, Barkley Dam pool.
- **Approval:** Sector_Ops #51, 2026-11-11 ~23:40Z, decision 4. It is a 30-day collector under Pulse, so `--until` stops recording after the window.
- **Access:** read-only public GETs. It appends JSON lines under `--data` and never rewrites a stored observation.

```bash
python3 crosscheck.py collect --data /tmp/xc --until 2026-12-12T00:00:00Z
python3 crosscheck.py summarize --data /tmp/xc          # daily-mean agreement, default tolerance 0.25 ft
python -m pytest -q
```
