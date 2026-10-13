"""TWDB Water Data for Texas full-history daily reservoir elevation (public CSV). usage: twdb_fetch.py amistad falcon"""
import sys, io, csv
from common import *
OUT = f"{PLAN}/history/twdb"; os.makedirs(OUT, exist_ok=True)
for slug in sys.argv[1:]:
    txt = get(f"https://www.waterdatafortexas.org/reservoirs/individual/{slug}.csv", accept="text/csv", timeout=120, sleep=1)
    rows = [l for l in txt.splitlines() if not l.startswith("#") and l.strip()]
    rd = csv.DictReader(rows)
    s = {r["date"]: float(r["water_level"]) for r in rd if r.get("water_level") not in ("", None)}
    write_daily(f"{OUT}/{slug}_water_level.csv.gz", s)
    ys = complete_years(s)
    print(slug, len(s), min(s), max(s), "complete years", len(ys), ys[0], ys[-1])
