# water-clarity-h1-shadow (SHADOW lane, Mac mini / Sector Pulse)

Runs the H1 clarity rule beside production. For each lake and season, the rule is the median of the lake's own public Secchi readings from the last five years (bands V0–V3, G0-2). The job writes `h1-shadow.json` under `--out`, and nothing else.

- **Shadow only:** no customer path, no database write, no upload. Serving H1 to customers is a separate owner approval (Sector_Ops #51, 2026-11-11 ~23:40Z, decision 1).
- **Rule:** frozen in the H1 pre-registration (Sector_Ops #40, 2026-11-01). The evidence that it holds on unseen lakes is now-test CL-NOW-1 (Sector_Ops #51, 2026-11-11).
- **Stations:** by default, WQP lake sites within `--radius-mi` of the directory point. `--sites-file` is an optional runtime JSON `{lakeId: [WQP site ids]}` for a lake's own stations, built from its NHD polygon on the runner and **never committed** (research-derived).
- **Comparison:** `--production-dir` is read-only. The newest water-clarity artifact under it supplies production `clarityFt` per lake, compared band for band.

```bash
python3 h1_shadow.py --lakes "Guntersville|AL,Lake Hartwell|SC" --out /tmp/h1 --cache /tmp/h1c
python -m pytest -q
```
