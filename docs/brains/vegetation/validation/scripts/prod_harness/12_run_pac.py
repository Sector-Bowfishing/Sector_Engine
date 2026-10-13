"""Production s2_pass on every cached scene of the FWC PAC/PVI lake-years (note-05 lean caches, +-21 d of the survey median).
usage: 12_run_pac.py CELL_M  -> out/pac{CELL}_{lake_id}.npz"""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, warnings, time, json, collections
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
import prod_import as P, loaders as L
dws = P.dws
FIELDS = ["read","grass_prod","gfrac","hidden","near","seen_share","nodata_share","cloudscl_share","gfrac_v1","dark_share","glare_share"]
LY = [o for o in json.load(open(L.ROOT/"data/pac_lakeyears.json")) if o["lake"] != "Okeechobee"]

def work(args):
    lid, cell = args
    t0 = time.time()
    g = L.fwc_all_lakes()[lid]
    lys = [o for o in LY if o["lake_id"] == lid]
    scenes = {}
    for o in lys:
        for s in L.pac_scenes(lid, o["survey_med"]):
            scenes[s["file"]] = s
    sc = sorted(scenes.values(), key=lambda s: s["date"])
    if not sc: return lid, 0, 0, 0.0
    utm = sc[0]["crs"].to_string()
    dws.UTM = utm
    fr = dws.Frame(g, cell=cell); m = dws.lake_masks(g, fr)
    S = len(sc); out = {f: np.zeros((S, fr.height, fr.width), "float16" if f not in ("read","grass_prod") else bool) for f in FIELDS}
    rej = np.array([""]*S, dtype=object); err = np.array([""]*S, dtype=object)
    for i, s in enumerate(sc):
        if s["crs"].to_string() != utm: err[i] = "other UTM zone"; continue
        try:
            try: r = P.run_scene(s["id"], s["tile"], fr, m, utm)
            except dws.PassRejected as e:
                rej[i] = str(e); r = P.run_scene(s["id"], s["tile"], fr, m, utm, gate=False)
            for f in FIELDS: out[f][i] = r[f]
        except Exception as e:
            err[i] = repr(e)[:200]
    np.savez_compressed(L.ROOT/f"adoption/prod_harness/out/pac{int(cell)}_{lid}.npz", **out, rejected=rej.astype(str), error=err.astype(str),
                        dates=np.array([s["date"] for s in sc]), files=np.array([s["file"] for s in sc]), lake=m["lake"], clarity=m["clarity"],
                        ground_m=fr.cell_ground_m(), cell=cell, utm=utm)
    return lid, S, int((err != "").sum()), round(time.time()-t0, 1)

if __name__ == "__main__":
    cell = float(sys.argv[1])
    ids = sorted({o["lake_id"] for o in LY}, key=lambda i: -max(o["km2"] for o in LY if o["lake_id"] == i))
    with ProcessPoolExecutor(6) as ex:
        for r in ex.map(work, [(i, cell) for i in ids]): print(cell, r, flush=True)
