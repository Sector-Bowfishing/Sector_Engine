"""Daily-mean history for a CO-OPS Great Lakes station (IGLD85, ft) -> history/coops_<ID>_daily_mean.csv.gz. Used for Lake St. Clair (9034052), a wave-1 flagged lake with no history leg."""
import csv, gzip, sys, json, datetime as dt
from common2 import *
def pull(sid, y0=1990):
    daily = {}
    for y in range(y0, 2026, 4):
        b, e = f"{y}0101", f"{min(y+3, 2025)}1231"
        s, d = get_json(f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=daily_mean&application=SectorEngineResearch&begin_date={b}&end_date={e}&datum=IGLD&station={sid}&time_zone=gmt&units=english&format=json", timeout=90, sleep=0.8)
        for r in (d or {}).get("data", []):
            try:
                daily[r["t"][:10]] = float(r["v"])
            except Exception:
                pass
    with gzip.open(f"{B2}/history/coops_{sid}_daily_mean.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily): w.writerow([k, daily[k]])
    return daily
if __name__ == "__main__":
    for sid in sys.argv[1:]:
        d = pull(sid); print(sid, len(d), min(d) if d else None, max(d) if d else None)
