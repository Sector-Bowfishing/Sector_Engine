"""How many qualifying evenings per month does a field programme get? CAL+H1 METAR only (2026-05-06..2026-10-06; H2 never read).
Qualifying evening at a station: >= 3 hours in 00-06Z (7 pm-1 am CDT) with sustained >= 8 mph; quadrant = circular-mean wind-FROM of those hours.
  python research/field_program_climatology.py OUT.json"""
import json, math, os, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.validate import load_obs
MPH = 0.44704
ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
S, E = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
assert E < datetime(2026, 10, 7, tzinfo=timezone.utc)
cfg = load_config(); obs = load_obs(LocalStore(ROOT), S, E)
quad = lambda d: "N" if d >= 315 or d < 45 else "E" if d < 135 else "S" if d < 225 else "W"
by = defaultdict(lambda: defaultdict(list))
for (sid, h), o in obs.items():
    if S <= h <= E and 0 <= h.hour <= 6 and o["speedMS"] is not None:
        by[sid][h.date()].append((o["speedMS"] / MPH, o["dirFromDeg"]))
dayby = defaultdict(lambda: defaultdict(list))
for (sid, h), o in obs.items():
    if S <= h <= E and 15 <= h.hour <= 23 and o["speedMS"] is not None:
        dayby[sid][h.date()].append((o["speedMS"] / MPH, o["dirFromDeg"]))
def count(days, thr, nmin=3):
    q = defaultdict(int); tot = 0
    for d, hrs in days.items():
        w = [(s, dr) for s, dr in hrs if s >= thr and dr is not None]
        if len(w) >= nmin:
            sx = sum(s * math.sin(math.radians(dr)) for s, dr in w); sy = sum(s * math.cos(math.radians(dr)) for s, dr in w)
            q[quad(math.degrees(math.atan2(sx, sy)) % 360)] += 1; tot += 1
    return tot, q
out = {}
for sid, days in by.items():
    q = defaultdict(int); tot = 0
    for d, hrs in days.items():
        w = [(s, dr) for s, dr in hrs if s >= 8 and dr is not None]
        if len(w) >= 3:
            sx = sum(s * math.sin(math.radians(dr)) for s, dr in w); sy = sum(s * math.cos(math.radians(dr)) for s, dr in w)
            q[quad(math.degrees(math.atan2(sx, sy)) % 360)] += 1; tot += 1
    dt8, dq8 = count(dayby[sid], 8); dt10, dq10 = count(dayby[sid], 10)
    out[sid] = {"lake": cfg["stations"][sid]["lake"], "nights": len(days), "qualifyingEvenings": tot, "perMonth": round(tot / 5.0, 1), "byQuadrantPerMonth": {k: round(v / 5.0, 1) for k, v in sorted(q.items())},
                "afternoons>=8mph(15-23Z) perMonth": round(dt8 / 5.0, 1), "afternoonQuadrants8": {k: round(v / 5.0, 1) for k, v in sorted(dq8.items())},
                "afternoons>=10mph perMonth": round(dt10 / 5.0, 1), "afternoonQuadrants10": {k: round(v / 5.0, 1) for k, v in sorted(dq10.items())}}
json.dump(out, open(sys.argv[1], "w"), indent=1); print(json.dumps(out, indent=1))
