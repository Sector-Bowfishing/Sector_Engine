"""Wave-1 probe bug fix: probe_usgs picked the parameter with the latest timestamp, tie-broken by sample count, so sites reporting both an absolute lake
elevation (62614/62615/00062/72020...) and gage height (00065) at the same instant were often recorded as 00065 (stage), turning an elevation lake into STAGE_ONLY.
This re-queries every wave-1 USGS probe that chose 00065 and, when an elevation parameter is live in the same window, records the elevation parameter instead.
Output: binding2/probe_results_v2.json = wave-1 probe_results.json with those USGS entries replaced (field 'reprobed': True)."""
import json, copy
from common2 import *
from providers import usgs_iv_batch, summarize

ELEV = ["00062", "62614", "62615", "62616", "72020", "72022"]
pr = json.load(open(f"{BIND}/probe_results.json"))
sites = [v["station"] for k, v in pr.items() if k.startswith("usgs|") and v.get("param") == "00065"]
print("USGS probes that chose 00065:", len(sites))
new = copy.deepcopy(pr); fixed = []
for i in range(0, len(sites), 10):
    b = sites[i:i + 10]
    d = usgs_iv_batch(b, ELEV + ["00065"], days=30)
    for s in b:
        el = {p: v for p, v in d.get(s, {}).items() if p in ELEV and v}
        if not el:
            continue
        best = max(el.items(), key=lambda kv: (summarize(kv[1])["last_t"], summarize(kv[1])["n"]))
        sm = summarize(best[1])
        e = new[f"usgs|{s}"]
        e.update(param=best[0], stats=sm, family="elev", mode="iv", reprobed=True)
        fixed.append((s, best[0], sm["med_ft"], sm["age_h"]))
json.dump(new, open(f"{B2}/probe_results_v2.json", "w"))
print("re-pointed to an elevation parameter:", len(fixed))
