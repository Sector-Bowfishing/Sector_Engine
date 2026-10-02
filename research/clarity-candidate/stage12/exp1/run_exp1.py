"""Stage 12 Part 1 driver (geo env): per scene, fetch the L1C once, run each frozen candidate (K0-K4, section 1),
sample, delete. AERONET-OC and representative scenes run K1-K4 (K0 is Stage 11's) plus K0 on 3 reproducibility
scenes; guard scenes run K0-K4. One result file per scene in exp1/res/. 4 scenes in parallel."""
import json, os, sys, subprocess, time, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
D = f"{S}/stage12/exp1"; os.makedirs(f"{D}/res", exist_ok=True); os.makedirs(f"{S}/stage12/work", exist_ok=True)
K = {"K0": {}, "K1": {"dsf_interface_reflectance": True, "dsf_interface_option": "default"},
     "K2": {"dsf_interface_reflectance": True, "dsf_interface_option": "6sv"},
     "K3": {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_toa"},
     "K4": {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa"}}


def tasks():
    first = {}
    for j in json.load(open(f"{S}/stage11/ac/jobs_aeronet.json")):
        first.setdefault(j["job"], j)
    G = json.load(open(f"{D}/guard.json"))
    T = []
    repro = sorted(first)[:: max(1, len(first) // 3)][:3]
    for name, j in first.items():
        T.append({"task": name, "kind": "aeronet", "c1": j["c1"], "lat": j["lat"], "lon": j["lon"], "points": j["points"],
                  "configs": (["K0"] if name in repro else []) + ["K1", "K2", "K3", "K4"]})
    for j in G["repr"]:
        T.append({"task": j["job"], "kind": "repr", "c1": j["c1"], "lat": j["lat"], "lon": j["lon"], "points": j["points"], "configs": ["K1", "K2", "K3", "K4"]})
    for j in G["guard"]:
        T.append({"task": j["job"], "kind": "guard", "c1": j["c1"], "lat": j["lat"], "lon": j["lon"], "points": j["points"], "configs": list(K)})
    return T


def one(t):
    out = f"{D}/res/{t['task'].replace('|', '_')}.json"
    r = json.load(open(out)) if os.path.exists(out) else {"task": t["task"], "kind": t["kind"], "configs": {}}
    need = [k for k in t["configs"] if k not in r["configs"]]
    if not need: return t["task"], "done"
    t0 = time.time()
    try:
        name = SAFE.l1c_for(t["c1"]); r["l1c"] = name
        if not name: r["error"] = "no L1C"; json.dump(r, open(out, "w")); return t["task"], "no L1C"
        path = SAFE.fetch(name)
        for k in need:
            wd = f"{S}/stage12/work/{t['task'].replace('|', '_')}_{k}"
            p = subprocess.run([ACO, f"{S}/stage12/tools/aco12_one.py", path, str(t["lat"]), str(t["lon"]), wd, json.dumps(t["points"]), json.dumps(K[k])],
                               capture_output=True, text=True, timeout=3600)
            line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
            r["configs"][k] = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-400:]}
            json.dump(r, open(out, "w"), default=str)
        SAFE.delete(name)
    except Exception as e:
        r["error"] = str(e)[:300]
    r["seconds"] = round(time.time() - t0, 1)
    json.dump(r, open(out, "w"), default=str)
    return t["task"], f"{r['seconds']}s " + " ".join(f"{k}:{'ok' if r['configs'].get(k, {}).get('points') else 'ERR'}" for k in t["configs"])


if __name__ == "__main__":
    T = tasks()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only == "--probe":
        T = T[:1]
    print(len(T), "tasks", flush=True)
    with cf.ProcessPoolExecutor(4 if only != "--probe" else 1) as ex:
        for name, msg in ex.map(one, T):
            print(name, msg, flush=True)
    print("EXP1_DONE", flush=True)
