"""Stage 22: run lists (PREREGISTRATION_STAGE22.md section 2). Writes tasks22_{TD,TH,T2,S,FL,truth}.json."""
import json, os, sys, hashlib, collections, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage20"]
import safe as SAFE
from lib20 import split
src = open(f"{S}/stage20/build20.py").read(); ns = {"__name__": "b20"}; exec(src.split('if sys.argv[1] == "prelim":')[0], ns)
crops, elev = ns["crops"], ns["elev"]
C21 = json.load(open(f"{S}/stage21/corr21.json"))["bands"]
SEL = json.load(open(f"{S}/stage21/select21.json"))
def var_from(off): return {"K0": None, "K1": dict(off), "C1": {b: off[b] for b in ("B11", "B12")}, "C2": {b: off[b] for b in ("B08", "B8A")}}
def stage21_off(m_c):
    o = {b: c["delta"] for b, c in C21.items()}; c = C21["B11"]; o["B11"] = c["alpha"] + c["beta"] * m_c; return o
def with_elev(T):
    jobs = [c for t in T for c in t["crops"]]
    with cf.ThreadPoolExecutor(8) as ex:
        for c, v in zip(jobs, ex.map(lambda c: elev(c["lat"], c["lon"], not str(c["points"][0][2]).startswith(("G:", "H:"))), jobs)): c["elev"] = v
    return T
out = {}
# ---- winter tandem TD / TH
for sp, statdir in (("D", "toa21_D"), ("H", "toa21_H")):
    T = []
    for t in [t for t in SEL if t["split"] == sp]:
        key = f"{t['tile']}_{t['date']}"; f = f"{S}/stage21/{statdir}/{key}.json"
        if not os.path.exists(f): continue
        st = json.load(open(f))
        if sp == "D":
            if st.get("error") or st.get("n_water", 0) < 1: continue
            off = stage21_off(st["bands"]["B11"]["m_C"])
        else:
            off = st["offsets"]
        pts = [(s["lat"], s["lon"], f"{s['site']}|{s['s2a']}|{s['s2c']}") for s in t["sites"]]; cr = crops(pts)
        T += [{"run": f"W{sp}_A_{key}", "source": {"gcs": t["s2a_l1c"]}, "crops": cr, "variants": {"A": None}},
              {"run": f"W{sp}_C_{key}", "source": {"aws": t["s2c"]}, "crops": cr, "variants": var_from(off), "keep_l1r": sp == "D"}]
    out[f"T{sp}"] = with_elev(T)
P = json.load(open(f"{S}/stage22/pairs22_meta.json"))
def pair_tasks(Q, prefix, s2c=True):
    T = []
    for q in Q:
        lc, lo = SAFE.l1c_for(q["c"]), SAFE.l1c_for(q["o"])
        if not (lc and lo): continue
        key = f"{q['site']}|{q['o']}|{q['c']}"; cr = crops([(q["lat"], q["lon"], key)]); rid = hashlib.md5(key.encode()).hexdigest()[:12]
        T += [{"run": f"{prefix}_R_{rid}", "source": {"gcs": lo}, "crops": cr, "variants": {"A": None}, "pair": q},
              {"run": f"{prefix}_C_{rid}", "source": {"gcs": lc}, "crops": cr, "variants": ({"K0": None, "K1": "corr21:K1", "C1": "corr21:C1", "C2": "corr21:C2"} if s2c else {"A": None}), "pair": q}]
    return with_elev(T)
# ---- T2: 80 per year in md5 order, split by S2C datatake
T2 = []
for y in ("2025", "2026"):
    Q = sorted([p for p in P if p["kind"] == "T2" and p["c_time"][:4] == y], key=lambda p: hashlib.md5(f"stage22|{p['site']}|{y}".encode()).hexdigest())[:80]; T2 += Q
cnt = collections.Counter(f"{p['c_time'][:10]}|{p['c_orbit']}" for p in T2); d, h = split(cnt)
for p in T2: p["split"] = "T2D" if f"{p['c_time'][:10]}|{p['c_orbit']}" in d else "T2H"
out["T2"] = pair_tasks(T2, "T2")
# ---- S: Hazen same-day, open-water window, both <= 20% cloud
SQ = [p for p in P if p["kind"] == "S" and "-07-15" <= p["c_time"][4:10] <= "-09-15" and p["c_cloud"] <= 20 and p["o_cloud"] <= 20]
for p in SQ: p["split"] = "S"
out["S"] = pair_tasks(SQ, "S")
# ---- FLOOR: same-day S2A <-> S2B, 60 in md5 order
FQ = sorted([p for p in P if p["kind"] == "FLOOR"], key=lambda p: hashlib.md5(f"stage22|floor|{p['site']}|{p['c_time']}".encode()).hexdigest())[:60]
for p in FQ: p["split"] = "FLOOR"
out["FL"] = pair_tasks(FQ, "FL", s2c=False)
# ---- truth S2C scenes (validation only, read after the cand22 freeze)
T = []
for t in json.load(open(f"{S}/stage21/tasks21_s2c.json")):
    if not t["run"].startswith("K0_"): continue
    T.append({"run": f"TR_{t['l1c']}", "source": {"gcs": t["l1c"]}, "crops": t["crops"], "variants": {"K0": None, "K1": "corr21:K1", "C1": "corr21:C1", "C2": "corr21:C2"}})
out["truth"] = T
for k, T in out.items():
    json.dump(T, open(f"{S}/stage22/tasks22_{k}.json", "w"))
    print(k, "tasks", len(T), "crops", sum(len(t["crops"]) for t in T), "points", sum(len(c["points"]) for t in T for c in t["crops"]), "no elev", sum(1 for t in T for c in t["crops"] if c.get("elev") is None))
print("T2 split", collections.Counter(p["split"] for p in T2), "| S pairs", len(SQ), "sites", len({p["site"] for p in SQ}), "| FLOOR", len(FQ), "sites", len({p["site"] for p in FQ}))
