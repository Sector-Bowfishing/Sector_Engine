"""Wave-1 STAGE_ONLY lakes: can gage height + site altitude (alt_va, the gage datum) be promoted to an absolute elevation? (rule v1.1-S, flagged only)
Reads the wave-1 chosen STAGE_ONLY rows, the USGS catalog altitude, and the probe results (30-day median stage)."""
import csv, json
from common2 import *
ver = [r for r in csv.DictReader(open(f"{BIND}/verified.csv")) if r["bindingStatus"] == "STAGE_ONLY"]
probes = json.load(open(f"{BIND}/probe_results.json"))
alt = {}
for l in open(f"{BIND}/catalog.jsonl"):
    r = json.loads(l)
    if r["prov"] == "usgs" and r["family"] == "stage":
        alt[r["station"]] = (r["extra"].get("alt"), r["datum"], r["name"])
out = []
for r in ver:
    row = dict(lakeId=r["lakeId"], prov=r["provider"], station=r["station"], name=r["stationName"], stageMed=r["medFt"], fullPool=r["fullPoolFt"], basis=r["poolBasis"], derived=None, delta=None, verdict="")
    fp = float(r["fullPoolFt"]) if r["fullPoolFt"] else None
    if r["provider"] == "usgs":
        a, dm, nm = alt.get(r["station"], (None, None, None))
        try:
            a = float(a)
        except Exception:
            a = None
        row.update(alt=a, altDatum=dm)
        if a is not None and a != 0 and dm and r["medFt"]:
            row["derived"] = round(float(r["medFt"]) + a, 2)
            if fp:
                row["delta"] = round(row["derived"] - fp, 2)
                row["verdict"] = "plausible(|d|<=8)" if abs(row["delta"]) <= 8 else "weak(|d|<=25)" if abs(row["delta"]) <= 25 else "fail"
        else:
            row["verdict"] = "no usable altitude/datum"
    else:
        row["verdict"] = "non-USGS stage (needs provider datum offset)"
    out.append(row)
json.dump(out, open(f"{B2}/stage_plus_alt.json", "w"), indent=1)
for x in out:
    print(f"{x['lakeId'][:30]:30} {x['prov']:5} {x['station'][:16]:16} stage={x['stageMed']:>8} alt={x.get('alt')} {x.get('altDatum')} derived={x['derived']} fp={x['fullPool']} d={x['delta']} {x['verdict']}")
