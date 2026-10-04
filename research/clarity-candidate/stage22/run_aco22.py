"""Stage 22 driver: the frozen ACOLITE K4 path, instrumented (aco22_one.py). Per task (one scene):
  base run on the source (Google Cloud SAFE, or a LAZY real-nominal S2C SAFE from AWS with windowed /vsis3/ reads) with the
  crop's L1R kept; every further variant (additive TOA offsets) is run from that L1R, so the remote imagery is read once.
Task: {"run", "source": {"gcs": l1c} | {"aws": select21 s2c record}, "crops": [...], "variants": {"K0": null, "K1": {..}, ...},
       "keep_l1r": bool}. The first variant listed is the base run (must be null = no offsets).
Results: RESDIR/<run>__<variant>.json. Remote bytes are parsed from GDAL network statistics and appended to
stage21/aws_bytes.log (the same requester-pays record and 95 GB cap as Stage 21).
  python run_aco22.py TASKS_JSON RESDIR [--workers N]"""
import json, os, sys, subprocess, shutil, time, re, glob, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage21", f"{S}/stage22"]
import safe as SAFE, fetch21 as F21, lazy22 as LZ
_fetch = SAFE.fetch
SAFE.fetch = lambda name, skip=("HTML/", "rep_info/", "preview", "_TCI.jp2"): _fetch(name, skip)
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}
WORK = f"{S}/stage22/work"; LAZY = f"{S}/stage22/lazy"; L1R = f"{S}/stage22/l1r"
ENV_LAZY = {"AWS_REQUEST_PAYER": "requester", "AWS_REGION": "eu-central-1", "CPL_VSIL_SHOW_NETWORK_STATS": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "GDAL_HTTP_MAX_RETRY": "5", "GDAL_HTTP_RETRY_DELAY": "3", "VSI_CACHE": "TRUE", "VSI_CACHE_SIZE": "200000000"}


def netbytes(text):
    i = text.find("Network statistics:")
    if i < 0: return 0
    try:
        j = json.loads(text[text.index("{", i):])
        return int(j.get("methods", {}).get("GET", {}).get("downloaded_bytes", 0)) + int(j.get("methods", {}).get("HEAD", {}).get("downloaded_bytes", 0))
    except Exception:
        return sum(int(x) for x in re.findall(r'"downloaded_bytes":(\d+)', text[i:])[:1])


def run_crop(inp, c, variant_sub, keep, lazy, tag):
    o = dict(OV)
    if c.get("elev") is not None: o["elevation"] = c["elev"]
    if variant_sub: o["_toa_sub"] = variant_sub
    if keep: o["_keep_l1r"] = keep
    wd = f"{WORK}/{tag}"; env = dict(os.environ); env.update(ENV_LAZY if lazy else {})
    p = subprocess.run([ACO, f"{S}/stage22/aco22_one.py", inp, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(o)], capture_output=True, text=True, timeout=3600, env=env)
    shutil.rmtree(wd, ignore_errors=True)
    line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
    rec = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-400:]}
    nb = netbytes(p.stdout + "\n" + p.stderr) if lazy else 0
    return rec, nb


def task(t, resdir):
    names = list(t["variants"]); base = names[0]; assert t["variants"][base] is None
    if all(os.path.exists(f"{resdir}/{t['run']}__{v}.json") for v in names): return t["run"], "done"
    lazy = "aws" in t["source"]; t0 = time.time(); msg = []
    try:
        if lazy:
            if F21.billed_gb() >= F21.CAP_GB: raise RuntimeError(f"AWS cap {F21.CAP_GB} GB reached")
            inp = LZ.build(t["source"]["aws"], LAZY)
        else:
            inp = SAFE.fetch(t["source"]["gcs"])
        # runtime offsets ("corr21:K1|C1|C2"): the frozen Stage 21 values, B11 from this S2C tile's own clear-pixel brightness
        if any(isinstance(x, str) for x in t["variants"].values()):
            import run_aco21 as RA21
            full = RA21.offsets(inp, RA21.corr())
            pick = {"K1": ("B08", "B8A", "B11", "B12"), "C1": ("B11", "B12"), "C2": ("B08", "B8A")}
            t["variants"] = {v: ({b_: full[b_] for b_ in pick[x.split(":")[1]]} if isinstance(x, str) else x) for v, x in t["variants"].items()}
        recs = {v: {"run": t["run"], "variant": v, "source": t["source"].get("gcs") or t["source"]["aws"]["product"], "toa_sub": t["variants"][v], "crops": []} for v in names}
        for i, c in enumerate(t["crops"]):
            keep = f"{L1R}/{t['run']}_{i}"                    # folder; holds ACOLITE's own *_L1R.nc
            if not os.path.exists(f"{resdir}/{t['run']}__{base}.json"):
                r, nb = run_crop(inp, c, None, keep, lazy, f"{t['run']}_{i}_{base}")
                if nb: F21._log(nb, f"vsis3-window:{t['source']['aws']['product']}:{i}")
            else:
                r = next(cc for cc in json.load(open(f"{resdir}/{t['run']}__{base}.json"))["crops"] if abs(cc["lat"] - c["lat"]) < 1e-9 and abs(cc["lon"] - c["lon"]) < 1e-9)
            r.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); recs[base]["crops"].append(r)
            for v in names[1:]:
                kl = glob.glob(f"{keep}/*_L1R.nc")
                if not kl: recs[v]["crops"].append({"error": "no L1R", "lat": c["lat"], "lon": c["lon"]}); continue
                rv, _ = run_crop(kl[0], c, t["variants"][v], None, False, f"{t['run']}_{i}_{v}")
                rv.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); recs[v]["crops"].append(rv)
            if not t.get("keep_l1r"): shutil.rmtree(keep, ignore_errors=True)
        for v in names:
            recs[v]["seconds"] = round(time.time() - t0, 1); json.dump(recs[v], open(f"{resdir}/{t['run']}__{v}.json", "w"), default=str)
            ok = sum(1 for c in recs[v]["crops"] for p in (c.get("points") or {}).values() if ((p or {}).get("M0") or {}).get("n", 0) >= 5); msg.append(f"{v}:M0 {ok}")
    except Exception as e:
        msg.append("ERR " + str(e)[:160])
    finally:
        if not lazy and "gcs" in t["source"]: SAFE.delete(t["source"]["gcs"])
    return t["run"], " ".join(msg) + f" | {round(time.time() - t0)}s | AWS {F21.billed_gb():.2f} GB"


if __name__ == "__main__":
    T = json.load(open(sys.argv[1])); resdir = sys.argv[2]
    for d in (resdir, WORK, LAZY, L1R): os.makedirs(d, exist_ok=True)
    W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    with cf.ThreadPoolExecutor(W) as ex:
        for n, (run, msg) in enumerate(ex.map(lambda t: task(t, resdir), T), 1): print(n, run, msg, flush=True)
    print("ACO22_DONE", flush=True)
