# brains/moon — Moon and Night Light Brain

**brainId** `moon` · **lifecycle** CALIBRATION · **registered disabled** (control manifest PARKED, no executor, not in the execution control) · **gated live writer** (approved release + `MOON_WRITE_APPROVED=1`) · customer publication off.

Tonight's moon phase, illumination, moonrise/moonset, sunset/sunrise and civil/nautical/astronomical twilight for every directory lake, plus the on-water darkness class (DARKNESS_RULE_V1). Plan and decisions: `docs/brains/MOON_BRAIN_PLAN.md`. Rules: `BRAIN_OPERATING_CONTRACT.md`. Contract: `contracts/moon-night-light-v1.json`.

```bash
cd brains/moon && python -m pytest -q                                   # domain tests + USNO cross-check + Brain Cert Kit V1
python runtime/run.py --tonight /tmp/tonight.json --date 2026-11-22     # local file only
python runtime/run.py --dry-run /tmp/dry.json                           # RTDB write set, in memory only
python runtime/run.py --write                                           # refused: exit 2 (release NOT_RECORDED), exit 3 without MOON_WRITE_APPROVED=1
```

| Path | What |
|---|---|
| `runtime/moon_brain/ephemeris.py` | sector-moon-v1 port (Schlyter), line for line from `Sources/SectorEngine/Engine/Astronomy.swift` |
| `runtime/moon_brain/events.py` | rise/set/twilight by the USNO / Meeus standard altitudes |
| `runtime/moon_brain/night.py` | tonight's span (local solar noon to noon), fishing window, moonlight presence |
| `runtime/moon_brain/darkness.py` | DARKNESS_RULE_V1; MOON_ONLY when cloud cover is missing |
| `runtime/knowledge/` | packaged lake-directory projection (knowledge release) |
| `tests/fixtures/usno_reference.json` | USNO reference values, retrieved 2026-11-22 |
