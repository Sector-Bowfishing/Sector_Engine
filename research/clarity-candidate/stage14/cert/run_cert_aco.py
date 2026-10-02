"""Stage 14 certification: the frozen ACOLITE path on every matched certification observation (value-blind).
One task per Sentinel-2 L2A match item; the L1C is fetched once from the Google bucket; one ACOLITE K4 run per crop
(+-0.08 lat, +-0.10 lon around the first station not yet covered) with lake-elevation pressure and l2w_mask=False;
each station sampled under the default mask (M0 = tier 1) and the relaxed mask M3 (tier 2), 60 m disk, >= 5 pixels.
S2C harmonisation (V-rho_w) is applied later, at scoring, exactly as in Stages 12-13. Outputs deleted after sampling.
  python run_cert_aco.py TASKS_JSON RESDIR [--workers N] [--limit N]"""
import json, os, sys, subprocess, time, shutil, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}     # K4, mask off for M0/M3 sampling


def l1c_name(t):
    """C1 items carry the sensing time in the id; legacy items (S2B_15SWS_20170906_0_L2A) use the matched pass time."""
    item = t["item"]
    if "T" in item.split("_")[2]:
        return SAFE.l1c_for(item)
    sat, tile, day = item.split("_")[0], item.split("_")[1], item.split("_")[2]
    cands = SAFE.listing(tile, f"{sat}_MSIL1C_{day}")
    if not cands: return None
    pt = (t.get("pass_time") or "")[11:19].replace(":", "")
    if len(pt) != 6: return cands[0] if len(cands) == 1 else None
    sec = lambda s: int(s[:2]) * 3600 + int(s[2:4]) * 60 + int(s[4:6])
    best = min(cands, key=lambda n: (abs(sec(n.split("_")[2][9:15]) - sec(pt)), -int(n.split("_")[3][1:])))
    return best if abs(sec(best.split("_")[2][9:15]) - sec(pt)) < 3600 else None


def one(t, resdir):
    out = f"{resdir}/{t['item']}.json"
    if os.path.exists(out): return t["item"], "done"
    r = {"item": t["item"], "crops": []}; t0 = time.time()
    try:
        name = l1c_name(t); r["l1c"] = name
        if not name:
            r["error"] = "no L1C"
        else:
            path = SAFE.fetch(name)
            for i, c in enumerate(t["crops"]):
                ov = dict(OV)
                if c.get("elev") is not None: ov["elevation"] = c["elev"]
                wd = f"{S}/stage14/work/c_{t['item']}_{i}"
                p = subprocess.run([ACO, f"{S}/stage13/tools/aco13_one.py", path, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(ov)],
                                   capture_output=True, text=True, timeout=3600)
                line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
                rec = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-300:]}
                rec.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")})
                r["crops"].append(rec)
                shutil.rmtree(wd, ignore_errors=True)
            SAFE.delete(name)
    except Exception as e:
        r["error"] = str(e)[:300]
    r["seconds"] = round(time.time() - t0, 1)
    json.dump(r, open(out, "w"), default=str)
    ok = sum(1 for c in r["crops"] for p in (c.get("points") or {}).values() if ((p or {}).get("M0") or {}).get("n", 0) >= 5)
    ok3 = sum(1 for c in r["crops"] for p in (c.get("points") or {}).values() if ((p or {}).get("M3") or {}).get("n", 0) >= 5)
    return t["item"], f"{r['seconds']}s crops {len(r['crops'])} M0 {ok} M3 {ok3}" + (" ERR " + r["error"][:80] if r.get("error") else "")


if __name__ == "__main__":
    T = json.load(open(sys.argv[1])); resdir = sys.argv[2]; os.makedirs(resdir, exist_ok=True); os.makedirs(f"{S}/stage14/work", exist_ok=True)
    W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    if "--limit" in sys.argv: T = T[:int(sys.argv[sys.argv.index("--limit") + 1])]
    print(len(T), "items,", sum(len(t["crops"]) for t in T), "crops,", sum(len(c["points"]) for t in T for c in t["crops"]), "stations", flush=True)
    with cf.ProcessPoolExecutor(W) as ex:
        for n, (item, msg) in enumerate(ex.map(one, T, [resdir] * len(T)), 1):
            print(n, item, msg, flush=True)
    print("CERT_ACO_DONE", flush=True)
