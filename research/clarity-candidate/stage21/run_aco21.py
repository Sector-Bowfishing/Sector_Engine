"""Stage 21 ACOLITE driver: the frozen K4 path (stage20/run_aco20.py settings) through aco21_one.py. Task source is either
Google Cloud ("l1c": name, SAFE.fetch with addendum A1) or the AWS real nominal S2C ("aws": select21 s2c record,
fetch21.fetch). "toa_sub": true applies the FROZEN corr21.json offsets (M1 constant or M2 from the S2C tile's own clear-pixel
median), recorded in the result. Tasks sharing a source product run in one worker, then the download is deleted.
  python run_aco21.py TASKS_JSON RESDIR [--workers N]"""
import json, os, sys, subprocess, shutil, time, hashlib, concurrent.futures as cf
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage21"]
import safe as SAFE, fetch21 as F21
_fetch = SAFE.fetch
SAFE.fetch = lambda name, skip=("HTML/", "rep_info/", "preview", "_TCI.jp2"): _fetch(name, skip)
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}
WORK = f"{S}/stage21/work_aws"


def corr():
    F = json.load(open(f"{S}/stage21/FREEZE_STAGE21.json"))
    assert hashlib.sha256(open(f"{S}/stage21/corr21.json", "rb").read()).hexdigest() == F["corr21_sha256"], "corr21 not frozen"
    return json.load(open(f"{S}/stage21/corr21.json"))


def offsets(safe, C):
    out = {}
    for b, c in C["bands"].items():
        if c["model"] == "M1": out[b] = c["delta"]
        else:
            import toa21 as T21
            q, off = T21.meta(safe); x = T21.read(safe, b, q, off, "mean10" if b == "B08" else "native20")
            b10 = T21.read(safe, "B10", q, off, "rep60"); b02 = T21.read(safe, "B02", q, off, "level20")
            out[b] = c["alpha"] + c["beta"] * float(np.nanmedian(x[(b10 < 0.002) & (b02 < 0.3)]))
    return out


def src_path(t):
    return F21.fetch(t["aws"], WORK) if t.get("aws") else SAFE.fetch(t["l1c"])


def one(t, resdir, path):
    out = f"{resdir}/{t['run']}.json"
    if os.path.exists(out): return t["run"], "done"
    r = {"run": t["run"], "source": "aws" if t.get("aws") else "gcs", "product": (t.get("aws") or {}).get("product") or t["l1c"], "crops": []}; t0 = time.time()
    try:
        ov = dict(OV)
        if t.get("toa_sub"): sub = offsets(path, corr()); ov["_toa_sub"] = sub; r["toa_sub"] = sub
        for i, c in enumerate(t["crops"]):
            o = dict(ov)
            if c.get("elev") is not None: o["elevation"] = c["elev"]
            wd = f"{S}/stage21/work/c_{t['run']}_{i}"
            p = subprocess.run([ACO, f"{S}/stage21/aco21_one.py", path, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(o)],
                               capture_output=True, text=True, timeout=3600, env=dict(os.environ))
            line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
            rec = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-300:]}
            rec.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); r["crops"].append(rec)
            shutil.rmtree(wd, ignore_errors=True)
    except Exception as e:
        r["error"] = str(e)[:300]
    r["seconds"] = round(time.time() - t0, 1); json.dump(r, open(out, "w"), default=str)
    ok = sum(1 for c in r["crops"] for p in (c.get("points") or {}).values() if ((p or {}).get("M0") or {}).get("n", 0) >= 5)
    return t["run"], f"{r['seconds']}s crops {len(r['crops'])} M0 {ok}" + (" ERR " + r["error"][:80] if r.get("error") else "")


if __name__ == "__main__":
    T = json.load(open(sys.argv[1])); resdir = sys.argv[2]; os.makedirs(resdir, exist_ok=True); os.makedirs(f"{S}/stage21/work", exist_ok=True); os.makedirs(WORK, exist_ok=True)
    W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    key = lambda t: ("aws:" + t["aws"]["product"]) if t.get("aws") else t["l1c"]
    by = {}
    for t in T: by.setdefault(key(t), []).append(t)
    print(len(T), "runs over", len(by), "products", flush=True)
    def grp(ts):
        todo = [t for t in ts if not os.path.exists(f"{resdir}/{t['run']}.json")]
        if not todo: return [(t["run"], "done") for t in ts]
        try:
            path = src_path(ts[0]); msgs = [one(t, resdir, path) for t in ts]
        except Exception as e:
            msgs = [(t["run"], "FETCH ERR " + str(e)[:100]) for t in ts]
        if ts[0].get("aws"): shutil.rmtree(os.path.join(WORK, ts[0]["aws"]["product"] + ".SAFE"), ignore_errors=True)
        else: SAFE.delete(ts[0]["l1c"])
        return msgs
    with cf.ThreadPoolExecutor(W) as ex:
        for n, msgs in enumerate(ex.map(grp, list(by.values())), 1):
            for run, msg in msgs: print(n, run, msg, f"| AWS {F21.billed_gb():.1f} GB", flush=True)
    print("ACO21_DONE", flush=True)
