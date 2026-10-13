"""Evaluate whether USGS gage height (00065) + site altitude (alt_va, gage datum) yields a usable absolute lake elevation.
Calibration set: every USGS site in the wave-1 catalog that reports BOTH an absolute lake-elevation parameter (00062/62614/62615/62616/72020/72022) and 00065,
live in the last 14 days. offset error = (00065 + alt_va) - elevation, in ft. Output: binding2/usgs_stage_calibration.json (+ summary printed)."""
import json, collections, statistics, datetime as dt
from common2 import *
from providers import usgs_iv_batch, summarize

ELEV = ["00062", "62614", "62615", "62616", "72020", "72022"]
sites = collections.defaultdict(dict)
for l in open(f"{BIND}/catalog.jsonl"):
    r = json.loads(l)
    if r["prov"] != "usgs":
        continue
    s = sites[r["station"]]
    s.setdefault("fam", set()).add(f"{r['family']}:{r['param']}")
    s["alt"] = r["extra"].get("alt"); s["datum"] = r["datum"]; s["end"] = max(s.get("end", ""), r["end"] or ""); s["name"] = r["name"]; s["stype"] = r["stype"]
both = [k for k, v in sites.items() if any(f.startswith("elev") for f in v["fam"]) and "stage:00065" in v["fam"] and v["end"] >= "2026-09-01"]
res = {}
for i in range(0, len(both), 10):
    b = both[i:i + 10]
    d = usgs_iv_batch(b, ELEV + ["00065"], days=14)
    for s in b:
        dd = d.get(s, {})
        gh = dd.get("00065")
        el = [(p, v) for p, v in dd.items() if p in ELEV and v]
        if not gh or not el:
            continue
        e = summarize(el[0][1]); g = summarize(gh)
        try:
            alt = float(sites[s]["alt"])
        except Exception:
            alt = None
        res[s] = dict(name=sites[s]["name"], stype=sites[s]["stype"], altDatum=sites[s]["datum"], alt=alt, elevParam=el[0][0], elevMed=e["med_ft"], ghMed=g["med_ft"],
                      err=(round(g["med_ft"] + alt - e["med_ft"], 2) if alt is not None else None))
json.dump(res, open(f"{B2}/usgs_stage_calibration.json", "w"), indent=1)
errs = [v["err"] for v in res.values() if v["err"] is not None]
print("sites with both live:", len(res), "with alt:", len(errs))
ab = sorted(abs(x) for x in errs)
print("abs err quantiles (ft):", [round(ab[int(q * (len(ab) - 1))], 2) for q in (0.25, 0.5, 0.75, 0.9)], "within 0.5 ft:", sum(1 for x in ab if x <= 0.5), "within 2 ft:", sum(1 for x in ab if x <= 2), "of", len(ab))
for s, v in sorted(res.items(), key=lambda kv: abs(kv[1]["err"] or 9999)):
    print(s, v["name"][:38], v["altDatum"], v["alt"], v["elevParam"], v["elevMed"], v["ghMed"], v["err"])
