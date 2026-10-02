"""Stage 12 Part 3 driver: every Stage 11 corpus row dated <= 2025-12-31 through the frozen BEST ACOLITE configuration.
One task per C1 item: the L1C is fetched once; one ACOLITE run per crop (+-0.08 lat, +-0.10 lon around the first
station not yet covered); S2C scenes are also run TOA-harmonised (operational bands, production coefficients, processed
as S2A) from the raw run's L1R. Samples only; outputs deleted. 4 items in parallel. One result file per item.
  python run_corpus.py OVERRIDES_JSON"""
import json, os, sys, subprocess, time, collections, shutil, glob, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
D = f"{S}/stage12/corpus"; os.makedirs(f"{D}/res", exist_ok=True)
OV = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
ELEV = json.load(open(f"{D}/elevations.json")) if os.path.exists(f"{D}/elevations.json") else {}   # addendum C


def tasks():
    rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
    by = collections.defaultdict(list)
    for x in rows: by[x["item"]].append(x)
    T = []
    for item, xs in sorted(by.items()):
        crops, left = [], list(xs)
        while left:
            c = left[0]; inside = [y for y in left if abs(y["lat"] - c["lat"]) < 0.07 and abs(y["lon"] - c["lon"]) < 0.09]
            crops.append({"lat": c["lat"], "lon": c["lon"], "points": [[y["lat"], y["lon"], y["id"]] for y in inside]})
            left = [y for y in left if y not in inside]
        T.append({"item": item, "s2c": item.startswith("S2C"), "crops": crops})
    return T


def aco(inp, lat, lon, wd, pts, keep=False, elev=None):
    ov = dict(OV)
    if elev is not None: ov["elevation"] = elev
    p = subprocess.run([ACO, f"{S}/stage12/tools/aco12_one.py", inp, str(lat), str(lon), wd, json.dumps(pts), json.dumps(ov)] + (["--keep"] if keep else []),
                       capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
    return json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-400:]}


def one(t):
    out = f"{D}/res/{t['item']}.json"
    if os.path.exists(out): return t["item"], "done"
    r = {"item": t["item"], "s2c": t["s2c"], "crops": []}; t0 = time.time()
    try:
        name = SAFE.l1c_for(t["item"]); r["l1c"] = name
        if not name:
            r["error"] = "no L1C"
        else:
            path = SAFE.fetch(name)
            for i, c in enumerate(t["crops"]):
                wd = f"{S}/stage12/work/c_{t['item']}_{i}"
                el = ELEV.get(f"{c['lat']},{c['lon']}")
                raw = aco(path, c["lat"], c["lon"], wd, c["points"], keep=t["s2c"], elev=el)
                rec = {"lat": c["lat"], "lon": c["lon"], "elevation_m": el, "raw": {k: v for k, v in raw.items() if k != "l1r"}}
                if t["s2c"] and raw.get("l1r"):
                    l1r = raw["l1r"][0]; h = f"{wd}_h_L1R.nc"
                    q = subprocess.run([ACO, f"{S}/stage12/tools/harm_l1r.py", l1r, h, f"{S}/stage12/harm/harm_prod_toa.json", "vop"], capture_output=True, text=True)
                    if q.returncode == 0:
                        hv = aco(h, c["lat"], c["lon"], f"{wd}_h", c["points"], elev=el)
                        rec["harm_vop"] = {k: v for k, v in hv.items() if k != "l1r"}
                    else:
                        rec["harm_vop"] = {"error": q.stderr[-300:]}
                    for f in [h]: 
                        if os.path.exists(f): os.remove(f)
                shutil.rmtree(wd, ignore_errors=True)
                r["crops"].append(rec)
            SAFE.delete(name)
    except Exception as e:
        r["error"] = str(e)[:300]
    r["seconds"] = round(time.time() - t0, 1)
    json.dump(r, open(out, "w"), default=str)
    ok = sum(1 for c in r["crops"] for p in (c["raw"].get("points") or {}).values() if (p or {}).get("n", 0) >= 5)
    return t["item"], f"{r['seconds']}s crops {len(r['crops'])} valid points {ok}" + (" ERR " + r["error"][:80] if r.get("error") else "")


if __name__ == "__main__":
    T = tasks()
    print(len(T), "items,", sum(len(t["crops"]) for t in T), "crops,", sum(1 for t in T if t["s2c"]), "S2C items", flush=True)
    with cf.ProcessPoolExecutor(int(os.environ.get("WORKERS", "4"))) as ex:
        for n, (item, msg) in enumerate(ex.map(one, T), 1):
            print(n, item, msg, flush=True)
    print("CORPUS_DONE", flush=True)
