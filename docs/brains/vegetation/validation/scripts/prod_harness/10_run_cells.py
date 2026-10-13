"""Run the IMPORTED production s2_pass on every cached scene of the Snohomish / FWC-point lakes.
usage: 10_run_cells.py snoco|fwc CELL_M   -> out/cells{CELL}_{tag}_{lake}.npz"""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, warnings, time, json
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
import prod_import as P, loaders as L
dws = P.dws
FIELDS = ["read","grass_prod","gfrac","hidden","near","seen_share","nodata_share","cloudscl_share","gfrac_v1","dark_share","glare_share"]

def work(args):
    tag, nm, cell = args
    t0 = time.time()
    g = L.lakes(tag)[nm]
    st, sc = L.stack_scenes(tag, nm)
    ref = next(s for s in sc if s)
    utm = ref["crs"].to_string(); dws.UTM = utm
    fr = dws.Frame(g, cell=cell); m = dws.lake_masks(g, fr)
    S = len(sc); out = {f: np.zeros((S, fr.height, fr.width), "float32" if f not in ("read","grass_prod") else bool) for f in FIELDS}
    ok = np.zeros(S, bool); rej = np.array([""]*S, dtype=object)
    for i, s in enumerate(sc):
        if s is None: continue
        try:
            r = P.run_scene(s["id"], s["tile"], fr, m, utm)
        except dws.PassRejected as e:
            rej[i] = str(e)                    # production skips this pass ("skipped: ..."); arrays still filled by the gate-off sensitivity run
            r = P.run_scene(s["id"], s["tile"], fr, m, utm, gate=False)
        for f in FIELDS: out[f][i] = r[f]
        ok[i] = True
    # truth fractions on this frame from the 10 m label rasters (note-04 stacks)
    truth = {}
    for c in st.files:
        if c.startswith("lab_"):
            truth["truth_"+c[4:]] = dws.to_grid(st[c].astype("float32"), ref["transform"], ref["crs"], fr)
    np.savez_compressed(L.ROOT/f"adoption/prod_harness/out/cells{int(cell)}_{tag}_{nm}.npz", **out, ok=ok, rejected=rej.astype(str), dates=np.array([s["date"] if s else "" for s in sc]),
                        clear_stack=st["clear"], survey=str(st["survey"]), lake=m["lake"], clarity=m["clarity"], ground_m=fr.cell_ground_m(), cell=cell,
                        utm=utm, ids=np.array([s["id"] if s else "" for s in sc]), **truth,
                        **({"n_points": st["n_points"], "survey_min": st["survey_min"], "survey_max": st["survey_max"]} if "n_points" in st.files else {}))
    return nm, S, int(ok.sum()), round(time.time()-t0, 1)

if __name__ == "__main__":
    tag, cell = sys.argv[1], float(sys.argv[2])
    names = list(L.lakes(tag))
    with ProcessPoolExecutor(6) as ex:
        for r in ex.map(work, [(tag, n, cell) for n in names]): print(tag, cell, r, flush=True)
