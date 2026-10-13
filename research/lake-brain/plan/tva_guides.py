"""TVA operating-guide for every bound TVA lake: guide-curve swing (max-min over the 365-day guide), zone presence. Writes plan/raw/tva_guides.json"""
import json
from common import *
os.makedirs(f"{PLAN}/raw/tva", exist_ok=True)
out = {}
for r in bound():
    if r["provider"] != "tva": continue
    lid = r["station"]; p = f"{PLAN}/raw/tva/{lid}.json"
    if not os.path.exists(p):
        old = f"{DATA}/history/tva_guides/{lid}.json"
        if os.path.exists(old): open(p, "w").write(open(old).read())
        else:
            txt = get(f"https://www.tva.com/RestApi/operating-guide/{lid}", accept="application/json", ua=BROWSER_UA, sleep=2.5)
            open(p, "w").write(txt)
    d = json.load(open(p)); it = d.get("items", [])
    g = [i["GuideCurve"] for i in it if (i.get("GuideCurve") or 0) > 0]; tz = [i["TopOpZone"] for i in it if (i.get("TopOpZone") or 0) > 0]; bz = [i["BtmOpZone"] for i in it if (i.get("BtmOpZone") or 0) > 0]
    gd = [(i["Day"], i["GuideCurve"]) for i in it if (i.get("GuideCurve") or 0) > 0]
    out[lid] = {"lake": r["lakeId"], "guideDays": len(g), "guideMin": min(g) if g else None, "guideMax": max(g) if g else None, "guideSwingFt": round(max(g) - min(g), 2) if g else None,
                "guideMinDay": min(gd, key=lambda x: x[1])[0] if gd else None, "guideMaxDay": max(gd, key=lambda x: x[1])[0] if gd else None, "topZoneDays": len(tz), "btmZoneDays": len(bz), "topOfGates": it[0].get("TopOfGates") if it else None}
    print(lid, out[lid])
json.dump(out, open(f"{PLAN}/raw/tva_guides.json", "w"), indent=1)
