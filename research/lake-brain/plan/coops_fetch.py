"""NOAA CO-OPS daily_mean (IGLD, English) full history by 1-year requests. usage: coops_fetch.py STATION first_year"""
import sys, json
from common import *
OUT = f"{PLAN}/history/coops"; os.makedirs(OUT, exist_ok=True)
st, y0 = sys.argv[1], int(sys.argv[2]); s = {}
for y in range(y0, dt.date.today().year + 1):
    u = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=daily_mean&application=SectorResearch&station={st}&datum=IGLD&units=english&time_zone=lst&format=json&begin_date={y}0101&end_date={y}1231"
    try:
        d = json.loads(get(u, sleep=0.5))
    except Exception as e:
        print("err", y, e); continue
    for r in d.get("data", []):
        if r.get("v"): s[r["t"][:10]] = float(r["v"])
write_daily(f"{OUT}/{st}_daily_mean.csv.gz", s)
ys = complete_years(s); print(st, len(s), min(s), max(s), "complete", len(ys), (ys[0], ys[-1]) if ys else "")
