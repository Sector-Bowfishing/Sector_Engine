"""Stage 20 ACOLITE driver: the frozen K4 path (stage14/cert/run_cert_aco.py settings: K4 + l2w_mask False + lake-elevation
pressure; addendum A1 fetch without the TCI preview) through stage20/aco20_one.py (frozen L2W sampling + L1R/L2R
diagnostics). Tasks: {"run": id, "l1c": <GCP L1C name>, "crops": [...], "emulate_nominal": bool}. With emulate_nominal,
the product's own MTD PHYSICAL_GAINS are compared with the nominal S2C N0511 reference (meta20.json) and ACOLITE's TOA
gains (gains=True, gains_toa) rescale the L1R by gain_product / gain_reference per band - a DIAGNOSTIC re-calibration of a
preliminary product to nominal calibration, never used for any product answer.
  python run_aco20.py TASKS_JSON RESDIR [--workers N]"""
import json, os, sys, subprocess, shutil, time, concurrent.futures as cf
import xml.etree.ElementTree as ET
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
_fetch = SAFE.fetch
SAFE.fetch = lambda name, skip=("HTML/", "rep_info/", "preview", "_TCI.jp2"): _fetch(name, skip)
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}
RSR = ["1", "2", "3", "4", "5", "6", "7", "8", "8A", "9", "10", "11", "12"]
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"]
REF = next(v for v in json.load(open(f"{S}/stage20/meta20.json")).values() if v.get("group") == ["S2C", "N0511", "2025"])["gains"]
LOCK = {}


def gains_of(safe_dir):
    root = ET.parse(os.path.join(safe_dir, "MTD_MSIL1C.xml")).getroot()
    return {BANDS[int(g.get("bandId"))]: float(g.text) for g in root.iter("PHYSICAL_GAINS")}


def one(t, resdir):
    out = f"{resdir}/{t['run']}.json"
    if os.path.exists(out): return t["run"], "done"
    r = {"run": t["run"], "l1c": t["l1c"], "emulate_nominal": bool(t.get("emulate_nominal")), "crops": []}; t0 = time.time()
    try:
        path = SAFE.fetch(t["l1c"])
        ov = dict(OV)
        if t.get("emulate_nominal"):
            g = gains_of(path); ratio = [g[b] / REF[b] for b in BANDS]
            ov.update({"gains": True, "gains_toa": ratio}); r["gains_toa"] = dict(zip(BANDS, ratio))
        for i, c in enumerate(t["crops"]):
            o = dict(ov)
            if c.get("elev") is not None: o["elevation"] = c["elev"]
            wd = f"{S}/stage20/work/c_{t['run']}_{i}"
            if t.get("toa_sub"): o["_toa_sub"] = t["toa_sub"]
            p = subprocess.run([ACO, f"{S}/stage20/{'aco20x_one.py' if t.get('toa_sub') else 'aco20_one.py'}", path, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(o)],
                               capture_output=True, text=True, timeout=3600, env=dict(os.environ))
            line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
            rec = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-300:]}
            rec.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); r["crops"].append(rec)
            shutil.rmtree(wd, ignore_errors=True)
    except Exception as e:
        r["error"] = str(e)[:300]
    r["seconds"] = round(time.time() - t0, 1)
    json.dump(r, open(out, "w"), default=str)
    ok = sum(1 for c in r["crops"] for p in (c.get("points") or {}).values() if ((p or {}).get("M0") or {}).get("n", 0) >= 5)
    return t["run"], f"{r['seconds']}s crops {len(r['crops'])} M0 {ok}" + (" ERR " + r["error"][:80] if r.get("error") else "")


if __name__ == "__main__":
    T = json.load(open(sys.argv[1])); resdir = sys.argv[2]; os.makedirs(resdir, exist_ok=True); os.makedirs(f"{S}/stage20/work", exist_ok=True)
    W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    # one L1C is fetched by one worker at a time: tasks sharing an L1C run in sequence inside one job
    by = {}
    for t in T: by.setdefault(t["l1c"], []).append(t)
    groups = list(by.values())
    print(len(T), "runs over", len(groups), "L1C products", flush=True)
    def grp(ts):
        msgs = [one(t, resdir) for t in ts]
        SAFE.delete(ts[0]["l1c"]); return msgs
    with cf.ThreadPoolExecutor(W) as ex:
        for n, msgs in enumerate(ex.map(grp, groups), 1):
            for run, msg in msgs: print(n, run, msg, flush=True)
    print("ACO20_DONE", flush=True)
