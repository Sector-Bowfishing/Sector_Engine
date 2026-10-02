"""Stage 13 section 8 tier 2: rerun ACOLITE K4 + elevation with l2w_mask=False on every Stage 12 corpus crop that ran but
left a station without a valid disk; sample the mask variants. 6 items in parallel. Writes coverage/res/<item>.json."""
import json, os, sys, glob, subprocess, time, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"; D = f"{S}/stage13/coverage"; os.makedirs(f"{D}/res", exist_ok=True)
ELEV = json.load(open(f"{S}/stage12/corpus/elevations.json"))
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}
def tasks():
    T = []
    for f in sorted(glob.glob(f"{S}/stage12/corpus/res/*.json")):
        r = json.load(open(f))
        if r.get("error") or not r.get("l1c"): continue
        crops = []
        for c in r["crops"]:
            raw = c["raw"]
            if raw.get("error"): continue
            bad = [k for k, p in (raw.get("points") or {}).items() if (p or {}).get("n", 0) < 5]
            if bad: crops.append({"lat": c["lat"], "lon": c["lon"], "elev": c.get("elevation_m"), "points": [[None, None, k] for k in bad]})
        if crops: T.append({"item": r["item"], "l1c": r["l1c"], "crops": crops})
    rows = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
    for t in T:
        for c in t["crops"]: c["points"] = [[rows[k]["lat"], rows[k]["lon"], k] for _, _, k in c["points"]]
    return T
def one(t):
    out = f"{D}/res/{t['item']}.json"
    if os.path.exists(out): return t["item"], "done"
    r = {"item": t["item"], "crops": []}; t0 = time.time()
    try:
        path = SAFE.fetch(t["l1c"])
        for i, c in enumerate(t["crops"]):
            ov = dict(OV); 
            if c.get("elev") is not None: ov["elevation"] = c["elev"]
            p = subprocess.run([ACO, f"{S}/stage13/tools/aco13_one.py", path, str(c["lat"]), str(c["lon"]), f"{S}/stage13/work/t2_{t['item']}_{i}", json.dumps(c["points"]), json.dumps(ov)],
                               capture_output=True, text=True, timeout=3600)
            line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
            r["crops"].append(json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-300:]})
        SAFE.delete(t["l1c"])
    except Exception as e:
        r["error"] = str(e)[:300]
    r["seconds"] = round(time.time() - t0, 1); json.dump(r, open(out, "w"), default=str)
    return t["item"], f"{r['seconds']}s"
if __name__ == "__main__":
    os.makedirs(f"{S}/stage13/work", exist_ok=True)
    T = tasks(); print(len(T), "items,", sum(len(c["points"]) for t in T for c in t["crops"]), "stations", flush=True)
    if "--probe" in sys.argv: T = T[:1]
    with cf.ProcessPoolExecutor(1 if "--probe" in sys.argv else 6) as ex:
        for n, (i, m) in enumerate(ex.map(one, T), 1): print(n, i, m, flush=True)
    print("TIER2_DONE", flush=True)
