"""TEST run (once) with the FROZEN pair from out/chosen_params.frozen.json. Also covers every NLA lake (dev lakes included) for the descriptive sanity stats; gate verdicts use odd-hash lakes only.
Snohomish all 5 lakes, FWC 7 lakes, NLA 2017 primary + 2018/2019 secondary. Modes S, A, P."""
from v2jobs import *
import pickle
from multiprocessing import Pool
install_guard()
fz = load_frozen(); assert fz["written_before_test_scoring"]
PAIR = (fz["haze_swir"], fz["haze_standoff_px"]); SET = [PAIR]
print("FROZEN PAIR", PAIR, fz["written_at"], flush=True)
CLS = pd.read_csv(NLA / "out/nla_lake_classes.csv").set_index("lakeKey")
if __name__ == "__main__":
    jobs_s = [("snoco", n, SET, "SAP") for n in SNOCO.values()] + [("fwc", n, SET, "SAP") for n in FWC_IDS]
    jobs_n = []
    for k in CLS.index[CLS.n_stations > 0]:
        if k == "Lake_Mead_NV": continue
        ref0 = dt.date.fromisoformat(CLS.loc[k, "visit_dates"].split(";")[0])
        jobs_n.append((k, "p2017", str(ref0), SET, "SAP"))
        for y in (2018, 2019):
            try: an = ref0.replace(year=y)
            except ValueError: an = ref0.replace(year=y, day=28)
            jobs_n.append((k, f"s{y}", str(an), SET, "SAP"))
    with Pool(8) as p:
        rs = p.map_async(snoco_fwc_job, jobs_s, chunksize=1)
        rn = p.map(nla_job, jobs_n, chunksize=1)
        rs = rs.get()
    pickle.dump(dict(pair=PAIR, frozen=fz, snoco_fwc={f"{r['info']['tag']}|{r['info']['nm']}": r for r in rs}, nla=rn), open(OUT2 / "test_raw.pkl", "wb"))
    print("done", len(rs), len(rn))
