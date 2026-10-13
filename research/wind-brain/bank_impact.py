"""G5/G6: bank-impact vocabulary (DIRECT / CROSS / LEE) vs frozen-CEM exposure on the frozen fetch tables."""
import base64, glob, gzip, json, math, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from polygon_fetch import exposure_class
ang = lambda a, b: abs((a - b + 180) % 360 - 180)
def brg(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lo2 - lo1) * math.cos(la2); x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360
def auc(pos, neg):
    if len(pos) == 0 or len(neg) == 0: return None
    allv = np.concatenate([pos, neg]); r = allv.argsort().argsort() + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
files = glob.glob(os.path.expanduser("~/Library/Caches/sector-wind/national-fetch/tables/*.gz")) + \
        glob.glob(os.path.expanduser("~/Desktop/Development/iOS/sector-wind/Sector/Assets.xcassets/FishIntel/Wind/*/*.windfetch.json.gz"))
res, tot = [], {}
for f in files:
    d = json.load(gzip.open(f)); banks = d["banks"]
    t = base64.b64decode(d["tableBase64"]); n = len(t) // 2
    tab = np.array(struct.unpack(f"<{n}H", t), dtype=float).reshape(len(banks), 120) * 10.0
    keep = [i for i, b in enumerate(banks) if not b.get("belowResolution") and b.get("standoff")]
    if len(keep) < 30: continue
    face = np.array([brg(banks[i]["anchor"], banks[i]["standoff"]) for i in keep]); T = tab[keep]
    cls = {"DIRECT": [], "CROSS": [], "LEE": []}; hi_lee = []; ratios = []; A_pos, A_neg = [], []
    for th in range(0, 360, 45):
        c = int(round(th / 3.0)) % 120
        eff = np.mean([T[:, (c + k) % 120] for k in range(-4, 5)], axis=0)
        a = np.array([ang(th, x) for x in face]); high = np.array([exposure_class(12, v) == "HIGH" for v in eff])
        direct, cross, lee = a <= 45, (a > 45) & (a <= 90), a > 90
        for nm, m in (("DIRECT", direct), ("CROSS", cross), ("LEE", lee)):
            if m.any(): cls[nm].append(eff[m])
        if lee.any(): hi_lee.append(high[lee].mean())
        A_pos.append(eff[direct & high] if (direct & high).any() else np.array([])); A_neg.append(eff[~direct])
    med = {k: float(np.median(np.concatenate(v))) if v else None for k, v in cls.items()}
    # AUC for predicting HIGH from "DIRECT" flag (binary), pooled over 8 directions
    hi_all, dir_all = [], []
    for th in range(0, 360, 45):
        c = int(round(th / 3.0)) % 120; eff = np.mean([T[:, (c + k) % 120] for k in range(-4, 5)], axis=0)
        a = np.array([ang(th, x) for x in face]); hi_all += [exposure_class(12, v) == "HIGH" for v in eff]; dir_all += list(a <= 45)
    hi_all, dir_all = np.array(hi_all), np.array(dir_all)
    A = auc(dir_all[hi_all].astype(float), dir_all[~hi_all].astype(float)) if hi_all.any() and (~hi_all).any() else None
    res.append({"lake": d.get("name"), "state": d["directory"]["state"] if "directory" in d else None, "banks": len(keep), "medianFetch": med,
                "highShareLee": round(float(np.mean(hi_lee)), 4), "highShareAll": round(float(hi_all.mean()), 4),
                "ratioDirectOverLee": (med["DIRECT"] / max(med["LEE"], 1)) if med["DIRECT"] and med["LEE"] else None, "auc": A})
ok = [r for r in res if r["ratioDirectOverLee"] is not None]
p = [r for r in ok if r["highShareLee"] <= 0.05 and r["ratioDirectOverLee"] >= 5]
print("lakes evaluated", len(res), "usable", len(ok), "pass both", len(p), f"({len(p)/max(len(ok),1):.2f})")
print("median auc", np.nanmedian([r["auc"] for r in ok if r["auc"] is not None]), "median ratio", np.median([r["ratioDirectOverLee"] for r in ok]))
print("median highShareLee", np.median([r["highShareLee"] for r in ok]), "median highShareAll", np.median([r["highShareAll"] for r in ok]))
for r in sorted(ok, key=lambda r: -r["highShareLee"])[:6]: print("worstLee", r)
# G6 fetch x speed table
print("G6 class by fetch (m) and speed (mph): ", {mph: {fm: exposure_class(mph, fm) for fm in (100, 250, 500, 1000, 2000, 5000, 10000)} for mph in (5, 8, 12, 18, 25)})
json.dump(res, open(sys.argv[1], "w"), indent=1)
