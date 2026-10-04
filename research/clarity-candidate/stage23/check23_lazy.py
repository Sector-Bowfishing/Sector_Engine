"""Stage 23 tooling check (before any Stage 23 reflectance is read): the lazy Google Cloud read (lazy23.py) must
reproduce the full-download ACOLITE samples of Stage 22 exactly. Two Stage 22 FLOOR scenes (one S2A, one S2B; high-latitude,
already seen, not part of Stage 23) are re-run through the frozen instrumented path from a lazy SAFE and compared
value by value with res22_FL. Writes check23_lazy.json."""
import json, os, sys, subprocess, shutil, re
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage23"); import lazy23 as LZ
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}
T = json.load(open(f"{S}/stage22/tasks22_FL.json"))
pick = [next(t for t in T if t["run"].startswith("FL_R_") and os.path.exists(f"{S}/stage22/res22_FL/{t['run']}__A.json")),
        next(t for t in T if t["run"].startswith("FL_C_") and os.path.exists(f"{S}/stage22/res22_FL/{t['run']}__A.json"))]
root = f"{S}/stage23/lazy_check"; out = []
for t in pick:
    name = t["source"]["gcs"]; safe = LZ.build(name, root); c = t["crops"][0]
    o = dict(OV)
    if c.get("elev") is not None: o["elevation"] = c["elev"]
    env = dict(os.environ); env.update(LZ.ENV); env["CPL_VSIL_SHOW_NETWORK_STATS"] = "YES"
    wd = f"{S}/stage23/work/check_{t['run']}"
    p = subprocess.run([ACO, f"{S}/stage22/aco22_one.py", safe, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(o)], capture_output=True, text=True, timeout=3600, env=env)
    shutil.rmtree(wd, ignore_errors=True)
    line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
    new = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-500:]}
    old = json.load(open(f"{S}/stage22/res22_FL/{t['run']}__A.json"))["crops"][0]
    m = re.findall(r'"downloaded_bytes":\s*(\d+)', p.stdout + p.stderr)
    diffs = []
    for k, pt in (old.get("points") or {}).items():
        q = (new.get("points") or {}).get(k) or {}
        for lev in ("M0", "M3"):
            a, b = (pt or {}).get(lev) or {}, q.get(lev) or {}
            for band in set(a) | set(b):
                va, vb = a.get(band), b.get(band)
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)): diffs.append(abs(va - vb))
                elif va != vb: diffs.append(float("inf"))
    out.append({"run": t["run"], "product": name, "n_values": len(diffs), "max_abs_diff": max(diffs) if diffs else None, "error": new.get("error"),
                "network_bytes_reported": [int(x) for x in m][:3]})
    print(out[-1], flush=True)
    LZ.delete(name, root)
json.dump({"checks": out, "identical": all(c["n_values"] > 0 and c["max_abs_diff"] == 0 for c in out)}, open(f"{S}/stage23/check23_lazy.json", "w"), indent=1)
print("IDENTICAL", all(c["n_values"] > 0 and c["max_abs_diff"] == 0 for c in out))
