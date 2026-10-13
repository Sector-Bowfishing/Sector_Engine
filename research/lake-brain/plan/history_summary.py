"""Summaries of the history extension (counts, shares, agreement metrics) -> docs/research/lake-brain/data/history_extension_summary.json"""
import json, statistics, collections, csv
from common import *
r = json.load(open(f"{PLAN}/history_ext_results.json"))
core = lambda x: x["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED")
S = {}
for tag, f in (("core", core), ("flagged", lambda x: not core(x)), ("all71", lambda x: True)):
    rs = [x for x in r if f(x)]
    ext = [x for x in rs if x["status"] == "EXTENDED" and x["newClass"] == "SUFFICIENT"]
    S[tag] = {"targets": len(rs), "newlySufficient": len(ext), "pilotsAlreadyCounted": sum(1 for x in rs if x["status"] == "PILOT_COMPOSITE"),
              "fromNone": sum(1 for x in ext if x["priorClass"] == "NONE"), "fromLimitedOrInsufficient": sum(1 for x in ext if x["priorClass"] != "NONE"),
              "ge10y": sum(1 for x in ext if int(x["completeYears"]) >= 10), "ge15y": sum(1 for x in ext if int(x["completeYears"]) >= 15),
              "stillLimited": sum(1 for x in rs if x["status"] == "NOT_EXTENDED" and x["priorClass"] in ("LIMITED", "INSUFFICIENT")),
              "stillNone": sum(1 for x in rs if x["status"] == "NOT_EXTENDED" and x["priorClass"] == "NONE"),
              "bySource": dict(collections.Counter(x["sources"].split(":")[0] for x in ext))}
live = [x for x in r if x.get("liveDays")]
S["liveAgreementNWPS"] = {"lakes": len(live), "medianMAEft": statistics.median(x["liveMaeFt"] for x in live), "maxMAEft": max(x["liveMaeFt"] for x in live),
                          "within0.05ft": sum(1 for x in live if x["liveMaeFt"] <= 0.05), "datumShifted": [x["lake"] for x in r if "constant" in (x.get("note") or "")]}
S["usgsOffsets"] = [{"lake": x["lake"], "agreement": x["agreement"]} for x in r if "usgs:" in (x.get("sources") or "") and x.get("agreement")]
cad = []
for x in r:
    try: c = json.loads(x.get("hadsCadence") or "{}")
    except Exception: c = {}
    for lid, m in c.items():
        if "first" in m: cad.append((x["lake"], lid, m["first"]["readingsPerDay"], m["first"]["modalLocalHour"], m["last"]["readingsPerDay"]))
S["hadsCadence"] = {"lakes": len(cad), "firstYearAtMost2PerDay": sum(1 for c in cad if c[2] <= 2.5), "firstYearHourly": sum(1 for c in cad if c[2] >= 20), "rows": cad}
json.dump(S, open(f"{DOCS_DATA}/history_extension_summary.json", "w"), indent=1)
print(json.dumps(S, indent=1)[:2500])
