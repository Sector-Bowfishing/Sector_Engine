"""Stage 24 run lists: T24N (new N0513 pairs: S2A A; S2C K0, C1, N2) and T2N_N2 (Stage 23 T2N S2C scenes re-run for N2 only,
into a separate result folder; Stage 23 results untouched)."""
import json, os, sys, hashlib, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage20"]
import safe as SAFE
src = open(f"{S}/stage20/build20.py").read(); ns = {"__name__": "b20"}; exec(src.split('if sys.argv[1] == "prelim":')[0], ns)
crops, elev = ns["crops"], ns["elev"]
D = json.load(open(f"{S}/stage24/derived24.json")); N2 = D["N2"]["offsets"]
md5 = lambda s: hashlib.md5(s.encode()).hexdigest()
P = json.load(open(f"{S}/stage24/pairs24_meta.json"))["pairs"]
def l1c(q): return q, SAFE.l1c_for(q["c"]), SAFE.l1c_for(q["o"])
with cf.ThreadPoolExecutor(8) as ex: L = list(ex.map(l1c, P))
T = []
for q, lc, lo in L:
    if not (lc and lo): continue
    key = f"{q['site']}|{q['o']}|{q['c']}"; cr = crops([(q["lat"], q["lon"], key)]); rid = md5(key)[:12]
    T += [{"run": f"T24N_R_{rid}", "source": {"gcsl": lo}, "crops": cr, "variants": {"A": None}, "pair": q},
          {"run": f"T24N_C_{rid}", "source": {"gcsl": lc}, "crops": cr, "variants": {"K0": None, "C1": "corr21:C1", "N2": dict(N2)}, "pair": q}]
jobs = [c for t in T for c in t["crops"]]
with cf.ThreadPoolExecutor(8) as ex:
    for c, v in zip(jobs, ex.map(lambda c: elev(c["lat"], c["lon"], True), jobs)): c["elev"] = v
json.dump(T, open(f"{S}/stage24/tasks24_T24N.json", "w"))
T2 = [dict(t, variants={"K0": None, "N2": dict(N2)}) for t in json.load(open(f"{S}/stage23/tasks23_T2N.json")) if t["run"].startswith("T2N_C_")]
json.dump(T2, open(f"{S}/stage24/tasks24_T2N_N2.json", "w"))
print("T24N tasks", len(T), "pairs", len(T) // 2, "| T2N N2 tasks", len(T2), "| N2", N2)
