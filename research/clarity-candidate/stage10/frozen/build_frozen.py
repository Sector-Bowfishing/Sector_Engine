"""Stage 10: freeze the benchmarks for fresh validation. Deterministic; reads Stage 7/8 inputs only.
C3 is fitted ONCE on every historical clean row (national + Guntersville), exactly Stage 7's form, and
its validated input domain is taken from those training INPUTS (no Secchi enters the domain).
C6 is Stage 8's c6_model.json (copied, not refitted). The champion is secchi-power-v1."""
import io, contextlib, runpy, json, math, os, shutil, filecmp, hashlib
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D7, D10 = f"{S}/stage7", f"{S}/stage10/frozen"
os.makedirs(f"{D10}/_s7_check", exist_ok=True)
for f in ("results.json", "tables.json"): shutil.copy(f"{D7}/{f}", f"{D10}/_s7_check/{f}")
cwd = os.getcwd(); os.chdir(D7)
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path(f"{D7}/research.py")
os.chdir(cwd)
same = {f: filecmp.cmp(f"{D7}/{f}", f"{D10}/_s7_check/{f}", shallow=False) for f in ("results.json", "tables.json")}
Nc, Gc, fit = g["Nc"], g["Gc"], g["fit"]
train = Nc + Gc
beta = fit(train, "C3")
def pct(v, q): return float(np.percentile(v, q))
lo_b = [math.log10(r["red"]) for r in train if r["ndci"] <= 0]
hi_b = [math.log10(r["red"]) for r in train if r["ndci"] > 0]
nd = [r["ndci"] for r in train]
out = {"model": "C3", "form": "log10 Secchi_ft = [1-a, (1-a)*log10(R), a, a*log10(R)] . beta, a = 1 if NDCI > 0 else 0; "
                             "R = max(rho_B04, 0.001), NDCI from max(rho,0.001) of B05/B04 (Stage 7 feats)",
       "fittedOn": {"national": len(Nc), "guntersville": len(Gc)}, "beta": [float(x) for x in beta],
       "domain": {"note": "1st-99th percentile of the training INPUTS; outside = refuse (never clamp)",
                  "log10R_ndciLE0": [round(pct(lo_b, 1), 4), round(pct(lo_b, 99), 4)],
                  "log10R_ndciGT0": [round(pct(hi_b, 1), 4), round(pct(hi_b, 99), 4)],
                  "ndci": [round(pct(nd, 1), 4), round(pct(nd, 99), 4)],
                  "outputFt": [0.5, 20.0]},
       "stage7FilesReproduced": same}
json.dump(out, open(f"{D10}/c3_frozen.json", "w"), indent=1)
shutil.copy(f"{S}/stage8/c6_model.json", f"{D10}/c6_model.json")
print(json.dumps(out, indent=1))
