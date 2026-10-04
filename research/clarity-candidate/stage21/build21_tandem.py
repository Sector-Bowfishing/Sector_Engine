"""Stage 21 (value-blind): ACOLITE tasks for the HELD-OUT real nominal tandem tiles (select21.json split H): per tile-date
one S2A run (Google Cloud), one raw S2C run (K0) and one corrected S2C run (K1, frozen offsets) on the same AWS download.
Crops: research grouping (+-0.07/0.09); elevation EPQS (US) / GLO-30 (global), as Stage 20. Writes tasks21_tandem.json."""
import json, os, sys, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
src = open(f"{S}/stage20/build20.py").read(); ns = {"__name__": "b20"}; exec(src.split('if sys.argv[1] == "prelim":')[0], ns)
T = []
for t in [t for t in json.load(open(f"{S}/stage21/select21.json")) if t["split"] == "H"]:
    pts = [(s["lat"], s["lon"], f"{s['site']}|{s['s2a']}|{s['s2c']}") for s in t["sites"]]; cr = ns["crops"](pts)
    T += [{"run": f"A_{t['tile']}_{t['date']}", "l1c": t["s2a_l1c"], "crops": cr},
          {"run": f"C0_{t['tile']}_{t['date']}", "aws": t["s2c"], "crops": cr}, {"run": f"C1_{t['tile']}_{t['date']}", "aws": t["s2c"], "crops": cr, "toa_sub": True}]
jobs = [c for t in T if t["run"].startswith("A_") for c in t["crops"]]
with cf.ThreadPoolExecutor(8) as ex:
    for c, v in zip(jobs, ex.map(lambda c: ns["elev"](c["lat"], c["lon"], not str(c["points"][0][2]).startswith("G:")), jobs)): c["elev"] = v
json.dump(ns["EL"], open(ns["EP"], "w")); json.dump(T, open(f"{S}/stage21/tasks21_tandem.json", "w"))
print("held-out tandem runs", len(T), "tiles", len(T) // 3, "crops", len(jobs), "points", sum(len(c["points"]) for c in jobs), "no elevation", sum(1 for c in jobs if c["elev"] is None))
