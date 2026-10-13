"""USGS NWIS series catalog (period of record per parameter) for USGS-target sites and NWPS usgsId relays."""
import json, csv, io, re
from common import *
T = json.load(open(f"{PLAN}/targets.json"))
meta = json.load(open(f"{PLAN}/raw/nwps_meta.json"))
sites = {}
for t in T:
    if t["provider"] == "usgs": sites[t["station"]] = t["lakeId"]
    if t["provider"] == "nwps":
        u = meta.get(t["station"], {}).get("usgsId")
        if u: sites[u] = t["lakeId"]
out = {}
for s, lake in sites.items():
    try:
        txt = get(f"https://waterservices.usgs.gov/nwis/site/?format=rdb&sites={s}&seriesCatalogOutput=true&siteStatus=all", accept="text/plain", sleep=0.5)
    except Exception as e:
        out[s] = {"lake": lake, "error": str(e)}; continue
    lines = [l for l in txt.splitlines() if l and not l.startswith("#")]
    hdr = lines[0].split("\t"); rows = [dict(zip(hdr, l.split("\t"))) for l in lines[2:]]
    ser = [(r["parm_cd"], r["stat_cd"], r["data_type_cd"], r["begin_date"], r["end_date"], r["count_nu"]) for r in rows
           if r["parm_cd"] in ("00062", "62614", "62615", "62616", "62617", "62619", "72020", "72214", "72215", "00065", "30211", "72036", "00054", "62620", "72275")]
    out[s] = {"lake": lake, "name": rows[0]["station_nm"] if rows else None, "series": ser}
    print(s, lake, out[s]["name"], ser, flush=True)
json.dump(out, open(f"{PLAN}/raw/usgs_catalog.json", "w"), indent=1)
