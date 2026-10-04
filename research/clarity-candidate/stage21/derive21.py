"""Stage 21 section 3a on the DERIVATION tandem tiles only (select21.json split D): pixel-paired TOA statistics
(toa21.stats), then the pre-registered offset model (M1 constant; M2 only if both tests pass on TD), frozen into
corr21.json and FREEZE_STAGE21.json. S2A from Google Cloud (free); S2C real nominal from AWS (requester pays; only the
bands the statistics need + qi masks). Every download is deleted after use. No Secchi value is read.
  python derive21.py [--workers N]"""
import json, os, sys, hashlib, datetime, shutil, concurrent.futures as cf
import numpy as np
from scipy.stats import theilslopes, spearmanr
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage21"]
import safe as SAFE, fetch21 as F21, toa21 as T21
F = json.load(open(f"{S}/stage21/FREEZE_STAGE21.json"))
assert hashlib.sha256(open(f"{S}/stage21/PREREGISTRATION_STAGE21.md", "rb").read()).hexdigest() == F["prereg_sha256"]
SEL = [t for t in json.load(open(f"{S}/stage21/select21.json")) if t["split"] == "D"]
OUT = f"{S}/stage21/toa21_D"; os.makedirs(OUT, exist_ok=True); WORK = f"{S}/stage21/work_aws"; os.makedirs(WORK, exist_ok=True)
SKIP_A = ("HTML/", "rep_info/", "preview", "_TCI.jp2", "_B01.jp2", "_B04.jp2", "_B06.jp2", "_B07.jp2", "_B09.jp2")
CB = ["B02", "B05", "B08", "B8A", "B10", "B11", "B12"]
W = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3


def one(t):
    o = f"{OUT}/{t['tile']}_{t['date']}.json"
    if os.path.exists(o): return t["tile"], "done"
    try:
        a = SAFE.fetch(t["s2a_l1c"], SKIP_A); c = F21.fetch(t["s2c"], WORK, CB, qi=True)
        r = {"tile": t["tile"], "date": t["date"], "datatake": t["datatake"], "s2a": t["s2a_l1c"], "s2c": t["s2c"]["product"], **T21.stats(a, c)}
    except Exception as e:
        r = {"tile": t["tile"], "date": t["date"], "error": str(e)[:300]}
    finally:
        SAFE.delete(t["s2a_l1c"]); shutil.rmtree(os.path.join(WORK, t["s2c"]["product"] + ".SAFE"), ignore_errors=True)
    json.dump(r, open(o, "w")); return t["tile"], f"water {r.get('n_water')} err {r.get('error', '')[:60]} | AWS {F21.billed_gb():.1f} GB"


if "--fit-only" not in sys.argv:
    with cf.ThreadPoolExecutor(W) as ex:
        for n, (tile, msg) in enumerate(ex.map(one, SEL), 1): print(n, tile, msg, flush=True)
R = [json.load(open(f"{OUT}/{t['tile']}_{t['date']}.json")) for t in SEL]
use = [r for r in R if not r.get("error") and r.get("n_water", 0) >= 200]
corr = {"n_tiles_D": len(SEL), "n_tiles_used": len(use), "n_errors": sum(1 for r in R if r.get("error")), "bands": {}}
for b in T21.CORR:
    d = np.array([r["bands"][b]["delta_tile"] for r in use]); m = np.array([r["bands"][b]["m_C"] for r in use])
    m1 = float(np.median(d)); mad1 = float(np.median(np.abs(d - m1)))
    rho = float(spearmanr(d, m).correlation); sl, ic, _, _ = theilslopes(d, m); mad2 = float(np.median(np.abs(d - (ic + sl * m))))
    m2 = abs(rho) >= 0.5 and mad2 <= 0.75 * mad1
    corr["bands"][b] = {"model": "M2" if m2 else "M1", "delta": m1, "alpha": float(ic), "beta": float(sl), "spearman": rho, "mad_M1": mad1, "mad_M2": mad2,
                        "delta_tile_iqr": [float(np.percentile(d, 25)), float(np.percentile(d, 75))], "n": int(d.size)}
corr["b05_l2w"] = {"g": 1.0332, "k": -0.0397, "source": "stage20/srf20.json sbaf_S2C_to_S2A B05 (rounded as pre-registered)"}
json.dump(corr, open(f"{S}/stage21/corr21.json", "w"), indent=1)
F["corr21_sha256"] = hashlib.sha256(open(f"{S}/stage21/corr21.json", "rb").read()).hexdigest()
F["correction_frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); F["aws_gb_after_derivation"] = F21.billed_gb()
json.dump(F, open(f"{S}/stage21/FREEZE_STAGE21.json", "w"), indent=1)
print("FROZEN", json.dumps(corr["bands"], indent=0)[:1500], "| AWS GB", round(F21.billed_gb(), 2))
