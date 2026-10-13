"""G3/G4 fleet summary from fleet_fetch.json + Lake Brain geometry confidence + directory."""
import csv, json, os, sys, collections
import numpy as np
D = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/")
fleet = {r["id"]: r for r in json.load(open(sys.argv[1]))}
flags = {r["id"]: r for r in csv.DictReader(open(D + "geometry/lake_geometry_flags.csv"))}
dirx = json.load(open(D + "directory_lakes_2026-10-13.json"))["lakes"]
ids = [l["id"] for l in dirx]; st = {l["id"]: l["state"] for l in dirx}
frozen = set()
import glob, gzip
for f in glob.glob(os.path.expanduser("~/Library/Caches/sector-wind/national-fetch/tables/*.gz")):
    d = json.load(gzip.open(f)); frozen.add(d["directory"]["name"] + "|" + d["directory"]["state"])
frozen |= {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}
out = collections.OrderedDict()
out["directoryLakes"] = len(ids)
poly = [i for i in ids if i in fleet]; out["withEnginePolygon"] = len(poly)
ok = [i for i in poly if fleet[i].get("ok")]; out["polygonFetchComputed"] = len(ok)
conf = collections.Counter(flags[i]["confidence"] for i in ids if i in flags); out["geometryConfidence(all621)"] = dict(conf)
good = [i for i in ok if flags[i]["confidence"] in ("HIGH", "MEDIUM")]; out["fetchComputed_and_confidenceHIGH_or_MEDIUM"] = len(good)
hi = [i for i in ok if flags[i]["confidence"] == "HIGH"]; out["fetchComputed_and_confidenceHIGH"] = len(hi)
out["frozenTables(profiled)"] = len(frozen & set(ids))
out["newlyCoveredBeyondFrozen(HIGH|MEDIUM)"] = len(set(good) - frozen)
out["newlyCoveredBeyondFrozen(HIGH)"] = len(set(hi) - frozen)
out["rasterResolutionM_median/p90/max"] = [float(np.median([fleet[i]["res"] for i in ok])), float(np.percentile([fleet[i]["res"] for i in ok], 90)), float(max(fleet[i]["res"] for i in ok))]
out["lakes_res_gt_40m"] = sum(fleet[i]["res"] > 40 for i in ok)
p90 = {i: max(fleet[i]["p90FetchByDir"]) for i in ok}
bins = [(0, 300, "pond-like (max p90 fetch < 300 m)"), (300, 1000, "300 m-1 km"), (1000, 3000, "1-3 km"), (3000, 10000, "3-10 km"), (10000, 1e9, ">10 km")]
out["maxP90FetchBins(good)"] = {lab: sum(lo <= p90[i] < hi_ for i in good) for lo, hi_, lab in bins}
# class shares at reference winds across good lakes
for mph in ("8", "12", "18"):
    out[f"meanClassShare@{mph}mph(good)"] = {k: round(float(np.mean([fleet[i]["classShare"][mph][k] for i in good])), 3) for k in ("LOW", "MODERATE", "HIGH")}
    out[f"lakes_with_>=10%_HIGH@{mph}mph(good)"] = sum(fleet[i]["classShare"][mph]["HIGH"] >= 0.10 for i in good)
# G4 monotonicity: shares across speeds must increase HIGH and decrease LOW
mono = sum(all(fleet[i]["classShare"]["8"]["HIGH"] <= fleet[i]["classShare"]["12"]["HIGH"] <= fleet[i]["classShare"]["18"]["HIGH"] for _ in [0]) for i in ok)
out["G4_monotone_HIGH_share_8<=12<=18"] = f"{mono}/{len(ok)}"
# dominant exposure direction distribution
NAMES = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
dom = collections.Counter(NAMES[int(np.argmax(fleet[i]["p90FetchByDir"]))] for i in good); out["dominantP90Dir(good)"] = dict(dom.most_common())
out["AK_HI_lakes"] = {s: sum(st[i] == s for i in ids) for s in ("AK", "HI")}
out["failed_polygon_fetch"] = [i for i in poly if not fleet[i].get("ok")]
out["noPolygon"] = [i for i in ids if i not in fleet]
print(json.dumps(out, indent=1)); json.dump(out, open(sys.argv[2], "w"), indent=1)
