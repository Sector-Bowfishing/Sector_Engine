import json, numpy as np
from pathlib import Path
from scipy.stats import spearmanr
ROOT = Path(__file__).resolve().parent.parent
sec = json.load(open(ROOT/"out/secchi_summary.json")); pm = json.load(open(ROOT/"out/metrics_fwc.json"))["per_lake"]; cm = json.load(open(ROOT/"out/metrics_cell_fwc.json"))
rows = []
for nm in sec:
    s = pm[nm]["single"]
    rows.append(dict(lake=nm, secchi_m=sec[nm]["median_year_MaySep"], n_secchi=sec[nm]["n_year"], secchi_pm2=sec[nm]["median_pm2yr_MaySep"],
        surf_auc_ndvi_matched=s["auc"]["surface"]["NDVI"][1], surf_auc_fai_matched=s["auc"]["surface"]["FAI"][1], sub_auc_ndvi=s["auc"]["submerged"]["NDVI"][1], sub_auc_fai=s["auc"]["submerged"]["FAI"][1],
        sector_recall_surface_px=s["sector"]["surface"]["ndvi>=0.30"]["R"], sector_recall_sub_px=s["sector"]["submerged"]["ndvi>=0.30"]["R"],
        cell_recall_surface=cm["per"][f"{nm}|single (closest clear date)|surface"], cell_rate_sub=cm["per"][f"{nm}|single (closest clear date)|submersed_only"]))
json.dump(rows, open(ROOT/"out/secchi_strat.json", "w"), indent=1)
for r in rows: print(r)
X = np.array([r["secchi_m"] for r in rows]); X2 = np.array([r["secchi_pm2"] for r in rows])
res = {}
for k in rows[0]:
    if k in ("lake","secchi_m","secchi_pm2","n_secchi"): continue
    y = np.array([r[k] for r in rows], float); res[k] = dict(rho_year=round(float(spearmanr(X, y)[0]), 2), rho_pm2=round(float(spearmanr(X2, y)[0]), 2))
    print(k, res[k])
json.dump(res, open(ROOT/"out/secchi_spearman.json", "w"), indent=1)
