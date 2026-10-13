"""G2: polygon fetch (fleet_fetch.json) vs frozen NHD-raster fetch tables, on lakes present in both. Also tests the
direction convention by checking correlation at 0 deg vs 180 deg shift (a reversed convention would peak at 180)."""
import glob, gzip, json, os, sys
import numpy as np
from scipy.stats import spearmanr
sys.path.insert(0, os.path.dirname(__file__))
from polygon_fetch import load_frozen, NAMES16
fleet = {r["id"]: r for r in json.load(open(sys.argv[1])) if r.get("ok")}
files = glob.glob(os.path.expanduser("~/Library/Caches/sector-wind/national-fetch/tables/*.gz")) + \
        glob.glob(os.path.expanduser("~/Desktop/Development/iOS/sector-wind/Sector/Assets.xcassets/FishIntel/Wind/*/*.windfetch.json.gz"))
out, seen = [], set()
for f in files:
    d, T = load_frozen(f)
    nm = d.get("name"); st = d.get("state")
    cand = [k for k in fleet if k.split("|")[1] == st and (k.split("|")[0] == nm or k.split("|")[0].split(" ")[0] == nm.split(" ")[0])]
    if not cand: out.append({"file": os.path.basename(f), "name": nm, "state": st, "matched": False}); continue
    k = cand[0]
    if k in seen: continue
    seen.add(k)
    a = np.median(T, axis=0); b = np.array(fleet[k]["medianFetchByDir"])
    if len(a) != 16 or np.all(a == a[0]) or np.all(b == b[0]): out.append({"id": k, "matched": True, "degenerate": True}); continue
    rho0 = spearmanr(a, b)[0]; rho180 = spearmanr(np.roll(a, 8), b)[0]
    da = int(np.argmax(a)); db = int(np.argmax(b)); dd = min((da - db) % 16, (db - da) % 16) * 22.5
    out.append({"id": k, "matched": True, "rho": round(float(rho0), 3), "rho_if_reversed": round(float(rho180), 3), "domFrozen": NAMES16[da], "domPoly": NAMES16[db],
                "domDiffDeg": dd, "medianFrozenM": int(np.median(a)), "medianPolyM": int(np.median(b)), "logRatio": round(float(np.log(max(np.median(b),1) / max(np.median(a),1))), 3),
                "areaKm2": fleet[k]["areaKm2"], "nFrozenBanks": int(T.shape[0])})
m = [o for o in out if o.get("rho") is not None]
print("matched with usable profile:", len(m), "of", len(out))
print("median rho", np.median([o["rho"] for o in m]), " median rho if reversed", np.median([o["rho_if_reversed"] for o in m]))
print("rho>=0.85 share", np.mean([o["rho"] >= 0.85 for o in m]), " dominant within 45deg share", np.mean([o["domDiffDeg"] <= 45 for o in m]))
print("median log ratio of median fetch (poly/frozen)", np.median([o["logRatio"] for o in m]))
json.dump(out, open(sys.argv[2], "w"), indent=1)
for o in sorted(m, key=lambda o: o["rho"])[:8]: print("worst", o)
