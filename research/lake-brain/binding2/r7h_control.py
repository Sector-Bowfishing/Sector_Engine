"""Negative control for rule R7h: how often would a series from a DIFFERENT lake pass the +-8 ft p99 envelope test against a lake's directory full pool?
For every lake promoted by R7h (and every wave-1 core lake), count the other bound lakes' >=5y series whose p99 lies within +-8 ft of that lake's fullPoolFt. Output binding2/r7h_control.json"""
import json, statistics
from common2 import *
import history2 as H, envelope_promote as EP
out = json.load(open(f"{B2}/assembled_v2.json"))
ser = {}
for r in out:
    if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_ENVELOPE", "VERIFIED_FLAG") and r.get("histSeries") and r["completeYears"] and int(r["completeYears"]) >= 5:
        p = EP.hist_file(r["histSeries"])
        d = H.load_daily(p)
        if d:
            e = EP.envelope(d, 0.0)
            if e: ser[r["lakeId"]] = e["p99"]
res = {}
for r in out:
    if r["bindingStatus"] == "VERIFIED_ENVELOPE" and r["fullPoolFt"] not in (None, ""):
        F = float(r["fullPoolFt"])
        hits = [k for k, p99 in ser.items() if k != r["lakeId"] and abs(p99 - F) <= 8]
        res[r["lakeId"]] = dict(fullPool=F, others=len(ser) - 1, falseMatches=len(hits), rate=round(len(hits) / (len(ser) - 1), 3))
rates = [v["rate"] for v in res.values()]
S = dict(nPromoted=len(res), nSeries=len(ser), medianChanceRate=statistics.median(rates), maxChanceRate=max(rates), over10pct=sum(1 for x in rates if x > 0.10), per=res)
json.dump(S, open(f"{B2}/r7h_control.json", "w"), indent=1)
print({k: v for k, v in S.items() if k != "per"})
for k, v in sorted(res.items(), key=lambda kv: -kv[1]["rate"])[:12]: print(k, v)
