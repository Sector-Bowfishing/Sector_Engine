"""Cross-checks of tier-1 (CWMS/A2W) conservation-pool levels against independent tier-2 sources: NWPS normalThreshold and TWDB conservation pool. Writes docs data/plan_crosscheck.json"""
import csv, json, re
from common import *
import plan_evidence as pe
D, poly, V, nid = pe.load_lakes(); locs, lvl = pe.load_cwms(); a2w = pe.load_a2w()
ev = {r["lakeId"]: r for r in csv.DictReader(open(f"{DOCS_DATA}/plan_flood_evidence.csv"))}
nw = json.load(open(f"{PLAN}/raw/nwps_meta.json")); tw = json.load(open(f"{DATA}/binding/raw/twdb/recent-conditions.json"))
def topcon(codes):
    vals = []
    for part in codes.split("|")[0].split(";"):
        part = part.strip()
        if ":" not in part: continue
        o, c = part.split(":", 1)
        for key, L in ((o, lvl.get((o, c), [])), (o, a2w.get((o, c), {}).get("levels", []))):
            for l in L:
                if pe.TOPCON_RX.match(l["label"]) and l["ft"]: vals.append(sum(l["ft"]) / 2 if l["ft"][0] == l["ft"][1] else None)
    vals = [v for v in vals if v]
    return vals
out = []
for lid, e in ev.items():
    if e["tier2Source"] and e["matchedProject"]:
        t1 = topcon(e["matchedProject"])
        if t1 and e["tier2ConsPoolFt"]:
            t2 = float(e["tier2ConsPoolFt"])
            d = min(abs(x - t2) for x in t1)
            out.append({"lake": lid, "tier2": e["tier2Source"], "tier2Ft": t2, "tier1TopConsFt": round(min(t1, key=lambda x: abs(x - t2)), 2), "diffFt": round(d, 2)})
agree = [o for o in out if o["diffFt"] <= 3]
res = {"pairs": len(out), "within1ft": sum(o["diffFt"] <= 1 for o in out), "within3ft": len(agree), "rows": out}
json.dump(res, open(f"{DOCS_DATA}/plan_crosscheck.json", "w"), indent=1)
print(res["pairs"], res["within1ft"], res["within3ft"]); [print(o) for o in out]
