"""Profile the unbound lakes after wave 1 (binding2 step 1)."""
import csv, json, collections, sys
sys.path.insert(0, "/Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/binding")
from common import *
B2 = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
FEAT = "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv"
feat = {r["id"]: r for r in csv.DictReader(open(FEAT))}
ver = list(csv.DictReader(open(f"{BIND}/verified.csv")))
unb = [r for r in ver if r["bindingStatus"] == "NONE"]
print(len(unb))
lakes = {l["id"]: l for l in load_directory()}
out = []
for r in unb:
    l = lakes[r["lakeId"]]; f = feat.get(r["lakeId"], {})
    out.append(dict(lakeId=r["lakeId"], name=r["name"], state=r["state"], operator=r["operator"], opfam=f.get("operator_family"), hasDam=r["hasDam"], poolBasis=r["poolBasis"],
                    conf=l["poolConfidence"], fullPoolFt=r["fullPoolFt"], apiLevel=l["apiLevel"], usgsGage=l["usgsGage"], areaKm2=f.get("area_km2"), lake_class=f.get("lake_class"),
                    regime=f.get("regime"), reason=r["reason"], lat=l["lat"], lon=l["lon"], nid_height=f.get("nid_height_ft"), states=",".join(l.get("states") or [])))
json.dump(out, open(f"{B2}/unbound_profile.json", "w"), indent=1)
C = collections.Counter
print(C(o["reason"] for o in out))
print("state", sorted(C(o["state"] for o in out).items(), key=lambda x: -x[1]))
print("opfam", C(o["opfam"] for o in out))
print("operator", C(o["operator"] for o in out).most_common(30))
print("hasDam", C(o["hasDam"] for o in out), "poolBasis", C(o["poolBasis"] for o in out))
print("apiLevel", C(o["apiLevel"] for o in out), "usgsGage", C(o["usgsGage"] for o in out))
import statistics
a = [float(o["areaKm2"]) for o in out if o["areaKm2"]]
print("area quantiles", [round(x,1) for x in statistics.quantiles(a, n=10)])
print("area>=10:", sum(1 for x in a if x>=10), ">=5", sum(1 for x in a if x>=5), ">=2", sum(1 for x in a if x>=2))

# ---------------------------------------------------------------- bowfishing relevance (documented heuristic; no popularity data exists)
STATE_W = {s: 3 for s in "AL AR FL GA IL IN IA KS KY LA MI MN MS MO NE NC ND OH OK SC SD TN TX WI VA".split()}
STATE_W.update({s: 2 for s in "CA MD PA NY NJ DE MA WV CO ID WA OR UT NV AZ NM MT WY".split()})
STATE_W.update({s: 1 for s in "AK HI ME NH VT CT RI".split()})


def relevance(o):
    import math
    a = float(o["areaKm2"] or 0.5)
    size = 0 if a < 2 else 1 if a < 5 else 2 if a < 15 else 3 if a < 50 else 4
    st = STATE_W.get(o["state"], 2)
    reg = 1 if (o["hasDam"] == "True" or o["poolBasis"] == "fullPool") else 0
    warm = 0 if (o["state"] in ("AK",) or (o["lake_class"] or "").startswith("N1a")) else 1
    s = size + st + reg + warm
    return s, ("A" if s >= 8 else "B" if s >= 6 else "C")


for o in out:
    o["bowScore"], o["bowTier"] = relevance(o)
json.dump(out, open(f"{B2}/unbound_profile.json", "w"), indent=1)
print("tiers", C(o["bowTier"] for o in out))
print("tier by reason", C((o["bowTier"], o["reason"]) for o in out))
