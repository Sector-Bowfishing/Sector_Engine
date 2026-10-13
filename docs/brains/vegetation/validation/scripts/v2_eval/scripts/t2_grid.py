"""DEV grid (A4): observer A over haze_swir x haze_standoff_px on DEV sets only (Snohomish Roesiger+Serene; NLA even-hash lakes, primary 2017).
Saves out/grid_dev_raw.pkl and out/grid_dev.json. Does NOT choose and does NOT touch any TEST lake."""
from v2jobs import *
import pickle
from multiprocessing import Pool
install_guard()
SET = [(hs, hp) for hs in GRID_HS for hp in GRID_HP]
split = nla_split(); dev = split[split.split == "DEV"]
CLS = pd.read_csv(NLA / "out/nla_lake_classes.csv").set_index("lakeKey")
if __name__ == "__main__":
    jobs_s = [("snoco", n, SET, "A") for n in DEV_SNOCO]
    jobs_n = []
    for k in dev.lakeKey:
        if k == "Lake_Mead_NV": continue
        ref0 = CLS.loc[k, "visit_dates"].split(";")[0]
        jobs_n.append((k, "p2017", ref0, SET, "A"))
    with Pool(8) as p:
        rs = p.map_async(snoco_fwc_job, jobs_s, chunksize=1)
        rn = p.map(nla_job, jobs_n, chunksize=1)
        rs = rs.get()
    R = {f"snoco|{r['info']['nm']}": r for r in rs}
    pickle.dump(dict(snoco=R, nla=rn), open(OUT2 / "grid_dev_raw.pkl", "wb"))
    print("dev lakes run:", len(rn), "snoco", list(R))
