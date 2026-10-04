"""Stage 23: run lists from pairs23_meta.json (metadata only). PREREGISTRATION_STAGE23.md section 2.
  FL23   the mid-latitude S2A <-> S2B floor: every TANDEM candidate (same relative orbit, the Jan-Feb 2026 S2A/S2B tandem,
         ~30 s apart) plus ADJACENT-track candidates (~10 min apart) in md5("stage23|floor|site|date") order, at most 3 per
         lake, to 240 pairs in all. FL23X = the next 120 adjacent candidates in the same order (used only under the
         pre-registered extension rule).
  T2N    every N0513 S2C -> S2A 2-day same-track candidate (S2C: K0 + C1; S2A: A).
Writes tasks23_{FL23,FL23X,T2N}.json."""
import json, os, sys, hashlib, collections, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage20"]
import safe as SAFE
src = open(f"{S}/stage20/build20.py").read(); ns = {"__name__": "b20"}; exec(src.split('if sys.argv[1] == "prelim":')[0], ns)
crops, elev = ns["crops"], ns["elev"]
P = json.load(open(f"{S}/stage23/pairs23_meta.json"))["pairs"]
md5 = lambda s: hashlib.md5(s.encode()).hexdigest()


def with_elev(T):
    jobs = [c for t in T for c in t["crops"]]
    with cf.ThreadPoolExecutor(8) as ex:
        for c, v in zip(jobs, ex.map(lambda c: elev(c["lat"], c["lon"], True), jobs)): c["elev"] = v
    return T


def pair_tasks(Q, prefix, s2c):
    def l1c(q): return q, SAFE.l1c_for(q["c"]), SAFE.l1c_for(q["o"])
    with cf.ThreadPoolExecutor(8) as ex: L = list(ex.map(l1c, Q))
    T = []
    for q, lc, lo in L:
        if not (lc and lo): q["l1c_missing"] = True; continue
        key = f"{q['site']}|{q['o']}|{q['c']}"; cr = crops([(q["lat"], q["lon"], key)]); rid = md5(key)[:12]
        T += [{"run": f"{prefix}_R_{rid}", "source": {"gcsl": lo}, "crops": cr, "variants": {"A": None}, "pair": q},
              {"run": f"{prefix}_C_{rid}", "source": {"gcsl": lc}, "crops": cr, "variants": ({"K0": None, "C1": "corr21:C1"} if s2c else {"A": None}), "pair": q}]
    return with_elev(T)


F = [p for p in P if p["kind"] == "FLOOR23"]
for p in F: p["subtype"] = "tandem" if p["c_orbit"] == p["o_orbit"] else "adjacent"
tandem = sorted([p for p in F if p["subtype"] == "tandem"], key=lambda p: md5(f"stage23|floor|{p['site']}|{p['c_time'][:10]}"))
adj = sorted([p for p in F if p["subtype"] == "adjacent"], key=lambda p: md5(f"stage23|floor|{p['site']}|{p['c_time'][:10]}"))
cnt = collections.Counter(p["site"] for p in tandem); A, X = [], []
for p in adj:
    if cnt[p["site"]] >= 3: continue
    if len(tandem) + len(A) < 240: A.append(p); cnt[p["site"]] += 1
    elif len(X) < 120: X.append(p); cnt[p["site"]] += 1
out = {"FL23": pair_tasks(tandem + A, "FL23", False), "FL23X": pair_tasks(X, "FL23X", False),
       "T2N": pair_tasks([p for p in P if p["kind"] == "T2N"], "T2N", True)}
for k, T in out.items():
    json.dump(T, open(f"{S}/stage23/tasks23_{k}.json", "w"))
    Q = [t["pair"] for t in T if "_R_" in t["run"]]
    print(k, "pairs", len(Q), "lakes", len({q["site"] for q in Q}), "regions", dict(collections.Counter(q["region"] for q in Q)),
          "subtypes", dict(collections.Counter(q.get("subtype") for q in Q)), "no elev", sum(1 for t in T for c in t["crops"] if c.get("elev") is None))
