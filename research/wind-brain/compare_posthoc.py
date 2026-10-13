"""POST-HOC (not pre-registered) diagnostic for the failed G2: which statistic and which lakes agree? Labelled as exploratory."""
import glob, gzip, json, os, sys
import numpy as np
from scipy.stats import spearmanr
sys.path.insert(0, os.path.dirname(__file__))
from polygon_fetch import load_frozen, NAMES16
fleet = {r["id"]: r for r in json.load(open(sys.argv[1])) if r.get("ok")}
files = glob.glob(os.path.expanduser("~/Library/Caches/sector-wind/national-fetch/tables/*.gz")) + glob.glob(os.path.expanduser("~/Desktop/Development/iOS/sector-wind/Sector/Assets.xcassets/FishIntel/Wind/*/*.windfetch.json.gz"))
rows = []
for f in files:
    d, T = load_frozen(f); nm, st = d.get("name"), d.get("state")
    c = [k for k in fleet if k.split("|")[1] == st and (k.split("|")[0] == nm or k.split("|")[0].split(" ")[0] == nm.split(" ")[0])]
    if not c: continue
    k = c[0]; p90a = np.percentile(T, 90, axis=0); p90b = np.array(fleet[k]["p90FetchByDir"]); meda = np.median(T, axis=0); medb = np.array(fleet[k]["medianFetchByDir"])
    r90 = spearmanr(p90a, p90b)[0] if p90a.std() > 0 and p90b.std() > 0 else np.nan
    rows.append((k, fleet[k]["areaKm2"], float(np.percentile(T, 90)), r90, np.log(max(p90b.mean(), 1) / max(p90a.mean(), 1))))
rows = [r for r in rows if not np.isnan(r[3])]
print("lakes", len(rows), " p90-fetch rho median", round(float(np.median([r[3] for r in rows])), 3), " share>=0.85", round(float(np.mean([r[3] >= .85 for r in rows])), 3))
for lab, sel in (("lakes with frozen p90 fetch > 1 km", lambda r: r[2] > 1000), ("area > 20 km2", lambda r: r[1] > 20), ("p90 <= 1 km", lambda r: r[2] <= 1000)):
    s = [r for r in rows if sel(r)]
    if s: print(lab, "n", len(s), "median rho", round(float(np.median([r[3] for r in s])), 3), "share>=0.85", round(float(np.mean([r[3] >= .85 for r in s])), 3), "median log ratio p90", round(float(np.median([r[4] for r in s])), 2))
