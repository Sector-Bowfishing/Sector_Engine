"""Stage 21 held-out tandem (select21.json split H), after the correction freeze: per tile-date one S2A download (Google
Cloud) and one real nominal S2C download (AWS), then
  1. the held-out TOA check: toa21.stats raw, and with the frozen offsets removed (residual water offset per band);
  2. the frozen ACOLITE path on S2A (A), raw S2C (C0) and corrected S2C (C1, frozen corr21 offsets), same crops;
then both downloads are deleted. Results: toa21_H/<tile>_<date>.json, res_tandem21/<run>.json.
  python th21.py [--workers N]"""
import json, os, sys, hashlib, shutil, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage21"]
import run_aco21 as RA, toa21 as T21, fetch21 as F21
import safe as SAFE
C = RA.corr()                                          # asserts corr21.json is the frozen one
T = json.load(open(f"{S}/stage21/tasks21_tandem.json"))
by = {}
for t in T: by.setdefault(t["run"].split("_", 1)[1], {})[t["run"].split("_", 1)[0]] = t
OUT = f"{S}/stage21/toa21_H"; RES = f"{S}/stage21/res_tandem21"
for d in (OUT, RES, f"{S}/stage21/work", RA.WORK): os.makedirs(d, exist_ok=True)
W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3


def tile(key):
    g = by[key]; o = f"{OUT}/{key}.json"
    if os.path.exists(o) and all(os.path.exists(f"{RES}/{g[k]['run']}.json") for k in g): return key, "done"
    a = c = None
    try:
        a = SAFE.fetch(g["A"]["l1c"]); c = F21.fetch(g["C0"]["aws"], RA.WORK)
        if not os.path.exists(o):
            sub = RA.offsets(c, C)
            r = {"tile": key, "raw": T21.stats(a, c), "corrected": T21.stats(a, c, delta=sub), "offsets": sub}
            json.dump(r, open(o, "w"))
        msgs = [RA.one(g["A"], RES, a)[1], RA.one(g["C0"], RES, c)[1], RA.one(g["C1"], RES, c)[1]]
        msg = " | ".join(msgs)
    except Exception as e:
        msg = "ERR " + str(e)[:160]
    finally:
        SAFE.delete(g["A"]["l1c"])
        if c: shutil.rmtree(c, ignore_errors=True)
    return key, msg + f" | AWS {F21.billed_gb():.1f} GB"


with cf.ThreadPoolExecutor(W) as ex:
    for n, (k, m) in enumerate(ex.map(tile, sorted(by)), 1): print(n, k, m, flush=True)
print("TH21_DONE", flush=True)
