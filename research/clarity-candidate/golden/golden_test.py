"""Golden test for the frozen Current Clarity candidate (Stage 16 baseline + Stage 17 challenger).

Every check compares against outputs written when the candidate was frozen (Stages 14-18), never against a fresh run
of itself. Run with the research environment (env/bootstrap.sh):
    geo/bin/python golden/golden_test.py [hashes] [models] [selfcheck] [scenes] [all] [--workers N] [--json OUT]

  hashes     every frozen file matches its freeze-time sha256 (after undoing the recorded path rewrite)
  models     in a scratch copy: dev14.py, dev15.py, dev16.py and freeze18.py regenerate dev14*, semantics15.json,
             dev15*, rule16.json, dev16* and challenger17.json byte for byte; a C-gbm refit from the development rows
             reproduces frozen_gbm.pkl (max |difference| 0 over all 1,397 tier-1/2 rows)
  selfcheck  engine14 on every Stage 14 certification row and engine16 on every Stage 16 fresh row, from their stored
             raw inputs: every output field identical to cert14_rows.json / score16_rows.json; plus the
             N:t15769 production-pickle check (p 0.7751, Normal, 5.957 ft)
  scenes     the six development validation scenes through the frozen ACOLITE path (run_cert_aco_a1.py, K4) reproduce
             stage14/cert/validate_res exactly: same pixel counts, max |difference| 0 over every sampled value
Exit status 0 only if every requested check passes."""
import csv, glob, hashlib, json, math, os, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["CLARITY_RESEARCH_ROOT"] = ROOT
PY = sys.executable
SELF_P = 0.7750620848927173   # N:t15769 through frozen_gbm.pkl (tier 1, S2B, 2024-09-24)


def sha_bytes(b): return hashlib.sha256(b).hexdigest()


def unrewrite(data):
    P = json.load(open(f"{ROOT}/provenance/FROZEN_HASH_CHECK.json"))["rules_in_order"]
    for a, b in P: data = data.replace(b.encode(), a.encode())
    return data


# ------------------------------------------------------------------ hashes
def check_hashes():
    H = json.load(open(f"{ROOT}/provenance/FROZEN_HASH_CHECK.json"))["checks"]
    bad, n = [], 0
    for c in H:
        if c["status"] != "ok" or not c.get("file"): continue
        p = os.path.join(ROOT, c["file"]); data = open(p, "rb").read()
        if p.endswith((".py", ".sh")): data = unrewrite(data)
        n += 1
        if sha_bytes(data) != c["frozen_sha256"]: bad.append(c["file"])
    return {"pass": not bad, "files_checked": n, "mismatched": bad}


# ------------------------------------------------------------------ models
REGEN = [("stage14/analysis/dev14.py", ["stage14/analysis/dev14.json", "stage14/analysis/dev14_rows.json"]),
         ("stage15/analysis/dev15.py", ["stage15/engine/semantics15.json", "stage15/analysis/dev15.json", "stage15/analysis/dev15_rows.json"]),
         ("stage16/analysis/dev16.py", ["stage16/engine/rule16.json", "stage16/analysis/dev16.json", "stage16/analysis/dev16_rows.json", "stage16/analysis/dev16_feet.json"]),
         ("stage18/freeze18.py", ["stage18/engine/challenger17.json"])]


def check_models():
    out = {"regenerated": {}, "pass": True}
    tmp = tempfile.mkdtemp(prefix="clarity-golden-")
    try:
        root = os.path.join(tmp, "root")
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("geo", "venv", "src", "safe_cache", "work", "__pycache__", "golden_runs"))
        for a, d, fs in os.walk(root):
            for f in fs: os.chmod(os.path.join(a, f), 0o644)
        env = dict(os.environ, CLARITY_RESEARCH_ROOT=root)
        for script, outs in REGEN:
            t0 = time.time()
            p = subprocess.run([PY, os.path.join(root, script)], cwd=root, env=env, capture_output=True, text=True)
            same = {o: p.returncode == 0 and open(os.path.join(root, o), "rb").read() == open(os.path.join(ROOT, o), "rb").read() for o in outs}
            out["regenerated"][script] = {"exit": p.returncode, "seconds": round(time.time() - t0, 1), "identical": same,
                                          **({"stderr": p.stderr[-400:]} if p.returncode else {})}
            out["pass"] &= p.returncode == 0 and all(same.values())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.path[:0] = [f"{ROOT}/stage14/engine", f"{ROOT}/stage14/analysis"]
    import numpy as np, engine14 as E14, lib14 as L14
    ALL, t1, t2, rest = L14.dev_rows()
    g = L14.fit_gbm(t1); te = t1 + t2
    a = np.array(L14.pred_gbm(g, te)); b = E14.G.predict(np.array([L14.L.f7(x) for x in te]))
    out["refit"] = {"train_rows": len(t1), "compared_rows": len(te), "max_abs_diff": float(np.max(np.abs(a - b)))}
    out["pass"] &= out["refit"]["max_abs_diff"] == 0.0 and len(te) == 1397
    return out


# ------------------------------------------------------------------ selfcheck
def _sen_outputs(paths, want):
    X = {}
    for p in paths:
        if "discarded" in p: continue
        for r in csv.DictReader(open(p)):
            k = (r["id"], r.get("item"))
            if k in want and not r.get("error"):
                try: nv = int(float(r.get("n_valid") or 0))
                except ValueError: continue
                if k not in X or nv > X[k][0]: X[k] = (nv, r)
    return X


def _aco(paths):
    A = {}
    for f in paths:
        r = json.load(open(f))
        for c in r.get("crops", []):
            for pid, pt in (c.get("points") or {}).items(): A[(pid, r["item"])] = pt
    return A


g_ = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None
sen_of = lambda xr: {"blue": g_(xr, "rho_blue_v"), "green": g_(xr, "rho_green_v"), "red": g_(xr, "rho_red_v"), "re1": g_(xr, "rho_rededge1_v"), "swir16": g_(xr, "rho_swir16_v")} if xr else None
norm = lambda o: json.loads(json.dumps(o, default=str))


def engine_inputs_cert14():
    C = f"{ROOT}/stage14/cert"
    smp = [dict(r, part="NLA" if r["src"].startswith("NLA") else "SYKE") for r in csv.DictReader(open(f"{ROOT}/stage13/cert/blind_sample13.csv"))]
    smp += [dict(r, part="WQP") for r in csv.DictReader(open(f"{C}/wqp_sample.csv"))]
    OUTS = sorted(glob.glob(f"{ROOT}/stage12/cert/out_*.csv")) + [f"{ROOT}/stage13/cert/out13_c1.csv", f"{ROOT}/stage13/cert/out13_legacy.csv", f"{C}/out_wqp_c1.csv", f"{C}/out_wqp_legacy.csv"]
    X = _sen_outputs(OUTS, {(r["id"], r["item"]) for r in smp}); A = _aco(glob.glob(f"{C}/res_ns/*.json") + glob.glob(f"{C}/res_wqp/*.json"))
    for r in smp:
        xr = X.get((r["id"], r["item"]), (0, {}))[1]; pt = A.get((r["id"], r["item"])) or {}
        yield r["id"], (pt.get("M0"), pt.get("M3"), sen_of(xr), g_(xr, "sun_elev") if xr else None, r.get("platform") or xr.get("platform") or "")


def engine_inputs_fresh16():
    D = f"{ROOT}/stage16/fresh"; smp = list(csv.DictReader(open(f"{D}/fresh_sample.csv")))
    X = _sen_outputs([f"{D}/out_fresh_c1.csv"], {(r["id"], r["item"]) for r in smp}); A = _aco(glob.glob(f"{D}/res_fresh/*.json"))
    for r in smp:
        xr = X.get((r["id"], r["item"]), (0, {}))[1]; pt = A.get((r["id"], r["item"])) or {}
        yield r["id"], (pt.get("M0"), pt.get("M3"), sen_of(xr), g_(xr, "sun_elev") if xr else None, r["platform"])


def check_selfcheck():
    sys.path[:0] = [f"{ROOT}/stage14/engine", f"{ROOT}/stage16/engine", f"{ROOT}/stage14/analysis", f"{ROOT}/stage16/analysis"]
    import engine14 as E14, engine16 as E16, lib14 as L14
    out = {}
    F14 = {r["id"]: r for r in json.load(open(f"{ROOT}/stage14/analysis/cert14_rows.json"))}
    keys = ("tier", "authority", "p", "hard", "state", "feet", "interval")
    n = bad = 0
    for i, args in engine_inputs_cert14():
        if i not in F14: continue
        a = norm(E14.answer(*args)); a["interval"] = a.pop("interval_ft"); n += 1
        if any(a[k] != F14[i][k] for k in keys): bad += 1
    out["engine14_cert_rows"] = {"rows": n, "mismatched": bad}
    F16 = {r["id"]: r for r in json.load(open(f"{ROOT}/stage16/analysis/score16_rows.json"))}
    n16 = bad16 = 0
    for i, args in engine_inputs_fresh16():
        if i not in F16: continue
        n16 += 1
        if norm(E16.answer16(*args)) != F16[i]["o"]: bad16 += 1
    out["engine16_fresh_rows"] = {"rows": n16, "mismatched": bad16}
    ALL = L14.dev_rows()[0]; x = next(r for r in ALL if r["id"] == "N:t15769")
    a = E14.answer(x["aco"], None, None, x["sun_elev"], x["platform"])
    out["N:t15769"] = {"p": a["p"], "state": a["state"], "feet": round(a["feet"], 3), "expected_p": SELF_P}
    out["pass"] = (n > 1000 and bad == 0 and n16 == 108 and bad16 == 0 and a["p"] == SELF_P and a["state"] == "Normal" and round(a["feet"], 3) == 5.957)
    return out


# ------------------------------------------------------------------ scenes
def compare_res(a, b):
    """-> (values compared, max |diff|, structural differences)."""
    n, mx, diffs = 0, 0.0, []
    if (a.get("l1c"), a.get("error")) != (b.get("l1c"), b.get("error")): diffs.append(("l1c/error", a.get("l1c"), b.get("l1c")))
    if len(a["crops"]) != len(b["crops"]): diffs.append(("crops", len(a["crops"]), len(b["crops"]))); return n, mx, diffs
    for ca, cb in zip(a["crops"], b["crops"]):
        if set(ca.get("points") or {}) != set(cb.get("points") or {}) or ca.get("error") != cb.get("error"): diffs.append(("points", ca.get("error"), cb.get("error"))); continue
        for k, p in (ca.get("points") or {}).items():
            q = cb["points"][k]
            if set(p) != set(q): diffs.append((k, "variants")); continue
            for v in p:
                x, y = p[v], q[v]
                if not isinstance(x, dict):
                    if x != y: diffs.append((k, v, x, y))
                    continue
                if set(x) != set(y): diffs.append((k, v, "fields")); continue
                for f in x:
                    if isinstance(x[f], float) and isinstance(y[f], float):
                        n += 1; mx = max(mx, abs(x[f] - y[f]))
                    elif x[f] != y[f]: diffs.append((k, v, f, x[f], y[f]))
    return n, mx, diffs


def check_scenes(workers=3):
    tasks = f"{ROOT}/stage14/cert/validate_tasks.json"; want = f"{ROOT}/stage14/cert/validate_res"
    res = os.path.join(ROOT, "golden_runs", time.strftime("%Y%m%dT%H%M%S"))
    t0 = time.time()
    p = subprocess.run([PY, f"{ROOT}/stage14/cert/run_cert_aco_a1.py", tasks, res, "--workers", str(workers)], capture_output=True, text=True)
    out = {"exit": p.returncode, "seconds": round(time.time() - t0, 1), "scenes": {}, "values": 0, "max_abs_diff": 0.0}
    ok = p.returncode == 0 and "CERT_ACO_DONE" in p.stdout
    for t in json.load(open(tasks)):
        f = f"{t['item']}.json"
        if not os.path.exists(os.path.join(res, f)): out["scenes"][t["item"]] = "missing"; ok = False; continue
        n, mx, diffs = compare_res(json.load(open(os.path.join(res, f))), json.load(open(os.path.join(want, f))))
        out["scenes"][t["item"]] = {"values": n, "max_abs_diff": mx, "structural_diffs": diffs[:5]}
        out["values"] += n; out["max_abs_diff"] = max(out["max_abs_diff"], mx); ok &= mx == 0.0 and not diffs and n > 0
    if not ok: out["stdout_tail"] = p.stdout[-600:] + p.stderr[-600:]
    out["pass"] = ok and out["values"] == 264
    shutil.rmtree(res, ignore_errors=True)
    return out


def main(argv):
    want = [a for a in argv if not a.startswith("--") and not a.isdigit() and not a.endswith(".json")] or ["all"]
    if "all" in want: want = ["hashes", "models", "selfcheck", "scenes"]
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 3
    R = {"root": ROOT, "python": sys.version.split()[0], "platform": sys.platform, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    fns = {"hashes": check_hashes, "models": check_models, "selfcheck": check_selfcheck, "scenes": lambda: check_scenes(workers)}
    for w in want:
        R[w] = fns[w](); print(w, "PASS" if R[w]["pass"] else "FAIL", flush=True)
    R["GOLDEN_TEST_PASS"] = all(R[w]["pass"] for w in want)
    s = json.dumps(R, indent=1, default=str)
    if "--json" in argv: open(argv[argv.index("--json") + 1], "w").write(s)
    print(s)
    return 0 if R["GOLDEN_TEST_PASS"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
