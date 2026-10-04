"""Stage 23 driver: the frozen, instrumented ACOLITE K4 path (stage22/aco22_one.py, unchanged) on LAZY Google Cloud SAFEs
(lazy23.py; verified identical to full downloads, check23_lazy.json). Same task format and outputs as stage22/run_aco22.py:
  {"run", "source": {"gcsl": l1c}, "crops": [...], "variants": {"A": null} | {"K0": null, "C1": "corr21:C1", ...}}
The first variant is the base run (no offsets); every further variant runs from the crop's kept L1R. Runtime offsets
"corr21:K1|C1|C2" are the frozen Stage 21 values (B11 from this S2C tile's own clear-pixel brightness), as in Stage 22.
Results: RESDIR/<run>__<variant>.json.
  python run_aco23.py TASKS_JSON RESDIR [--workers N]"""
import json, os, sys, subprocess, shutil, time, glob, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage21", f"{S}/stage23"]
import lazy23 as LZ
os.environ.update(LZ.ENV)                                  # rasterio (in-process TOA reads) and the ACOLITE subprocesses


def _lazy_path(safe, b):
    """toa21.path on a lazy SAFE: the band's public URL from lazy.json (the placeholder itself is empty)."""
    lj = os.path.join(safe, "lazy.json")
    if os.path.exists(lj):
        mp = json.load(open(lj))["map"]; k = next((k for k in mp if "/IMG_DATA/" in k and k.endswith(f"_{b}.jp2")), None)
        return mp[k] if k else None
    f = glob.glob(os.path.join(safe, "GRANULE", "*", "IMG_DATA", f"*_{b}.jp2")); return f[0] if f else None


def corr():
    """The frozen Stage 21 offsets (stage21/run_aco21.corr, verbatim; that module needs the AWS client, this does not)."""
    import hashlib
    F = json.load(open(f"{S}/stage21/FREEZE_STAGE21.json"))
    assert hashlib.sha256(open(f"{S}/stage21/corr21.json", "rb").read()).hexdigest() == F["corr21_sha256"], "corr21 not frozen"
    return json.load(open(f"{S}/stage21/corr21.json"))


def offsets(safe, C=None):
    """stage21/run_aco21.offsets, verbatim, reading the bands through the lazy map."""
    import numpy as np, toa21 as T21
    T21.path = _lazy_path; C = C or corr(); out = {}
    for b, c in C["bands"].items():
        if c["model"] == "M1": out[b] = c["delta"]
        else:
            q, off = T21.meta(safe); x = T21.read(safe, b, q, off, "mean10" if b == "B08" else "native20")
            b10 = T21.read(safe, "B10", q, off, "rep60"); b02 = T21.read(safe, "B02", q, off, "level20")
            out[b] = c["alpha"] + c["beta"] * float(np.nanmedian(x[(b10 < 0.002) & (b02 < 0.3)]))
    return out
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}
WORK = f"{S}/stage23/work"; LAZY = f"{S}/stage23/lazy"; L1R = f"{S}/stage23/l1r"


def run_crop(inp, c, sub, keep, tag, lazy):
    o = dict(OV)
    if c.get("elev") is not None: o["elevation"] = c["elev"]
    if sub: o["_toa_sub"] = sub
    if keep: o["_keep_l1r"] = keep
    wd = f"{WORK}/{tag}"; env = dict(os.environ)
    if lazy: env.update(LZ.ENV)
    p = subprocess.run([ACO, f"{S}/stage22/aco22_one.py", inp, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(o)], capture_output=True, text=True, timeout=3600, env=env)
    shutil.rmtree(wd, ignore_errors=True)
    line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
    return json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-400:]}


def task(t, resdir):
    names = list(t["variants"]); base = names[0]; assert t["variants"][base] is None
    if all(os.path.exists(f"{resdir}/{t['run']}__{v}.json") for v in names): return t["run"], "done"
    t0 = time.time(); msg = []; name = t["source"]["gcsl"]; root = f"{LAZY}/{t['run']}"   # per task: no two tasks share (or delete) a lazy SAFE
    try:
        inp = LZ.build(name, root)
        if any(isinstance(x, str) for x in t["variants"].values()):
            full = offsets(inp)
            pick = {"K1": ("B08", "B8A", "B11", "B12"), "C1": ("B11", "B12"), "C2": ("B08", "B8A")}
            t["variants"] = {v: ({b_: full[b_] for b_ in pick[x.split(":")[1]]} if isinstance(x, str) else x) for v, x in t["variants"].items()}
        recs = {v: {"run": t["run"], "variant": v, "source": name, "toa_sub": t["variants"][v], "crops": [], "pair": t.get("pair")} for v in names}
        for i, c in enumerate(t["crops"]):
            keep = f"{L1R}/{t['run']}_{i}" if len(names) > 1 else None
            r = run_crop(inp, c, None, keep, f"{t['run']}_{i}_{base}", True)
            r.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); recs[base]["crops"].append(r)
            for v in names[1:]:
                kl = glob.glob(f"{keep}/*_L1R.nc")
                if not kl: recs[v]["crops"].append({"error": "no L1R", "lat": c["lat"], "lon": c["lon"]}); continue
                rv = run_crop(kl[0], c, t["variants"][v], None, f"{t['run']}_{i}_{v}", False)
                rv.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); recs[v]["crops"].append(rv)
            if keep: shutil.rmtree(keep, ignore_errors=True)
        for v in names:
            recs[v]["seconds"] = round(time.time() - t0, 1); json.dump(recs[v], open(f"{resdir}/{t['run']}__{v}.json", "w"), default=str)
            ok = sum(1 for c in recs[v]["crops"] for p in (c.get("points") or {}).values() if ((p or {}).get("M0") or {}).get("n", 0) >= 5); msg.append(f"{v}:M0 {ok}")
    except Exception as e:
        msg.append("ERR " + str(e)[:160])
    finally:
        LZ.delete(name, root); shutil.rmtree(root, ignore_errors=True)
    return t["run"], " ".join(msg) + f" | {round(time.time() - t0)}s"


if __name__ == "__main__":
    T = json.load(open(sys.argv[1])); resdir = sys.argv[2]
    for d in (resdir, WORK, LAZY, L1R): os.makedirs(d, exist_ok=True)
    W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    with cf.ThreadPoolExecutor(W) as ex:
        for n, (run, msg) in enumerate(ex.map(lambda t: task(t, resdir), T), 1): print(n, run, msg, flush=True)
    print("ACO23_DONE", flush=True)
