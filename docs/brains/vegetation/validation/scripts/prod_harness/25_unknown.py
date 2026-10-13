"""Unknown / refusal accounting per guard. usage: 25_unknown.py CELL"""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, datetime as dt, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import score_lib as SL
ROOT = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
CELL = int(sys.argv[1])
SNOCO = ["Serene","Blackmans","Storm","Roesiger","Bosworth"]; FWC = ["Orange","Griffin","Apopka","Harris","Panasoffkee","Yale","Cypress"]
LYS = [o for o in json.load(open(ROOT.parent.parent/"data/pac_lakeyears.json")) if o["lake"] != "Okeechobee"]
CODES = [SL.SHORE, SL.NODATA, SL.CLOUD, SL.HAZE, SL.DARK, SL.NOSCENE, SL.NOTACC, SL.CLEAR, SL.FLAG]
def nm(c): return {SL.CLEAR: "CLEAR", SL.FLAG: "FLAG"}.get(c) or SL.NAMES[c]

def datasets():
    d = {"snoco": [], "fwc_points": [], "fwc_pac": []}
    for n in SNOCO:
        z = np.load(ROOT/f"out/cells{CELL}_snoco_{n}.npz", allow_pickle=True); d["snoco"].append((n, z, dt.date.fromisoformat(str(z["survey"]))))
    for n in FWC:
        z = np.load(ROOT/f"out/cells{CELL}_fwc_{n}.npz", allow_pickle=True); d["fwc_points"].append((n, z, dt.date.fromisoformat(str(z["survey"]))))
    cache = {}
    for o in LYS:
        f = ROOT/f"out/pac{CELL}_{o['lake_id']}.npz"
        if not f.exists(): continue
        if o["lake_id"] not in cache: cache[o["lake_id"]] = np.load(f, allow_pickle=True)
        d["fwc_pac"].append((f"{o['lake_id']}_{o['year']}", cache[o["lake_id"]], dt.date.fromisoformat(o["survey_med"])))
    return d

out = {}
for mode in ("prod", "v1", "v1fix"):
    for dsname, items in datasets().items():
        tot = {o: {nm(c): 0 for c in CODES} for o in "SA"}; lakecells = {o: 0 for o in "SA"}
        guard = {k: 0 for k in ("unseen", "nodata", "hidden", "hidden_near_cloud", "dark", "glare")}; gcells = 0; nsc = 0
        nlake_noscene = {o: 0 for o in "SA"}
        for name, z, ref in items:
            sc = SL.prep(z, mode, False)
            for o in "SA":
                st, info = SL.OBS[o](z, sc, ref)
                if info["kind"] == "NONE": nlake_noscene[o] += 1
                for c in CODES: tot[o][nm(c)] += int(((st == c) & z["lake"]).sum())
                lakecells[o] += int(z["lake"].sum())
            # non-exclusive guard hit frequency over all in-window production-accepted scenes, clarity cells only
            for s in sc:
                if abs((s["date"] - ref).days) > SL.WINDOW_DAYS: continue
                gm = SL.guard_masks(z, s["i"]); cc = z["lake"] & z["clarity"]
                for k in guard: guard[k] += int((gm[k] & cc).sum())
                gcells += int(cc.sum()); nsc += 1
        out[f"{mode}|{dsname}"] = dict(n_units=len(items), lakecells=lakecells, status=tot, lakes_with_no_selected_scene=nlake_noscene,
                                       guard_hit_share_all_window_scenes={k: v / max(1, gcells) for k, v in guard.items()}, n_scene_unit_pairs=nsc)
json.dump(out, open(ROOT/f"out/unknown_{CELL}.json", "w"), indent=1)
for k, v in out.items():
    if not k.startswith("v1|") and not k.startswith("prod|"): continue
    print(k, "units", v["n_units"], "no-scene lakes", v["lakes_with_no_selected_scene"])
    for o in "SA":
        L = v["lakecells"][o]; print("  ", o, {n: round(c / L, 3) for n, c in v["status"][o].items() if c})
    print("   guard hit (all in-window scenes, clarity cells)", {a: round(b, 3) for a, b in v["guard_hit_share_all_window_scenes"].items()})
