"""Directory fullPoolFt suspects: bound lakes whose own multi-year history (>=5 complete years) never gets within 10 ft below the directory full pool at the 99th percentile
(flood-control pools legitimately exceed it, so high values are not flagged), or natural-surface lakes whose median is more than 10 ft from it. These are candidate data-quality errors in the directory (or local-datum/regulated-pool differences), not binding errors.
Output: binding2/fp_suspects.json"""
import json, csv
from common2 import *
import history2 as H, envelope_promote as EP
out = json.load(open(f"{B2}/assembled_v2.json"))
res = []
for r in out:
    if r["bindingStatus"] not in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG", "VERIFIED_ENVELOPE") or not r.get("histSeries") or r["fullPoolFt"] in (None, ""):
        continue
    hp = None
    label, d, c = None, None, None
    p = EP.hist_file(r["histSeries"])
    d = H.load_daily(p)
    if not d:
        continue
    e = EP.envelope(d, float(r["fullPoolFt"]))
    if e and (e["d99"] < -10 or (r["poolBasis"] == "naturalSurface" and abs(e["p50"] - float(r["fullPoolFt"])) > 10)):
        res.append(dict(lakeId=r["lakeId"], fullPool=r["fullPoolFt"], basis=r["poolBasis"], p50=e["p50"], p99=e["p99"], d99=e["d99"], years=e["years"], series=r["histSeries"], status=r["bindingStatus"]))
json.dump(res, open(f"{B2}/fp_suspects.json", "w"), indent=1)
for x in sorted(res, key=lambda x: -abs(x["d99"])):
    print(x)
print(len(res))
